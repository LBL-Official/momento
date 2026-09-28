"""Endpoint, spread, and paired-path audit.

The frozen primary tables are not recomputed here. Every block is a
labeled sensitivity or a decomposition of the same complete sample.
"""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.sugarland.metrics import json_number, summarize_series

EXCLUSION_LABELS = (
    "ABSENT_CANDLES",
    "STALE_OBSERVATION",
    "BOUNDARY_QUOTE",
    "EXCESSIVE_SPREAD",
    "CLOCK_PROBLEM",
    "OTHER_EXCLUSION",
)

AUDIT_LABEL = "ENDPOINT_SPREAD_AUDIT"
BOUNDARY_LABEL = "BOUNDARY_BID_ARITHMETIC_SENSITIVITY"
PAIRED_LABEL = "PAIRED_48H_PRICE_ONLY"


def _cents(exit_bid: int, entry_bid: int, entry_ask: int) -> dict[str, float]:
    appreciation = (exit_bid - entry_bid) / 100.0
    spread = (entry_ask - entry_bid) / 100.0
    profit = (exit_bid - entry_ask) / 100.0
    return {
        "bid_appreciation_cents": appreciation,
        "entry_spread_cents": spread,
        "quote_profit_cents": profit,
    }


def _series_cell(summary: dict[str, Any]) -> dict[str, Any]:
    if summary["interval_status"] == "INSUFFICIENT_SAMPLE":
        low = high = "INSUFFICIENT_SAMPLE"
    else:
        low = json_number(summary["ci95_low"])
        high = json_number(summary["ci95_high"])
    return {
        "n": summary["n"],
        "mean_cents": json_number(summary["mean"]),
        "median_cents": json_number(summary["median"]),
        "share_positive": json_number(summary["share_positive"]),
        "ci95_low": low,
        "ci95_high": high,
        "interval_status": summary["interval_status"],
    }


def _around(contracts: list[dict[str, Any]], sport: str, hours: int) -> list[dict[str, Any]]:
    flag = f"h{hours}_around80"
    return [
        row
        for row in contracts
        if row.get("sport") == sport and not row.get("quarantine") and row.get(flag)
    ]


def spread_terms(rows: list[dict[str, Any]], hours: int) -> dict[str, Any]:
    """Three cent terms on the primary complete endpoint sample."""
    complete = []
    for row in rows:
        entry_bid = row.get(f"h{hours}_bid_e4")
        entry_ask = row.get(f"h{hours}_ask_e4")
        exit_bid = row.get("p30_bid_e4")
        if entry_bid is None or entry_ask is None or exit_bid is None:
            continue
        terms = _cents(int(exit_bid), int(entry_bid), int(entry_ask))
        terms["game_date"] = row.get("game_date")
        complete.append(terms)
    identity_gap = 0.0
    for row in complete:
        gap = row["quote_profit_cents"] - (row["bid_appreciation_cents"] - row["entry_spread_cents"])
        identity_gap = max(identity_gap, abs(gap))
    return {
        "label": "PRIMARY_COMPLETE_SAMPLE",
        "eligible_n": len(rows),
        "complete_n": len(complete),
        "identity_max_abs_cents": identity_gap,
        "bid_appreciation_cents": _series_cell(summarize_series(complete, "bid_appreciation_cents")),
        "entry_spread_cents": _series_cell(summarize_series(complete, "entry_spread_cents")),
        "quote_profit_cents": _series_cell(summarize_series(complete, "quote_profit_cents")),
    }


def _exclusion_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing = [row for row in rows if row.get("p30_bid_e4") is None]
    counts = {label: 0 for label in EXCLUSION_LABELS}
    boundary_candle_rows = 0
    for row in missing:
        label = str(row.get("endpoint_exclusion") or "OTHER_EXCLUSION")
        if label not in counts:
            label = "OTHER_EXCLUSION"
        counts[label] += 1
        if int(row.get("endpoint_window_boundary") or 0) > 0:
            boundary_candle_rows += 1
    return {
        "eligible_n": len(rows),
        "endpoint_n": len(rows) - len(missing),
        "missing_n": len(missing),
        "counts": counts,
        "missing_with_any_boundary_candle": boundary_candle_rows,
    }


