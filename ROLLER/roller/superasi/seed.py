"""Asked-six FIRST80 80/40 seed. Reconstruct from locked CSVs. Do not rescan."""

from __future__ import annotations

import csv
from fractions import Fraction
from typing import Any

from roller.superasi.exit_mixes import ev_from_s
from roller.superasi.four_cell import cells_from_counts
from roller.superasi.library import repo_root, write_package
from roller.superasi.models import SuperasiError
from roller.superasi.package import new_package, sha256_hex
from roller.superasi.path_windows import (
    apply_derived_to_trades,
    load_asked_six_windows,
    validate_asked_six_locks,
)

SEED_ID = "asked_six_first80_80_40"
ASKED_SIX_TRADES = (
    repo_root() / "research" / "first80_asked_six_chatgpt_export" / "first80_asked_six.csv"
)

LOCK_N = 1182
LOCK_CELLS = (883, 108, 0, 191)
LOCK_LEDGER_EV = Fraction(5700, 1182)
LOCK_T40_EV = Fraction(4058, 1182)
LOCK_PLAN_L = Fraction(14705, 299)


def load_asked_six_trades() -> list[dict[str, Any]]:
    if not ASKED_SIX_TRADES.is_file():
        raise SuperasiError("DATA_REQUIRED", f"missing {ASKED_SIX_TRADES}")
    rows: list[dict[str, Any]] = []
    with ASKED_SIX_TRADES.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            rows.append(raw)
    if len(rows) != LOCK_N:
        raise SuperasiError("POPULATION_COUNT_MISMATCH", f"asked-six N {len(rows)} != {LOCK_N}")
    return rows


def build_seed(*, root=None) -> dict[str, Any]:
    raw_trades = load_asked_six_trades()
    windows = load_asked_six_windows()
    validate_asked_six_locks(windows)
    four = cells_from_counts(*LOCK_CELLS)
    if four["n"] != LOCK_N:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", "asked-six four-cell N mismatch")
    s = Fraction(four["S"]["numer"], four["S"]["denom"])
    if s != Fraction(883, 1182):
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", "S != 883/1182")
    ledger_ev = ev_from_s(s, 20, Fraction(40))
    if ledger_ev != LOCK_LEDGER_EV:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"ledger EV {ledger_ev} != {LOCK_LEDGER_EV}")
    t40_sum = 0
    t40_n = 0
    for w in windows:
        if int(w["offset"]) == 0 and w.get("yes_bid_close") is not None:
            t40_sum += int(w["yes_bid_close"])
            t40_n += 1
    mean_l = Fraction(t40_n * 80 - t40_sum, t40_n)
    t40_ev = ev_from_s(s, 20, mean_l)
    if t40_ev != LOCK_T40_EV:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"T40-close EV {t40_ev} != {LOCK_T40_EV}")
    pkg, trades = new_package(
        source="seed_asked_six",
        trades=raw_trades,
        research_object_id="FIRST80_ASKED_SIX_80_40",
        empirical_four_cell=four,
        package_id=SEED_ID,
        extra={
            "seed_locks": {
                "N": LOCK_N,
                "four_cell": list(LOCK_CELLS),
                "S": "883/1182",
                "ledger_EV": "5700/1182",
                "t40_close_EV": "4058/1182",
                "planning_L": "14705/299",
            }
        },
    )
    trades = apply_derived_to_trades(trades, windows)
    pkg["checksums"]["trades"] = sha256_hex(trades)
    dest = write_package(pkg, trades, windows, root=root, replace=True)
    dest["four_cell"] = four
    dest["locks"] = pkg["seed_locks"]
    return dest
