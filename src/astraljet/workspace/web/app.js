'use strict';
// AstralJet Trade Workspace — klient. Cały stan pochodzi z jednego snapshotu /api/state.
// Wykres używa tej samej formuły co serwer (session.price_to_y): y = (hi - p) / (hi - lo) * H.

const $ = (id) => document.getElementById(id);
let S = null;          // ostatni snapshot
let busy = false;
let drag = null;       // {key, price}
let autoTimer = null;

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (v) => (v === null || v === undefined || v === '' ? null : Number(v));
const digits = () => (S ? S.instrument.digits : 5);
const fmtP = (v, d = digits()) => (v === null || v === undefined ? '—' : Number(v).toFixed(d));
const fmtM = (v, cur = 'USD') => (v === null || v === undefined ? 'brak danych' : Number(v).toLocaleString('pl-PL', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' ' + cur);
const fmtN = (v, d = 0) => (v === null || v === undefined ? '—' : Number(v).toLocaleString('pl-PL', {minimumFractionDigits: d, maximumFractionDigits: d}));
const fmtPct = (v, d = 2) => (v === null || v === undefined ? '—' : (Number(v) * 100).toLocaleString('pl-PL', {minimumFractionDigits: d, maximumFractionDigits: d}) + '%');
const badge = (s, text) => `<span class="badge ${esc(s)}">${esc(text ?? s)}</span>`;
const sign = (v) => (num(v) > 0 ? 'pos' : num(v) < 0 ? 'neg' : '');
const rid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2));

async function load() {
  const r = await fetch('/api/state', {cache: 'no-store'});
  S = await r.json();
  render();
}

