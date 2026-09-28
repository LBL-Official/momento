"""Write REPORT.md from experiment outputs."""

from __future__ import annotations

from pathlib import Path

from . import PROGRAM

DOCS = Path("/Users/user/Desktop/Momento/docs/research/A1_HYBRID_HEDGE")


def _m(d, *keys, default="—"):
    cur = d
    for k in keys:
        if cur is None or not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    if isinstance(cur, float):
        return f"{cur:.4f}"
    return cur


def write_report(sports: dict, meta: dict) -> Path:
    nba = sports["nba"]
    p5 = sports["ncaab"]
    lines = [
        "# A1 Hybrid Hedge Optimization — REPORT",
        "",
        "Research only. **LIVE EXECUTION CHANGED: FALSE.**",
        "Does not change FIRST01, Risk, Execution, or live MLB 80/81/83/89.",
        "",
        f"Program: `{PROGRAM}`  ",
        f"UNIVERSE_VERSION: `{meta.get('universe_version')}`  ",
        f"DATASET_VERSION: `{meta.get('dataset_version')}`  ",
        f"CODE_VERSION: `{meta.get('code_version')}`  ",
        f"CONFIG_HASH: `{meta.get('config_hash')}`  ",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        "The question is whether buying opponent YES (A2) after a FIRST-80",
        "favorite-YES entry improves the 80→40 book under **realistic**",
        "execution assumptions. A one-minute close crossing a threshold is a",
        "**price event**, not a fill.",
        "",
        f"- **NBA** conservative causal verdict: `{nba['verdict']}`",
        f"- **NCAAB P5** conservative causal verdict: `{p5['verdict']}`",
        "",
        f"NBA note: {nba['verdict_note']}",
        "",
        f"NCAAB P5 note: {p5['verdict_note']}",
        "",
        "Headline book: **conservative causal in-band** — first A2 close after",
        "entry that lands inside the band is modeled at the **observed** close;",
        "jump-through / overshoot above the band is a **miss**; then 80→40.",
        "Persist-k lookahead is reported separately and is **not** the headline.",
        "",
        "Theoretical V1 (book every close≥H at exactly H) is labeled",
        "**NON-EXECUTION-AUDITED** and is not a production recommendation.",
        "",
        "### Locked VAL configurations (disclosure)",
        "",
        f"- NBA locked H = **{nba['locked_h']}**. {nba['lock_reason']}",
        f"- NCAAB P5 locked H = **{p5['locked_h']}**. {p5['lock_reason']}",
        "",
        "Selection used VALIDATION only. OOS is reported once.",
        "",
        "---",
        "",
        "## Data",
        "",
        "| Sport | Universe | n | Date min | Date max | TRAIN | VAL | OOS |",
        "|---|---|---:|---|---|---:|---:|---:|",
        _row_sport("NBA", nba),
        _row_sport("NCAAB P5 vs P5", p5),
        "",
        "Warehouse NCAAB FIRST-80 = 4,099 is **not** used.",
        "",
        "- Resolution: 1-minute candles (`yes_bid_close`).",
        "- A1/A2: same `event_id`, opposing YES tickers. Not inferred from price.",
        "- Timing: V3 strict next-bar (`t > first_80_timestamp`).",
        "- L2 / queue / maker fills: **UNOBSERVED**.",
        "- Fees: **UNRESOLVED** (gross ¢). Cost model is a zero stub.",
        "- Actual A1 entry close: unavailable on V4 ledger; nominal entry = 80.",
        "",
        "---",
        "",
        "## Methodology",
        "",
        "1. **Entry:** frozen FIRST-80 (first tradable bid-close ≥ 80 after < 80).",
        "2. **Hedge search:** H = 10…60¢. Bands: exact, ±1, ±2, plus named 17–22 / 27–32 / 37–42 / 35–45.",
        "3. **Causal in-band:** first close ≥ band_lo; if that close ∈ [lo, hi] and not a 10¢ jump, modeled hedge at **that close**. Else miss.",
        "4. **Lookahead persist:** TIER1 if `1 + persist_subsequent_min ≥ k`. Uses future bars. Labeled LOOKAHEAD.",
        "5. **Gap:** close≥lo but close > hi or `jump_10c`. No fill at H.",
        "6. **Fallback A:** 80→40 Model A (−40 if A1 later close ≤ 40). Headline.",
        "7. **Fallback C/D:** refuse the −40 A1 fill; hold to settlement.",
        "8. **Theoretical replace:** any close≥H fills at H, else hold. Upper bound.",
        "9. **Probabilistic / partial:** scenario weights, not observed probabilities.",
        "",
        "---",
        "",
        "## Experiment A — reproduced FIRST80 baseline",
        "",
        _repro_table(nba, p5),
        "",
        "---",
        "",
        "## Results",
        "",
        "### Theoretical vs conservative (H=40 exact, FULL)",
        "",
        _h40_table(nba, p5),
        "",
        "### VAL lock and OOS (conservative causal, exact band)",
        "",
        _lock_table(nba, p5),
        "",
        "### Gap leakage at H=40",
        "",
        _gap_text(nba, p5),
        "",
        "---",
        "",
        "## Risk",
        "",
        "Tail metrics are on the conservative causal book. Theoretical EV that",
        "appears from booking 23→75 @ 40 is **not** risk reduction — it is fiction.",
        "",
        "Bootstrap CIs on the dashboard are **sampling** uncertainty",
        "(IID trades and date-block). They are not regime / season uncertainty.",
        "",
        "---",
        "",
        "## Recommendation",
        "",
        _reco(nba, p5),
        "",
        "---",
        "",
        "## Limitations",
        "",
        "- No historical L2; no confirmed maker fills.",
        "- One-minute bars cannot prove a print inside a gap.",
        "- Persist-k is lookahead unless used only as a label.",
        "- Fallback B has no extra A1 stop-candle occupancy in V3; it equals A.",
        "- Fees, slippage, and depth are not in the warehouse.",
        "- P5 OOS is small; do not over-read a single season.",
        "- Live FIRST01 cannot currently hold A2 (one market per game).",
        "- Do not program a VAL/FULL hedge EV as a T0 live rule.",
        "",
        "---",
        "",
        "## Does realistic A1 hedging improve FIRST80?",
        "",
        _final(nba, p5),
        "",
        "Artifacts: `docs/research/A1_HYBRID_HEDGE/`.",
        "Dashboard: `frontend/a1-hybrid-hedge/`.",
        "",
    ]
    path = DOCS / "REPORT.md"
    path.write_text("\n".join(lines))
    # user-facing alias
    (Path("/Users/user/Desktop/Momento/docs/research/A1_HYBRID_HEDGE_REPORT.md")).write_text(
        path.read_text()
    )
    return path


