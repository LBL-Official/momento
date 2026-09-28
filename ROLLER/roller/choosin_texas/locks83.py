"""FIRST83 asked-four + asked-six locks. Integers are the authority.

Same clock slices as Texas FIRST80 / FIRST75 / FIRST77. Different τ.
TABLES.md has no FIRST83. Reconstructs from first83_asked_six.csv.
No warehouse rescan at serve time. Not a live 80/81/83 rule.
"""

from __future__ import annotations

from roller.choosin_texas.locks import Barrier55Lock, PartitionLock

PARTITIONS_83: tuple[PartitionLock, ...] = (
    PartitionLock(
        partition_id="nba_2q",
        sport="nba",
        sport_label="NBA",
        slice="Q2",
        slice_label="2Q",
        csv_sport="NBA",
        csv_slice="Q2",
        n=299,
        W=264,
        L=35,
        win_no=245,
        win_t40=19,
        lose_no=0,
        lose_t40=35,
    ),
    PartitionLock(
        partition_id="nba_3q",
        sport="nba",
        sport_label="NBA",
        slice="Q3",
        slice_label="3Q",
        csv_sport="NBA",
        csv_slice="Q3",
        n=318,
        W=275,
        L=43,
        win_no=254,
        win_t40=21,
        lose_no=0,
        lose_t40=43,
    ),
    PartitionLock(
        partition_id="ncaab_h1_2",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H1_2",
        slice_label="1H second 10",
        csv_sport="NCAAB",
        csv_slice="H1_2",
        n=198,
        W=175,
        L=23,
        win_no=159,
        win_t40=16,
        lose_no=0,
        lose_t40=23,
    ),
    PartitionLock(
        partition_id="ncaab_h2_1",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H2_1",
        slice_label="2H first 10",
        csv_sport="NCAAB",
        csv_slice="H2_1",
        n=158,
        W=137,
        L=21,
        win_no=128,
        win_t40=9,
        lose_no=0,
        lose_t40=21,
    ),
)

POOL_N_83 = 973
POOL_W_83 = 851
POOL_L_83 = 122
POOL_CELLS_83 = (786, 65, 0, 122)
POOL_ROLE_83 = "derived_four"

ASKED_SIX_N_83 = 1243
ASKED_SIX_W_83 = 1088
ASKED_SIX_L_83 = 155
ASKED_SIX_CELLS_83 = (992, 96, 0, 155)
WNBA_UNION_N_83 = 270
WNBA_UNION_CELLS_83 = (206, 31, 0, 33)

WNBA_PARTITIONS_83: tuple[PartitionLock, ...] = (
    PartitionLock(
        partition_id="wnba_2q",
        sport="wnba",
        sport_label="WNBA",
        slice="Q2",
        slice_label="2Q",
        csv_sport="WNBA",
        csv_slice="Q2",
        n=135,
        W=122,
        L=13,
        win_no=99,
        win_t40=23,
        lose_no=0,
        lose_t40=13,
    ),
    PartitionLock(
        partition_id="wnba_3q",
        sport="wnba",
        sport_label="WNBA",
        slice="Q3",
        slice_label="3Q",
        csv_sport="WNBA",
        csv_slice="Q3",
        n=135,
        W=115,
        L=20,
        win_no=107,
        win_t40=8,
        lose_no=0,
        lose_t40=20,
    ),
)

ASKED_SIX_PARTITIONS_83: tuple[PartitionLock, ...] = PARTITIONS_83 + WNBA_PARTITIONS_83

RULE_83 = "FIRST83"
K_NUMER_83 = 83
K_DENOM_83 = 100
ENTRY_CENTS_83 = 83
GAIN_CENTS_83 = 17
STOP_CENTS_83 = 40
STOP_55_CENTS_83 = 55
ENTRY_CAP_CENTS_83 = 89
BARRIER_STOPS_83: tuple[int, ...] = (25, 30, 35, 45, 50)
PATH_STOPS_83: tuple[int, ...] = (25, 30, 35, 40, 45, 50, 55)
MID_STOPS_83: tuple[int, ...] = (33, 37, 43, 47)
BARRIER_55_83: tuple[Barrier55Lock, ...] = (
    Barrier55Lock("nba_2q", 299, 0, 264, 35, 213, 51, 0, 35),
    Barrier55Lock("nba_3q", 314, 4, 271, 43, 229, 42, 0, 43),
    Barrier55Lock("ncaab_h1_2", 193, 5, 170, 23, 132, 38, 0, 23),
    Barrier55Lock("ncaab_h2_1", 153, 5, 133, 20, 110, 23, 0, 20),
)

