"""FIRST77 asked-four locks. Integers are the authority.

Same clock slices as Texas FIRST80 / FIRST75. Different τ. TABLES.md has
no FIRST77. Reconstructs from first77_asked_six.csv. No warehouse rescan
at serve time.
"""

from __future__ import annotations

from roller.choosin_texas.locks import Barrier55Lock, PartitionLock

# Measured asked-six FIRST77 ledger. Not TABLES.md.
PARTITIONS_77: tuple[PartitionLock, ...] = (
    PartitionLock(
        partition_id="nba_2q",
        sport="nba",
        sport_label="NBA",
        slice="Q2",
        slice_label="2Q",
        csv_sport="NBA",
        csv_slice="Q2",
        n=324,
        W=250,
        L=74,
        win_no=218,
        win_t40=32,
        lose_no=1,
        lose_t40=73,
    ),
    PartitionLock(
        partition_id="nba_3q",
        sport="nba",
        sport_label="NBA",
        slice="Q3",
        slice_label="3Q",
        csv_sport="NBA",
        csv_slice="Q3",
        n=281,
        W=223,
        L=58,
        win_no=196,
        win_t40=27,
        lose_no=0,
        lose_t40=58,
    ),
    PartitionLock(
        partition_id="ncaab_h1_2",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H1_2",
        slice_label="1H second 10",
        csv_sport="NCAAB",
        csv_slice="H1_2",
        n=188,
        W=153,
        L=35,
        win_no=131,
        win_t40=22,
        lose_no=0,
        lose_t40=35,
    ),
    PartitionLock(
        partition_id="ncaab_h2_1",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H2_1",
        slice_label="2H first 10",
        csv_sport="NCAAB",
        csv_slice="H2_1",
        n=140,
        W=120,
        L=20,
        win_no=109,
        win_t40=11,
        lose_no=0,
        lose_t40=20,
    ),
)

POOL_N_77 = 933
POOL_W_77 = 746
POOL_L_77 = 187
POOL_CELLS_77 = (654, 92, 1, 186)
POOL_ROLE_77 = "derived_four"

ASKED_SIX_N_77 = 1158
ASKED_SIX_CELLS_77 = (813, 114, 1, 230)
WNBA_UNION_N_77 = 225
WNBA_UNION_CELLS_77 = (159, 22, 0, 44)

# Complement only. Not Texas (77) partitions.
WNBA_PARTITIONS_77: tuple[PartitionLock, ...] = (
    PartitionLock(
        partition_id="wnba_2q",
        sport="wnba",
        sport_label="WNBA",
        slice="Q2",
        slice_label="2Q",
        csv_sport="WNBA",
        csv_slice="Q2",
        n=119,
        W=97,
        L=22,
        win_no=82,
        win_t40=15,
        lose_no=0,
        lose_t40=22,
    ),
    PartitionLock(
        partition_id="wnba_3q",
        sport="wnba",
        sport_label="WNBA",
        slice="Q3",
        slice_label="3Q",
        csv_sport="WNBA",
        csv_slice="Q3",
        n=106,
        W=84,
        L=22,
        win_no=77,
        win_t40=7,
        lose_no=0,
        lose_t40=22,
    ),
)

RULE_77 = "FIRST77"
K_NUMER_77 = 77
K_DENOM_77 = 100
ENTRY_CENTS_77 = 77
GAIN_CENTS_77 = 23
STOP_CENTS_77 = 40
STOP_55_CENTS_77 = 55
ENTRY_CAP_CENTS_77 = 83
BARRIER_STOPS_77: tuple[int, ...] = (25, 30, 35, 45, 50)
PATH_STOPS_77: tuple[int, ...] = (25, 30, 35, 40, 45, 50, 55)
# Extra tile only. Not mixed into PATH_STOPS_77 / ledger_rank.
MID_STOPS_77: tuple[int, ...] = (33, 37, 43, 47)

# FIRST77 asked four, entry yes_bid_close < 83. T55 = post-entry min close ≤ 55.
BARRIER_55_77: tuple[Barrier55Lock, ...] = (
    Barrier55Lock("nba_2q", 321, 3, 248, 73, 175, 73, 1, 72),
    Barrier55Lock("nba_3q", 262, 19, 205, 57, 154, 51, 0, 57),
    Barrier55Lock("ncaab_h1_2", 176, 12, 143, 33, 99, 44, 0, 33),
    Barrier55Lock("ncaab_h2_1", 124, 16, 106, 18, 78, 28, 0, 18),
)

