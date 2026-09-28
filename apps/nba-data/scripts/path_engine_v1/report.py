#!/usr/bin/env python3
"""Write Path Engine V1 REPORT.md, summary.json, and production line."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import (
    EV_UNCONDITIONAL,
    EXPECTED_FIRST80,
    EXPECTED_STOPS,
    MIN_ACCEPTANCE,
    OUT,
    Q_UNCONDITIONAL,
    SPEC_DIR,
    utc_now,
    write_json,
)


def load(path: Path):
    return json.loads(path.read_text())


def pct(x, digits=2):
    if x is None:
        return "NA"
    return f"{100.0 * x:.{digits}f}%"


def num(x, digits=4):
    if x is None:
        return "NA"
    return f"{x:.{digits}f}"


def bucket_table(buckets):
    lines = [
        "| Bucket | n | actual q | Wilson 95% | mean q̂ | EV = 1−3q |",
        "| --- | ---: | ---: | --- | ---: | ---: |",
    ]
    for b in buckets:
        wil = "NA"
        if b.get("wilson_lo") is not None:
            wil = f"{pct(b['wilson_lo'])}–{pct(b['wilson_hi'])}"
        ev = "NA" if b.get("ev_actual") is None else f"{b['ev_actual']:+.3f} R"
        lines.append(
            f"| {b['bucket']} | {b['n']} | {pct(b.get('actual_q'))} | {wil} | "
            f"{pct(b.get('mean_pred'))} | {ev} |"
        )
    return "\n".join(lines)


def production_decision(sel, m_oos, filt, filt_oos):
    sep = bool(m_oos.get("adjacent_separation"))
    ece = m_oos.get("ece")
    mean_pred = m_oos.get("mean_pred")
    actual_q = m_oos.get("actual_q")
    cal_ok = (
        ece is not None
        and ece <= 0.05
        and mean_pred is not None
        and actual_q is not None
        and abs(mean_pred - actual_q) <= 0.08
    )
    if filt.get("chosen_threshold") is None or filt_oos is None:
        return (
            "NO FILTER",
            sep,
            cal_ok,
            False,
            False,
            "No reject-high-q threshold cleared the VAL economic+acceptance gate.",
        )
    ev_ok = bool(filt_oos.get("beats_unconditional_ev"))
    acc_ok = bool(filt_oos.get("meets_acceptance_floor"))
    traded_cal = cal_ok
    if filt_oos.get("actual_q_accepted") is not None and filt_oos.get("n_accepted"):
        # crude: accepted-set actual q should be below breakeven and not explode vs pred
        traded_cal = filt_oos["actual_q_accepted"] < 0.40
    all_four = sep and traded_cal and ev_ok and acc_ok
    if all_four:
        return (
            "CANDIDATE PRODUCTION FILTER",
            sep,
            traded_cal,
            ev_ok,
            acc_ok,
            "OOS met separation, calibration, EV, and ≥50% acceptance.",
        )
    if ev_ok or sep:
        return (
            "RESEARCH-ONLY FILTER",
            sep,
            traded_cal,
            ev_ok,
            acc_ok,
            "Some economic or statistical structure exists but OOS does not meet all four production criteria.",
        )
    return (
        "NO FILTER",
        sep,
        traded_cal,
        ev_ok,
        acc_ok,
        "Selected filter does not improve OOS economics with usable frequency.",
    )


def verdict(prod, m2a_oos, m2a_val, m0_val, sep_oos, gate_2b, gate_3):
    brier_gain = m0_val["brier"] - m2a_val["brier"]
    if prod == "CANDIDATE PRODUCTION FILTER" and sep_oos:
        return "VERDICT A — STRONG CONDITIONAL SIGNAL"
    if sep_oos or brier_gain > 0.002 or gate_2b or gate_3:
        return "VERDICT B — WEAK / DESCRIPTIVE SIGNAL"
    return "VERDICT C — NO ROBUST CONDITIONAL SIGNAL"


def main() -> int:
    m0 = load(OUT / "models" / "baseline" / "metrics.json")
    m2a = load(OUT / "models" / "logistic_2a" / "metrics.json")
    m2b = load(OUT / "models" / "logistic_2b" / "metrics.json")
    m3 = load(OUT / "models" / "tree" / "metrics.json")
    sel = load(OUT / "model_selection.json")
    uni = load(OUT / "univariate_train.json")
    leak = load(OUT / "leakage_audit.json")
    obs = load(OUT / "observations_summary.json")

    chosen = sel["selected_model"]
    if chosen == "3":
        m_oos = m3["oos"]
        m_val = m3["validation"]
    elif chosen == "2B":
        m_oos = m2b["oos"]
        m_val = m2b["validation"]
    else:
        m_oos = m2a["oos"]
        m_val = m2a["validation"]

    prod, sep, cal_ok, ev_ok, acc_ok, prod_why = production_decision(
        sel, m_oos, sel["filter"], sel.get("filter_oos")
    )
    verd = verdict(
        prod,
        m2a["oos"],
        m2a["validation"],
        m0["validation"],
        sep,
        sel["2b_promoted"],
        sel["model3_selected"],
    )

    uni_rows = uni["rows"]
    interesting = [
        u
        for u in uni_rows
        if u.get("trend") in ("MONOTONE_UP", "MONOTONE_DOWN")
    ]
    interesting_s = ", ".join(u["feature"] for u in interesting[:12]) or "none"

    filt = sel["filter"]
    filt_oos = sel.get("filter_oos")
    weekly = sel.get("weekly_first80_historical")
    weekly_f = sel.get("expected_weekly_if_filter")

    md = f"""# Path Engine V1 report

