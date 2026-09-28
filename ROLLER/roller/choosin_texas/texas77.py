"""FIRST77 Texas clone. Reconstructs first77_asked_six.csv. TABLES.md has no FIRST77."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from roller.choosin_texas.ev import ev_payload
from roller.choosin_texas.locks import Barrier55Lock, PartitionLock
from roller.choosin_texas.locks77 import (
    ASKED_SIX_CELLS_77,
    ASKED_SIX_N_77,
    BARRIER_55_77,
    BARRIER_55_POOL_CELLS_77,
    BARRIER_55_POOL_EXCL_77,
    BARRIER_55_POOL_L_77,
    BARRIER_55_POOL_N_77,
    BARRIER_55_POOL_W_77,
    BARRIER_STOPS_77,
    ENTRY_CAP_CENTS_77,
    ENTRY_CENTS_77,
    GAIN_CENTS_77,
    K_DENOM_77,
    K_NUMER_77,
    MID_STOPS_77,
    PARTITIONS_77,
    PATH_STOPS_77,
    POOL_CELLS_77,
    POOL_L_77,
    POOL_N_77,
    POOL_W_77,
    RULE_77,
    STOP_55_CENTS_77,
    STOP_CENTS_77,
    WNBA_PARTITIONS_77,
    WNBA_UNION_CELLS_77,
    WNBA_UNION_N_77,
    ladder_cells_77,
    loss_cents_for_stop_77,
)
from roller.choosin_texas.models import ChoosinTexasError, frac, pct_display, ratio_display
from roller.choosin_texas.rates import assert_identities, ledger_rank, rates_from_cells
from roller.choosin_texas.sources import (
    default_asked_six_77_csv,
    load_csv_barrier_55,
    load_csv_barriers,
    load_csv_cells,
)
from roller.results_math.proportions import wilson_interval


def _cell_tuple(counts: dict[str, int]) -> tuple[int, int, int, int]:
    return (
        int(counts["win_no"]),
        int(counts["win_t40"]),
        int(counts["lose_no"]),
        int(counts["lose_t40"]),
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
                f"{source} FIRST77 {lock.partition_id} "
                f"n/W/L/cells {counts['n']}/{counts['W']}/{counts['L']}/{_cell_tuple(counts)} "
                f"!= lock {lock.n}/{lock.W}/{lock.L}/{lock.cells}"
            ),
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
            f"{source} 77/55 {lock.partition_id} {observed} != lock {expected}",
        )


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


def path_payload_77(
    n: int,
    w: int,
    lose: int,
    win_no: int,
    win_tx: int,
    lose_no: int,
    lose_tx: int,
    *,
    stop_cents: int,
    label: str,
    excluded_hit_83: int | None = None,
) -> dict[str, Any]:
    assert_identities(n, w, lose, win_no, win_tx, lose_no, lose_tx, label=label)
    s_n = win_no + lose_no
    trade_l = n - s_n
    s = Fraction(s_n, n)
    loss = loss_cents_for_stop_77(stop_cents)
    ev = ev_payload(
        n=n,
        s_n=s_n,
        stop_cents=stop_cents,
        gain_cents=GAIN_CENTS_77,
        loss_cents=loss,
    )
    body: dict[str, Any] = {
        "key": f"77/{stop_cents}",
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
        "S_wilson": _wilson_pct(s_n, n),
        "gain_cents": GAIN_CENTS_77,
        "loss_cents": loss,
        "note": (
            f"S = P(¬T{stop_cents}). EV = {GAIN_CENTS_77}S − {loss}(1−S). "
            "Candle path ≠ fill. Not live EV."
        ),
        **ev,
    }
    if excluded_hit_83 is not None:
        body["excluded_hit_83"] = excluded_hit_83
        body["excluded_hit_86"] = excluded_hit_83
        body["filter"] = {
            "entry_yes_bid_lt": ENTRY_CAP_CENTS_77,
            "excluded_hit_83": excluded_hit_83,
            "n_full": n + excluded_hit_83,
            "note": (
                "Only FIRST77 prints still below 83. "
                "If the first ≥77 close is already ≥83, do not count."
            ),
        }
        body["note"] = (
            "S = P(¬T55 | entry yes_bid < 83). EV = 23S − 22(1−S). "
            "Candle path ≠ fill. Not live EV."
        )
    return body


def trade_77_55_payload(
    n: int,
    w: int,
    lose: int,
    win_no: int,
    win_t55: int,
    lose_no: int,
    lose_t55: int,
    *,
    excluded_hit_83: int,
    label: str,
) -> dict[str, Any]:
    body = path_payload_77(
        n,
        w,
        lose,
        win_no,
        win_t55,
        lose_no,
        lose_t55,
        stop_cents=STOP_55_CENTS_77,
        label=label,
        excluded_hit_83=excluded_hit_83,
    )
    body.update(
        {
            "excluded_hit_83": excluded_hit_83,
            "terminal": {
                "wins": w,
                "losses": lose,
                "p": frac(w, n),
                "p_display": ratio_display(w, n),
                "p_pct_display": pct_display(w, n),
                "p_bar_pct": float(Fraction(w, n) * 100),
                "loss_display": ratio_display(lose, n),
                "loss_pct_display": pct_display(lose, n),
                "note": "Terminal YES on the entry<83 subset. Not 77/55 S.",
            },
        }
    )
    return body


def _trade_77_40(
    n: int,
    w: int,
    lose: int,
    win_no: int,
    win_t40: int,
    lose_no: int,
    lose_t40: int,
    *,
    label: str,
) -> dict[str, Any]:
    body = rates_from_cells(
        n, w, lose, win_no, win_t40, lose_no, lose_t40, label=label
    )
    trade = path_payload_77(
        n,
        w,
        lose,
        win_no,
        win_t40,
        lose_no,
        lose_t40,
        stop_cents=STOP_CENTS_77,
        label=label,
    )
    k = Fraction(K_NUMER_77, K_DENOM_77)
    p = Fraction(w, n)
    alpha = p - k
    body["K"] = {"numer": K_NUMER_77, "denom": K_DENOM_77}
    body["stop_cents"] = STOP_CENTS_77
    body["entry_cents"] = ENTRY_CENTS_77
    body["gain_cents"] = GAIN_CENTS_77
    body["alpha"] = {
        "numer": alpha.numerator,
        "denom": alpha.denominator,
        "status": "DERIVED",
        "K": {"numer": K_NUMER_77, "denom": K_DENOM_77},
        "pp_display": f"{float(alpha * 100):+.4f}",
    }
    body["terminal"]["note"] = (
        "Settlement YES given FIRST77. Not the 77/40 trade win rate."
    )
    body["trade_77_40"] = trade
    del body["trade_80_40"]
    return body


def paths_from_lock_77(lock: PartitionLock) -> list[dict[str, Any]]:
    barrier_55 = {row.partition_id: row for row in BARRIER_55_77}[lock.partition_id]
    out: list[dict[str, Any]] = []
    for stop in PATH_STOPS_77:
        if stop == 55:
            out.append(
                path_payload_77(
                    barrier_55.n,
                    barrier_55.W,
                    barrier_55.L,
                    barrier_55.win_no,
                    barrier_55.win_t55,
                    barrier_55.lose_no,
                    barrier_55.lose_t55,
                    stop_cents=55,
                    label=f"77_55:{lock.partition_id}",
                    excluded_hit_83=barrier_55.excluded_hit_86,
                )
            )
            continue
        win_no, win_tx, lose_no, lose_tx = ladder_cells_77(stop, lock.partition_id)
        out.append(
            path_payload_77(
                lock.n,
                lock.W,
                lock.L,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"77_{stop}:{lock.partition_id}",
            )
        )
    return out


def paths_from_pool_77() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in PATH_STOPS_77:
        if stop == 55:
            out.append(
                path_payload_77(
                    BARRIER_55_POOL_N_77,
                    BARRIER_55_POOL_W_77,
                    BARRIER_55_POOL_L_77,
                    *BARRIER_55_POOL_CELLS_77,
                    stop_cents=55,
                    label="77_55:derived_four",
                    excluded_hit_83=BARRIER_55_POOL_EXCL_77,
                )
            )
            continue
        win_no, win_tx, lose_no, lose_tx = ladder_cells_77(stop, "derived_four")
        out.append(
            path_payload_77(
                POOL_N_77,
                POOL_W_77,
                POOL_L_77,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"77_{stop}:derived_four",
            )
        )
    return out


def mid_paths_from_lock_77(lock: PartitionLock) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in MID_STOPS_77:
        win_no, win_tx, lose_no, lose_tx = ladder_cells_77(stop, lock.partition_id)
        out.append(
            path_payload_77(
                lock.n,
                lock.W,
                lock.L,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"77_{stop}:{lock.partition_id}",
            )
        )
    return out


def mid_paths_from_pool_77() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in MID_STOPS_77:
        win_no, win_tx, lose_no, lose_tx = ladder_cells_77(stop, "derived_four")
        out.append(
            path_payload_77(
                POOL_N_77,
                POOL_W_77,
                POOL_L_77,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"77_{stop}:derived_four",
            )
        )
    return out


def partition_payload_77(lock: PartitionLock) -> dict[str, Any]:
    body = _trade_77_40(
        lock.n,
        lock.W,
        lock.L,
        lock.win_no,
        lock.win_t40,
        lock.lose_no,
        lock.lose_t40,
        label=f"first77:{lock.partition_id}",
    )
    barrier = {row.partition_id: row for row in BARRIER_55_77}[lock.partition_id]
    paths = paths_from_lock_77(lock)
    mid_paths = mid_paths_from_lock_77(lock)
    body.update(
        {
            "partition_id": lock.partition_id,
            "sport": lock.sport,
            "sport_label": lock.sport_label,
            "slice": lock.slice,
            "slice_label": lock.slice_label,
            "role": "asked_six_slice",
            "rule": RULE_77,
            "trade_77_55": trade_77_55_payload(
                barrier.n,
                barrier.W,
                barrier.L,
                barrier.win_no,
                barrier.win_t55,
                barrier.lose_no,
                barrier.lose_t55,
                excluded_hit_83=barrier.excluded_hit_86,
                label=f"77_55:{lock.partition_id}",
            ),
            "paths": paths,
            "ledger_rank": ledger_rank(paths),
            "mid_paths": mid_paths,
            "mid_ledger_rank": ledger_rank(mid_paths),
        }
    )
    return body


def pool_payload_77() -> dict[str, Any]:
    body = _trade_77_40(
        POOL_N_77,
        POOL_W_77,
        POOL_L_77,
        *POOL_CELLS_77,
        label="first77:derived_four",
    )
    paths = paths_from_pool_77()
    mid_paths = mid_paths_from_pool_77()
    body.update(
        {
            "partition_id": "derived_four",
            "sport": "nba_ncaab_p5",
            "sport_label": "NBA + NCAAB P5",
            "slice": "asked_four",
            "slice_label": "NBA 2Q+3Q ∪ NCAAB 1H2+2H1",
            "role": "derived_four",
            "rule": RULE_77,
            "note": "Derived union of the four FIRST77 slices. Not asked-six (1158).",
            "trade_77_55": trade_77_55_payload(
                BARRIER_55_POOL_N_77,
                BARRIER_55_POOL_W_77,
                BARRIER_55_POOL_L_77,
                *BARRIER_55_POOL_CELLS_77,
                excluded_hit_83=BARRIER_55_POOL_EXCL_77,
                label="77_55:derived_four",
            ),
            "paths": paths,
            "ledger_rank": ledger_rank(paths),
            "mid_paths": mid_paths,
            "mid_ledger_rank": ledger_rank(mid_paths),
        }
    )
    return body


def verify_locks_77(
    *,
    partitions: tuple[PartitionLock, ...] = PARTITIONS_77,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    csv_file = csv_path or default_asked_six_77_csv()
    for lock in partitions:
        assert_identities(
            lock.n,
            lock.W,
            lock.L,
            lock.win_no,
            lock.win_t40,
            lock.lose_no,
            lock.lose_t40,
            label=f"lock77:{lock.partition_id}",
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
    if partitions is PARTITIONS_77:
        if (pool_n, pool_w, pool_l, pool_cells) != (
            POOL_N_77,
            POOL_W_77,
            POOL_L_77,
            POOL_CELLS_77,
        ):
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                (
                    f"FIRST77 derived four {pool_n}/{pool_w}/{pool_l}/{pool_cells} "
                    f"!= {POOL_N_77}/{POOL_W_77}/{POOL_L_77}/{POOL_CELLS_77}"
                ),
            )
    assert_identities(pool_n, pool_w, pool_l, *pool_cells, label="first77:derived_four")

    wnba_n = 0
    wnba_cells = [0, 0, 0, 0]
    for lock in WNBA_PARTITIONS_77:
        wnba_n += lock.n
        for i, value in enumerate(lock.cells):
            wnba_cells[i] += value
    if partitions is PARTITIONS_77:
        if wnba_n != WNBA_UNION_N_77 or tuple(wnba_cells) != WNBA_UNION_CELLS_77:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST77 WNBA complement {wnba_n}/{tuple(wnba_cells)} "
                f"!= {WNBA_UNION_N_77}/{WNBA_UNION_CELLS_77}",
            )
        asked_n = pool_n + wnba_n
        asked_cells = tuple(pool_cells[i] + wnba_cells[i] for i in range(4))
        if asked_n != ASKED_SIX_N_77 or asked_cells != ASKED_SIX_CELLS_77:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST77 asked-six {asked_n}/{asked_cells} "
                f"!= {ASKED_SIX_N_77}/{ASKED_SIX_CELLS_77}",
            )

    csv_body = load_csv_cells(csv_file, partitions=partitions)
    for lock in partitions:
        _same_row(lock, csv_body["partitions"][lock.partition_id], source="asked_six_77_csv")
    if partitions is PARTITIONS_77:
        if csv_body["asked_six_n"] != ASKED_SIX_N_77:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST77 CSV N {csv_body['asked_six_n']} != {ASKED_SIX_N_77}",
            )
        if csv_body["wnba_n"] != WNBA_UNION_N_77:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST77 WNBA CSV N {csv_body['wnba_n']} != {WNBA_UNION_N_77}",
            )
        if pool_n + csv_body["wnba_n"] != ASKED_SIX_N_77:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST77 complement {pool_n}+{csv_body['wnba_n']} != {ASKED_SIX_N_77}",
            )
        wnba_csv = load_csv_cells(csv_file, partitions=WNBA_PARTITIONS_77)
        for lock in WNBA_PARTITIONS_77:
            _same_row(
                lock,
                wnba_csv["partitions"][lock.partition_id],
                source="asked_six_77_csv",
            )

        barrier_locks = {row.partition_id: row for row in BARRIER_55_77}
        barrier_csv = load_csv_barrier_55(
            csv_file,
            partitions=partitions,
            entry_cents=ENTRY_CENTS_77,
            cap_cents=ENTRY_CAP_CENTS_77,
        )["partitions"]
        pool_55_n = pool_55_excl = pool_55_w = pool_55_l = 0
        pool_55_cells = [0, 0, 0, 0]
        for lock in partitions:
            expected = barrier_locks[lock.partition_id]
            observed = barrier_csv[lock.partition_id]
            _same_barrier_55(expected, observed, source="asked_six_77_csv")
            pool_55_n += expected.n
            pool_55_excl += expected.excluded_hit_86
            pool_55_w += expected.W
            pool_55_l += expected.L
            for i, value in enumerate(expected.cells):
                pool_55_cells[i] += value
        if (
            pool_55_n != BARRIER_55_POOL_N_77
            or pool_55_excl != BARRIER_55_POOL_EXCL_77
            or pool_55_w != BARRIER_55_POOL_W_77
            or pool_55_l != BARRIER_55_POOL_L_77
            or tuple(pool_55_cells) != BARRIER_55_POOL_CELLS_77
        ):
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                "77/55 derived four does not match locked 883 / 506/196/1/180",
            )
        if pool_55_n + pool_55_excl != pool_n:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"77/55 {pool_55_n}+{pool_55_excl} != derived four {pool_n}",
            )

        ladder = load_csv_barriers(csv_file, partitions=partitions)["partitions"]
        for stop in BARRIER_STOPS_77 + MID_STOPS_77 + (40,):
            pool_obs = [0, 0, 0, 0]
            for lock in partitions:
                observed = ladder[int(stop)][lock.partition_id]
                cells = (
                    int(observed["win_no"]),
                    int(observed["win_tx"]),
                    int(observed["lose_no"]),
                    int(observed["lose_tx"]),
                )
                expected = ladder_cells_77(int(stop), lock.partition_id)
                if (
                    int(observed["n"]) != lock.n
                    or int(observed["W"]) != lock.W
                    or int(observed["L"]) != lock.L
                    or cells != expected
                ):
                    raise ChoosinTexasError(
                        "LOCK_MISMATCH",
                        (
                            f"asked_six_77_csv 77/{stop} {lock.partition_id} "
                            f"{observed['n']}/{observed['W']}/{observed['L']}/{cells} "
                            f"!= lock {lock.n}/{lock.W}/{lock.L}/{expected}"
                        ),
                    )
                for i, value in enumerate(cells):
                    pool_obs[i] += value
            if tuple(pool_obs) != ladder_cells_77(int(stop), "derived_four"):
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"77/{stop} derived four {tuple(pool_obs)} != lock",
                )

    partitions_out = [partition_payload_77(lock) for lock in partitions]
    for row in partitions_out:
        share = Fraction(int(row["n"]), pool_n)
        row["n_share_display"] = ratio_display(int(row["n"]), pool_n)
        row["n_share_pct_display"] = pct_display(int(row["n"]), pool_n)
        row["n_bar_pct"] = float(share * 100)

    return {
        "status": "OBSERVED",
        "partitions": partitions_out,
        "pool": pool_payload_77(),
        "complement": {
            "asked_six_n": ASKED_SIX_N_77,
            "asked_six_cells": list(ASKED_SIX_CELLS_77),
            "wnba_2q_3q_n": WNBA_UNION_N_77,
            "wnba_2q_3q_cells": list(WNBA_UNION_CELLS_77),
            "derived_four_n": pool_n,
            "identity": f"{ASKED_SIX_N_77} = {pool_n} + {WNBA_UNION_N_77}",
            "note": (
                "Complement only. Texas (77) universe is FIRST77 derived_four, "
                "not asked-six and not FIRST80 936."
            ),
        },
        "sources": [
            "locks77_first77_asked_four",
            "research/first77_asked_six_chatgpt_export/first77_asked_six.csv",
            "asked_six_77_csv 77/55 entry<83",
            "asked_six_77_csv barrier ladder 25/30/35/40/45/50",
            "asked_six_77_csv mid-stop tile 33/37/43/47",
        ],
    }
