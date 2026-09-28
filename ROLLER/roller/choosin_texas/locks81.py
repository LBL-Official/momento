"""FIRST81 asked-four + asked-six locks. Integers are the authority.

Same clock slices as Texas FIRST80 / FIRST75 / FIRST77. Different τ.
TABLES.md has no FIRST81. Reconstructs from first81_asked_six.csv.
No warehouse rescan at serve time. Not a live 80/81/83 rule.
"""

from __future__ import annotations

from roller.choosin_texas.locks import Barrier55Lock, PartitionLock

PARTITIONS_81: tuple[PartitionLock, ...] = (
    PartitionLock(
        partition_id="nba_2q",
        sport="nba",
        sport_label="NBA",
        slice="Q2",
        slice_label="2Q",
        csv_sport="NBA",
        csv_slice="Q2",
        n=307,
        W=264,
        L=43,
        win_no=239,
        win_t40=25,
        lose_no=0,
        lose_t40=43,
    ),
    PartitionLock(
        partition_id="nba_3q",
        sport="nba",
        sport_label="NBA",
        slice="Q3",
        slice_label="3Q",
        csv_sport="NBA",
        csv_slice="Q3",
        n=298,
        W=254,
        L=44,
        win_no=227,
        win_t40=27,
        lose_no=0,
        lose_t40=44,
    ),
    PartitionLock(
        partition_id="ncaab_h1_2",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H1_2",
        slice_label="1H second 10",
        csv_sport="NCAAB",
        csv_slice="H1_2",
        n=185,
        W=157,
        L=28,
        win_no=138,
        win_t40=19,
        lose_no=0,
        lose_t40=28,
    ),
    PartitionLock(
        partition_id="ncaab_h2_1",
        sport="ncaab_p5",
        sport_label="NCAAB P5",
        slice="H2_1",
        slice_label="2H first 10",
        csv_sport="NCAAB",
        csv_slice="H2_1",
        n=150,
        W=129,
        L=21,
        win_no=119,
        win_t40=10,
        lose_no=0,
        lose_t40=21,
    ),
)

POOL_N_81 = 940
POOL_W_81 = 804
POOL_L_81 = 136
POOL_CELLS_81 = (723, 81, 0, 136)
POOL_ROLE_81 = "derived_four"

ASKED_SIX_N_81 = 1193
ASKED_SIX_W_81 = 1022
ASKED_SIX_L_81 = 171
ASKED_SIX_CELLS_81 = (916, 106, 0, 171)
WNBA_UNION_N_81 = 253
WNBA_UNION_CELLS_81 = (193, 25, 0, 35)

WNBA_PARTITIONS_81: tuple[PartitionLock, ...] = (
    PartitionLock(
        partition_id="wnba_2q",
        sport="wnba",
        sport_label="WNBA",
        slice="Q2",
        slice_label="2Q",
        csv_sport="WNBA",
        csv_slice="Q2",
        n=126,
        W=111,
        L=15,
        win_no=94,
        win_t40=17,
        lose_no=0,
        lose_t40=15,
    ),
    PartitionLock(
        partition_id="wnba_3q",
        sport="wnba",
        sport_label="WNBA",
        slice="Q3",
        slice_label="3Q",
        csv_sport="WNBA",
        csv_slice="Q3",
        n=127,
        W=107,
        L=20,
        win_no=99,
        win_t40=8,
        lose_no=0,
        lose_t40=20,
    ),
)

ASKED_SIX_PARTITIONS_81: tuple[PartitionLock, ...] = PARTITIONS_81 + WNBA_PARTITIONS_81

RULE_81 = "FIRST81"
K_NUMER_81 = 81
K_DENOM_81 = 100
ENTRY_CENTS_81 = 81
GAIN_CENTS_81 = 19
STOP_CENTS_81 = 40
STOP_55_CENTS_81 = 55
ENTRY_CAP_CENTS_81 = 87
BARRIER_STOPS_81: tuple[int, ...] = (25, 30, 35, 45, 50)
PATH_STOPS_81: tuple[int, ...] = (25, 30, 35, 40, 45, 50, 55)
MID_STOPS_81: tuple[int, ...] = (33, 37, 43, 47)
BARRIER_55_81: tuple[Barrier55Lock, ...] = (
    Barrier55Lock("nba_2q", 306, 1, 263, 43, 204, 59, 0, 43),
    Barrier55Lock("nba_3q", 287, 11, 245, 42, 200, 45, 0, 42),
    Barrier55Lock("ncaab_h1_2", 181, 4, 153, 28, 111, 42, 0, 28),
    Barrier55Lock("ncaab_h2_1", 143, 7, 122, 21, 95, 27, 0, 21),
)

