"""Fail-closed lock verification. Disagreeing sources are LOCK_MISMATCH."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from roller.choosin_texas.locks import (
    ASKED_SIX_CELLS,
    ASKED_SIX_N,
    BARRIER_55,
    BARRIER_55_POOL_CELLS,
    BARRIER_55_POOL_EXCL,
    BARRIER_55_POOL_L,
    BARRIER_55_POOL_N,
    BARRIER_55_POOL_W,
    BARRIER_STOPS,
    MID_STOPS,
    PARTITIONS,
    POOL_CELLS,
    POOL_L,
    POOL_N,
    POOL_W,
    WNBA_UNION_N,
    Barrier55Lock,
    PartitionLock,
    ladder_cells,
)
from roller.choosin_texas.models import ChoosinTexasError, pct_display, ratio_display
from roller.choosin_texas.rates import (
    assert_identities,
    barrier_55_from_lock,
    ledger_rank,
    mid_paths_from_lock,
    mid_paths_from_pool,
    partition_payload,
    paths_from_lock,
    paths_from_pool,
    pool_payload,
    trade_80_55_payload,
)
from roller.choosin_texas.sources import (
    load_csv_barrier_55,
    load_csv_barriers,
    load_csv_cells,
    load_tables_rows,
)


def _cell_tuple(counts: dict[str, int]) -> tuple[int, int, int, int]:
    return (
        int(counts["win_no"]),
        int(counts["win_t40"]),
        int(counts["lose_no"]),
        int(counts["lose_t40"]),
    )


def _same_barrier_55(lock: Barrier55Lock, counts: dict[str, int], *, source: str) -> None:
    observed = (
        int(counts["n"]),
        int(counts["excluded_hit_86"]),
        int(counts["W"]),
        int(counts["L"]),
        (
            int(counts["win_no"]),
            int(counts["win_t55"]),
            int(counts["lose_no"]),
            int(counts["lose_t55"]),
        ),
    )
    expected = (lock.n, lock.excluded_hit_86, lock.W, lock.L, lock.cells)
    if observed != expected:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"{source} 80/55 {lock.partition_id} {observed} != lock {expected}",
        )


def trade_80_55_pool() -> dict[str, Any]:
    return trade_80_55_payload(
        BARRIER_55_POOL_N,
        BARRIER_55_POOL_W,
        BARRIER_55_POOL_L,
        *BARRIER_55_POOL_CELLS,
        excluded_hit_86=BARRIER_55_POOL_EXCL,
        label="80_55:derived_four",
    )


def _same_row(lock: PartitionLock, counts: dict[str, int], *, source: str) -> None:
    if (
        counts["n"] != lock.n
        or counts["W"] != lock.W
        or counts["L"] != lock.L
        or _cell_tuple(counts) != lock.cells
    ):
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            (
                f"{source} {lock.partition_id} "
                f"n/W/L/cells {counts['n']}/{counts['W']}/{counts['L']}/{_cell_tuple(counts)} "
                f"!= lock {lock.n}/{lock.W}/{lock.L}/{lock.cells}"
            ),
        )


def verify_locks(
    *,
    partitions: tuple[PartitionLock, ...] = PARTITIONS,
    tables_path: Path | None = None,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    for lock in partitions:
        assert_identities(
            lock.n,
            lock.W,
            lock.L,
            lock.win_no,
            lock.win_t40,
            lock.lose_no,
            lock.lose_t40,
            label=f"lock:{lock.partition_id}",
        )
        if lock.lose_no != 0:
            raise ChoosinTexasError(
                "LOCK_MISMATCH", f"{lock.partition_id}: s_L must be 0 on FIRST80 asked four"
            )

    pool_n = sum(p.n for p in partitions)
    pool_w = sum(p.W for p in partitions)
    pool_l = sum(p.L for p in partitions)
    pool_cells = (
        sum(p.win_no for p in partitions),
        sum(p.win_t40 for p in partitions),
        sum(p.lose_no for p in partitions),
        sum(p.lose_t40 for p in partitions),
    )
    if partitions is PARTITIONS:
        if (pool_n, pool_w, pool_l, pool_cells) != (POOL_N, POOL_W, POOL_L, POOL_CELLS):
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"derived four {pool_n}/{pool_w}/{pool_l}/{pool_cells} != {POOL_N}/{POOL_W}/{POOL_L}/{POOL_CELLS}",
            )
    assert_identities(pool_n, pool_w, pool_l, *pool_cells, label="derived_four")

    tables = load_tables_rows(tables_path)
    for lock in partitions:
        row = tables.get((lock.sport, lock.slice))
        if row is None:
            raise ChoosinTexasError(
                "DATA_REQUIRED",
                f"tables.json missing FIRST80 asked_six {lock.sport}/{lock.slice}",
            )
        _same_row(lock, row, source="tables.json")

    csv_body = load_csv_cells(csv_path, partitions=partitions)
    csv_parts = csv_body["partitions"]
    for lock in partitions:
        _same_row(lock, csv_parts[lock.partition_id], source="asked_six_csv")

    barrier_locks = {row.partition_id: row for row in BARRIER_55}
    barrier_csv = load_csv_barrier_55(csv_path, partitions=partitions)["partitions"]
    if partitions is PARTITIONS:
        pool_55_n = pool_55_excl = pool_55_w = pool_55_l = 0
        pool_55_cells = [0, 0, 0, 0]
        for lock in partitions:
            expected = barrier_locks[lock.partition_id]
            observed = barrier_csv[lock.partition_id]
            _same_barrier_55(expected, observed, source="asked_six_csv")
            pool_55_n += expected.n
            pool_55_excl += expected.excluded_hit_86
            pool_55_w += expected.W
            pool_55_l += expected.L
            for i, value in enumerate(expected.cells):
                pool_55_cells[i] += value
        if (
            pool_55_n != BARRIER_55_POOL_N
            or pool_55_excl != BARRIER_55_POOL_EXCL
            or pool_55_w != BARRIER_55_POOL_W
            or pool_55_l != BARRIER_55_POOL_L
            or tuple(pool_55_cells) != BARRIER_55_POOL_CELLS
        ):
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                "80/55 derived four does not match locked 905 / 579/180/0/146",
            )
        if pool_55_n + pool_55_excl != pool_n:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"80/55 {pool_55_n}+{pool_55_excl} != derived four {pool_n}",
            )

        ladder = load_csv_barriers(csv_path, partitions=partitions)["partitions"]
        for stop in BARRIER_STOPS + MID_STOPS + (40,):
            pool_obs = [0, 0, 0, 0]
            for lock in partitions:
                observed = ladder[int(stop)][lock.partition_id]
                cells = (
                    int(observed["win_no"]),
                    int(observed["win_tx"]),
                    int(observed["lose_no"]),
                    int(observed["lose_tx"]),
                )
                expected = ladder_cells(int(stop), lock.partition_id)
                if (
                    int(observed["n"]) != lock.n
                    or int(observed["W"]) != lock.W
                    or int(observed["L"]) != lock.L
                    or cells != expected
                ):
                    raise ChoosinTexasError(
                        "LOCK_MISMATCH",
                        (
                            f"asked_six_csv 80/{stop} {lock.partition_id} "
                            f"{observed['n']}/{observed['W']}/{observed['L']}/{cells} "
                            f"!= lock {lock.n}/{lock.W}/{lock.L}/{expected}"
                        ),
                    )
                if int(observed["lose_no"]) != 0:
                    raise ChoosinTexasError(
                        "LOCK_MISMATCH",
                        f"80/{stop} {lock.partition_id}: s_L must be 0",
                    )
                for i, value in enumerate(cells):
                    pool_obs[i] += value
            if tuple(pool_obs) != ladder_cells(int(stop), "derived_four"):
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"80/{stop} derived four {tuple(pool_obs)} != lock",
                )

    if csv_body["asked_six_n"] != ASKED_SIX_N:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"asked-six CSV N {csv_body['asked_six_n']} != {ASKED_SIX_N}",
        )
    if csv_body["wnba_n"] != WNBA_UNION_N:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"WNBA CSV N {csv_body['wnba_n']} != {WNBA_UNION_N}",
        )
    if pool_n + csv_body["wnba_n"] != ASKED_SIX_N:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"complement {pool_n}+{csv_body['wnba_n']} != {ASKED_SIX_N}",
        )

    from roller.superasi.seed import LOCK_CELLS, LOCK_N

    if LOCK_N != ASKED_SIX_N or tuple(LOCK_CELLS) != ASKED_SIX_CELLS:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            "SuperASI asked-six seed locks drifted from 1182 / 883/108/0/191",
        )

    partitions_out = [partition_payload(lock) for lock in partitions]
    for row in partitions_out:
        share = Fraction(int(row["n"]), pool_n)
        row["n_share_display"] = ratio_display(int(row["n"]), pool_n)
        row["n_share_pct_display"] = pct_display(int(row["n"]), pool_n)
        row["n_bar_pct"] = float(share * 100)
        if partitions is PARTITIONS:
            row["trade_80_55"] = barrier_55_from_lock(barrier_locks[row["partition_id"]])
            lock = next(p for p in partitions if p.partition_id == row["partition_id"])
            row["paths"] = paths_from_lock(lock)
            row["ledger_rank"] = ledger_rank(row["paths"])
            row["mid_paths"] = mid_paths_from_lock(lock)
            row["mid_ledger_rank"] = ledger_rank(row["mid_paths"])

    pool_out = pool_payload(pool_n, pool_w, pool_l, *pool_cells)
    if partitions is PARTITIONS:
        pool_out["trade_80_55"] = trade_80_55_pool()
        pool_out["paths"] = paths_from_pool()
        pool_out["ledger_rank"] = ledger_rank(pool_out["paths"])
        pool_out["mid_paths"] = mid_paths_from_pool()
        pool_out["mid_ledger_rank"] = ledger_rank(pool_out["mid_paths"])

    return {
        "status": "OBSERVED",
        "partitions": partitions_out,
        "pool": pool_out,
        "complement": {
            "asked_six_n": ASKED_SIX_N,
            "asked_six_cells": list(ASKED_SIX_CELLS),
            "wnba_2q_3q_n": WNBA_UNION_N,
            "derived_four_n": pool_n,
            "identity": f"{ASKED_SIX_N} = {pool_n} + {WNBA_UNION_N}",
            "superasi_seed_n": LOCK_N,
            "superasi_seed_cells": list(LOCK_CELLS),
            "note": "Complement only. Choosin Texas universe is derived_four, not asked-six.",
        },
        "sources": [
            "tables_md_locks",
            "docs/research/lebronner/tables.json",
            "research/first80_asked_six_chatgpt_export/first80_asked_six.csv",
            "roller.superasi.seed LOCK_N/LOCK_CELLS",
            "asked_six_csv 80/55 entry<86",
            "asked_six_csv barrier ladder 25/30/35/40/45/50",
            "asked_six_csv mid-stop tile 33/37/43/47",
        ],
    }