async function act(action, params = {}) {
  if (busy) return null;
  busy = true;
  document.body.style.cursor = 'progress';
  try {
    const r = await fetch('/api/action', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Astra-Workspace': 'SIMULATED'}, body: JSON.stringify({action, params})});
    const data = await r.json();
    if (data.state) S = data.state;
    if (!r.ok) showBanner(data.detail || 'Błąd akcji'); else hideBanner();
    render();
    return data;
  } catch (e) {
    showBanner('Brak połączenia z lokalnym serwerem Workspace.');
    return null;
  } finally {
    busy = false;
    document.body.style.cursor = '';
  }
}

function showBanner(t) { const b = $('banner'); b.textContent = t; b.hidden = false; }
function hideBanner() { $('banner').hidden = true; }

// ---------------------------------------------------------------- render
function render() {
  if (!S) return;
  document.documentElement.dataset.theme = S.ui.theme;
  $('ver').textContent = S.workspace_version;
  const acc = S.account;
  const q = S.quote_status;
  $('context').innerHTML = [
    `<span>Rachunek ${esc(acc ? acc.account_id : '—')} · ${esc(acc ? acc.currency : '')} · ${esc(acc ? acc.margin_mode : '')}</span>`,
    `<span>${esc(S.symbol)} · ${esc(S.timeframe)}</span>`,
    `<span>Kwotowanie ${badge(q.state)} ${q.age_s === null ? '' : esc(q.age_s) + ' s'}</span>`,
    `<span>Połączenie ${badge(S.connection.connected ? 'ok' : 'bad', S.connection.state)}</span>`,
    S.kill_switch.active ? `<span>${badge('bad', 'KILL SWITCH AKTYWNY')}</span>` : '',
    `<span>snapshot v${esc(S.version)}</span>`,
  ].join('');
  $('mode').title = S.mode_note;
  $('clock').textContent = 'Zegar symulacji: ' + S.generated_at.replace('T', ' ').slice(0, 19) + ' UTC';
  $('conn').textContent = S.connection.connected ? 'Rozłącz' : 'Połącz';
  $('kill').textContent = S.kill_switch.active ? 'Wyłącz kill switch' : 'Kill switch';
  fillSelect($('symbol'), S.symbols, S.symbol);
  fillSelect($('timeframe'), S.timeframes, S.timeframe);
  const qt = S.quote;
  $('quote').innerHTML = qt ? `Bid ${fmtP(qt.bid)} · Ask ${fmtP(qt.ask)} · spread ${fmtN(S.widgets.spread.points, 0)} pkt · ${esc(qt.source)}` : 'Brak kwotowania';
  renderChart();
  renderPlan();
  renderPositions();
  renderTriggers();
  renderWidgets();
  renderRequests();
  renderReview();
  $('events').innerHTML = S.events.map((e) => `<li><span class="muted">${esc(e.at.slice(11, 19))}</span> [${esc(e.kind)}] ${esc(e.message)}</li>`).join('') || '<li class="muted">Brak zdarzeń.</li>';
}

function fillSelect(el, values, current) {
  if (el.dataset.v !== values.join('|')) {
    el.innerHTML = values.map((v) => `<option>${esc(v)}</option>`).join('');
    el.dataset.v = values.join('|');
  }
  if (document.activeElement !== el) el.value = current;
}

// ---------------------------------------------------------------- wykres
const H = 420, PAD_R = 92, PAD_B = 22;
function geometry() {
  const box = $('chart-box');
  const W = Math.max(320, box.clientWidth);
  const lo = num(S.chart.lo), hi = num(S.chart.hi);
  const plotH = H - PAD_B;
  const yOf = (p) => ((hi - p) / (hi - lo)) * plotH;           // identyczna formuła jak w session.price_to_y
  const pOf = (y) => hi - (y / plotH) * (hi - lo);
  return {W, lo, hi, plotH, yOf, pOf};
}

function levelItems() {
  const items = [];
  const ev = S.plan.evaluation;
  if (S.plan.symbol === S.symbol) {
    if (ev.entry !== null) items.push({key: 'entry', price: num(ev.entry), cls: 'lvl-entry', drag: S.plan.order_type !== 'MARKET', text: `PLAN ${S.plan.side} ${S.plan.volume} @ ${fmtP(ev.entry)}${S.plan.order_type === 'MARKET' ? ' (' + ev.entry_basis + ')' : ''}`});
    if (S.plan.sl !== null) items.push({key: 'sl', price: num(S.plan.sl), cls: 'lvl-sl', drag: true, text: `SL ${fmtP(S.plan.sl)} · ${fmtN(ev.sl_points)} pkt · −${fmtM(ev.risk_account)}`});
    if (S.plan.tp !== null) items.push({key: 'tp', price: num(S.plan.tp), cls: 'lvl-tp', drag: true, text: `TP ${fmtP(S.plan.tp)} · ${fmtN(ev.tp_points)} pkt · +${fmtM(ev.reward_account)}`});
  }
  for (const p of S.positions.filter((x) => x.symbol === S.symbol)) {
    items.push({key: 'pos', price: num(p.open_price), cls: 'lvl-pos', text: `POZ ${p.position_id} ${p.side} ${p.volume} @ ${fmtP(p.open_price)}`});
    if (p.sl) items.push({key: 'psl', price: num(p.sl), cls: 'lvl-sl', text: `SL poz. ${fmtP(p.sl)} (potwierdzony)`});
    if (p.tp) items.push({key: 'ptp', price: num(p.tp), cls: 'lvl-tp', text: `TP poz. ${fmtP(p.tp)}`});
  }
  for (const t of S.triggers.filter((x) => x.symbol === S.symbol && x.line_price_now && !['FIRED', 'CANCELLED', 'EXPIRED'].includes(x.state))) {
    items.push({key: 'trg', price: num(t.line_price_now), cls: 'lvl-trg', text: `TRIGGER ${t.trigger_id} ${t.cross || '?'} → ${t.side || '?'} (${t.state})`});
  }
  return items;
}

function renderChart() {
  const g = geometry();
  const c = S.chart.candles;
  const plotW = g.W - PAD_R;
  const step = plotW / Math.max(1, c.length);
  const bw = Math.max(1, step * 0.6);
  let svg = `<svg viewBox="0 0 ${g.W} ${H}" role="img" aria-label="Wykres świecowy ${esc(S.symbol)} ${esc(S.timeframe)} z poziomami planu">`;
  for (let i = 0; i <= 6; i++) {
    const p = g.lo + ((g.hi - g.lo) * i) / 6;
    const y = g.yOf(p);
    svg += `<line class="grid-line" x1="0" x2="${plotW}" y1="${y}" y2="${y}"/><text class="axis" x="${plotW + 4}" y="${Math.min(g.plotH - 2, Math.max(10, y + 3))}">${fmtP(p)}</text>`;
  }
  const ev = S.plan.evaluation;
  if (S.plan.symbol === S.symbol && ev.entry !== null) {
    const ye = g.yOf(num(ev.entry));
    if (S.plan.tp !== null) { const yt = g.yOf(num(S.plan.tp)); svg += `<rect class="zone-tp" x="0" width="${plotW}" y="${Math.min(ye, yt)}" height="${Math.abs(ye - yt)}"/>`; }
    if (S.plan.sl !== null) { const ys = g.yOf(num(S.plan.sl)); svg += `<rect class="zone-sl" x="0" width="${plotW}" y="${Math.min(ye, ys)}" height="${Math.abs(ye - ys)}"/>`; }
  }
  c.forEach((k, i) => {
    const x = i * step + step / 2;
    const o = num(k.o), cl = num(k.c);
    const up = cl >= o;
    const top = g.yOf(Math.max(o, cl)), bot = g.yOf(Math.min(o, cl));
    svg += `<line class="${up ? 'candle-up' : 'candle-down'}" x1="${x}" x2="${x}" y1="${g.yOf(num(k.h))}" y2="${g.yOf(num(k.l))}"/>`;
    svg += `<rect class="${up ? 'candle-up' : 'candle-down'}" x="${x - bw / 2}" width="${bw}" y="${top}" height="${Math.max(1, bot - top)}"/>`;
  });
  for (const it of levelItems()) {
    const price = drag && drag.key === it.key ? drag.price : it.price;
    const y = g.yOf(price);
    const label = drag && drag.key === it.key ? `${it.key.toUpperCase()} → ${fmtP(price)} (puść, aby przeliczyć)` : it.text;
    svg += `<g data-key="${it.key}" class="${it.drag ? 'drag' : ''}"><line class="lvl ${it.cls}" x1="0" x2="${plotW}" y1="${y}" y2="${y}"/>`;
    if (it.drag) svg += `<line class="hit" x1="0" x2="${plotW}" y1="${y}" y2="${y}"/>`;
    const tw = Math.min(plotW - 8, label.length * 5.6 + 10);
    svg += `<rect class="lbl-bg" x="${plotW - tw - 4}" y="${y - 9}" width="${tw}" height="16" rx="3"/><text class="lbl" x="${plotW - tw + 1}" y="${y + 3}">${esc(label)}</text></g>`;
  }
  svg += `<text class="axis" x="4" y="${H - 6}">${esc(c.length ? c[0].t.slice(5, 16).replace('T', ' ') : '')}</text><text class="axis" x="${plotW - 90}" y="${H - 6}">${esc(c.length ? c[c.length - 1].t.slice(5, 16).replace('T', ' ') : '')}</text></svg>`;
  $('chart-box').innerHTML = svg;
  $('chart-caption').textContent = `Źródło: ${S.chart.source} (${S.chart.mode}). Oś obejmuje świece i wszystkie poziomy. Przeciągnij linię SL/TP (lub wejście zlecenia oczekującego), aby zmienić plan; cena jest przyciągana do ticka ${S.instrument.tick}.`;
}

function bindChart() {
  const box = $('chart-box');
  box.addEventListener('pointerdown', (e) => {
    const g = e.target.closest('g.drag');
    if (!g || busy) return;
    const key = g.dataset.key;
    drag = {key, price: null};
    box.setPointerCapture(e.pointerId);
    moveDrag(e);
  });
  box.addEventListener('pointermove', (e) => { if (drag) moveDrag(e); });
  box.addEventListener('pointerup', async () => {
    if (!drag || drag.price === null) { drag = null; return; }
    const d = drag;
    drag = null;
    await act('set_plan', {[d.key]: d.price.toFixed(digits())});
  });
}

function moveDrag(e) {
  const svg = $('chart-box').querySelector('svg');
  const rect = svg.getBoundingClientRect();
  const y = ((e.clientY - rect.top) / rect.height) * H;
  drag.price = geometry().pOf(Math.min(H - PAD_B, Math.max(0, y)));
  renderChart();
}

// ---------------------------------------------------------------- plan
function renderPlan() {
  const p = S.plan, ev = p.evaluation;
  document.querySelectorAll('[data-side]').forEach((b) => b.classList.toggle('on', b.dataset.side === p.side));
  for (const k of ['volume', 'entry', 'sl', 'tp']) { const el = $(k); if (document.activeElement !== el) el.value = p[k] ?? ''; }
  if (document.activeElement !== $('order_type')) $('order_type').value = p.order_type;
  const cur = ev.account_currency;
  const rows = [
    ['Wejście', `${fmtP(ev.entry)} <span class="muted">${esc(ev.entry_basis)}</span>`],
    ['Odległość SL', ev.sl_points === null ? 'brak SL' : `${fmtN(ev.sl_points)} pkt · ${fmtN(ev.sl_pips, 1)} pips`],
    ['Odległość TP', ev.tp_points === null ? 'brak TP' : `${fmtN(ev.tp_points)} pkt · ${fmtN(ev.tp_pips, 1)} pips`],
    ['Strata przy SL (brutto)', ev.risk_account === null ? (p.sl === null ? 'nieokreślona' : 'brak kursu') : `<span class="neg">−${fmtM(ev.risk_account, cur)}</span>`],
    ['Zysk przy TP (brutto)', ev.reward_account === null ? 'nieokreślony' : `<span class="pos">+${fmtM(ev.reward_account, cur)}</span>`],
    ['Reward/risk', ev.reward_risk === null ? '—' : fmtN(ev.reward_risk, 4)],
    ['Wymagany win rate (BE)', ev.breakeven_win_rate === null ? '—' : fmtPct(ev.breakeven_win_rate, 2)],
    ['Koszty (szacunek)', ev.costs_account === null ? 'nieznane' : fmtM(ev.costs_account, cur)],
    ['Strata przy SL netto', ev.net_risk_account === null ? '—' : `−${fmtM(ev.net_risk_account, cur)}`],
    ['Zysk przy TP netto', ev.net_reward_account === null ? '—' : `+${fmtM(ev.net_reward_account, cur)}`],
    ['Strata przy SL / equity', ev.risk_to_equity === null ? '—' : fmtPct(ev.risk_to_equity, 3)],
    ['Instrument', `point ${esc(S.instrument.point)} · tick ${esc(S.instrument.tick)} · pip ${esc(S.instrument.pip)} · kontrakt ${esc(S.instrument.contract_size)} ${esc(S.instrument.profit_currency)}`],
  ];
  $('metrics').innerHTML = rows.map(([a, b]) => `<div><span>${a}</span><span>${b}</span></div>`).join('');
  $('plan-msgs').innerHTML = ev.errors.map((m) => `<li class="err">${esc(m)}</li>`).join('') + ev.warnings.map((m) => `<li class="warn">${esc(m)}</li>`).join('') + (ev.cost_note && ev.costs_account !== null ? `<li class="muted">${esc(ev.cost_note)}</li>` : '');
  $('send').disabled = !ev.can_send || p.order_type !== 'MARKET';
  $('send').title = p.order_type !== 'MARKET' ? 'Symulator v0.1 obsługuje wyłącznie zlecenia rynkowe' : '';
}

function readPlanForm() {
  return {volume: $('volume').value, entry: $('entry').value, sl: $('sl').value, tp: $('tp').value, order_type: $('order_type').value};
}

// ---------------------------------------------------------------- pozycje
function renderPositions() {
  if (!S.connection.connected) { $('positions-box').innerHTML = `<p>${badge('MISSING', 'BRAK DANYCH')} Brak połączenia: pozycje nieznane (nie „zero pozycji”).</p>`; return; }
  if (!S.positions.length) { $('positions-box').innerHTML = '<p class="muted">Brak otwartych pozycji (potwierdzone odczytem symulatora).</p>'; return; }
  $('positions-box').innerHTML = S.positions.map((p) => {
    const r = p.rules || {};
    const be = r.be || {trigger_points: 100, offset_points: 10, enabled: false};
    const tr = r.trailing || {activation_points: 500, distance_points: 250, step_points: 10, enabled: false};
    const st = (s) => (s ? `${badge(s.state)} <span class="muted">${esc(s.reason)}${s.target ? ' · cel ' + fmtP(s.target) : ''}</span>` : badge('DISABLED'));
    return `<div class="trg"><table><thead><tr><th>Pozycja</th><th>Kierunek</th><th>Wolumen</th><th>Wejście</th><th>SL (potw.)</th><th>TP</th><th>Wynik pkt</th><th>Floating</th><th>Ochrona</th><th>Wynik przy SL</th></tr></thead>
      <tbody><tr><td>${esc(p.position_id)}<br><span class="muted">${esc(p.symbol)}</span></td><td>${esc(p.side)}</td><td>${esc(p.volume)}</td><td>${fmtP(p.open_price)}</td><td>${p.sl ? fmtP(p.sl) : '—'}</td><td>${p.tp ? fmtP(p.tp) : '—'}</td>
      <td class="${sign(p.profit_points)}">${fmtN(p.profit_points)}</td><td class="${sign(p.floating)}">${fmtM(p.floating)}</td><td>${badge(p.protection.status)}</td><td>${p.protection.pnl_at_sl_account === null ? '—' : fmtM(p.protection.pnl_at_sl_account)}<br><span class="muted">szacunek, bez gwarancji</span></td></tr></tbody></table>
      <div class="pos-rules" data-pos="${esc(p.position_id)}">
        <fieldset><legend>Break-even</legend><label>Trigger (pkt)<input name="be_t" value="${esc(be.trigger_points)}"></label><label>Bufor (pkt)<input name="be_o" value="${esc(be.offset_points)}"></label><button data-act="be_on" type="button">Włącz</button><button data-act="be_off" type="button">Wyłącz</button><div>${st(r.be_status)}</div></fieldset>
        <fieldset><legend>Trailing</legend><label>Aktywacja (pkt)<input name="tr_a" value="${esc(tr.activation_points)}"></label><label>Odległość (pkt)<input name="tr_d" value="${esc(tr.distance_points)}"></label><label>Krok (pkt)<input name="tr_s" value="${esc(tr.step_points)}"></label><button data-act="tr_on" type="button">Włącz</button><button data-act="tr_off" type="button">Wyłącz</button><div>${st(r.trailing_status)}</div></fieldset>
        <fieldset><legend>Ręczny SL</legend><label>Nowy SL<input name="m_sl" value="${esc(p.sl ?? '')}"></label><label><span><input type="checkbox" name="m_worse"> świadomie pogarszam</span></label><button data-act="manual" type="button">Ustaw</button><div>${st(r.manual_status)}</div></fieldset>
        <fieldset><legend>Zamknięcie</legend><label>Wolumen<input name="c_vol" value="${esc(p.volume)}"></label><button data-act="close" type="button">Zamknij (żądanie)</button></fieldset>
      </div><p class="caption">${esc(p.protection.note)}</p></div>`;
  }).join('');
}

async function onPositionAction(e) {
  const b = e.target.closest('button[data-act]');
  if (!b) return;
  const box = b.closest('[data-pos]');
  const pid = box.dataset.pos;
  const v = (n) => box.querySelector(`[name=${n}]`);
  const a = b.dataset.act;
  if (a === 'be_on' || a === 'be_off') await act('set_be', {position_id: pid, trigger_points: v('be_t').value, offset_points: v('be_o').value, enabled: a === 'be_on'});
  if (a === 'tr_on' || a === 'tr_off') await act('set_trailing', {position_id: pid, activation_points: v('tr_a').value, distance_points: v('tr_d').value, step_points: v('tr_s').value, enabled: a === 'tr_on'});
  if (a === 'manual') await act('manual_sl', {position_id: pid, sl: v('m_sl').value, acknowledge_worse: v('m_worse').checked});
  if (a === 'close') await act('close_position', {position_id: pid, volume: v('c_vol').value, client_request_id: rid()});
}

// ---------------------------------------------------------------- triggery
function renderTriggers() {
  if (!$('t_price').value && S.quote) $('t_price').value = S.quote.bid;
  $('triggers-box').innerHTML = S.triggers.slice().reverse().map((t) => `<div class="trg" data-trg="${esc(t.trigger_id)}">
    <p>${badge(t.state)} <b>${esc(t.trigger_id)}</b> <span class="muted">rew. ${esc(t.revision)}${t.line_price_now ? ' · linia teraz ' + fmtP(t.line_price_now) : ''}</span></p>
    <p>${esc(t.summary)}</p>
    ${t.warnings.map((w) => `<p class="neg">${esc(w)}</p>`).join('')}
    <p class="muted">${esc(t.reason)}</p>
    <button data-t="arm" type="button" ${t.missing.length ? 'disabled title="Reguła niekompletna"' : ''}>Uzbrój</button><button data-t="pause" type="button">Wstrzymaj</button><button data-t="cancel" type="button">Anuluj</button>
    <label>Nowa cena linii <input name="mv" value="${esc(t.line ? t.line.p1 : '')}"></label><button data-t="move" type="button">Przesuń</button><button data-t="del" type="button">Usuń linię</button>
    ${t.fired_request_id ? `<p class="muted">Żądanie: ${esc(t.fired_request_id)} (stan w tabeli „Żądania”)</p>` : ''}
  </div>`).join('') || '<p class="muted">Brak reguł.</p>';
}

async function onTriggerAction(e) {
  const b = e.target.closest('button[data-t]');
  if (!b) return;
  const box = b.closest('[data-trg]');
  const id = box.dataset.trg;
  const map = {arm: 'trigger_arm', pause: 'trigger_pause', cancel: 'trigger_cancel', del: 'trigger_delete_line'};
  if (b.dataset.t === 'move') await act('trigger_move', {trigger_id: id, line_price: box.querySelector('[name=mv]').value});
  else await act(map[b.dataset.t], {trigger_id: id});
}

// ---------------------------------------------------------------- widgety
function renderWidgets() {
  const w = S.widgets;
  const acc = S.account;
  const ind = w.indicators;
  const risk = w.risk_to_sl;
  const macd = ind.macd_12_26_9.value;
  const items = [
    ['Rachunek', acc ? `<div class="big">${fmtM(acc.equity, acc.currency)}</div><span class="muted">equity · saldo ${fmtM(acc.balance, acc.currency)}<br>${esc(acc.source)}</span>` : badge('MISSING', 'BRAK DANYCH')],
    ['Wykorzystanie depozytu', `<div class="big">${w.margin.ratio === null ? '—' : fmtPct(w.margin.ratio)}</div><span class="muted">${esc(w.margin.label)}<br>wolny depozyt ${fmtM(w.margin.free_margin)}</span>`],
    ['Ryzyko do SL', `${badge(risk.state)}<div class="big">${risk.loss_to_sl_from_now === null ? 'nieznane' : fmtM(risk.loss_to_sl_from_now)}</div><span class="muted">${esc(risk.label)}${risk.loss_to_sl_pct_equity ? ' · ' + fmtPct(risk.loss_to_sl_pct_equity) + ' equity' : ''}</span>`],
    ['Czas świecy', `<div class="big">${Math.floor(w.candle_timer.remaining_s / 60)}:${String(Math.floor(w.candle_timer.remaining_s % 60)).padStart(2, '0')}</div><span class="muted">${esc(S.symbol)} ${esc(w.candle_timer.timeframe)} · ${esc(w.candle_timer.note)}</span>`],
    ['Spread', `<div class="big">${w.spread.points === null ? '—' : fmtN(w.spread.points) + ' pkt'}</div><span class="muted">${esc(S.symbol)} · ${esc(w.spread.source || '')}</span>`],
    ['RSI(14)', `<div class="big">${ind.rsi14.value ?? '—'}</div><span class="muted">${esc(ind.rsi14.symbol)} ${esc(ind.rsi14.timeframe)} · zamknięta świeca ${esc((ind.rsi14.as_of_bar || '').slice(11, 16))} · ${esc(ind.rsi14.mode)}<br>${esc(ind.rsi14.note)}</span>`],
    ['MACD(12,26,9)', `<div class="big">${macd ? Number(macd.histogram).toExponential(2) : '—'}</div><span class="muted">histogram (MACD − sygnał) · MACD ${macd ? Number(macd.macd).toExponential(2) : '—'} · sygnał ${macd ? Number(macd.signal).toExponential(2) : '—'}<br>${esc(ind.macd_12_26_9.symbol)} ${esc(ind.macd_12_26_9.timeframe)} · ${esc(ind.macd_12_26_9.mode)}</span>`],
  ];
  $('widgets-box').innerHTML = items.map(([h, b]) => `<div class="widget"><h3>${h}</h3>${b}</div>`).join('') + '<p class="caption">Bez syntetycznego „Health %”: pokazujemy sprawdzalne składniki (SL, połączenie, świeżość, depozyt).</p>';
}

// ---------------------------------------------------------------- żądania
function renderRequests() {
  const rows = S.requests.map((r) => `<tr><td>${esc(r.request.request_id)}</td><td>${esc(r.request.kind)}</td><td>${esc(r.request.origin)}</td><td>${esc(r.request.symbol)} ${esc(r.request.side || '')} ${esc(r.request.volume || '')}</td><td>${badge(r.state)}</td><td>${esc(r.message)}</td><td>${esc(r.transmissions)}</td><td>${['UNCERTAIN', 'SENT'].includes(r.state) ? `<button data-rec="${esc(r.request.request_id)}" type="button">Uzgodnij</button>` : r.retry_allowed ? '<span class="muted">wolno nowe żądanie</span>' : ''}</td></tr>`).join('');
  $('requests-box').innerHTML = rows ? `<table><thead><tr><th>ID</th><th>Rodzaj</th><th>Źródło</th><th>Instrument</th><th>Stan</th><th>Komunikat</th><th>Wysyłek</th><th></th></tr></thead><tbody>${rows}</tbody></table><p class="caption">UNCERTAIN = brak odpowiedzi; system nie ponawia w ciemno. „Uzgodnij” pyta brokera o to samo żądanie.</p>` : '<p class="muted">Brak żądań.</p>';
}

// ---------------------------------------------------------------- review
function renderReview() {
  const r = S.review;
  if (!r) { $('review-box').innerHTML = `<p>${badge('MISSING', 'BRAK DANYCH')} Brak połączenia: historia nieznana.</p>`; return; }
  fillSelect($('r_symbol'), [''].concat(S.symbols), r.filter.symbol || '');
  const st = r.stats;
  const k = [
    ['Zrealizowane w okresie', fmtM(r.realized_period, r.currency), sign(r.realized_period)],
    ['w tym z zamkniętych transakcji', fmtM(r.realized_breakdown.from_closed_trades_in_period), ''],
    ['w tym częściowe zamknięcia otwartych', fmtM(r.realized_breakdown.from_partial_closes_of_open_positions), ''],
    ['w tym koszty wejścia otwartych', fmtM(r.realized_breakdown.entry_costs_of_open_positions), ''],
    ['Zamknięte transakcje — pełny wynik', fmtM(r.realized_breakdown.closed_trades_full_net), sign(r.realized_breakdown.closed_trades_full_net)],
    ['Koszty (prow.+swap+opłaty)', fmtM(Number(r.realized_breakdown.commission) + Number(r.realized_breakdown.swap) + Number(r.realized_breakdown.fee)), 'neg'],
    ['Floating teraz (osobno)', fmtM(r.floating_now), sign(r.floating_now)],
    ['Wpłaty / wypłaty', `${fmtM(r.cash_flows.deposits)} / ${fmtM(r.cash_flows.withdrawals)}`, ''],
    ['Transakcje', `${st.trades} (W ${st.wins} / L ${st.losses} / 0 ${st.breakeven})`, ''],
    ['Win rate', fmtPct(st.win_rate, 1), ''],
    ['Expectancy', st.expectancy === null ? '—' : fmtM(st.expectancy), ''],
    ['Profit factor', st.profit_factor === null ? 'brak strat' : fmtN(st.profit_factor, 2), ''],
    ['Max DD salda', fmtM(st.max_drawdown), ''],
  ];
  const curve = r.curve.map((p) => num(p.balance));
  const lo = Math.min(...curve), hi = Math.max(...curve);
  const W = 600, Hc = 170, span = hi - lo || 1;
  const pts = curve.map((v, i) => `${(i / Math.max(1, curve.length - 1)) * W},${Hc - ((v - lo) / span) * (Hc - 10) - 5}`).join(' ');
  const sides = ['BUY', 'SELL'].map((s) => ({s, ...r.by_side[s]}));
  const maxAbs = Math.max(1e-9, ...sides.map((x) => Math.abs(num(x.net))));
  const bars = sides.map((x, i) => { const w = (Math.abs(num(x.net)) / maxAbs) * 140; const neg = num(x.net) < 0; return `<text class="axis" x="0" y="${30 + i * 50}">${x.s}: ${x.trades} tr. · ${x.volume} lot · ${fmtM(x.net)}</text><rect class="${neg ? 'zone-sl' : 'zone-tp'}" x="${neg ? 150 - w : 150}" y="${38 + i * 50}" width="${w}" height="14"/>`; }).join('') + '<line class="grid-line" x1="150" x2="150" y1="20" y2="130"/><text class="axis" x="152" y="150">0 (strata ← → zysk)</text>';
  $('review-box').innerHTML = `<p class="muted">Rachunek ${esc(r.account_id)} · ${esc(r.source)} · okres ${esc(r.filter.start ? r.filter.start.slice(0, 16) : 'od początku danych')} → teraz · saldo początkowe ${r.balance.start === null ? '— (filtr: wynik od 0)' : fmtM(r.balance.start)}</p>
    <div class="kpis">${k.map(([a, b, c]) => `<div class="kpi"><span class="muted">${a}</span><b class="${c}">${b}</b></div>`).join('')}</div>
    <div class="review-charts"><div><span class="muted">${esc(r.definitions.balance_curve)}</span><svg viewBox="0 0 ${W} ${Hc}" preserveAspectRatio="none"><polyline fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke" points="${pts}"/></svg><span class="muted">min ${fmtM(lo)} · max ${fmtM(hi)} · punktów ${curve.length}</span></div>
    <div><span class="muted">Wynik netto wg kierunku (te same liczby co w tabeli)</span><svg viewBox="0 0 300 160">${bars}</svg></div></div>
    <details><summary>Definicje</summary><ul>${Object.entries(r.definitions).map(([a, b]) => `<li><b>${esc(a)}</b>: ${esc(b)}</li>`).join('')}</ul></details>
    <div class="table-scroll"><table><thead><tr><th>Pozycja</th><th>Symbol</th><th>Kier.</th><th>Wolumen</th><th>Wyjść</th><th>Brutto</th><th>Koszty</th><th>Netto</th><th>Zamknięta</th></tr></thead><tbody>${r.trades.map((t) => `<tr><td>${esc(t.position_id)}</td><td>${esc(t.symbol)}</td><td>${esc(t.side)}</td><td>${esc(t.volume)}</td><td>${esc(t.exits)}</td><td>${fmtM(t.gross)}</td><td>${fmtM(t.costs)}</td><td class="${sign(t.net)}">${fmtM(t.net)}</td><td>${esc(t.closed_at.slice(11, 19))}</td></tr>`).join('') || '<tr><td colspan="9" class="muted">Brak w pełni zamkniętych transakcji w okresie.</td></tr>'}</tbody></table></div>`;
}

// ---------------------------------------------------------------- zdarzenia
function bind() {
  document.querySelectorAll('[data-step]').forEach((b) => b.addEventListener('click', () => act('step', {n: Number(b.dataset.step)})));
  document.querySelectorAll('[data-drift]').forEach((b) => b.addEventListener('click', () => act('step', {n: 1, drift_points: Number(b.dataset.drift)})));
  document.querySelectorAll('[data-side]').forEach((b) => b.addEventListener('click', () => act('set_plan', {side: b.dataset.side})));
  $('auto').addEventListener('change', (e) => { clearInterval(autoTimer); if (e.target.checked) autoTimer = setInterval(() => act('step', {n: 1}), 2000); });
  $('script').addEventListener('change', async (e) => { if (e.target.value) await act('script_next', {behaviour: e.target.value}); e.target.value = ''; });
  $('conn').addEventListener('click', () => act('set_connected', {connected: !S.connection.connected}));
  $('kill').addEventListener('click', () => act('kill_switch', {active: !S.kill_switch.active}));
  $('theme').addEventListener('click', () => act('ui_settings', {theme: S.ui.theme === 'dark' ? 'light' : 'dark'}));
  $('symbol').addEventListener('change', (e) => act('set_symbol', {symbol: e.target.value}));
  $('timeframe').addEventListener('change', (e) => act('set_timeframe', {timeframe: e.target.value}));
  $('apply-plan').addEventListener('click', () => act('set_plan', readPlanForm()));
  for (const id of ['volume', 'entry', 'sl', 'tp']) $(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') act('set_plan', readPlanForm()); });
  $('order_type').addEventListener('change', () => act('set_plan', readPlanForm()));
  $('send').addEventListener('click', async () => { const b = $('send'); b.disabled = true; await act('send_plan', {client_request_id: rid()}); });
  $('positions-box').addEventListener('click', onPositionAction);
  $('triggers-box').addEventListener('click', onTriggerAction);
  $('requests-box').addEventListener('click', (e) => { const b = e.target.closest('[data-rec]'); if (b) act('reconcile', {request_id: b.dataset.rec}); });
  $('t_create').addEventListener('click', async () => {
    const res = await act('trigger_create', {line_price: $('t_price').value, cross: $('t_cross').value || null, side: $('t_side').value || null, volume: $('t_vol').value, price_source: $('t_src').value, sl_points: $('t_sl').value, tp_points: $('t_tp').value, expires_minutes: $('t_exp').value || null});
    if (res && res.result) $('t_price').value = '';
  });
  const rf = () => act('review_filter', {hours: $('r_hours').value || null, symbol: $('r_symbol').value || null, side: $('r_side').value || null});
  ['r_hours', 'r_symbol', 'r_side'].forEach((id) => $(id).addEventListener('change', rf));
  bindChart();
  window.addEventListener('resize', () => S && renderChart());
}

bind();
load().catch(() => showBanner('Nie można pobrać stanu Workspace.'));