BARRIER_55_POOL_N_81 = 917
BARRIER_55_POOL_EXCL_81 = 23
BARRIER_55_POOL_W_81 = 783
BARRIER_55_POOL_L_81 = 134
BARRIER_55_POOL_CELLS_81 = (610, 173, 0, 134)
BARRIER_CELLS_81: dict[int, dict[str, tuple[int, int, int, int]]] = {
    25: {
        "nba_2q": (252, 12, 0, 43),
        "nba_3q": (243, 11, 0, 44),
        "ncaab_h1_2": (150, 7, 0, 28),
        "ncaab_h2_1": (124, 5, 0, 21),
        "derived_four": (769, 35, 0, 136),
    },
    30: {
        "nba_2q": (249, 15, 0, 43),
        "nba_3q": (240, 14, 0, 44),
        "ncaab_h1_2": (147, 10, 0, 28),
        "ncaab_h2_1": (122, 7, 0, 21),
        "derived_four": (758, 46, 0, 136),
    },
    33: {
        "nba_2q": (247, 17, 0, 43),
        "nba_3q": (239, 15, 0, 44),
        "ncaab_h1_2": (142, 15, 0, 28),
        "ncaab_h2_1": (122, 7, 0, 21),
        "derived_four": (750, 54, 0, 136),
    },
    35: {
        "nba_2q": (245, 19, 0, 43),
        "nba_3q": (237, 17, 0, 44),
        "ncaab_h1_2": (141, 16, 0, 28),
        "ncaab_h2_1": (121, 8, 0, 21),
        "derived_four": (744, 60, 0, 136),
    },
    37: {
        "nba_2q": (243, 21, 0, 43),
        "nba_3q": (234, 20, 0, 44),
        "ncaab_h1_2": (140, 17, 0, 28),
        "ncaab_h2_1": (120, 9, 0, 21),
        "derived_four": (737, 67, 0, 136),
    },
    43: {
        "nba_2q": (236, 28, 0, 43),
        "nba_3q": (226, 28, 0, 44),
        "ncaab_h1_2": (137, 20, 0, 28),
        "ncaab_h2_1": (117, 12, 0, 21),
        "derived_four": (716, 88, 0, 136),
    },
    45: {
        "nba_2q": (229, 35, 0, 43),
        "nba_3q": (226, 28, 0, 44),
        "ncaab_h1_2": (134, 23, 0, 28),
        "ncaab_h2_1": (116, 13, 0, 21),
        "derived_four": (705, 99, 0, 136),
    },
    47: {
        "nba_2q": (223, 41, 0, 43),
        "nba_3q": (224, 30, 0, 44),
        "ncaab_h1_2": (128, 29, 0, 28),
        "ncaab_h2_1": (116, 13, 0, 21),
        "derived_four": (691, 113, 0, 136),
    },
    50: {
        "nba_2q": (218, 46, 0, 43),
        "nba_3q": (220, 34, 0, 44),
        "ncaab_h1_2": (123, 34, 0, 28),
        "ncaab_h2_1": (113, 16, 0, 21),
        "derived_four": (674, 130, 0, 136),
    },
}

