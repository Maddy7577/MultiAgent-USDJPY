document.addEventListener('DOMContentLoaded', () => {
  initSharedNav();
  startPolling(fetchDashboardData);
});

async function fetchDashboardData() {
  const [dash, strategiesPayload] = await Promise.all([
    apiFetch('/api/dashboard'),
    apiFetch('/api/strategies')
  ]);
  const strategies = strategiesPayload.strategies || [];
  fetchStatus();
  renderPrice(dash);
  renderSession();
  renderMarketContext(dash);
  renderSignalCounts(strategies);
  renderActiveSignals(strategies);
  if (dash.price?.bid != null) updateNavPrice(dash.price.bid);
}

function renderPrice(d) {
  const bid = d.price?.bid;
  const ask = d.price?.ask;
  document.getElementById('price-bid').textContent = bid != null ? bid.toFixed(3) : '—';
  document.getElementById('price-ask').textContent = ask != null ? ask.toFixed(3) : '—';
  if (bid != null && ask != null) {
    const spread = ((ask - bid) * 100).toFixed(1);
    document.getElementById('price-spread').textContent = `Spread: ${spread} pips`;
  }
}

function renderSession() {
  const now = new Date();
  const h = now.getUTCHours();
  const m = now.getUTCMinutes();
  const session = currentSession(h);
  const badge = document.getElementById('session-badge');
  badge.textContent = session;
  badge.className = 'session-badge ' + session.toLowerCase().replace(' ', '-').replace('-hours', '');

  const mins = minsToNextSession(h, m);
  const nextH = String(Math.floor(mins / 60)).padStart(2, '0');
  const nextM = String(mins % 60).padStart(2, '0');
  document.getElementById('session-next').textContent = `Next session in ${nextH}:${nextM}`;
}

function renderMarketContext(d) {
  const ctx = d.market_context || {};
  if (ctx.dxy   != null) document.getElementById('tile-dxy').textContent   = ctx.dxy.toFixed(2);
  if (ctx.us10y != null) document.getElementById('tile-us10y').textContent = ctx.us10y.toFixed(2);
  if (ctx.vix   != null) {
    document.getElementById('tile-vix').textContent        = ctx.vix.toFixed(1);
    document.getElementById('tile-vix-regime').textContent = vixLabel(ctx.vix);
  }
  const ev = ctx.next_event;
  if (ev) {
    document.getElementById('tile-event-name').textContent      = ev.name;
    document.getElementById('tile-event-countdown').textContent = countdownToUtc(ev.datetime_utc);
    const impactBadge = document.getElementById('tile-event-impact');
    impactBadge.textContent = ev.impact || '';
    impactBadge.className = 'badge ' + (ev.impact === 'High' ? 'badge-wait' : '');
  }
}

function renderSignalCounts(strategies) {
  const valid   = strategies.filter(s => s.status === 'VALID_TRADE').length;
  const wait    = strategies.filter(s => s.status === 'WAIT_FOR_LEVELS').length;
  const noTrade = strategies.filter(s => s.status === 'NO_TRADE').length;
  document.getElementById('count-valid').textContent    = valid;
  document.getElementById('count-wait').textContent     = wait;
  document.getElementById('count-no-trade').textContent = noTrade;
}

function renderActiveSignals(strategies) {
  const active = strategies.filter(s => s.status === 'VALID_TRADE' || s.status === 'WAIT_FOR_LEVELS');
  const list = document.getElementById('active-signals-list');
  list.innerHTML = '';

  if (active.length === 0) {
    const msg = document.createElement('div');
    msg.className = 'empty-state';
    msg.textContent = 'No active setups at this time';
    list.appendChild(msg);
    return;
  }

  for (const s of active) {
    const row = document.createElement('div');
    row.className = 'signal-row';
    row.addEventListener('click', () => {
      window.location.href = `/detail.html?strategy=${s.strategy_id}`;
    });

    const name = document.createElement('div');
    name.className = 'signal-name';
    name.textContent = s.strategy_name;

    const chip = document.createElement('span');
    chip.className = s.direction === 'BUY' ? 'chip-buy' : 'chip-sell';
    chip.textContent = s.direction ?? '—';

    const params = document.createElement('div');
    params.className = 'signal-params';
    params.textContent = `E: ${s.entry?.toFixed(3) ?? '—'}  SL: ${s.sl?.toFixed(3) ?? '—'}  TP1: ${s.tp1?.toFixed(3) ?? '—'}`;

    const conf = document.createElement('div');
    conf.className = 'signal-confidence';
    conf.textContent = `${s.confidence ?? '—'}% confidence`;

    row.appendChild(name);
    row.appendChild(chip);
    row.appendChild(params);
    row.appendChild(conf);
    list.appendChild(row);
  }
}
