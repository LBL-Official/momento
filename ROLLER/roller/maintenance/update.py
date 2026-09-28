"""Master update pipeline. Default is offline (no network)."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from roller.admin import load_dataset
from roller.canonical.candles import canonicalize_candles
from roller.canonical.polymarket_candles import canonicalize_polymarket_candles
from roller.ingest.games import load_sport_games
from roller.ingest.polymarket import load_raw_events
from roller.canonical.games import canonicalize_games
from roller.canonical.identity_build import build_identity
from roller.canonical.markets import canonicalize_markets
from roller.canonical.orderbook import canonicalize_orderbook
from roller.canonical.pbp import canonicalize_pbp
from roller.canonical.players import upsert_players
from roller.canonical.trades import canonicalize_trades
from roller.research.first80 import write_first80
from roller.measurement.corpus import write_response_corpus
from roller.state.possessions import write_possessions
from roller.config import RollerConfig
from roller.features.d2d import build_d2d_daily, write_terminal_game_state
from roller.features.team_features import build_team_features
from roller.io_csv import sha256_file, write_json
from roller.maintenance.logging import append_log
from roller.paths import ensure_season_dirs
from roller.registry import default_registry, dataset_id, load_registry, save_registry, upsert_dataset_meta
from roller.timeutil import now_utc_iso
from roller.validation.integrity import run_integrity
from roller.validation.leakage import run_leakage


def _count_rows(path: Path) -> int:
    if path.is_file():
        with path.open() as f:
            return max(0, sum(1 for _ in f) - 1)
    if path.is_dir():
        n = 0
        for p in path.glob("*.csv"):
            n += _count_rows(p)
        return n
    return 0


def _log(cfg: RollerConfig, **row: Any) -> None:
    row.setdefault("update_id", uuid.uuid4().hex[:16])
    row.setdefault("pipeline_version", cfg.pipeline_version)
    row.setdefault("timestamp", now_utc_iso())
    append_log(cfg.root, row)


def fetch_sources(cfg: RollerConfig, sport: str, season: str) -> None:
    meta = cfg.season_meta(sport, season)
    cli = cfg.sources.get("fetch_clis", {}).get(sport)
    if not cli:
        return
    cmd = list(cli) + ["--season", meta["warehouse_season"]]
    subprocess.run(cmd, cwd=str(cfg.repo_root), check=False)


def update_sport(
    cfg: RollerConfig,
    sport: str,
    season: str,
    *,
    fetch: bool = False,
    include_pbp: bool = True,
    include_candles: bool = True,
) -> dict[str, Any]:
    ensure_season_dirs(cfg.root, sport, cfg.season_meta(sport, season)["path_key"])
    report: dict[str, Any] = {"sport": sport, "season": season, "steps": []}
    if fetch:
        fetch_sources(cfg, sport, season)
        report["steps"].append("fetch")

    ident_path = cfg.root / "meta" / "game_identity.csv"
    before_id = _count_rows(ident_path)
    prior_hash = sha256_file(ident_path) if ident_path.is_file() else ""
    identity = build_identity(cfg, sports=[sport])
    after_id = _count_rows(ident_path)
    new_hash = sha256_file(ident_path) if ident_path.is_file() else ""
    _log(
        cfg,
        dataset="game_identity",
        sport=sport,
        season=season,
        records_before=before_id,
        records_after=after_id,
        records_added=max(0, after_id - before_id),
        records_updated=0,
        status="OK",
        prior_source_hash=prior_hash,
        new_source_hash=new_hash,
        source_version="warehouse",
    )
    report["identity_rows"] = after_id

    games_path = cfg.dataset_path(sport, season, "games")
    before_g = _count_rows(games_path)
    prior_g = sha256_file(games_path) if games_path.is_file() else ""
    games = canonicalize_games(cfg, sport, season, identity)
    after_g = len(games)
    new_g = sha256_file(games_path) if games_path.is_file() else ""
    _log(
        cfg,
        dataset=dataset_id(sport, season, "games"),
        sport=sport,
        season=season,
        records_before=before_g,
        records_after=after_g,
        records_added=max(0, after_g - before_g),
        records_updated=0,
        status="OK",
        prior_source_hash=prior_g,
        new_source_hash=new_g,
        source_version="warehouse_games",
    )
    report["games"] = after_g

    n_pbp = 0
    if include_pbp:
        n_pbp = canonicalize_pbp(cfg, sport, season, identity, games)
        report["pbp"] = n_pbp
        _log(
            cfg,
            dataset=dataset_id(sport, season, "pbp"),
            sport=sport,
            season=season,
            records_before=0,
            records_after=n_pbp,
            records_added=n_pbp,
            records_updated=0,
            status="OK",
            source_version="pbp",
        )

    n_c = 0
    if include_candles:
        n_c = canonicalize_candles(cfg, sport, season, identity)
        report["candles"] = n_c
        _log(
            cfg,
            dataset=dataset_id(sport, season, "kalshi_candles"),
            sport=sport,
            season=season,
            records_before=0,
            records_after=n_c,
            records_added=n_c,
            records_updated=0,
            status="OK",
            source_version="candles_1m",
        )
        n_m = canonicalize_markets(cfg, sport, season, identity)
        report["markets"] = n_m
        _log(
            cfg,
            dataset=dataset_id(sport, season, "kalshi_markets"),
            sport=sport,
            season=season,
            records_before=0,
            records_after=n_m,
            records_added=n_m,
            records_updated=0,
            status="OK",
            source_version="markets",
        )
        n_t = canonicalize_trades(cfg, sport, season, identity)
        report["trades"] = n_t
        _log(
            cfg,
            dataset=dataset_id(sport, season, "kalshi_trades"),
            sport=sport,
            season=season,
            records_before=0,
            records_after=n_t,
            records_added=n_t,
            records_updated=0,
            status="OK",
            source_version="trades",
        )
        n_ob = canonicalize_orderbook(cfg, sport, season, identity)
        report["orderbook"] = n_ob
        _log(
            cfg,
            dataset=dataset_id(sport, season, "kalshi_orderbook_snapshots"),
            sport=sport,
            season=season,
            records_before=0,
            records_after=n_ob,
            records_added=n_ob,
            records_updated=0,
            status="OK",
            source_version="orderbook_snapshots",
        )
        _, _, wh_pm = load_sport_games(cfg, sport, season)
        if load_raw_events(wh_pm, sport):
            pm_stats = canonicalize_polymarket_candles(cfg, sport, season, identity=identity, download=False)
            report["polymarket_candles"] = pm_stats.get("candles")
            _log(
                cfg,
                dataset=dataset_id(sport, season, "polymarket_candles"),
                sport=sport,
                season=season,
                records_before=0,
                records_after=pm_stats.get("candles") or 0,
                records_added=pm_stats.get("candles") or 0,
                records_updated=0,
                status="OK",
                source_version="polymarket_prices_history_1m",
            )
        n80 = len(write_first80(cfg, sport, season))
        report["first80"] = n80
        _log(
            cfg,
            dataset=dataset_id(sport, season, "first80_triggers"),
            sport=sport,
            season=season,
            records_before=0,
            records_after=n80,
            records_added=n80,
            records_updated=0,
            status="OK",
            source_version="first80_frozen_v1",
        )

    src_hash = new_g
    feats = build_team_features(cfg, sport, season, games, source_hash=src_hash)
    d2d = build_d2d_daily(cfg, sport, season, games, source_hash=src_hash)
    write_terminal_game_state(cfg, sport, season, games, source_hash=src_hash)
    if include_pbp:
        try:
            pbp_df = load_dataset(cfg, sport, season, "pbp")
        except FileNotFoundError:
            pbp_df = None
        if pbp_df is not None and not pbp_df.empty:
            upsert_players(cfg, sport, pbp_df)
            n_poss = len(write_possessions(cfg, sport, season, pbp_df, games))
            report["possessions"] = n_poss
            _log(
                cfg,
                dataset=dataset_id(sport, season, "possessions"),
                sport=sport,
                season=season,
                records_before=0,
                records_after=n_poss,
                records_added=n_poss,
                records_updated=0,
                status="OK",
                source_version="pbp",
            )
    if include_pbp and sport in {"NBA", "WNBA", "NCAAB"}:
        from roller.fundamental.corpus import write_fundamental_corpus

        fund = write_fundamental_corpus(cfg, sport, season)
        report["fundamental_corpus"] = len(fund)
        _log(
            cfg,
            dataset=dataset_id(sport, season, "v4a_fundamental_state_corpus"),
            sport=sport,
            season=season,
            records_before=0,
            records_after=len(fund),
            records_added=len(fund),
            records_updated=0,
            status="OK",
            source_version="pbp_last_per_clock_bucket_v1",
        )
    if include_candles:
        corpus = write_response_corpus(cfg, sport, season)
        report["response_corpus"] = len(corpus)
        _log(
            cfg,
            dataset=dataset_id(sport, season, "v3_response_corpus"),
            sport=sport,
            season=season,
            records_before=0,
            records_after=len(corpus),
            records_added=len(corpus),
            records_updated=0,
            status="OK",
            source_version="sampled_first_mid_last",
        )
    report["team_features"] = len(feats)
    report["d2d"] = len(d2d)
    _log(
        cfg,
        dataset=dataset_id(sport, season, "team_features"),
        sport=sport,
        season=season,
        records_before=0,
        records_after=len(feats),
        records_added=len(feats),
        records_updated=0,
        status="OK",
        prior_source_hash=prior_g,
        new_source_hash=src_hash,
        source_version="games",
    )
    return report


def update_all(
    cfg: RollerConfig,
    *,
    sports: list[str] | None = None,
    seasons: dict[str, list[str]] | None = None,
    fetch: bool = False,
    include_pbp: bool = True,
    include_candles: bool = True,
    validate: bool = True,
) -> dict[str, Any]:
    _ensure_registry(cfg)
    sports = sports or cfg.sport_ids()
    reports = []
    for sport in sports:
        labels = (seasons or {}).get(sport) or cfg.season_labels(sport)
        for season in labels:
            print(f"ROLLER update {sport} {season}", flush=True)
            reports.append(
                update_sport(
                    cfg,
                    sport,
                    season,
                    fetch=fetch,
                    include_pbp=include_pbp,
                    include_candles=include_candles,
                )
            )
            for name in cfg.db_map["sports"][sport]["seasons"][season]["datasets"]:
                path = cfg.dataset_path(sport, season, name)
                present = path.is_file() or (path.is_dir() and any(path.glob("*.csv")))
                upsert_dataset_meta(
                    cfg,
                    dataset_id(sport, season, name),
                    last_updated=now_utc_iso(),
                    status="required" if present else "pending",
                )
            upsert_dataset_meta(cfg, "game_identity", last_updated=now_utc_iso(), status="required")

    integrity = run_integrity(cfg, sports=sports) if validate else {"status": "SKIPPED"}
    leakage = run_leakage(cfg, sports=sports) if validate else {"status": "SKIPPED"}
    if integrity.get("status") == "FAIL":
        raise SystemExit("integrity FAIL: " + "; ".join(integrity.get("errors", [])[:8]))
    if leakage.get("status") == "FAIL":
        raise SystemExit("leakage FAIL: " + "; ".join(leakage.get("errors", [])[:8]))

    daily = {
        "written_at": now_utc_iso(),
        "pipeline_version": cfg.pipeline_version,
        "sports": reports,
        "integrity": integrity,
        "leakage": leakage,
    }
    day = now_utc_iso()[:10]
    write_json(cfg.root / "reports" / "daily_updates" / f"{day}.json", daily)
    md = [
        f"# ROLLER daily update {day}",
        "",
        f"pipeline {cfg.pipeline_version}",
        f"integrity {integrity.get('status')}",
        f"leakage {leakage.get('status')}",
        "",
    ]
    for r in reports:
        md.append(f"- {r['sport']} {r['season']}: games={r.get('games')} pbp={r.get('pbp')} candles={r.get('candles')}")
    (cfg.root / "reports" / "daily_updates" / f"{day}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    daily["status"] = "OK"
    return daily


def _ensure_registry(cfg: RollerConfig) -> None:
    """Seed missing registry rows without demoting already-required datasets."""
    existing = load_registry(cfg)
    have = {ds.get("dataset_name") for ds in existing.get("datasets", [])}
    if not have:
        save_registry(cfg, default_registry(cfg))
        return
    seeded = default_registry(cfg)
    by_name = {ds["dataset_name"]: ds for ds in existing.get("datasets", [])}
    for ds in seeded["datasets"]:
        name = ds["dataset_name"]
        if name not in by_name:
            existing["datasets"].append(ds)
    save_registry(cfg, existing)
