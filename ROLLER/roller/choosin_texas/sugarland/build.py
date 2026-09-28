"""Batch Sugarland build. Refuses summaries until SPEC.sha256 matches SPEC.md."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.choosin_texas.sugarland.accum import TickerState
from roller.choosin_texas.sugarland.associate import fit_association
from roller.choosin_texas.sugarland.clocks import classify_stored_schedule
from roller.choosin_texas.sugarland.constants import UNIVERSE_ID
from roller.choosin_texas.sugarland.quotes import epoch, parse_e4, parse_ts
from roller.choosin_texas.sugarland.audit import build_audit
from roller.choosin_texas.sugarland.report import findings_markdown, sport_tables
from roller.choosin_texas.sugarland.trades import aggregate_positions, load_wnba_fills

SPORT_ROOTS = (
    ("WNBA", "wnba/2025"),
    ("WNBA", "wnba/2026"),
    ("NBA", "nba/2025_2026"),
    ("NCAAB", "ncaab/2025_2026"),
    ("MLB", "mlb/2025_2026"),
)
DASHBOARD_SPORTS = ("NBA", "NCAAB")


def momento_root() -> Path:
    return Path(__file__).resolve().parents[4]


def artifact_dir() -> Path:
    return momento_root() / "research" / "sugarland" / "v1"


def spec_digest() -> str:
    return hashlib.sha256((artifact_dir() / "SPEC.md").read_bytes()).hexdigest()


def require_locked_spec() -> str:
    digest = spec_digest()
    lock = artifact_dir() / "SPEC.sha256"
    recorded = lock.read_text().strip() if lock.is_file() else ""
    if recorded != digest:
        raise RuntimeError("SPEC.sha256 does not match SPEC.md; refuse to emit summaries")
    return digest


@dataclass
class GameRec:
    game_id: str
    sport: str
    season: str
    game_date: str
    event_ticker: str
    t_start: int | None
    t_end: int | None
    t_end_sched: int | None
    clock_label: str
    quarantine: str
    schedule_relation: str
    partition: str = ""
    tickers: list[str] = field(default_factory=list)


def _read_manifest(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def _first_pbp(pbp_dir: Path) -> dict[str, datetime]:
    best: dict[str, datetime] = {}
    if not pbp_dir.is_dir():
        return best
    for path in sorted(pbp_dir.glob("month=*.csv")):
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                gid = row.get("internal_game_id") or ""
                raw = row.get("event_timestamp") or ""
                if raw.endswith("T00:00:00Z"):
                    continue
                ts = parse_ts(raw)
                if not gid or ts is None:
                    continue
                prev = best.get(gid)
                if prev is None or ts < prev:
                    best[gid] = ts
    return best


def _settlement(row: dict[str, str]) -> int | None:
    raw = parse_e4(row.get("settlement_value_e4"))
    if raw in (0, 10000):
        return raw
    result = (row.get("result") or "").strip().lower()
    if result == "yes":
        return 10000
    if result == "no":
        return 0
    return None


def _load_sport(root: Path, sport: str, rel: str, pbp_first: dict[str, datetime]) -> tuple[dict[str, GameRec], dict[str, dict[str, Any]], set[str]]:
    base = root / "ROLLER" / "data" / rel / "canonical"
    games: dict[str, GameRec] = {}
    games_path = base / "games.csv"
    if not games_path.is_file():
        return games, {}, set()
    with games_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            gid = row.get("internal_game_id") or ""
            if not gid:
                continue
            scheduled = parse_ts(row.get("scheduled_start"))
            actual = parse_ts(row.get("actual_start"))
            quarantine = ""
            t_end_sched = None if scheduled is None else epoch(scheduled) - 1800
            if sport == "MLB" and actual is None:
                pbp = pbp_first.get(gid)
                if pbp is None:
                    games[gid] = GameRec(
                        gid,
                        sport,
                        row.get("season") or "",
                        (row.get("game_date") or "")[:10],
                        row.get("event_ticker") or "",
                        None,
                        None,
                        None,
                        "UNMEASURABLE",
                        "",
                        "NO_START_CLOCK",
                    )
                    continue
                start = epoch(pbp)
                games[gid] = GameRec(
                    gid,
                    sport,
                    row.get("season") or "",
                    (row.get("game_date") or "")[:10],
                    row.get("event_ticker") or "",
                    start,
                    None if start is None else start - 1800,
                    None,
                    "FIRST_PBP_EVENT",
                    "",
                    "NO_STORED_SCHEDULE",
                )
                continue
            info = classify_stored_schedule(scheduled, actual)
            quarantine = info["quarantine"]
            if actual is None:
                games[gid] = GameRec(
                    gid,
                    sport,
                    row.get("season") or "",
                    (row.get("game_date") or "")[:10],
                    row.get("event_ticker") or "",
                    None,
                    None,
                    t_end_sched if isinstance(t_end_sched, int) else None,
                    "NO_ACTUAL_START",
                    quarantine,
                    info["schedule_relation"],
                )
                continue
            start = epoch(actual)
            assert start is not None
            games[gid] = GameRec(
                gid,
                sport,
                row.get("season") or "",
                (row.get("game_date") or "")[:10],
                row.get("event_ticker") or "",
                start,
                start - 1800,
                t_end_sched if isinstance(t_end_sched, int) else None,
                info["primary_role"],
                quarantine,
                info["schedule_relation"],
            )
    by_event: dict[str, list[GameRec]] = defaultdict(list)
    for game in games.values():
        if game.event_ticker:
            by_event[game.event_ticker].append(game)
    for group in by_event.values():
        if len({item.game_id for item in group}) > 1:
            for item in group:
                item.quarantine = item.quarantine or "AMBIGUOUS_MAP"

    markets: dict[str, dict[str, Any]] = {}
    ambiguous: set[str] = set()
    markets_path = base / "kalshi_markets.csv"
    if markets_path.is_file():
        with markets_path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                ticker = row.get("ticker") or ""
                gid = row.get("internal_game_id") or ""
                if not ticker or not gid:
                    continue
                prior = markets.get(ticker)
                if prior is not None and prior["game_id"] != gid:
                    ambiguous.add(ticker)
                    continue
                markets[ticker] = {
                    "game_id": gid,
                    "team_side": row.get("team_side") or "",
                    "result": row.get("result") or "",
                    "settlement_e4": _settlement(row),
                }
    for ticker in ambiguous:
        markets.pop(ticker, None)
    return games, markets, ambiguous


def _assign_partitions(games: dict[str, GameRec]) -> None:
    dates: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    for game in games.values():
        if game.t_start is None or not game.game_date or game.quarantine:
            continue
        if game.game_date not in seen[game.sport]:
            seen[game.sport].add(game.game_date)
            dates[game.sport].append(game.game_date)
    medians: dict[str, str] = {}
    for sport, values in dates.items():
        ordered = sorted(values)
        medians[sport] = ordered[(len(ordered) - 1) // 2]
    for game in games.values():
        median = medians.get(game.sport)
        if not median or not game.game_date:
            game.partition = ""
        elif game.game_date <= median:
            game.partition = "discovery"
        else:
            game.partition = "validation"


def _scan_candles(
    candle_dir: Path,
    games: dict[str, GameRec],
    markets: dict[str, dict[str, Any]],
    ambiguous: set[str],
    states: dict[str, TickerState],
    coverage: dict[str, int],
) -> None:
    if not candle_dir.is_dir():
        return
    for path in sorted(candle_dir.glob("month=*.csv")):
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                coverage["candle_rows"] += 1
                if coverage["candle_rows"] % 1_000_000 == 0:
                    print(f"sugarland candles {coverage['candle_rows']}", flush=True)
                ticker = row.get("ticker") or ""
                if not ticker:
                    continue
                if ticker in states:
                    state = states[ticker]
                    if state.t_start <= 0:
                        continue
                    _consume_row(state, row)
                    continue
                market = markets.get(ticker)
                gid = (market or {}).get("game_id") or row.get("internal_game_id") or ""
                game = games.get(gid)
                if game is None or game.t_start is None or game.t_end is None:
                    coverage["rows_without_clock"] += 1
                    continue
                if row.get("internal_game_id") and market and row["internal_game_id"] != market["game_id"]:
                    ambiguous.add(ticker)
                    continue
                quarantine = game.quarantine
                if ticker in ambiguous:
                    quarantine = quarantine or "AMBIGUOUS_MAP"
                side = (market or {}).get("team_side") or row.get("team_side") or ""
                state = TickerState(
                    ticker=ticker,
                    game_id=game.game_id,
                    sport=game.sport,
                    season=game.season,
                    team_side=side,
                    game_date=game.game_date,
                    clock_label=game.clock_label,
                    t_start=game.t_start,
                    t_end=game.t_end,
                    t_end_sched=game.t_end_sched,
                    quarantine=quarantine,
                    schedule_relation=game.schedule_relation,
                    partition=game.partition,
                    result=(market or {}).get("result") or "",
                    settlement_e4=(market or {}).get("settlement_e4"),
                )
                states[ticker] = state
                _consume_row(state, row)


def _consume_row(state: TickerState, row: dict[str, str]) -> None:
    ts = parse_ts(row.get("available_at"))
    if ts is None:
        return
    stamp = epoch(ts)
    if stamp is None:
        return
    state.consume(stamp, parse_e4(row.get("yes_bid_close")), parse_e4(row.get("yes_ask_close")), parse_e4(row.get("volume")))


def _coverage(games: dict[str, GameRec], contracts: list[dict[str, Any]], candle_rows: dict[str, int], manifests: dict[str, Any]) -> dict[str, Any]:
    by_sport: dict[str, Any] = {}
    sports = sorted({game.sport for game in games.values()})
    for sport in sports:
        sport_games = [game for game in games.values() if game.sport == sport]
        sport_rows = [row for row in contracts if row.get("sport") == sport]
        by_sport[sport] = {
            "games": len(sport_games),
            "games_with_primary_clock": sum(1 for game in sport_games if game.t_start is not None),
            "games_unmeasurable_clock": sum(1 for game in sport_games if game.clock_label in {"UNMEASURABLE", "NO_ACTUAL_START"}),
            "games_schedule_exception": sum(1 for game in sport_games if game.quarantine == "SCHEDULE_EXCEPTION"),
            "games_ambiguous_map": sum(1 for game in sport_games if game.quarantine == "AMBIGUOUS_MAP"),
            "games_utc_date_rollover": sum(1 for game in sport_games if game.schedule_relation == "UTC_DATE_ROLLOVER"),
            "games_stored_match_not_implementable": sum(
                1 for game in sport_games if game.schedule_relation == "STORED_MATCH_NOT_IMPLEMENTABLE"
            ),
            "tickers": len(sport_rows),
            "first_observed_above_70": sum(1 for row in sport_rows if row.get("in_a")),
            "missing_endpoint_above_70": sum(
                1 for row in sport_rows if row.get("in_a") and row.get("endpoint_status") == "MISSING_ENDPOINT"
            ),
            "pregame_first80_crossing": sum(1 for row in sport_rows if row.get("in_b")),
            "already_above_80_at_first_valid": sum(1 for row in sport_rows if row.get("already_above_80")),
            "listing_time": "UNAVAILABLE",
            "history_before_first_raw": "UNKNOWN",
        }
    return {
        "candle_rows": candle_rows["candle_rows"],
        "rows_without_clock": candle_rows["rows_without_clock"],
        "by_sport": by_sport,
        "parquet_inventory": manifests,
        "cohort_source": "canonical kalshi_candles CSV",
        "parquet_in_cohort_n": False,
    }


def _examples(contracts: list[dict[str, Any]], games: dict[str, GameRec]) -> dict[str, Any]:
    def brief(row: dict[str, Any], kind: str) -> dict[str, Any]:
        return {
            "kind": kind,
            "ticker": row.get("ticker"),
            "game_id": row.get("game_id"),
            "sport": row.get("sport"),
            "clock_label": row.get("clock_label"),
            "p0_bid_e4": row.get("p0_bid_e4"),
            "p0_ask_e4": row.get("p0_ask_e4"),
            "p30_bid_e4": row.get("p30_bid_e4"),
            "p0_ts": row.get("p0_ts"),
            "p30_ts": row.get("p30_ts"),
            "t_end": row.get("t_end"),
            "dpp_e4": row.get("dpp_e4"),
            "exclusion": row.get("exclusion"),
            "quarantine": row.get("quarantine"),
            "schedule_relation": row.get("schedule_relation"),
            "in_a": row.get("in_a"),
            "n_invalid_before_valid": row.get("n_invalid_before_valid"),
        }

    up = next((row for row in contracts if row.get("in_a") and isinstance(row.get("dpp_e4"), int) and row["dpp_e4"] > 0), None)
    down = next((row for row in contracts if row.get("in_a") and isinstance(row.get("dpp_e4"), int) and row["dpp_e4"] < 0), None)
    missing = next(
        (
            row
            for row in contracts
            if row.get("in_a") and row.get("endpoint_status") == "MISSING_ENDPOINT"
        ),
        None,
    )
    schedule = next((row for row in contracts if row.get("quarantine") == "SCHEDULE_EXCEPTION"), None)
    schedule_payload: dict[str, Any] | None
    if schedule is not None:
        schedule_payload = brief(schedule, "schedule_exception")
    else:
        missing_game = next((game for game in games.values() if game.clock_label == "UNMEASURABLE"), None)
        if missing_game is None:
            schedule_payload = None
        else:
            schedule_payload = {
                "kind": "mlb_or_start_missing",
                "ticker": None,
                "game_id": missing_game.game_id,
                "sport": missing_game.sport,
                "clock_label": missing_game.clock_label,
                "schedule_relation": missing_game.schedule_relation,
                "p0_bid_e4": None,
                "p30_bid_e4": None,
                "p0_ts": None,
                "p30_ts": None,
                "t_end": None,
                "dpp_e4": None,
                "reason": "scheduled_start and actual_start are blank, and no non-midnight PBP timestamp was found",
            }
    return {
        "appreciation": None if up is None else brief(up, "appreciation"),
        "depreciation": None if down is None else brief(down, "depreciation"),
        "missing_endpoint": None if missing is None else brief(missing, "missing_endpoint"),
        "schedule_exception": schedule_payload,
    }


def _page(
    contracts: list[dict[str, Any]],
    tables: dict[str, Any],
    coverage: dict[str, Any],
    digest: str,
    audit: dict[str, Any],
) -> dict[str, Any]:
    rows = []
    for row in contracts:
        if row.get("sport") not in DASHBOARD_SPORTS:
            continue
        if not (row.get("in_a") or row.get("in_b") or row.get("h48_bid_e4") is not None or row.get("h24_bid_e4") is not None):
            continue
        rows.append(
            {
                "ticker": row.get("ticker"),
                "sport": row.get("sport"),
                "season": row.get("season"),
                "game_date": row.get("game_date"),
                "partition": row.get("partition"),
                "band": row.get("band"),
                "lead_bucket": row.get("lead_bucket_descriptive"),
                "in_a": bool(row.get("in_a")),
                "in_b": bool(row.get("in_b")),
                "already_above_80": bool(row.get("already_above_80")),
                "endpoint": row.get("endpoint_status") == "OBSERVED",
                "dpp": None if row.get("dpp") is None else float(row["dpp"]),
                "return_on_ask": None if row.get("return_on_ask") is None else float(row["return_on_ask"]),
                "gross_dollars": None if row.get("gross_dollars") is None else float(row["gross_dollars"]),
                "h48_dpp": None if row.get("h48_dpp") is None else float(row["h48_dpp"]),
                "h24_dpp": None if row.get("h24_dpp") is None else float(row["h24_dpp"]),
                "h48_around80": bool(row.get("h48_around80")),
                "h24_around80": bool(row.get("h24_around80")),
                "h48_above70": bool(row.get("h48_above70")),
                "h24_above70": bool(row.get("h24_above70")),
                "h48_return_on_ask": None if row.get("h48_return_on_ask") is None else float(row["h48_return_on_ask"]),
                "h24_return_on_ask": None if row.get("h24_return_on_ask") is None else float(row["h24_return_on_ask"]),
                "slope_pp_per_hour": row.get("slope_pp_per_hour"),
                "slope_status": row.get("slope_status") or "UNAVAILABLE",
                "covered_hours": row.get("covered_hours"),
                "uncovered_hours": row.get("uncovered_hours"),
                "share_time_above": row.get("share_time_above"),
                "h48": None if row.get("h48_bid_e4") is None else row["h48_bid_e4"] / 10000,
                "h24": None if row.get("h24_bid_e4") is None else row["h24_bid_e4"] / 10000,
                "h12": None if row.get("h12_bid_e4") is None else row["h12_bid_e4"] / 10000,
                "h6": None if row.get("h6_bid_e4") is None else row["h6_bid_e4"] / 10000,
                "h2": None if row.get("h2_bid_e4") is None else row["h2_bid_e4"] / 10000,
                "h1": None if row.get("h1_bid_e4") is None else row["h1_bid_e4"] / 10000,
                "p30": None if row.get("p30_bid_e4") is None else row["p30_bid_e4"] / 10000,
                "exclusion": row.get("exclusion") or "",
            }
        )
    nba_ncaab_tables = {
        "headline_first_observed_above_70": [
            row for row in tables["headline_first_observed_above_70"] if row["sport"] in DASHBOARD_SPORTS
        ],
        "around_80": [row for row in tables["around_80"] if row["sport"] in DASHBOARD_SPORTS],
    }
    return {
        "status": "OBSERVED",
        "universe_id": UNIVERSE_ID,
        "spec_sha256": digest,
        "live_execution": False,
        "submits": False,
        "research_only": True,
        "execution_disabled": True,
        "question": (
            "Among contracts observed around 80¢ one to two days before play, "
            "how much did the same contract’s bid change by T−30, and did that change "
            "exceed the observed purchase-to-sale spread?"
        ),
        "dashboard_sports": list(DASHBOARD_SPORTS),
        "library_note": "WNBA and MLB are measured in research/sugarland/v1 and are not this dashboard.",
        "limitations": [
            "Official listing time is UNAVAILABLE. Cohort A is first-observed above 70, not a verified open.",
            "Stored scheduled start is a sensitivity, including when it matches actual start.",
            "Quote-based return on entry ask is not an executable return.",
            "Historical L2, depth, latency, and maker fills are absent.",
            "NCAAB canonical candles are the mapped subset. Parquet counts are inventory only.",
        ],
        "coverage": {sport: coverage["by_sport"].get(sport) for sport in DASHBOARD_SPORTS},
        "parquet_inventory": coverage["parquet_inventory"],
        "tables": nba_ncaab_tables,
        "audit": audit,
        "contracts": rows,
    }


def _write_contracts(path: Path, contracts: list[dict[str, Any]]) -> None:
    if not contracts:
        path.write_text("")
        return
    keys: list[str] = []
    seen: set[str] = set()
    for row in contracts:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in contracts:
            flat = {}
            for key in keys:
                value = row.get(key)
                if value is None:
                    flat[key] = ""
                elif isinstance(value, bool):
                    flat[key] = "1" if value else "0"
                elif isinstance(value, float):
                    flat[key] = value
                elif hasattr(value, "numerator") and hasattr(value, "denominator") and not isinstance(value, int):
                    flat[key] = float(value)
                else:
                    flat[key] = value
            writer.writerow(flat)


def build() -> dict[str, Any]:
    digest = require_locked_spec()
    root = momento_root()
    out = artifact_dir()
    pbp_first = _first_pbp(root / "ROLLER" / "data" / "mlb" / "2025_2026" / "canonical" / "pbp")
    games: dict[str, GameRec] = {}
    markets: dict[str, dict[str, Any]] = {}
    ambiguous: set[str] = set()
    for sport, rel in SPORT_ROOTS:
        sport_games, sport_markets, sport_ambiguous = _load_sport(root, sport, rel, pbp_first if sport == "MLB" else {})
        games.update(sport_games)
        markets.update(sport_markets)
        ambiguous.update(sport_ambiguous)
    _assign_partitions(games)
    states: dict[str, TickerState] = {}
    counts = {"candle_rows": 0, "rows_without_clock": 0}
    for _sport, rel in SPORT_ROOTS:
        _scan_candles(root / "ROLLER" / "data" / rel / "canonical" / "kalshi_candles", games, markets, ambiguous, states, counts)
    contracts = [state.finalize() for state in states.values()]
    states.clear()
    manifests = {}
    for label, rel in (
        ("NBA", "nba/2025_2026"),
        ("NCAAB", "ncaab/2025_2026"),
        ("MLB", "mlb/2025_2026"),
        ("WNBA_2025", "wnba/2025"),
        ("WNBA_2026", "wnba/2026"),
    ):
        manifest = _read_manifest(root / "ROLLER" / "data" / rel / "derived" / "warehouse" / "manifest.json")
        manifests[label] = None if manifest is None else {
            "games": manifest.get("games"),
            "observation_rows": manifest.get("observation_rows"),
            "orderbook_data_available": manifest.get("orderbook_data_available"),
            "observation_basis": manifest.get("observation_basis") or manifest.get("observation_bases"),
        }
    coverage = _coverage(games, contracts, counts, manifests)
    tables = sport_tables(contracts, ("WNBA", "NBA", "NCAAB", "MLB"))
    audit = build_audit(contracts, ("WNBA", "NBA", "NCAAB", "MLB"))
    concentration: dict[str, Any] = {}
    for sport_name in ("WNBA", "NBA", "NCAAB", "MLB"):
        positive = sorted(
            (
                float(row["dpp"])
                for row in contracts
                if row.get("sport") == sport_name and row.get("in_a") and row.get("dpp") is not None and float(row["dpp"]) > 0
            ),
            reverse=True,
        )
        total = sum(positive)
        concentration[sport_name] = {
            "positive_n": len(positive),
            "top10_share_of_positive_dpp": None if total <= 0 else sum(positive[:10]) / total,
        }
    association = fit_association([row for row in contracts if row.get("in_a")])
    descriptive = fit_association([row for row in contracts if row.get("in_a")], descriptive=True)
    fills_path = root / "research" / "vital" / "bots" / "mlb-001" / "execution" / "fills.jsonl"
    positions = aggregate_positions(load_wnba_fills(fills_path))
    by_ticker = {row.get("ticker"): row for row in contracts}
    for position in positions:
        market = position.get("market")
        ticker = market if isinstance(market, str) else None
        contract = by_ticker.get(ticker)
        position["hypothetical_endpoint_bid_e4"] = None if contract is None else contract.get("p30_bid_e4")
        position["hypothetical_role"] = "HYPOTHETICAL_ENDPOINT_OR_SETTLEMENT"
        position["realized_pnl"] = "NOT_SUPPORTED"
    examples = _examples(contracts, games)
    summary = {
        "universe_id": UNIVERSE_ID,
        "spec_sha256": digest,
        "live_execution": False,
        "submits": False,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tables": tables,
        "audit": audit,
        "concentration": concentration,
        "coverage": coverage,
        "association_entry_time": association,
        "association_descriptive_lead_time": descriptive,
        "wnba_positions": positions,
        "examples": examples,
        "unmeasurable": {
            "listing_time": "UNAVAILABLE",
            "entry_time_schedule_snapshot": "UNAVAILABLE",
            "historical_l2": "UNAVAILABLE",
            "ledger_fees": "UNAVAILABLE",
            "injury_lineup_pitching": "UNAVAILABLE",
            "maker_fill_from_candle_touch": "NOT_A_FILL",
        },
    }
    _write_contracts(out / "contracts.csv", contracts)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (out / "examples.json").write_text(json.dumps(examples, indent=2))
    (out / "trades.json").write_text(json.dumps({"positions": positions, "fee_cents": "UNAVAILABLE"}, indent=2, default=str))
    (out / "coverage.json").write_text(json.dumps(coverage, indent=2))
    findings = findings_markdown(summary)
    (out / "FINDINGS.md").write_text(findings)
    page = _page(contracts, tables, coverage, digest, audit)
    (out / "page.json").write_text(json.dumps(page))
    print(f"sugarland contracts {len(contracts)} candles {counts['candle_rows']}", flush=True)
    return summary


def main() -> None:
    build()


if __name__ == "__main__":
    main()