BARRIER_CELLS_ASKED_81: dict[int, dict[str, tuple[int, int, int, int]]] = {
    25: {
        "nba_2q": (252, 12, 0, 43),
        "nba_3q": (243, 11, 0, 44),
        "ncaab_h1_2": (150, 7, 0, 28),
        "ncaab_h2_1": (124, 5, 0, 21),
        "wnba_2q": (101, 10, 0, 15),
        "wnba_3q": (103, 4, 0, 20),
        "asked_six": (973, 49, 0, 171),
    },
    30: {
        "nba_2q": (249, 15, 0, 43),
        "nba_3q": (240, 14, 0, 44),
        "ncaab_h1_2": (147, 10, 0, 28),
        "ncaab_h2_1": (122, 7, 0, 21),
        "wnba_2q": (98, 13, 0, 15),
        "wnba_3q": (103, 4, 0, 20),
        "asked_six": (959, 63, 0, 171),
    },
    33: {
        "nba_2q": (247, 17, 0, 43),
        "nba_3q": (239, 15, 0, 44),
        "ncaab_h1_2": (142, 15, 0, 28),
        "ncaab_h2_1": (122, 7, 0, 21),
        "wnba_2q": (96, 15, 0, 15),
        "wnba_3q": (100, 7, 0, 20),
        "asked_six": (946, 76, 0, 171),
    },
    35: {
        "nba_2q": (245, 19, 0, 43),
        "nba_3q": (237, 17, 0, 44),
        "ncaab_h1_2": (141, 16, 0, 28),
        "ncaab_h2_1": (121, 8, 0, 21),
        "wnba_2q": (94, 17, 0, 15),
        "wnba_3q": (100, 7, 0, 20),
        "asked_six": (938, 84, 0, 171),
    },
    37: {
        "nba_2q": (243, 21, 0, 43),
        "nba_3q": (234, 20, 0, 44),
        "ncaab_h1_2": (140, 17, 0, 28),
        "ncaab_h2_1": (120, 9, 0, 21),
        "wnba_2q": (94, 17, 0, 15),
        "wnba_3q": (100, 7, 0, 20),
        "asked_six": (931, 91, 0, 171),
    },
    40: {
        "nba_2q": (239, 25, 0, 43),
        "nba_3q": (227, 27, 0, 44),
        "ncaab_h1_2": (138, 19, 0, 28),
        "ncaab_h2_1": (119, 10, 0, 21),
        "wnba_2q": (94, 17, 0, 15),
        "wnba_3q": (99, 8, 0, 20),
        "asked_six": (916, 106, 0, 171),
    },
    43: {
        "nba_2q": (236, 28, 0, 43),
        "nba_3q": (226, 28, 0, 44),
        "ncaab_h1_2": (137, 20, 0, 28),
        "ncaab_h2_1": (117, 12, 0, 21),
        "wnba_2q": (93, 18, 0, 15),
        "wnba_3q": (98, 9, 0, 20),
        "asked_six": (907, 115, 0, 171),
    },
    45: {
        "nba_2q": (229, 35, 0, 43),
        "nba_3q": (226, 28, 0, 44),
        "ncaab_h1_2": (134, 23, 0, 28),
        "ncaab_h2_1": (116, 13, 0, 21),
        "wnba_2q": (92, 19, 0, 15),
        "wnba_3q": (98, 9, 0, 20),
        "asked_six": (895, 127, 0, 171),
    },
    47: {
        "nba_2q": (223, 41, 0, 43),
        "nba_3q": (224, 30, 0, 44),
        "ncaab_h1_2": (128, 29, 0, 28),
        "ncaab_h2_1": (116, 13, 0, 21),
        "wnba_2q": (91, 20, 0, 15),
        "wnba_3q": (98, 9, 0, 20),
        "asked_six": (880, 142, 0, 171),
    },
    50: {
        "nba_2q": (218, 46, 0, 43),
        "nba_3q": (220, 34, 0, 44),
        "ncaab_h1_2": (123, 34, 0, 28),
        "ncaab_h2_1": (113, 16, 0, 21),
        "wnba_2q": (89, 22, 0, 15),
        "wnba_3q": (95, 12, 0, 20),
        "asked_six": (858, 164, 0, 171),
    },
}

BARRIER_55_ASKED_81: dict[str, tuple[int, int, int, int, tuple[int, int, int, int]]] = {
    "nba_2q": (306, 1, 263, 43, (204, 59, 0, 43)),
    "nba_3q": (287, 11, 245, 42, (200, 45, 0, 42)),
    "ncaab_h1_2": (181, 4, 153, 28, (111, 42, 0, 28)),
    "ncaab_h2_1": (143, 7, 122, 21, (95, 27, 0, 21)),
    "wnba_2q": (125, 1, 110, 15, (84, 26, 0, 15)),
    "wnba_3q": (117, 10, 97, 20, (82, 15, 0, 20)),
    "asked_six": (1159, 34, 990, 169, (776, 214, 0, 169)),
}

