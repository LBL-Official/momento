"""TABLES.md FIRST75 asked-four locks. Integers are the authority.

Same clock slices as Texas FIRST80. Different τ. Not the 936-row book.
Path ladder reconstructs from first75_asked_six.csv. No warehouse rescan
at serve time.
"""

from __future__ import annotations

from roller.choosin_texas.locks import Barrier55Lock, PartitionLock

# docs/research/lebronner/TABLES.md §2 / §7 FIRST75 asked_six, WNBA excluded.
PARTITIONS_75: tuple[PartitionLock, ...] = (
    PartitionLock(
        partition_id="nba_2q",
        sport="nba",
        sport_label="NBA",
        slice="Q2",
        slice_label="2Q",
        csv_sport="NBA",
        csv_slice="Q2",
        n=318,
        W=242,
        L=76,
        win_no=208,
        win_t40=34,
        lose_no=1,
        lose_t40=75,
    ),
    PartitionLock(
        partition_id="nba_3q",
        sport="nba",
        sport_label="NBA",
        slice="Q3",
        slice_label="3Q",
        csv_sport="NBA",
        csv_slice="Q3",
        n=258,
        W=192,
        L=66,
        win_no=167,
        win_t40=25,
        lose_no=0,
        lose_t40=66,
    ),
    PartitionLock(
        partition_id="ncaab_h1_2",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H1_2",
        slice_label="1H second 10",
        csv_sport="NCAAB",
        csv_slice="H1_2",
        n=204,
        W=152,
        L=52,
        win_no=126,
        win_t40=26,
        lose_no=0,
        lose_t40=52,
    ),
    PartitionLock(
        partition_id="ncaab_h2_1",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H2_1",
        slice_label="2H first 10",
        csv_sport="NCAAB",
        csv_slice="H2_1",
        n=133,
        W=110,
        L=23,
        win_no=99,
        win_t40=11,
        lose_no=0,
        lose_t40=23,
    ),
)

POOL_N_75 = 913
POOL_W_75 = 696
POOL_L_75 = 217
POOL_CELLS_75 = (600, 96, 1, 216)
POOL_ROLE_75 = "derived_four"

ASKED_SIX_N_75 = 1126
ASKED_SIX_CELLS_75 = (750, 121, 1, 254)
WNBA_UNION_N_75 = 213
WNBA_UNION_CELLS_75 = (150, 25, 0, 38)

# Complement only. Not Texas (75) partitions.
WNBA_PARTITIONS_75: tuple[PartitionLock, ...] = (
    PartitionLock(
        partition_id="wnba_2q",
        sport="wnba",
        sport_label="WNBA",
        slice="Q2",
        slice_label="2Q",
        csv_sport="WNBA",
        csv_slice="Q2",
        n=128,
        W=105,
        L=23,
        win_no=91,
        win_t40=14,
        lose_no=0,
        lose_t40=23,
    ),
    PartitionLock(
        partition_id="wnba_3q",
        sport="wnba",
        sport_label="WNBA",
        slice="Q3",
        slice_label="3Q",
        csv_sport="WNBA",
        csv_slice="Q3",
        n=85,
        W=70,
        L=15,
        win_no=59,
        win_t40=11,
        lose_no=0,
        lose_t40=15,
    ),
)

RULE_75 = "FIRST75"
K_NUMER_75 = 75
K_DENOM_75 = 100
ENTRY_CENTS_75 = 75
GAIN_CENTS_75 = 25
STOP_CENTS_75 = 40
STOP_55_CENTS_75 = 55
ENTRY_CAP_CENTS_75 = 81
BARRIER_STOPS_75: tuple[int, ...] = (25, 30, 35, 45, 50)
PATH_STOPS_75: tuple[int, ...] = (25, 30, 35, 40, 45, 50, 55)
# Extra tile only. Not mixed into PATH_STOPS_75 / ledger_rank.
MID_STOPS_75: tuple[int, ...] = (33, 37, 43, 47)

# FIRST75 asked four, entry yes_bid_close < 81. T55 = post-entry min close ≤ 55.
BARRIER_55_75: tuple[Barrier55Lock, ...] = (
    Barrier55Lock("nba_2q", 309, 9, 235, 74, 157, 78, 1, 73),
    Barrier55Lock("nba_3q", 241, 17, 179, 62, 130, 49, 0, 62),
    Barrier55Lock("ncaab_h1_2", 193, 11, 146, 47, 91, 55, 0, 47),
    Barrier55Lock("ncaab_h2_1", 125, 8, 103, 22, 71, 32, 0, 22),
)

