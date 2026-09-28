"""Asked-six NBA 80/40 population locks. Integers are the authority."""

from __future__ import annotations

from pathlib import Path

from roller.choosin_texas.sources import repo_root

RULE = "FIRST80"
SPORT = "NBA"
SLICES = ("Q2", "Q3")
STOP_CENTS = 40
GAIN_CENTS = 20
LOSS_CENTS = 40

NBA_Q2Q3_N = 604
NBA_Q2Q3_S = 450
NBA_Q2Q3_W_T40 = 55
NBA_Q2Q3_L_T40 = 99
NBA_Q2Q3_BOOK = 2840

NBA_Q2_N = 314
NBA_Q3_N = 290

NBA_Q2_RS_N = 280
NBA_Q2_RS_S = 218
NBA_Q2_RS_W_T40 = 22
NBA_Q2_RS_L_T40 = 40
NBA_Q2_RS_BOOK = 1880

LIBRARY = Path("research/nba_8040_reverse_features")


def library_root() -> Path:
    return repo_root() / LIBRARY


def features_path() -> Path:
    return library_root() / "features" / "pre80.parquet"


def labels_path() -> Path:
    return library_root() / "labels" / "outcomes.parquet"


def event_path_path() -> Path:
    return library_root() / "reports" / "event_path.parquet"


def reports_dir() -> Path:
    return library_root() / "reports"


def figures_dir() -> Path:
    return reports_dir() / "figures"


def matrix_path() -> Path:
    return library_root() / "features" / "pre80_matrix.parquet"


def pca_scores_path() -> Path:
    return library_root() / "features" / "pca_scores.parquet"


def pca_loadings_path() -> Path:
    return library_root() / "features" / "pca_loadings.parquet"


def knn_neighbors_path() -> Path:
    return library_root() / "features" / "knn_neighbors.parquet"


def cross_period_matches_path() -> Path:
    return library_root() / "features" / "cross_period_matches.parquet"


# Frozen hashes of the locked v1 store and the Choosin Texas book.
# Deep-quant writes additive artifacts only. These files must not change.
PRE80_SHA256 = "32469d086b8882cc7fce4534934ef527ebddee4f760864e8048c2946ae10e154"
LABELS_SHA256 = "ce9fcdb53cea273eaf74603021f64abd15fa0f3d96ce822c412e1a0ec1b73932"
BOOK_SHA256 = "4da5fdd3a48d2a5513ab6e9452657a790514fbef389a05d0385cfaba009b8cf6"
BOOK_RELATIVE = Path("research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json")


def book_path() -> Path:
    return repo_root() / BOOK_RELATIVE
