"""Locked constants. Not a live trading rule."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PathFeConfig:
    seed: int = 80
    entry_lo: int = 78
    entry_hi: int = 82
    chase: int = 89
    bail: int = 40
    hedge_lo: int = 38
    hedge_hi: int = 42
    r_min: float = 0.12
    r_max: float = 0.25
    p_r_max: float = 0.55
    k_grid: tuple[int, ...] = (15, 25, 35, 51)
    tau_lo: float = 0.77
    tau_hi: float = 0.84
    tau_grid: tuple[float, ...] = (0.77, 0.80, 0.82, 0.84)
    m_pcs_max: int = 4
    default_k: int = 25
    default_tau: float = 0.80
    k_min: int = 8
    embargo_games: int = 2
    n_clusters: int = 3
    dmax_percentile: float = 0.90
    state_fair_version: str = "v1_logistic_prev_season"
    # ESTIMATED_PLACEHOLDER cents / contract / side. Not production KalshiFeeModel.
    fee_cents_per_side_est: int = 1
    q2_policy_filter: bool = False
    max_raw_enter_features: int = 8
    max_pcs: int = 4
    ambition_p_k: float = 0.82
    ambition_r: float = 0.18
    residual_promote_max: int = 2
    residual_z_min: float = 2.5
    # Synthetic generator
    n_games: int = 220
    ticks_per_game: int = 192
    fill_rate: float = 0.92
    source_tag: str = "SYNTHETIC_E2E"
    enter_families: tuple[str, ...] = ("A", "B", "C", "D")
    pca_families: tuple[str, ...] = ("A", "B", "C")
    hedge_family: str = "E"


DEFAULT = PathFeConfig()
