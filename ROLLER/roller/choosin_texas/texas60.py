"""FIRST80 80/60 on the derived-four book. Same N as 80/40. Candle path ≠ fill."""

from __future__ import annotations

import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from roller.choosin_texas.locks import (
    BAND_STOPS_60,
    BARRIER_55_FULL,
    BARRIER_60,
    BARRIER_65,
    ENTRY_CENTS,
    GAIN_CENTS,
    GAP_60_POOL,
    GAP_60_SLICE,
    GAP_65_POOL,
    GAP_65_SLICE,
    NBA_T60_BINS,
    NBA_T60_N,
    NBA_T60_PERIOD,
    NBA_T60_REMAINING_SUM,
    PARTITIONS,
    POOL_CELLS,
    POOL_L,
    POOL_N,
    POOL_W,
    STOP_60_CENTS,
    PartitionLock,
    ladder_cells,
    loss_cents_for_stop,
)
from roller.choosin_texas.nba_path import CLOCK_BIN_ORDER, PERIOD_ORDER, _clock_display
from roller.choosin_texas.models import ChoosinTexasError, pct_display, ratio_display
from roller.choosin_texas.rates import ledger_rank, partition_payload, path_payload, pool_payload
from roller.choosin_texas.sources import load_csv_barriers, repo_root
from roller.choosin_texas.verify import verify_locks


def _cells(partition_id: str, book: dict[str, tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    try:
        return book[partition_id]
    except KeyError as exc:
        raise ChoosinTexasError("LOCK_MISMATCH", f"80/60 missing {partition_id}") from exc


def _assert_t60_nests(cells: tuple[int, int, int, int], partition_id: str) -> None:
    """T40 ⊂ T50 ⊂ T60 on this book. Survivors shrink as the stop rises."""
    for prior in (40, 50):
        win_no, win_tx, lose_no, lose_tx = ladder_cells(prior, partition_id)
        if cells[0] > win_no or cells[1] < win_tx or cells[2] != lose_no or cells[3] != lose_tx:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"80/60 {partition_id} {cells} is not nested over 80/{prior} "
                f"{(win_no, win_tx, lose_no, lose_tx)}",
            )


def verify_universe_60(
    *,
    csv_path: Path | None = None,
    cells: dict[str, tuple[int, int, int, int]] | None = None,
) -> dict[str, Any]:
    """Fail closed when the 936 book or the T60 min-close tally drifts."""
    book = cells if cells is not None else BARRIER_60
    verify_locks(csv_path=csv_path)
    observed = load_csv_barriers(csv_path, stops=(STOP_60_CENTS,))["partitions"]
    pool = [0, 0, 0, 0]
    for lock in PARTITIONS:
        row = observed[STOP_60_CENTS][lock.partition_id]
        got = (
            int(row["win_no"]),
            int(row["win_tx"]),
            int(row["lose_no"]),
            int(row["lose_tx"]),
        )
        expected = _cells(lock.partition_id, book)
        if (
            int(row["n"]) != lock.n
            or int(row["W"]) != lock.W
            or int(row["L"]) != lock.L
            or got != expected
        ):
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"asked_six_csv 80/60 {lock.partition_id} "
                f"{row['n']}/{row['W']}/{row['L']}/{got} != {lock.n}/{lock.W}/{lock.L}/{expected}",
            )
        if got[2] != 0:
            raise ChoosinTexasError("LOCK_MISMATCH", f"80/60 {lock.partition_id}: s_L must be 0")
        _assert_t60_nests(got, lock.partition_id)
        for index, value in enumerate(got):
            pool[index] += value
    pool_cells = _cells("derived_four", book)
    if tuple(pool) != pool_cells:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"80/60 derived four {tuple(pool)} != lock {pool_cells}",
        )
    if sum(pool_cells) != POOL_N:
        raise ChoosinTexasError("LOCK_MISMATCH", f"80/60 cell sum {sum(pool_cells)} != {POOL_N}")
    _assert_t60_nests(pool_cells, "derived_four")
    return {"cells": book, "pool_cells": pool_cells}


def _trade(lock: PartitionLock, book: dict[str, tuple[int, int, int, int]]) -> dict[str, Any]:
    win_no, win_tx, lose_no, lose_tx = _cells(lock.partition_id, book)
    return path_payload(
        lock.n,
        lock.W,
        lock.L,
        win_no,
        win_tx,
        lose_no,
        lose_tx,
        stop_cents=STOP_60_CENTS,
        label=f"80_60:{lock.partition_id}",
    )


