const API_BASE = 'http://localhost:8000';

let isInFlight = false;
let countdown = 60;
let lastSuccessTime = null;

let navPrice, navClock, navCountdown, navMt5Dot, staleBanner;

function initSharedNav() {
  navPrice     = document.getElementById('nav-price');
  navClock     = document.getElementById('nav-clock');
  navCountdown = document.getElementById('nav-countdown');
  navMt5Dot    = document.getElementById('mt5-dot');
  staleBanner  = document.getElementById('stale-banner');

  setInterval(() => {
    if (navClock) navClock.textContent = new Date().toUTCString().slice(17, 25) + ' UTC';
  }, 1000);
}

function startPolling(fetchFn) {
  runFetch(fetchFn);

  setInterval(() => {
    countdown--;
    if (navCountdown) navCountdown.textContent = `Refreshing in: ${countdown}s`;
    if (countdown <= 0) {
      countdown = 60;
      if (!isInFlight) runFetch(fetchFn);
    }
  }, 1000);
}

async function runFetch(fetchFn) {
  if (isInFlight) return;
  isInFlight = true;
  try {
    await fetchFn();
    lastSuccessTime = new Date();
    hideStaleBanner();
  } catch (err) {
    showStaleBanner();
    console.error('[USDJPY Agent] Fetch error:', err);
  } finally {
    isInFlight = false;
    countdown = 60;
    if (navCountdown) navCountdown.textContent = `Refreshing in: ${countdown}s`;
  }
}

function showStaleBanner() {
  if (!staleBanner) return;
  let msg;
  if (lastSuccessTime === null) {
    msg = 'Cannot connect to server — make sure the backend is running (python backend/main.py)';
  } else {
    const ts = lastSuccessTime.toUTCString().slice(0, 25) + ' UTC';
    msg = `Stale data — last updated ${ts}`;
  }
  staleBanner.textContent = msg;
  staleBanner.classList.add('visible');
}
function hideStaleBanner() {
  if (staleBanner) staleBanner.classList.remove('visible');
}

function updateMt5Dot(connected) {
  if (!navMt5Dot) return;
  navMt5Dot.className = 'mt5-dot ' + (connected ? 'connected' : 'disconnected');
  navMt5Dot.title = connected ? 'MT5 Connected' : 'MT5 Disconnected';
}

function updateNavPrice(bid) {
  if (navPrice && bid != null) navPrice.textContent = `¥${bid.toFixed(3)}`;
}

function relativeTime(isoString) {
  if (!isoString) return '—';
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diff < 60)  return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)} mins ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function scoreColour(score) {
  if (score >= 75) return 'var(--color-valid)';
  if (score >= 50) return 'var(--color-wait)';
  return '#ef4444';
}

function vixLabel(vix) {
  if (vix < 15)  return 'Low';
  if (vix < 25)  return 'Elevated';
  return 'High';
}

function currentSession(utcHour) {
  if (utcHour >= 13 && utcHour < 22) return 'New York';
  if (utcHour >= 8  && utcHour < 17) return 'London';
  if (utcHour >= 0  && utcHour < 9)  return 'Tokyo';
  return 'Off-Hours';
}

function minsToNextSession(utcHour, utcMin) {
  const sessionStarts = [0, 8, 13];
  const totalMins = utcHour * 60 + utcMin;
  for (const h of sessionStarts) {
    const sessionMins = h * 60;
    if (sessionMins > totalMins) return sessionMins - totalMins;
  }
  return (24 * 60) - totalMins;
}

function pips(a, b) {
  return Math.abs((a - b) * 100).toFixed(1);
}

function countdownToUtc(isoString) {
  if (!isoString) return '—';
  const diff = Math.max(0, new Date(isoString).getTime() - Date.now());
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
}

async function apiFetch(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status} from ${path}`);
  const json = await res.json();
  if (!json.success) throw new Error(json.error || `API error from ${path}`);
  return json.data;
}

async function fetchStatus() {
  try {
    const data = await apiFetch('/api/status');
    updateMt5Dot(data.mt5_connected);
  } catch {
    updateMt5Dot(false);
  }
}
