"""Locked NCAAB H1_2 / H2_1 cohorts. Split before any Austin query."""

from __future__ import annotations

import csv
import hashlib
import json
from math import floor
from typing import Any

from roller.austin.clock import parse_utc
from roller.austin.errors import AustinError
from roller.austin.experiments.ids import (
    ALLOWED_SLICES,
    CSV_SPORT,
    ENTRY_SOURCE,
    EXPERIMENT_A,
    EXPERIMENT_B,
    LOCK_BY_EXPERIMENT,
    MEMBERS,
    N_A,
    N_B,
    N_BY_EXPERIMENT,
    N_UNION,
    SLICE_A,
    SLICE_B,
    SLICE_BY_EXPERIMENT,
    assert_experiment_id,
    assert_slice,
)
from roller.austin.experiments.warehouse import join_ncaab_identity
from roller.austin.paths import experiment_dir
from roller.austin.store import load_json, write_json
from roller.choosin_texas.sources import default_asked_six_csv


def _bool(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes"}


def _int(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def normalize_timestamp(value: object) -> str | None:
    stamp = parse_utc(value)
    if stamp is None:
        text = str(value or "").strip()
        return text or None
    return stamp.isoformat()


def _trade_id(rec: dict[str, str]) -> str:
    key = "|".join(
        [
            str(rec.get("event_id") or ""),
            str(rec.get("ticker") or ""),
            str(rec.get("timestamp_utc") or ""),
            "FIRST80",
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def load_asked_six_ncaab() -> list[dict[str, Any]]:
    path = default_asked_six_csv()
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            sport = str(rec.get("sport") or "").strip()
            if sport != CSV_SPORT:
                continue
            slice_name = str(rec.get("slice") or "").strip()
            if slice_name in {"H2_2", "H1_1", "H2_2ND10", "2ND10"}:
                continue
            if slice_name not in ALLOWED_SLICES:
                continue
            assert_slice(slice_name)
            rows.append(
                {
                    "trade_id": _trade_id(rec),
                    "asked_game_id": str(rec.get("game_id") or "").strip(),
                    "event_id": str(rec.get("event_id") or "").strip(),
                    "ticker": str(rec.get("ticker") or "").strip(),
                    "game_date": str(rec.get("game_date") or "").strip(),
                    "entry_timestamp": str(rec.get("timestamp_utc") or "").strip(),
                    "period": _int(rec.get("period")),
                    "game_clock": str(rec.get("game_clock") or "").strip(),
                    "entry_seconds_remaining": _int(rec.get("period_remaining_s")),
                    "side": str(rec.get("side") or "").strip().lower(),
                    "entry_price_cents": _int(rec.get("market_yes_bid")),
                    "home_score_entry": _int(rec.get("score_home")),
                    "away_score_entry": _int(rec.get("score_away")),
                    "score_diff_entry": _int(rec.get("score_diff")),
                    "won": _bool(rec.get("W")),
                    "t40": _bool(rec.get("T40")),
                    "terminal_yes": _bool(rec.get("terminal_yes")),
                    "last_tradable_timestamp": normalize_timestamp(rec.get("last_tradable_timestamp")),
                    "last_tradable_yes_bid_cents": _int(rec.get("last_tradable_yes_bid_cents")),
                    "slice": slice_name,
                    "entry_source": ENTRY_SOURCE,
                    "home_team": str(rec.get("home_team_code") or rec.get("home_team") or ""),
                    "away_team": str(rec.get("away_team_code") or rec.get("away_team") or ""),
                }
            )
    return rows


def assert_locked_population(rows: list[dict[str, Any]]) -> None:
    a = [r for r in rows if r["slice"] == SLICE_A]
    b = [r for r in rows if r["slice"] == SLICE_B]
    if any(r["slice"] == "H2_2" for r in rows):
        raise AustinError("LOCK_MISMATCH", "H2_2 in eligible cohort")
    if len(a) != N_A:
        raise AustinError("LOCK_MISMATCH", f"H1_2 N={len(a)} != {N_A}")
    if len(b) != N_B:
        raise AustinError("LOCK_MISMATCH", f"H2_1 N={len(b)} != {N_B}")
    if len(rows) != N_UNION:
        raise AustinError("LOCK_MISMATCH", f"union N={len(rows)} != {N_UNION}")
    for experiment_id, subset in ((EXPERIMENT_A, a), (EXPERIMENT_B, b)):
        lock = LOCK_BY_EXPERIMENT[experiment_id]
        w = sum(1 for r in subset if r["won"])
        l = len(subset) - w
        t40 = sum(1 for r in subset if r["t40"])
        win_no = sum(1 for r in subset if r["won"] and not r["t40"])
        if w != lock.W or l != lock.L or win_no != lock.win_no:
            raise AustinError(
                "LOCK_MISMATCH",
                f"{experiment_id} cells drifted W={w} L={l} W∩¬T40={win_no} T40={t40}",
            )


def _game_key(row: dict[str, Any]) -> str:
    return str(row.get("internal_game_id") or row.get("asked_game_id") or row["event_id"])


def attach_warehouse(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    identity = join_ncaab_identity()
    out = []
    for row in rows:
        extra = identity.get(row["ticker"]) or {}
        attached = {
            **row,
            "internal_game_id": extra.get("internal_game_id") or row.get("asked_game_id"),
            "warehouse_event_id": extra.get("event_id"),
            "warehouse_joined": bool(extra.get("internal_game_id")),
        }
        out.append(attached)
    return out


def split_games(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    games: dict[str, dict[str, Any]] = {}
    for row in rows:
        gid = _game_key(row)
        prev = games.get(gid)
        if prev is None or (row["entry_timestamp"], gid) < (prev["entry_timestamp"], gid):
            games[gid] = {
                "internal_game_id": gid,
                "game_date": row["game_date"],
                "entry_timestamp": row["entry_timestamp"],
            }
    ordered = sorted(
        games.values(),
        key=lambda g: (g["game_date"], g["entry_timestamp"], g["internal_game_id"]),
    )
    g = len(ordered)
    cut = floor(g / 2)
    discovery = [item["internal_game_id"] for item in ordered[:cut]]
    confirmation = [item["internal_game_id"] for item in ordered[cut:]]
    return discovery, confirmation


def date_boundary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = sorted(str(r.get("game_date") or "") for r in rows if r.get("game_date"))
    return {
        "first_game_date": dates[0] if dates else None,
        "last_game_date": dates[-1] if dates else None,
    }


def _cohort_payload(experiment_id: str, role: str, rows: list[dict[str, Any]], game_ids: list[str]) -> dict[str, Any]:
    body = {
        "experiment_id": experiment_id,
        "slice": SLICE_BY_EXPERIMENT[experiment_id],
        "role": role,
        "n_lock": N_BY_EXPERIMENT[experiment_id],
        "n_games": len(game_ids),
        "n_trades": len(rows),
        "game_ids": game_ids,
        "trades": rows,
        "date_boundary": date_boundary(rows),
        "split_method": "temporal_floor_g_over_2_unique_games",
        "sort": ["game_date ASC", "entry_timestamp ASC", "internal_game_id ASC"],
    }
    raw = json.dumps({"game_ids": game_ids, "trade_ids": [r["trade_id"] for r in rows]}, sort_keys=True)
    body["cohort_hash"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return body


def print_lock_card(payload: dict[str, Any], model: dict[str, Any] | None = None) -> str:
    lines = ["MODEL MANIFEST VERIFIED = PASS" if model and model.get("verified") else "MODEL MANIFEST"]
    if model:
        lines.append(f"git_commit={model.get('git_commit')} status={model.get('git_commit_status')} reason={model.get('git_commit_reason')}")
        lines.append(f"model_manifest_hash={model.get('model_manifest_hash')}")
    h2 = 0
    for experiment_id in MEMBERS:
        block = payload.get(experiment_id) or {}
        disc = block.get("discovery") or {}
        conf = block.get("confirmation") or {}
        d_bound = disc.get("date_boundary") or date_boundary(disc.get("trades") or [])
        c_bound = conf.get("date_boundary") or date_boundary(conf.get("trades") or [])
        for row in list(disc.get("trades") or []) + list(conf.get("trades") or []):
            if str(row.get("slice")) == "H2_2":
                h2 += 1
        label = "A" if experiment_id == EXPERIMENT_A else "B"
        lines += [
            "",
            f"EXPERIMENT {label}: {experiment_id}",
            f"slice {SLICE_BY_EXPERIMENT[experiment_id]}",
            f"N total {N_BY_EXPERIMENT[experiment_id]}",
            f"N discovery trades {disc.get('n_trades')} games {disc.get('n_games')}",
            f"N confirmation trades {conf.get('n_trades')} games {conf.get('n_games')}",
            f"discovery date boundary {d_bound.get('first_game_date')} → {d_bound.get('last_game_date')}",
            f"confirmation date boundary {c_bound.get('first_game_date')} → {c_bound.get('last_game_date')}",
            f"discovery hash {disc.get('cohort_hash')}",
            f"confirmation hash {conf.get('cohort_hash')}",
        ]
    lines += ["", f"H2_2 rows = {h2}"]
    text = "\n".join(lines)
    print(text)
    return text


def persist_experiment_cohorts(experiment_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    experiment_id = assert_experiment_id(experiment_id)
    if any(r["slice"] == "H2_2" for r in rows):
        raise AustinError("LOCK_MISMATCH", "H2_2 cannot enter a cohort")
    if len(rows) != N_BY_EXPERIMENT[experiment_id]:
        raise AustinError("LOCK_MISMATCH", f"{experiment_id} N={len(rows)}")
    discovery_ids, confirmation_ids = split_games(rows)
    disc_set = set(discovery_ids)
    conf_set = set(confirmation_ids)
    if disc_set & conf_set:
        raise AustinError("LOCK_MISMATCH", "discovery/confirmation game overlap")
    disc_rows = [r for r in rows if _game_key(r) in disc_set]
    conf_rows = [r for r in rows if _game_key(r) in conf_set]
    root = experiment_dir(experiment_id)
    disc = _cohort_payload(experiment_id, "DISCOVERY", disc_rows, discovery_ids)
    conf = _cohort_payload(experiment_id, "CONFIRMATION", conf_rows, confirmation_ids)
    write_json(root / "discovery_cohort.json", disc)
    write_json(root / "confirmation_cohort.json", conf)
    prior = load_json(root / "MANIFEST.json", required=False) or {}
    write_json(
        root / "MANIFEST.json",
        {
            **prior,
            "experiment_id": experiment_id,
            "slice": SLICE_BY_EXPERIMENT[experiment_id],
            "n_trades": len(rows),
            "discovery_hash": disc["cohort_hash"],
            "confirmation_hash": conf["cohort_hash"],
            "split_before_query": True,
            "page3_n280_queried": False,
            "policy_status": prior.get("policy_status") or "UNFROZEN",
            "policy_hash": prior.get("policy_hash") or "UNAVAILABLE",
            "confirmation_result": prior.get("confirmation_result") or "NOT RUN",
        },
    )
    return {"discovery": disc, "confirmation": conf}


def write_all_cohorts() -> dict[str, Any]:
    rows = attach_warehouse(load_asked_six_ncaab())
    assert_locked_population(rows)
    out = {}
    for experiment_id in MEMBERS:
        slice_name = SLICE_BY_EXPERIMENT[experiment_id]
        subset = [r for r in rows if r["slice"] == slice_name]
        out[experiment_id] = persist_experiment_cohorts(experiment_id, subset)
    return out


def load_cohort(experiment_id: str, role: str) -> dict[str, Any]:
    experiment_id = assert_experiment_id(experiment_id)
    name = "discovery_cohort.json" if role == "DISCOVERY" else "confirmation_cohort.json"
    path = experiment_dir(experiment_id) / name
    payload = load_json(path)
    if any(str(t.get("slice")) == "H2_2" for t in payload.get("trades") or []):
        raise AustinError("LOCK_MISMATCH", "H2_2 leaked into persisted cohort")
    for trade in payload.get("trades") or []:
        trade["last_tradable_timestamp"] = normalize_timestamp(trade.get("last_tradable_timestamp"))
    return payload


def ensure_cohorts() -> dict[str, Any]:
    missing = any(not (experiment_dir(eid) / "discovery_cohort.json").is_file() for eid in MEMBERS)
    if missing:
        return write_all_cohorts()
    return {
        eid: {
            "discovery": load_cohort(eid, "DISCOVERY"),
            "confirmation": load_cohort(eid, "CONFIRMATION"),
        }
        for eid in MEMBERS
    }