_SLICE_PARTITION = {
    "Q2": "nba_2q",
    "Q3": "nba_3q",
    "H1_2": "ncaab_h1_2",
    "H2_1": "ncaab_h2_1",
}
_BAND_BOOKS = {55: BARRIER_55_FULL, 60: BARRIER_60, 65: BARRIER_65}


def touches_json_path() -> Path:
    return repo_root() / "research" / "choosin_texas" / "t60_band" / "touches.json"


def _band_note(stop: int) -> str:
    loss = loss_cents_for_stop(stop)
    if stop == 55:
        return (
            "S = P(¬T55) on the full N=936 book. "
            f"EV = 20S − {loss}(1−S). "
            "The Texas ladder 80/55 is the entry<86 book (905)."
        )
    return (
        f"S = P(¬T{stop}) on the full N=936 book. "
        f"EV = 20S − {loss}(1−S). Candle path ≠ fill."
    )


def _band_trade(lock: PartitionLock, stop: int) -> dict[str, Any]:
    win_no, win_tx, lose_no, lose_tx = _cells(lock.partition_id, _BAND_BOOKS[stop])
    body = path_payload(
        lock.n,
        lock.W,
        lock.L,
        win_no,
        win_tx,
        lose_no,
        lose_tx,
        stop_cents=stop,
        label=f"80_{stop}:{lock.partition_id}",
    )
    body["note"] = _band_note(stop)
    return body


def _count_block(k: int, n: int) -> dict[str, Any]:
    return {
        "k": int(k),
        "n": int(n),
        "display": ratio_display(k, n),
        "pct_display": pct_display(k, n),
    }


def _gap_slice(kind: str, raw: dict[str, int], *, partition_id: str) -> dict[str, Any]:
    n = int(raw["n"])
    if kind == "65":
        return {
            "partition_id": partition_id,
            "n": n,
            "separate_print": _count_block(raw["separate_61_65"], n),
            "same_bar_at_or_below_60": _count_block(raw["same_bar_le60"], n),
            "separate_then_60": _count_block(raw["separate_then_t60"], raw["separate_61_65"]),
            "separate_held_above_60": _count_block(raw["separate_survive_60"], raw["separate_61_65"]),
        }
    return {
        "partition_id": partition_id,
        "n": n,
        "separate_print": _count_block(raw["separate_56_60"], n),
        "same_bar_at_or_below_55": _count_block(raw["same_bar_le55"], n),
        "continued_to_55": _count_block(raw["continued_to_55"], n),
        "never_printed_55": _count_block(raw["never_55"], n),
    }