def _row_sport(name, s):
    sn = s["split_n"]
    return (
        f"| {name} | {s.get('date_min')}–{s.get('date_max')} | {s['n']} | "
        f"{s['date_min']} | {s['date_max']} | {sn.get('TRAIN', 0)} | "
        f"{sn.get('VALIDATION', 0)} | {sn.get('OOS', 0)} |"
    )


def _repro_table(nba, p5):
    def line(label, s):
        r = s["experiment_a"]["reproduction"]
        flag = "PASS" if r["ok"] else "FAIL"
        return (
            f"| {label} | {r['n']} | {r['hold']} | {r['stop']} | {r['v1']} | {flag} |"
        )

    return "\n".join(
        [
            "| Sport | n | Hold EV | 80→40 EV | V1 H=40 EV | Gate |",
            "|---|---:|---:|---:|---:|---|",
            line("NBA", nba),
            line("NCAAB P5", p5),
        ]
    )


def _pick_h40(s):
    full = s["locked"].get("FULL")
    # locked may not be H=40; find from neighbors or experiment_a v1
    return full


def _h40_from_locked_or_surface(s):
    # runner slim has surface_full_exact in dashboard; full sports have surface
    rows = s.get("surface") or s.get("surface_full_exact") or []
    for r in rows:
        if r.get("H") == 40 and r.get("band") == "exact" and r.get("split") == "FULL":
            return r
    return None


