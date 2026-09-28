#!/usr/bin/env python3
"""Time-alignment audit. Hard gate: publish exclusion bias before modeling."""

from __future__ import annotations

import sys
from collections import Counter, defaultdict

from common import (
    Q_UNCONDITIONAL,
    OUT,
    PRIMARY_ALIGN,
    ev_from_q,
    rate_ci,
    read_parquet_rows,
    utc_now,
    write_json,
)


def _q(rows):
    n = len(rows)
    k = sum(int(r.get("Y_40_CLOSE") or 0) for r in rows)
    return rate_ci(k, n)


def main() -> int:
    obs_path = OUT / "observations.parquet"
    aln_path = OUT / "alignment.parquet"
    if not obs_path.exists() or not aln_path.exists():
        print("missing observations or alignment", file=sys.stderr)
        return 1
    obs = read_parquet_rows(obs_path)
    aln = read_parquet_rows(aln_path)
    by_conf = defaultdict(list)
    for r in obs:
        by_conf[r.get("alignment_confidence") or "MISSING"].append(r)
    primary = [r for r in obs if r.get("alignment_confidence") in PRIMARY_ALIGN]
    excluded = [r for r in obs if r.get("alignment_confidence") not in PRIMARY_ALIGN]
    reasons = Counter(r.get("alignment_reason") for r in aln)
    phases = Counter(r.get("game_phase") for r in aln)
    tip_lags = [
        r["tip_to_q1_start_s"]
        for r in aln
        if isinstance(r.get("tip_to_q1_start_s"), (int, float))
    ]
    residuals = [
        r["median_replay_residual_s"]
        for r in aln
        if isinstance(r.get("median_replay_residual_s"), (int, float))
    ]
    report = {
        "written_utc": utc_now(),
        "alignment_model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
        "per_play_wall_clock_observed": False,
        "tip_inferred_from_kalshi_open": False,
        "n_observations": len(obs),
        "confidence_counts": {k: len(v) for k, v in sorted(by_conf.items(), key=lambda x: str(x[0]))},
        "game_phase_counts": dict(phases),
        "alignment_reason_counts": dict(reasons),
        "primary_set": "HIGH+MEDIUM",
        "full_universe": _q(obs),
        "primary": _q(primary),
        "excluded": _q(excluded),
        "by_confidence": {k: _q(v) for k, v in by_conf.items()},
        "q_unconditional_frozen": Q_UNCONDITIONAL,
        "exclusion_bias_delta_q": None
        if _q(primary)["q"] is None
        else _q(primary)["q"] - Q_UNCONDITIONAL,
        "median_tip_to_q1_s": sorted(tip_lags)[len(tip_lags) // 2] if tip_lags else None,
        "median_replay_residual_s": (
            sorted(residuals)[len(residuals) // 2] if residuals else None
        ),
        "n_with_replay_residual": len(residuals),
        "gate": "PRIMARY_ANALYSIS_USES_HIGH_MEDIUM_ONLY",
    }
    write_json(OUT / "time_alignment_audit.json", report)
    pq = report["primary"]["q"]
    print(
        f"alignment primary n={report['primary']['n']} q={pq} "
        f"excluded n={report['excluded']['n']} q={report['excluded']['q']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
