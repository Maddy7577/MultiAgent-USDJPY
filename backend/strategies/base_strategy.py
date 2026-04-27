from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class StrategyResult:
    strategy_id: int
    strategy_name: str
    strategy_type: str
    status: str  # VALID_TRADE / WAIT_FOR_LEVELS / NO_TRADE
    direction: Optional[str]
    entry: Optional[float]
    sl: Optional[float]
    tp1: Optional[float]
    tp2: Optional[float]
    tp3: Optional[float]
    rrr: Optional[float]
    confidence: int
    probability: int
    timeframes: list
    wait_zone: Optional[str]
    conditions_to_meet: list
    reasons_for: list
    reasons_against: list
    verdict_summary: str
    evaluated_at: datetime
    agent_scores: dict

    def to_db_dict(self) -> dict:
        import json
        return {
            "timestamp": self.evaluated_at.isoformat(),
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type,
            "status": self.status,
            "direction": self.direction,
            "entry": self.entry,
            "sl": self.sl,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "rrr": self.rrr,
            "confidence": self.confidence,
            "probability": self.probability,
            "timeframes": json.dumps(self.timeframes),
            "wait_zone": self.wait_zone,
            "conditions_to_meet": json.dumps(self.conditions_to_meet),
            "reasons_for": json.dumps(self.reasons_for),
            "reasons_against": json.dumps(self.reasons_against),
            "verdict_summary": self.verdict_summary,
            "agent_scores": json.dumps(self.agent_scores),
        }


class BaseStrategy:
    STRATEGY_ID: int = 0
    STRATEGY_NAME: str = "Base"
    STRATEGY_TYPE: str = "Unknown"
    TIMEFRAMES: list = []

    def __init__(self, market_data: dict):
        self.md = market_data
        self.ohlcv = market_data.get("ohlcv", {})
        self.ind = market_data.get("indicators", {})
        self.ctx = market_data.get("context", {})
        self.now = datetime.now(timezone.utc)

    def evaluate(self) -> StrategyResult:
        raise NotImplementedError

    def _has_data(self, *timeframes: str) -> bool:
        for tf in timeframes:
            df = self.ohlcv.get(tf)
            if df is None or len(df) < 50:
                return False
        return True

    def _no_trade(self, reasons: list, confidence: int = 10, probability: int = 10) -> StrategyResult:
        return StrategyResult(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE,
            status="NO_TRADE",
            direction=None,
            entry=None, sl=None, tp1=None, tp2=None, tp3=None, rrr=None,
            confidence=confidence, probability=probability,
            timeframes=self.TIMEFRAMES,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=[], reasons_against=reasons,
            verdict_summary=f"NO TRADE: {reasons[0] if reasons else 'Conditions not met'}",
            evaluated_at=self.now,
            agent_scores={},
        )

    def _wait(self, direction: str, wait_zone: str, conditions_to_meet: list,
              reasons_for: list, reasons_against: list,
              entry: Optional[float] = None, sl: Optional[float] = None,
              tp1: Optional[float] = None) -> StrategyResult:
        rrr = None
        if entry is not None and sl is not None and tp1 is not None:
            risk = abs(entry - sl)
            reward = abs(tp1 - entry)
            rrr = round(reward / risk, 2) if risk > 0 else None
        total = len(reasons_for) + len(conditions_to_meet)
        compliance = len(reasons_for) / total if total > 0 else 0.5
        confidence = max(35, min(65, int(35 + 30 * compliance)))
        return StrategyResult(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE,
            status="WAIT_FOR_LEVELS",
            direction=direction,
            entry=entry, sl=sl, tp1=tp1, tp2=None, tp3=None, rrr=rrr,
            confidence=confidence, probability=confidence,
            timeframes=self.TIMEFRAMES,
            wait_zone=wait_zone,
            conditions_to_meet=conditions_to_meet,
            reasons_for=reasons_for,
            reasons_against=reasons_against,
            verdict_summary=f"WAIT FOR LEVELS: {wait_zone}",
            evaluated_at=self.now,
            agent_scores={},
        )


# ─── Indicator Utilities ──────────────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> float:
    if len(series) < 2:
        return float(series.iloc[-1])
    return float(series.ewm(span=period, adjust=False).mean().iloc[-1])


def ema_series(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> float:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    val = tr.ewm(span=period, adjust=False).mean().iloc[-1]
    return float(val) if not np.isnan(val) else 0.0


def rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)
    avg_gain = gains.ewm(span=period, adjust=False).mean().iloc[-1]
    avg_loss = losses.ewm(span=period, adjust=False).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - 100.0 / (1.0 + rs))