OOS_N_81: dict[str, object] = {
    "train": 424,
    "train_window": ('2025-05-22', '2025-12-31'),
    "validation": 588,
    "validation_window": ('2026-01-01', '2026-07-15'),
    "test": 181,
    "test_window": ('2026-03-16', '2026-08-30'),
    "slices": {
        "nba_2q": {"train": 121, "validation": 121, "test": 65},
        "nba_3q": {"train": 117, "validation": 130, "test": 51},
        "ncaab_h1_2": {"train": 41, "validation": 140, "test": 4},
        "ncaab_h2_1": {"train": 26, "validation": 115, "test": 9},
        "wnba_2q": {"train": 58, "validation": 43, "test": 25},
        "wnba_3q": {"train": 61, "validation": 39, "test": 27},
    },
}

OOS_CELLS_81: dict[str, dict[str, dict[int | str, object]]] = {
    "train": {
        "nba_2q": {
            "n": 121,
            25: (100, 5, 0, 16),
            30: (98, 7, 0, 16),
            33: (98, 7, 0, 16),
            35: (97, 8, 0, 16),
            37: (97, 8, 0, 16),
            40: (95, 10, 0, 16),
            43: (93, 12, 0, 16),
            45: (90, 15, 0, 16),
            47: (87, 18, 0, 16),
            50: (87, 18, 0, 16),
            55: {"n": 121, "excluded": 0, "W": 105, "L": 16, "cells": (79, 26, 0, 16)},
        },
        "nba_3q": {
            "n": 117,
            25: (94, 5, 0, 18),
            30: (93, 6, 0, 18),
            33: (92, 7, 0, 18),
            35: (90, 9, 0, 18),
            37: (89, 10, 0, 18),
            40: (87, 12, 0, 18),
            43: (86, 13, 0, 18),
            45: (86, 13, 0, 18),
            47: (86, 13, 0, 18),
            50: (86, 13, 0, 18),
            55: {"n": 113, "excluded": 4, "W": 96, "L": 17, "cells": (78, 18, 0, 17)},
        },
        "ncaab_h1_2": {
            "n": 41,
            25: (33, 1, 0, 7),
            30: (33, 1, 0, 7),
            33: (32, 2, 0, 7),
            35: (31, 3, 0, 7),
            37: (31, 3, 0, 7),
            40: (31, 3, 0, 7),
            43: (31, 3, 0, 7),
            45: (30, 4, 0, 7),
            47: (30, 4, 0, 7),
            50: (30, 4, 0, 7),
            55: {"n": 41, "excluded": 0, "W": 34, "L": 7, "cells": (26, 8, 0, 7)},
        },
        "ncaab_h2_1": {
            "n": 26,
            25: (22, 1, 0, 3),
            30: (22, 1, 0, 3),
            33: (22, 1, 0, 3),
            35: (22, 1, 0, 3),
            37: (21, 2, 0, 3),
            40: (20, 3, 0, 3),
            43: (20, 3, 0, 3),
            45: (20, 3, 0, 3),
            47: (20, 3, 0, 3),
            50: (19, 4, 0, 3),
            55: {"n": 25, "excluded": 1, "W": 22, "L": 3, "cells": (16, 6, 0, 3)},
        },
        "wnba_2q": {
            "n": 58,
            25: (49, 4, 0, 5),
            30: (46, 7, 0, 5),
            33: (45, 8, 0, 5),
            35: (45, 8, 0, 5),
            37: (45, 8, 0, 5),
            40: (45, 8, 0, 5),
            43: (45, 8, 0, 5),
            45: (44, 9, 0, 5),
            47: (44, 9, 0, 5),
            50: (44, 9, 0, 5),
            55: {"n": 57, "excluded": 1, "W": 52, "L": 5, "cells": (40, 12, 0, 5)},
        },
        "wnba_3q": {
            "n": 61,
            25: (50, 2, 0, 9),
            30: (50, 2, 0, 9),
            33: (48, 4, 0, 9),
            35: (48, 4, 0, 9),
            37: (48, 4, 0, 9),
            40: (48, 4, 0, 9),
            43: (48, 4, 0, 9),
            45: (48, 4, 0, 9),
            47: (48, 4, 0, 9),
            50: (47, 5, 0, 9),
            55: {"n": 55, "excluded": 6, "W": 46, "L": 9, "cells": (41, 5, 0, 9)},
        },
        "asked_six": {
            "n": 424,
            25: (348, 18, 0, 58),
            30: (342, 24, 0, 58),
            33: (337, 29, 0, 58),
            35: (333, 33, 0, 58),
            37: (331, 35, 0, 58),
            40: (326, 40, 0, 58),
            43: (323, 43, 0, 58),
            45: (318, 48, 0, 58),
            47: (315, 51, 0, 58),
            50: (313, 53, 0, 58),
            55: {"n": 412, "excluded": 12, "W": 355, "L": 57, "cells": (280, 75, 0, 57)},
        },
    },
    "test": {
        "nba_2q": {
            "n": 65,
            25: (57, 2, 0, 6),
            30: (57, 2, 0, 6),
            33: (55, 4, 0, 6),
            35: (55, 4, 0, 6),
            37: (54, 5, 0, 6),
            40: (53, 6, 0, 6),
            43: (53, 6, 0, 6),
            45: (52, 7, 0, 6),
            47: (50, 9, 0, 6),
            50: (47, 12, 0, 6),
            55: {"n": 65, "excluded": 0, "W": 59, "L": 6, "cells": (45, 14, 0, 6)},
        },
        "nba_3q": {
            "n": 51,
            25: (42, 4, 0, 5),
            30: (41, 5, 0, 5),
            33: (41, 5, 0, 5),
            35: (41, 5, 0, 5),
            37: (41, 5, 0, 5),
            40: (39, 7, 0, 5),
            43: (39, 7, 0, 5),
            45: (39, 7, 0, 5),
            47: (38, 8, 0, 5),
            50: (37, 9, 0, 5),
            55: {"n": 51, "excluded": 0, "W": 46, "L": 5, "cells": (37, 9, 0, 5)},
        },
        "ncaab_h1_2": {"n": 4, "status": "DATA_REQUIRED"},
        "ncaab_h2_1": {"n": 9, "status": "DATA_REQUIRED"},
        "wnba_2q": {
            "n": 25,
            25: (18, 4, 0, 3),
            30: (18, 4, 0, 3),
            33: (17, 5, 0, 3),
            35: (16, 6, 0, 3),
            37: (16, 6, 0, 3),
            40: (16, 6, 0, 3),
            43: (16, 6, 0, 3),
            45: (16, 6, 0, 3),
            47: (16, 6, 0, 3),
            50: (16, 6, 0, 3),
            55: {"n": 25, "excluded": 0, "W": 22, "L": 3, "cells": (16, 6, 0, 3)},
        },
        "wnba_3q": {
            "n": 27,
            25: (19, 0, 0, 8),
            30: (19, 0, 0, 8),
            33: (19, 0, 0, 8),
            35: (19, 0, 0, 8),
            37: (19, 0, 0, 8),
            40: (19, 0, 0, 8),
            43: (19, 0, 0, 8),
            45: (19, 0, 0, 8),
            47: (19, 0, 0, 8),
            50: (19, 0, 0, 8),
            55: {"n": 27, "excluded": 0, "W": 19, "L": 8, "cells": (17, 2, 0, 8)},
        },
        "asked_six": {
            "n": 181,
            25: (147, 12, 0, 22),
            30: (146, 13, 0, 22),
            33: (143, 16, 0, 22),
            35: (142, 17, 0, 22),
            37: (141, 18, 0, 22),
            40: (138, 21, 0, 22),
            43: (138, 21, 0, 22),
            45: (137, 22, 0, 22),
            47: (134, 25, 0, 22),
            50: (130, 29, 0, 22),
            55: {"n": 179, "excluded": 2, "W": 157, "L": 22, "cells": (124, 33, 0, 22)},
        },
    },
}

def loss_cents_for_stop_81(stop_cents: int) -> int:
    return ENTRY_CENTS_81 - int(stop_cents)


def ladder_cells_81(stop_cents: int, partition_id: str) -> tuple[int, int, int, int]:
    if stop_cents == 40:
        if partition_id == "derived_four":
            return POOL_CELLS_81
        for lock in PARTITIONS_81:
            if lock.partition_id == partition_id:
                return lock.cells
        raise KeyError(partition_id)
    return BARRIER_CELLS_81[int(stop_cents)][partition_id]
