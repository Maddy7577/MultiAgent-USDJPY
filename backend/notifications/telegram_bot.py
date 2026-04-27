import logging
import time

import requests

from backend import config

logger = logging.getLogger(__name__)

_TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_valid_trade_alert(result) -> bool:
    """
    Send a Telegram message for a VALID_TRADE result.
    Returns True on success, False after one retry.
    Never raises — all errors are logged.
    """
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — skipping alert for %s", result.strategy_name)
        return False

    text = _format_valid_trade(result)
    return _send(text)


def _format_valid_trade(result) -> str:
    entry = result.entry or 0.0
    sl = result.sl or 0.0
    tp1 = result.tp1 or 0.0

    sl_pips = (sl - entry) * 100
    tp1_pips = (tp1 - entry) * 100

    tfs = result.timeframes if isinstance(result.timeframes, list) else []
    reasons_for = result.reasons_for[:3] if isinstance(result.reasons_for, list) else []
    reasons_against = result.reasons_against[:2] if isinstance(result.reasons_against, list) else []

    lines = [
        "[USDJPY Smart Agent] 🔔 VALID TRADE",
        "",
        f"Strategy: {result.strategy_name} (#{result.strategy_id})",
        f"Direction: {result.direction}",
        f"Entry: {entry:.3f}",
        f"Stop Loss: {sl:.3f}  ({sl_pips:+.0f} pips)",
        f"TP1: {tp1:.3f}  ({tp1_pips:+.0f} pips)",
    ]

    if result.tp2:
        tp2_pips = (result.tp2 - entry) * 100
        lines.append(f"TP2: {result.tp2:.3f}  ({tp2_pips:+.0f} pips)")

    rrr_str = f"1:{result.rrr:.1f}" if result.rrr else "—"
    lines += [
        f"Risk-Reward: {rrr_str}",
        f"Confidence: {result.confidence}/100",
        f"Timeframes: {' / '.join(tfs)}",
        "",
    ]

    if reasons_for:
        lines.append(f"Why: {', '.join(reasons_for)}")
    if reasons_against:
        lines.append(f"Against: {', '.join(reasons_against)}")

    lines.append(f"\nEvaluated: {result.evaluated_at.strftime('%H:%M')} UTC")

    return "\n".join(lines)


def _send(text: str) -> bool:
    """POST to Telegram API. Retries once after 30 seconds on failure."""
    url = _TELEGRAM_URL.format(token=config.TELEGRAM_TOKEN)
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": text}

    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("Telegram alert sent successfully")
            return True
        except Exception as exc:
            logger.error("Telegram send attempt %d failed: %s", attempt + 1, exc)
            if attempt == 0:
                time.sleep(30)

    return False
