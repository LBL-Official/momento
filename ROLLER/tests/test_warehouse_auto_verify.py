"""Phase 18 warehouse verify. Read-only on live. Fixture trees for failure cases.

Never write the live warehouse.
"""

from __future__ import annotations

import ast
import inspect
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.research_query.models import ResearchQuestion, ResearchStatus, Universe
from roller.warehouse.auto_ingest import IngestStatus, run_nba_warehouse_ingest
from roller.warehouse.auto_verify import (
    VerifyStatus,
    run_nba_warehouse_verify,
    verify_question,
)
from roller.warehouse.conditional_backtest import run_conditional_backtest
from roller.warehouse.coverage import (
    DATA_REQUIRED_CAPABILITIES,
    OBS_BASIS,
    OBS_RESOLUTION,
    OPERATION_REQUIRED_CAPABILITIES,
    PIT_FIELD,
    CapabilityName,
)
from roller.warehouse.layout import warehouse_root
from roller.warehouse.research_compiler import compile_research

from tests.test_warehouse_auto_ingest import _copy_root, _write_fixture

SRC = Path(__file__).resolve().parents[1]
LIVE_WAREHOUSE = SRC / "data" / "nba" / "2025_2026" / "derived" / "warehouse"
CFG = RollerConfig(SRC)
LIVE_SKIP = not (LIVE_WAREHOUSE / "manifest.json").is_file()


def _assert_not_live(path: Path) -> None:
    resolved = path.resolve()
    live = LIVE_WAREHOUSE.resolve()
    assert resolved != live
    assert live not in resolved.parents


def _check(report, name: str):
    found = [c for c in report.checks if c.name == name]
    assert found, f"missing check {name}: {[c.name for c in report.checks]}"
    return found[0]


@pytest.fixture(scope="module")
def live_report():
    if LIVE_SKIP:
        pytest.skip("Phase 8 warehouse absent")
    before = (LIVE_WAREHOUSE / "manifest.json").stat().st_mtime
    report = run_nba_warehouse_verify(CFG, include_research=True)
    after = (LIVE_WAREHOUSE / "manifest.json").stat().st_mtime
    assert after == before
    return report


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_identity_verification(live_report):
    ident = _check(live_report, "identity")
    assert ident.status is VerifyStatus.PASS, ident.detail
    assert live_report.identity["game_count"] == 1362
    assert live_report.identity["duplicate_games"] == 0
    assert live_report.identity["ambiguous_links"] == 0
    assert live_report.markets["linked_count"] == 2724
    assert live_report.markets["unlinked_count"] == 0


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_observation_semantics(live_report):
    obs = _check(live_report, "observations")
    assert obs.status is VerifyStatus.PASS, obs.detail
    assert live_report.observations["observation_basis"] == OBS_BASIS
    assert live_report.observations["resolution"] == OBS_RESOLUTION
    assert live_report.observations["pit_field"] == PIT_FIELD
    assert live_report.observations["observation_count"] == 6165183
    assert live_report.observations["silent_duplicates"] == 0
    assert live_report.observations["flagged_duplicate_rows"] == 6
    assert live_report.observations["invented_minutes"] == 0
    assert live_report.observation_basis == OBS_BASIS
    assert live_report.pit_field == PIT_FIELD


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_settlement_semantics(live_report):
    settle = _check(live_report, "settlements")
    assert settle.status is VerifyStatus.PASS, settle.detail
    assert live_report.settlements["source"] == "kalshi_rest"
    assert live_report.settlements["settlement_count"] == 2724
    assert live_report.settlements["YES"] == 1359
    assert live_report.settlements["NO"] == 1359
    assert live_report.settlements["INVALID"] == 6
    assert live_report.settlements["MISSING"] == 0
    assert live_report.settlements["INVALID"] != live_report.settlements["NO"]


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_pbp_semantics(live_report):
    pbp = _check(live_report, "pbp")
    assert pbp.status is VerifyStatus.PASS, pbp.detail
    assert live_report.pbp["pbp_pit_aligned_to_candles"] is False
    assert live_report.pbp["pbp_count"] == 780137
    man = json.loads((LIVE_WAREHOUSE / "manifest.json").read_text(encoding="utf-8"))
    assert man["pbp_pit_aligned_to_candles"] is False


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_capability_matrix(live_report):
    caps = _check(live_report, "capabilities")
    assert caps.status is VerifyStatus.PASS, caps.detail
    matrix = live_report.capability_matrix
    assert matrix[CapabilityName.TRADABLE_YES_BID_1M.value] == ResearchStatus.READY.value
    assert matrix[CapabilityName.CANDLE_PIT.value] == ResearchStatus.READY.value
    assert matrix[CapabilityName.SETTLEMENT.value] == ResearchStatus.READY.value
    assert matrix[CapabilityName.PBP.value] == ResearchStatus.READY.value
    assert matrix[CapabilityName.GAME.value] == ResearchStatus.READY.value
    assert matrix[CapabilityName.GAME_MARKET_LINK.value] == ResearchStatus.READY.value
    assert matrix[CapabilityName.HISTORICAL_L2.value] == ResearchStatus.DATA_REQUIRED.value
    assert matrix[CapabilityName.HISTORICAL_TICK.value] == ResearchStatus.DATA_REQUIRED.value
    assert matrix[CapabilityName.PBP_MARKET_PIT_ALIGNMENT.value] == ResearchStatus.OPERATION_REQUIRED.value
    for cap in DATA_REQUIRED_CAPABILITIES:
        assert matrix[cap.value] != ResearchStatus.READY.value
    for cap in OPERATION_REQUIRED_CAPABILITIES:
        assert matrix[cap.value] != ResearchStatus.READY.value


