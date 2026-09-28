#!/usr/bin/env python3
"""V2 HIGH vs MEDIUM q-gap forensics. Data quality research, not a filter.

Reads V2 alignment.parquet / observations.parquet as frozen artifacts.
"""

from __future__ import annotations

import sys
from collections import defaultdict

from common import OUT, SPEC_DIR, V2_OUT, ev_from_q, read_parquet_rows, utc_now, wilson, write_json, write_parquet


def qn(rows, key="Y_40_CLOSE"):
    n = len(rows)
    k = sum(int(r.get(key) or 0) for r in rows)
    p, lo, hi = wilson(k, n)
    return {"n": n, "k": k, "q": p, "wilson_lo": lo, "wilson_hi": hi, "ev": ev_from_q(p)}


def main() -> int:
    aln_p = V2_OUT / "alignment.parquet"
    obs_p = V2_OUT / "observations.parquet"
    if not aln_p.exists() or not obs_p.exists():
        print("missing V2 alignment artifacts", file=sys.stderr)
        return 1
    aln = {r["observation_id"]: r for r in read_parquet_rows(aln_p)}
    obs = read_parquet_rows(obs_p)
    rows = []
    for o in obs:
        a = aln.get(o["observation_id"], {})
        rec = {
            "trade_id": o["observation_id"],
            "game_date": o.get("game_date"),
            "Y_40_CLOSE": o.get("Y_40_CLOSE"),
            "alignment_confidence": o.get("alignment_confidence") or a.get("alignment_confidence"),
            "alignment_reason": o.get("alignment_reason") or a.get("alignment_reason"),
            "game_phase": o.get("game_phase") or a.get("game_phase"),
            "median_replay_residual_s": a.get("median_replay_residual_s"),
            "tip_to_q1_start_s": a.get("tip_to_q1_start_s"),
            "snap_lag_s": a.get("snap_lag_s"),
            "n_actions": a.get("n_actions"),
            "n_replay_residuals": a.get("n_replay_residuals"),
            "first_period_start_ts": a.get("first_period_start_ts"),
            "last_period_end_ts": a.get("last_period_end_ts"),
        }
        first = rec["first_period_start_ts"]
        last = rec["last_period_end_ts"]
        rec["modeled_duration_s"] = None if first is None or last is None else int(last) - int(first)
        rec["overtime_duration_proxy"] = (
            rec["modeled_duration_s"] is not None and rec["modeled_duration_s"] > (48 * 60 + 120)
        )
        rec["unusual_tip_lag"] = (
            rec["tip_to_q1_start_s"] is not None
            and abs(float(rec["tip_to_q1_start_s"]) - 720) > 300
        )
        rec["high_replay_residual"] = (
            rec["median_replay_residual_s"] is not None and rec["median_replay_residual_s"] > 180
        )
        rec["month"] = (rec["game_date"] or "")[:7]
        rec["weekday"] = None
        rows.append(rec)
    write_parquet(OUT / "alignment_diagnostics.parquet", rows)

    by_conf = defaultdict(list)
    by_reason = defaultdict(list)
    by_phase = defaultdict(list)
    by_month = defaultdict(list)
    for r in rows:
        by_conf[r["alignment_confidence"]].append(r)
        by_reason[r["alignment_reason"]].append(r)
        by_phase[r["game_phase"]].append(r)
        by_month[r["month"]].append(r)

    medium = by_conf.get("MEDIUM") or []
    high = by_conf.get("HIGH") or []
    slices = {
        "HIGH": qn(high),
        "MEDIUM": qn(medium),
        "MEDIUM_replay_residual": qn([r for r in medium if r["alignment_reason"] == "IN_PERIOD_REPLAY_RESIDUAL"]),
        "MEDIUM_intermission": qn([r for r in medium if r["game_phase"] == "INTERMISSION"]),
        "MEDIUM_game_not_started": qn([r for r in medium if r["game_phase"] == "GAME_NOT_STARTED"]),
        "HIGH_replay_validated": qn([r for r in high if r["alignment_reason"] == "IN_PERIOD_REPLAY_VALIDATED"]),
        "HIGH_in_period_bounds": qn([r for r in high if r["alignment_reason"] == "IN_PERIOD_BOUNDS"]),
        "all_high_replay_residual_flag": qn([r for r in rows if r["high_replay_residual"]]),
        "all_unusual_tip": qn([r for r in rows if r["unusual_tip_lag"]]),
        "all_ot_duration_proxy": qn([r for r in rows if r["overtime_duration_proxy"]]),
        "MEDIUM_excluding_replay_residual": qn(
            [r for r in medium if r["alignment_reason"] != "IN_PERIOD_REPLAY_RESIDUAL"]
        ),
    }
    reason_q = {k: qn(v) for k, v in sorted(by_reason.items(), key=lambda x: -len(x[1]))}
    month_q = {k: qn(v) for k, v in sorted(by_month.items())}

    # Residual magnitude among IN_PERIOD
    in_period = [r for r in rows if r.get("game_phase") == "IN_PERIOD"]
    res_buckets = {"<=60s": [], "61-180s": [], ">180s": [], "missing": []}
    for r in in_period:
        m = r.get("median_replay_residual_s")
        if m is None:
            res_buckets["missing"].append(r)
        elif m <= 60:
            res_buckets["<=60s"].append(r)
        elif m <= 180:
            res_buckets["61-180s"].append(r)
        else:
            res_buckets[">180s"].append(r)
    residual_q = {k: qn(v) for k, v in res_buckets.items()}

    # Gap after restricting to IN_PERIOD only
    high_ip = [r for r in high if r.get("game_phase") == "IN_PERIOD"]
    med_ip = [r for r in medium if r.get("game_phase") == "IN_PERIOD"]

    conclusion = "B"
    conclusion_text = "UNRESOLVED"
    # MEDIUM is compositionally different (replay residual / intermission / pre-tip).
    n_med = len(medium)
    n_res = sum(1 for r in medium if r["alignment_reason"] == "IN_PERIOD_REPLAY_RESIDUAL")
    share_res = n_res / n_med if n_med else 0
    q_high = slices["HIGH"]["q"]
    q_med = slices["MEDIUM"]["q"]
    q_res = slices["MEDIUM_replay_residual"]["q"]
    q_val = slices["HIGH_replay_validated"]["q"]
    # Artifact if the gap is concentrated in the residual/intermission strata
    # and IN_PERIOD residual vs validated still differs but residual is a clock-quality flag.
    if share_res >= 0.7 and q_med is not None and q_high is not None and (q_med - q_high) >= 0.08:
        conclusion = "A"
        conclusion_text = "LIKELY DATA ARTIFACT"
    # Do not choose C without strong evidence of a basketball mechanism independent of alignment quality.
    write_json(
        OUT / "alignment_forensics.json",
        {
            "written_utc": utc_now(),
            "source": "V2 alignment.parquet + observations.parquet (read-only)",
            "not_a_trading_filter": True,
            "v2_published": {"HIGH_n": 955, "HIGH_q": 0.2314, "MEDIUM_n": 214, "MEDIUM_q": 0.4112},
            "recomputed": {k: slices[k] for k in ("HIGH", "MEDIUM")},
            "slices": slices,
            "by_reason": reason_q,
            "by_month": month_q,
            "in_period_residual_buckets": residual_q,
            "in_period_only": {"HIGH": qn(high_ip), "MEDIUM": qn(med_ip)},
            "medium_replay_residual_share": share_res,
            "conclusion_code": conclusion,
            "conclusion": conclusion_text,
        },
    )

    md = []
    md.append("# ALIGNMENT FORENSICS")
    md.append("")
    md.append("Data-quality research on the V2 HIGH vs MEDIUM barrier-rate gap.")
    md.append("This is **not** a trading filter. Alignment confidence is a quality label.")
    md.append("")
    md.append("## V2 published numbers (frozen)")
    md.append("")
    md.append("| Confidence | n | q |")
    md.append("| --- | ---: | ---: |")
    md.append("| HIGH | 955 | 23.14% |")
    md.append("| MEDIUM | 214 | 41.12% |")
    md.append("| LOW | 3 | 66.67% |")
    md.append("| UNUSABLE | 58 | 15.52% |")
    md.append("")
    md.append("## Recomputed slices")
    md.append("")
    md.append("| Slice | n | k | q |")
    md.append("| --- | ---: | ---: | ---: |")
    for k, v in slices.items():
        q = "—" if v["q"] is None else f"{100*v['q']:.2f}%"
        md.append(f"| {k} | {v['n']} | {v['k']} | {q} |")
    md.append("")
    md.append("## By alignment reason")
    md.append("")
    md.append("| Reason | n | q |")
    md.append("| --- | ---: | ---: |")
    for k, v in reason_q.items():
        q = "—" if v["q"] is None else f"{100*v['q']:.2f}%"
        md.append(f"| {k} | {v['n']} | {q} |")
    md.append("")
    md.append("## In-period replay residual buckets")
    md.append("")
    md.append("| Residual | n | q |")
    md.append("| --- | ---: | ---: |")
    for k, v in residual_q.items():
        q = "—" if v["q"] is None else f"{100*v['q']:.2f}%"
        md.append(f"| {k} | {v['n']} | {q} |")
    md.append("")
    md.append("## Composition")
    md.append("")
    md.append(
        f"MEDIUM n={n_med}; IN_PERIOD_REPLAY_RESIDUAL share={share_res:.1%} "
        f"({n_res}). Remaining MEDIUM is intermission / game-not-started / other."
    )
    md.append("")
    md.append("HIGH is almost entirely IN_PERIOD_REPLAY_VALIDATED or IN_PERIOD_BOUNDS.")
    md.append("The strata are therefore not comparable basketball states; they are clock-quality strata.")
    md.append("")
    md.append("## Candidate explanations")
    md.append("")
    md.append("- Overtime duration proxy (modeled Q1-start→last-end > 50 minutes): see slices.")
    md.append("- Unusual tip→Q1 lag (|lag−720s| > 300s): see slices.")
    md.append("- Delayed / missing knots: LOW/UNUSABLE and MISSING_PERIOD_STAMPS.")
    md.append("- Timestamp reconstruction: replay residual > 180s is the MEDIUM definition for in-period games.")
    md.append("- Specific dates: month table in JSON.")
    md.append("")
    md.append("## Conclusion")
    md.append("")
    if conclusion == "A":
        md.append("**A — likely data artifact.**")
        md.append("")
        md.append(
            "MEDIUM is not a random subsample of first-80 games. It is concentrated in "
            "replay-residual, intermission, and pre-tip alignment. Those labels mean the "
            "modeled wall clock is less trustworthy. A higher barrier rate in a poorly "
            "timestamped stratum can be produced by snapping the market to the wrong "
            "game state (or to no game state). That is not evidence that 'medium alignment' "
            "is an economically interpretable basketball regime."
        )
        md.append("")
        md.append(
            "We do **not** promote excluding MEDIUM as a trading filter. Quality labels "
            "were not preregistered as features. The residual vs validated in-period gap "
            "remains a reconstruction issue, not a demonstrated live edge."
        )
    elif conclusion == "C":
        md.append("**C — economically interpretable structural difference.**")
        md.append("")
        md.append("Not used: evidence was not strong enough to claim a basketball mechanism.")
    else:
        md.append("**B — unresolved.**")
        md.append("")
        md.append("The compositional difference is clear, but a residual basketball mechanism cannot be ruled out.")
    md.append("")
    md.append(f"Generated {utc_now()}")
    md.append("")
    text = "\n".join(md) + "\n"
    (OUT / "ALIGNMENT_FORENSICS.md").write_text(text)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    (SPEC_DIR / "ALIGNMENT_FORENSICS.md").write_text(text)
    print(f"forensics conclusion={conclusion_text} MEDIUM_replay_share={share_res:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
