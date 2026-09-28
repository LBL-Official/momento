"""FIRST75 Texas clone. Reconstructs TABLES.md + first75_asked_six.csv."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from roller.choosin_texas.ev import ev_payload
from roller.choosin_texas.locks import Barrier55Lock, PartitionLock
from roller.choosin_texas.locks75 import (
    ASKED_SIX_CELLS_75,
    ASKED_SIX_N_75,
    BARRIER_55_75,
    BARRIER_55_POOL_CELLS_75,
    BARRIER_55_POOL_EXCL_75,
    BARRIER_55_POOL_L_75,
    BARRIER_55_POOL_N_75,
    BARRIER_55_POOL_W_75,
    BARRIER_STOPS_75,
    ENTRY_CAP_CENTS_75,
    ENTRY_CENTS_75,
    GAIN_CENTS_75,
    K_DENOM_75,
    K_NUMER_75,
    MID_STOPS_75,
    PARTITIONS_75,
    PATH_STOPS_75,
    POOL_CELLS_75,
    POOL_L_75,
    POOL_N_75,
    POOL_W_75,
    RULE_75,
    STOP_55_CENTS_75,
    STOP_CENTS_75,
    WNBA_PARTITIONS_75,
    WNBA_UNION_CELLS_75,
    WNBA_UNION_N_75,
    ladder_cells_75,
    loss_cents_for_stop_75,
)
from roller.choosin_texas.models import ChoosinTexasError, frac, pct_display, ratio_display
from roller.choosin_texas.rates import assert_identities, ledger_rank, rates_from_cells
from roller.choosin_texas.sources import (
    default_asked_six_75_csv,
    load_csv_barrier_55,
    load_csv_barriers,
    load_csv_cells,
    load_tables_asked_six,
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
                f"{source} FIRST75 {lock.partition_id} "
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
            f"{source} 75/55 {lock.partition_id} {observed} != lock {expected}",
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


def path_payload_75(
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
    excluded_hit_81: int | None = None,
) -> dict[str, Any]:
    assert_identities(n, w, lose, win_no, win_tx, lose_no, lose_tx, label=label)
    s_n = win_no + lose_no
    trade_l = n - s_n
    s = Fraction(s_n, n)
    loss = loss_cents_for_stop_75(stop_cents)
    ev = ev_payload(
        n=n,
        s_n=s_n,
        stop_cents=stop_cents,
        gain_cents=GAIN_CENTS_75,
        loss_cents=loss,
    )
    body: dict[str, Any] = {
        "key": f"75/{stop_cents}",
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
        "gain_cents": GAIN_CENTS_75,
        "loss_cents": loss,
        "note": (
            f"S = P(¬T{stop_cents}). EV = {GAIN_CENTS_75}S − {loss}(1−S). "
            "Candle path ≠ fill. Not live EV."
        ),
        **ev,
    }
    if excluded_hit_81 is not None:
        body["excluded_hit_81"] = excluded_hit_81
        body["excluded_hit_86"] = excluded_hit_81
        body["filter"] = {
            "entry_yes_bid_lt": ENTRY_CAP_CENTS_75,
            "excluded_hit_81": excluded_hit_81,
            "n_full": n + excluded_hit_81,
            "note": (
                "Only FIRST75 prints still below 81. "
                "If the first ≥75 close is already ≥81, do not count."
            ),
        }
        body["note"] = (
            "S = P(¬T55 | entry yes_bid < 81). EV = 25S − 20(1−S). "
            "Candle path ≠ fill. Not live EV."
        )
    return body


def trade_75_55_payload(
    n: int,
    w: int,
    lose: int,
    win_no: int,
    win_t55: int,
    lose_no: int,
    lose_t55: int,
    *,
    excluded_hit_81: int,
    label: str,
) -> dict[str, Any]:
    body = path_payload_75(
        n,
        w,
        lose,
        win_no,
        win_t55,
        lose_no,
        lose_t55,
        stop_cents=STOP_55_CENTS_75,
        label=label,
        excluded_hit_81=excluded_hit_81,
    )
    body.update(
        {
            "excluded_hit_81": excluded_hit_81,
            "terminal": {
                "wins": w,
                "losses": lose,
                "p": frac(w, n),
                "p_display": ratio_display(w, n),
                "p_pct_display": pct_display(w, n),
                "p_bar_pct": float(Fraction(w, n) * 100),
                "loss_display": ratio_display(lose, n),
                "loss_pct_display": pct_display(lose, n),
                "note": "Terminal YES on the entry<81 subset. Not 75/55 S.",
            },
        }
    )
    return body


def _trade_75_40(
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
    trade = path_payload_75(
        n,
        w,
        lose,
        win_no,
        win_t40,
        lose_no,
        lose_t40,
        stop_cents=STOP_CENTS_75,
        label=label,
    )
    k = Fraction(K_NUMER_75, K_DENOM_75)
    p = Fraction(w, n)
    alpha = p - k
    body["K"] = {"numer": K_NUMER_75, "denom": K_DENOM_75}
    body["stop_cents"] = STOP_CENTS_75
    body["entry_cents"] = ENTRY_CENTS_75
    body["gain_cents"] = GAIN_CENTS_75
    body["alpha"] = {
        "numer": alpha.numerator,
        "denom": alpha.denominator,
        "status": "DERIVED",
        "K": {"numer": K_NUMER_75, "denom": K_DENOM_75},
        "pp_display": f"{float(alpha * 100):+.4f}",
    }
    body["terminal"]["note"] = (
        "Settlement YES given FIRST75. Not the 75/40 trade win rate."
    )
    body["trade_75_40"] = trade
    del body["trade_80_40"]
    return body


def paths_from_lock_75(lock: PartitionLock) -> list[dict[str, Any]]:
    barrier_55 = {row.partition_id: row for row in BARRIER_55_75}[lock.partition_id]
    out: list[dict[str, Any]] = []
    for stop in PATH_STOPS_75:
        if stop == 55:
            out.append(
                path_payload_75(
                    barrier_55.n,
                    barrier_55.W,
                    barrier_55.L,
                    barrier_55.win_no,
                    barrier_55.win_t55,
                    barrier_55.lose_no,
                    barrier_55.lose_t55,
                    stop_cents=55,
                    label=f"75_55:{lock.partition_id}",
                    excluded_hit_81=barrier_55.excluded_hit_86,
                )
            )
            continue
        win_no, win_tx, lose_no, lose_tx = ladder_cells_75(stop, lock.partition_id)
        out.append(
            path_payload_75(
                lock.n,
                lock.W,
                lock.L,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"75_{stop}:{lock.partition_id}",
            )
        )
    return out


def paths_from_pool_75() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in PATH_STOPS_75:
        if stop == 55:
            out.append(
                path_payload_75(
                    BARRIER_55_POOL_N_75,
                    BARRIER_55_POOL_W_75,
                    BARRIER_55_POOL_L_75,
                    *BARRIER_55_POOL_CELLS_75,
                    stop_cents=55,
                    label="75_55:derived_four",
                    excluded_hit_81=BARRIER_55_POOL_EXCL_75,
                )
            )
            continue
        win_no, win_tx, lose_no, lose_tx = ladder_cells_75(stop, "derived_four")
        out.append(
            path_payload_75(
                POOL_N_75,
                POOL_W_75,
                POOL_L_75,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"75_{stop}:derived_four",
            )
        )
    return out


def mid_paths_from_lock_75(lock: PartitionLock) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in MID_STOPS_75:
        win_no, win_tx, lose_no, lose_tx = ladder_cells_75(stop, lock.partition_id)
        out.append(
            path_payload_75(
                lock.n,
                lock.W,
                lock.L,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"75_{stop}:{lock.partition_id}",
            )
        )
    return out


def mid_paths_from_pool_75() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in MID_STOPS_75:
        win_no, win_tx, lose_no, lose_tx = ladder_cells_75(stop, "derived_four")
        out.append(
            path_payload_75(
                POOL_N_75,
                POOL_W_75,
                POOL_L_75,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"75_{stop}:derived_four",
            )
        )
    return out


def partition_payload_75(lock: PartitionLock) -> dict[str, Any]:
    body = _trade_75_40(
        lock.n,
        lock.W,
        lock.L,
        lock.win_no,
        lock.win_t40,
        lock.lose_no,
        lock.lose_t40,
        label=f"first75:{lock.partition_id}",
    )
    barrier = {row.partition_id: row for row in BARRIER_55_75}[lock.partition_id]
    paths = paths_from_lock_75(lock)
    mid_paths = mid_paths_from_lock_75(lock)
    body.update(
        {
            "partition_id": lock.partition_id,
            "sport": lock.sport,
            "sport_label": lock.sport_label,
            "slice": lock.slice,
            "slice_label": lock.slice_label,
            "role": "asked_six_slice",
            "rule": RULE_75,
            "trade_75_55": trade_75_55_payload(
                barrier.n,
                barrier.W,
                barrier.L,
                barrier.win_no,
                barrier.win_t55,
                barrier.lose_no,
                barrier.lose_t55,
                excluded_hit_81=barrier.excluded_hit_86,
                label=f"75_55:{lock.partition_id}",
            ),
            "paths": paths,
            "ledger_rank": ledger_rank(paths),
            "mid_paths": mid_paths,
            "mid_ledger_rank": ledger_rank(mid_paths),
        }
    )
    return body


def pool_payload_75() -> dict[str, Any]:
    body = _trade_75_40(
        POOL_N_75,
        POOL_W_75,
        POOL_L_75,
        *POOL_CELLS_75,
        label="first75:derived_four",
    )
    paths = paths_from_pool_75()
    mid_paths = mid_paths_from_pool_75()
    body.update(
        {
            "partition_id": "derived_four",
            "sport": "nba_ncaab_p5",
            "sport_label": "NBA + NCAAB P5",
            "slice": "asked_four",
            "slice_label": "NBA 2Q+3Q ∪ NCAAB 1H2+2H1",
            "role": "derived_four",
            "rule": RULE_75,
            "note": "Derived union of the four FIRST75 slices. Not asked-six (1126).",
            "trade_75_55": trade_75_55_payload(
                BARRIER_55_POOL_N_75,
                BARRIER_55_POOL_W_75,
                BARRIER_55_POOL_L_75,
                *BARRIER_55_POOL_CELLS_75,
                excluded_hit_81=BARRIER_55_POOL_EXCL_75,
                label="75_55:derived_four",
            ),
            "paths": paths,
            "ledger_rank": ledger_rank(paths),
            "mid_paths": mid_paths,
            "mid_ledger_rank": ledger_rank(mid_paths),
        }
    )
    return body


def verify_locks_75(
    *,
    partitions: tuple[PartitionLock, ...] = PARTITIONS_75,
    tables_path: Path | None = None,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    csv_file = csv_path or default_asked_six_75_csv()
    for lock in partitions:
        assert_identities(
            lock.n,
            lock.W,
            lock.L,
            lock.win_no,
            lock.win_t40,
            lock.lose_no,
            lock.lose_t40,
            label=f"lock75:{lock.partition_id}",
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
    if partitions is PARTITIONS_75:
        if (pool_n, pool_w, pool_l, pool_cells) != (
            POOL_N_75,
            POOL_W_75,
            POOL_L_75,
            POOL_CELLS_75,
        ):
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                (
                    f"FIRST75 derived four {pool_n}/{pool_w}/{pool_l}/{pool_cells} "
                    f"!= {POOL_N_75}/{POOL_W_75}/{POOL_L_75}/{POOL_CELLS_75}"
                ),
            )
    assert_identities(pool_n, pool_w, pool_l, *pool_cells, label="first75:derived_four")

    tables = load_tables_asked_six(tables_path, rule=RULE_75)
    for lock in partitions:
        row = tables.get((lock.sport, lock.slice))
        if row is None:
            raise ChoosinTexasError(
                "DATA_REQUIRED",
                f"tables.json missing FIRST75 asked_six {lock.sport}/{lock.slice}",
            )
        _same_row(lock, row, source="tables.json")

    wnba_n = 0
    wnba_cells = [0, 0, 0, 0]
    for lock in WNBA_PARTITIONS_75:
        row = tables.get((lock.sport, lock.slice))
        if row is None:
            raise ChoosinTexasError(
                "DATA_REQUIRED",
                f"tables.json missing FIRST75 asked_six {lock.sport}/{lock.slice}",
            )
        _same_row(lock, row, source="tables.json")
        wnba_n += lock.n
        for i, value in enumerate(lock.cells):
            wnba_cells[i] += value
    if partitions is PARTITIONS_75:
        if wnba_n != WNBA_UNION_N_75 or tuple(wnba_cells) != WNBA_UNION_CELLS_75:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST75 WNBA complement {wnba_n}/{tuple(wnba_cells)} "
                f"!= {WNBA_UNION_N_75}/{WNBA_UNION_CELLS_75}",
            )
        asked_n = pool_n + wnba_n
        asked_cells = tuple(pool_cells[i] + wnba_cells[i] for i in range(4))
        if asked_n != ASKED_SIX_N_75 or asked_cells != ASKED_SIX_CELLS_75:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST75 asked-six {asked_n}/{asked_cells} "
                f"!= {ASKED_SIX_N_75}/{ASKED_SIX_CELLS_75}",
            )

    csv_body = load_csv_cells(csv_file, partitions=partitions)
    for lock in partitions:
        _same_row(lock, csv_body["partitions"][lock.partition_id], source="asked_six_75_csv")
    if partitions is PARTITIONS_75:
        if csv_body["asked_six_n"] != ASKED_SIX_N_75:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST75 CSV N {csv_body['asked_six_n']} != {ASKED_SIX_N_75}",
            )
        if csv_body["wnba_n"] != WNBA_UNION_N_75:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST75 WNBA CSV N {csv_body['wnba_n']} != {WNBA_UNION_N_75}",
            )
        if pool_n + csv_body["wnba_n"] != ASKED_SIX_N_75:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"FIRST75 complement {pool_n}+{csv_body['wnba_n']} != {ASKED_SIX_N_75}",
            )

        barrier_locks = {row.partition_id: row for row in BARRIER_55_75}
        barrier_csv = load_csv_barrier_55(
            csv_file,
            partitions=partitions,
            entry_cents=ENTRY_CENTS_75,
            cap_cents=ENTRY_CAP_CENTS_75,
        )["partitions"]
        pool_55_n = pool_55_excl = pool_55_w = pool_55_l = 0
        pool_55_cells = [0, 0, 0, 0]
        for lock in partitions:
            expected = barrier_locks[lock.partition_id]
            observed = barrier_csv[lock.partition_id]
            _same_barrier_55(expected, observed, source="asked_six_75_csv")
            pool_55_n += expected.n
            pool_55_excl += expected.excluded_hit_86
            pool_55_w += expected.W
            pool_55_l += expected.L
            for i, value in enumerate(expected.cells):
                pool_55_cells[i] += value
        if (
            pool_55_n != BARRIER_55_POOL_N_75
            or pool_55_excl != BARRIER_55_POOL_EXCL_75
            or pool_55_w != BARRIER_55_POOL_W_75
            or pool_55_l != BARRIER_55_POOL_L_75
            or tuple(pool_55_cells) != BARRIER_55_POOL_CELLS_75
        ):
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                "75/55 derived four does not match locked 868 / 449/214/1/204",
            )
        if pool_55_n + pool_55_excl != pool_n:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"75/55 {pool_55_n}+{pool_55_excl} != derived four {pool_n}",
            )

        ladder = load_csv_barriers(csv_file, partitions=partitions)["partitions"]
        for stop in BARRIER_STOPS_75 + MID_STOPS_75 + (40,):
            pool_obs = [0, 0, 0, 0]
            for lock in partitions:
                observed = ladder[int(stop)][lock.partition_id]
                cells = (
                    int(observed["win_no"]),
                    int(observed["win_tx"]),
                    int(observed["lose_no"]),
                    int(observed["lose_tx"]),
                )
                expected = ladder_cells_75(int(stop), lock.partition_id)
                if (
                    int(observed["n"]) != lock.n
                    or int(observed["W"]) != lock.W
                    or int(observed["L"]) != lock.L
                    or cells != expected
                ):
                    raise ChoosinTexasError(
                        "LOCK_MISMATCH",
                        (
                            f"asked_six_75_csv 75/{stop} {lock.partition_id} "
                            f"{observed['n']}/{observed['W']}/{observed['L']}/{cells} "
                            f"!= lock {lock.n}/{lock.W}/{lock.L}/{expected}"
                        ),
                    )
                for i, value in enumerate(cells):
                    pool_obs[i] += value
            if tuple(pool_obs) != ladder_cells_75(int(stop), "derived_four"):
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"75/{stop} derived four {tuple(pool_obs)} != lock",
                )

    partitions_out = [partition_payload_75(lock) for lock in partitions]
    for row in partitions_out:
        share = Fraction(int(row["n"]), pool_n)
        row["n_share_display"] = ratio_display(int(row["n"]), pool_n)
        row["n_share_pct_display"] = pct_display(int(row["n"]), pool_n)
        row["n_bar_pct"] = float(share * 100)

    return {
        "status": "OBSERVED",
        "partitions": partitions_out,
        "pool": pool_payload_75(),
        "complement": {
            "asked_six_n": ASKED_SIX_N_75,
            "asked_six_cells": list(ASKED_SIX_CELLS_75),
            "wnba_2q_3q_n": WNBA_UNION_N_75,
            "wnba_2q_3q_cells": list(WNBA_UNION_CELLS_75),
            "derived_four_n": pool_n,
            "identity": f"{ASKED_SIX_N_75} = {pool_n} + {WNBA_UNION_N_75}",
            "note": (
                "Complement only. Texas (75) universe is FIRST75 derived_four, "
                "not asked-six and not FIRST80 936."
            ),
        },
        "sources": [
            "tables_md_locks_first75",
            "docs/research/lebronner/tables.json FIRST75 asked_six",
            "research/first75_asked_six_chatgpt_export/first75_asked_six.csv",
            "asked_six_75_csv 75/55 entry<81",
            "asked_six_75_csv barrier ladder 25/30/35/40/45/50",
            "asked_six_75_csv mid-stop tile 33/37/43/47",
        ],
    }
