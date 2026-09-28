"""τ band policy. Undershoot is not a success path."""

from __future__ import annotations

from roller.nba_path_fe.config import DEFAULT, PathFeConfig

MODE_SPEC = "spec_band"
MODE_OOB_SYNTHETIC = "out_of_band_synthetic"


def tau_in_spec_band(tau: float, cfg: PathFeConfig = DEFAULT) -> bool:
    try:
        t = float(tau)
    except (TypeError, ValueError):
        return False
    if t != t:  # NaN
        return False
    return cfg.tau_lo <= t <= cfg.tau_hi


def r_in_band(r: float, cfg: PathFeConfig = DEFAULT) -> bool:
    try:
        v = float(r)
    except (TypeError, ValueError):
        return False
    if v != v:
        return False
    return cfg.r_min <= v <= cfg.r_max


def tau_mode(tau: float, cfg: PathFeConfig = DEFAULT) -> str:
    if tau_in_spec_band(tau, cfg):
        return MODE_SPEC
    return MODE_OOB_SYNTHETIC


def may_claim_band_compliance(*, tau: float, r: float, cfg: PathFeConfig = DEFAULT) -> bool:
    """Band compliance requires τ ∈ [0.77, 0.84] and r ∈ [0.12, 0.25]."""
    return tau_in_spec_band(tau, cfg) and r_in_band(r, cfg)


def raw_warehouse_present(raw_dir) -> bool:
    path = raw_dir
    if not getattr(path, "is_dir", lambda: False)():
        return False
    for p in path.iterdir():
        if p.name == ".gitkeep":
            continue
        if p.is_file() and p.stat().st_size > 0:
            return True
        if p.is_dir() and any(c.is_file() and c.stat().st_size > 0 for c in p.rglob("*")):
            return True
    return False


def sealed_real_data_criteria(
    *,
    source: str,
    raw_present: bool,
    folds: list[dict],
    pooled: dict,
    cfg: PathFeConfig = DEFAULT,
) -> tuple[bool, list[str]]:
    """Promotion may pass only on sealed real warehouse data. Synthetic never passes."""
    reasons: list[str] = []
    if source == "SYNTHETIC_E2E" or not raw_present:
        reasons.append("warehouse_raw_absent")
    ok = [f for f in folds if f.get("status") == "OK"]
    if any(not tau_in_spec_band(float(f.get("tau", float("nan"))), cfg) for f in ok):
        reasons.append("tau_out_of_spec_band")
    if any(not r_in_band(float(f.get("r", float("nan"))), cfg) for f in ok):
        reasons.append("fold_r_out_of_band")
    if not r_in_band(float(pooled.get("r", float("nan"))), cfg):
        reasons.append("pooled_r_out_of_band")
    pk = float(pooled.get("p_K", float("nan")))
    if pk != pk or pk < cfg.ambition_p_k:
        reasons.append("p_K_below_ambition")
    pr = float(pooled.get("p_R", float("nan")))
    if pr == pr and pr > cfg.p_r_max:
        reasons.append("p_R_above_max")
    return (len(reasons) == 0, reasons)