BARRIER_55_POOL_N_83 = 959
BARRIER_55_POOL_EXCL_83 = 14
BARRIER_55_POOL_W_83 = 838
BARRIER_55_POOL_L_83 = 121
BARRIER_55_POOL_CELLS_83 = (684, 154, 0, 121)
BARRIER_CELLS_83: dict[int, dict[str, tuple[int, int, int, int]]] = {
    25: {
        "nba_2q": (256, 8, 0, 35),
        "nba_3q": (264, 11, 0, 43),
        "ncaab_h1_2": (169, 6, 0, 23),
        "ncaab_h2_1": (134, 3, 0, 21),
        "derived_four": (823, 28, 0, 122),
    },
    30: {
        "nba_2q": (253, 11, 0, 35),
        "nba_3q": (260, 15, 0, 43),
        "ncaab_h1_2": (167, 8, 0, 23),
        "ncaab_h2_1": (132, 5, 0, 21),
        "derived_four": (812, 39, 0, 122),
    },
    33: {
        "nba_2q": (251, 13, 0, 35),
        "nba_3q": (259, 16, 0, 43),
        "ncaab_h1_2": (162, 13, 0, 23),
        "ncaab_h2_1": (132, 5, 0, 21),
        "derived_four": (804, 47, 0, 122),
    },
    35: {
        "nba_2q": (250, 14, 0, 35),
        "nba_3q": (259, 16, 0, 43),
        "ncaab_h1_2": (161, 14, 0, 23),
        "ncaab_h2_1": (131, 6, 0, 21),
        "derived_four": (801, 50, 0, 122),
    },
    37: {
        "nba_2q": (248, 16, 0, 35),
        "nba_3q": (259, 16, 0, 43),
        "ncaab_h1_2": (160, 15, 0, 23),
        "ncaab_h2_1": (130, 7, 0, 21),
        "derived_four": (797, 54, 0, 122),
    },
    43: {
        "nba_2q": (243, 21, 0, 35),
        "nba_3q": (252, 23, 0, 43),
        "ncaab_h1_2": (159, 16, 0, 23),
        "ncaab_h2_1": (124, 13, 0, 21),
        "derived_four": (778, 73, 0, 122),
    },
    45: {
        "nba_2q": (236, 28, 0, 35),
        "nba_3q": (251, 24, 0, 43),
        "ncaab_h1_2": (155, 20, 0, 23),
        "ncaab_h2_1": (123, 14, 0, 21),
        "derived_four": (765, 86, 0, 122),
    },
    47: {
        "nba_2q": (231, 33, 0, 35),
        "nba_3q": (249, 26, 0, 43),
        "ncaab_h1_2": (149, 26, 0, 23),
        "ncaab_h2_1": (123, 14, 0, 21),
        "derived_four": (752, 99, 0, 122),
    },
    50: {
        "nba_2q": (225, 39, 0, 35),
        "nba_3q": (243, 32, 0, 43),
        "ncaab_h1_2": (143, 32, 0, 23),
        "ncaab_h2_1": (121, 16, 0, 21),
        "derived_four": (732, 119, 0, 122),
    },
}

