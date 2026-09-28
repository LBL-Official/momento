"""Phase orchestration. Stops if leakage audit fails. Phase 7 is gated."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from terminal_efficiency import PHASE7_AUTHORIZED, __version__
from terminal_efficiency.config import load_league_config
from terminal_efficiency.features.pregame import build_pregame_features
from terminal_efficiency.features.registry import registry_records
from terminal_efficiency.identity import build_game_key_map, ticker_to_game_id
from terminal_efficiency.ingestion.kalshi import record_existing_kalshi_gap, run_kalshi_download
from terminal_efficiency.ingestion.nba_stats import record_nba_pbp_status, try_timeactual_ingest
from terminal_efficiency.ingestion.ncaab_espn import ingest_ncaab_espn
from terminal_efficiency.models.mcd import evaluate_mcd_on_val
from terminal_efficiency.models.metrics import probability_metrics
from terminal_efficiency.models.xib import apply_xib, train_xib_hierarchy
from terminal_efficiency.normalize.nba_games import build_nba_games
from terminal_efficiency.normalize.nba_pbp import load_all_nba_events
from terminal_efficiency.normalize.ncaab import load_all_ncaab_events, load_ncaab_games
from terminal_efficiency.paths import derived_root, models_dir, predictions_dir, reports_dir
from terminal_efficiency.provenance import write_json
from terminal_efficiency.state.candle_alignment import align_states_to_candles, load_raw_candles_frame
from terminal_efficiency.state.game_state_builder import build_possession_observations
from terminal_efficiency.validation.leakage_audit import run_leakage_audit
from terminal_efficiency.validation.temporal_split import add_split, assert_no_test_in_fit


class LeakageAuditFailed(RuntimeError):
    pass


class Phase7NotAuthorized(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PHASE 7 OOS EVALUATION = NOT AUTHORIZED")


def ingest(league: str, season: str, *, kalshi_dry_run: bool = True, ncaab_max_days: int | None = None) -> dict:
    out: dict = {"league": league, "season": season}
    out["kalshi_existing"] = record_existing_kalshi_gap(league, season)
    out["kalshi_cli"] = run_kalshi_download(league, season, dry_run=kalshi_dry_run)
    if league.upper() == "NBA":
        out["nba_stats"] = record_nba_pbp_status(season)
        if season == "2024-2025":
            out["timeactual"] = try_timeactual_ingest(season)
    else:
        out["ncaab_espn"] = ingest_ncaab_espn(season, max_days=ncaab_max_days, fetch_pbp=True)
    write_json(reports_dir(league, season) / "ingest_report.json", out)
    return out


def _load_games_events(league: str, season: str):
    cfg = load_league_config(league)
    if league.upper() == "NBA":
        games = build_nba_games(season)
        events = load_all_nba_events(games, cfg, season)
    else:
        games = load_ncaab_games(season)
        events = load_all_ncaab_events(games, cfg, season)
    return cfg, games, events


def build_states(league: str, season: str) -> dict:
    cfg, games, events = _load_games_events(league, season)
    if games.empty:
        return {"status": "MISSING", "reason": "no games"}
    pregame = build_pregame_features(games)
    pregame = add_split(pregame, cfg.train_end)
    dest = derived_root(league, season)
    pregame.to_parquet(dest / "dataset_a_pregame.parquet", index=False)
    obs = build_possession_observations(games, events, cfg)
    if not obs.empty:
        # drop frozen test if someone pointed at 2025-26
        obs = obs[obs["split"] != "TEST_FROZEN"] if season != "2025-2026" else obs
        obs.to_parquet(dest / "dataset_b_possession.parquet", index=False)
    write_json(
        dest / "build_states_manifest.json",
        {
            "n_games": int(len(games)),
            "n_events": int(len(events)),
            "n_pregame": int(len(pregame)),
            "n_possession_obs": int(len(obs)),
            "feature_registry": registry_records(),
        },
    )
    return {"n_games": int(len(games)), "n_events": int(len(events)), "n_obs": int(len(obs))}


def audit_leakage(league: str, season: str) -> dict:
    dest = derived_root(league, season)
    pregame = pd.read_parquet(dest / "dataset_a_pregame.parquet") if (dest / "dataset_a_pregame.parquet").exists() else None
    obs = pd.read_parquet(dest / "dataset_b_possession.parquet") if (dest / "dataset_b_possession.parquet").exists() else None
    feature_cols = None
    if obs is not None:
        feature_cols = [
            c
            for c in obs.columns
            if c
            not in {
                "final_home_win",
                "observation_id",
                "game_id",
                "split",
                "xib_home_win_probability",
                "mcd_home_win_probability",
            }
        ]
    report = run_leakage_audit(league=league, season=season, pregame=pregame, observations=obs, feature_columns=feature_cols)
    if report["status"] != "PASS":
        raise LeakageAuditFailed(json.dumps(report["failures"][:10], default=str))
    return report


def train_xib(league: str, season: str, *, freeze: bool = False) -> dict:
    dest = derived_root(league, season)
    obs = pd.read_parquet(dest / "dataset_b_possession.parquet")
    assert_no_test_in_fit(obs)
    result = train_xib_hierarchy(obs)
    if result.get("status") != "OK":
        write_json(reports_dir(league, season) / "xib_train.json", result)
        return result
    cal = result.pop("calibrator")
    cols = result["selected_features"]
    work = obs.dropna(subset=["final_home_win"]).copy()
    work = work[work["split"].isin(["TRAIN", "VAL"])]
    p = apply_xib(cal, work, cols)
    work["xib_home_win_probability"] = p
    work["xib_away_win_probability"] = 1.0 - p
    work.to_parquet(predictions_dir(league, season) / "xib_2024_25.parquet", index=False)
    import joblib

    if freeze:
        joblib.dump({"calibrator": cal, "features": cols, "meta": result}, models_dir(league, season) / "xib_frozen.joblib")
    from terminal_efficiency.training.charts import write_hist, write_reliability_chart

    valp = work[work["split"] == "VAL"]
    if not valp.empty:
        m = None
        for c in result.get("candidates") or []:
            if c.get("name") == result.get("selected") and c.get("val"):
                m = c["val"]
        if m and m.get("reliability"):
            write_reliability_chart(
                reports_dir(league, season) / "xib_reliability.png",
                m["reliability"],
                f"{league} {result.get('selected')} VAL reliability",
            )
        write_hist(
            reports_dir(league, season) / "xib_prediction_hist.png",
            valp["xib_home_win_probability"].to_numpy(),
            f"{league} XIB VAL prediction distribution",
        )
    write_json(reports_dir(league, season) / "xib_train.json", result)
    return {k: v for k, v in result.items() if k != "calibrator"}


def train_mcd(league: str, season: str) -> dict:
    cfg = load_league_config(league)
    obs = pd.read_parquet(derived_root(league, season) / "dataset_b_possession.parquet")
    report = evaluate_mcd_on_val(obs, cfg)
    write_json(reports_dir(league, season) / "mcd_val.json", report)
    return report


def apply_candles(league: str, season: str) -> dict:
    dest = derived_root(league, season)
    obs_path = dest / "dataset_b_possession.parquet"
    if not obs_path.exists():
        return {"status": "MISSING", "reason": "build-states first"}
    obs = pd.read_parquet(obs_path)
    games = pd.read_parquet(dest / "games.parquet") if (dest / "games.parquet").exists() else pd.DataFrame()
    candles = load_raw_candles_frame(league, season)
    key_map = build_game_key_map(games) if not games.empty else {}
    aligned, coverage = align_states_to_candles(
        obs, candles, game_id_from_ticker=lambda t: ticker_to_game_id(t, key_map)
    )
    if not aligned.empty:
        aligned.to_parquet(dest / "dataset_c_candle_aligned.parquet", index=False)
    write_json(reports_dir(league, season) / "candle_alignment_coverage.json", coverage)
    return coverage


def evaluate_oos(season: str) -> None:
    if season.startswith("2025") and not PHASE7_AUTHORIZED:
        raise Phase7NotAuthorized()
    raise Phase7NotAuthorized()
