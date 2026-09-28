"""Derived-four FIRST81 / FIRST83 companion tiles. Not live 80/81/83."""

from __future__ import annotations

import importlib
from typing import Any

from roller.choosin_texas.asked_six import tau_path_payload
from roller.choosin_texas.locks import Barrier55Lock, PartitionLock
from roller.choosin_texas.locks_asked_six import ASKED_SIX_STOPS, FULL_ASKED_STOPS, cap_cents_for_tau
from roller.choosin_texas.models import ChoosinTexasError, pct_display, ratio_display
from roller.choosin_texas.rates import assert_identities, ledger_rank
from roller.choosin_texas.sources import (
    default_asked_six_csv_for_tau,
    load_csv_barrier_55,
    load_csv_barriers,
    load_csv_cells,
)


def _same_row(lock: PartitionLock, counts: dict[str, int], *, source: str, tau: int) -> None:
    cells = (
        int(counts["win_no"]),
        int(counts.get("win_t40", counts.get("win_tx", -1))),
        int(counts["lose_no"]),
        int(counts.get("lose_t40", counts.get("lose_tx", -1))),
    )
    if (
        int(counts["n"]) != lock.n
        or int(counts["W"]) != lock.W
        or int(counts["L"]) != lock.L
        or cells != lock.cells
    ):
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            (
                f"{source} FIRST{tau} {lock.partition_id} "
                f"{counts['n']}/{counts['W']}/{counts['L']}/{cells} "
                f"!= {lock.n}/{lock.W}/{lock.L}/{lock.cells}"
            ),
        )