def boundary_sensitivity(rows: list[dict[str, Any]], hours: int) -> dict[str, Any]:
    """Primary endpoints plus boundary bid marks the frozen rule drops.

    Log-odds stay unavailable when the retained bid is 0 or 10000.
    """
    kept = []
    added = 0
    log_odds_unavailable = 0
    for row in rows:
        entry_bid = row.get(f"h{hours}_bid_e4")
        entry_ask = row.get(f"h{hours}_ask_e4")
        if entry_bid is None or entry_ask is None:
            continue
        source = "PRIMARY"
        exit_bid = row.get("p30_bid_e4")
        if exit_bid is None:
            exit_bid = row.get("boundary_p30_bid_e4")
            source = "BOUNDARY_BID_ARITHMETIC"
        if exit_bid is None:
            continue
        if source != "PRIMARY":
            added += 1
        if not (0 < int(exit_bid) < 10000):
            log_odds_unavailable += 1
        terms = _cents(int(exit_bid), int(entry_bid), int(entry_ask))
        terms["game_date"] = row.get("game_date")
        terms["source"] = source
        kept.append(terms)
    return {
        "label": BOUNDARY_LABEL,
        "eligible_n": len(rows),
        "endpoint_n": len(kept),
        "added_boundary_n": added,
        "log_odds_unavailable_n": log_odds_unavailable,
        "log_odds_role": "UNAVAILABLE_WHEN_BID_IS_0_OR_10000",
        "bid_appreciation_cents": _series_cell(summarize_series(kept, "bid_appreciation_cents")),
        "entry_spread_cents": _series_cell(summarize_series(kept, "entry_spread_cents")),
        "quote_profit_cents": _series_cell(summarize_series(kept, "quote_profit_cents")),
    }