BARRIER_55_POOL_N_75 = 868
BARRIER_55_POOL_EXCL_75 = 45
BARRIER_55_POOL_W_75 = 663
BARRIER_55_POOL_L_75 = 205
BARRIER_55_POOL_CELLS_75 = (449, 214, 1, 204)

BARRIER_CELLS_75: dict[int, dict[str, tuple[int, int, int, int]]] = {
    25: {
        "nba_2q": (226, 16, 1, 75),
        "nba_3q": (180, 12, 0, 66),
        "ncaab_h1_2": (139, 13, 0, 52),
        "ncaab_h2_1": (106, 4, 0, 23),
        "derived_four": (651, 45, 1, 216),
    },
    30: {
        "nba_2q": (225, 17, 1, 75),
        "nba_3q": (177, 15, 0, 66),
        "ncaab_h1_2": (137, 15, 0, 52),
        "ncaab_h2_1": (104, 6, 0, 23),
        "derived_four": (643, 53, 1, 216),
    },
    35: {
        "nba_2q": (217, 25, 1, 75),
        "nba_3q": (174, 18, 0, 66),
        "ncaab_h1_2": (131, 21, 0, 52),
        "ncaab_h2_1": (102, 8, 0, 23),
        "derived_four": (624, 72, 1, 216),
    },
    33: {
        "nba_2q": (223, 19, 1, 75),
        "nba_3q": (177, 15, 0, 66),
        "ncaab_h1_2": (133, 19, 0, 52),
        "ncaab_h2_1": (103, 7, 0, 23),
        "derived_four": (636, 60, 1, 216),
    },
    37: {
        "nba_2q": (213, 29, 1, 75),
        "nba_3q": (172, 20, 0, 66),
        "ncaab_h1_2": (130, 22, 0, 52),
        "ncaab_h2_1": (99, 11, 0, 23),
        "derived_four": (614, 82, 1, 216),
    },
    43: {
        "nba_2q": (203, 39, 1, 75),
        "nba_3q": (164, 28, 0, 66),
        "ncaab_h1_2": (122, 30, 0, 52),
        "ncaab_h2_1": (94, 16, 0, 23),
        "derived_four": (583, 113, 1, 216),
    },
    47: {
        "nba_2q": (193, 49, 1, 75),
        "nba_3q": (160, 32, 0, 66),
        "ncaab_h1_2": (111, 41, 0, 52),
        "ncaab_h2_1": (91, 19, 0, 23),
        "derived_four": (555, 141, 1, 216),
    },
    45: {
        "nba_2q": (200, 42, 1, 75),
        "nba_3q": (162, 30, 0, 66),
        "ncaab_h1_2": (117, 35, 0, 52),
        "ncaab_h2_1": (92, 18, 0, 23),
        "derived_four": (571, 125, 1, 216),
    },
    50: {
        "nba_2q": (184, 58, 1, 75),
        "nba_3q": (154, 38, 0, 66),
        "ncaab_h1_2": (105, 47, 0, 52),
        "ncaab_h2_1": (88, 22, 0, 23),
        "derived_four": (531, 165, 1, 216),
    },
}

NBA_PATH_N_75 = 576
NBA_SURVIVE_N_75 = 376
NBA_T40_N_75 = 200
NBA_SLICE_N_75 = {"Q2": 318, "Q3": 258}
NBA_SLICE_T40_75 = {"Q2": 109, "Q3": 91}
NBA_T40_PERIOD_75 = {
    "Q2": {"Q2": 2, "Q3": 42, "Q4": 63, "OT": 2},
    "Q3": {"Q2": 0, "Q3": 15, "Q4": 71, "OT": 5},
}


def loss_cents_for_stop_75(stop_cents: int) -> int:
    return ENTRY_CENTS_75 - int(stop_cents)


def ladder_cells_75(stop_cents: int, partition_id: str) -> tuple[int, int, int, int]:
    if stop_cents == 40:
        if partition_id == "derived_four":
            return POOL_CELLS_75
        for lock in PARTITIONS_75:
            if lock.partition_id == partition_id:
                return lock.cells
        raise KeyError(partition_id)
    return BARRIER_CELLS_75[int(stop_cents)][partition_id]
