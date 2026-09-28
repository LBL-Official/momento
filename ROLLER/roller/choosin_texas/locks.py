"""TABLES.md FIRST80 asked-four locks. Integers are the authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PartitionLock:
    partition_id: str
    sport: str
    sport_label: str
    slice: str
    slice_label: str
    csv_sport: str
    csv_slice: str
    n: int
    W: int
    L: int
    win_no: int
    win_t40: int
    lose_no: int
    lose_t40: int

    @property
    def cells(self) -> tuple[int, int, int, int]:
        return (self.win_no, self.win_t40, self.lose_no, self.lose_t40)

    def as_dict(self) -> dict[str, Any]:
        return {
            "partition_id": self.partition_id,
            "sport": self.sport,
            "sport_label": self.sport_label,
            "slice": self.slice,
            "slice_label": self.slice_label,
            "csv_sport": self.csv_sport,
            "csv_slice": self.csv_slice,
            "n": self.n,
            "W": self.W,
            "L": self.L,
            "cells": {
                "W_and_not_T40": self.win_no,
                "W_and_T40": self.win_t40,
                "L_and_not_T40": self.lose_no,
                "L_and_T40": self.lose_t40,
            },
        }


# docs/research/lebronner/TABLES.md §3 / §7 FIRST80 asked_six, WNBA excluded.
PARTITIONS: tuple[PartitionLock, ...] = (
    PartitionLock(
        partition_id="nba_2q",
        sport="nba",
        sport_label="NBA",
        slice="Q2",
        slice_label="2Q",
        csv_sport="NBA",
        csv_slice="Q2",
        n=314,
        W=267,
        L=47,
        win_no=239,
        win_t40=28,
        lose_no=0,
        lose_t40=47,
    ),
    PartitionLock(
        partition_id="nba_3q",
        sport="nba",
        sport_label="NBA",
        slice="Q3",
        slice_label="3Q",
        csv_sport="NBA",
        csv_slice="Q3",
        n=290,
        W=238,
        L=52,
        win_no=211,
        win_t40=27,
        lose_no=0,
        lose_t40=52,
    ),
    PartitionLock(
        partition_id="ncaab_h1_2",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H1_2",
        slice_label="1H second 10",
        csv_sport="NCAAB",
        csv_slice="H1_2",
        n=193,
        W=163,
        L=30,
        win_no=142,
        win_t40=21,
        lose_no=0,
        lose_t40=30,
    ),
    PartitionLock(
        partition_id="ncaab_h2_1",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H2_1",
        slice_label="2H first 10",
        csv_sport="NCAAB",
        csv_slice="H2_1",
        n=139,
        W=118,
        L=21,
        win_no=108,
        win_t40=10,
        lose_no=0,
        lose_t40=21,
    ),
)

POOL_N = 936
POOL_W = 786
POOL_L = 150
POOL_CELLS = (700, 86, 0, 150)
POOL_ROLE = "derived_four"

ASKED_SIX_N = 1182
ASKED_SIX_CELLS = (883, 108, 0, 191)
WNBA_UNION_N = 246
WNBA_UNION_CELLS = (183, 22, 0, 41)

RULE = "FIRST80"
K_NUMER = 80
K_DENOM = 100
ENTRY_CENTS = 80
GAIN_CENTS = 20
STOP_CENTS = 40
STOP_55_CENTS = 55
ENTRY_CAP_CENTS = 86
# Full-book ladder on N=936. 55 stays the entry<86 book.
BARRIER_STOPS: tuple[int, ...] = (25, 30, 35, 45, 50)
PATH_STOPS: tuple[int, ...] = (25, 30, 35, 40, 45, 50, 55)
# Extra tile only. Not mixed into PATH_STOPS / ledger_rank.
MID_STOPS: tuple[int, ...] = (33, 37, 43, 47)
EV_BAR_FULL_CENTS = 8


@dataclass(frozen=True)
class Barrier55Lock:
    partition_id: str
    n: int
    excluded_hit_86: int
    W: int
    L: int
    win_no: int
    win_t55: int
    lose_no: int
    lose_t55: int

    @property
    def cells(self) -> tuple[int, int, int, int]:
        return (self.win_no, self.win_t55, self.lose_no, self.lose_t55)


# FIRST80 asked four, entry yes_bid_close < 86. T55 = post-entry min close ≤ 55.
# Reconstructs from asked-six CSV. Does not rescan the warehouse.
BARRIER_55: tuple[Barrier55Lock, ...] = (
    Barrier55Lock("nba_2q", 311, 3, 265, 46, 202, 63, 0, 46),
    Barrier55Lock("nba_3q", 272, 18, 222, 50, 177, 45, 0, 50),
    Barrier55Lock("ncaab_h1_2", 187, 6, 158, 29, 115, 43, 0, 29),
    Barrier55Lock("ncaab_h2_1", 135, 4, 114, 21, 85, 29, 0, 21),
)

BARRIER_55_POOL_N = 905
BARRIER_55_POOL_EXCL = 31
BARRIER_55_POOL_W = 759
BARRIER_55_POOL_L = 146
BARRIER_55_POOL_CELLS = (579, 180, 0, 146)

# Four-cells W∩¬Tx / W∩Tx / L∩¬Tx / L∩Tx on the full 936 book.
# T40 cells stay on PartitionLock / POOL_CELLS. Reconstruct from CSV min-close.
BARRIER_CELLS: dict[int, dict[str, tuple[int, int, int, int]]] = {
    25: {
        "nba_2q": (252, 15, 0, 47),
        "nba_3q": (226, 12, 0, 52),
        "ncaab_h1_2": (155, 8, 0, 30),
        "ncaab_h2_1": (113, 5, 0, 21),
        "derived_four": (746, 40, 0, 150),
    },
    30: {
        "nba_2q": (249, 18, 0, 47),
        "nba_3q": (223, 15, 0, 52),
        "ncaab_h1_2": (152, 11, 0, 30),
        "ncaab_h2_1": (112, 6, 0, 21),
        "derived_four": (736, 50, 0, 150),
    },
    35: {
        "nba_2q": (245, 22, 0, 47),
        "nba_3q": (220, 18, 0, 52),
        "ncaab_h1_2": (146, 17, 0, 30),
        "ncaab_h2_1": (110, 8, 0, 21),
        "derived_four": (721, 65, 0, 150),
    },
    33: {
        "nba_2q": (247, 20, 0, 47),
        "nba_3q": (222, 16, 0, 52),
        "ncaab_h1_2": (147, 16, 0, 30),
        "ncaab_h2_1": (111, 7, 0, 21),
        "derived_four": (727, 59, 0, 150),
    },
    37: {
        "nba_2q": (243, 24, 0, 47),
        "nba_3q": (218, 20, 0, 52),
        "ncaab_h1_2": (144, 19, 0, 30),
        "ncaab_h2_1": (109, 9, 0, 21),
        "derived_four": (714, 72, 0, 150),
    },
    43: {
        "nba_2q": (235, 32, 0, 47),
        "nba_3q": (210, 28, 0, 52),
        "ncaab_h1_2": (141, 22, 0, 30),
        "ncaab_h2_1": (106, 12, 0, 21),
        "derived_four": (692, 94, 0, 150),
    },
    47: {
        "nba_2q": (224, 43, 0, 47),
        "nba_3q": (207, 31, 0, 52),
        "ncaab_h1_2": (131, 32, 0, 30),
        "ncaab_h2_1": (105, 13, 0, 21),
        "derived_four": (667, 119, 0, 150),
    },
    45: {
        "nba_2q": (229, 38, 0, 47),
        "nba_3q": (208, 30, 0, 52),
        "ncaab_h1_2": (138, 25, 0, 30),
        "ncaab_h2_1": (105, 13, 0, 21),
        "derived_four": (680, 106, 0, 150),
    },
    50: {
        "nba_2q": (221, 46, 0, 47),
        "nba_3q": (202, 36, 0, 52),
        "ncaab_h1_2": (126, 37, 0, 30),
        "ncaab_h2_1": (101, 17, 0, 21),
        "derived_four": (650, 136, 0, 150),
    },
}

# FIRST80 derived four, full N=936. T60 = post-entry min close ≤ 60.
# Same book as 80/40. Not the entry<86 80/55 book. Not a PATH_STOPS rung.
# Reconstructs from asked-six CSV. Does not rescan the warehouse.
STOP_60_CENTS = 60
BARRIER_60: dict[str, tuple[int, int, int, int]] = {
    "nba_2q": (188, 79, 0, 47),
    "nba_3q": (186, 52, 0, 52),
    "ncaab_h1_2": (109, 54, 0, 30),
    "ncaab_h2_1": (85, 33, 0, 21),
    "derived_four": (568, 218, 0, 150),
}

# 55 and 65 on the same full 936 book. Not the entry<86 80/55 book.
# Four-cells are W∩¬Tx / W∩Tx / L∩¬Tx / L∩Tx. s_L = 0.
BAND_STOPS_60: tuple[int, ...] = (55, 60, 65)
BARRIER_55_FULL: dict[str, tuple[int, int, int, int]] = {
    "nba_2q": (204, 63, 0, 47),
    "nba_3q": (192, 46, 0, 52),
    "ncaab_h1_2": (118, 45, 0, 30),
    "ncaab_h2_1": (89, 29, 0, 21),
    "derived_four": (603, 183, 0, 150),
}
BARRIER_65: dict[str, tuple[int, int, int, int]] = {
    "nba_2q": (168, 99, 0, 47),
    "nba_3q": (167, 71, 0, 52),
    "ncaab_h1_2": (98, 65, 0, 30),
    "ncaab_h2_1": (82, 36, 0, 21),
    "derived_four": (515, 271, 0, 150),
}

# First ≤65 close still 61–65, versus already ≤60 on that bar.
# First ≤60 close still 56–60, versus already ≤55 on that bar.
# Derived four only. Candle path ≠ fill.
GAP_65_POOL = {
    "n": 421,
    "separate_61_65": 306,
    "same_bar_le60": 115,
    "separate_then_t60": 253,
    "separate_survive_60": 53,
}
GAP_65_SLICE = {
    "nba_2q": {"n": 146, "separate_61_65": 111, "same_bar_le60": 35, "separate_then_t60": 91, "separate_survive_60": 20},
    "nba_3q": {"n": 123, "separate_61_65": 89, "same_bar_le60": 34, "separate_then_t60": 70, "separate_survive_60": 19},
    "ncaab_h1_2": {"n": 95, "separate_61_65": 70, "same_bar_le60": 25, "separate_then_t60": 59, "separate_survive_60": 11},
    "ncaab_h2_1": {"n": 57, "separate_61_65": 36, "same_bar_le60": 21, "separate_then_t60": 33, "separate_survive_60": 3},
}
GAP_60_POOL = {
    "n": 368,
    "separate_56_60": 251,
    "same_bar_le55": 117,
    "continued_to_55": 333,
    "never_55": 35,
}
GAP_60_SLICE = {
    "nba_2q": {"n": 126, "separate_56_60": 98, "same_bar_le55": 28, "continued_to_55": 110, "never_55": 16},
    "nba_3q": {"n": 104, "separate_56_60": 65, "same_bar_le55": 39, "continued_to_55": 98, "never_55": 6},
    "ncaab_h1_2": {"n": 84, "separate_56_60": 56, "same_bar_le55": 28, "continued_to_55": 75, "never_55": 9},
    "ncaab_h2_1": {"n": 54, "separate_56_60": 32, "same_bar_le55": 22, "continued_to_55": 50, "never_55": 4},
}

# NBA first ≤60 close, modeled PBP snap. Same bins as the T40 clock.
NBA_T60_N = {"Q2": 126, "Q3": 104}
NBA_T60_PERIOD = {
    "Q2": {"Q2": 21, "Q3": 66, "Q4": 38, "OT": 1},
    "Q3": {"Q2": 0, "Q3": 40, "Q4": 64, "OT": 0},
}
NBA_T60_BINS = {
    "Q2": {
        ("Q2", "12:00-9:01"): 0,
        ("Q2", "9:00-6:01"): 3,
        ("Q2", "6:00-3:01"): 5,
        ("Q2", "3:00-0:00"): 13,
        ("Q3", "12:00-9:01"): 13,
        ("Q3", "9:00-6:01"): 21,
        ("Q3", "6:00-3:01"): 20,
        ("Q3", "3:00-0:00"): 12,
        ("Q4", "12:00-9:01"): 14,
        ("Q4", "9:00-6:01"): 10,
        ("Q4", "6:00-3:01"): 9,
        ("Q4", "3:00-0:00"): 5,
        ("OT", "12:00-9:01"): 0,
        ("OT", "9:00-6:01"): 0,
        ("OT", "6:00-3:01"): 1,
        ("OT", "3:00-0:00"): 0,
    },
    "Q3": {
        ("Q2", "12:00-9:01"): 0,
        ("Q2", "9:00-6:01"): 0,
        ("Q2", "6:00-3:01"): 0,
        ("Q2", "3:00-0:00"): 0,
        ("Q3", "12:00-9:01"): 0,
        ("Q3", "9:00-6:01"): 5,
        ("Q3", "6:00-3:01"): 7,
        ("Q3", "3:00-0:00"): 28,
        ("Q4", "12:00-9:01"): 18,
        ("Q4", "9:00-6:01"): 20,
        ("Q4", "6:00-3:01"): 11,
        ("Q4", "3:00-0:00"): 15,
        ("OT", "12:00-9:01"): 0,
        ("OT", "9:00-6:01"): 0,
        ("OT", "6:00-3:01"): 0,
        ("OT", "3:00-0:00"): 0,
    },
}
NBA_T60_REMAINING_SUM = {
    "Q2": {"Q2": 3304, "Q3": 23629, "Q4": 16384, "OT": 300},
    "Q3": {"Q3": 5621, "Q4": 24713},
}

NBA_PATH_N = 604
NBA_SURVIVE_N = 450
NBA_T40_N = 154
NBA_T40_WIN_N = 55
NBA_T40_LOSE_N = 99
NBA_SLICE_N = {"Q2": 314, "Q3": 290}
NBA_SLICE_T40 = {"Q2": 75, "Q3": 79}
NBA_SLICE_SURVIVE = {"Q2": 239, "Q3": 211}
NBA_SLICE_T40_WIN = {"Q2": 28, "Q3": 27}
NBA_SLICE_T40_LOSE = {"Q2": 47, "Q3": 52}
NBA_T40_PERIOD = {
    "Q2": {"Q2": 1, "Q3": 26, "Q4": 46, "OT": 2},
    "Q3": {"Q2": 0, "Q3": 8, "Q4": 64, "OT": 7},
}


def loss_cents_for_stop(stop_cents: int) -> int:
    return ENTRY_CENTS - int(stop_cents)


def ladder_cells(stop_cents: int, partition_id: str) -> tuple[int, int, int, int]:
    if stop_cents == 40:
        if partition_id == "derived_four":
            return POOL_CELLS
        for lock in PARTITIONS:
            if lock.partition_id == partition_id:
                return lock.cells
        raise KeyError(partition_id)
    return BARRIER_CELLS[int(stop_cents)][partition_id]
