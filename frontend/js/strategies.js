let activeFilter = 'all';
let strategiesData = [];

const TYPE_LABELS = {
  'Trend': 'Trend', 'Breakout': 'Breakout',
  'Mean Reversion': 'Mean Rev.', 'Hybrid': 'Hybrid', 'Event-Driven': 'Event'
};

document.addEventListener('DOMContentLoaded', () => {
  initSharedNav();
  setupFilterButtons();
  startPolling(fetchStrategies);
});

function setupFilterButtons() {
  document.getElementById('filter-bar').addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    activeFilter = btn.dataset.filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    applyFilter();
  });
}

async function fetchStrategies() {
  const [payload, dash] = await Promise.all([
    apiFetch('/api/strategies'),
    apiFetch('/api/dashboard')
  ]);
  fetchStatus();
  strategiesData = payload.strategies || [];
  if (dash.price?.bid != null) updateNavPrice(dash.price.bid);
  updateFilterCounts(strategiesData);
  renderCards(strategiesData);
  applyFilter();
}

function updateFilterCounts(strategies) {
  const valid   = strategies.filter(s => s.status === 'VALID_TRADE').length;
  const wait    = strategies.filter(s => s.status === 'WAIT_FOR_LEVELS').length;
  const noTrade = strategies.filter(s => s.status === 'NO_TRADE').length;
  document.getElementById('count-all').textContent      = `(${strategies.length})`;
  document.getElementById('count-valid').textContent    = `(${valid})`;
  document.getElementById('count-wait').textContent     = `(${wait})`;
  document.getElementById('count-no-trade').textContent = `(${noTrade})`;
}

function renderCards(strategies) {
  const grid = document.getElementById('cards-grid');
  grid.innerHTML = '';
  for (const s of strategies) {
    grid.appendChild(buildCard(s));
  }
}

function buildCard(s) {
  const statusClass = s.status === 'VALID_TRADE' ? 'valid' : s.status === 'WAIT_FOR_LEVELS' ? 'wait' : 'no-trade';
  const card = document.createElement('div');
  card.className = `card ${statusClass}`;
  card.dataset.status = s.status;
  card.dataset.strategyId = s.strategy_id;

  const hdr = document.createElement('div');
  hdr.className = 'card-header';
  const numEl = document.createElement('span');
  numEl.className = 'card-num';
  numEl.textContent = `#${s.strategy_id}`;
  const typeEl = document.createElement('span');
  typeEl.className = 'type-badge';
  typeEl.textContent = TYPE_LABELS[s.strategy_type] ?? s.strategy_type ?? '—';
  hdr.appendChild(numEl);
  hdr.appendChild(typeEl);

  const nameEl = document.createElement('div');
  nameEl.className = 'card-name';
  nameEl.textContent = s.strategy_name;

  const tagsEl = document.createElement('div');
  tagsEl.className = 'card-tags';
  const tfList = Array.isArray(s.timeframes)
    ? s.timeframes
    : (s.timeframes || '').split('/').filter(Boolean);
  for (const tf of tfList) {
    const chip = document.createElement('span');
    chip.className = 'tf-chip';
    chip.textContent = tf.trim();
    tagsEl.appendChild(chip);
  }

  let paramsEl = null;
  if (s.status !== 'NO_TRADE') {
    paramsEl = document.createElement('div');
    paramsEl.className = 'card-params';

    const dirChip = document.createElement('div');
    dirChip.style.marginBottom = '0.5rem';
    const chip = document.createElement('span');
    chip.className = s.direction === 'BUY' ? 'chip-buy' : 'chip-sell';
    chip.textContent = s.direction ?? '—';
    dirChip.appendChild(chip);

    for (const [label, value] of [
      ['Entry', s.entry?.toFixed(3)],
      ['Stop Loss', s.sl?.toFixed(3)],
      ['TP1', s.tp1?.toFixed(3)],
      ['RRR', s.rrr?.toFixed(2)]
    ]) {
      const row = document.createElement('div');
      row.className = 'card-param-row';
      const lbl = document.createElement('span');
      lbl.className = 'card-param-label';
      lbl.textContent = label;
      const val = document.createElement('span');
      val.className = 'card-param-value';
      val.textContent = value ?? '—';
      row.appendChild(lbl);
      row.appendChild(val);
      paramsEl.appendChild(row);
    }
    paramsEl.insertBefore(dirChip, paramsEl.firstChild);
  }

  const confContainer = document.createElement('div');
  confContainer.className = 'score-bar-container';
  const confLabel = document.createElement('div');
  confLabel.className = 'score-bar-label';
  const confLabelText = document.createElement('span');
  confLabelText.textContent = 'Confidence';
  const confNum = document.createElement('span');
  confNum.textContent = `${s.confidence ?? '—'}%`;
  confLabel.appendChild(confLabelText);
  confLabel.appendChild(confNum);
  const track = document.createElement('div');
  track.className = 'score-bar-track';
  const fill = document.createElement('div');
  fill.className = 'score-bar-fill';
  fill.style.width = `${s.confidence ?? 0}%`;
  fill.style.background = scoreColour(s.confidence ?? 0);
  track.appendChild(fill);
  confContainer.appendChild(confLabel);
  confContainer.appendChild(track);

  const footer = document.createElement('div');
  footer.className = 'card-footer';
  const statusRow = document.createElement('div');
  statusRow.className = 'card-status-row';
  const statusLabelEl = document.createElement('span');
  statusLabelEl.className = `badge badge-${statusClass}`;
  statusLabelEl.textContent = s.status === 'NO_TRADE' ? 'No Trade'
    : s.status === 'VALID_TRADE' ? 'Valid Trade'
    : 'Wait for Levels';
  const timeEl = document.createElement('span');
  timeEl.className = 'card-time';
  timeEl.textContent = relativeTime(s.timestamp);
  statusRow.appendChild(statusLabelEl);
  statusRow.appendChild(timeEl);
  footer.appendChild(statusRow);

  card.appendChild(hdr);
  card.appendChild(nameEl);
  card.appendChild(tagsEl);
  if (paramsEl) card.appendChild(paramsEl);
  card.appendChild(confContainer);
  card.appendChild(footer);

  card.addEventListener('click', () => {
    window.location.href = `/detail.html?strategy=${s.strategy_id}`;
  });

  return card;
}

function applyFilter() {
  document.querySelectorAll('.card').forEach(card => {
    if (activeFilter === 'all' || card.dataset.status === activeFilter) {
      card.classList.remove('hidden');
    } else {
      card.classList.add('hidden');
    }
  });
}
