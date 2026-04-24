"""Debate engine — aggregates 4 agent outputs into a final verdict."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.agents.opportunity_agent import OpportunityResult
from backend.agents.risk_agent import RiskResult
from backend.strategies.base_strategy import StrategyResult
from backend import config


def _normalize(net_score: float) -> int:
    """Map net_score (approx -20 to +15) to confidence 0–100."""
    return max(0, min(100, int((net_score + 20.0) / 35.0 * 100)))


def _probability(
    rule_compliance: float,   # 0–1: fraction of hard rules met
    structure_quality: float, # 0–1: how clean the price structure is
    trend_alignment: float,   # 0–1: how well HTF trend aligns
) -> int:
    raw = 0.5 * rule_compliance + 0.3 * structure_quality + 0.2 * trend_alignment
    return max(0, min(100, int(raw * 100)))


def run_debate(
    opp1: OpportunityResult,
    opp2: OpportunityResult,
    risk1: RiskResult,
    risk2: RiskResult,
    rrr: Optional[float],
    direction: Optional[str],
    current_price: float,
    spread_pips: float,
    news_imminent: bool,
    rule_compliance: float,
    structure_quality: float,
    trend_alignment: float,
    strategy_id: int,
    strategy_name: str,
    strategy_type: str,
    timeframes: list,
    entry: Optional[float],
    sl: Optional[float],
    tp1: Optional[float],
    tp2: Optional[float],
    tp3: Optional[float],
    wait_zone: Optional[str],
    conditions_to_meet: list,
    reasons_for: list,
    reasons_against: list,
    evaluated_at: Optional[datetime] = None,
) -> StrategyResult:

    if evaluated_at is None:
        evaluated_at = datetime.now(timezone.utc)

    # ── Score aggregation ───────────────────────────────────────────────────
    opp_score = (opp1.score + opp2.score) / 2.0
    opp_score = max(0.0, min(10.0, opp_score))

    risk_score = (risk1.risk_score + risk2.risk_score) / 2.0

    alignment_bonus = 5.0 if abs(opp1.score - opp2.score) <= 1.5 else 0.0
    conflict_penalty = 5.0 if abs(opp1.score - opp2.score) > 3.0 else 0.0

    common_critical = set(risk1.critical_flags) & set(risk2.critical_flags)
    risk_alignment_penalty = 5.0 if common_critical else 0.0

    net_score = opp_score - risk_score + alignment_bonus - conflict_penalty - risk_alignment_penalty
    confidence = _normalize(net_score)

    prob = _probability(rule_compliance, structure_quality, trend_alignment)

    # ── Critical override flags ─────────────────────────────────────────────
    all_critical_raw = list(common_critical) + list(risk1.critical_flags) + list(risk2.critical_flags)
    seen = set()
    critical_deduped = []
    for f in all_critical_raw:
        if f not in seen:
            seen.add(f)
            critical_deduped.append(f)

    all_reasons_against = list(reasons_against)
    all_reasons_against.extend(risk1.risk_flags)
    for f in risk2.risk_flags:
        if f not in all_reasons_against:
            all_reasons_against.append(f)

    all_reasons_for = list(reasons_for)
    for r in opp1.reasons + opp2.reasons:
        if r not in all_reasons_for:
            all_reasons_for.append(r)

    agent_scores = {
        "opp1_score": opp1.score,
        "opp2_score": opp2.score,
        "risk1_score": risk1.risk_score,
        "risk2_score": risk2.risk_score,
        "opp_avg": round(opp_score, 2),
        "risk_avg": round(risk_score, 2),
        "alignment_bonus": alignment_bonus,
        "conflict_penalty": conflict_penalty,
        "risk_alignment_penalty": risk_alignment_penalty,
        "net_score": round(net_score, 2),
        "critical_flags": critical_deduped,
    }

    # ── Auto-override to NO_TRADE if critical flags present ─────────────────
    if critical_deduped:
        all_reasons_against = critical_deduped + [r for r in all_reasons_against if r not in critical_deduped]
        return StrategyResult(
            strategy_id=strategy_id, strategy_name=strategy_name, strategy_type=strategy_type,
            status="NO_TRADE", direction=direction,
            entry=None, sl=None, tp1=None, tp2=None, tp3=None, rrr=None,
            confidence=max(0, confidence - 25), probability=max(0, prob - 25),
            timeframes=timeframes,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=all_reasons_for,
            reasons_against=all_reasons_against,
            verdict_summary=f"NO TRADE (critical override): {critical_deduped[0]}",
            evaluated_at=evaluated_at,
            agent_scores=agent_scores,
        )

    # ── Verdict thresholds ──────────────────────────────────────────────────
    valid_rrr = rrr is not None and rrr >= config.MIN_RRR

    if (confidence >= config.CONFIDENCE_THRESHOLD and
            prob >= config.PROBABILITY_THRESHOLD and
            valid_rrr and
            entry is not None and sl is not None and tp1 is not None):
        status = "VALID_TRADE"
        summary = (f"VALID TRADE: {direction} @ {entry:.3f} | SL {sl:.3f} | TP1 {tp1:.3f} "
                   f"| RRR {rrr:.2f} | Conf {confidence} | Prob {prob}")
    elif wait_zone and rule_compliance >= 0.4:
        status = "WAIT_FOR_LEVELS"
        summary = f"WAIT FOR LEVELS: {wait_zone}"
    else:
        status = "NO_TRADE"
        summary = (f"NO TRADE: confidence {confidence} / probability {prob} / "
                   f"rrr {rrr if rrr else 'N/A'}")

    return StrategyResult(
        strategy_id=strategy_id, strategy_name=strategy_name, strategy_type=strategy_type,
        status=status, direction=direction,
        entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3,
        rrr=rrr if status == "VALID_TRADE" else None,
        confidence=confidence, probability=prob,
        timeframes=timeframes,
        wait_zone=wait_zone if status == "WAIT_FOR_LEVELS" else None,
        conditions_to_meet=conditions_to_meet if status == "WAIT_FOR_LEVELS" else [],
        reasons_for=all_reasons_for,
        reasons_against=all_reasons_against,
        verdict_summary=summary,
        evaluated_at=evaluated_at,
        agent_scores=agent_scores,
    )
