"""Asked-six desk: FIRST80 / FIRST75 / FIRST77 (+ FIRST81 / FIRST83 when locked).

Reconstructs CSVs. Does not rescan the warehouse. Candle path ≠ fill.
asked-six ≠ derived four. Frontend does not compute EV.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from roller.choosin_texas.ev import ev_payload
from roller.choosin_texas.locks import PartitionLock
from roller.choosin_texas.locks_asked_six import (
    ASKED_SIX_CELLS_75,
    ASKED_SIX_CELLS_77,
    ASKED_SIX_CELLS_80,
    ASKED_SIX_N_75,
    ASKED_SIX_N_77,
    ASKED_SIX_N_80,
    ASKED_SIX_PARTITIONS_75,
    ASKED_SIX_PARTITIONS_77,
    ASKED_SIX_PARTITIONS_80,
    ASKED_SIX_STOPS,
    ASKED_SIX_W_75,
    ASKED_SIX_W_77,
    ASKED_SIX_W_80,
    ASKED_SIX_L_75,
    ASKED_SIX_L_77,
    ASKED_SIX_L_80,
    BARRIER_55_ASKED_75,
    BARRIER_55_ASKED_77,
    BARRIER_55_ASKED_80,
    BARRIER_CELLS_ASKED_75,
    BARRIER_CELLS_ASKED_77,
    BARRIER_CELLS_ASKED_80,
    FULL_ASKED_STOPS,
    NCAAB_WINDOW_NOTE,
    OOS_CELLS_75,
    OOS_CELLS_77,
    OOS_CELLS_80,
    OOS_MIN_N,
    OOS_N_75,
    OOS_N_77,
    OOS_N_80,
    OOS_SPLIT_COLUMN,
    OOS_TEST_KEY,
    OOS_TRAIN_KEY,
    OOS_VALIDATION_KEY,
    SLICE_ORDER,
    WNBA_UNION_CELLS_75,
    WNBA_UNION_CELLS_77,
    WNBA_UNION_CELLS_80,
    WNBA_UNION_N_75,
    WNBA_UNION_N_77,
    WNBA_UNION_N_80,
    cap_cents_for_tau,
    gain_cents_for_tau,
    loss_cents_for_tau_stop,
)
from roller.choosin_texas.models import ChoosinTexasError, frac, pct_display, ratio_display
from roller.choosin_texas.rates import assert_identities, ledger_rank
from roller.choosin_texas.sources import (
    default_asked_six_75_csv,
    default_asked_six_77_csv,
    default_asked_six_81_csv,
    default_asked_six_83_csv,
    default_asked_six_csv,
    default_asked_six_csv_for_tau,
    load_csv_asked_six_splits,
    load_csv_barrier_55,
    load_csv_barriers,
    load_csv_cells,
    load_tables_asked_six,
)
from roller.results_math.proportions import wilson_interval


@dataclass(frozen=True)
class AskedSixBook:
    tau: int
    rule: str
    partitions: tuple[PartitionLock, ...]
    asked_six_n: int
    asked_six_w: int
    asked_six_l: int
    asked_six_cells: tuple[int, int, int, int]
    wnba_n: int
    wnba_cells: tuple[int, int, int, int]
    barrier_cells: dict[int, dict[str, tuple[int, int, int, int]]]
    barrier_55: dict[str, tuple[int, int, int, int, tuple[int, int, int, int]]]
    oos_n: dict[str, Any]
    oos_cells: dict[str, Any]
    csv_loader: Callable[[], Path]
    tables_rule: str | None


def _wilson_pct(successes: int, n: int) -> dict[str, Any] | None:
    interval = wilson_interval(successes, n)
    if interval is None:
        return None
    return {
        "lower_pct": round(interval["lower"] * 100, 4),
        "upper_pct": round(interval["upper"] * 100, 4),
        "display": f"{interval['lower'] * 100:.4f}–{interval['upper'] * 100:.4f}",
        "status": "DERIVED",
        "method": "wilson",
        "numer": int(successes),
        "denom": int(n),
    }


def tau_path_payload(
    *,
    tau: int,
    stop_cents: int,
    n: int,
    cells: tuple[int, int, int, int],
    label: str,
    excluded: int | None = None,
    wilson: bool = True,
) -> dict[str, Any]:
    win_no, win_tx, lose_no, lose_tx = (int(v) for v in cells)
    w = win_no + win_tx
    lose = lose_no + lose_tx
    assert_identities(n, w, lose, win_no, win_tx, lose_no, lose_tx, label=label)
    s_n = win_no + lose_no
    trade_l = n - s_n
    s = Fraction(s_n, n)
    gain = gain_cents_for_tau(tau)
    loss = loss_cents_for_tau_stop(tau, stop_cents)
    cap = cap_cents_for_tau(tau)
    ev = ev_payload(
        n=n,
        s_n=s_n,
        stop_cents=stop_cents,
        gain_cents=gain,
        loss_cents=loss,
    )
    body: dict[str, Any] = {
        "key": f"{int(tau)}/{int(stop_cents)}",
        "tau": int(tau),
        "stop_cents": int(stop_cents),
        "n": n,
        "W": w,
        "L": lose,
        "cells": {
            f"W_and_not_T{stop_cents}": win_no,
            f"W_and_T{stop_cents}": win_tx,
            f"L_and_not_T{stop_cents}": lose_no,
            f"L_and_T{stop_cents}": lose_tx,
        },
        "S": frac(s_n, n),
        "wins": s_n,
        "losses": trade_l,
        "S_display": ratio_display(s_n, n),
        "S_pct_display": pct_display(s_n, n),
        "S_bar_pct": float(s * 100),
        "loss_display": ratio_display(trade_l, n),
        "loss_pct_display": pct_display(trade_l, n),
        "gain_cents": gain,
        "loss_cents": loss,
        "note": (
            f"S = P(¬T{stop_cents}). EV = {gain}S − {loss}(1−S). "
            "Candle path ≠ fill. Not live EV."
        ),
        **ev,
    }
    if wilson:
        body["S_wilson"] = _wilson_pct(s_n, n)
    if excluded is not None:
        excl_key = f"excluded_hit_{cap}"
        body[excl_key] = int(excluded)
        body["excluded_hit_86"] = int(excluded)
        body["filter"] = {
            "entry_yes_bid_lt": cap,
            excl_key: int(excluded),
            "n_full": n + int(excluded),
            "note": (
                f"Only FIRST{tau} prints still below {cap}. "
                f"If the first ≥{tau} close is already ≥{cap}, do not count."
            ),
        }
        body["note"] = (
            f"S = P(¬T55 | entry yes_bid < {cap}). EV = {gain}S − {loss}(1−S). "
            "Candle path ≠ fill. Not live EV."
        )
    return body


def _paths_for_partition(book: AskedSixBook, lock: PartitionLock) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in ASKED_SIX_STOPS:
        if stop == 55:
            n, excl, w, lose, cells = book.barrier_55[lock.partition_id]
            out.append(
                tau_path_payload(
                    tau=book.tau,
                    stop_cents=55,
                    n=n,
                    cells=cells,
                    label=f"{book.tau}_55:{lock.partition_id}",
                    excluded=excl,
                )
            )
            continue
        cells = book.barrier_cells[int(stop)][lock.partition_id]
        out.append(
            tau_path_payload(
                tau=book.tau,
                stop_cents=stop,
                n=lock.n,
                cells=cells,
                label=f"{book.tau}_{stop}:{lock.partition_id}",
            )
        )
    return out


def _paths_for_pool(book: AskedSixBook) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in ASKED_SIX_STOPS:
        if stop == 55:
            n, excl, w, lose, cells = book.barrier_55["asked_six"]
            out.append(
                tau_path_payload(
                    tau=book.tau,
                    stop_cents=55,
                    n=n,
                    cells=cells,
                    label=f"{book.tau}_55:asked_six",
                    excluded=excl,
                )
            )
            continue
        cells = book.barrier_cells[int(stop)]["asked_six"]
        out.append(
            tau_path_payload(
                tau=book.tau,
                stop_cents=stop,
                n=book.asked_six_n,
                cells=cells,
                label=f"{book.tau}_{stop}:asked_six",
            )
        )
    return out


def _same_row(lock: PartitionLock, counts: dict[str, int], *, source: str, tau: int) -> None:
    observed = (
        int(counts["n"]),
        int(counts["W"]),
        int(counts["L"]),
        (
            int(counts["win_no"]),
            int(counts.get("win_t40", counts.get("win_tx", -1))),
            int(counts["lose_no"]),
            int(counts.get("lose_t40", counts.get("lose_tx", -1))),
        ),
    )
    expected = (lock.n, lock.W, lock.L, lock.cells)
    if observed != expected:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            (
                f"{source} FIRST{tau} {lock.partition_id} "
                f"{observed} != lock {expected}"
            ),
        )


def _verify_book(book: AskedSixBook) -> dict[str, Any]:
    csv_file = book.csv_loader()
    if not csv_file.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing FIRST{book.tau} asked-six CSV {csv_file}")

    for lock in book.partitions:
        assert_identities(
            lock.n,
            lock.W,
            lock.L,
            lock.win_no,
            lock.win_t40,
            lock.lose_no,
            lock.lose_t40,
            label=f"asked_six_{book.tau}:{lock.partition_id}",
        )

    pool_n = sum(p.n for p in book.partitions)
    pool_w = sum(p.W for p in book.partitions)
    pool_l = sum(p.L for p in book.partitions)
    pool_cells = (
        sum(p.win_no for p in book.partitions),
        sum(p.win_t40 for p in book.partitions),
        sum(p.lose_no for p in book.partitions),
        sum(p.lose_t40 for p in book.partitions),
    )
    if (
        pool_n != book.asked_six_n
        or pool_w != book.asked_six_w
        or pool_l != book.asked_six_l
        or pool_cells != book.asked_six_cells
    ):
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            (
                f"FIRST{book.tau} asked-six sum {pool_n}/{pool_w}/{pool_l}/{pool_cells} "
                f"!= {book.asked_six_n}/{book.asked_six_w}/{book.asked_six_l}/{book.asked_six_cells}"
            ),
        )
    assert_identities(pool_n, pool_w, pool_l, *pool_cells, label=f"asked_six_{book.tau}:pool")

    wnba = [p for p in book.partitions if p.csv_sport == "WNBA"]
    wnba_n = sum(p.n for p in wnba)
    wnba_cells = (
        sum(p.win_no for p in wnba),
        sum(p.win_t40 for p in wnba),
        sum(p.lose_no for p in wnba),
        sum(p.lose_t40 for p in wnba),
    )
    if wnba_n != book.wnba_n or wnba_cells != book.wnba_cells:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{book.tau} WNBA {wnba_n}/{wnba_cells} != {book.wnba_n}/{book.wnba_cells}",
        )
    four_n = pool_n - wnba_n
    if four_n + wnba_n != book.asked_six_n:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{book.tau} complement {four_n}+{wnba_n} != {book.asked_six_n}",
        )

    if book.tables_rule is not None:
        tables = load_tables_asked_six(rule=book.tables_rule)
        for lock in book.partitions:
            row = tables.get((lock.sport, lock.slice))
            if row is None:
                raise ChoosinTexasError(
                    "DATA_REQUIRED",
                    f"tables.json missing {book.tables_rule} asked_six {lock.sport}/{lock.slice}",
                )
            _same_row(lock, row, source="tables.json", tau=book.tau)

    csv_body = load_csv_cells(csv_file, partitions=book.partitions)
    if csv_body["asked_six_n"] != book.asked_six_n:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{book.tau} CSV N {csv_body['asked_six_n']} != {book.asked_six_n}",
        )
    if csv_body["wnba_n"] != book.wnba_n:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{book.tau} WNBA CSV N {csv_body['wnba_n']} != {book.wnba_n}",
        )
    for lock in book.partitions:
        _same_row(
            lock,
            csv_body["partitions"][lock.partition_id],
            source=f"asked_six_{book.tau}_csv",
            tau=book.tau,
        )

    cap = cap_cents_for_tau(book.tau)
    barrier_csv = load_csv_barrier_55(
        csv_file,
        partitions=book.partitions,
        entry_cents=book.tau,
        cap_cents=cap,
    )["partitions"]
    pool_55 = [0, 0, 0, 0, 0, 0, 0, 0]
    for lock in book.partitions:
        obs = barrier_csv[lock.partition_id]
        observed = (
            int(obs["n"]),
            int(obs["excluded_hit_86"]),
            int(obs["W"]),
            int(obs["L"]),
            (
                int(obs["win_no"]),
                int(obs["win_t55"]),
                int(obs["lose_no"]),
                int(obs["lose_t55"]),
            ),
        )
        expected = book.barrier_55[lock.partition_id]
        if observed != expected:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"asked_six_{book.tau}_csv {book.tau}/55 {lock.partition_id} {observed} != {expected}",
            )
        pool_55[0] += expected[0]
        pool_55[1] += expected[1]
        pool_55[2] += expected[2]
        pool_55[3] += expected[3]
        for i, value in enumerate(expected[4]):
            pool_55[4 + i] += value
    exp_pool_55 = book.barrier_55["asked_six"]
    got_pool_55 = (
        pool_55[0],
        pool_55[1],
        pool_55[2],
        pool_55[3],
        (pool_55[4], pool_55[5], pool_55[6], pool_55[7]),
    )
    if got_pool_55 != exp_pool_55:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{book.tau} 55 asked-six {got_pool_55} != {exp_pool_55}",
        )
    if pool_55[0] + pool_55[1] != book.asked_six_n:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{book.tau} 55 {pool_55[0]}+{pool_55[1]} != asked-six {book.asked_six_n}",
        )

    ladder = load_csv_barriers(csv_file, partitions=book.partitions, stops=FULL_ASKED_STOPS)["partitions"]
    for stop in FULL_ASKED_STOPS:
        pool_obs = [0, 0, 0, 0]
        for lock in book.partitions:
            observed = ladder[int(stop)][lock.partition_id]
            cells = (
                int(observed["win_no"]),
                int(observed["win_tx"]),
                int(observed["lose_no"]),
                int(observed["lose_tx"]),
            )
            expected = book.barrier_cells[int(stop)][lock.partition_id]
            if (
                int(observed["n"]) != lock.n
                or int(observed["W"]) != lock.W
                or int(observed["L"]) != lock.L
                or cells != expected
            ):
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    (
                        f"asked_six_{book.tau}_csv {book.tau}/{stop} {lock.partition_id} "
                        f"{observed['n']}/{observed['W']}/{observed['L']}/{cells} "
                        f"!= lock {lock.n}/{lock.W}/{lock.L}/{expected}"
                    ),
                )
            for i, value in enumerate(cells):
                pool_obs[i] += value
        if tuple(pool_obs) != book.barrier_cells[int(stop)]["asked_six"]:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"{book.tau}/{stop} asked-six {tuple(pool_obs)} != lock",
            )

    splits = load_csv_asked_six_splits(
        csv_file,
        partitions=book.partitions,
        stops=FULL_ASKED_STOPS,
        entry_cents=book.tau,
        cap_cents=cap,
    )
    _verify_oos(book, splits)

    sources = [
        str(csv_file.relative_to(csv_file.parents[2])),
        f"asked_six_{book.tau}_csv {book.tau}/55 entry<{cap}",
        f"asked_six_{book.tau}_csv barrier ladder {','.join(str(s) for s in FULL_ASKED_STOPS)}",
        f"dataset_split train={OOS_TRAIN_KEY} test={OOS_TEST_KEY}",
    ]
    if book.tables_rule is not None:
        sources.insert(0, f"docs/research/lebronner/tables.json {book.tables_rule} asked_six")
    else:
        sources.insert(0, f"CSV + locks_asked_six FIRST{book.tau} (no TABLES.md row)")

    return {
        "status": "OBSERVED",
        "book": book,
        "four_n": four_n,
        "splits": splits,
        "sources": sources,
    }


def _oos_cells(part: dict[str, Any], stop: int) -> tuple[int, int, int, int]:
    cell = part["stops"][int(stop)]
    return (
        int(cell["win_no"]),
        int(cell["win_tx"]),
        int(cell["lose_no"]),
        int(cell["lose_tx"]),
    )


def _verify_oos(book: AskedSixBook, splits: dict[str, Any]) -> None:
    fold_map = {
        "train": OOS_TRAIN_KEY,
        "validation": OOS_VALIDATION_KEY,
        "test": OOS_TEST_KEY,
    }
    for name, split_key in fold_map.items():
        fold = splits["folds"][split_key]
        locked_n = int(book.oos_n[name])
        locked_window = tuple(book.oos_n[f"{name}_window"])
        if int(fold["n"]) != locked_n:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST{book.tau} OOS {name} N {fold['n']} != lock {locked_n}",
            )
        if fold["window"] != locked_window:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST{book.tau} OOS {name} window {fold['window']} != {locked_window}",
            )
        slice_lock = book.oos_n["slices"]
        for lock in book.partitions:
            got = int(fold["partitions"][lock.partition_id]["n"])
            exp = int(slice_lock[lock.partition_id][name])
            if got != exp:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"FIRST{book.tau} OOS {name} {lock.partition_id} n={got} != {exp}",
                )

    for name, split_key in (("train", OOS_TRAIN_KEY), ("test", OOS_TEST_KEY)):
        fold = splits["folds"][split_key]
        locked_fold = book.oos_cells[name]
        for pid, locked in locked_fold.items():
            part = fold["partitions"][pid]
            if locked.get("status") == "DATA_REQUIRED":
                if int(part["n"]) != int(locked["n"]):
                    raise ChoosinTexasError(
                        "LOCK_MISMATCH",
                        f"FIRST{book.tau} OOS {name} {pid} thin n {part['n']} != {locked['n']}",
                    )
                continue
            if int(part["n"]) != int(locked["n"]):
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"FIRST{book.tau} OOS {name} {pid} n {part['n']} != {locked['n']}",
                )
            for stop in FULL_ASKED_STOPS:
                got = _oos_cells(part, stop)
                exp = tuple(int(v) for v in locked[stop])
                if got != exp:
                    raise ChoosinTexasError(
                        "LOCK_MISMATCH",
                        f"FIRST{book.tau} OOS {name} {pid} T{stop} {got} != {exp}",
                    )
            t55 = part["t55"]
            exp55 = locked[55]
            got55 = (
                int(t55["n"]),
                int(t55["excluded"]),
                int(t55["W"]),
                int(t55["L"]),
                (
                    int(t55["win_no"]),
                    int(t55["win_tx"]),
                    int(t55["lose_no"]),
                    int(t55["lose_tx"]),
                ),
            )
            expected55 = (
                int(exp55["n"]),
                int(exp55["excluded"]),
                int(exp55["W"]),
                int(exp55["L"]),
                tuple(int(v) for v in exp55["cells"]),
            )
            if got55 != expected55:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"FIRST{book.tau} OOS {name} {pid} T55 {got55} != {expected55}",
                )


def _oos_fold_payload(
    book: AskedSixBook,
    *,
    fold_name: str,
    split_key: str,
    splits: dict[str, Any],
) -> dict[str, Any]:
    fold = splits["folds"][split_key]
    locked = book.oos_cells[fold_name]
    slices: dict[str, Any] = {}
    for lock in book.partitions:
        pid = lock.partition_id
        cell_lock = locked[pid]
        n = int(fold["partitions"][pid]["n"])
        if cell_lock.get("status") == "DATA_REQUIRED" or n < OOS_MIN_N:
            slices[pid] = {
                "status": "DATA_REQUIRED",
                "partition_id": pid,
                "sport_label": lock.sport_label,
                "slice_label": lock.slice_label,
                "n": n,
                "message": (
                    f"{fold_name} N={n} < min_n_to_lock={OOS_MIN_N}. "
                    "Not enough to lock S or EV. Not a fill."
                ),
            }
            continue
        slices[pid] = {
            "status": "OBSERVED",
            "partition_id": pid,
            "sport_label": lock.sport_label,
            "slice_label": lock.slice_label,
            "n": n,
            "paths": _oos_paths(book, cell_lock, label=f"{book.tau}_{fold_name}:{pid}"),
        }
    pool_lock = locked["asked_six"]
    return {
        "status": "OBSERVED",
        "fold": fold_name,
        "split_key": split_key,
        "n": int(fold["n"]),
        "window": list(fold["window"]) if fold["window"] else None,
        "pool": {
            "status": "OBSERVED",
            "n": int(pool_lock["n"]),
            "paths": _oos_paths(book, pool_lock, label=f"{book.tau}_{fold_name}:asked_six"),
            "note": "Asked-six pool. Candle-path theoretical. Not a fill. Not in-sample.",
        },
        "slices": slices,
    }


def _oos_paths(book: AskedSixBook, locked: dict[str, Any], *, label: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in ASKED_SIX_STOPS:
        if stop == 55:
            row = locked[55]
            out.append(
                tau_path_payload(
                    tau=book.tau,
                    stop_cents=55,
                    n=int(row["n"]),
                    cells=tuple(int(v) for v in row["cells"]),
                    label=f"{label}:55",
                    excluded=int(row["excluded"]),
                    wilson=False,
                )
            )
            continue
        out.append(
            tau_path_payload(
                tau=book.tau,
                stop_cents=stop,
                n=int(locked["n"]),
                cells=tuple(int(v) for v in locked[stop]),
                label=f"{label}:{stop}",
                wilson=False,
            )
        )
    return out


def _book_tile(book: AskedSixBook, lock: PartitionLock) -> dict[str, Any]:
    paths = _paths_for_partition(book, lock)
    n55, excl, _w, _l, _cells = book.barrier_55[lock.partition_id]
    return {
        "tau": book.tau,
        "rule": book.rule,
        "n": lock.n,
        "W": lock.W,
        "L": lock.L,
        "cells": {
            "W_and_not_T40": lock.win_no,
            "W_and_T40": lock.win_t40,
            "L_and_not_T40": lock.lose_no,
            "L_and_T40": lock.lose_t40,
        },
        "n_55": n55,
        "excluded_55": excl,
        "entry_cents": book.tau,
        "entry_cap_cents": cap_cents_for_tau(book.tau),
        "gain_cents": gain_cents_for_tau(book.tau),
        "paths": paths,
        "ledger_rank": ledger_rank(paths),
        "note": (
            f"FIRST{book.tau} asked-six slice. "
            f"{book.tau}/25–{book.tau}/50 use N={lock.n}. "
            f"{book.tau}/55 is entry<{cap_cents_for_tau(book.tau)}. "
            "Candle path ≠ fill."
        ),
    }


def _pool_tile(book: AskedSixBook) -> dict[str, Any]:
    paths = _paths_for_pool(book)
    n55, excl, w55, l55, cells55 = book.barrier_55["asked_six"]
    return {
        "tau": book.tau,
        "rule": book.rule,
        "partition_id": "asked_six",
        "role": "asked_six",
        "n": book.asked_six_n,
        "W": book.asked_six_w,
        "L": book.asked_six_l,
        "cells": {
            "W_and_not_T40": book.asked_six_cells[0],
            "W_and_T40": book.asked_six_cells[1],
            "L_and_not_T40": book.asked_six_cells[2],
            "L_and_T40": book.asked_six_cells[3],
        },
        "n_55": n55,
        "excluded_55": excl,
        "entry_cents": book.tau,
        "entry_cap_cents": cap_cents_for_tau(book.tau),
        "gain_cents": gain_cents_for_tau(book.tau),
        "paths": paths,
        "ledger_rank": ledger_rank(paths),
        "note": (
            f"Asked-six FIRST{book.tau} N={book.asked_six_n}. "
            f"Not derived four. {book.tau}/55 N={n55} excluded={excl}. "
            "Candle path ≠ fill."
        ),
    }


def _books() -> tuple[AskedSixBook, ...]:
    core = (
        AskedSixBook(
            tau=80,
            rule="FIRST80",
            partitions=ASKED_SIX_PARTITIONS_80,
            asked_six_n=ASKED_SIX_N_80,
            asked_six_w=ASKED_SIX_W_80,
            asked_six_l=ASKED_SIX_L_80,
            asked_six_cells=ASKED_SIX_CELLS_80,
            wnba_n=WNBA_UNION_N_80,
            wnba_cells=WNBA_UNION_CELLS_80,
            barrier_cells=BARRIER_CELLS_ASKED_80,
            barrier_55=BARRIER_55_ASKED_80,
            oos_n=OOS_N_80,
            oos_cells=OOS_CELLS_80,
            csv_loader=default_asked_six_csv,
            tables_rule="FIRST80",
        ),
        AskedSixBook(
            tau=75,
            rule="FIRST75",
            partitions=ASKED_SIX_PARTITIONS_75,
            asked_six_n=ASKED_SIX_N_75,
            asked_six_w=ASKED_SIX_W_75,
            asked_six_l=ASKED_SIX_L_75,
            asked_six_cells=ASKED_SIX_CELLS_75,
            wnba_n=WNBA_UNION_N_75,
            wnba_cells=WNBA_UNION_CELLS_75,
            barrier_cells=BARRIER_CELLS_ASKED_75,
            barrier_55=BARRIER_55_ASKED_75,
            oos_n=OOS_N_75,
            oos_cells=OOS_CELLS_75,
            csv_loader=default_asked_six_75_csv,
            tables_rule="FIRST75",
        ),
        AskedSixBook(
            tau=77,
            rule="FIRST77",
            partitions=ASKED_SIX_PARTITIONS_77,
            asked_six_n=ASKED_SIX_N_77,
            asked_six_w=ASKED_SIX_W_77,
            asked_six_l=ASKED_SIX_L_77,
            asked_six_cells=ASKED_SIX_CELLS_77,
            wnba_n=WNBA_UNION_N_77,
            wnba_cells=WNBA_UNION_CELLS_77,
            barrier_cells=BARRIER_CELLS_ASKED_77,
            barrier_55=BARRIER_55_ASKED_77,
            oos_n=OOS_N_77,
            oos_cells=OOS_CELLS_77,
            csv_loader=default_asked_six_77_csv,
            tables_rule=None,
        ),
    )
    extra: list[AskedSixBook] = []
    for tau, loader in ((81, default_asked_six_81_csv), (83, default_asked_six_83_csv)):
        try:
            L = __import__(f"roller.choosin_texas.locks{tau}", fromlist=["*"])
        except ImportError:
            continue
        if not hasattr(L, f"ASKED_SIX_PARTITIONS_{tau}"):
            continue
        extra.append(
            AskedSixBook(
                tau=tau,
                rule=f"FIRST{tau}",
                partitions=getattr(L, f"ASKED_SIX_PARTITIONS_{tau}"),
                asked_six_n=getattr(L, f"ASKED_SIX_N_{tau}"),
                asked_six_w=getattr(L, f"ASKED_SIX_W_{tau}"),
                asked_six_l=getattr(L, f"ASKED_SIX_L_{tau}"),
                asked_six_cells=getattr(L, f"ASKED_SIX_CELLS_{tau}"),
                wnba_n=getattr(L, f"WNBA_UNION_N_{tau}"),
                wnba_cells=getattr(L, f"WNBA_UNION_CELLS_{tau}"),
                barrier_cells=getattr(L, f"BARRIER_CELLS_ASKED_{tau}"),
                barrier_55=getattr(L, f"BARRIER_55_ASKED_{tau}"),
                oos_n=getattr(L, f"OOS_N_{tau}"),
                oos_cells=getattr(L, f"OOS_CELLS_{tau}"),
                csv_loader=loader,
                tables_rule=None,
            )
        )
    return core + tuple(extra)


def verify_asked_six() -> dict[str, Any]:
    verified = {}
    sources: list[str] = []
    for book in _books():
        body = _verify_book(book)
        verified[book.rule] = body
        sources.extend(body["sources"])
    return {"status": "OBSERVED", "books": verified, "sources": sources}


def _missing_tau_payload(tau: int) -> dict[str, Any]:
    path = default_asked_six_csv_for_tau(tau)
    return {
        "status": "DATA_REQUIRED",
        "tau": tau,
        "rule": f"FIRST{tau}",
        "message": (
            f"FIRST{tau} asked-six CSV missing at {path}. "
            "TABLES.md has no FIRST{tau}. Collect before locking. "
            "Do not invent N."
        ).replace("{tau}", str(tau)),
        "csv": str(path),
    }


def build_asked_six() -> dict[str, Any]:
    verified = verify_asked_six()
    books_out: dict[str, Any] = {}
    tiles: dict[str, dict[str, Any]] = {}
    pool_books: dict[str, Any] = {}
    oos_books: dict[str, Any] = {}

    by_id_meta = {p.partition_id: p for p in ASKED_SIX_PARTITIONS_80}

    for book in _books():
        body = verified["books"][book.rule]
        book_tile = _pool_tile(book)
        pool_books[book.rule] = book_tile
        books_out[book.rule] = {
            "tau": book.tau,
            "rule": book.rule,
            "n": book.asked_six_n,
            "W": book.asked_six_w,
            "L": book.asked_six_l,
            "cells": book_tile["cells"],
            "four_n": body["four_n"],
            "wnba_n": book.wnba_n,
            "identity": f"{book.asked_six_n} = {body['four_n']} + {book.wnba_n}",
            "entry_cents": book.tau,
            "entry_cap_cents": cap_cents_for_tau(book.tau),
            "gain_cents": gain_cents_for_tau(book.tau),
        }
        for lock in book.partitions:
            tiles.setdefault(
                lock.partition_id,
                {
                    "partition_id": lock.partition_id,
                    "sport": lock.sport,
                    "sport_label": lock.sport_label,
                    "slice": lock.slice,
                    "slice_label": lock.slice_label,
                    "role": "asked_six_slice",
                    "ncaab_window_note": NCAAB_WINDOW_NOTE if lock.csv_sport == "NCAAB" else None,
                    "books": {},
                },
            )
            tiles[lock.partition_id]["books"][book.rule] = _book_tile(book, lock)
        oos_books[book.rule] = {
            "tau": book.tau,
            "rule": book.rule,
            "split": {
                "column": OOS_SPLIT_COLUMN,
                "train": OOS_TRAIN_KEY,
                "test": OOS_TEST_KEY,
                "validation": OOS_VALIDATION_KEY,
                "min_n_to_lock": OOS_MIN_N,
                "train_n": int(book.oos_n["train"]),
                "validation_n": int(book.oos_n["validation"]),
                "test_n": int(book.oos_n["test"]),
                "train_window": list(book.oos_n["train_window"]),
                "validation_window": list(book.oos_n["validation_window"]),
                "test_window": list(book.oos_n["test_window"]),
                "rule": (
                    "CSV dataset_split. Train = IN_SAMPLE (earlier window). "
                    "Test = OOS (later window). VALIDATION is a measured middle "
                    "fold and is not mixed into train. Full-book EV is not OOS."
                ),
                "slices": book.oos_n["slices"],
            },
            "train": _oos_fold_payload(
                book, fold_name="train", split_key=OOS_TRAIN_KEY, splits=body["splits"]
            ),
            "test": _oos_fold_payload(
                book, fold_name="test", split_key=OOS_TEST_KEY, splits=body["splits"]
            ),
            "validation_n": int(book.oos_n["validation"]),
            "note": (
                "OOS is measured from dataset_split. Not a fill. "
                "No 95% CI. No significance claim. In-sample ≠ OOS."
            ),
        }

    for tau in (81, 83):
        rule = f"FIRST{tau}"
        if rule not in books_out:
            missing = _missing_tau_payload(tau)
            books_out[rule] = missing
            oos_books[rule] = missing

    slice_tiles = [tiles[pid] for pid in SLICE_ORDER if pid in tiles]
    # keep declared order even if a later τ adds a lock with same ids
    for pid in SLICE_ORDER:
        if pid not in tiles and pid in by_id_meta:
            continue

    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "page": "asked_six",
        "live_execution": False,
        "submits": False,
        "universe": "asked_six",
        "path_stops": list(ASKED_SIX_STOPS),
        "books": books_out,
        "pool": {
            "partition_id": "asked_six",
            "sport_label": "Asked-six",
            "slice_label": "NBA 2Q+3Q ∪ NCAAB 1H2+2H1 ∪ WNBA 2Q+3Q",
            "role": "asked_six",
            "ncaab_window_note": NCAAB_WINDOW_NOTE,
            "books": pool_books,
        },
        "partitions": slice_tiles,
        "oos": {
            "status": "OBSERVED",
            "label": "OOS · dataset_split IN_SAMPLE vs OOS",
            "in_sample_note": "Full asked-six EV above is in-sample. It is not OOS.",
            "books": oos_books,
        },
        "verification": {
            "status": verified["status"],
            "sources": verified["sources"],
        },
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ ACTUAL FILL",
            "PAGE · ASKED-SIX · not Texas derived four",
            "asked-six FIRST80 1182 ≠ derived four 936",
            "asked-six FIRST75 1126 ≠ derived four 913",
            "asked-six FIRST77 1158 ≠ derived four 933",
            "FIRST83 ≠ FIRST81 ≠ FIRST77 ≠ FIRST75 ≠ FIRST80",
            "NCAAB 1H/2H are H1_2 / H2_1 10-minute windows, not full halves",
            "55 is the cap book (τ+6). 25–50 use full asked-six N",
            "s_L is not assumed 0",
            "OOS is CSV dataset_split. Full-book EV is not OOS",
            "ledger EV is candle-path theoretical, not a fill or live EV",
        ],
    }


def handle_asked_six() -> dict[str, Any]:
    return build_asked_six()
