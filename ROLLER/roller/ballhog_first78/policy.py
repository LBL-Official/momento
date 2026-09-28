"""78/67 Ballhog policy. The 35–45 file is not loaded here."""

from __future__ import annotations

from pathlib import Path

from roller.ballhog.errors import BallhogError
from roller.ballhog.policy import POLICY_SCHEMA, BallhogPolicy
from roller.momento.registry import parse_yaml_subset
from roller.paths import find_root, momento_root

GRID = tuple(range(62, 73))


def policy_path() -> Path:
    return momento_root(find_root()) / "research" / "ballhog" / "policy" / "first78_v1.yaml"


def load_policy(path: Path | None = None) -> BallhogPolicy:
    src = path or policy_path()
    if not src.is_file():
        raise BallhogError("POLICY_MISSING", f"missing {src}", 500)
    raw = parse_yaml_subset(src.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != POLICY_SCHEMA:
        raise BallhogError("POLICY_INVALID", "ballhog.policy.v1 schema mismatch", 500)
    if raw.get("live_execution") is not False or raw.get("execution_enabled") is not False:
        raise BallhogError("POLICY_INVALID", "execution must stay false", 500)
    grid = tuple(int(x) for x in (raw.get("price_grid") or []))
    if grid != GRID:
        raise BallhogError("POLICY_INVALID", "price_grid must be 62 through 72 inclusive", 500)
    if int(raw.get("entry_cents") or 0) != 78 or int(raw.get("lock_gain_cents") or 0) != 22:
        raise BallhogError("POLICY_INVALID", "entry must be 78 and lock gain must be 22", 500)
    timing = raw.get("timing") if isinstance(raw.get("timing"), dict) else {}
    return BallhogPolicy(
        schema=str(raw["schema"]),
        version=str(raw.get("version") or "first78_v1"),
        live_execution=False,
        execution_enabled=False,
        entry_cents=78,
        lock_gain_cents=22,
        research_unit_qty=int(raw.get("research_unit_qty") or 1),
        default_q_dir=int(raw.get("default_q_dir") or 1),
        max_q_dir=int(raw.get("max_q_dir") or 500),
        price_grid=grid,
        positive_robust_portfolio_ev=bool(raw.get("positive_robust_portfolio_ev")),
        execution_assumption=str(raw.get("execution_assumption") or "THEORETICAL"),
        risk_metric=str(raw.get("risk_metric") or "T67_RISK_PROXY"),
        timing=timing,
        note=str(raw.get("note") or ""),
        raw=raw,
    )
