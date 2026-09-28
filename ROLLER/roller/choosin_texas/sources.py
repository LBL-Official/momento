"""Reconstruct four-cells from locked tables.json and asked-six CSV. No rescan."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from roller.choosin_texas.locks import MID_STOPS, PARTITIONS, PATH_STOPS, PartitionLock
from roller.choosin_texas.models import ChoosinTexasError

FULL_BOOK_STOPS: tuple[int, ...] = tuple(
    sorted(set(stop for stop in PATH_STOPS if stop != 55) | set(MID_STOPS))
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_tables_json() -> Path:
    return repo_root() / "docs" / "research" / "lebronner" / "tables.json"


def default_asked_six_csv() -> Path:
    return (
        repo_root()
        / "research"
        / "first80_asked_six_chatgpt_export"
        / "first80_asked_six.csv"
    )


def default_asked_six_75_csv() -> Path:
    return (
        repo_root()
        / "research"
        / "first75_asked_six_chatgpt_export"
        / "first75_asked_six.csv"
    )


def default_asked_six_77_csv() -> Path:
    return (
        repo_root()
        / "research"
        / "first77_asked_six_chatgpt_export"
        / "first77_asked_six.csv"
    )


def default_asked_six_81_csv() -> Path:
    return (
        repo_root()
        / "research"
        / "first81_asked_six_chatgpt_export"
        / "first81_asked_six.csv"
    )


def default_asked_six_83_csv() -> Path:
    return (
        repo_root()
        / "research"
        / "first83_asked_six_chatgpt_export"
        / "first83_asked_six.csv"
    )


def default_asked_six_csv_for_tau(tau: int) -> Path:
    loaders = {
        80: default_asked_six_csv,
        75: default_asked_six_75_csv,
        77: default_asked_six_77_csv,
        81: default_asked_six_81_csv,
        83: default_asked_six_83_csv,
    }
    try:
        return loaders[int(tau)]()
    except KeyError as exc:
        raise ChoosinTexasError("DATA_REQUIRED", f"no asked-six CSV loader for τ={tau}") from exc


def _as_bool(value: Any, *, field: str, ticker: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ChoosinTexasError(
        "DATA_REQUIRED", f"cannot parse {field}={value!r} for {ticker}"
    )


def _cents_field(value: Any, *, field: str, ticker: str) -> int:
    if value is None or str(value).strip() == "":
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {field} for {ticker}")
    try:
        return int(round(float(value)))
    except (TypeError, ValueError) as exc:
        raise ChoosinTexasError(
            "DATA_REQUIRED", f"cannot parse {field}={value!r} for {ticker}"
        ) from exc


def _int_field(row: dict[str, Any], key: str, *, label: str) -> int:
    raw = row.get(key)
    if raw is None:
        raise ChoosinTexasError("DATA_REQUIRED", f"{label} missing {key}")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ChoosinTexasError("DATA_REQUIRED", f"{label} bad {key}={raw!r}") from exc


def load_tables_asked_six(
    path: Path | None = None,
    *,
    rule: str = "FIRST80",
) -> dict[tuple[str, str], dict[str, int]]:
    tables_path = path or default_tables_json()
    if not tables_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {tables_path}")
    payload = json.loads(tables_path.read_text(encoding="utf-8"))
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ChoosinTexasError("DATA_REQUIRED", "tables.json rows missing")
    out: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        if row.get("rule") != rule or row.get("role") != "asked_six":
            continue
        sport = str(row.get("sport") or "")
        slice_id = str(row.get("slice") or "")
        out[(sport, slice_id)] = {
            "n": _int_field(row, "n", label=f"{sport}/{slice_id}"),
            "W": _int_field(row, "W", label=f"{sport}/{slice_id}"),
            "L": _int_field(row, "L", label=f"{sport}/{slice_id}"),
            "win_no": _int_field(row, "W_and_not_T40", label=f"{sport}/{slice_id}"),
            "win_t40": _int_field(row, "W_and_T40", label=f"{sport}/{slice_id}"),
            "lose_no": _int_field(row, "L_and_not_T40", label=f"{sport}/{slice_id}"),
            "lose_t40": _int_field(row, "L_and_T40", label=f"{sport}/{slice_id}"),
        }
    return out


def load_tables_rows(
    path: Path | None = None,
    *,
    rule: str = "FIRST80",
    partitions: tuple[PartitionLock, ...] | None = None,
) -> dict[tuple[str, str], dict[str, int]]:
    wanted = {(p.sport, p.slice) for p in (partitions or PARTITIONS)}
    return {
        key: value
        for key, value in load_tables_asked_six(path, rule=rule).items()
        if key in wanted
    }


def _classify_csv_row(row: dict[str, Any]) -> tuple[bool, bool]:
    ticker = str(row.get("ticker") or row.get("event_id") or "?")
    win = _as_bool(row.get("W"), field="W", ticker=ticker)
    t40 = _as_bool(row.get("T40"), field="T40", ticker=ticker)
    terminal = row.get("terminal_yes")
    if terminal not in (None, ""):
        if _as_bool(terminal, field="terminal_yes", ticker=ticker) != win:
            raise ChoosinTexasError(
                "LOCK_MISMATCH", f"W != terminal_yes for {ticker}"
            )
    return win, t40


def load_csv_cells(
    path: Path | None = None,
    *,
    partitions: tuple[PartitionLock, ...] = PARTITIONS,
) -> dict[str, dict[str, int]]:
    csv_path = path or default_asked_six_csv()
    if not csv_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {csv_path}")
    wanted = {(p.csv_sport, p.csv_slice): p.partition_id for p in partitions}
    tallies = {
        p.partition_id: {
            "n": 0,
            "W": 0,
            "L": 0,
            "win_no": 0,
            "win_t40": 0,
            "lose_no": 0,
            "lose_t40": 0,
        }
        for p in partitions
    }
    asked_six_n = 0
    wnba_n = 0
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            asked_six_n += 1
            sport = str(row.get("sport") or "").strip()
            slice_id = str(row.get("slice") or "").strip()
            if sport == "WNBA":
                wnba_n += 1
            key = (sport, slice_id)
            partition_id = wanted.get(key)
            if partition_id is None:
                continue
            win, t40 = _classify_csv_row(row)
            cell = tallies[partition_id]
            cell["n"] += 1
            if win:
                cell["W"] += 1
                if t40:
                    cell["win_t40"] += 1
                else:
                    cell["win_no"] += 1
            else:
                cell["L"] += 1
                if t40:
                    cell["lose_t40"] += 1
                else:
                    cell["lose_no"] += 1
    return {
        "partitions": tallies,
        "asked_six_n": asked_six_n,
        "wnba_n": wnba_n,
    }


def load_csv_barrier_55(
    path: Path | None = None,
    *,
    partitions: tuple[PartitionLock, ...] = PARTITIONS,
    entry_cents: int = 80,
    cap_cents: int = 86,
) -> dict[str, Any]:
    """Tx=55 on rows whose entry yes_bid_close is still below the cap.

    FIRST80 default: entry 80, cap 86. FIRST75 uses entry 75, cap 81.
    Hit cap at the first print = gapped through entry before fill. Do not count.
    T55 = post_entry_min_yes_bid_cents ≤ 55. T40 ⇒ T55. No warehouse rescan.
    """
    csv_path = path or default_asked_six_csv()
    if not csv_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {csv_path}")
    wanted = {(p.csv_sport, p.csv_slice): p.partition_id for p in partitions}
    excl_key = f"excluded_hit_{int(cap_cents)}"
    tallies = {
        p.partition_id: {
            "n": 0,
            "excluded_hit_86": 0,
            excl_key: 0,
            "W": 0,
            "L": 0,
            "win_no": 0,
            "win_t55": 0,
            "lose_no": 0,
            "lose_t55": 0,
        }
        for p in partitions
    }
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            partition_id = wanted.get((str(row.get("sport") or "").strip(), str(row.get("slice") or "").strip()))
            if partition_id is None:
                continue
            ticker = str(row.get("ticker") or row.get("event_id") or "?")
            bid = _cents_field(row.get("market_yes_bid"), field="market_yes_bid", ticker=ticker)
            post_min = _cents_field(
                row.get("post_entry_min_yes_bid_cents"),
                field="post_entry_min_yes_bid_cents",
                ticker=ticker,
            )
            win, t40 = _classify_csv_row(row)
            if bid < int(entry_cents):
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"{ticker}: FIRST{entry_cents} entry bid {bid} < {entry_cents}",
                )
            if bid >= int(cap_cents):
                tallies[partition_id]["excluded_hit_86"] += 1
                if excl_key != "excluded_hit_86":
                    tallies[partition_id][excl_key] += 1
                continue
            t55 = post_min <= 55
            if t40 and not t55:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH", f"{ticker}: T40 is not a subset of T55 (min={post_min})"
                )
            cell = tallies[partition_id]
            cell["n"] += 1
            if win:
                cell["W"] += 1
                if t55:
                    cell["win_t55"] += 1
                else:
                    cell["win_no"] += 1
            else:
                cell["L"] += 1
                if t55:
                    cell["lose_t55"] += 1
                else:
                    cell["lose_no"] += 1
    return {"partitions": tallies}


def _empty_barrier_cell() -> dict[str, int]:
    return {
        "n": 0,
        "W": 0,
        "L": 0,
        "win_no": 0,
        "win_tx": 0,
        "lose_no": 0,
        "lose_tx": 0,
    }


def load_csv_barriers(
    path: Path | None = None,
    *,
    partitions: tuple[PartitionLock, ...] = PARTITIONS,
    stops: tuple[int, ...] = FULL_BOOK_STOPS,
) -> dict[str, Any]:
    """Min-close Tx on the full four-pool. No 86 filter. No warehouse rescan.

    Tx = post_entry_min_yes_bid_cents ≤ x.
    Nested: T25 ⊂ T30 ⊂ T33 ⊂ T35 ⊂ T37 ⊂ T40 ⊂ T43 ⊂ T45 ⊂ T47 ⊂ T50.
    CSV T40 must equal min ≤ 40.
    """
    csv_path = path or default_asked_six_csv()
    if not csv_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {csv_path}")
    wanted = {(p.csv_sport, p.csv_slice): p.partition_id for p in partitions}
    tallies = {
        int(stop): {p.partition_id: _empty_barrier_cell() for p in partitions}
        for stop in stops
    }
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            partition_id = wanted.get(
                (str(row.get("sport") or "").strip(), str(row.get("slice") or "").strip())
            )
            if partition_id is None:
                continue
            ticker = str(row.get("ticker") or row.get("event_id") or "?")
            post_min = _cents_field(
                row.get("post_entry_min_yes_bid_cents"),
                field="post_entry_min_yes_bid_cents",
                ticker=ticker,
            )
            win, t40 = _classify_csv_row(row)
            if (post_min <= 40) != t40:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"{ticker}: T40={t40} but post_entry_min={post_min}",
                )
            seen_hit = False
            for nest_stop in FULL_BOOK_STOPS:
                hit = post_min <= int(nest_stop)
                if seen_hit and not hit:
                    raise ChoosinTexasError(
                        "LOCK_MISMATCH",
                        f"{ticker}: nest failed min={post_min} at T{nest_stop}",
                    )
                if hit:
                    seen_hit = True
            for stop in stops:
                hit = post_min <= int(stop)
                cell = tallies[int(stop)][partition_id]
                cell["n"] += 1
                if win:
                    cell["W"] += 1
                    if hit:
                        cell["win_tx"] += 1
                    else:
                        cell["win_no"] += 1
                else:
                    cell["L"] += 1
                    if hit:
                        cell["lose_tx"] += 1
                    else:
                        cell["lose_no"] += 1
    return {"partitions": tallies, "stops": list(stops)}


_SPLIT_KEYS = ("IN_SAMPLE", "VALIDATION", "OOS")


def _empty_split_cell() -> dict[str, int]:
    return {
        "n": 0,
        "W": 0,
        "L": 0,
        "win_no": 0,
        "win_tx": 0,
        "lose_no": 0,
        "lose_tx": 0,
        "excluded": 0,
    }


def load_csv_asked_six_splits(
    path: Path | None,
    *,
    partitions: tuple[PartitionLock, ...],
    stops: tuple[int, ...] = FULL_BOOK_STOPS,
    entry_cents: int,
    cap_cents: int,
) -> dict[str, Any]:
    """Tally IN_SAMPLE / VALIDATION / OOS from dataset_split. No warehouse rescan.

    Train/test windows are the min/max game_date on each split. Missing
    game_date or an unknown split is DATA_REQUIRED. 55 uses the cap book.
    """
    csv_path = path or default_asked_six_csv()
    if not csv_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {csv_path}")
    wanted = {(p.csv_sport, p.csv_slice): p.partition_id for p in partitions}
    pool_id = "asked_six"
    pids = [p.partition_id for p in partitions] + [pool_id]
    folds: dict[str, dict[str, Any]] = {}
    for split in _SPLIT_KEYS:
        folds[split] = {
            "n": 0,
            "dates": [],
            "partitions": {
                pid: {
                    "n": 0,
                    "W": 0,
                    "L": 0,
                    "stops": {int(stop): _empty_split_cell() for stop in stops},
                    "t55": _empty_split_cell(),
                }
                for pid in pids
            },
        }

    def _bump(cell: dict[str, int], *, win: bool, hit: bool) -> None:
        cell["n"] += 1
        if win:
            cell["W"] += 1
            if hit:
                cell["win_tx"] += 1
            else:
                cell["win_no"] += 1
        else:
            cell["L"] += 1
            if hit:
                cell["lose_tx"] += 1
            else:
                cell["lose_no"] += 1

    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            split = str(row.get("dataset_split") or "").strip()
            if split not in _SPLIT_KEYS:
                ticker = str(row.get("ticker") or row.get("event_id") or "?")
                raise ChoosinTexasError(
                    "DATA_REQUIRED",
                    f"{ticker}: dataset_split={split!r} not IN_SAMPLE/VALIDATION/OOS",
                )
            gd = str(row.get("game_date") or "").strip()
            if not gd:
                ticker = str(row.get("ticker") or row.get("event_id") or "?")
                raise ChoosinTexasError("DATA_REQUIRED", f"{ticker}: missing game_date")
            partition_id = wanted.get(
                (str(row.get("sport") or "").strip(), str(row.get("slice") or "").strip())
            )
            if partition_id is None:
                continue
            ticker = str(row.get("ticker") or row.get("event_id") or "?")
            post_min = _cents_field(
                row.get("post_entry_min_yes_bid_cents"),
                field="post_entry_min_yes_bid_cents",
                ticker=ticker,
            )
            bid = _cents_field(row.get("market_yes_bid"), field="market_yes_bid", ticker=ticker)
            win, t40 = _classify_csv_row(row)
            if (post_min <= 40) != t40:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH",
                    f"{ticker}: T40={t40} but post_entry_min={post_min}",
                )
            fold = folds[split]
            fold["n"] += 1
            fold["dates"].append(gd)
            for pid in (partition_id, pool_id):
                part = fold["partitions"][pid]
                part["n"] += 1
                if win:
                    part["W"] += 1
                else:
                    part["L"] += 1
                for stop in stops:
                    _bump(part["stops"][int(stop)], win=win, hit=post_min <= int(stop))
                if bid >= int(cap_cents):
                    part["t55"]["excluded"] += 1
                else:
                    _bump(part["t55"], win=win, hit=post_min <= 55)

    out_folds: dict[str, Any] = {}
    for split, fold in folds.items():
        dates = fold["dates"]
        out_folds[split] = {
            "n": int(fold["n"]),
            "window": (min(dates), max(dates)) if dates else None,
            "partitions": fold["partitions"],
        }
    return {
        "folds": out_folds,
        "column": "dataset_split",
        "entry_cents": int(entry_cents),
        "cap_cents": int(cap_cents),
    }
