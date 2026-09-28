"""Headline tables. Numbers come from contract rows, never from a handwritten result."""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.sugarland.audit import audit_lines
from roller.choosin_texas.sugarland.metrics import json_number, summarize_dpp, without_largest_gain


def _cell(summary: dict[str, Any], *, discovery: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "eligible_n": summary["eligible_n"],
        "endpoint_n": summary["endpoint_n"],
        "mean_dpp": json_number(summary["mean_dpp"]),
        "median_dpp": json_number(summary["median_dpp"]),
        "sd_dpp": json_number(summary["sd_dpp"]),
        "q10": json_number(summary["q10"]),
        "q25": json_number(summary["q25"]),
        "q75": json_number(summary["q75"]),
        "q90": json_number(summary["q90"]),
        "share_rising": json_number(summary["share_rising"]),
        "share_unchanged": json_number(summary["share_unchanged"]),
        "share_falling": json_number(summary["share_falling"]),
        "ci95_low": _interval_bound(summary, "ci95_low"),
        "ci95_high": _interval_bound(summary, "ci95_high"),
        "mean_return_on_ask": json_number(summary["mean_return_on_ask"]),
        "share_gross_positive": json_number(summary["share_gross_positive"]),
        "discovery_mean_dpp": json_number(discovery["mean_dpp"]),
        "discovery_endpoint_n": discovery["endpoint_n"],
        "validation_mean_dpp": json_number(validation["mean_dpp"]),
        "validation_endpoint_n": validation["endpoint_n"],
        "status": summary["status"],
    }


def _interval_bound(summary: dict[str, Any], key: str) -> Any:
    if summary.get("endpoint_n") == 1:
        return "INSUFFICIENT_SAMPLE"
    return json_number(summary.get(key))


def _pack(rows: list[dict[str, Any]], *, dpp_key: str = "dpp", ask_key: str = "return_on_ask", gross_key: str = "gross_positive") -> list[dict[str, Any]]:
    packed = []
    for row in rows:
        packed.append(
            {
                "game_date": row.get("game_date"),
                "dpp": row.get(dpp_key),
                "return_on_ask": row.get(ask_key),
                "gross_positive": row.get(gross_key),
                "partition": row.get("partition"),
            }
        )
    return packed


def headline_for(rows: list[dict[str, Any]], *, dpp_key: str = "dpp", ask_key: str = "return_on_ask", gross_key: str = "gross_positive") -> dict[str, Any]:
    mapped = []
    for row in rows:
        cloned = dict(row)
        cloned["dpp"] = row.get(dpp_key)
        cloned["return_on_ask"] = row.get(ask_key)
        cloned["gross_positive"] = row.get(gross_key)
        mapped.append(cloned)
    packed = _pack(mapped)
    all_rows = summarize_dpp(packed)
    discovery = summarize_dpp([row for row in packed if row["partition"] == "discovery"])
    validation = summarize_dpp([row for row in packed if row["partition"] == "validation"])
    cell = _cell(all_rows, discovery=discovery, validation=validation)
    trimmed = summarize_dpp(_pack(without_largest_gain(mapped)))
    cell["mean_dpp_without_largest_gain"] = json_number(trimmed["mean_dpp"])
    cell["endpoint_n_without_largest_gain"] = trimmed["endpoint_n"]
    return cell


def cohort_a(contracts: list[dict[str, Any]], sport: str) -> list[dict[str, Any]]:
    return [row for row in contracts if row.get("sport") == sport and row.get("in_a")]


def horizon_members(contracts: list[dict[str, Any]], sport: str, hours: int, *, around: bool) -> list[dict[str, Any]]:
    flag = f"h{hours}_around80" if around else f"h{hours}_above70"
    chosen = []
    for row in contracts:
        if row.get("sport") != sport or row.get("quarantine"):
            continue
        if not row.get(flag):
            continue
        chosen.append(row)
    return chosen


def union_around(contracts: list[dict[str, Any]], sport: str) -> list[dict[str, Any]]:
    """One row per ticker. Prefer the 48h snapshot when it is in the around-80 band."""
    chosen = []
    for row in contracts:
        if row.get("sport") != sport or row.get("quarantine"):
            continue
        if row.get("h48_around80"):
            hours = 48
        elif row.get("h24_around80"):
            hours = 24
        else:
            continue
        cloned = dict(row)
        cloned["union_horizon_h"] = hours
        cloned["dpp"] = row.get(f"h{hours}_dpp")
        cloned["return_on_ask"] = row.get(f"h{hours}_return_on_ask")
        cloned["gross_positive"] = row.get(f"h{hours}_gross_positive")
        chosen.append(cloned)
    return chosen