def paired_from_48h(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """48h around-80 contracts that also have a primary 24h quote and a primary T−30 bid.

    The 24h price is not required to stay in the around-80 band.
    """
    paired = []
    missing_24h = 0
    missing_endpoint = 0
    left_band_at_24h = 0
    for row in rows:
        bid48 = row.get("h48_bid_e4")
        bid24 = row.get("h24_bid_e4")
        bid30 = row.get("p30_bid_e4")
        if bid48 is None:
            continue
        if bid24 is None or bid30 is None:
            if bid24 is None:
                missing_24h += 1
            if bid30 is None:
                missing_endpoint += 1
            continue
        if not row.get("h24_around80"):
            left_band_at_24h += 1
        paired.append(
            {
                "game_date": row.get("game_date"),
                "cents_48_to_24": (int(bid24) - int(bid48)) / 100.0,
                "cents_24_to_30": (int(bid30) - int(bid24)) / 100.0,
                "cents_48_to_30": (int(bid30) - int(bid48)) / 100.0,
            }
        )
    return {
        "label": PAIRED_LABEL,
        "selection": "48h around-80 bid only",
        "eligible_48h_n": len(rows),
        "paired_n": len(paired),
        "dropped_missing_24h": missing_24h,
        "dropped_missing_endpoint": missing_endpoint,
        "still_outside_around80_at_24h": left_band_at_24h,
        "cents_48_to_24": _series_cell(summarize_series(paired, "cents_48_to_24")),
        "cents_24_to_30": _series_cell(summarize_series(paired, "cents_24_to_30")),
        "cents_48_to_30": _series_cell(summarize_series(paired, "cents_48_to_30")),
    }


def build_audit(contracts: list[dict[str, Any]], sports: tuple[str, ...]) -> dict[str, Any]:
    blocks = []
    for sport in sports:
        for hours in (48, 24):
            members = _around(contracts, sport, hours)
            blocks.append(
                {
                    "sport": sport,
                    "horizon_h": hours,
                    "cohort": "AROUND_80_78_82",
                    "exclusions": _exclusion_counts(members),
                    "spread_cents": spread_terms(members, hours),
                    "boundary_sensitivity": boundary_sensitivity(members, hours),
                }
            )
        members_48 = _around(contracts, sport, 48)
        blocks.append(
            {
                "sport": sport,
                "horizon_h": 48,
                "cohort": PAIRED_LABEL,
                "paired": paired_from_48h(members_48),
            }
        )
    return {"label": AUDIT_LABEL, "primary_tables_unchanged": True, "blocks": blocks}


def _cent_phrase(cell: dict[str, Any]) -> str:
    interval = cell.get("interval_status")
    if interval == "INSUFFICIENT_SAMPLE":
        band = "INSUFFICIENT_SAMPLE"
    elif cell.get("n") == 0:
        band = "UNAVAILABLE"
    else:
        band = f"[{_num(cell.get('ci95_low'))}, {_num(cell.get('ci95_high'))}]"
    mean = cell.get("mean_cents")
    if not isinstance(mean, float):
        return f"{mean} (N {cell.get('n')})"
    return f"{mean:.4f}¢ (N {cell.get('n')}, 95% {band})"


def audit_lines(audit: dict[str, Any] | None) -> list[str]:
    if not audit:
        return []
    lines = [
        "",
        "## Endpoint and spread audit",
        "",
        "This section does not replace the frozen primary tables. "
        "Quote-based cents per contract are `b30 − a0`. "
        "That equals bid appreciation `b30 − b0` minus entry spread `a0 − b0`, on the same complete endpoint sample.",
        "",
        "### Spread-adjusted cents",
        "",
        "| Sport | Horizon | Complete N | Mean bid change ¢ | Mean entry spread ¢ | Mean quote profit ¢ | Profit 95% interval |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for block in audit.get("blocks") or []:
        spread = block.get("spread_cents")
        if not spread:
            continue
        profit = spread["quote_profit_cents"]
        if profit.get("interval_status") == "INSUFFICIENT_SAMPLE":
            interval = "INSUFFICIENT_SAMPLE"
        elif profit.get("n") == 0:
            interval = "UNAVAILABLE"
        else:
            interval = f"[{_num(profit.get('ci95_low'))}, {_num(profit.get('ci95_high'))}]"
        lines.append(
            "| {sport} | {horizon} | {n} | {appr} | {spread} | {profit} | {interval} |".format(
                sport=block["sport"],
                horizon=block["horizon_h"],
                n=spread["complete_n"],
                appr=profit_mean(spread["bid_appreciation_cents"]),
                spread=profit_mean(spread["entry_spread_cents"]),
                profit=profit_mean(profit),
                interval=interval,
            )
        )
    lines.extend(
        [
            "",
            "### Missing endpoints",
            "",
            "Each missing primary endpoint has one label. A boundary candle is a two-sided mark inside the spread cap that the frozen rule drops because a side is 0 or 10000.",
            "",
            "| Sport | Horizon | Eligible | Endpoint | Missing | Absent | Stale | Boundary | Excessive spread | Clock | Other |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for block in audit.get("blocks") or []:
        exclusions = block.get("exclusions")
        if not exclusions:
            continue
        counts = exclusions["counts"]
        lines.append(
            "| {sport} | {horizon} | {eligible} | {endpoint} | {missing} | {absent} | {stale} | {boundary} | {wide} | {clock} | {other} |".format(
                sport=block["sport"],
                horizon=block["horizon_h"],
                eligible=exclusions["eligible_n"],
                endpoint=exclusions["endpoint_n"],
                missing=exclusions["missing_n"],
                absent=counts["ABSENT_CANDLES"],
                stale=counts["STALE_OBSERVATION"],
                boundary=counts["BOUNDARY_QUOTE"],
                wide=counts["EXCESSIVE_SPREAD"],
                clock=counts["CLOCK_PROBLEM"],
                other=counts["OTHER_EXCLUSION"],
            )
        )
    lines.extend(
        [
            "",
            "### Boundary-bid arithmetic sensitivity",
            "",
            "Label `BOUNDARY_BID_ARITHMETIC_SENSITIVITY`. Primary endpoints stay. "
            "Contracts whose only fresher mark is a boundary bid are added for cent arithmetic. "
            "Log-odds stay unavailable when that bid is 0 or 10000.",
            "",
        ]
    )
    for block in audit.get("blocks") or []:
        sens = block.get("boundary_sensitivity")
        if not sens:
            continue
        lines.append(
            f"- {block['sport']} {block['horizon_h']}h: added {sens['added_boundary_n']} boundary marks "
            f"(endpoint N {sens['endpoint_n']} of eligible {sens['eligible_n']}). "
            f"Mean bid change {_cent_phrase(sens['bid_appreciation_cents'])}. "
            f"Mean quote profit {_cent_phrase(sens['quote_profit_cents'])}. "
            f"Log-odds unavailable on {sens['log_odds_unavailable_n']} retained bids."
        )
    lines.extend(
        [
            "",
            "### Paired 48h → 24h → T−30",
            "",
            "Selection uses the 48h around-80 bid only. A contract that leaves that band by 24h stays in the pair. "
            "The separate 48h and 24h headline rows are different populations.",
            "",
            "| Sport | Paired N | Dropped missing 24h | Dropped missing T−30 | Left the band by 24h | 48h→24h ¢ | 24h→T−30 ¢ | 48h→T−30 ¢ |",
            "|---|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for block in audit.get("blocks") or []:
        paired = block.get("paired")
        if not paired:
            continue
        lines.append(
            "| {sport} | {n} | {m24} | {m30} | {left} | {a} | {b} | {c} |".format(
                sport=block["sport"],
                n=paired["paired_n"],
                m24=paired["dropped_missing_24h"],
                m30=paired["dropped_missing_endpoint"],
                left=paired["still_outside_around80_at_24h"],
                a=_cent_phrase(paired["cents_48_to_24"]),
                b=_cent_phrase(paired["cents_24_to_30"]),
                c=_cent_phrase(paired["cents_48_to_30"]),
            )
        )
    lines.append("")
    return lines


def _num(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def profit_mean(cell: dict[str, Any]) -> str:
    mean = cell.get("mean_cents")
    if isinstance(mean, float):
        return f"{mean:.4f}"
    return str(mean)
