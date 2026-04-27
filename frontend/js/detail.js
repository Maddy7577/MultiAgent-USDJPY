const params = new URLSearchParams(window.location.search);
const rawId = params.get('strategy');
const strategyId = parseInt(rawId, 10);

document.addEventListener('DOMContentLoaded', () => {
  if (!rawId || isNaN(strategyId) || strategyId < 1 || strategyId > 20) {
    document.getElementById('loading-msg').style.display = 'none';
    document.getElementById('error-view').style.display = 'block';
    return;
  }
  initSharedNav();
  startPolling(fetchDetail);
});

async function fetchDetail() {
  let data;
  try {
    data = await apiFetch(`/api/strategy/${strategyId}`);
  } catch (err) {
    if (/HTTP 404|No data for strategy/i.test(err.message)) {
      document.getElementById('loading-msg').style.display = 'none';
      const errView = document.getElementById('error-view');
      errView.querySelector('h2').textContent = 'No Data Yet';
      errView.querySelector('p').textContent =
        'This strategy has not been evaluated yet. Run an evaluation cycle or wait for the scheduler to fire.';
      errView.style.display = 'block';
      return;
    }
    throw err;
  }
  fetchStatus();
  document.getElementById('loading-msg').style.display = 'none';
  document.getElementById('detail-view').style.display = 'block';
  renderHeader(data);
  renderParams(data);
  renderScores(data);
  renderAgents(data.agent_scores);
  renderVerdict(data);
}

function renderHeader(d) {
  document.getElementById('detail-name').textContent = d.strategy_name;

  const tags = document.getElementById('detail-tags');
  tags.innerHTML = '';
  const typeBadge = document.createElement('span');
  typeBadge.className = 'type-badge';
  typeBadge.textContent = d.strategy_type ?? '—';
  tags.appendChild(typeBadge);

  const tfList = Array.isArray(d.timeframes)
    ? d.timeframes
    : (d.timeframes || '').split('/').filter(Boolean);
  for (const tf of tfList) {
    const chip = document.createElement('span');
    chip.className = 'tf-chip';
    chip.textContent = tf.trim();
    tags.appendChild(chip);
  }

  const statusClass = d.status === 'VALID_TRADE' ? 'valid'
    : d.status === 'WAIT_FOR_LEVELS' ? 'wait'
    : 'no-trade';
  const statusBadge = document.getElementById('detail-status-badge');
  statusBadge.innerHTML = '';
  const badge = document.createElement('span');
  badge.className = `badge badge-${statusClass} badge-large`;
  badge.textContent = d.status === 'NO_TRADE' ? 'No Trade'
    : d.status === 'VALID_TRADE' ? 'Valid Trade'
    : 'Wait for Levels';
  statusBadge.appendChild(badge);

  document.getElementById('detail-eval-time').textContent =
    d.timestamp ? `Evaluated: ${new Date(d.timestamp).toUTCString()}` : '';
}

function renderParams(d) {
  const section = document.getElementById('params-section');
  const grid = document.getElementById('params-grid');
  grid.innerHTML = '';

  if (d.status === 'NO_TRADE') {
    section.style.display = 'none';
    return;
  }
  section.style.display = 'block';

  const rows = [
    ['Direction', null, d.direction],
    ['Entry',     null, d.entry?.toFixed(3)],
    ['Stop Loss', d.entry && d.sl ? `${pips(d.entry, d.sl)} pips` : null, d.sl?.toFixed(3)],
    ['Take Profit 1', d.entry && d.tp1 ? `+${pips(d.entry, d.tp1)} pips` : null, d.tp1?.toFixed(3)],
    ['Take Profit 2', null, d.tp2?.toFixed(3)],
    ['Take Profit 3', null, d.tp3 ? d.tp3.toFixed(3) : null],
    ['Risk-Reward', null, d.rrr ? `${d.rrr.toFixed(2)}:1` : null],
  ];

  if (d.status === 'WAIT_FOR_LEVELS') {
    rows.push(['Wait Zone', null, d.wait_zone ?? 'Watch for price to reach entry zone']);
  }

  for (const [label, sub, value] of rows) {
    if (value == null && label !== 'Wait Zone') continue;
    const item = document.createElement('div');
    item.className = 'param-item';
    const lbl = document.createElement('span');
    lbl.className = 'param-label';
    lbl.textContent = label;
    const valWrap = document.createElement('div');
    valWrap.style.textAlign = 'right';

    if (label === 'Direction') {
      const chip = document.createElement('span');
      chip.className = d.direction === 'BUY' ? 'chip-buy' : 'chip-sell';
      chip.textContent = d.direction ?? '—';
      valWrap.appendChild(chip);
    } else {
      const val = document.createElement('div');
      val.className = 'param-value';
      val.textContent = value ?? '—';
      valWrap.appendChild(val);
      if (sub) {
        const subEl = document.createElement('div');
        subEl.className = 'param-sub';
        subEl.textContent = sub;
        valWrap.appendChild(subEl);
      }
    }

    item.appendChild(lbl);
    item.appendChild(valWrap);
    grid.appendChild(item);
  }

  if (d.status === 'WAIT_FOR_LEVELS' && d.conditions_to_meet?.length) {
    const condSection = document.createElement('div');
    condSection.style.marginTop = '1rem';
    const condTitle = document.createElement('div');
    condTitle.style.cssText = 'font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;';
    condTitle.textContent = 'Conditions to Meet Before Entry:';
    const condList = document.createElement('ul');
    condList.className = 'verdict-list';
    condList.style.color = 'var(--text-secondary)';
    for (const cond of d.conditions_to_meet) {
      const li = document.createElement('li');
      li.textContent = cond;
      condList.appendChild(li);
    }
    condSection.appendChild(condTitle);
    condSection.appendChild(condList);
    grid.appendChild(condSection);
  }
}

