"""superasi_package_v1 identity, checksums, trade normalization."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from roller.superasi.models import SuperasiError
from roller.superasi.versions import (
    CAVEATS,
    CODE_VERSION,
    PACKAGE_SCHEMA,
    PRICE_BASES,
    SEMANTICS_VERSION,
    SOURCES,
)

TRADE_IDENTITY = (
    "ticker",
    "internal_game_id",
    "sport",
    "slice",
    "dataset_split",
)
TRADE_REQUIRED_KEYS = TRADE_IDENTITY + (
    "entry_ts",
    "entry_close",
    "entry_price_e4",
    "entry_ask",
    "entry_spread",
    "entry_tradable",
    "exit_ts",
    "exit_close",
    "exit_outcome",
    "path_true",
    "win_exit",
    "loss_exit",
    "terminal_yes",
    "mae_cents",
    "mfe_cents",
    "holding_seconds",
    "price_basis",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_package_id() -> str:
    return uuid.uuid4().hex


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def unavailable(field: str) -> dict[str, Any]:
    return {"field": field, "status": "UNAVAILABLE", "value": None}


def normalize_trade(raw: dict[str, Any], index: int) -> dict[str, Any]:
    row = dict(raw)
    ticker = row.get("ticker") or row.get("event_ticker")
    if not ticker:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"trade[{index}] missing ticker")
    basis = str(row.get("price_basis") or "YES_BID_CLOSE")
    if basis == "TRADABLE_YES_BID":
        basis = "YES_BID_CLOSE"
    if basis not in PRICE_BASES:
        basis = "OTHER" if basis else "YES_BID_CLOSE"
    trade = {
        "observation_id": row.get("observation_id") or f"obs_{index}",
        "ticker": str(ticker),
        "internal_game_id": row.get("internal_game_id") or row.get("game_id") or row.get("event_id"),
        "sport": row.get("sport"),
        "slice": row.get("slice") or row.get("entry_quarter_bucket"),
        "dataset_split": row.get("dataset_split"),
        "entry_ts": row.get("entry_ts") or row.get("first_80_timestamp") or row.get("timestamp_utc"),
        "entry_close": _price_cents(
            row.get("entry_close") if row.get("entry_close") is not None else row.get("market_yes_bid"),
            row.get("entry_price_e4"),
        ),
        "entry_price_e4": _maybe_int(row.get("entry_price_e4")),
        "entry_ask": _price_cents(
            row.get("entry_ask") if row.get("entry_ask") is not None else row.get("market_yes_ask"),
            row.get("entry_ask_e4") or row.get("ask_e4"),
        ),
        "entry_spread": _maybe_int(row.get("entry_spread")),
        "entry_tradable": row.get("entry_tradable") if row.get("entry_tradable") is not None else row.get("tradable"),
        "exit_ts": row.get("exit_ts") or row.get("exit_timestamp_utc"),
        "exit_close": _price_cents(
            row.get("exit_close") if row.get("exit_close") is not None else row.get("exit_price_cents"),
            row.get("exit_price_e4"),
        ),
        "league": row.get("league"),
        "warehouse_season": row.get("warehouse_season") or row.get("season"),
        "te": row.get("te") if isinstance(row.get("te"), dict) else None,
        "alignment": row.get("alignment") or row.get("alignment_confidence"),
        "hyp_pnl_cents": _maybe_int(row.get("hyp_pnl_cents")),
        "path_steps": row.get("path_steps") if isinstance(row.get("path_steps"), list) else None,
        "entry_operation": row.get("entry_operation"),
        "entry_direction": row.get("entry_direction"),
        "entry_ordinal": row.get("entry_ordinal"),
        "exit_outcome": row.get("exit_outcome") or row.get("outcome_80_40") or row.get("exit_kind"),
        "path_true": _maybe_bool(row.get("path_true")),
        "win_exit": _maybe_bool(row.get("win_exit") if row.get("win_exit") is not None else row.get("win_80_40")),
        "loss_exit": _maybe_bool(row.get("loss_exit") if row.get("loss_exit") is not None else row.get("stopped_40")),
        "terminal_yes": _maybe_bool(row.get("terminal_yes") if row.get("terminal_yes") is not None else row.get("W")),
        "T40": _maybe_bool(row.get("T40") if row.get("T40") is not None else row.get("stopped_40")),
        "mae_cents": _maybe_int(row.get("mae_cents")),
        "mfe_cents": _maybe_int(row.get("mfe_cents")),
        "holding_seconds": _maybe_int(row.get("holding_seconds")),
        "price_basis": basis,
        "source_fields": {k: row[k] for k in row if k not in {"raw"}},
    }
    if trade["entry_spread"] is None and trade["entry_ask"] is not None and trade["entry_close"] is not None:
        try:
            trade["entry_spread"] = int(trade["entry_ask"]) - int(trade["entry_close"])
        except (TypeError, ValueError):
            trade["entry_spread"] = None
    if trade["entry_price_e4"] is None and trade["entry_close"] is not None:
        trade["entry_price_e4"] = int(trade["entry_close"]) * 100
    trade["entry_ask_status"] = "OBSERVED" if trade["entry_ask"] is not None else "UNAVAILABLE"
    trade["entry_spread_status"] = "OBSERVED" if trade["entry_spread"] is not None else "UNAVAILABLE"
    trade["entry_tradable_status"] = (
        "OBSERVED" if trade["entry_tradable"] is not None else "UNAVAILABLE"
    )
    if trade["terminal_yes"] is None:
        trade["terminal_yes_status"] = "UNAVAILABLE"
    else:
        trade["terminal_yes_status"] = "OBSERVED"
    if trade["loss_exit"] is None and trade["T40"] is not None:
        trade["loss_exit"] = bool(trade["T40"])
    if trade["path_true"] is None and trade["T40"] is not None:
        trade["path_true"] = not bool(trade["T40"])
    if trade["path_true"] is None and trade["loss_exit"] is not None:
        trade["path_true"] = not bool(trade["loss_exit"])
    if trade["win_exit"] is None and trade["loss_exit"] is not None:
        trade["win_exit"] = not bool(trade["loss_exit"])
    if trade["entry_close"] is None and trade["entry_price_e4"] is not None:
        trade["entry_close"] = int(trade["entry_price_e4"]) // 100
    return trade


def normalize_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_trade(r, i) for i, r in enumerate(rows)]


def new_package(
    *,
    source: str,
    trades: list[dict[str, Any]],
    research_spec: dict[str, Any] | None = None,
    research_object_id: str | None = None,
    compile_fingerprint: str | None = None,
    spec_fingerprint: str | None = None,
    question_hash: str | None = None,
    hashes: dict[str, Any] | None = None,
    dataset_version: str | None = None,
    trade_origin: str | None = None,
    definition_versions: dict[str, Any] | None = None,
    dataset_versions: dict[str, Any] | None = None,
    caveats: list[str] | None = None,
    analysis: dict[str, Any] | None = None,
    empirical_four_cell: dict[str, Any] | None = None,
    provenance_copy: dict[str, Any] | None = None,
    package_id: str | None = None,
    name: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if source not in SOURCES:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"unknown source {source}")
    if not trades:
        raise SuperasiError("EMPTY_POPULATION", "refusing empty SuperASI population")
    norm = normalize_trades(trades)
    bases = {t.get("price_basis") for t in norm}
    price_basis = next(iter(bases)) if len(bases) == 1 else "OTHER"
    notes = list(CAVEATS)
    if caveats:
        notes.extend(caveats)
    spec_fp = spec_fingerprint or compile_fingerprint
    pkg: dict[str, Any] = {
        "schema_version": PACKAGE_SCHEMA,
        "package_id": package_id or new_package_id(),
        "imported_at": utc_now(),
        "source": source,
        "research_spec": research_spec or {},
        "research_object_id": research_object_id,
        "name": name.strip() if isinstance(name, str) and name.strip() else None,
        "compile_fingerprint": spec_fp,
        "spec_fingerprint": spec_fp,
        "question_hash": question_hash,
        "hashes": dict(hashes) if hashes else {},
        "dataset_version": dataset_version,
        "trade_origin": trade_origin,
        "definition_versions": definition_versions or {},
        "dataset_versions": dataset_versions or {},
        "code_version": CODE_VERSION,
        "semantics_version": SEMANTICS_VERSION,
        "caveats": notes,
        "population_n": len(norm),
        "price_basis": price_basis,
        "live_execution": False,
        "analysis_gross_pre_superasi": _gross_analysis(analysis),
        "client_provenance": provenance_copy,
        "checksums": {},
    }
    if empirical_four_cell is not None:
        pkg["empirical_four_cell"] = empirical_four_cell
    if extra:
        pkg.update(extra)
    pkg["checksums"]["trades"] = sha256_hex(norm)
    pkg["checksums"]["package_identity"] = sha256_hex(
        {
            "package_id": pkg["package_id"],
            "source": source,
            "population_n": len(norm),
            "schema_version": PACKAGE_SCHEMA,
        }
    )
    return pkg, norm


def _gross_analysis(analysis: dict[str, Any] | None) -> dict[str, Any] | None:
    if not analysis:
        return None
    return {
        "label": "GROSS / PRE-SUPERASI",
        "observed": analysis.get("observed") or analysis.get("observed_ev") or analysis.get("observed_path"),
        "book": analysis.get("book") or analysis.get("book_price"),
        "settlement": analysis.get("settlement") or analysis.get("settlement_payoff"),
        "note": "Copied from ROLLER. SuperASI fees are not subtracted here.",
    }


def _price_cents(value: Any, e4: Any = None) -> int | None:
    """Kalshi research bars store yes_bid_close in e4 (80¢ → 8000). SuperASI math is cents."""
    raw = _maybe_int(value)
    if raw is not None:
        return raw // 100 if abs(raw) >= 200 else raw
    e4_i = _maybe_int(e4)
    if e4_i is not None:
        return e4_i // 100
    return None


def _maybe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _maybe_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if value is True or value is False:
        return bool(value)
    if value in (1, "1", "true", "True", "YES", "yes"):
        return True
    if value in (0, "0", "false", "False", "NO", "no"):
        return False
    return None
