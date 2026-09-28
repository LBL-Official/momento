#!/usr/bin/env python3
"""FIRST80_LIQUIDATION_MODEL_V1

40¢ is a liquidation TRIGGER, not a guaranteed fill.

Builds candle-structure scenario models of P(fill | bid crossed 40).
Historical L2 is UNAVAILABLE. Latency paths are SIMULATED, not observed.

Does not change live FIRST01 / Risk / Execution. LIVE EXECUTION CHANGED: FALSE.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ncaab_80_40_stop_candle_inspect as INS  # noqa: E402

PROGRAM = "FIRST80_LIQUIDATION_MODEL_V1"
ENTRY = 80.0
WIN = 20.0
TRIGGER = 40.0
DELAYS_MS = (0, 100, 250, 500, 1000, 2000, 5000)
FRONTIER_FILLS = (40.0, 38.0, 35.0, 32.0, 30.0, 28.0, 25.5, 25.0, 23.0, 20.0)

NCAAB_STOPS = (
    Path("/Users/user/Desktop/Momento/Backtesting Suite/Data/NCAAB/2025-2026/warehouse")
    / "derived/ncaab/first80_execution_audit/stop_candle_inspect/stop_candles.json"
)
NCAAB_OUT = (
    Path("/Users/user/Desktop/Momento/Backtesting Suite/Data/NCAAB/2025-2026/warehouse")
    / "derived/ncaab/first80_liquidation_model_v1"
)
NBA_CANDS = (
    Path("/Users/user/Desktop/Momento/Backtesting Suite/Data/NBA/2025-2026/warehouse")
    / "derived/nba/first80_execution_audit/candidates.json"
)
NBA_CANDLES = (
    Path("/Users/user/Desktop/Momento/Backtesting Suite/Data/NBA/2025-2026/warehouse")
    / "normalized/nba/candles_1m"
)
NBA_OUT = (
    Path("/Users/user/Desktop/Momento/Backtesting Suite/Data/NBA/2025-2026/warehouse")
    / "derived/nba/first80_liquidation_model_v1"
)
DOCS = Path("/Users/user/Desktop/Momento/docs/research/ncaab/FIRST80_LIQUIDATION_MODEL_V1.md")
GENERATED_TABLES = Path(
    "/Users/user/Desktop/Momento/docs/research/ncaab/FIRST80_LIQUIDATION_MODEL_V1_TABLES.md"
)

# Settled FIRST-80 counts from the frozen/measured audits. Do not refit.
BOOKS = {
    "ncaab": {"wins": 2998, "stops": 1099, "leak": 2, "n": 4099},
    "nba": {"wins": 910, "stops": 320, "leak": 0, "n": 1230},
}


def e4_to_cents(v) -> float | None:
    if v is None:
        return None
    return int(v) / 100.0


def clamp_fill(px: float | None) -> float | None:
    if px is None:
        return None
    return max(0.0, min(TRIGGER, px))


def buckets(fills: list[float]) -> dict:
    n = len(fills)
    if n == 0:
        return {"n": 0}
    ge38 = sum(1 for p in fills if p >= 38.0)
    mid3538 = sum(1 for p in fills if 35.0 <= p < 38.0)
    mid3035 = sum(1 for p in fills if 30.0 <= p < 35.0)
    lt30 = sum(1 for p in fills if p < 30.0)
    return {
        "n": n,
        "p_fill_ge_38": round(ge38 / n, 4),
        "p_fill_35_38": round(mid3538 / n, 4),
        "p_fill_30_35": round(mid3035 / n, 4),
        "p_fill_lt_30": round(lt30 / n, 4),
        "counts": {
            "ge_38": ge38,
            "35_38": mid3538,
            "30_35": mid3035,
            "lt_30": lt30,
        },
        "mean": round(sum(fills) / n, 4),
        "median": round(sorted(fills)[n // 2], 4),
        "p10": round(sorted(fills)[int(0.10 * (n - 1))], 4),
        "p90": round(sorted(fills)[int(0.90 * (n - 1))], 4),
        "min": round(min(fills), 4),
        "max": round(max(fills), 4),
    }


def ev_from_mean_fill(book: dict, mean_fill: float) -> dict:
    loss = ENTRY - mean_fill
    n = book["n"]
    pnl = book["wins"] * WIN - book["stops"] * loss
    ev = pnl / n
    return {
        "mean_fill_cents": round(mean_fill, 4),
        "e_loss_given_stop_cents": round(loss, 4),
        "gross_ev_cents": round(ev, 4),
        "gross_ev_R": round(ev / WIN, 4),
        "survival": round(book["wins"] / n, 6),
        "stop_rate": round(book["stops"] / n, 6),
    }


def zero_fill(book: dict) -> float:
    """Average stop fill at which gross EV is 0 (leak P&L = 0)."""
    return ENTRY - (book["wins"] * WIN) / book["stops"]


def frontier(book: dict) -> list[dict]:
    rows = []
    z = zero_fill(book)
    for p in FRONTIER_FILLS:
        ev = ev_from_mean_fill(book, p)
        rows.append(
            {
                **ev,
                "region": "positive"
                if ev["gross_ev_cents"] > 1.0
                else ("near_zero" if ev["gross_ev_cents"] > 0 else "negative"),
            }
        )
    return {"zero_crossing_fill_cents": round(z, 4), "points": rows}


def model_a(_row: dict) -> float:
    return TRIGGER


def model_b(row: dict) -> float | None:
    return clamp_fill(e4_to_cents(row.get("bid_close_e4")))


def model_c(row: dict) -> float | None:
    return clamp_fill(e4_to_cents(row.get("bid_low_e4")))


def model_d(row: dict) -> float | None:
    """Gap-aware SCENARIO: crash minutes use low; orderly minutes use close."""
    if row.get("jumped_from_above_50"):
        return model_c(row)
    return model_b(row)


def model_e(row: dict, delay_ms: int, horizon_ms: int) -> float | None:
    """SIMULATED path from first-touch/gap-high to bid_low. Not observed.

    horizon_ms is the assumed time for the candle's remaining range to
    realize. 60_000 ms = remainder of the minute. 5_000 ms = crash-collapse
    scenario (the whole wick happens in five seconds).
    If the minute already sits entirely below 40, t=0 uses bid_high.
    """
    low = e4_to_cents(row.get("bid_low_e4"))
    high = e4_to_cents(row.get("bid_high_e4"))
    if low is None or high is None:
        return None
    frac = min(1.0, max(0.0, delay_ms / float(horizon_ms)))
    start = high if high < TRIGGER else TRIGGER
    return clamp_fill(start + (low - start) * frac)


def apply_model(rows: list[dict], fn) -> list[float]:
    out = []
    for r in rows:
        if r.get("missing_candle"):
            continue
        px = fn(r)
        if px is not None:
            out.append(px)
    return out


def summarize_model(name: str, status: str, note: str, fills: list[float], book: dict) -> dict:
    b = buckets(fills)
    raw_mean = (sum(fills) / len(fills)) if fills else None
    ev = ev_from_mean_fill(book, raw_mean) if raw_mean is not None else None
    return {
        "model": name,
        "status": status,
        "note": note,
        "n_fills": len(fills),
        "distribution": b,
        "ev": ev,
    }


def inspect_nba_stops() -> list[dict]:
    cached = NBA_OUT / "stop_candles.json"
    if cached.exists():
        rows = json.loads(cached.read_text())
        if len(rows) == BOOKS["nba"]["stops"]:
            print(f"reusing cached NBA stop candles n={len(rows)}", flush=True)
            return rows
    cands = json.loads(NBA_CANDS.read_text())
    stops = [
        c
        for c in cands
        if c.get("status") == "FIRST_80"
        and c.get("stop_close_triggered")
        and c.get("expiration_result_yes") is not None
    ]
    orig_candles = INS.CANDLES
    INS.CANDLES = NBA_CANDLES
    rows = []
    try:
        for i, c in enumerate(stops, 1):
            if i % 50 == 0 or i == 1:
                print(f"nba inspect {i}/{len(stops)}", flush=True)
            row = INS.inspect_stop(c)
            if row:
                rows.append(row)
    finally:
        INS.CANDLES = orig_candles
    return rows


def run_sport(sport: str, rows: list[dict], out: Path) -> dict:
    book = BOOKS[sport]
    n_ok = sum(1 for r in rows if not r.get("missing_candle"))
    n_missing = sum(1 for r in rows if r.get("missing_candle"))
    if n_ok != book["stops"]:
        print(
            f"WARN {sport}: reconstructed {n_ok} stop candles "
            f"(missing {n_missing}) vs book stops {book['stops']}",
            flush=True,
        )
    models = [
        summarize_model(
            "A_impossible_ideal",
            "SCENARIO",
            "ExitPrice = 40. Not executable. Upper bound only.",
            apply_model(rows, model_a),
            book,
        ),
        summarize_model(
            "B_stop_minute_bid_close",
            "ESTIMATED",
            "Fill proxy = stop-minute yes_bid_close. Candle end, not a match.",
            apply_model(rows, model_b),
            book,
        ),
        summarize_model(
            "C_stop_minute_bid_low",
            "ESTIMATED",
            "Fill proxy = stop-minute yes_bid_low. Conservative intra-minute print.",
            apply_model(rows, model_c),
            book,
        ),
        summarize_model(
            "D_gap_aware",
            "SCENARIO",
            "If prior close > 50 and this close ≤ 40, use bid_low; else bid_close.",
            apply_model(rows, model_d),
            book,
        ),
    ]
    e_surface = []
    for horizon_ms, tag, note in (
        (60_000, "E60", "Linear remainder of the 60s candle. Optimistic if the crash is faster than one minute."),
        (5_000, "E5", "Crash-collapse: the stop-minute range realizes in 5s. Still SIMULATED."),
    ):
        for d in DELAYS_MS:
            fills = apply_model(
                rows,
                lambda r, delay=d, h=horizon_ms: model_e(r, delay, h),
            )
            e_surface.append(
                summarize_model(
                    f"{tag}_latency_{d}ms",
                    "SIMULATED",
                    note,
                    fills,
                    book,
                )
            )

    gap = [r for r in rows if r.get("jumped_from_above_50") and not r.get("missing_candle")]
    calm = [r for r in rows if not r.get("jumped_from_above_50") and not r.get("missing_candle")]
    cond = {
        "liquidity_L": "UNAVAILABLE",
        "l2": "UNAVAILABLE",
        "p_trigger": "prev_bid_close ESTIMATED as state immediately before the stop minute",
        "spread_S": "stop-minute ask_close - bid_close ESTIMATED; not intra-minute",
        "gap_n": len(gap),
        "non_gap_n": len(calm),
        "B_given_gap": buckets(apply_model(gap, model_b)),
        "B_given_non_gap": buckets(apply_model(calm, model_b)),
        "C_given_gap": buckets(apply_model(gap, model_c)),
        "C_given_range_gt_10c": buckets(
            apply_model([r for r in rows if r.get("bid_range_gt_10c")], model_c)
        ),
    }

    payload = {
        "program": PROGRAM,
        "sport": sport,
        "live_execution_changed": False,
        "trigger_is_not_fill": True,
        "rule": "40¢ = SIGNAL TO LIQUIDATE, not guaranteed fill price",
        "book": book,
        "stop_candles_reconstructed": n_ok,
        "stop_candles_missing": n_missing,
        "zero_crossing_fill_cents": round(zero_fill(book), 4),
        "models": models,
        "latency_surface": e_surface,
        "conditional": cond,
        "frontier": frontier(book),
        "future_live_experiment": {
            "status": "NOT_RUN",
            "record": ["T0_cross", "T1_detect", "T2_submit", "T3_ack", "T4_first_partial", "T5_final_fill", "P0", "P_fill_vwap"],
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    (out / "stop_candles.json").write_text(json.dumps(rows) + "\n")
    fills_rows = []
    for r in rows:
        if r.get("missing_candle"):
            continue
        fills_rows.append(
            {
                "ticker": r.get("ticker"),
                "event_ticker": r.get("event_ticker"),
                "stop_ts": r.get("stop_ts"),
                "A": model_a(r),
                "B": model_b(r),
                "C": model_c(r),
                "D": model_d(r),
                **{f"E60_{d}ms": model_e(r, d, 60_000) for d in DELAYS_MS},
                **{f"E5_{d}ms": model_e(r, d, 5_000) for d in DELAYS_MS},
                "prev_bid_close_cents": e4_to_cents(r.get("prev_bid_close_e4")),
                "spread_close_cents": (
                    None
                    if r.get("ask_close_e4") is None or r.get("bid_close_e4") is None
                    else (int(r["ask_close_e4"]) - int(r["bid_close_e4"])) / 100.0
                ),
                "bid_range_cents": e4_to_cents(r.get("bid_range_e4")),
                "jumped_from_above_50": r.get("jumped_from_above_50"),
                "gapped_entirely_below_40": r.get("gapped_entirely_below_40"),
            }
        )
    (out / "fills.json").write_text(json.dumps(fills_rows) + "\n")
    write_sport_report(payload, out / "REPORT.md")
    return payload


def write_sport_report(p: dict, path: Path) -> None:
    book = p["book"]
    z = p["zero_crossing_fill_cents"]
    lines = [
        f"# {PROGRAM} — {p['sport'].upper()}",
        "",
        "**40¢ = signal to liquidate, not a guaranteed fill.**",
        "LIVE EXECUTION CHANGED: FALSE. L2 UNAVAILABLE.",
        "",
        f"Book: {book['wins']} wins / {book['stops']} stops / {book['leak']} leak / n={book['n']}",
        f"Gross EV is zero when average stop fill falls to **{z}¢** (before fees).",
        "",
        "## Models",
        "",
        "| Model | Status | E[P_fill] | E[L\\|Stop] | P(≥38) | P(35–38) | P(30–35) | P(<30) | EV ¢ |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in p["models"] + p["latency_surface"]:
        d = m["distribution"]
        ev = m["ev"] or {}
        lines.append(
            f"| {m['model']} | {m['status']} | {d.get('mean')} | "
            f"{ev.get('e_loss_given_stop_cents')} | {d.get('p_fill_ge_38')} | "
            f"{d.get('p_fill_35_38')} | {d.get('p_fill_30_35')} | "
            f"{d.get('p_fill_lt_30')} | {ev.get('gross_ev_cents')} |"
        )
    lines.extend(["", "## Viability frontier (constant average fill)", "", "| Avg stop fill | EV ¢ | Region |", "|---:|---:|---|"])
    for row in p["frontier"]["points"]:
        lines.append(
            f"| {row['mean_fill_cents']} | {row['gross_ev_cents']} | {row['region']} |"
        )
    lines.extend(
        [
            "",
            "Latency rows are **SIMULATED** (linear remainder of a 60s candle).",
            "They are not historical millisecond observations.",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def write_docs(ncaab: dict, nba: dict) -> None:
    zn = ncaab["zero_crossing_fill_cents"]
    zb = nba["zero_crossing_fill_cents"]

    def row(p, name):
        m = next(x for x in p["models"] if x["model"] == name)
        return m

    nb = row(ncaab, "B_stop_minute_bid_close")
    nc = row(ncaab, "C_stop_minute_bid_low")
    nd = row(ncaab, "D_gap_aware")
    bb = row(nba, "B_stop_minute_bid_close")
    bc = row(nba, "C_stop_minute_bid_low")
    text = f"""# FIRST80_LIQUIDATION_MODEL_V1

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
40¢ = SIGNAL TO LIQUIDATE
40¢ ≠ GUARANTEED FILL PRICE
```

The 80→40 path exists on NBA and NCAAB candles. The remaining object is
not “can we sell at exactly 40?” It is:

```text
P(P_fill | market crosses 40)
```

and the EV question:

```text
How bad can average liquidation become before the path edge disappears?
```

## What this model is allowed to use

Observed / estimated from 1-minute TOB candles:

- `P_trigger` proxy: previous minute `yes_bid_close`
- `R_candle`: stop-minute bid high−low
- `ΔP` proxy: previous close → this close
- `S` proxy: stop-minute `ask_close − bid_close`

Unavailable (not invented):

- Historical L2 / `L` queue liquidity
- Intra-minute matching
- Detection / decision / RTT timestamps

Status labels: `ESTIMATED` (candle proxy), `SCENARIO` (defined rule),
`SIMULATED` (latency interpolation), `UNAVAILABLE` (L2).

## Detection vs matching

```text
cross 40 → detect → decide → transmit → MATCH / consume liquidity → fill
```

Fast ①–③ (as on the MLB desk) does not solve ④. If the book prints
42→41→40→38→35→30 inside one minute, an instant bot still cannot
guarantee 40.00.

## Book (unchanged path counts)

| | NCAAB | NBA |
|---|---:|---:|
| Settled FIRST-80 | 4,099 | 1,230 |
| Survivors | 2,998 | 910 |
| Close-40 stops | 1,099 | 320 |
| Survival | 73.14% | 73.98% |
| **EV = 0 at avg fill** | **{zn}¢** | **{zb}¢** |

Wins still +20¢. Only stop legs are re-priced. Fees UNRESOLVED.

## NCAAB liquidation models (1,099 stops)

| Model | Status | E[P_fill] | E[L\\|Stop] | EV ¢ |
|---|---|---:|---:|---:|
| A ideal 40 | SCENARIO | {ncaab['models'][0]['distribution']['mean']} | {ncaab['models'][0]['ev']['e_loss_given_stop_cents']} | {ncaab['models'][0]['ev']['gross_ev_cents']} |
| B bid close | ESTIMATED | {nb['distribution']['mean']} | {nb['ev']['e_loss_given_stop_cents']} | {nb['ev']['gross_ev_cents']} |
| C bid low | ESTIMATED | {nc['distribution']['mean']} | {nc['ev']['e_loss_given_stop_cents']} | {nc['ev']['gross_ev_cents']} |
| D gap-aware | SCENARIO | {nd['distribution']['mean']} | {nd['ev']['e_loss_given_stop_cents']} | {nd['ev']['gross_ev_cents']} |

Model B close-path distribution (NCAAB):

- P(fill ≥ 38) = {nb['distribution']['p_fill_ge_38']}
- P(35–38) = {nb['distribution']['p_fill_35_38']}
- P(30–35) = {nb['distribution']['p_fill_30_35']}
- P(< 30) = {nb['distribution']['p_fill_lt_30']}

## NBA liquidation models (320 stops)

| Model | Status | E[P_fill] | EV ¢ |
|---|---|---:|---:|
| B bid close | ESTIMATED | {bb['distribution']['mean']} | {bb['ev']['gross_ev_cents']} |
| C bid low | ESTIMATED | {bc['distribution']['mean']} | {bc['ev']['gross_ev_cents']} |

## Viability frontier

Hold the observed survival rates fixed. Vary only average stop fill.

| Avg stop fill | NCAAB EV ¢ | NBA EV ¢ |
|---:|---:|---:|
"""
    nba_pts = {r["mean_fill_cents"]: r["gross_ev_cents"] for r in nba["frontier"]["points"]}
    for r in ncaab["frontier"]["points"]:
        p = r["mean_fill_cents"]
        text += f"| {p} | {r['gross_ev_cents']} | {nba_pts.get(p, '')} |\n"
    text += f"""
The strategy does not need perfect 40¢ fills. It needs average liquidation
**above ~{zn}¢ (NCAAB)** / **~{zb}¢ (NBA)** before fees.

## Latency surface

Model E interpolates from first-touch 40 (or gap high) to bid_low over 60s.
That is a **SIMULATED** stress, not a reconstructed clock.

Live/paper next season should record T0…T5 and VWAP exit so
`P(P_fill | 80→40 liquidation)` becomes empirical.

## Non-goals

- Do not write 40.00 into live NBA/NCAAB execution as a fill.
- Do not invent L2 from candles.
- Do not change MLB FIRST01 50% VWAP stop semantics.
- Do not promote this model to Risk/Execution.

Code: `apps/ncaab-data/scripts/first80_liquidation_model_v1.py`  
Artifacts: `.../warehouse/derived/{{ncaab,nba}}/first80_liquidation_model_v1/`
"""
    GENERATED_TABLES.write_text(text)


def main() -> int:
    z_n = zero_fill(BOOKS["ncaab"])
    z_b = zero_fill(BOOKS["nba"])
    assert abs(z_n - 25.441) < 0.01, z_n
    assert abs(z_b - 23.125) < 0.01, z_b
    assert ev_from_mean_fill(BOOKS["ncaab"], 40.0)["gross_ev_cents"] > 3.8
    assert ev_from_mean_fill(BOOKS["ncaab"], z_n)["gross_ev_cents"] == 0.0

    print("loading NCAAB stop candles", flush=True)
    ncaab_rows = json.loads(NCAAB_STOPS.read_text())
    ncaab = run_sport("ncaab", ncaab_rows, NCAAB_OUT)
    print("inspecting NBA stop candles", flush=True)
    nba_rows = inspect_nba_stops()
    nba = run_sport("nba", nba_rows, NBA_OUT)
    write_docs(ncaab, nba)
    cmp = {
        "program": PROGRAM,
        "live_execution_changed": False,
        "ncaab_zero_crossing_fill_cents": ncaab["zero_crossing_fill_cents"],
        "nba_zero_crossing_fill_cents": nba["zero_crossing_fill_cents"],
        "ncaab": {m["model"]: m["ev"] for m in ncaab["models"]},
        "nba": {m["model"]: m["ev"] for m in nba["models"]},
        "ncaab_E5_5000ms": next(
            x["ev"] for x in ncaab["latency_surface"] if x["model"] == "E5_latency_5000ms"
        ),
        "nba_E5_5000ms": next(
            x["ev"] for x in nba["latency_surface"] if x["model"] == "E5_latency_5000ms"
        ),
    }
    (NCAAB_OUT / "comparison.json").write_text(json.dumps(cmp, indent=2) + "\n")
    print(json.dumps(cmp, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