function renderScores(d) {
  setBar('conf-bar', 'conf-num', d.confidence);
  setBar('prob-bar', 'prob-num', d.probability);
}

function setBar(barId, numId, score) {
  document.getElementById(numId).textContent = score != null ? `${score}%` : '—';
  const bar = document.getElementById(barId);
  bar.style.width = `${score ?? 0}%`;
  bar.style.background = scoreColour(score ?? 0);
}

const CONDITION_ICONS   = { met: '✓', not_met: '✗', partial: '⚠' };
const CONDITION_CLASSES = { met: 'met', not_met: 'not-met', partial: 'partial' };

function renderAgents(agentScores) {
  const container = document.getElementById('agents-container');

  const expandedIndices = new Set();
  container.querySelectorAll('.agent-section').forEach((el, i) => {
    if (el.classList.contains('expanded')) expandedIndices.add(i);
  });

  container.innerHTML = '';

  if (!agentScores || typeof agentScores !== 'object') return;

  // Use full per-agent data when available (new format), else fall back to aggregate display
  const agentList = agentScores.agents || [
    { name: 'Opportunity Agent 1', score: agentScores.opp1_score, conditions: [], flags: [] },
    { name: 'Opportunity Agent 2', score: agentScores.opp2_score, conditions: [], flags: [] },
    { name: 'Risk Agent 1',        score: agentScores.risk1_score, conditions: [], flags: agentScores.critical_flags || [] },
    { name: 'Risk Agent 2',        score: agentScores.risk2_score, conditions: [], flags: [] },
  ];

  agentList.forEach((agent, idx) => {
    const section = document.createElement('div');
    section.className = 'agent-section' + (expandedIndices.has(idx) ? ' expanded' : '');

    const header = document.createElement('div');
    header.className = 'agent-header';
    header.addEventListener('click', () => section.classList.toggle('expanded'));

    const title = document.createElement('span');
    title.className = 'agent-title';
    title.textContent = agent.name;

    const scoreEl = document.createElement('span');
    scoreEl.className = 'agent-score';
    scoreEl.textContent = `Score: ${agent.score?.toFixed(1) ?? '—'}/10`;

    const chevron = document.createElement('span');
    chevron.className = 'agent-chevron';
    chevron.textContent = '▾';

    header.appendChild(title);
    header.appendChild(scoreEl);
    header.appendChild(chevron);

    const body = document.createElement('div');
    body.className = 'agent-body';

    // Conditions list (11 dimensions)
    if (agent.conditions?.length) {
      const condList = document.createElement('ul');
      condList.className = 'condition-list';
      for (const c of agent.conditions) {
        const li = document.createElement('li');
        li.className = 'condition-item';
        const icon = document.createElement('span');
        icon.className = `condition-icon ${CONDITION_CLASSES[c.result] ?? ''}`;
        icon.textContent = CONDITION_ICONS[c.result] ?? '?';
        const lbl = document.createElement('span');
        lbl.className = 'condition-label';
        lbl.textContent = c.label;
        li.appendChild(icon);
        li.appendChild(lbl);
        condList.appendChild(li);
      }
      body.appendChild(condList);
    }

    // Flags
    if (agent.flags?.length) {
      const flagsDiv = document.createElement('div');
      flagsDiv.className = 'flags-list';
      for (const flag of agent.flags) {
        const f = document.createElement('div');
        f.className = 'flag-item';
        f.textContent = flag;
        flagsDiv.appendChild(f);
      }
      body.appendChild(flagsDiv);
    }

    section.appendChild(header);
    section.appendChild(body);
    container.appendChild(section);
  });
}

function renderVerdict(d) {
  const forList = document.getElementById('reasons-for');
  const againstList = document.getElementById('reasons-against');
  forList.innerHTML = '';
  againstList.innerHTML = '';

  for (const reason of (d.reasons_for ?? [])) {
    const li = document.createElement('li');
    li.textContent = reason;
    forList.appendChild(li);
  }
  for (const reason of (d.reasons_against ?? [])) {
    const li = document.createElement('li');
    li.textContent = reason;
    againstList.appendChild(li);
  }

  document.getElementById('verdict-summary').textContent = d.verdict_summary ?? '';
}
