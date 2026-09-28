"""Current versus target exposure. Research object only."""

from __future__ import annotations

from roller.momento.contracts import HedgeAnalysis, RVHedgeAssessment, TargetExposure


def target_from_research(
    hedge: HedgeAnalysis,
    rv: RVHedgeAssessment,
    *,
    current_exposure_bps: int,
    generated_at: str,
    as_of: str,
    game_id: str | None,
) -> TargetExposure:
    _ = rv
    return TargetExposure(
        generated_at=generated_at,
        as_of=as_of,
        source_system="position_management",
        game_id=game_id,
        provenance={
            "hedge_method": hedge.method,
            "rv_method": rv.method,
            "live": False,
        },
        current_exposure_bps=int(current_exposure_bps),
        target_exposure_bps=int(hedge.target_exposure_bps),
        status="RESEARCH_ONLY",
    )
