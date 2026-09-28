"""Path-trade FE: leakage, labels, import wall, synthetic walk-forward."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from roller.nba_path_fe.config import PathFeConfig
from roller.nba_path_fe.enter_skip import p_k_identity
from roller.nba_path_fe.episodes import build_episodes
from roller.nba_path_fe.features import build_enter_features
from roller.nba_path_fe.labels import build_labels
from roller.nba_path_fe.leakage import assert_no_post_ts_leakage
from roller.nba_path_fe.registry import enter_skip_names, hedge_names, load_registry
from roller.nba_path_fe.synthetic import generate_games


PKG = Path(__file__).resolve().parents[1] / "roller" / "nba_path_fe"


def _small_cfg() -> PathFeConfig:
    return PathFeConfig(n_games=96, ticks_per_game=96, seed=80)


def test_registry_family_e_hedge_only() -> None:
    reg = load_registry()
    for spec in reg["features"]:
        if spec.family == "E":
            assert spec.used_in == "hedge_only"
    assert "impulse_x_disagreement" in enter_skip_names(reg)
    assert "thin_x_disagreement" in enter_skip_names(reg)
    assert all(n.startswith("hedge_") for n in hedge_names(reg))


def test_enter_skip_modules_do_not_import_hedge() -> None:
    banned = {"roller.nba_path_fe.hedge", "hedge"}
    for name in ("enter_skip.py", "features.py", "pca_rep.py", "walkforward.py", "leakage.py"):
        src = (PKG / name).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "hedge" not in alias.name
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module not in banned
                assert "hedge" not in node.module


def test_y_is_s_and_not_t40() -> None:
    ticks, games = generate_games(_small_cfg())
    ep = build_episodes(ticks, games, _small_cfg())
    lab = build_labels(ep, ticks, _small_cfg())
    filled = lab.loc[lab["filled"] == 1]
    assert not filled.empty
    for rec in filled.itertuples(index=False):
        expect = int(rec.S == 1 and rec.M is not None and int(rec.M) > 40)
        assert int(rec.Y) == expect
        if rec.hit40 == 1:
            assert int(rec.Y) == 0


def test_first_touch_one_per_market() -> None:
    ticks, games = generate_games(_small_cfg())
    ep = build_episodes(ticks, games, _small_cfg())
    assert ep.duplicated(["game_id", "market_id", "side"]).sum() == 0
    assert set(ep["period"].unique()) <= {1, 2, 3, 4}


def test_no_post_ts_leakage() -> None:
    cfg = _small_cfg()
    ticks, games = generate_games(cfg)
    ep = build_episodes(ticks, games, cfg)
    lab = build_labels(ep, ticks, cfg)
    out = assert_no_post_ts_leakage(ep, ticks, lab, cfg)
    assert out["ok"] is True


def test_enter_features_exclude_hedge_columns() -> None:
    cfg = _small_cfg()
    ticks, games = generate_games(cfg)
    ep = build_episodes(ticks, games, cfg)
    lab = build_labels(ep, ticks, cfg)
    feat, _ = build_enter_features(ep, ticks, lab, cfg)
    assert not any(c.startswith("hedge_") for c in feat.columns)
    assert "impulse_x_disagreement" in feat.columns
    assert "thin_x_disagreement" in feat.columns


def test_recover_criteria_requires_lift_and_r() -> None:
    from roller.nba_path_fe.config import DEFAULT
    from roller.nba_path_fe.decision_grid import meets_recover_criteria

    folds = [
        {"status": "OK", "era": str(i), "r": 0.18} for i in range(5)
    ]
    ok, misses = meets_recover_criteria(
        {"p_0": 0.715, "p_K": 0.691, "p_R": 0.726, "r": 0.18},
        folds,
        DEFAULT,
    )
    assert ok is False
    assert "p_K_not_above_p0" in misses
    assert "p_R_not_below_p0" in misses
    ok2, _ = meets_recover_criteria(
        {"p_0": 0.70, "p_K": 0.72, "p_R": 0.60, "r": 0.18},
        folds,
        DEFAULT,
    )
    assert ok2 is True


def test_clock_and_e4() -> None:
    from roller.nba_path_fe.clockparse import clock_to_seconds, e4_to_cents

    assert clock_to_seconds("PT09M04.00S") == 544
    assert clock_to_seconds("PT11M39.00S") == 699
    assert e4_to_cents(8100) == 81
    assert e4_to_cents("4600") == 46


def test_fee_model_unresolved_on_warehouse() -> None:
    from roller.nba_path_fe.fees_sim import UNRESOLVED_ID, ev_cents, resolve_fee_model

    real = resolve_fee_model("WAREHOUSE_2025_2026")
    assert real["id"] == UNRESOLVED_ID
    assert real["status"] == "UNAVAILABLE"
    cfg = PathFeConfig(source_tag="WAREHOUSE_2025_2026")
    assert ev_cents(0.74, cfg) != ev_cents(0.74, cfg)  # NaN


def test_tau_policy_band_claim() -> None:
    from roller.nba_path_fe.config import DEFAULT
    from roller.nba_path_fe.tau_policy import (
        MODE_OOB_SYNTHETIC,
        may_claim_band_compliance,
        sealed_real_data_criteria,
        tau_mode,
    )

    cfg = DEFAULT
    assert may_claim_band_compliance(tau=0.80, r=0.18, cfg=cfg) is True
    assert may_claim_band_compliance(tau=0.59, r=0.17, cfg=cfg) is False
    assert may_claim_band_compliance(tau=0.80, r=0.08, cfg=cfg) is False
    assert tau_mode(0.59, cfg) == MODE_OOB_SYNTHETIC
    ok, reasons = sealed_real_data_criteria(
        source="SYNTHETIC_E2E",
        raw_present=False,
        folds=[{"status": "OK", "era": "e", "tau": 0.80, "r": 0.18}],
        pooled={"r": 0.18, "p_K": 0.90, "p_R": 0.04},
        cfg=cfg,
    )
    assert ok is False
    assert "warehouse_raw_absent" in reasons


def test_p_k_identity() -> None:
    p0, pr, r = 0.70, 0.40, 0.20
    pk = p_k_identity(p0, pr, r)
    assert pk == pytest.approx(0.70 + (0.20 / 0.80) * (0.70 - 0.40))


def test_synthetic_walkforward_writes_summary(tmp_path, monkeypatch) -> None:
    import shutil

    from roller.nba_path_fe import paths as P
    from roller.nba_path_fe.build import run_synthetic_e2e

    src_reg = P.features_registry_path()
    (tmp_path / "features").mkdir(parents=True)
    shutil.copy(src_reg, tmp_path / "features" / "registry.yaml")
    monkeypatch.setattr(P, "library_root", lambda: tmp_path)
    cfg = PathFeConfig(n_games=160, ticks_per_game=80, seed=80)
    summary = run_synthetic_e2e(cfg, leakage=False)
    assert (tmp_path / "artifacts" / "walkforward" / "summary.json").is_file()
    pooled = summary["pooled"]
    assert pooled["n"] >= 30
    assert 0.0 <= pooled["r"] <= 1.0
    assert summary["representation"] == "pcs_plus_knn"
    assert int(summary["folds"][0].get("m_pcs", 4)) <= 4
    assert summary["enter_skip_has_hedge_columns"] is False
    assert summary["ambition"]["p_K"] == 0.82
    assert summary["ambition"]["hit"] is False
    assert summary["ambition"]["claimable"] is False
    assert summary["promotion"] == "FAILED"
    assert summary["promoted_residuals"] == []
    assert "train_rate_target" not in summary.get("tau_modes", [])
    assert summary["warehouse_gate"]["ambition_claimable"] is False
    for fold in summary["folds"]:
        if fold.get("status") != "OK":
            continue
        assert "r_in_band" in fold
        assert "tau" in fold
        assert "p_0" in fold and "p_K" in fold and "p_R" in fold
        tau = float(fold["tau"])
        mode = fold["tau_mode"]
        if 0.77 <= tau <= 0.84:
            assert mode == "spec_band"
        else:
            assert mode == "out_of_band_synthetic"
            assert fold["band_compliance_claimed"] is False
        if mode == "spec_band" and fold["r_in_band"]:
            assert fold["band_compliance_claimed"] is True
        else:
            assert fold["band_compliance_claimed"] is False
    pooled = summary["pooled"]
    assert "all_folds_r_in_band" in pooled
    assert "fold_r_failures" in pooled
    if not pooled["all_folds_r_in_band"]:
        assert len(pooled["fold_r_failures"]) >= 1