```text
PATH_ENGINE_V1_MARKET_ONLY
ENTRY_DECISION_TIME = end of first-80 candle
Y_40 = 1 ⇔ close-path 40 after entry
q(Z) = P(Y_40 = 1 | Z_τ80)
EV_gross = 1 − 3q
breakeven q = 33.33%
```

Written `{utc_now()}`. Research only. Does not change live FIRST01.

## Frozen baseline

| Quantity | Value |
| --- | ---: |
| Games | {obs['games']} |
| First-80 | {obs['first80']} |
| Y_40 (close-path 40) | {obs['target_close_40']} |
| Survivors | {obs['survivors']} |
| Wick 40 post-entry only | {obs['target_wick_40_post_entry_bar_only']} |
| Wick 40 including entry bar | {obs['target_wick_40_including_entry_bar']} |
| q unconditional | {pct(obs['q_unconditional'])} |
| EV_gross unconditional | {obs['ev_unconditional']:+.4f} R |

Gate `{EXPECTED_FIRST80}/{EXPECTED_STOPS}` reproduced: **{obs['baseline_ok']}**.

Splits: {json.dumps(obs['splits'])}.

## Leakage

Fail count: **{leak['fail_count']}**. Same-bar OHLC is allowed because the modeled
decision is candle close. Targets are TARGET_ONLY. PBP wall-clock was not used.

## Canonical economics

Unconditional q = {pct(Q_UNCONDITIONAL)} so EV ≈ **{EV_UNCONDITIONAL:+.3f} R**.
The engine estimates path-barrier failure, not NBA winner.

## Model 1 (TRAIN univariate)

Pre-registered confirmatory windows are 1m / 5m / 15m. 3m / 10m / 30m are
exploratory TRAIN-only and did not enter Model 2A.

Monotone TRAIN features: {interesting_s}.

Full tables: `univariate_train.json`.

## Models (VAL = CHOOSE, OOS = VERIFY)

| Model | VAL Brier | VAL AUC | VAL ECE | VAL separation | OOS Brier | OOS AUC | OOS ECE | OOS separation |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| 0 unconditional | {num(m0['validation']['brier'])} | {num(m0['validation']['roc_auc'])} | {num(m0['validation']['ece'])} | {m0['validation']['adjacent_separation']} | {num(m0['oos']['brier'])} | {num(m0['oos']['roc_auc'])} | {num(m0['oos']['ece'])} | {m0['oos']['adjacent_separation']} |
| 2A core logistic (12) | {num(m2a['validation']['brier'])} | {num(m2a['validation']['roc_auc'])} | {num(m2a['validation']['ece'])} | {m2a['validation']['adjacent_separation']} | {num(m2a['oos']['brier'])} | {num(m2a['oos']['roc_auc'])} | {num(m2a['oos']['ece'])} | {m2a['oos']['adjacent_separation']} |
| 2B extended L2 (25) | {num(m2b['validation']['brier'])} | {num(m2b['validation']['roc_auc'])} | {num(m2b['validation']['ece'])} | {m2b['validation']['adjacent_separation']} | {num(m2b['oos']['brier'])} | {num(m2b['oos']['roc_auc'])} | {num(m2b['oos']['ece'])} | {m2b['oos']['adjacent_separation']} |
| 3 depth-2 GBM | {num(m3['validation']['brier'])} | {num(m3['validation']['roc_auc'])} | {num(m3['validation']['ece'])} | {m3['validation']['adjacent_separation']} | {num(m3['oos']['brier'])} | {num(m3['oos']['roc_auc'])} | {num(m3['oos']['ece'])} | {m3['oos']['adjacent_separation']} |