def sport_tables(contracts: list[dict[str, Any]], sports: tuple[str, ...]) -> dict[str, Any]:
    headline = []
    around = []
    for sport in sports:
        members = cohort_a(contracts, sport)
        cell = headline_for(members)
        cell["sport"] = sport
        cell["cohort"] = "FIRST_OBSERVED_ABOVE_70"
        headline.append(cell)
        for hours in (48, 24):
            block = headline_for(
                horizon_members(contracts, sport, hours, around=True),
                dpp_key=f"h{hours}_dpp",
                ask_key=f"h{hours}_return_on_ask",
                gross_key=f"h{hours}_gross_positive",
            )
            block["sport"] = sport
            block["cohort"] = "AROUND_80_78_82"
            block["horizon_h"] = hours
            around.append(block)
        union = headline_for(union_around(contracts, sport))
        union["sport"] = sport
        union["cohort"] = "AROUND_80_UNION_PREFER_48H"
        union["horizon_h"] = "48_else_24"
        around.append(union)
    return {"headline_first_observed_above_70": headline, "around_80": around}


def fmt(value: Any) -> str:
    if value is None or value == "UNAVAILABLE":
        return "UNAVAILABLE"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def findings_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Sugarland findings",
        "",
        f"Universe `{payload['universe_id']}`. Spec `{payload['spec_sha256']}`.",
        "",
        "Research only. Execution disabled. Quote differences are not fills.",
        "",
        "## First result — around 80¢ at 24h and 48h",
        "",
        "Same contract, bid at the frozen horizon versus the bid at T−30. "
        "Return on entry ask is the quote-based spread comparison (exit bid minus entry ask, divided by entry ask). "
        "It is not an executable return.",
        "",
        "| Sport | Horizon | Eligible N | Endpoint N | Mean Δpp | Median Δpp | 95% interval | Share rising | Return on entry ask | Discovery mean (N) | Validation mean (N) |",
        "|---|---|---:|---:|---:|---:|---|---:|---:|---|---|",
    ]
    for row in payload["tables"]["around_80"]:
        if row["cohort"] == "AROUND_80_UNION_PREFER_48H":
            horizon = "union 48h else 24h"
        else:
            horizon = f"{row['horizon_h']}h"
        if row["ci95_low"] == "INSUFFICIENT_SAMPLE":
            interval = "INSUFFICIENT_SAMPLE"
        else:
            interval = f"[{fmt(row['ci95_low'])}, {fmt(row['ci95_high'])}]"
        lines.append(
            "| {sport} | {horizon} | {eligible_n} | {endpoint_n} | {mean} | {median} | {interval} | {rising} | {ask} | {disc} ({dn}) | {val} ({vn}) |".format(
                sport=row["sport"],
                horizon=horizon,
                eligible_n=row["eligible_n"],
                endpoint_n=row["endpoint_n"],
                mean=fmt(row["mean_dpp"]),
                median=fmt(row["median_dpp"]),
                interval=interval,
                rising=fmt(row["share_rising"]),
                ask=fmt(row["mean_return_on_ask"]),
                disc=fmt(row["discovery_mean_dpp"]),
                dn=row["discovery_endpoint_n"],
                val=fmt(row["validation_mean_dpp"]),
                vn=row["validation_endpoint_n"],
            )
        )
    lines.extend(
        [
            "",
            "Return on entry ask divides each contract by its own entry ask. "
            "Whether appreciation exceeded the spread is the unweighted cent comparison in the audit below, "
            "on the same complete endpoint sample.",
            "",
            "A one-contract interval is labeled INSUFFICIENT_SAMPLE. It is not a confidence interval.",
            "",
            "## Cohort A — first observed above 70¢",
            "",
            "Membership uses the first valid pregame quote only. A later crossing of 70¢ does not enter.",
            "",
            "| Sport | Eligible N | Endpoint N | Mean Δpp | Median Δpp | 95% interval | Share rising | Return on entry ask | Discovery mean (N) | Validation mean (N) |",
            "|---|---:|---:|---:|---:|---|---:|---:|---|---|",
        ]
    )
    for row in payload["tables"]["headline_first_observed_above_70"]:
        if row["ci95_low"] == "INSUFFICIENT_SAMPLE":
            interval = "INSUFFICIENT_SAMPLE"
        else:
            interval = f"[{fmt(row['ci95_low'])}, {fmt(row['ci95_high'])}]"
        lines.append(
            "| {sport} | {eligible_n} | {endpoint_n} | {mean} | {median} | {interval} | {rising} | {ask} | {disc} ({dn}) | {val} ({vn}) |".format(
                sport=row["sport"],
                eligible_n=row["eligible_n"],
                endpoint_n=row["endpoint_n"],
                mean=fmt(row["mean_dpp"]),
                median=fmt(row["median_dpp"]),
                interval=interval,
                rising=fmt(row["share_rising"]),
                ask=fmt(row["mean_return_on_ask"]),
                disc=fmt(row["discovery_mean_dpp"]),
                dn=row["discovery_endpoint_n"],
                val=fmt(row["validation_mean_dpp"]),
                vn=row["validation_endpoint_n"],
            )
        )
    lines.extend(["", "## Did the bid usually rise?", ""])
    for row in payload["tables"]["around_80"]:
        if row["cohort"] == "AROUND_80_UNION_PREFER_48H":
            continue
        horizon = row.get("horizon_h")
        rising = row["share_rising"]
        dpp = row["mean_dpp"]
        if row["endpoint_n"] == 0 or dpp == "UNAVAILABLE":
            lines.append(
                f"- {row['sport']} at {horizon}h: endpoint N is 0. The fresh around-80 quote at that horizon is UNAVAILABLE. That is not a zero return."
            )
            continue
        if row["endpoint_n"] < 2:
            lines.append(
                f"- {row['sport']} at {horizon}h: endpoint N is {row['endpoint_n']}. "
                "The interval is INSUFFICIENT_SAMPLE."
            )
            continue
        if isinstance(rising, (int, float)) and rising > 0.5:
            rose = "A majority of endpoint contracts rose."
        elif isinstance(rising, (int, float)) and rising == 0.5:
            rose = "Half of endpoint contracts rose."
        else:
            rose = "Fewer than half of endpoint contracts rose."
        lines.append(
            f"- {row['sport']} at {horizon}h: mean bid change {fmt(dpp)}¢ on endpoint N {row['endpoint_n']} "
            f"(eligible {row['eligible_n']}), share rising {fmt(rising)}. {rose}"
        )
    lines.extend(audit_lines(payload.get("audit")))
    conc = payload.get("concentration") or {}
    if conc:
        lines.extend(["", "## Concentration of positive cohort-A bid changes", ""])
        for sport, item in conc.items():
            lines.append(
                f"- {sport}: top 10 positive contracts account for {fmt(item.get('top10_share_of_positive_dpp'))} "
                f"of the summed positive Δpp (positive N {item.get('positive_n')})."
            )
    lines.extend(
        [
            "",
            "## What this does not show",
            "",
            "- Listing time is UNAVAILABLE. First observed is not the market open.",
            "- Stored scheduled start is a sensitivity. It is not an entry-time snapshot, including when it matches actual start.",
            "- The quote-based benchmark has no depth, latency, or fill. Estimated fees are a separate labeled layer and are not in the tables above.",
            "- WNBA ledger fees are UNAVAILABLE. Realized P&L is reported only with exit linkage and settlement evidence. Otherwise the ledger section is confirmed acquisition cost plus a hypothetical valuation.",
            "- Lead time from the primary clock is descriptive. It is not an entry-time feature.",
            "- Injury, lineup, and pitching timestamps were not used. If that feed is absent, the price path is unexplained.",
            "- MLB uses FIRST_PBP_EVENT when a play timestamp exists. That is not a schedule snapshot. Games without a clock stay UNMEASURABLE.",
            "- NCAAB cohort N is the canonical candle subset. Phase 8 parquet counts are inventory only.",
            "- Dashboard `#/sugarland` shows NBA and NCAAB. WNBA and MLB are in this file and are not that dashboard.",
            "",
            "A null or negative bid change is a completed result.",
            "",
        ]
    )
    return "\n".join(lines)
