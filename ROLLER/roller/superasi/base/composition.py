"""Mode A desk instrument. Does not consume observed win probability.

Roller-dynamic Monte Carlo lives in run_roller_risk_profile. It does not
change BASE_GRADE.theoretical_alignment, which still uses the instrument.
"""

from __future__ import annotations

from typing import Any

from roller import desk_settings
from roller.config import RollerConfig
from roller.risk.engine import run_risk
from roller.superasi.base.versions import (
    DESK_PATHS,
    DESK_SEED,
    RISK_PROFILE_WEEKS,
)


def run_desk_composition(
    *,
    research_result_hash: str = "",
    monte_carlo_paths: int = DESK_PATHS,
) -> dict[str, Any]:
    levels = desk_settings.scaled_levels()
    return run_risk(
        {
            "mode": "A",
            "seed": DESK_SEED,
            "research_result_hash": research_result_hash,
            "config": {
                "monte_carlo_paths": int(monte_carlo_paths),
                "initial_bankroll": levels["initial_bankroll"],
                "trade_allocation": levels["trade_allocation"],
            },
        }
    )


def run_desk_risk_profile(
    *,
    research_result_hash: str = "",
    monte_carlo_paths: int = DESK_PATHS,
) -> dict[str, Any]:
    levels = desk_settings.scaled_levels()
    return run_risk(
        {
            "mode": "A",
            "seed": DESK_SEED,
            "research_result_hash": research_result_hash,
            "config": {
                "monte_carlo_paths": int(monte_carlo_paths),
                "weeks_per_year": RISK_PROFILE_WEEKS,
                "initial_bankroll": levels["initial_bankroll"],
                "trade_allocation": levels["trade_allocation"],
                "bankroll_floor": levels["bankroll_floor"],
                "target_bankroll": levels["target_bankroll"],
            },
        }
    )


def run_roller_risk_profile(
    *,
    payoff: dict[str, float],
    p: float,
    research_result_hash: str = "",
    monte_carlo_paths: int = DESK_PATHS,
    cfg: RollerConfig | None = None,
) -> dict[str, Any]:
    """Mode A horizon with this Roller's payoff and observed p. Reuses Debase Bernoulli."""
    from roller.superasi.debase.simulation import run_bernoulli

    levels = desk_settings.scaled_levels(cfg=cfg)
    return run_bernoulli(
        payoff,
        p=float(p),
        research_result_hash=research_result_hash,
        paths=int(monte_carlo_paths),
        desk=levels,
    )