def handle_universe_tau(tau: int) -> dict[str, Any]:
    csv_file = default_asked_six_csv_for_tau(tau)
    if not csv_file.is_file():
        raise ChoosinTexasError(
            "DATA_REQUIRED",
            (
                f"FIRST{tau} asked-six CSV missing at {csv_file}. "
                "TABLES.md has no this τ. Collect before locking. Do not invent N."
            ),
        )
    try:
        locks = importlib.import_module(f"roller.choosin_texas.locks{tau}")
    except ImportError as exc:
        raise ChoosinTexasError(
            "DATA_REQUIRED",
            f"FIRST{tau} derived-four locks not written yet. CSV exists at {csv_file}.",
        ) from exc

    partitions: tuple[PartitionLock, ...] = getattr(locks, f"PARTITIONS_{tau}")
    pool_n = getattr(locks, f"POOL_N_{tau}")
    pool_w = getattr(locks, f"POOL_W_{tau}")
    pool_l = getattr(locks, f"POOL_L_{tau}")
    pool_cells = getattr(locks, f"POOL_CELLS_{tau}")
    asked_n = getattr(locks, f"ASKED_SIX_N_{tau}")
    asked_cells = getattr(locks, f"ASKED_SIX_CELLS_{tau}")
    wnba_n = getattr(locks, f"WNBA_UNION_N_{tau}")
    wnba_cells = getattr(locks, f"WNBA_UNION_CELLS_{tau}")
    barrier_55: tuple[Barrier55Lock, ...] = getattr(locks, f"BARRIER_55_{tau}")
    barrier_55_pool_n = getattr(locks, f"BARRIER_55_POOL_N_{tau}")
    barrier_55_pool_excl = getattr(locks, f"BARRIER_55_POOL_EXCL_{tau}")
    barrier_55_pool_w = getattr(locks, f"BARRIER_55_POOL_W_{tau}")
    barrier_55_pool_l = getattr(locks, f"BARRIER_55_POOL_L_{tau}")
    barrier_55_pool_cells = getattr(locks, f"BARRIER_55_POOL_CELLS_{tau}")
    ladder_cells = getattr(locks, f"ladder_cells_{tau}")
    cap = cap_cents_for_tau(tau)

    for lock in partitions:
        assert_identities(
            lock.n, lock.W, lock.L, lock.win_no, lock.win_t40, lock.lose_no, lock.lose_t40,
            label=f"lock{tau}:{lock.partition_id}",
        )
    got_n = sum(p.n for p in partitions)
    got_w = sum(p.W for p in partitions)
    got_l = sum(p.L for p in partitions)
    got_cells = (
        sum(p.win_no for p in partitions),
        sum(p.win_t40 for p in partitions),
        sum(p.lose_no for p in partitions),
        sum(p.lose_t40 for p in partitions),
    )
    if (got_n, got_w, got_l, got_cells) != (pool_n, pool_w, pool_l, pool_cells):
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{tau} derived four {got_n}/{got_w}/{got_l}/{got_cells} != {pool_n}/{pool_w}/{pool_l}/{pool_cells}",
        )
    if got_n + wnba_n != asked_n:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{tau} complement {got_n}+{wnba_n} != {asked_n}",
        )
    if tuple(c + d for c, d in zip(pool_cells, wnba_cells)) != asked_cells:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{tau} asked-six cells {tuple(c + d for c, d in zip(pool_cells, wnba_cells))} != {asked_cells}",
        )

    csv_body = load_csv_cells(csv_file, partitions=partitions)
    if csv_body["asked_six_n"] != asked_n:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{tau} CSV N {csv_body['asked_six_n']} != {asked_n}",
        )
    if csv_body["wnba_n"] != wnba_n:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"FIRST{tau} WNBA CSV N {csv_body['wnba_n']} != {wnba_n}",
        )
    for lock in partitions:
        _same_row(lock, csv_body["partitions"][lock.partition_id], source=f"asked_six_{tau}_csv", tau=tau)

    barrier_csv = load_csv_barrier_55(
        csv_file, partitions=partitions, entry_cents=tau, cap_cents=cap
    )["partitions"]
    barrier_locks = {row.partition_id: row for row in barrier_55}
    pool_55 = [0, 0, 0, 0, 0, 0, 0, 0]
    for lock in partitions:
        expected = barrier_locks[lock.partition_id]
        obs = barrier_csv[lock.partition_id]
        observed = (
            int(obs["n"]),
            int(obs["excluded_hit_86"]),
            int(obs["W"]),
            int(obs["L"]),
            (int(obs["win_no"]), int(obs["win_t55"]), int(obs["lose_no"]), int(obs["lose_t55"])),
        )
        exp = (expected.n, expected.excluded_hit_86, expected.W, expected.L, expected.cells)
        if observed != exp:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"{tau}/55 {lock.partition_id} {observed} != {exp}",
            )
        pool_55[0] += expected.n
        pool_55[1] += expected.excluded_hit_86
        pool_55[2] += expected.W
        pool_55[3] += expected.L
        for i, value in enumerate(expected.cells):
            pool_55[4 + i] += value
    if (
        pool_55[0] != barrier_55_pool_n
        or pool_55[1] != barrier_55_pool_excl
        or pool_55[2] != barrier_55_pool_w
        or pool_55[3] != barrier_55_pool_l
        or tuple(pool_55[4:]) != barrier_55_pool_cells
    ):
        raise ChoosinTexasError("LOCK_MISMATCH", f"{tau}/55 derived four pool mismatch")
    if pool_55[0] + pool_55[1] != pool_n:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"{tau}/55 {pool_55[0]}+{pool_55[1]} != derived four {pool_n}",
        )

    ladder = load_csv_barriers(csv_file, partitions=partitions, stops=FULL_ASKED_STOPS)["partitions"]
    for stop in FULL_ASKED_STOPS:
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
                or cells != expected
            ):
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"{tau}/{stop} {lock.partition_id} {cells} != {expected}",
                )
            for i, value in enumerate(cells):
                pool_obs[i] += value
        if tuple(pool_obs) != ladder_cells(int(stop), "derived_four"):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{tau}/{stop} derived four mismatch")

    def _paths(lock: PartitionLock | None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for stop in ASKED_SIX_STOPS:
            if stop == 55:
                if lock is None:
                    out.append(
                        tau_path_payload(
                            tau=tau,
                            stop_cents=55,
                            n=barrier_55_pool_n,
                            cells=barrier_55_pool_cells,
                            label=f"{tau}_55:derived_four",
                            excluded=barrier_55_pool_excl,
                        )
                    )
                else:
                    row = barrier_locks[lock.partition_id]
                    out.append(
                        tau_path_payload(
                            tau=tau,
                            stop_cents=55,
                            n=row.n,
                            cells=row.cells,
                            label=f"{tau}_55:{lock.partition_id}",
                            excluded=row.excluded_hit_86,
                        )
                    )
                continue
            pid = "derived_four" if lock is None else lock.partition_id
            n = pool_n if lock is None else lock.n
            w = pool_w if lock is None else lock.W
            lose = pool_l if lock is None else lock.L
            cells = ladder_cells(stop, pid)
            out.append(
                tau_path_payload(
                    tau=tau,
                    stop_cents=stop,
                    n=n,
                    cells=cells,
                    label=f"{tau}_{stop}:{pid}",
                )
            )
        return out

    partitions_out = []
    for lock in partitions:
        paths = _paths(lock)
        share_n = lock.n
        partitions_out.append(
            {
                "partition_id": lock.partition_id,
                "sport_label": lock.sport_label,
                "slice_label": lock.slice_label,
                "role": "asked_six_slice",
                "rule": f"FIRST{tau}",
                "n": lock.n,
                "W": lock.W,
                "L": lock.L,
                "cells": {
                    "W_and_not_T40": lock.win_no,
                    "W_and_T40": lock.win_t40,
                    "L_and_not_T40": lock.lose_no,
                    "L_and_T40": lock.lose_t40,
                },
                "paths": paths,
                "ledger_rank": ledger_rank(paths),
                "n_share_display": ratio_display(share_n, pool_n),
                "n_share_pct_display": pct_display(share_n, pool_n),
                "n_bar_pct": float(share_n) * 100.0 / float(pool_n),
            }
        )

    pool_paths = _paths(None)
    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "page": f"texas_{tau}_companion",
        "live_execution": False,
        "submits": False,
        "rule": f"FIRST{tau}",
        "entry_cents": tau,
        "entry_cap_cents": cap,
        "gain_cents": 100 - tau,
        "path_stops": list(ASKED_SIX_STOPS),
        "unit": f"FIRST{tau} trigger events. Not Kalshi prints. Not live 80/81/83.",
        "partitions": partitions_out,
        "pool": {
            "partition_id": "derived_four",
            "sport_label": "NBA + NCAAB P5",
            "slice_label": "NBA 2Q+3Q ∪ NCAAB 1H2+2H1",
            "role": "derived_four",
            "rule": f"FIRST{tau}",
            "n": pool_n,
            "W": pool_w,
            "L": pool_l,
            "cells": {
                "W_and_not_T40": pool_cells[0],
                "W_and_T40": pool_cells[1],
                "L_and_not_T40": pool_cells[2],
                "L_and_T40": pool_cells[3],
            },
            "paths": pool_paths,
            "ledger_rank": ledger_rank(pool_paths),
            "note": (
                f"Derived four FIRST{tau}. Not asked-six ({asked_n}). "
                "Candle path ≠ fill. Not a live 80/81/83 rule."
            ),
        },
        "complement": {
            "asked_six_n": asked_n,
            "asked_six_cells": list(asked_cells),
            "wnba_2q_3q_n": wnba_n,
            "derived_four_n": pool_n,
            "identity": f"{asked_n} = {pool_n} + {wnba_n}",
            "note": f"Complement only. This tile is FIRST{tau} derived_four, not asked-six.",
        },
        "verification": {
            "status": "OBSERVED",
            "sources": [
                f"research/first{tau}_asked_six_chatgpt_export/first{tau}_asked_six.csv",
                f"locks{tau}.py",
            ],
        },
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ ACTUAL FILL",
            f"FIRST{tau} is an entry threshold, not a stop on 75/77/80",
            f"asked-six FIRST{tau} {asked_n} ≠ derived four {pool_n}",
            "RESEARCH_REGISTERED ≠ LIVE_ARMED",
            "Does not change live FIRST01 / 80/81/83/89",
        ],
    }
