#!/usr/bin/env python3
"""Phase 1 hard gate: frozen labels, possession validation, exclusion Δq."""

from __future__ import annotations

import sys

from common import (
    EXPECTED_FIRST80,
    EXPECTED_STOPS,
    OUT,
    PRIMARY_ALIGN,
    Q_UNCONDITIONAL,
    SPEC_DIR,
    utc_now,
    write_json,
)


def main() -> int:
    import json

    obs = json.loads((OUT / "observations_summary.json").read_text())
    poss = json.loads((OUT / "possession_validation.json").read_text())
    overlay = json.loads((OUT / "overlay_summary.json").read_text())
    from common import read_parquet_rows

    snaps = read_parquet_rows(OUT / "entry_snaps.parquet")
    n = len(snaps)
    y = sum(int(s["Y_40_CLOSE"]) for s in snaps)
    primary = [s for s in snaps if s.get("alignment_confidence") in PRIMARY_ALIGN]
    excluded = [s for s in snaps if s.get("alignment_confidence") not in PRIMARY_ALIGN]
    yp = sum(int(s["Y_40_CLOSE"]) for s in primary)
    ye = sum(int(s["Y_40_CLOSE"]) for s in excluded)
    qp = yp / len(primary) if primary else None
    qe = ye / len(excluded) if excluded else None
    dq = None if qp is None else abs(qp - Q_UNCONDITIONAL)
    conf = {}
    for s in snaps:
        conf[s.get("alignment_confidence") or "NA"] = conf.get(s.get("alignment_confidence") or "NA", 0) + 1

    baseline_ok = obs.get("first80") == EXPECTED_FIRST80 and obs.get("Y_40_CLOSE") == EXPECTED_STOPS
    leakage_ok = all(not s.get("leakage_post_entry_in_z") for s in snaps)
    dup_ok = poss.get("duplicate_possession_ids", 0) == 0
    material_bias = dq is not None and dq > 0.03
    ok = baseline_ok and leakage_ok and dup_ok and obs.get("baseline_ok")

    md = f"""# PHASE 1 VALIDATION — Test 2

Written `{utc_now()}`

## Frozen labels

- first80: {obs.get('first80')} (expected {EXPECTED_FIRST80})
- Y_40_CLOSE: {obs.get('Y_40_CLOSE')} (expected {EXPECTED_STOPS})
- baseline_ok: **{obs.get('baseline_ok')}**

## Possessions

- n_possessions: {poss.get('n_possessions')}
- games_built: {poss.get('issues', {}).get('games_built')}
- unmatched observations: {poss.get('unmatched_observations')}
- no PBP: {poss.get('no_pbp')}
- duplicate ids: {poss.get('duplicate_possession_ids')}
- impossible score jumps (flagged, not dropped): {poss.get('issues', {}).get('impossible_score_jumps')}
- nonmonotonic clocks (flagged): {poss.get('issues', {}).get('nonmonotonic_clock')}
- unmapped action types: {poss.get('issues', {}).get('unmapped_action_types')}

## Alignment (MODELED walls; per-play timeActual unavailable)

Confidence counts: {conf}

- Primary HIGH+MEDIUM n={len(primary)} q={qp}
- Excluded n={len(excluded)} q={qe}
- |q_primary − 26.02%| = {dq}
- Leakage post-entry in Z: **{not leakage_ok}**

## Overlay quality

{overlay.get('quality_counts')}

## Gate

- PASS: **{ok and not material_bias}**
- Material exclusion bias (>3pp): **{material_bias}**
"""
    (OUT / "PHASE1_VALIDATION.md").write_text(md)
    (SPEC_DIR / "PHASE1_VALIDATION.md").write_text(md)
    write_json(
        OUT / "phase1_gate.json",
        {
            "ok": ok,
            "material_exclusion_bias": material_bias,
            "primary_n": len(primary),
            "primary_q": qp,
            "excluded_n": len(excluded),
            "delta_q": dq,
            "confidence_counts": conf,
        },
    )
    print(md)
    if not ok:
        print("PHASE 1 GATE FAIL", file=sys.stderr)
        return 1
    if material_bias:
        print("PHASE 1: exclusion Δq material — documented; continuing with bias report.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
