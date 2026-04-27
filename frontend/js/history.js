let currentPage = 1;
const PER_PAGE = 50;

document.addEventListener('DOMContentLoaded', () => {
  initSharedNav();
  fetchStatus();

  document.getElementById('apply-filters').addEventListener('click', () => {
    currentPage = 1;
    fetchAndRender();
  });

  document.getElementById('reset-filters').addEventListener('click', () => {
    document.getElementById('filter-strategy').value = '';
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-from').value = '';
    document.getElementById('filter-to').value = '';
    currentPage = 1;
    fetchAndRender();
  });

  fetchAndRender();
});

async function fetchAndRender() {
  const strategy = document.getElementById('filter-strategy').value;
  const status   = document.getElementById('filter-status').value;
  const from     = document.getElementById('filter-from').value;
  const to       = document.getElementById('filter-to').value;

  const params = new URLSearchParams({ page: currentPage, per_page: PER_PAGE });
  if (strategy) params.set('strategy_id', strategy);
  if (status)   params.set('status', status);
  if (from)     params.set('from_date', from);
  if (to)       params.set('to_date', to);

  const tbody = document.getElementById('history-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Loading…</td></tr>';

  try {
    const data = await apiFetch('/api/history?' + params.toString());
    renderTable(data.items);
    renderStatsBar(data.items, data.total);
    renderPagination(data.total, data.page, data.per_page);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state" style="color:var(--color-sell)">Error loading history: ${err.message}</td></tr>`;
  }
}

function renderTable(items) {
  const tbody = document.getElementById('history-tbody');

  if (!items || items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No signals match the current filters.</td></tr>';
    return;
  }

  tbody.innerHTML = '';
  for (const signal of items) {
    const tr = document.createElement('tr');
    tr.title = 'Click to view strategy detail';

    const ts = signal.timestamp
      ? new Date(signal.timestamp).toISOString().replace('T', ' ').slice(0, 16)
      : '—';

    const statusBadge = statusToHtml(signal.status);
    const dirChip     = dirToHtml(signal.direction);
    const entry  = signal.entry  != null ? signal.entry.toFixed(3)  : '—';
    const sl     = signal.sl     != null ? signal.sl.toFixed(3)     : '—';
    const tp1    = signal.tp1    != null ? signal.tp1.toFixed(3)    : '—';
    const rrr    = signal.rrr    != null ? `1:${signal.rrr.toFixed(1)}` : '—';
    const conf   = signal.confidence != null ? `${signal.confidence}/100` : '—';

    tr.innerHTML = `
      <td>${ts}</td>
      <td>${signal.strategy_name || '—'}</td>
      <td>${statusBadge}</td>
      <td>${dirChip}</td>
      <td>${entry}</td>
      <td>${sl}</td>
      <td>${tp1}</td>
      <td>${rrr}</td>
      <td>${conf}</td>
      <td class="${outcomeClass(signal.outcome)}" data-signal-id="${signal.id}" data-outcome="${signal.outcome || 'PENDING'}"></td>
    `;

    const outcomeTd = tr.querySelector('td[data-signal-id]');
    outcomeTd.textContent = signal.outcome || 'PENDING';

    // Only VALID_TRADE rows with PENDING outcome are editable
    if (signal.status === 'VALID_TRADE' && (!signal.outcome || signal.outcome === 'PENDING')) {
      outcomeTd.title = 'Click to update outcome';
      outcomeTd.style.cursor = 'pointer';
      outcomeTd.addEventListener('click', (e) => {
        e.stopPropagation();
        handleOutcomeEdit(signal.id, outcomeTd);
      });
    }

    // Row click → detail page (only if not clicking the outcome cell)
    tr.addEventListener('click', (e) => {
      if (e.target === outcomeTd || outcomeTd.contains(e.target)) return;
      window.location.href = `/detail.html?strategy=${signal.strategy_id}`;
    });

    tbody.appendChild(tr);
  }
}

function renderStatsBar(items, total) {
  const validItems    = items.filter(s => s.status === 'VALID_TRADE');
  const resolved      = validItems.filter(s => s.outcome === 'WIN' || s.outcome === 'LOSS');
  const wins          = resolved.filter(s => s.outcome === 'WIN');
  const avgConf       = validItems.length > 0
    ? Math.round(validItems.reduce((sum, s) => sum + (s.confidence || 0), 0) / validItems.length)
    : null;

  const winRateText = resolved.length < 10
    ? 'Insufficient data'
    : `${Math.round(wins.length / resolved.length * 100)}%`;

  document.getElementById('stat-total').textContent    = `${total} signals`;
  document.getElementById('stat-valid').textContent    = `${validItems.length} VALID TRADE`;
  document.getElementById('stat-winrate').textContent  = `Win Rate: ${winRateText}`;
  document.getElementById('stat-avg-conf').textContent = avgConf != null
    ? `Avg Confidence: ${avgConf}/100`
    : 'Avg Confidence: —';
}

function renderPagination(total, page, perPage) {
  const totalPages = Math.ceil(total / perPage);
  const container  = document.getElementById('pagination');
  container.innerHTML = '';
  if (totalPages <= 1) return;

  if (page > 1) {
    const btn = document.createElement('button');
    btn.className = 'page-btn';
    btn.textContent = '← Prev';
    btn.onclick = () => { currentPage--; fetchAndRender(); };
    container.appendChild(btn);
  }

  const info = document.createElement('span');
  info.className = 'page-info';
  info.textContent = `Page ${page} of ${totalPages} (${total} total)`;
  container.appendChild(info);

  if (page < totalPages) {
    const btn = document.createElement('button');
    btn.className = 'page-btn';
    btn.textContent = 'Next →';
    btn.onclick = () => { currentPage++; fetchAndRender(); };
    container.appendChild(btn);
  }
}

async function handleOutcomeEdit(signalId, td) {
  const select = document.createElement('select');
  select.className = 'outcome-select';
  for (const opt of ['WIN', 'LOSS', 'N/A']) {
    const o = document.createElement('option');
    o.value = opt;
    o.textContent = opt;
    select.appendChild(o);
  }
  td.innerHTML = '';
  td.appendChild(select);
  select.focus();

  select.onchange = async () => {
    const outcome = select.value;
    td.textContent = 'Saving…';
    try {
      const res = await fetch(`${API_BASE}/api/history/${signalId}/outcome`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outcome }),
      });
      if (res.ok) {
        td.textContent = outcome;
        td.className = outcomeClass(outcome);
        td.title = '';
        td.style.cursor = 'default';
      } else {
        td.textContent = 'Error';
      }
    } catch {
      td.textContent = 'Error';
    }
  };

  // Cancel on blur without selecting
  select.onblur = () => {
    if (td.contains(select)) {
      const current = td.dataset.outcome || 'PENDING';
      td.textContent = current;
      td.className = outcomeClass(current);
    }
  };
}

function statusToHtml(status) {
  const map = {
    VALID_TRADE:    '<span class="badge badge-valid">Valid Trade</span>',
    WAIT_FOR_LEVELS:'<span class="badge badge-wait">Wait</span>',
    NO_TRADE:       '<span class="badge badge-no-trade">No Trade</span>',
  };
  return map[status] || `<span>${status || '—'}</span>`;
}

function dirToHtml(dir) {
  if (!dir) return '—';
  return dir === 'BUY'
    ? '<span class="chip-buy">BUY</span>'
    : '<span class="chip-sell">SELL</span>';
}

function outcomeClass(outcome) {
  const map = { WIN: 'outcome-win', LOSS: 'outcome-loss', 'N/A': 'outcome-na' };
  return map[outcome] || 'outcome-pending';
}
