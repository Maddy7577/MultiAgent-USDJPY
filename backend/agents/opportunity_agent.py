"""OpportunityAgent — pure scoring function for positive trade conditions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OpportunityResult:
    score: float  # 0–10
    reasons: list = field(default_factory=list)
    agent_id: int = 1


class OpportunityAgent:
    """Evaluates how strong the opportunity side of a trade setup is.

    Two instances per strategy (agent_id 1 and 2) use slightly different weights
    so scoring variance surfaces genuinely ambiguous setups.
    """

    _WEIGHTS = {
        1: {"conditions": 0.40, "entry_quality": 0.25, "momentum": 0.20, "timing": 0.15},
        2: {"conditions": 0.35, "entry_quality": 0.20, "momentum": 0.30, "timing": 0.15},
    }

    def __init__(self, agent_id: int = 1):
        self.agent_id = agent_id
        self._w = self._WEIGHTS.get(agent_id, self._WEIGHTS[1])

    def evaluate(
        self,
        conditions_met: int,
        conditions_total: int,
        entry_quality: float,    # 0.0–1.0: how precise / clean the entry zone is
        momentum_aligned: bool,  # trend momentum supports the direction
        in_zone: bool,           # price is actually at the entry zone
        extra_factors: float = 0.0,  # 0.0–1.0 additional confluence
    ) -> OpportunityResult:
        """Score the opportunity from 0 (no edge) to 10 (perfect setup)."""
        if conditions_total == 0:
            return OpportunityResult(score=0.0, agent_id=self.agent_id)

        cond_ratio = conditions_met / conditions_total
        momentum_val = 1.0 if momentum_aligned else 0.3
        timing_val = (0.8 if in_zone else 0.3) + 0.2 * extra_factors

        raw = (
            self._w["conditions"] * cond_ratio +
            self._w["entry_quality"] * entry_quality +
            self._w["momentum"] * momentum_val +
            self._w["timing"] * timing_val
        )

        # Agent 2 applies a small variance for sensitivity analysis
        if self.agent_id == 2:
            variance = 0.05 * (0.5 - cond_ratio)
            raw = max(0.0, min(1.0, raw + variance))

        score = round(raw * 10.0, 2)
        reasons = self._build_reasons(cond_ratio, entry_quality, momentum_aligned, in_zone)
        return OpportunityResult(score=score, reasons=reasons, agent_id=self.agent_id)

    def _build_reasons(
        self, cond_ratio: float, entry_quality: float,
        momentum_aligned: bool, in_zone: bool
    ) -> list:
        reasons = []
        pct = int(cond_ratio * 100)
        reasons.append(f"Conditions met: {pct}%")
        if entry_quality >= 0.7:
            reasons.append("Clean entry zone")
        elif entry_quality < 0.4:
            reasons.append("Entry zone imprecise")
        if momentum_aligned:
            reasons.append("Momentum supports direction")
        else:
            reasons.append("Momentum not aligned")
        if in_zone:
            reasons.append("Price at target zone")
        else:
            reasons.append("Price not yet at target zone")
        return reasons
