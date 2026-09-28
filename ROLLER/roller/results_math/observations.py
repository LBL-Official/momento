"""Normalize result rows. Does not change N, entry, exit, or terminal semantics."""

from __future__ import annotations

from typing import Any

from roller.results_math.models import AMBIGUOUS, OBSERVED, UNAVAILABLE


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    if value is True or value is False:
        return bool(value)
    if value in (1, "1", "true", "True", "YES", "yes"):
        return True
    if value in (0, "0", "false", "False", "NO", "no"):
        return False
    return None


def e4_to_cents(e4: int | None) -> int | None:
    if e4 is None:
        return None
    return int(e4) // 100


def normalize_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    entry_e4 = _int(row.get("entry_close") if row.get("entry_close") is not None else row.get("entry_price_e4"))
    exit_e4 = _int(row.get("exit_close") if row.get("exit_close") is not None else row.get("exit_price_e4"))
    hyp = row.get("hyp_pnl_cents")
    hyp_f: float | None
    try:
        hyp_f = float(hyp) if hyp is not None and hyp != "" else None
    except (TypeError, ValueError):
        hyp_f = None
    return_e4 = (exit_e4 - entry_e4) if entry_e4 is not None and exit_e4 is not None else None
    if hyp_f is not None:
        return_cents: float | None = hyp_f
    elif return_e4 is not None:
        return_cents = return_e4 / 100.0
    else:
        return_cents = None
    terminal = _bool(row.get("terminal_yes"))
    ts = row.get("entry_ts")
    return {
        "observation_id": row.get("observation_id") or f"obs_{index}",
        "game_id": str(row.get("internal_game_id") or "") or None,
        "ticker": str(row.get("ticker") or "") or None,
        "observation_ts": ts,
        "date": str(ts)[:10] if ts else None,
        "entry_price_e4": entry_e4,
        "entry_price_definition": (
            "last_close_e4"
            if row.get("price_basis") and "LAST_TRADE" in str(row.get("price_basis"))
            else "yes_bid_close"
        ),
        "exit_price_e4": exit_e4,
        "exit_ts": row.get("exit_ts"),
        "exit_outcome": row.get("exit_outcome"),
        "score_state": row.get("score_state"),
        "entry_side_state": row.get("entry_side_state"),
        "terminal_outcome": None if terminal is None else ("YES" if terminal else "NO"),
        "terminal_source": "kalshi_settlement",
        "path_true": _bool(row.get("path_true")),
        "return_e4": return_e4,
        "return_cents": return_cents,
        "return_status": OBSERVED if return_cents is not None else UNAVAILABLE,
        "mae_cents": _int(row.get("mae_cents")),
        "mfe_cents": _int(row.get("mfe_cents")),
        "holding_seconds": _int(row.get("holding_seconds")),
        "sample_partition": row.get("sample_partition"),
        "exclusion_reason": row.get("exclusion_reason"),
        "price_basis": row.get("price_basis"),
        "alignment": row.get("alignment"),
        "tie": AMBIGUOUS if row.get("exit_outcome") in ("TIE_EXCLUDED", "AMBIGUOUS") else None,
        "raw": row,
    }


def normalize_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [normalize_row(r, i) for i, r in enumerate(rows or [])]


def valid_returns(obs: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for r in obs:
        v = r.get("return_cents")
        if v is None:
            continue
        out.append(float(v))
    return out


def chronological_returns(obs: list[dict[str, Any]]) -> list[float]:
    dated = [
        (str(r.get("observation_ts") or ""), float(r["return_cents"]))
        for r in obs
        if r.get("return_cents") is not None
    ]
    dated.sort(key=lambda x: x[0])
    return [p for _, p in dated]


def return_vector(obs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in obs:
        rows.append(
            {
                "entry_ts": r.get("observation_ts"),
                "exit_ts": r.get("exit_ts"),
                "entry_price_e4": r.get("entry_price_e4"),
                "exit_price_e4": r.get("exit_price_e4"),
                "return_e4": r.get("return_e4"),
                "return_cents": r.get("return_cents"),
                "internal_game_id": r.get("game_id"),
                "ticker": r.get("ticker"),
                "date": r.get("date"),
                "score_state": r.get("score_state"),
                "entry_side_state": r.get("entry_side_state"),
                "exit_outcome": r.get("exit_outcome"),
                "path_true": r.get("path_true"),
                "holding_seconds": r.get("holding_seconds"),
                "return_status": r.get("return_status"),
            }
        )
    return rows
