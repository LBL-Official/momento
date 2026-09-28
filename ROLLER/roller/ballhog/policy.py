"""Versioned Ballhog policy. Thresholds live on disk, not in call sites."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from roller.ballhog.errors import BallhogError
from roller.momento.registry import parse_yaml_subset
from roller.paths import find_root, momento_root

POLICY_SCHEMA = "ballhog.policy.v1"


def policy_path() -> Path:
    return momento_root(find_root()) / "research" / "ballhog" / "policy" / "v1.yaml"


@dataclass(frozen=True)
class BallhogPolicy:
    schema: str
    version: str
    live_execution: bool
    execution_enabled: bool
    entry_cents: int
    lock_gain_cents: int
    research_unit_qty: int
    default_q_dir: int
    max_q_dir: int
    price_grid: tuple[int, ...]
    positive_robust_portfolio_ev: bool
    execution_assumption: str
    risk_metric: str
    timing: dict[str, Any]
    note: str
    raw: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "live_execution": self.live_execution,
            "execution_enabled": self.execution_enabled,
            "entry_cents": self.entry_cents,
            "lock_gain_cents": self.lock_gain_cents,
            "research_unit_qty": self.research_unit_qty,
            "default_q_dir": self.default_q_dir,
            "max_q_dir": self.max_q_dir,
            "price_grid": list(self.price_grid),
            "positive_robust_portfolio_ev": self.positive_robust_portfolio_ev,
            "execution_assumption": self.execution_assumption,
            "risk_metric": self.risk_metric,
            "timing": dict(self.timing),
            "note": self.note,
        }


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
    if grid != tuple(range(35, 46)):
        raise BallhogError("POLICY_INVALID", "price_grid must be 35 through 45 inclusive", 500)
    max_q = int(raw.get("max_q_dir") or 500)
    if max_q < 1:
        raise BallhogError("POLICY_INVALID", "max_q_dir must be a positive integer", 500)
    timing = raw.get("timing") if isinstance(raw.get("timing"), dict) else {}
    return BallhogPolicy(
        schema=str(raw["schema"]),
        version=str(raw.get("version") or "v1"),
        live_execution=False,
        execution_enabled=False,
        entry_cents=int(raw.get("entry_cents") or 80),
        lock_gain_cents=int(raw.get("lock_gain_cents") or 20),
        research_unit_qty=int(raw.get("research_unit_qty") or 1),
        default_q_dir=int(raw.get("default_q_dir") or 1),
        max_q_dir=max_q,
        price_grid=grid,
        positive_robust_portfolio_ev=bool(raw.get("positive_robust_portfolio_ev")),
        execution_assumption=str(raw.get("execution_assumption") or "THEORETICAL"),
        risk_metric=str(raw.get("risk_metric") or "T40_RISK_PROXY"),
        timing=timing,
        note=str(raw.get("note") or ""),
        raw=raw,
    )