def _h40_table(nba, p5):
    lines = [
        "| Book | NBA EV | vs 80→40 | NCAAB P5 EV | vs 80→40 |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, key in (
        ("80→40 original", None),
        ("Theoretical replace @40", "theoretical_replace"),
        ("Theoretical hybrid @40", "theoretical_hybrid"),
        ("Conservative causal @40", "conservative_causal"),
        ("Lookahead persist k=3 @40", "lookahead_persist"),
    ):
        nr, pr = _h40_from_locked_or_surface(nba), _h40_from_locked_or_surface(p5)
        if key is None:
            n_ev = _m(nr, "original", "mean") if nr else _m(nba["experiment_a"]["stop_80_40"], "mean")
            p_ev = _m(pr, "original", "mean") if pr else _m(p5["experiment_a"]["stop_80_40"], "mean")
            lines.append(f"| {label} | {n_ev} | 0 | {p_ev} | 0 |")
        else:
            n_ev = _m(nr, key, "mean")
            p_ev = _m(pr, key, "mean")
            n_inc = _m(nr, key, "inc_vs_original")
            p_inc = _m(pr, key, "inc_vs_original")
            lines.append(f"| {label} | {n_ev} | {n_inc} | {p_ev} | {p_inc} |")
    return "\n".join(lines)


def _lock_table(nba, p5):
    lines = [
        "| Sport | Locked H | VAL EV | VAL vs 80→40 | OOS EV | OOS vs 80→40 | Plateau |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, s in (("NBA", nba), ("NCAAB P5", p5)):
        plat = s["plateau"]
        val = s["locked"].get("VALIDATION") or {}
        oos = s["locked"].get("OOS") or {}
        lines.append(
            f"| {name} | {s['locked_h']} | "
            f"{_m(val, 'conservative_causal', 'mean')} | "
            f"{_m(val, 'conservative_causal', 'inc_vs_original')} | "
            f"{_m(oos, 'conservative_causal', 'mean')} | "
            f"{_m(oos, 'conservative_causal', 'inc_vs_original')} | "
            f"{plat.get('h_lo')}–{plat.get('h_hi')} (w={plat.get('width')}) |"
        )
    return "\n".join(lines)


def _gap_text(nba, p5):
    def g(s):
        rows = [x for x in s["gaps"] if x.get("split") == "FULL" or "n_gap" in x]
        # first FULL-like
        for x in s["gaps"]:
            if x.get("split") == "FULL":
                return x
        return s["gaps"][0] if s["gaps"] else {}

    gn, gp = g(nba), g(p5)
    return (
        f"NBA H=40: close hits={gn.get('n_close')} in-band={gn.get('n_in_band')} "
        f"gaps={gn.get('n_gap')} theo−causal={gn.get('delta_theo_minus_causal')}.  "
        f"NCAAB P5: close hits={gp.get('n_close')} in-band={gp.get('n_in_band')} "
        f"gaps={gp.get('n_gap')} theo−causal={gp.get('delta_theo_minus_causal')}."
    )


def _reco(nba, p5):
    return (
        f"**NBA:** `{nba['verdict']}` — {nba['verdict_note']}\n\n"
        f"**NCAAB P5:** `{p5['verdict']}` — {p5['verdict_note']}\n\n"
        "Assumptions required for any hedge-positive reading: in-band close is a "
        "fill at that close (not proven), complete hedge, zero fees, fallback A, "
        "strict next-bar timing. Relaxing any of those (gaps booked as fills, "
        "partial size, taker fees) moves the book toward 80→40 or worse."
    )


def _final(nba, p5):
    vs = {nba["verdict"], p5["verdict"]}
    if vs == {"NO_ECONOMIC_CASE_FOR_HEDGING"}:
        return (
            "**No — not under the conservative causal book.** Theoretical V1 edge "
            "is largely gap fiction. Do not implement A2 hedging in production "
            "from this layer."
        )
    if "HEDGING_IMPROVES_BOTH_EV_AND_RISK" in vs:
        return (
            "Possibly, but only where VAL and OOS both beat 80→40 on the "
            "causal in-band book. Read sport sections and CIs before any "
            "implementation discussion. Still not a live order."
        )
    return (
        "**Not as a live rule.** Results are sport- and assumption-dependent. "
        "The conservative causal book does not support programming an A2 hedge "
        "into FIRST01. Keep 80→40 as the research-supported causal trade."
    )
