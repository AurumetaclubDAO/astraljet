import json
import sqlite3
import sys
from contextlib import contextmanager
from .models import now


class Journal:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lockfile = None
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS signals (
              idempotency_key TEXT PRIMARY KEY, timestamp TEXT NOT NULL,
              strategy TEXT, symbol TEXT, asset_type TEXT, direction TEXT,
              score TEXT, entry REAL, stop REAL, target REAL, status TEXT,
              reason TEXT, body TEXT NOT NULL, result TEXT);
            CREATE TABLE IF NOT EXISTS orders (
              client_order_id TEXT PRIMARY KEY, alpaca_order_id TEXT,
              signal_id TEXT NOT NULL, side TEXT, qty REAL, price REAL,
              status TEXT, filled_price REAL DEFAULT 0, filled_qty REAL DEFAULT 0,
              role TEXT NOT NULL, payload TEXT NOT NULL, response TEXT);
            CREATE TABLE IF NOT EXISTS protections (
              signal_id TEXT PRIMARY KEY, symbol TEXT, asset_type TEXT,
              direction TEXT, qty REAL, entry REAL, stop REAL, target REAL,
              initial_risk REAL, opened TEXT, state TEXT, exit_sequence INTEGER DEFAULT 0,
              reason_exit TEXT, realized_qty REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS trades (
              id TEXT PRIMARY KEY, signal_id TEXT, entry_time TEXT, exit_time TEXT,
              entry_price REAL, exit_price REAL, qty REAL, pnl REAL, pnl_pct REAL,
              R REAL, strategy TEXT, reason_exit TEXT);
            CREATE TABLE IF NOT EXISTS challenge_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp TEXT NOT NULL, event TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN
              SELECT RAISE(ABORT, 'append only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN
              SELECT RAISE(ABORT, 'append only'); END;
            CREATE TRIGGER IF NOT EXISTS trades_no_delete BEFORE DELETE ON trades BEGIN
              SELECT RAISE(ABORT, 'history protected'); END;
            ''')

    def acquire(self):
        self.lockfile = open(str(self.path)+'.lock', 'a+b')
        self.lockfile.seek(0)
        if sys.platform == 'win32':
            import msvcrt
            self.lockfile.write(b'0')
            self.lockfile.flush()
            self.lockfile.seek(0)
            msvcrt.locking(self.lockfile.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def release(self):
        if self.lockfile:
            self.lockfile.close()
            self.lockfile = None

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def rows(self, table, limit=200):
        if table not in {'signals','orders','audit','trades','protections'}:
            raise ValueError('table')
        with self.connect() as c:
            return [dict(r) for r in c.execute(f'SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?', (limit,))]

    def audit(self, event, body):
        with self.connect() as c:
            c.execute('INSERT INTO audit(timestamp,event,body) VALUES(?,?,?)',
                      (now().isoformat(),event,json.dumps(body,ensure_ascii=False,allow_nan=False)))

    def get(self, key, default=None):
        with self.connect() as c:
            row = c.execute('SELECT value FROM challenge_state WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.connect() as c:
            c.execute('INSERT INTO challenge_state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                      (key,json.dumps(value,allow_nan=False)))

    def reserve(self, s):
        with self.connect() as c:
            previous = c.execute('SELECT * FROM signals WHERE idempotency_key=?',(s.idempotency_key,)).fetchone()
            if previous:
                if previous['body'] != s.model_dump_json():
                    raise ValueError('Idempotency key użyty dla innego sygnału')
                return dict(previous)
            c.execute('INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (s.idempotency_key,s.timestamp.isoformat(),s.strategy_id,s.symbol,s.asset_type,s.direction,
                 s.setup_grade,s.entry_price,s.stop_loss,s.take_profit,'PROCESSING',s.reason,s.model_dump_json(),None))
        return None

    def finish(self, key, result):
        with self.connect() as c:
            c.execute('UPDATE signals SET status=?,result=? WHERE idempotency_key=?',
                      (result['status'],json.dumps(result,allow_nan=False),key))
        self.audit('signal.decision', {'idempotency_key':key,**result})

    def order_intent(self, cid, signal_id, payload, role):
        with self.connect() as c:
            c.execute('INSERT INTO orders(client_order_id,signal_id,side,qty,price,status,role,payload) VALUES(?,?,?,?,?,?,?,?)',
                (cid,signal_id,payload['side'],float(payload['qty']),payload.get('limit_price'),
                 'SUBMITTING',role,json.dumps(payload)))
        self.audit('order.intent',{'client_order_id':cid,'payload':payload,'role':role})

    def order_update(self, cid, result):
        if not isinstance(result,dict) or not all(result.get(k) for k in ('id','status','client_order_id')) or result['client_order_id'] != cid:
            raise ValueError('Niepotwierdzona odpowiedź zlecenia')
        with self.connect() as c:
            c.execute('UPDATE orders SET alpaca_order_id=?,status=?,filled_price=?,filled_qty=?,response=? WHERE client_order_id=?',
                      (result['id'],result['status'],float(result.get('filled_avg_price') or 0),
                       float(result.get('filled_qty') or 0),json.dumps(result),cid))
        self.audit('order.update',{'client_order_id':cid,'status':result['status'],'filled_qty':result.get('filled_qty')})

    def metrics(self):
        with self.connect() as c:
            trades = [dict(r) for r in c.execute('SELECT * FROM trades')]
            closed=[dict(r) for r in c.execute("SELECT t.signal_id,SUM(t.pnl) pnl,SUM(t.R) R FROM trades t JOIN protections p ON p.signal_id=t.signal_id WHERE p.state='CLOSED' GROUP BY t.signal_id")]
        gains = sum(max(0,t['pnl']) for t in closed)
        losses = -sum(min(0,t['pnl']) for t in closed)
        return {'number_of_trades':len(closed),'realized_pnl':sum(t['pnl'] for t in trades),
                'win_rate':sum(t['pnl']>0 for t in closed)/len(closed) if closed else 0,
                'profit_factor':gains/losses if losses else None,
                'average_R':sum(t['R'] for t in closed)/len(closed) if closed else 0}