def test_duplicate_detection(tmp_path: Path):
    cfg = RollerConfig(_write_fixture(_copy_root(tmp_path)))
    ingested = run_nba_warehouse_ingest(cfg)
    assert ingested.status is IngestStatus.PUBLISHED
    published = Path(ingested.published_root)
    _assert_not_live(published)
    clean = run_nba_warehouse_verify(cfg, include_research=False)
    assert clean.status is VerifyStatus.PASS, clean.failures

    games_dup = tmp_path / "dup_games"
    shutil.copytree(published, games_dup)
    _assert_not_live(games_dup)
    games = pd.read_parquet(games_dup / "games" / "games.parquet")
    pd.concat([games, games.iloc[[0]]], ignore_index=True).to_parquet(games_dup / "games" / "games.parquet", index=False)
    games_report = run_nba_warehouse_verify(root=games_dup, include_research=False)
    assert games_report.status is VerifyStatus.FAIL
    assert any("duplicate" in f.lower() for f in games_report.failures)

    obs_dup = tmp_path / "dup_obs"
    shutil.copytree(published, obs_dup)
    _assert_not_live(obs_dup)
    month = next((obs_dup / "observations" / "basis=tradable_yes_bid").glob("month=*.parquet"))
    obs = pd.read_parquet(month)
    pd.concat([obs, obs.iloc[[0]]], ignore_index=True).to_parquet(month, index=False)
    obs_report = run_nba_warehouse_verify(root=obs_dup, include_research=False)
    assert obs_report.status is VerifyStatus.FAIL
    assert any("duplicate" in f.lower() for f in obs_report.failures)


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_manifest_fingerprint_consistency(live_report):
    fp = _check(live_report, "fingerprints")
    man_check = _check(live_report, "manifest")
    assert fp.status is VerifyStatus.PASS, fp.detail
    assert man_check.status is VerifyStatus.PASS, man_check.detail
    man_path = LIVE_WAREHOUSE / "manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    from roller.io_csv import sha256_file

    assert live_report.manifest_fingerprint == sha256_file(man_path)
    assert live_report.warehouse_version == man["updated_at"]
    assert man["games"] == live_report.identity["game_count"]
    assert man["observation_rows"] == live_report.observations["observation_count"]
    assert man["settlements"] == live_report.settlements["settlement_count"]
    assert man["pbp_rows"] == live_report.pbp["pbp_count"]
    assert man["observation_basis"] == OBS_BASIS


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_deterministic_research_result(live_report):
    repro = _check(live_report, "reproducibility")
    assert repro.status is VerifyStatus.PASS, repro.detail
    payload = live_report.reproducibility
    assert payload["plan_hash"]
    assert payload["result_hash"]
    assert payload["warehouse_version"] == live_report.warehouse_version
    assert payload["observation_basis"] == OBS_BASIS
    assert payload["pit_field"] == PIT_FIELD
    assert payload["runs"] == 2
    q = verify_question()
    again = run_conditional_backtest(q, CFG)
    assert again.plan_hash == payload["plan_hash"]
    assert again.result_hash == payload["result_hash"]
    assert again.population == payload["population"]
    assert dict(sorted(again.classification_counts.items())) == payload["classification_counts"]
    assert [list(r.identity()) for r in again.rows] == payload["row_identities"]
    assert "current_time" not in json.dumps(payload)


def _with_market_data(question: ResearchQuestion, market_data: tuple[str, ...], *, game_data=None, dims=None) -> ResearchQuestion:
    uni = question.universe
    return ResearchQuestion(
        universe=Universe(
            sports=uni.sports,
            leagues=uni.leagues,
            seasons=uni.seasons,
            markets=uni.markets,
            market_data=market_data,
            game_data=uni.game_data if game_data is None else game_data,
            date_from=uni.date_from,
            date_to=uni.date_to,
        ),
        entry_conditions=question.entry_conditions,
        path_conditions=question.path_conditions,
        terminal=question.terminal,
        requested_dimensions=question.requested_dimensions if dims is None else dims,
    )


@pytest.mark.skipif(LIVE_SKIP, reason="Phase 8 warehouse absent")
def test_fail_closed_unsupported_capability():
    q = verify_question()
    ready = compile_research(q, CFG)
    assert ready.status is ResearchStatus.READY
    l2 = compile_research(_with_market_data(q, ("historical_l2",)), CFG)
    tick = compile_research(_with_market_data(q, ("historical_tick",)), CFG)
    align = compile_research(
        _with_market_data(q, q.universe.market_data, game_data=("pbp",), dims=("PBP_MARKET_PIT_ALIGNMENT",)),
        CFG,
    )
    assert l2.status is ResearchStatus.DATA_REQUIRED
    assert tick.status is ResearchStatus.DATA_REQUIRED
    assert align.status is ResearchStatus.OPERATION_REQUIRED
    closed = run_conditional_backtest(_with_market_data(q, ("historical_l2",)), CFG)
    assert closed.status.value == "DATA_REQUIRED"
    assert closed.population == 0
    assert closed.rows == ()


def test_verify_does_not_import_confirm_and_run_or_first80():
    src = Path(__file__).resolve().parents[1] / "roller" / "warehouse" / "auto_verify.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    forbidden = {
        "roller.research_query.execute",
        "roller.research_query.compiler",
        "roller.research_query.planner",
        "roller.research_query.official_settlement",
        "roller.admin",
        "roller.research.first80",
        "roller.auto_roller.ingest",
        "roller.auto_roller.verify",
    }
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not (imported & forbidden)
    text = src.read_text(encoding="utf-8")
    assert "FIRST80" not in text
    assert "first80" not in text
    load_src = inspect.getsource(run_nba_warehouse_verify)
    assert "to_csv" not in load_src
    assert "write_nba_warehouse" not in load_src
    assert "execute_question" not in text