BARRIER_CELLS_ASKED_83: dict[int, dict[str, tuple[int, int, int, int]]] = {
    25: {
        "nba_2q": (256, 8, 0, 35),
        "nba_3q": (264, 11, 0, 43),
        "ncaab_h1_2": (169, 6, 0, 23),
        "ncaab_h2_1": (134, 3, 0, 21),
        "wnba_2q": (109, 13, 0, 13),
        "wnba_3q": (111, 4, 0, 20),
        "asked_six": (1043, 45, 0, 155),
    },
    30: {
        "nba_2q": (253, 11, 0, 35),
        "nba_3q": (260, 15, 0, 43),
        "ncaab_h1_2": (167, 8, 0, 23),
        "ncaab_h2_1": (132, 5, 0, 21),
        "wnba_2q": (106, 16, 0, 13),
        "wnba_3q": (110, 5, 0, 20),
        "asked_six": (1028, 60, 0, 155),
    },
    33: {
        "nba_2q": (251, 13, 0, 35),
        "nba_3q": (259, 16, 0, 43),
        "ncaab_h1_2": (162, 13, 0, 23),
        "ncaab_h2_1": (132, 5, 0, 21),
        "wnba_2q": (104, 18, 0, 13),
        "wnba_3q": (108, 7, 0, 20),
        "asked_six": (1016, 72, 0, 155),
    },
    35: {
        "nba_2q": (250, 14, 0, 35),
        "nba_3q": (259, 16, 0, 43),
        "ncaab_h1_2": (161, 14, 0, 23),
        "ncaab_h2_1": (131, 6, 0, 21),
        "wnba_2q": (102, 20, 0, 13),
        "wnba_3q": (108, 7, 0, 20),
        "asked_six": (1011, 77, 0, 155),
    },
    37: {
        "nba_2q": (248, 16, 0, 35),
        "nba_3q": (259, 16, 0, 43),
        "ncaab_h1_2": (160, 15, 0, 23),
        "ncaab_h2_1": (130, 7, 0, 21),
        "wnba_2q": (101, 21, 0, 13),
        "wnba_3q": (108, 7, 0, 20),
        "asked_six": (1006, 82, 0, 155),
    },
    40: {
        "nba_2q": (245, 19, 0, 35),
        "nba_3q": (254, 21, 0, 43),
        "ncaab_h1_2": (159, 16, 0, 23),
        "ncaab_h2_1": (128, 9, 0, 21),
        "wnba_2q": (99, 23, 0, 13),
        "wnba_3q": (107, 8, 0, 20),
        "asked_six": (992, 96, 0, 155),
    },
    43: {
        "nba_2q": (243, 21, 0, 35),
        "nba_3q": (252, 23, 0, 43),
        "ncaab_h1_2": (159, 16, 0, 23),
        "ncaab_h2_1": (124, 13, 0, 21),
        "wnba_2q": (98, 24, 0, 13),
        "wnba_3q": (107, 8, 0, 20),
        "asked_six": (983, 105, 0, 155),
    },
    45: {
        "nba_2q": (236, 28, 0, 35),
        "nba_3q": (251, 24, 0, 43),
        "ncaab_h1_2": (155, 20, 0, 23),
        "ncaab_h2_1": (123, 14, 0, 21),
        "wnba_2q": (98, 24, 0, 13),
        "wnba_3q": (107, 8, 0, 20),
        "asked_six": (970, 118, 0, 155),
    },
    47: {
        "nba_2q": (231, 33, 0, 35),
        "nba_3q": (249, 26, 0, 43),
        "ncaab_h1_2": (149, 26, 0, 23),
        "ncaab_h2_1": (123, 14, 0, 21),
        "wnba_2q": (97, 25, 0, 13),
        "wnba_3q": (107, 8, 0, 20),
        "asked_six": (956, 132, 0, 155),
    },
    50: {
        "nba_2q": (225, 39, 0, 35),
        "nba_3q": (243, 32, 0, 43),
        "ncaab_h1_2": (143, 32, 0, 23),
        "ncaab_h2_1": (121, 16, 0, 21),
        "wnba_2q": (95, 27, 0, 13),
        "wnba_3q": (104, 11, 0, 20),
        "asked_six": (931, 157, 0, 155),
    },
}

BARRIER_55_ASKED_83: dict[str, tuple[int, int, int, int, tuple[int, int, int, int]]] = {
    "nba_2q": (299, 0, 264, 35, (213, 51, 0, 35)),
    "nba_3q": (314, 4, 271, 43, (229, 42, 0, 43)),
    "ncaab_h1_2": (193, 5, 170, 23, (132, 38, 0, 23)),
    "ncaab_h2_1": (153, 5, 133, 20, (110, 23, 0, 20)),
    "wnba_2q": (133, 2, 120, 13, (90, 30, 0, 13)),
    "wnba_3q": (124, 11, 104, 20, (89, 15, 0, 20)),
    "asked_six": (1216, 27, 1062, 154, (863, 199, 0, 154)),
}

