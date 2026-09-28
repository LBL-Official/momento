"""Locked 80/40 research book for 2026-27. Not live. Does not submit."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from roller.choosin_texas.dallas import (
    LEAD_BINS,
    PREGAME_BINS,
    PREGAME_SOURCE,
    _lead_bin,
    _pregame_bin,
    _pregame_cents,
)
from roller.choosin_texas.ev import ev_payload
from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.nba_path import _int_value
from roller.choosin_texas.sources import _as_bool, _cents_field, default_asked_six_csv, repo_root

BOOK_ID = "nba_2q_regular_8040_1lot_2026_27"
BOOK_SCHEMA = "choosin_texas_book_v1"
LIBRARY_RELATIVE = Path("research/choosin_texas/library") / BOOK_ID / "book.json"
WRITEUP_RELATIVE = Path("research/choosin_texas/NBA_8040_2026_27_BET.md")
NOTE_RELATIVE = Path("research/choosin_texas/NBA_8040_2026_27_NOTE.md")

TAPE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "tape_id": "nba_2q3q",
        "sport": "NBA",
        "slices": ("Q2", "Q3"),
        "phase": None,
        "role": "dallas_universe",
    },
    {
        "tape_id": "ncaab_h12_h21",
        "sport": "NCAAB",
        "slices": ("H1_2", "H2_1"),
        "phase": None,
        "role": "validation_analog",
    },
    {
        "tape_id": "nba_2q_regular",
        "sport": "NBA",
        "slices": ("Q2",),
        "phase": "REGULAR_SEASON",
        "role": "registered_baseline",
    },
)


def default_book_json() -> Path:
    return repo_root() / LIBRARY_RELATIVE


def _load_rows(sport: str, slices: tuple[str, ...], phase: str | None) -> list[dict[str, Any]]:
    wanted = set(slices)
    rows: list[dict[str, Any]] = []
    with default_asked_six_csv().open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            if str(rec.get("sport") or "").strip() != sport:
                continue
            slice_id = str(rec.get("slice") or "").strip()
            if slice_id not in wanted:
                continue
            if phase is not None and str(rec.get("season_phase") or "").strip() != phase:
                continue
            ticker = str(rec.get("ticker") or rec.get("event_id") or "?")
            side = str(rec.get("side") or "").strip()
            if side not in {"home", "away"}:
                raise ChoosinTexasError("LOCK_MISMATCH", f"bad side {side!r} for {ticker}")
            source = str(rec.get("pregame_source") or "").strip()
            if source != PREGAME_SOURCE:
                raise ChoosinTexasError(
                    "LOCK_MISMATCH", f"{ticker}: pregame_source {source!r}"
                )
            t40 = _as_bool(rec.get("T40"), field="T40", ticker=ticker)
            win = _as_bool(rec.get("W"), field="W", ticker=ticker)
            lead = _int_value(
                rec.get("bought_team_margin"), field="bought_team_margin", ticker=ticker
            )
            pregame = _pregame_cents(rec, side, ticker=ticker)
            post = _cents_field(
                rec.get("post_entry_min_yes_bid_cents"),
                field="post_entry_min_yes_bid_cents",
                ticker=ticker,
            )
            if t40 != (post <= 40):
                raise ChoosinTexasError(
                    "LOCK_MISMATCH", f"{ticker}: T40 {t40} != post_min {post} ≤ 40"
                )
            rows.append(
                {
                    "ticker": ticker,
                    "slice": slice_id,
                    "t40": t40,
                    "w": win,
                    "lead": lead,
                    "pregame": pregame,
                    "post": post,
                    "date": str(rec.get("game_date") or ""),
                    "phase": str(rec.get("season_phase") or ""),
                    "split": str(rec.get("dataset_split") or ""),
                    "event": str(rec.get("event_id") or rec.get("game_id") or ticker),
                }
            )
    if not rows:
        raise ChoosinTexasError("DATA_REQUIRED", f"no FIRST80 rows for {sport} {slices}")
    return rows


def _cohorts(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    survive = sum(1 for row in rows if not row["t40"])
    t40_win = sum(1 for row in rows if row["t40"] and row["w"])
    t40_lose = sum(1 for row in rows if row["t40"] and not row["w"])
    if survive + t40_win + t40_lose != len(rows):
        raise ChoosinTexasError("LOCK_MISMATCH", "book cohort identity failed")
    return survive, t40_win, t40_lose


def _s_for_stop(rows: list[dict[str, Any]], stop: int) -> int:
    return sum(1 for row in rows if int(row["post"]) > int(stop))


def _ev_block(rows: list[dict[str, Any]], *, stop: int = 40) -> dict[str, Any]:
    n = len(rows)
    s_n = _s_for_stop(rows, stop) if stop != 40 else _cohorts(rows)[0]
    if stop == 40 and s_n != _s_for_stop(rows, 40):
        raise ChoosinTexasError("LOCK_MISMATCH", "T40 survive != post_min > 40")
    payload = ev_payload(n=n, s_n=s_n, stop_cents=stop)
    survive, t40_win, t40_lose = _cohorts(rows) if stop == 40 else (s_n, None, None)
    return {
        "n": n,
        "s_n": s_n,
        "s_display": f"{s_n}/{n}",
        "w_t40": t40_win,
        "l_t40": t40_lose,
        "t40": None if t40_win is None else t40_win + t40_lose,
        "stop_cents": stop,
        "loss_cents": payload["loss_cents"],
        "book_cents": payload["book_cents"],
        "ev_cents": payload["ev_cents"],
        "ev_per_trade_display": payload["ev_per_trade_display"],
        "ev_display": payload["ev_display"],
    }


def _lock_ints(block: dict[str, Any]) -> dict[str, int]:
    out = {
        "n": int(block["n"]),
        "s_n": int(block["s_n"]),
        "book_cents": int(block["book_cents"]),
    }
    if block.get("w_t40") is not None:
        out["w_t40"] = int(block["w_t40"])
        out["l_t40"] = int(block["l_t40"])
    return out


def _group_ev(
    rows: list[dict[str, Any]],
    *,
    key_fn,
    labels: tuple[tuple[str, str], ...],
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in labels}
    for row in rows:
        key = key_fn(row)
        if key not in groups:
            raise ChoosinTexasError("LOCK_MISMATCH", f"unknown book bin {key}")
        groups[key].append(row)
    out = []
    for key, label in labels:
        group = groups[key]
        if not group:
            continue
        body = _ev_block(group)
        body["key"] = key
        body["label"] = label
        out.append(body)
    if sum(int(row["n"]) for row in out) != len(rows):
        raise ChoosinTexasError("LOCK_MISMATCH", "book bin n does not sum to tape N")
    return out


def _split_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = ("IN_SAMPLE", "VALIDATION", "OOS")
    out = []
    for split in order:
        group = [row for row in rows if row["split"] == split]
        if not group:
            continue
        body = _ev_block(group)
        dates = [row["date"] for row in group]
        body["key"] = split
        body["label"] = split
        body["window"] = [min(dates), max(dates)]
        out.append(body)
    if sum(int(row["n"]) for row in out) != len(rows):
        raise ChoosinTexasError("LOCK_MISMATCH", "book split n does not sum to tape N")
    return out


def _slice_table(rows: list[dict[str, Any]], slices: tuple[str, ...]) -> list[dict[str, Any]]:
    out = []
    for slice_id in slices:
        group = [row for row in rows if row["slice"] == slice_id]
        if not group:
            continue
        body = _ev_block(group)
        body["key"] = slice_id
        body["label"] = slice_id
        out.append(body)
    if sum(int(row["n"]) for row in out) != len(rows):
        raise ChoosinTexasError("LOCK_MISMATCH", "book slice n does not sum to tape N")
    return out


def _cross_4_6_ge71(rows: list[dict[str, Any]]) -> dict[str, Any]:
    group = [
        row
        for row in rows
        if _lead_bin(int(row["lead"])) == "4_6" and _pregame_bin(int(row["pregame"])) == "ge71"
    ]
    body = _ev_block(group) if group else {
        "n": 0,
        "s_n": 0,
        "s_display": "0/0",
        "w_t40": 0,
        "l_t40": 0,
        "t40": 0,
        "book_cents": 0,
        "ev_per_trade_display": "UNAVAILABLE",
    }
    body["key"] = "4_6__ge71"
    body["label"] = "lead 4–6 × open ≥71¢"
    return body


def reconstruct_tape(spec: dict[str, Any]) -> dict[str, Any]:
    rows = _load_rows(spec["sport"], spec["slices"], spec["phase"])
    events = {row["event"] for row in rows}
    if len(events) != len(rows):
        raise ChoosinTexasError("LOCK_MISMATCH", f"{spec['tape_id']}: not one FIRST80 per game")
    dates = [row["date"] for row in rows]
    phases = sorted({row["phase"] for row in rows})
    sources = {PREGAME_SOURCE}
    ev40 = _ev_block(rows)
    return {
        "tape_id": spec["tape_id"],
        "label": spec.get("label") or spec["tape_id"],
        "sport": spec["sport"],
        "slices": list(spec["slices"]),
        "phase_filter": spec["phase"],
        "phases": phases,
        "role": spec["role"],
        "window": [min(dates), max(dates)],
        "pregame_source": PREGAME_SOURCE,
        "one_first80_per_game": True,
        "n": ev40["n"],
        "s_n": ev40["s_n"],
        "s_display": ev40["s_display"],
        "w_t40": ev40["w_t40"],
        "l_t40": ev40["l_t40"],
        "t40": ev40["t40"],
        "book_cents": ev40["book_cents"],
        "ev_cents": ev40["ev_cents"],
        "ev_per_trade_display": ev40["ev_per_trade_display"],
        "ev_display": ev40["ev_display"],
        "stop_cents": 40,
        "loss_cents": 40,
        "slice_rows": _slice_table(rows, spec["slices"]),
        "splits": _split_table(rows),
        "lead": _group_ev(rows, key_fn=lambda row: _lead_bin(int(row["lead"])), labels=LEAD_BINS),
        "open": _group_ev(
            rows, key_fn=lambda row: _pregame_bin(int(row["pregame"])), labels=PREGAME_BINS
        ),
        "cross_4_6_ge71": _cross_4_6_ge71(rows),
        "sources": list(sources),
    }


def reconstruct_tapes() -> dict[str, dict[str, Any]]:
    return {spec["tape_id"]: reconstruct_tape(spec) for spec in TAPE_SPECS}


def _assert_int_map(observed: dict[str, Any], locked: dict[str, Any], *, path: str) -> None:
    for key in ("n", "s_n", "book_cents", "w_t40", "l_t40"):
        if key not in locked:
            continue
        if int(observed[key]) != int(locked[key]):
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"{path}.{key} observed {observed[key]} != lock {locked[key]}",
            )


def _assert_rows(
    observed: list[dict[str, Any]],
    locked: list[dict[str, Any]],
    *,
    path: str,
) -> None:
    if len(observed) != len(locked):
        raise ChoosinTexasError(
            "LOCK_MISMATCH", f"{path} count {len(observed)} != lock {len(locked)}"
        )
    for got, want in zip(observed, locked, strict=True):
        if got["key"] != want["key"]:
            raise ChoosinTexasError(
                "LOCK_MISMATCH", f"{path} key {got['key']!r} != lock {want['key']!r}"
            )
        _assert_int_map(got, want, path=f"{path}.{got['key']}")
        if "window" in want and list(got.get("window") or []) != list(want["window"]):
            raise ChoosinTexasError(
                "LOCK_MISMATCH", f"{path}.{got['key']}.window != lock"
            )


def _assert_tapes(observed: dict[str, dict[str, Any]], locked: dict[str, Any]) -> None:
    if set(observed) != set(locked):
        raise ChoosinTexasError(
            "LOCK_MISMATCH", f"book tapes {sorted(observed)} != {sorted(locked)}"
        )
    for tape_id, tape in observed.items():
        want = locked[tape_id]
        _assert_int_map(tape, want, path=tape_id)
        if list(tape["window"]) != list(want["window"]):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{tape_id}.window != lock")
        if list(tape["slices"]) != list(want["slices"]):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{tape_id}.slices != lock")
        if want.get("phases") is not None and list(tape["phases"]) != list(want["phases"]):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{tape_id}.phases != lock")
        _assert_rows(tape["slice_rows"], want["slice_rows"], path=f"{tape_id}.slice_rows")
        _assert_rows(tape["splits"], want["splits"], path=f"{tape_id}.splits")
        _assert_rows(tape["lead"], want["lead"], path=f"{tape_id}.lead")
        _assert_rows(tape["open"], want["open"], path=f"{tape_id}.open")
        _assert_int_map(tape["cross_4_6_ge71"], want["cross_4_6_ge71"], path=f"{tape_id}.cross")


def load_book_lock(path: Path | None = None) -> dict[str, Any]:
    lock_path = path or default_book_json()
    if not lock_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {lock_path}")
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    if payload.get("schema") != BOOK_SCHEMA:
        raise ChoosinTexasError("LOCK_MISMATCH", f"book schema {payload.get('schema')!r}")
    if payload.get("book_id") != BOOK_ID:
        raise ChoosinTexasError("LOCK_MISMATCH", f"book_id {payload.get('book_id')!r}")
    if payload.get("live_execution") is not False or payload.get("submits") is not False:
        raise ChoosinTexasError("LOCK_MISMATCH", "saved book must stay research-only")
    return payload


def build_book() -> dict[str, Any]:
    lock = load_book_lock()
    tapes = reconstruct_tapes()
    _assert_tapes(tapes, lock["tapes"])
    registered = lock["registered"]
    if registered.get("live_execution") is not False:
        raise ChoosinTexasError("LOCK_MISMATCH", "registered book live_execution must be false")
    if registered.get("filters"):
        raise ChoosinTexasError("LOCK_MISMATCH", "registered 2026-27 book applies no filters")
    baseline = tapes["nba_2q_regular"]
    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "schema": BOOK_SCHEMA,
        "book_id": BOOK_ID,
        "live_execution": False,
        "submits": False,
        "risk_approved": False,
        "enable_live_trading": False,
        "tape_season": lock["tape_season"],
        "measure_season": lock["measure_season"],
        "pregame_source": PREGAME_SOURCE,
        "identity": lock["identity"],
        "library_path": str(LIBRARY_RELATIVE),
        "writeup_path": str(WRITEUP_RELATIVE),
        "note_path": str(NOTE_RELATIVE),
        "registered": registered,
        "hold_reverse": lock["hold_reverse"],
        "watch_do_not_filter": lock["watch_do_not_filter"],
        "forbidden": lock["forbidden"],
        "measurement": lock["measurement"],
        "conversion": lock["conversion"],
        "baseline": {
            "tape_id": baseline["tape_id"],
            "n": baseline["n"],
            "s_display": baseline["s_display"],
            "w_t40": baseline["w_t40"],
            "l_t40": baseline["l_t40"],
            "ev_per_trade_display": baseline["ev_per_trade_display"],
            "book_cents": baseline["book_cents"],
            "window": baseline["window"],
        },
        "tapes": [tapes[spec["tape_id"]] | {"label": lock["tapes"][spec["tape_id"]]["label"]} for spec in TAPE_SPECS],
        "disclaimers": lock["disclaimers"],
        "verification": {
            "status": "OBSERVED",
            "sources": [
                str(default_asked_six_csv().relative_to(repo_root())),
                str(LIBRARY_RELATIVE),
            ],
        },
    }