def verify_touch_artifact(path: Path | None = None) -> dict[str, Any]:
    """First-touch file must match the min-close locks and the clock locks."""
    json_path = path or touches_json_path()
    if not json_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {json_path}")
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    rows = doc.get("rows")
    if not isinstance(rows, list) or len(rows) != POOL_N:
        raise ChoosinTexasError("LOCK_MISMATCH", f"T60 touch rows {len(rows) if isinstance(rows, list) else None} != {POOL_N}")
    touch = {stop: defaultdict(int) for stop in BAND_STOPS_60}
    gap65 = {pid: defaultdict(int) for pid in GAP_65_SLICE}
    gap60 = {pid: defaultdict(int) for pid in GAP_60_SLICE}
    period_n = {slice_id: defaultdict(int) for slice_id in NBA_T60_N}
    bin_n = {slice_id: defaultdict(int) for slice_id in NBA_T60_N}
    remain_sum = {slice_id: defaultdict(int) for slice_id in NBA_T60_N}
    seen = set()
    for row in rows:
        ticker = str(row.get("ticker") or "")
        if ticker in seen or not ticker:
            raise ChoosinTexasError("LOCK_MISMATCH", f"duplicate or blank T60 touch ticker {ticker}")
        seen.add(ticker)
        partition_id = _SLICE_PARTITION.get(str(row.get("slice")))
        if partition_id is None:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker}: slice {row.get('slice')}")
        post_min = int(row["post_min"])
        for stop in BAND_STOPS_60:
            if post_min <= stop:
                touch[stop][partition_id] += 1
        t65 = row.get("t65_close") is not None
        t60 = row.get("t60_close") is not None
        t55 = row.get("t55_close") is not None
        if t65 != (post_min <= 65) or t60 != (post_min <= 60) or t55 != (post_min <= 55):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker}: touch flags disagree with post_min {post_min}")
        if t65:
            gap65[partition_id]["n"] += 1
            if bool(row["t65_separate"]):
                gap65[partition_id]["separate_61_65"] += 1
                if t60:
                    gap65[partition_id]["separate_then_t60"] += 1
                else:
                    gap65[partition_id]["separate_survive_60"] += 1
            else:
                gap65[partition_id]["same_bar_le60"] += 1
                if not t60:
                    raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker}: 65 gap-through without T60")
        if t60:
            gap60[partition_id]["n"] += 1
            if bool(row["t60_already_le55"]):
                gap60[partition_id]["same_bar_le55"] += 1
            elif bool(row["t60_separate"]):
                gap60[partition_id]["separate_56_60"] += 1
            else:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker}: T60 is neither separate nor gap")
            if t55:
                gap60[partition_id]["continued_to_55"] += 1
            else:
                gap60[partition_id]["never_55"] += 1
        if row.get("sport") == "NBA" and t60:
            period = str(row.get("exit_period") or "")
            bin_id = str(row.get("clock_bin") or "")
            if period not in PERIOD_ORDER or bin_id not in CLOCK_BIN_ORDER:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker}: T60 clock {period} {bin_id}")
            slice_id = str(row["slice"])
            period_n[slice_id][period] += 1
            bin_n[slice_id][(period, bin_id)] += 1
            remain_sum[slice_id][period] += int(row["exit_remaining_s"])
    for stop, book in _BAND_BOOKS.items():
        for lock in PARTITIONS:
            expected = book[lock.partition_id][1] + book[lock.partition_id][3]
            if touch[stop][lock.partition_id] != expected:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"T{stop} {lock.partition_id} touches {touch[stop][lock.partition_id]} != {expected}",
                )
    for pid, expected in GAP_65_SLICE.items():
        if dict(gap65[pid]) != expected:
            raise ChoosinTexasError("LOCK_MISMATCH", f"65 gap {pid} {dict(gap65[pid])} != {expected}")
    for pid, expected in GAP_60_SLICE.items():
        if dict(gap60[pid]) != expected:
            raise ChoosinTexasError("LOCK_MISMATCH", f"60 gap {pid} {dict(gap60[pid])} != {expected}")
    for slice_id, expected_n in NBA_T60_N.items():
        expected_period = {k: v for k, v in NBA_T60_PERIOD[slice_id].items() if v}
        if dict(period_n[slice_id]) != expected_period:
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"NBA {slice_id} T60 period {dict(period_n[slice_id])} != {expected_period}",
            )
        if sum(period_n[slice_id].values()) != expected_n:
            raise ChoosinTexasError("LOCK_MISMATCH", f"NBA {slice_id} T60 n {sum(period_n[slice_id].values())} != {expected_n}")
        for key, expected in NBA_T60_BINS[slice_id].items():
            if bin_n[slice_id][key] != expected:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"NBA {slice_id} T60 bin {key} {bin_n[slice_id][key]} != {expected}",
                )
        for period, expected_sum in NBA_T60_REMAINING_SUM[slice_id].items():
            if remain_sum[slice_id][period] != expected_sum:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"NBA {slice_id} {period} remaining sum {remain_sum[slice_id][period]} != {expected_sum}",
                )
    return {"rows": len(rows)}


def _clock_payload(slice_id: str) -> dict[str, Any]:
    n_t60 = NBA_T60_N[slice_id]
    bins = []
    for period in PERIOD_ORDER:
        for bin_id in CLOCK_BIN_ORDER:
            count = NBA_T60_BINS[slice_id][(period, bin_id)]
            bins.append(
                {
                    "period": period,
                    "clock_bin": bin_id,
                    "label": f"{period} {bin_id}",
                    "n": count,
                    "n_display": ratio_display(count, n_t60),
                    "pct_display": pct_display(count, n_t60) if count else "0.0000%",
                    "bar_pct": float(Fraction(count, n_t60) * 100),
                }
            )
    means = []
    for period, total in NBA_T60_REMAINING_SUM[slice_id].items():
        n = NBA_T60_PERIOD[slice_id][period]
        remaining = Fraction(int(total), int(n))
        means.append(
            {
                "period": period,
                "n": n,
                "clock_display": _clock_display(remaining),
            }
        )
    lock = next(row for row in PARTITIONS if row.csv_slice == slice_id)
    return {
        "slice": slice_id,
        "slice_label": lock.slice_label,
        "n": lock.n,
        "n_t60": n_t60,
        "bins": bins,
        "mean_remaining": means,
    }