BARRIER_55_POOL_N_77 = 883
BARRIER_55_POOL_EXCL_77 = 50
BARRIER_55_POOL_W_77 = 702
BARRIER_55_POOL_L_77 = 181
BARRIER_55_POOL_CELLS_77 = (506, 196, 1, 180)

BARRIER_CELLS_77: dict[int, dict[str, tuple[int, int, int, int]]] = {
    25: {
        "nba_2q": (233, 17, 1, 73),
        "nba_3q": (210, 13, 0, 58),
        "ncaab_h1_2": (142, 11, 0, 35),
        "ncaab_h2_1": (114, 6, 0, 20),
        "derived_four": (699, 47, 1, 186),
    },
    30: {
        "nba_2q": (231, 19, 1, 73),
        "nba_3q": (208, 15, 0, 58),
        "ncaab_h1_2": (140, 13, 0, 35),
        "ncaab_h2_1": (113, 7, 0, 20),
        "derived_four": (692, 54, 1, 186),
    },
    35: {
        "nba_2q": (225, 25, 1, 73),
        "nba_3q": (205, 18, 0, 58),
        "ncaab_h1_2": (134, 19, 0, 35),
        "ncaab_h2_1": (110, 10, 0, 20),
        "derived_four": (674, 72, 1, 186),
    },
    33: {
        "nba_2q": (229, 21, 1, 73),
        "nba_3q": (208, 15, 0, 58),
        "ncaab_h1_2": (135, 18, 0, 35),
        "ncaab_h2_1": (111, 9, 0, 20),
        "derived_four": (683, 63, 1, 186),
    },
    37: {
        "nba_2q": (220, 30, 1, 73),
        "nba_3q": (202, 21, 0, 58),
        "ncaab_h1_2": (133, 20, 0, 35),
        "ncaab_h2_1": (109, 11, 0, 20),
        "derived_four": (664, 82, 1, 186),
    },
    43: {
        "nba_2q": (212, 38, 1, 73),
        "nba_3q": (193, 30, 0, 58),
        "ncaab_h1_2": (129, 24, 0, 35),
        "ncaab_h2_1": (106, 14, 0, 20),
        "derived_four": (640, 106, 1, 186),
    },
    47: {
        "nba_2q": (203, 47, 1, 73),
        "nba_3q": (188, 35, 0, 58),
        "ncaab_h1_2": (119, 34, 0, 35),
        "ncaab_h2_1": (105, 15, 0, 20),
        "derived_four": (615, 131, 1, 186),
    },
    45: {
        "nba_2q": (207, 43, 1, 73),
        "nba_3q": (191, 32, 0, 58),
        "ncaab_h1_2": (125, 28, 0, 35),
        "ncaab_h2_1": (105, 15, 0, 20),
        "derived_four": (628, 118, 1, 186),
    },
    50: {
        "nba_2q": (198, 52, 1, 73),
        "nba_3q": (181, 42, 0, 58),
        "ncaab_h1_2": (115, 38, 0, 35),
        "ncaab_h2_1": (100, 20, 0, 20),
        "derived_four": (594, 152, 1, 186),
    },
}

NBA_PATH_N_77 = 605
NBA_SURVIVE_N_77 = 415
NBA_T40_N_77 = 190
NBA_SLICE_N_77 = {"Q2": 324, "Q3": 281}
NBA_SLICE_T40_77 = {"Q2": 105, "Q3": 85}
NBA_T40_PERIOD_77 = {
    "Q2": {"Q2": 0, "Q3": 40, "Q4": 62, "OT": 3},
    "Q3": {"Q2": 0, "Q3": 11, "Q4": 69, "OT": 5},
}


def loss_cents_for_stop_77(stop_cents: int) -> int:
    return ENTRY_CENTS_77 - int(stop_cents)


def ladder_cells_77(stop_cents: int, partition_id: str) -> tuple[int, int, int, int]:
    if stop_cents == 40:
        if partition_id == "derived_four":
            return POOL_CELLS_77
        for lock in PARTITIONS_77:
            if lock.partition_id == partition_id:
                return lock.cells
        raise KeyError(partition_id)
    return BARRIER_CELLS_77[int(stop_cents)][partition_id]