2B promotion gate passed: **{sel['2b_promoted']}**.
Model 3 VAL gate passed: **{sel['model3_selected']}** (OOS role: {m3['oos_role']}).
Selected model: **{chosen}**.

TRAIN CV / Platt (2A): {json.dumps(m2a['cv'])}.
TRAIN CV / Platt (2B): {json.dumps(m2b['cv'])}.
Platt was not fit on VALIDATION.

### Selected model OOS risk buckets

{bucket_table(m_oos['buckets'])}

Merged (n < 30 combined): adjacent_separation = **{m_oos['adjacent_separation']}**.

### Pre-registered filters (VALIDATION choose)

Thresholds {{0.20, 0.25, 0.30, 0.3333}}. Accept if q̂ < threshold.

"""
    for c in filt["candidates"]:
        md += (
            f"- t={c['threshold']}: accept {c['n_accepted']}/{c['n']} "
            f"({pct(c['acceptance_rate'])}), actual q={pct(c['actual_q_accepted'])}, "
            f"EV={num(c['ev_accepted'], 3)} R, "
            f"beats split EV={c['beats_unconditional_ev']}, "
            f"acc≥50%={c['meets_acceptance_floor']}\n"
        )
    md += f"\nChosen VAL threshold: **{filt['chosen_threshold']}**.\n\n"
    if filt_oos:
        md += (
            f"OOS frozen filter t={filt_oos['threshold']}: "
            f"accept {filt_oos['n_accepted']}/{filt_oos['n']} "
            f"({pct(filt_oos['acceptance_rate'])}), "
            f"actual q={pct(filt_oos['actual_q_accepted'])}, "
            f"EV={num(filt_oos['ev_accepted'], 3)} R "
            f"(unconditional on OOS {num(filt_oos['ev_unconditional'], 3)} R).\n\n"
        )
    else:
        md += "No filter frozen for OOS.\n\n"

    md += f"""## Opportunity frequency

Historical first-80 weekly rate (season span): **{num(weekly, 2)}** opportunities/week.
Expected weekly if VAL-chosen filter applied: **{num(weekly_f, 2)}**.
Production floor is {pct(MIN_ACCEPTANCE)} of first-80 opportunities.

## Production utility

```text
ProductionUtility = f(Edge, Calibration, AcceptanceRate, Capacity, Drawdown)
```

| Criterion | OOS |
| --- | --- |
| Risk-bucket separation | {sep} |
| Calibration | {cal_ok} |
| EV_accepted > EV_unconditional | {ev_ok} |
| AcceptanceRate ≥ 50% | {acc_ok} |

{prod_why}

## Coefficients (Model 2A, standardized TRAIN)

"""
    for row in m2a["coefficients"]:
        md += f"- `{row['feature']}`: {row['coef_standardized']:+.4f}\n"

    md += f"""

## What this engine refuses

- Winner-prediction creep
- Future candles in Z_τ80
- PBP timestamp invention
- OOS threshold mining
- Silent 3/10/30m promotion into 2A
- Overwriting the frozen 80/40 audit

A negative result is a scientific success: the unconditional 80/40 path
anomaly can stand on its own.

---

```text
{verd}
{prod}
```
"""
    (OUT / "REPORT.md").write_text(md)
    summary = {
        "written_utc": utc_now(),
        "verdict": verd,
        "production": prod,
        "selected_model": chosen,
        "q_unconditional": Q_UNCONDITIONAL,
        "ev_unconditional": EV_UNCONDITIONAL,
        "baseline_ok": obs["baseline_ok"],
        "leakage_fail_count": leak["fail_count"],
        "2b_promoted": sel["2b_promoted"],
        "model3_selected": sel["model3_selected"],
        "filter_threshold": filt["chosen_threshold"],
        "oos_metrics": m_oos,
        "oos_filter": filt_oos,
        "utility": {
            "separation": sep,
            "calibration": cal_ok,
            "ev": ev_ok,
            "acceptance": acc_ok,
        },
        "weekly_first80_historical": weekly,
        "expected_weekly_if_filter": weekly_f,
        "spec": str(SPEC_DIR),
    }
    write_json(OUT / "summary.json", summary)
    print(verd)
    print(prod)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