OOS_N_83: dict[str, object] = {
    "train": 436,
    "train_window": ('2025-05-22', '2025-12-31'),
    "validation": 622,
    "validation_window": ('2026-01-01', '2026-07-15'),
    "test": 185,
    "test_window": ('2026-03-16', '2026-08-30'),
    "slices": {
        "nba_2q": {"train": 118, "validation": 122, "test": 59},
        "nba_3q": {"train": 119, "validation": 139, "test": 60},
        "ncaab_h1_2": {"train": 42, "validation": 150, "test": 6},
        "ncaab_h2_1": {"train": 29, "validation": 120, "test": 9},
        "wnba_2q": {"train": 59, "validation": 52, "test": 24},
        "wnba_3q": {"train": 69, "validation": 39, "test": 27},
    },
}

OOS_CELLS_83: dict[str, dict[str, dict[int | str, object]]] = {
    "train": {
        "nba_2q": {
            "n": 118,
            25: (99, 3, 0, 16),
            30: (97, 5, 0, 16),
            33: (97, 5, 0, 16),
            35: (97, 5, 0, 16),
            37: (97, 5, 0, 16),
            40: (96, 6, 0, 16),
            43: (95, 7, 0, 16),
            45: (91, 11, 0, 16),
            47: (89, 13, 0, 16),
            50: (89, 13, 0, 16),
            55: {"n": 118, "excluded": 0, "W": 102, "L": 16, "cells": (82, 20, 0, 16)},
        },
        "nba_3q": {
            "n": 119,
            25: (100, 4, 0, 15),
            30: (98, 6, 0, 15),
            33: (97, 7, 0, 15),
            35: (97, 7, 0, 15),
            37: (97, 7, 0, 15),
            40: (96, 8, 0, 15),
            43: (94, 10, 0, 15),
            45: (94, 10, 0, 15),
            47: (93, 11, 0, 15),
            50: (91, 13, 0, 15),
            55: {"n": 119, "excluded": 0, "W": 104, "L": 15, "cells": (86, 18, 0, 15)},
        },
        "ncaab_h1_2": {
            "n": 42,
            25: (36, 1, 0, 5),
            30: (36, 1, 0, 5),
            33: (35, 2, 0, 5),
            35: (34, 3, 0, 5),
            37: (34, 3, 0, 5),
            40: (34, 3, 0, 5),
            43: (34, 3, 0, 5),
            45: (32, 5, 0, 5),
            47: (32, 5, 0, 5),
            50: (32, 5, 0, 5),
            55: {"n": 42, "excluded": 0, "W": 37, "L": 5, "cells": (29, 8, 0, 5)},
        },
        "ncaab_h2_1": {
            "n": 29,
            25: (23, 1, 0, 5),
            30: (23, 1, 0, 5),
            33: (23, 1, 0, 5),
            35: (23, 1, 0, 5),
            37: (22, 2, 0, 5),
            40: (21, 3, 0, 5),
            43: (21, 3, 0, 5),
            45: (21, 3, 0, 5),
            47: (21, 3, 0, 5),
            50: (21, 3, 0, 5),
            55: {"n": 29, "excluded": 0, "W": 24, "L": 5, "cells": (20, 4, 0, 5)},
        },
        "wnba_2q": {
            "n": 59,
            25: (49, 5, 0, 5),
            30: (46, 8, 0, 5),
            33: (45, 9, 0, 5),
            35: (45, 9, 0, 5),
            37: (44, 10, 0, 5),
            40: (43, 11, 0, 5),
            43: (43, 11, 0, 5),
            45: (43, 11, 0, 5),
            47: (43, 11, 0, 5),
            50: (43, 11, 0, 5),
            55: {"n": 58, "excluded": 1, "W": 53, "L": 5, "cells": (40, 13, 0, 5)},
        },
        "wnba_3q": {
            "n": 69,
            25: (56, 2, 0, 11),
            30: (55, 3, 0, 11),
            33: (53, 5, 0, 11),
            35: (53, 5, 0, 11),
            37: (53, 5, 0, 11),
            40: (53, 5, 0, 11),
            43: (53, 5, 0, 11),
            45: (53, 5, 0, 11),
            47: (53, 5, 0, 11),
            50: (52, 6, 0, 11),
            55: {"n": 60, "excluded": 9, "W": 49, "L": 11, "cells": (42, 7, 0, 11)},
        },
        "asked_six": {
            "n": 436,
            25: (363, 16, 0, 57),
            30: (355, 24, 0, 57),
            33: (350, 29, 0, 57),
            35: (349, 30, 0, 57),
            37: (347, 32, 0, 57),
            40: (343, 36, 0, 57),
            43: (340, 39, 0, 57),
            45: (334, 45, 0, 57),
            47: (331, 48, 0, 57),
            50: (328, 51, 0, 57),
            55: {"n": 426, "excluded": 10, "W": 369, "L": 57, "cells": (299, 70, 0, 57)},
        },
    },
    "test": {
        "nba_2q": {
            "n": 59,
            25: (53, 1, 0, 5),
            30: (53, 1, 0, 5),
            33: (51, 3, 0, 5),
            35: (51, 3, 0, 5),
            37: (50, 4, 0, 5),
            40: (49, 5, 0, 5),
            43: (49, 5, 0, 5),
            45: (48, 6, 0, 5),
            47: (46, 8, 0, 5),
            50: (43, 11, 0, 5),
            55: {"n": 59, "excluded": 0, "W": 54, "L": 5, "cells": (41, 13, 0, 5)},
        },
        "nba_3q": {
            "n": 60,
            25: (49, 4, 0, 7),
            30: (48, 5, 0, 7),
            33: (48, 5, 0, 7),
            35: (48, 5, 0, 7),
            37: (48, 5, 0, 7),
            40: (46, 7, 0, 7),
            43: (46, 7, 0, 7),
            45: (46, 7, 0, 7),
            47: (45, 8, 0, 7),
            50: (45, 8, 0, 7),
            55: {"n": 59, "excluded": 1, "W": 52, "L": 7, "cells": (44, 8, 0, 7)},
        },
        "ncaab_h1_2": {"n": 6, "status": "DATA_REQUIRED"},
        "ncaab_h2_1": {"n": 9, "status": "DATA_REQUIRED"},
        "wnba_2q": {
            "n": 24,
            25: (18, 3, 0, 3),
            30: (18, 3, 0, 3),
            33: (17, 4, 0, 3),
            35: (16, 5, 0, 3),
            37: (16, 5, 0, 3),
            40: (15, 6, 0, 3),
            43: (15, 6, 0, 3),
            45: (15, 6, 0, 3),
            47: (15, 6, 0, 3),
            50: (15, 6, 0, 3),
            55: {"n": 24, "excluded": 0, "W": 21, "L": 3, "cells": (15, 6, 0, 3)},
        },
        "wnba_3q": {
            "n": 27,
            25: (21, 0, 0, 6),
            30: (21, 0, 0, 6),
            33: (21, 0, 0, 6),
            35: (21, 0, 0, 6),
            37: (21, 0, 0, 6),
            40: (21, 0, 0, 6),
            43: (21, 0, 0, 6),
            45: (21, 0, 0, 6),
            47: (21, 0, 0, 6),
            50: (21, 0, 0, 6),
            55: {"n": 27, "excluded": 0, "W": 21, "L": 6, "cells": (19, 2, 0, 6)},
        },
        "asked_six": {
            "n": 185,
            25: (154, 10, 0, 21),
            30: (153, 11, 0, 21),
            33: (150, 14, 0, 21),
            35: (149, 15, 0, 21),
            37: (148, 16, 0, 21),
            40: (144, 20, 0, 21),
            43: (144, 20, 0, 21),
            45: (143, 21, 0, 21),
            47: (140, 24, 0, 21),
            50: (136, 28, 0, 21),
            55: {"n": 183, "excluded": 2, "W": 162, "L": 21, "cells": (130, 32, 0, 21)},
        },
    },
}

def loss_cents_for_stop_83(stop_cents: int) -> int:
    return ENTRY_CENTS_83 - int(stop_cents)


def ladder_cells_83(stop_cents: int, partition_id: str) -> tuple[int, int, int, int]:
    if stop_cents == 40:
        if partition_id == "derived_four":
            return POOL_CELLS_83
        for lock in PARTITIONS_83:
            if lock.partition_id == partition_id:
                return lock.cells
        raise KeyError(partition_id)
    return BARRIER_CELLS_83[int(stop_cents)][partition_id]
