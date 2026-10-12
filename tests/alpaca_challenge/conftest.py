import pytest
from astraljet.alpaca_challenge.config import Settings
from astraljet.alpaca_challenge.models import Signal, Quote, now
from astraljet.alpaca_challenge.strategies import WEIGHTS


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None,executor_bearer_token='test-only-token-not-a-real-secret-000',challenge_db=tmp_path/'test.sqlite3',scanner_autostart=False)


@pytest.fixture
def signal():
    return Signal(idempotency_key='test-signal-0001',timestamp=now(),strategy_id='CRYPTO_BREAKOUT',symbol='BTC/USD',
        asset_type='crypto',setup_grade='A+',entry_price=100,stop_loss=90,take_profit=125,max_loss_usd=50,
        confidence_components={k:1 for k in WEIGHTS},reason='explicit test fixture',time_in_force='gtc')


class FakeBroker:
    def __init__(self):
        self.writes=[]
        self.open_positions=[]
        self.open_orders=[]
        self.history={}
        self.account_data={'status':'ACTIVE','trading_blocked':False,'account_blocked':False,
            'equity':'1000','cash':'1000','buying_power':'1000','options_buying_power':'1000','options_trading_level':2}
    async def account(self): return self.account_data.copy()
    async def positions(self): return self.open_positions.copy()
    async def orders(self): return self.open_orders.copy()
    async def asset(self,symbol,kind):
        return {'tradable':True,'status':'active','fractionable':True,'shortable':True,'easy_to_borrow':True,
                'overnight_tradable':True,'overnight_halted':False,'size':'100'}
    async def quote(self,*args): return Quote(t=now(),bp=99.99,ap=100)
    async def clock(self): return {'is_open':True,'timestamp':now().isoformat()}
    async def by_client_id(self,cid): return self.history.get(cid)
    async def close(self): return None
    async def bars(self,*args): raise ValueError('No fixture market data')
    async def request(self,method,path,**kwargs):
        self.writes.append((method,path))
        if path=='/v2/orders': self.open_orders=[]
    async def submit(self,payload):
        self.writes.append(payload)
        result={'id':'order-'+str(len(self.writes)),'client_order_id':payload['client_order_id'],'status':'filled',
                'filled_avg_price':'100','filled_qty':payload['qty'],'filled_at':now().isoformat()}
        self.history[payload['client_order_id']]=result
        if payload['side']=='buy':
            self.open_positions=[{'symbol':payload['symbol'],'qty':payload['qty'],'market_value':str(float(payload['qty'])*100),'unrealized_pl':'0'}]
        else:
            self.open_positions=[]
        return result


@pytest.fixture
def broker(): return FakeBroker()