def rsi_series(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)
    avg_gain = gains.ewm(span=period, adjust=False).mean()
    avg_loss = losses.ewm(span=period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100.0 - 100.0 / (1.0 + rs)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal_period: int = 9) -> dict:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "line": float(macd_line.iloc[-1]),
        "signal": float(signal_line.iloc[-1]),
        "histogram": float(histogram.iloc[-1]),
        "line_prev": float(macd_line.iloc[-2]) if len(macd_line) > 1 else float(macd_line.iloc[-1]),
        "signal_prev": float(signal_line.iloc[-2]) if len(signal_line) > 1 else float(signal_line.iloc[-1]),
        "bullish_cross": (float(macd_line.iloc[-2]) < float(signal_line.iloc[-2]) and
                          float(macd_line.iloc[-1]) >= float(signal_line.iloc[-1])) if len(macd_line) > 1 else False,
        "bearish_cross": (float(macd_line.iloc[-2]) > float(signal_line.iloc[-2]) and
                          float(macd_line.iloc[-1]) <= float(signal_line.iloc[-1])) if len(macd_line) > 1 else False,
    }


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    return {
        "upper": float((sma + std_dev * std).iloc[-1]),
        "middle": float(sma.iloc[-1]),
        "lower": float((sma - std_dev * std).iloc[-1]),
        "std": float(std.iloc[-1]),
    }


def keltner_channel(df: pd.DataFrame, ema_period: int = 20, atr_period: int = 20, atr_mult: float = 2.0) -> dict:
    close = df["close"]
    midline = close.ewm(span=ema_period, adjust=False).mean()
    atr_val = atr(df, atr_period)
    mid = float(midline.iloc[-1])
    return {"upper": mid + atr_mult * atr_val, "middle": mid, "lower": mid - atr_mult * atr_val}


def donchian(df: pd.DataFrame, period: int = 20) -> dict:
    return {
        "upper": float(df["high"].rolling(period).max().iloc[-1]),
        "lower": float(df["low"].rolling(period).min().iloc[-1]),
    }


def adx_dmi(df: pd.DataFrame, period: int = 14) -> dict:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    atr14 = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / (atr14 + 1e-10)
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / (atr14 + 1e-10)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx_val = dx.ewm(span=period, adjust=False).mean()

    return {
        "adx": float(adx_val.iloc[-1]),
        "plus_di": float(plus_di.iloc[-1]),
        "minus_di": float(minus_di.iloc[-1]),
    }


def ichimoku(df: pd.DataFrame) -> dict:
    high, low, close = df["high"], df["low"], df["close"]
    n = len(df)

    tenkan_s = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun_s = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a_s = (tenkan_s + kijun_s) / 2
    senkou_b_s = (high.rolling(52).max() + low.rolling(52).min()) / 2

    tenkan = float(tenkan_s.iloc[-1])
    kijun = float(kijun_s.iloc[-1])
    senkou_a_current = float(senkou_a_s.iloc[-27]) if n >= 27 else float(senkou_a_s.dropna().iloc[0])
    senkou_b_current = float(senkou_b_s.iloc[-27]) if n >= 27 else float(senkou_b_s.dropna().iloc[0])
    senkou_a_future = float(senkou_a_s.iloc[-1])
    senkou_b_future = float(senkou_b_s.iloc[-1])

    chikou = float(close.iloc[-1])
    close_26_ago = float(close.iloc[-27]) if n >= 27 else float(close.iloc[0])

    kumo_top = max(senkou_a_current, senkou_b_current)
    kumo_bottom = min(senkou_a_current, senkou_b_current)
    kumo_thickness = kumo_top - kumo_bottom

    tenkan_prev = float(tenkan_s.iloc[-2]) if n >= 2 else tenkan
    kijun_prev = float(kijun_s.iloc[-2]) if n >= 2 else kijun

    return {
        "tenkan": tenkan,
        "kijun": kijun,
        "senkou_a_current": senkou_a_current,
        "senkou_b_current": senkou_b_current,
        "senkou_a_future": senkou_a_future,
        "senkou_b_future": senkou_b_future,
        "chikou": chikou,
        "close_26_ago": close_26_ago,
        "kumo_top": kumo_top,
        "kumo_bottom": kumo_bottom,
        "kumo_thickness": kumo_thickness,
        "tk_bullish_cross": tenkan_prev < kijun_prev and tenkan > kijun,
        "tk_bearish_cross": tenkan_prev > kijun_prev and tenkan < kijun,
    }


def daily_pivots(df: pd.DataFrame) -> dict:
    if len(df) < 2:
        return {}
    prev = df.iloc[-2]
    P = (float(prev["high"]) + float(prev["low"]) + float(prev["close"])) / 3
    r = float(prev["high"]) - float(prev["low"])
    return {
        "P": P,
        "R1": 2 * P - float(prev["low"]),
        "R2": P + r,
        "R3": float(prev["high"]) + 2 * (P - float(prev["low"])),
        "S1": 2 * P - float(prev["high"]),
        "S2": P - r,
        "S3": float(prev["low"]) - 2 * (float(prev["high"]) - P),
    }


