"""Reference NCAAB boundary. The implementation in ncaab_pbp_align is not edited."""

from __future__ import annotations

SPLIT_S = 600


def ncaab_bucket(period: int, remaining_s: float) -> str:
    if int(period) == 1:
        return "H1_1" if float(remaining_s) > SPLIT_S else "H1_2"
    if int(period) == 2:
        return "H2_1" if float(remaining_s) > SPLIT_S else "H2_2"
    return "OUT"
