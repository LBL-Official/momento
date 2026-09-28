"""NBA 80→40 reverse-features locks, leakage, and isolation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from roller.choosin_texas.ev import book_cents
from roller.nba_8040_reverse_features.catalog import (
    FORBIDDEN_NAMES,
    FUTURE,
    LABEL_SPECS,
    POST,
    matrix_specs,
    spec_by_name,
)
from datetime import datetime, timedelta, timezone

from roller.nba_8040_reverse_features.classify import classify
from roller.nba_8040_reverse_features.features import _window
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError
from roller.nba_8040_reverse_features.instances import instance_id, load_instances
from roller.nba_8040_reverse_features.knn import neighborhood_table
from roller.nba_8040_reverse_features.labels import target
from roller.nba_8040_reverse_features.leakage import assert_predictive_columns
from roller.nba_8040_reverse_features.locks import (
    GAIN_CENTS,
    LOSS_CENTS,
    features_path,
    labels_path,
    NBA_Q2_N,
    NBA_Q2_RS_BOOK,
    NBA_Q2_RS_N,
    NBA_Q2_RS_S,
    NBA_Q2Q3_BOOK,
    NBA_Q2Q3_L_T40,
    NBA_Q2Q3_N,
    NBA_Q2Q3_S,
    NBA_Q2Q3_W_T40,
    NBA_Q3_N,
)
from roller.nba_8040_reverse_features.matrix import (
    complete_mask,
    coverage_names,
    predictive_frame,
    standardized_matrix,
)
from roller.nba_8040_reverse_features.pca import run_pca

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "ROLLER" / "roller" / "nba_8040_reverse_features"
BOOK = (
    REPO
    / "research"
    / "choosin_texas"
    / "library"
    / "nba_2q_regular_8040_1lot_2026_27"
    / "book.json"
)
CONTRACT = REPO / "research" / "nba_8040_reverse_features" / "FEATURE_CONTRACT.md"


def test_feature_contract_exists():
    assert CONTRACT.is_file()
    text = CONTRACT.read_text(encoding="utf-8")
    assert "N=604" in text
    assert "PREDICTIVE_FEATURE_MATRIX" in text


def test_choosin_texas_book_untouched_path():
    assert BOOK.is_file()


def test_package_does_not_import_first80_or_confirm_and_run():
    forbidden = (
        "import first80",
        "from roller.first80",
        "from roller.execute",
        "from roller.compiler",
        "load_dataset",
    )
    for path in PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.relative_to(PKG)} contains {token}"


def test_matrix_module_does_not_import_labels_or_event_path():
    for name in ("matrix.py", "leakage.py"):
        text = (PKG / name).read_text(encoding="utf-8")
        assert "import labels" not in text
        assert "import event_path" not in text
        assert "nba_8040_reverse_features.labels" not in text
        assert "nba_8040_reverse_features.event_path" not in text


def test_instance_id_is_stable_hash():
    got = instance_id("EVT", "TICK", "2025-10-10T23:48:00+00:00")
    raw = b"EVT|TICK|2025-10-10T23:48:00+00:00|FIRST80"
    assert got == hashlib.sha256(raw).hexdigest()[:16]
    assert len(got) == 16


def test_ev_identity_on_locked_integers():
    assert book_cents(NBA_Q2Q3_S, NBA_Q2Q3_N, gain=GAIN_CENTS, loss=LOSS_CENTS) == NBA_Q2Q3_BOOK
    assert book_cents(NBA_Q2_RS_S, NBA_Q2_RS_N, gain=GAIN_CENTS, loss=LOSS_CENTS) == NBA_Q2_RS_BOOK
    assert NBA_Q2Q3_S + NBA_Q2Q3_W_T40 + NBA_Q2Q3_L_T40 == NBA_Q2Q3_N
    assert NBA_Q2_N + NBA_Q3_N == NBA_Q2Q3_N


def test_load_instances_reproduces_locks():
    rows = load_instances()
    assert len(rows) == NBA_Q2Q3_N
    assert len({row["instance_id"] for row in rows}) == NBA_Q2Q3_N
    assert len({row["event_id"] for row in rows}) == NBA_Q2Q3_N
    assert sum(row["period"] == "Q2" for row in rows) == NBA_Q2_N
    assert sum(row["period"] == "Q3" for row in rows) == NBA_Q3_N
    assert sum(row["period"] == "Q2" and row["regular_season"] for row in rows) == NBA_Q2_RS_N
    s_n = sum(1 for row in rows if not row["t40"])
    w_t40 = sum(1 for row in rows if row["t40"] and row["w"])
    l_t40 = sum(1 for row in rows if row["t40"] and not row["w"])
    assert (s_n, w_t40, l_t40) == (NBA_Q2Q3_S, NBA_Q2Q3_W_T40, NBA_Q2Q3_L_T40)
    q2_rs = [row for row in rows if row["period"] == "Q2" and row["regular_season"]]
    assert sum(1 for row in q2_rs if not row["t40"]) == NBA_Q2_RS_S
    assert all(row["slice"] in {"Q2", "Q3"} for row in rows)
    assert all(row["sport"] == "NBA" for row in rows)


def test_target_is_isolated_and_stop_reusable():
    instance = {"post_entry_min": 38}
    forty = target(instance, stop_cents=40)
    assert forty["t_stop"] is True
    assert forty["s"] is False
    assert forty["ev_contribution"] == -40
    twenty_five = target(instance, stop_cents=25)
    assert twenty_five["t_stop"] is False
    assert twenty_five["s"] is True
    assert twenty_five["ev_contribution"] == 20
    survive = target({"post_entry_min": 61}, stop_cents=40)
    assert survive["s"] is True
    assert survive["ev_contribution"] == 20


def test_leakage_rejects_forbidden_names():
    with pytest.raises(ReverseFeaturesError) as exc:
        assert_predictive_columns(["t40"])
    assert exc.value.code == "LEAKAGE"
    for name in sorted(FORBIDDEN_NAMES):
        with pytest.raises(ReverseFeaturesError) as exc:
            assert_predictive_columns([name])
        assert exc.value.code == "LEAKAGE"


def test_leakage_rejects_future_hints_and_unregistered():
    with pytest.raises(ReverseFeaturesError):
        assert_predictive_columns(["price_5m_after"])
    with pytest.raises(ReverseFeaturesError):
        assert_predictive_columns(["not_a_real_feature"])
    with pytest.raises(ReverseFeaturesError):
        assert_predictive_columns([])


def test_period_one_hot_and_labels_are_not_matrix_features():
    names = {spec.name for spec in matrix_specs()}
    assert "period_q2" not in names
    assert "period_q3" not in names
    assert "t40" not in names
    assert "s" not in names
    specs = spec_by_name()
    assert specs["period_q2"].include_in_matrix is False
    label_t40 = next(spec for spec in LABEL_SPECS if spec.name == "t40")
    assert label_t40.timing in {FUTURE, POST}


def test_predictive_frame_asserts_leakage():
    frame = pd.DataFrame({"entry_bid_cents": [80.0], "t40": [1]})
    with pytest.raises(ReverseFeaturesError):
        predictive_frame(frame, ["t40"])
    ok = pd.DataFrame({"entry_bid_cents": [80.0], "pregame_cents": [55.0]})
    out = predictive_frame(ok, ["entry_bid_cents", "pregame_cents"])
    assert list(out.columns) == ["entry_bid_cents", "pregame_cents"]


def _toy_store(n: int = 40) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(80)
    period = np.array(["Q2"] * (n // 2) + ["Q3"] * (n - n // 2))
    features = pd.DataFrame(
        {
            "instance_id": [f"i{i:03d}" for i in range(n)],
            "period": period,
            "dataset_split": ["IN_SAMPLE"] * n,
            "entry_bid_cents": 80 + rng.normal(0, 1, n),
            "pregame_cents": 50 + rng.normal(0, 5, n),
            "bought_margin": rng.normal(4, 3, n),
            "frac_period_remaining": rng.uniform(0.1, 0.9, n),
        }
    )
    for name in ("entry_bid_cents", "pregame_cents", "bought_margin", "frac_period_remaining"):
        features[f"{name}__status"] = "OBSERVED"
    features.loc[0, "pregame_cents"] = np.nan
    features.loc[0, "pregame_cents__status"] = "OBSERVATION_UNAVAILABLE"
    labels = pd.DataFrame(
        {
            "instance_id": features["instance_id"],
            "period": period,
            "s": rng.random(n) > 0.3,
            "t40": False,
            "ev_contribution": 20,
            "dataset_split": features["dataset_split"],
        }
    )
    labels["t40"] = ~labels["s"]
    labels["ev_contribution"] = np.where(labels["s"], 20, -40)
    return features, labels


def test_missing_stays_missing_and_complete_case_drops_row():
    features, _labels = _toy_store()
    names = ["entry_bid_cents", "pregame_cents"]
    mask = complete_mask(features, names)
    assert bool(mask.iloc[0]) is False
    assert pd.isna(features.loc[0, "pregame_cents"])
    assert features.loc[0, "pregame_cents"] != 0
    _matrix, used, index = standardized_matrix(features, names)
    assert 0 not in set(index)
    assert used == names


def test_coverage_and_pca_knn_do_not_need_outcomes_in_matrix():
    features, labels = _toy_store()
    names = ["entry_bid_cents", "pregame_cents", "bought_margin", "frac_period_remaining"]
    covered = coverage_names(features, names, min_frac=0.90)
    assert "entry_bid_cents" in covered
    pca = run_pca(features, labels, names=covered)
    assert pca["n"] >= 30
    assert pca["n_features"] == len(covered)
    table = neighborhood_table(features, labels, covered, ks=(5,), within=True)
    assert table
    with pytest.raises(ReverseFeaturesError):
        coverage_names(features, ["t40"], min_frac=0.0)


def test_one_minute_window_includes_exact_left_edge():
    entry = datetime(2025, 10, 10, 23, 48, tzinfo=timezone.utc)
    pre = [
        (entry - timedelta(minutes=2), 70.0),
        (entry - timedelta(minutes=1), 75.0),
        (entry - timedelta(seconds=30), 78.0),
    ]
    assert _window(pre, entry, 1) == [75.0, 78.0]
    assert _window(pre, entry, 1)[0] == 75.0


def test_classify_unexplained_when_regions_match():
    analysis = {
        "composition": {
            "population": [
                {"period": "Q2", "n": 100, "t40": 20, "book_cents": 400},
                {"period": "Q3", "n": 100, "t40": 25, "book_cents": 200},
            ],
            "q2_vs_q3": [
                {"feature": "bought_margin", "standardized_difference": 0.05},
                {"feature": "frac_period_remaining", "standardized_difference": 0.04},
            ],
        },
        "matching": [
            {"source_period": "Q2", "difference": 0.04},
        ],
        "temporal": [],
        "within": [
            {"q2_smd": 0.05, "q3_smd": 0.04},
        ],
    }
    verdict = classify(analysis)
    assert verdict["label"] == "UNEXPLAINED"


def test_classify_does_not_treat_definitional_clock_as_time_structure():
    analysis = {
        "composition": {
            "population": [
                {"period": "Q2", "n": 314, "t40": 75, "book_cents": 1780},
                {"period": "Q3", "n": 290, "t40": 79, "book_cents": 1060},
            ],
            "q2_vs_q3": [
                {"feature": "frac_game_elapsed", "standardized_difference": 3.0},
                {"feature": "bought_margin", "standardized_difference": 0.08},
                {"feature": "pregame_cents", "standardized_difference": 0.37},
                {"feature": "delta_5m", "standardized_difference": 0.40},
            ],
        },
        "matching": [{"source_period": "Q2", "difference": -0.07}],
        "temporal": [
            {"axis": "frac_period_remaining", "bin": "a", "period": "Q2", "ev_cents": 8.0},
            {"axis": "frac_period_remaining", "bin": "a", "period": "Q3", "ev_cents": 2.0},
        ],
        "within": [{"q2_smd": 0.05, "q3_smd": 0.04}],
    }
    verdict = classify(analysis)
    assert "TIME-STRUCTURAL" not in verdict["flags"]
    assert verdict["label"] == "UNEXPLAINED"


def test_written_store_keeps_labels_out_if_present():
    path = features_path()
    if not path.is_file():
        pytest.skip("feature store not built")
    features = pd.read_parquet(path)
    labels = pd.read_parquet(labels_path())
    assert len(features) == NBA_Q2Q3_N
    assert len(labels) == NBA_Q2Q3_N
    for name in FORBIDDEN_NAMES:
        assert name not in features.columns
    assert int(labels["s"].sum()) == NBA_Q2Q3_S
    assert int(labels["w_and_t40"].sum()) == NBA_Q2Q3_W_T40
    assert int(labels["l_and_t40"].sum()) == NBA_Q2Q3_L_T40


def test_locked_store_and_book_hashes():
    from roller.nba_8040_reverse_features.deep_quant.util import sha256_file
    from roller.nba_8040_reverse_features.locks import (
        BOOK_SHA256,
        LABELS_SHA256,
        PRE80_SHA256,
        book_path,
    )

    assert sha256_file(features_path()) == PRE80_SHA256
    assert sha256_file(labels_path()) == LABELS_SHA256
    assert sha256_file(book_path()) == BOOK_SHA256


def test_deep_quant_matrix_has_no_future_and_keeps_missing():
    from roller.nba_8040_reverse_features.deep_quant.space import raw_matrix_frame
    from roller.nba_8040_reverse_features.locks import matrix_path

    features = pd.read_parquet(features_path())
    frame = raw_matrix_frame(features)
    assert len(frame) == NBA_Q2Q3_N
    for name in FORBIDDEN_NAMES:
        assert name not in frame.columns
    assert "price_5m_after" not in frame.columns
    assert "entry_last_cents" in frame.columns
    assert frame["entry_last_cents"].isna().sum() == 3
    assert (frame["miss_entry_last_cents"] == 1).sum() == 3
    assert not (frame["entry_last_cents"].fillna(0).eq(0) & frame["entry_last_cents"].isna()).all()
    if matrix_path().is_file():
        written = pd.read_parquet(matrix_path())
        assert "t40" not in written.columns
        assert "terminal_yes" not in written.columns
        assert len(written) == NBA_Q2Q3_N


def test_pca_and_knn_distances_ignore_labels():
    from roller.nba_8040_reverse_features.deep_quant.knn_study import knn_tables
    from roller.nba_8040_reverse_features.deep_quant.pca_study import fit_pca
    from roller.nba_8040_reverse_features.deep_quant.space import representation
    from roller.nba_8040_reverse_features.deep_quant.util import KS

    features = pd.read_parquet(features_path())
    labels = pd.read_parquet(labels_path())
    rep = representation(features, ["entry_bid_cents", "pregame_cents", "bought_margin", "frac_period_remaining"], kind="complete_columns")
    pca_a = fit_pca(rep["z"], rep["used"], n_keep=3)
    labels_b = labels.copy()
    labels_b["t40"] = np.random.default_rng(1).permutation(labels_b["t40"].to_numpy())
    pca_b = fit_pca(rep["z"], rep["used"], n_keep=3)
    np.testing.assert_allclose(pca_a["scores"], pca_b["scores"])
    aligned = rep["meta"].copy()
    aligned["t40"] = labels.set_index("instance_id").loc[aligned["instance_id"], "t40"].to_numpy()
    aligned["s"] = ~aligned["t40"]
    knn_a = knn_tables(rep["z"], aligned, ks=(5,))
    aligned_b = aligned.copy()
    aligned_b["t40"] = np.random.default_rng(2).permutation(aligned_b["t40"].to_numpy())
    aligned_b["s"] = ~aligned_b["t40"]
    knn_b = knn_tables(rep["z"], aligned_b, ks=(5,))
    np.testing.assert_allclose(knn_a["distance"], knn_b["distance"])
    assert set(KS) == {5, 10, 20, 30}


def test_cross_period_match_never_same_instance_or_same_period():
    from roller.nba_8040_reverse_features.deep_quant.knn_study import cross_period_match
    from roller.nba_8040_reverse_features.deep_quant.space import representation
    from roller.nba_8040_reverse_features.deep_quant.util import pairwise_euclidean
    from roller.nba_8040_reverse_features.locks import cross_period_matches_path

    features = pd.read_parquet(features_path())
    labels = pd.read_parquet(labels_path())
    rep = representation(features, ["entry_bid_cents", "pregame_cents", "bought_margin"], kind="complete_columns")
    aligned = rep["meta"].copy()
    labs = labels.set_index("instance_id").loc[aligned["instance_id"]]
    aligned["t40"] = labs["t40"].to_numpy()
    aligned["s"] = labs["s"].to_numpy()
    dist = pairwise_euclidean(rep["z"])
    matches = cross_period_match(dist, aligned, k=5)
    assert (matches["instance_id"] != matches["neighbor_id"]).all()
    assert (matches["source_period"] != matches["match_period"]).all()
    if cross_period_matches_path().is_file():
        written = pd.read_parquet(cross_period_matches_path())
        assert (written["instance_id"] != written["neighbor_id"]).all()
        assert (written["source_period"] != written["match_period"]).all()


def test_null_seed_and_manifest_are_fixed():
    from roller.nba_8040_reverse_features.deep_quant.util import NULL_SEED, PERMUTATIONS, KS
    from roller.nba_8040_reverse_features.locks import reports_dir

    assert NULL_SEED == 80
    assert PERMUTATIONS == 100
    assert KS == (5, 10, 20, 30)
    manifest = reports_dir() / "PCA_FEATURE_MANIFEST.json"
    if not manifest.is_file():
        pytest.skip("deep quant not built")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["seeds"]["null"] == 80
    assert payload["k_values"] == [5, 10, 20, 30]
    assert "t40" not in payload["primary_features"]
    assert "period_q2" not in payload["primary_features"]
    splits = pd.read_parquet(features_path())["dataset_split"].value_counts().to_dict()
    assert splits == {"VALIDATION": 248, "IN_SAMPLE": 236, "OOS": 120}


def test_deep_quant_package_does_not_write_production_paths():
    text = "\n".join(path.read_text(encoding="utf-8") for path in (PKG / "deep_quant").rglob("*.py"))
    assert "to_parquet(features_path()" not in text
    assert "to_parquet(labels_path()" not in text
    assert "book_path().write" not in text
    assert "BOOK.write" not in text
