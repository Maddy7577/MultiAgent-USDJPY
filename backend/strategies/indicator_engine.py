"""Compute all shared indicators once per evaluation cycle."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from backend.strategies.base_strategy import (
    ema, ema_series, atr, rsi, macd, bollinger_bands, keltner_channel, donchian,
    adx_dmi, ichimoku, daily_pivots, detect_swing_points, get_session,
    is_bullish_engulfing, is_bearish_engulfing, is_inside_bar,
)


def compute_indicators(ohlcv: dict) -> dict:
    """Compute all indicators needed by any strategy. Called once per H1 cycle.

    Returns a flat dict keyed by "{TF}_{indicator}" (e.g. "H1_ema20", "H4_adx").
    Missing or insufficient data results in a None entry for that key.
    """
    ind: dict = {}
    now = datetime.now(timezone.utc)
    ind["utc_hour"] = now.hour
    ind["utc_minute"] = now.minute
    ind["session"] = get_session(now.hour, now.minute)

    for tf in ["M30", "H1", "H4", "D1"]:
        df = ohlcv.get(tf)
        if df is None or len(df) < 55:
            ind[f"{tf}_available"] = False
            continue

        ind[f"{tf}_available"] = True
        close = df["close"]
        curr = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else curr

        ind[f"{tf}_close"] = float(curr["close"])
        ind[f"{tf}_open"] = float(curr["open"])
        ind[f"{tf}_high"] = float(curr["high"])
        ind[f"{tf}_low"] = float(curr["low"])
        ind[f"{tf}_prev_close"] = float(prev["close"])

        ind[f"{tf}_ema20"] = ema(close, 20)
        ind[f"{tf}_ema50"] = ema(close, 50)
        if len(df) >= 200:
            ind[f"{tf}_ema200"] = ema(close, 200)
        else:
            ind[f"{tf}_ema200"] = None

        ind[f"{tf}_atr14"] = atr(df, 14)
        ind[f"{tf}_rsi14"] = rsi(close, 14)

        # Previous-bar RSI for crossover detection
        if len(df) >= 16:
            rsi_s = pd.Series([rsi(close.iloc[:i], 14) for i in range(len(df) - 10, len(df))])
            ind[f"{tf}_rsi14_prev"] = float(rsi_s.iloc[-2]) if len(rsi_s) >= 2 else ind[f"{tf}_rsi14"]
        else:
            ind[f"{tf}_rsi14_prev"] = ind[f"{tf}_rsi14"]

        # EMAs for crossover checks (series)
        ema50_s = ema_series(close, 50)
        ema200_s = ema_series(close, 200) if len(df) >= 200 else None
        if ema200_s is not None and len(ema50_s) >= 2:
            ind[f"{tf}_ema50_prev"] = float(ema50_s.iloc[-2])
            ind[f"{tf}_ema200_prev"] = float(ema200_s.iloc[-2])
            golden_cross = (float(ema50_s.iloc[-2]) < float(ema200_s.iloc[-2]) and
                            float(ema50_s.iloc[-1]) >= float(ema200_s.iloc[-1]))
            death_cross = (float(ema50_s.iloc[-2]) > float(ema200_s.iloc[-2]) and
                           float(ema50_s.iloc[-1]) <= float(ema200_s.iloc[-1]))
            ind[f"{tf}_golden_cross"] = golden_cross
            ind[f"{tf}_death_cross"] = death_cross
            # Check if cross happened within last 20 bars
            crossed_recently = False
            if len(ema50_s) >= 22:
                for i in range(2, 22):
                    e50_prev = float(ema50_s.iloc[-i - 1])
                    e200_prev = float(ema200_s.iloc[-i - 1])
                    e50_curr = float(ema50_s.iloc[-i])
                    e200_curr = float(ema200_s.iloc[-i])
                    if (e50_prev < e200_prev and e50_curr >= e200_curr) or \
                       (e50_prev > e200_prev and e50_curr <= e200_curr):
                        crossed_recently = True
                        break
            ind[f"{tf}_ema_crossed_recently"] = crossed_recently
        else:
            ind[f"{tf}_golden_cross"] = False
            ind[f"{tf}_death_cross"] = False
            ind[f"{tf}_ema_crossed_recently"] = False

        swings = detect_swing_points(df, fractal_size=5)
        ind[f"{tf}_swing_high"] = swings["swing_high"]
        ind[f"{tf}_swing_low"] = swings["swing_low"]

        ind[f"{tf}_bullish_engulfing"] = is_bullish_engulfing(df)
        ind[f"{tf}_bearish_engulfing"] = is_bearish_engulfing(df)
        ind[f"{tf}_inside_bar"] = is_inside_bar(df)

    # MACD on H1
    h1_df = ohlcv.get("H1")
    if h1_df is not None and len(h1_df) >= 40:
        ind["H1_macd"] = macd(h1_df["close"])
    else:
        ind["H1_macd"] = None

    # ADX/DMI on H4
    h4_df = ohlcv.get("H4")
    if h4_df is not None and len(h4_df) >= 30:
        adx_data = adx_dmi(h4_df)
        ind["H4_adx14"] = adx_data["adx"]
        ind["H4_plus_di"] = adx_data["plus_di"]
        ind["H4_minus_di"] = adx_data["minus_di"]
    else:
        ind["H4_adx14"] = None
        ind["H4_plus_di"] = None
        ind["H4_minus_di"] = None

    # ADX on H1
    if h1_df is not None and len(h1_df) >= 30:
        adx_h1 = adx_dmi(h1_df)
        ind["H1_adx14"] = adx_h1["adx"]
        ind["H1_plus_di"] = adx_h1["plus_di"]
        ind["H1_minus_di"] = adx_h1["minus_di"]
    else:
        ind["H1_adx14"] = None

    # Bollinger Bands on H1 and H4
    for tf, df_ref in [("H1", h1_df), ("H4", h4_df)]:
        if df_ref is not None and len(df_ref) >= 22:
            ind[f"{tf}_bb"] = bollinger_bands(df_ref["close"])
        else:
            ind[f"{tf}_bb"] = None

    # Keltner Channel on H1
    if h1_df is not None and len(h1_df) >= 25:
        ind["H1_keltner"] = keltner_channel(h1_df)
    else:
        ind["H1_keltner"] = None

    # Donchian on H4 (20-bar and 10-bar)
    if h4_df is not None and len(h4_df) >= 22:
        ind["H4_donchian20"] = donchian(h4_df, 20)
        ind["H4_donchian10"] = donchian(h4_df, 10)
    else:
        ind["H4_donchian20"] = None
        ind["H4_donchian10"] = None

    # Donchian on D1
    d1_df = ohlcv.get("D1")
    if d1_df is not None and len(d1_df) >= 22:
        ind["D1_donchian20"] = donchian(d1_df, 20)
        ind["D1_donchian10"] = donchian(d1_df, 10)
    else:
        ind["D1_donchian20"] = None
        ind["D1_donchian10"] = None

    # Ichimoku on H4
    if h4_df is not None and len(h4_df) >= 55:
        ind["H4_ichimoku"] = ichimoku(h4_df)
    else:
        ind["H4_ichimoku"] = None

    # Daily Pivots
    if d1_df is not None and len(d1_df) >= 2:
        ind["daily_pivots"] = daily_pivots(d1_df)
    else:
        ind["daily_pivots"] = None

    # H1 previous-bar engulfing check (for strategies that need bar -2 vs bar -1)
    # The is_bullish/bearish_engulfing functions already check last 2 bars of df

    return ind
