"""RiskAgent — pure scoring function for negative trade factors."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskResult:
    risk_score: float   # 0–10 (10 = maximum risk / strongest case against)
    risk_flags: list = field(default_factory=list)
    critical_flags: list = field(default_factory=list)
    conditions: list = field(default_factory=list)  # 11 dimensions, each {label, result}
    agent_id: int = 1


class RiskAgent:
    """Evaluates reasons NOT to take a trade.

    Two instances per strategy (agent_id 1 and 2) use slightly different weights
    to expose consensus vs divergence on risk.
    """

    _WEIGHTS = {
        1: {"news": 0.30, "htf_conflict": 0.30, "rrr": 0.20, "market_cond": 0.20},
        2: {"news": 0.25, "htf_conflict": 0.25, "rrr": 0.30, "market_cond": 0.20},
    }

    def __init__(self, agent_id: int = 1):
        self.agent_id = agent_id
        self._w = self._WEIGHTS.get(agent_id, self._WEIGHTS[1])

    def evaluate(
        self,
        news_imminent: bool,
        htf_conflict: bool,           # H4/Daily trend conflicts with trade direction
        rrr: Optional[float],         # Risk-Reward Ratio
        spread_pips: float,
        current_price: float,
        direction: Optional[str],     # BUY or SELL
        strategy_flags: Optional[list] = None,  # strategy-specific risk issues
    ) -> RiskResult:
        """Score the risk from 0 (no risk) to 10 (maximum risk)."""
        risk_flags = []
        critical_flags = []
        strategy_flags = strategy_flags or []

        # --- News risk ---
        news_risk = 1.0 if news_imminent else 0.0
        if news_imminent:
            critical_flags.append("High-impact news within 30 minutes")

        # --- HTF conflict ---
        htf_risk = 0.8 if htf_conflict else 0.0
        if htf_conflict:
            risk_flags.append("Higher-timeframe trend in conflict")

        # --- RRR risk ---
        if rrr is None or rrr < 1.0:
            rrr_risk = 0.9
            risk_flags.append(f"Poor RRR: {rrr}")
        elif rrr < 1.5:
            rrr_risk = 0.5
            risk_flags.append(f"Borderline RRR: {rrr:.2f}")
        else:
            rrr_risk = 0.0

        # --- Market condition risk ---
        market_risk = 0.0
        if spread_pips > 3.0:
            market_risk = 1.0
            critical_flags.append(f"Spread {spread_pips:.1f} pips — illiquid conditions")
        elif spread_pips > 1.5:
            market_risk = 0.4
            risk_flags.append(f"Elevated spread: {spread_pips:.1f} pips")

        if direction == "BUY" and current_price > 155.00:
            market_risk = max(market_risk, 0.8)
            critical_flags.append("USDJPY above 155.00 — BoJ intervention zone")

        # --- Strategy-specific flags ---
        extra_risk = min(1.0, len(strategy_flags) * 0.25)
        risk_flags.extend(strategy_flags)

        raw = (
            self._w["news"] * news_risk +
            self._w["htf_conflict"] * htf_risk +
            self._w["rrr"] * rrr_risk +
            self._w["market_cond"] * market_risk
        ) + extra_risk * 0.2

        if self.agent_id == 2:
            variance = 0.05 * (news_risk - htf_risk)
            raw = max(0.0, min(1.0, raw + variance))

        score = round(min(10.0, raw * 10.0), 2)
        conditions = self._build_conditions(
            news_imminent, htf_conflict, rrr, spread_pips,
            current_price, direction, strategy_flags
        )
        return RiskResult(
            risk_score=score,
            risk_flags=risk_flags,
            critical_flags=critical_flags,
            conditions=conditions,
            agent_id=self.agent_id,
        )

    def _build_conditions(
        self,
        news_imminent: bool,
        htf_conflict: bool,
        rrr: Optional[float],
        spread_pips: float,
        current_price: float,
        direction: Optional[str],
        strategy_flags: list,
    ) -> list:
        def rrr_result(r: Optional[float]) -> str:
            if r is None or r < 1.0: return "not_met"
            if r < 1.5:              return "partial"
            return "met"

        def spread_result(s: float) -> str:
            if s > 3.0:  return "not_met"
            if s > 1.5:  return "partial"
            return "met"

        htf_ok      = "not_met" if htf_conflict else "met"
        news_ok     = "not_met" if news_imminent else "met"
        flags_ok    = "not_met" if len(strategy_flags) > 2 else ("partial" if strategy_flags else "met")
        macro_ok    = "not_met" if (news_imminent or (direction == "BUY" and current_price > 155.00)) else "met"
        inval_ok    = "not_met" if htf_conflict else ("partial" if strategy_flags else "met")

        return [
            {"label": "Strategy rule compliance",           "result": "partial"},
            {"label": "Market structure quality",           "result": htf_ok},
            {"label": "Trend alignment (higher timeframe)", "result": htf_ok},
            {"label": "Confluence factors",                 "result": flags_ok},
            {"label": "Volatility conditions",              "result": spread_result(spread_pips)},
            {"label": "Entry precision",                    "result": "partial"},
            {"label": "Stop loss logic",                    "result": rrr_result(rrr)},
            {"label": "Take profit realism",                "result": rrr_result(rrr)},
            {"label": "Risk-reward ratio",                  "result": rrr_result(rrr)},
            {"label": "Invalidation strength",              "result": inval_ok},
            {"label": "Macro / news sensitivity",           "result": macro_ok},
        ]
