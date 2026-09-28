"""Cost overlay, adjacent entry buckets, season groups. No invented OOS labels."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from roller.results_math.means import mean, median, quantile
from roller.results_math.models import DERIVED, HYPOTHETICAL, OBSERVED, UNAVAILABLE
from roller.results_math.multiple_testing import disclose
from roller.results_math.observations import e4_to_cents
from roller.results_math.proportions import rate, wilson_interval
from roller.results_math.returns import return_distribution

COST_CENTS = (0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0)


def cost_sensitivity(gross_ev_cents: float | None) -> dict[str, Any]:
    if gross_ev_cents is None:
        return {"status": UNAVAILABLE, "reason": "No gross EV to stress."}
    rows = []
    for c in COST_CENTS:
        rows.append(
            {
                "cost_cents": c,
                "net_ev_cents": float(gross_ev_cents) - c,
            }
        )
    return {
        "status": HYPOTHETICAL,
        "label": "COST SENSITIVITY · symmetric per-contract cost · not platform fees",
        "gross_ev_cents": float(gross_ev_cents),
        "break_even_cost_cents": float(gross_ev_cents),
        "grid": rows,
        "note": "Platform fees are UNAVAILABLE. This is a scenario overlay.",
    }


def _season_from_ts(ts: str | None) -> str | None:
    if not ts or len(ts) < 7:
        return None
    try:
        year = int(ts[0:4])
        month = int(ts[5:7])
    except ValueError:
        return None
    if month >= 10:
        return f"{year}-{str(year + 1)[2:]}"
    return f"{year - 1}-{str(year)[2:]}"


def season_partitions(obs: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in obs:
        key = _season_from_ts(str(r.get("observation_ts") or "") or None)
        if key:
            buckets[key].append(r)
    if not buckets:
        return {"status": UNAVAILABLE, "reason": "No observation timestamps for season grouping."}
    seasons = []
    for name in sorted(buckets):
        rows = buckets[name]
        wins = sum(1 for r in rows if r.get("exit_outcome") == "WIN_EXIT" or r.get("path_true") is True)
        n = len(rows)
        xs = [float(r["return_cents"]) for r in rows if r.get("return_cents") is not None]
        seasons.append(
            {
                "season": name,
                "n": n,
                "win": rate(wins, n),
                "wilson": wilson_interval(wins, n) if n else None,
                "returns": return_distribution(xs) if xs else None,
            }
        )
    return {
        "status": OBSERVED,
        "label": "CROSS-SEASON · not silently pooled",
        "seasons": seasons,
    }


def adjacent_entry_buckets(obs: list[dict[str, Any]], *, width: int = 5) -> dict[str, Any]:
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in obs:
        cents = e4_to_cents(r.get("entry_price_e4"))
        if cents is None:
            continue
        lo = (cents // width) * width
        buckets[lo].append(r)
    if not buckets:
        return {"status": UNAVAILABLE, "reason": "No entry prices to bucket."}
    items = []
    for lo in sorted(buckets):
        rows = buckets[lo]
        wins = sum(1 for r in rows if r.get("exit_outcome") == "WIN_EXIT" or r.get("path_true") is True)
        n = len(rows)
        xs = [float(r["return_cents"]) for r in rows if r.get("return_cents") is not None]
        items.append(
            {
                "bucket": f"{lo}–{lo + width}¢",
                "lo_cents": lo,
                "hi_cents": lo + width,
                "n": n,
                "win": rate(wins, n),
                "wilson": wilson_interval(wins, n) if n else None,
                "returns": return_distribution(xs) if xs else None,
            }
        )
    return {
        "status": DERIVED,
        "label": "ADJACENT ENTRY-PRICE BUCKETS · not a discovered edge",
        "width_cents": width,
        "buckets": items,
        "multiple_testing": disclose(len(items), family="entry_price_buckets", method="disclosure_only"),
    }


def temporal_partitions(obs: list[dict[str, Any]]) -> dict[str, Any]:
    labeled = [r for r in obs if r.get("sample_partition") in ("TRAIN", "VALIDATION", "OOS")]
    if not labeled:
        return {
            "status": UNAVAILABLE,
            "reason": "No pre-specified sample_partition on rows. A median-date split is not invented.",
        }
    out = {}
    for name in ("TRAIN", "VALIDATION", "OOS"):
        rows = [r for r in labeled if r.get("sample_partition") == name]
        if not rows:
            out[name] = {"status": UNAVAILABLE, "n": 0}
            continue
        wins = sum(1 for r in rows if r.get("exit_outcome") == "WIN_EXIT" or r.get("path_true") is True)
        xs = [float(r["return_cents"]) for r in rows if r.get("return_cents") is not None]
        out[name] = {
            "status": OBSERVED,
            "n": len(rows),
            "win": rate(wins, len(rows)),
            "wilson": wilson_interval(wins, len(rows)),
            "returns": return_distribution(xs) if xs else None,
        }
    return {"status": OBSERVED, "label": "TEMPORAL REPLICATION · pre-specified partitions only", "partitions": out}


def holding_time_stats(seconds: list[int] | list[float]) -> dict[str, Any]:
    if not seconds:
        return {"status": UNAVAILABLE, "reason": "Need >= 1 exit timestamp. No exact exit−entry timestamps."}
    vals = [float(s) for s in seconds]
    return {
        "status": OBSERVED,
        "label": "HOLDING TIME · OBSERVED",
        "n": len(vals),
        "mean_seconds": mean(vals),
        "median_seconds": median(vals),
        "p5_seconds": quantile(vals, 0.05),
        "p25_seconds": quantile(vals, 0.25),
        "p75_seconds": quantile(vals, 0.75),
        "p90_seconds": quantile(vals, 0.90),
        "p95_seconds": quantile(vals, 0.95),
        "max_seconds": max(vals),
        "min_seconds": min(vals),
    }


HOLDING_EV_BOUNDS = (30, 60, 120, 300, 600)


def holding_time_ev_buckets(obs: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [
        r
        for r in obs
        if r.get("holding_seconds") is not None and r.get("return_cents") is not None
    ]
    if not usable:
        return {"status": UNAVAILABLE, "reason": "No exit timestamp. Holding-time EV buckets unavailable."}
    rows = []
    prev = 0
    for h in HOLDING_EV_BOUNDS:
        bucket = [r for r in usable if prev < int(r["holding_seconds"]) <= h]
        rows.append(_holding_bucket_row(f"≤{h}s" if prev == 0 else f"{prev}–{h}s", bucket, cumulative=[r for r in usable if int(r["holding_seconds"]) <= h], label_cum=f"≤{h}s"))
        prev = h
    tail = [r for r in usable if int(r["holding_seconds"]) > HOLDING_EV_BOUNDS[-1]]
    rows.append(_holding_bucket_row(f">{HOLDING_EV_BOUNDS[-1]}s", tail, cumulative=None, label_cum=None))
    return {
        "status": OBSERVED,
        "label": "EMPIRICAL TIME-TO-EXIT ECONOMICS · not a predictive probability · not ranked",
        "buckets": rows,
    }


def _holding_bucket_row(
    name: str,
    rows: list[dict[str, Any]],
    *,
    cumulative: list[dict[str, Any]] | None,
    label_cum: str | None,
) -> dict[str, Any]:
    xs = [float(r["return_cents"]) for r in rows]
    wins = sum(1 for r in rows if r.get("exit_outcome") == "WIN_EXIT" or r.get("path_true") is True)
    losses = sum(1 for r in rows if r.get("exit_outcome") == "LOSS_EXIT" or r.get("path_true") is False)
    holds = [int(r["holding_seconds"]) for r in rows]
    out: dict[str, Any] = {
        "bucket": name,
        "n": len(rows),
        "mean_return_cents": mean(xs) if xs else None,
        "median_return_cents": median(xs) if xs else None,
        "win_n": wins,
        "loss_n": losses,
        "mean_holding_seconds": mean(holds) if holds else None,
    }
    if cumulative is not None and label_cum:
        cxs = [float(r["return_cents"]) for r in cumulative]
        out["cumulative"] = {
            "bucket": label_cum,
            "n": len(cumulative),
            "mean_return_cents": mean(cxs) if cxs else None,
        }
    return out


def time_to_event(seconds: list[int], n_population: int) -> dict[str, Any]:
    if not seconds:
        return {"status": UNAVAILABLE, "reason": "Insufficient timestamp support."}
    horizons = (30, 60, 120, 300, 600)
    rows = []
    for h in horizons:
        k = sum(1 for s in seconds if s <= h)
        rows.append({"horizon_seconds": h, "events": k, "n_with_exit": len(seconds), "incidence": k / len(seconds)})
    return {
        "status": OBSERVED,
        "label": "EMPIRICAL TIME-TO-EVENT · not a predictive probability",
        "n_with_holding_time": len(seconds),
        "n_population": n_population,
        "horizons": rows,
    }


def excursion(obs: list[dict[str, Any]]) -> dict[str, Any]:
    maes = [int(r["mae_cents"]) for r in obs if r.get("mae_cents") is not None]
    mfes = [int(r["mfe_cents"]) for r in obs if r.get("mfe_cents") is not None]
    if not maes and not mfes:
        return {
            "status": UNAVAILABLE,
            "reason": "MAE/MFE not attached on rows. Not invented from missing later bars.",
        }
    def _side(outcome: str) -> dict[str, Any]:
        side_mae = [int(r["mae_cents"]) for r in obs if r.get("mae_cents") is not None and r.get("exit_outcome") == outcome]
        side_mfe = [int(r["mfe_cents"]) for r in obs if r.get("mfe_cents") is not None and r.get("exit_outcome") == outcome]
        if len(side_mae) < 2 and len(side_mfe) < 2:
            return {"status": UNAVAILABLE, "reason": "Insufficient denominator for conditional MAE/MFE."}
        return {
            "status": OBSERVED,
            "mae": {
                "n": len(side_mae),
                "mean_cents": mean(side_mae) if side_mae else None,
                "median_cents": median(side_mae) if side_mae else None,
            },
            "mfe": {
                "n": len(side_mfe),
                "mean_cents": mean(side_mfe) if side_mfe else None,
                "median_cents": median(side_mfe) if side_mfe else None,
            },
        }

    return {
        "status": OBSERVED,
        "label": "MAE / MFE · later bars after entry · historical movement, not risk",
        "mae": {
            "n": len(maes),
            "mean_cents": mean(maes) if maes else None,
            "median_cents": median(maes) if maes else None,
            "p5_cents": quantile(maes, 0.05) if maes else None,
            "min_cents": min(maes) if maes else None,
        },
        "mfe": {
            "n": len(mfes),
            "mean_cents": mean(mfes) if mfes else None,
            "median_cents": median(mfes) if mfes else None,
            "p95_cents": quantile(mfes, 0.95) if mfes else None,
            "max_cents": max(mfes) if mfes else None,
        },
        "win": _side("WIN_EXIT"),
        "loss": _side("LOSS_EXIT"),
    }