def build_universe_60(
    *,
    csv_path: Path | None = None,
    cells: dict[str, tuple[int, int, int, int]] | None = None,
) -> dict[str, Any]:
    verified = verify_universe_60(csv_path=csv_path, cells=cells)
    verify_touch_artifact()
    book = verified["cells"]
    loss = loss_cents_for_stop(STOP_60_CENTS)
    partitions_out: list[dict[str, Any]] = []
    for lock in PARTITIONS:
        row = partition_payload(lock)
        share = Fraction(lock.n, POOL_N)
        row["n_share_display"] = ratio_display(lock.n, POOL_N)
        row["n_share_pct_display"] = pct_display(lock.n, POOL_N)
        row["n_bar_pct"] = float(share * 100)
        row["trade_80_60"] = _trade(lock, book)
        row["band"] = [_band_trade(lock, stop) for stop in BAND_STOPS_60]
        row["band_rank"] = ledger_rank(row["band"])
        partitions_out.append(row)
    pool = pool_payload(POOL_N, POOL_W, POOL_L, *POOL_CELLS)
    win_no, win_tx, lose_no, lose_tx = verified["pool_cells"]
    pool["trade_80_60"] = path_payload(
        POOL_N,
        POOL_W,
        POOL_L,
        win_no,
        win_tx,
        lose_no,
        lose_tx,
        stop_cents=STOP_60_CENTS,
        label="80_60:derived_four",
    )
    pool["trade_80_60"]["note"] = _band_note(60)
    pool["band"] = []
    for stop in BAND_STOPS_60:
        cells = _BAND_BOOKS[stop]["derived_four"]
        trade = path_payload(
            POOL_N,
            POOL_W,
            POOL_L,
            *cells,
            stop_cents=stop,
            label=f"80_{stop}:derived_four",
        )
        trade["note"] = _band_note(stop)
        pool["band"].append(trade)
    pool["band_rank"] = ledger_rank(pool["band"])
    gap = {
        "t65": {
            "pool": _gap_slice("65", GAP_65_POOL, partition_id="derived_four"),
            "slices": [_gap_slice("65", GAP_65_SLICE[lock.partition_id], partition_id=lock.partition_id) for lock in PARTITIONS],
            "note": "T65 = first later tradable close ≤ 65. A separate print is still 61–65. Same-bar means that close was already ≤ 60.",
        },
        "t60": {
            "pool": _gap_slice("60", GAP_60_POOL, partition_id="derived_four"),
            "slices": [_gap_slice("60", GAP_60_SLICE[lock.partition_id], partition_id=lock.partition_id) for lock in PARTITIONS],
            "note": "T60 = first later tradable close ≤ 60. Continued to 55 means the path later printed ≤ 55. Same-bar means the first ≤60 close was already ≤ 55.",
        },
    }
    clocks = [_clock_payload(slice_id) for slice_id in ("Q2", "Q3")]
    anchor_s = POOL_CELLS[0] + POOL_CELLS[2]
    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "page": "80/60",
        "live_execution": False,
        "submits": False,
        "rule": "FIRST80",
        "entry_cents": ENTRY_CENTS,
        "stop_cents": STOP_60_CENTS,
        "gain_cents": GAIN_CENTS,
        "loss_cents": loss,
        "universe": "derived_four",
        "unit": "FIRST80 trigger events (one per settled event). Not Kalshi trade prints.",
        "partitions": partitions_out,
        "pool": pool,
        "band_stops": list(BAND_STOPS_60),
        "gap": gap,
        "clocks": clocks,
        "alignment": {
            "model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
            "note": (
                "Clock is a modeled PBP snap at the first ≤60 close. "
                "NBA 2Q and 3Q entries only. Not warehouse PBP↔candle PIT. "
                "PIT stays OPERATION_REQUIRED. Candle path ≠ fill."
            ),
        },
        "anchor_80_40": {
            "n": POOL_N,
            "S_display": ratio_display(anchor_s, POOL_N),
            "note": "80/40 on this same derived four. This page models stop 60.",
        },
        "verification": {"status": "OBSERVED"},
        "variables": {
            "rule": "FIRST80",
            "entry_cents": ENTRY_CENTS,
            "stop_cents": STOP_60_CENTS,
            "gain_cents": GAIN_CENTS,
            "loss_cents": loss,
            "n": POOL_N,
            "locked": True,
            "recompute": "FAIL_CLOSED",
            "note": (
                "T60 = post-entry min yes bid ≤ 60 on the full 936 book. "
                "s_L = 0, so S = (W ∩ ¬T60) / N. EV = 20S − 20(1−S). "
                "65 and 55 are the same book. The Texas-page 80/55 cap book stays 905."
            ),
        },
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ ACTUAL FILL",
            "Same derived four as 80/40. N=936.",
            "T60 = post-entry min yes bid ≤ 60",
            "80/65 and 80/55 on this page use the full N=936 book",
            "The Texas ladder 80/55 remains the entry<86 book (905)",
            "ledger EV is candle-path theoretical, not a fill or live EV",
        ],
    }
