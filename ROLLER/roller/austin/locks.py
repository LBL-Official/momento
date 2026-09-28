"""Austin universe locks. Integers are the authority. Do not mix books."""

from __future__ import annotations

from roller.nba_8040_reverse_features.locks import (
    GAIN_CENTS,
    LOSS_CENTS,
    NBA_Q2_N,
    NBA_Q2Q3_BOOK,
    NBA_Q2Q3_L_T40,
    NBA_Q2Q3_N,
    NBA_Q2Q3_S,
    NBA_Q2Q3_W_T40,
    NBA_Q3_N,
    RULE,
    SLICES,
    SPORT,
    STOP_CENTS,
)

N_TRADES = NBA_Q2Q3_N
N_Q2 = NBA_Q2_N
N_Q3 = NBA_Q3_N
S_N = NBA_Q2Q3_S
W_T40 = NBA_Q2Q3_W_T40
L_T40 = NBA_Q2Q3_L_T40
BOOK_CENTS = NBA_Q2Q3_BOOK
T40_N = W_T40 + L_T40

FORBIDDEN_N = {
    "derived_four": 936,
    "asked_six": 1182,
    "nba_full_first80": 1230,
    "path_fe_wf": 797,
}

__all__ = [
    "BOOK_CENTS",
    "FORBIDDEN_N",
    "GAIN_CENTS",
    "LOSS_CENTS",
    "N_Q2",
    "N_Q3",
    "N_TRADES",
    "RULE",
    "SLICES",
    "SPORT",
    "STOP_CENTS",
    "S_N",
    "T40_N",
    "W_T40",
    "L_T40",
]