def detect_swing_points(df: pd.DataFrame, fractal_size: int = 5) -> dict:
    highs = df["high"].values
    lows = df["low"].values
    n = len(highs)
    half = fractal_size // 2

    last_swing_high = None
    last_swing_low = None

    for i in range(n - half - 1, max(half, 0) - 1, -1):
        if last_swing_high is None:
            if (all(highs[i] >= highs[i - j] for j in range(1, half + 1)) and
                    all(highs[i] >= highs[i + j] for j in range(1, half + 1))):
                last_swing_high = float(highs[i])
        if last_swing_low is None:
            if (all(lows[i] <= lows[i - j] for j in range(1, half + 1)) and
                    all(lows[i] <= lows[i + j] for j in range(1, half + 1))):
                last_swing_low = float(lows[i])
        if last_swing_high is not None and last_swing_low is not None:
            break

    return {"swing_high": last_swing_high, "swing_low": last_swing_low}


def get_session(hour: int, minute: int) -> str:
    total = hour * 60 + minute
    if total < 7 * 60:
        return "Tokyo"
    elif total < 12 * 60:
        return "London"
    elif total < 16 * 60:
        return "LondonNY"
    elif total < 22 * 60:
        return "NY"
    return "Off"


def is_bullish_engulfing(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    bodies = (df["close"] - df["open"]).abs()
    avg_body = float(bodies.iloc[-11:-1].mean()) if len(df) >= 11 else float(bodies.mean())
    curr_body = abs(float(curr["close"]) - float(curr["open"]))
    return (
        float(prev["close"]) < float(prev["open"]) and
        float(curr["close"]) > float(curr["open"]) and
        float(curr["open"]) <= float(prev["close"]) and
        float(curr["close"]) >= float(prev["open"]) and
        (avg_body == 0 or curr_body >= 1.2 * avg_body)
    )


def is_bearish_engulfing(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    bodies = (df["close"] - df["open"]).abs()
    avg_body = float(bodies.iloc[-11:-1].mean()) if len(df) >= 11 else float(bodies.mean())
    curr_body = abs(float(curr["close"]) - float(curr["open"]))
    return (
        float(prev["close"]) > float(prev["open"]) and
        float(curr["close"]) < float(curr["open"]) and
        float(curr["open"]) >= float(prev["close"]) and
        float(curr["close"]) <= float(prev["open"]) and
        (avg_body == 0 or curr_body >= 1.2 * avg_body)
    )


def is_inside_bar(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    return float(curr["high"]) < float(prev["high"]) and float(curr["low"]) > float(prev["low"])


def is_bullish_pin_bar(bar: pd.Series) -> bool:
    body = abs(float(bar["close"]) - float(bar["open"]))
    total = float(bar["high"]) - float(bar["low"])
    if total == 0:
        return False
    lower_wick = min(float(bar["open"]), float(bar["close"])) - float(bar["low"])
    upper_wick = float(bar["high"]) - max(float(bar["open"]), float(bar["close"]))
    return lower_wick >= 2 * body and upper_wick < body and lower_wick >= 0.6 * total


def is_bearish_pin_bar(bar: pd.Series) -> bool:
    body = abs(float(bar["close"]) - float(bar["open"]))
    total = float(bar["high"]) - float(bar["low"])
    if total == 0:
        return False
    upper_wick = float(bar["high"]) - max(float(bar["open"]), float(bar["close"]))
    lower_wick = min(float(bar["open"]), float(bar["close"])) - float(bar["low"])
    return upper_wick >= 2 * body and lower_wick < body and upper_wick >= 0.6 * total


def detect_impulse_leg(df: pd.DataFrame, lookback: int = 50, min_pips: float = 100) -> Optional[dict]:
    if len(df) < lookback + 5:
        return None
    recent = df.tail(lookback)
    swings = detect_swing_points(recent, fractal_size=5)
    sh = swings.get("swing_high")
    sl = swings.get("swing_low")
    if sh is None or sl is None:
        return None
    range_ = sh - sl
    if range_ < min_pips * 0.01:
        return None
    current_close = float(df["close"].iloc[-1])
    direction = "UP" if current_close > (sh + sl) / 2 else "DOWN"
    return {"direction": direction, "high": sh, "low": sl, "range": range_}


def fibonacci_levels(impulse: dict) -> dict:
    h, l, r = impulse["high"], impulse["low"], impulse["range"]
    if impulse["direction"] == "UP":
        return {
            "impulse_high": h, "impulse_low": l,
            "ret_23.6": h - 0.236 * r,
            "ret_38.2": h - 0.382 * r,
            "ret_50.0": h - 0.500 * r,
            "ret_61.8": h - 0.618 * r,
            "ret_78.6": h - 0.786 * r,
            "ext_127.2": h + 0.272 * r,
            "ext_161.8": h + 0.618 * r,
        }
    else:
        return {
            "impulse_high": h, "impulse_low": l,
            "ret_23.6": l + 0.236 * r,
            "ret_38.2": l + 0.382 * r,
            "ret_50.0": l + 0.500 * r,
            "ret_61.8": l + 0.618 * r,
            "ret_78.6": l + 0.786 * r,
            "ext_127.2": l - 0.272 * r,
            "ext_161.8": l - 0.618 * r,
        }


def rrr_calc(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0:
        return 0.0
    return round(reward / risk, 2)
