"""Parse a Roller Labs CSV. Fail closed on missing rows or unreadable header."""

from __future__ import annotations

import csv
import io
from typing import Any

from roller.labs.schema import CSV_COLUMNS
from roller.superasi.models import SuperasiError

REQUIRED = (
    "record_type",
    "strategy_name",
    "population",
    "wins",
    "losses",
    "win_rate",
    "gross_ev",
    "classification",
    "result_hash",
    "plan_hash",
)

ROLLER_META = (
    "strategy_name",
    "sport",
    "league",
    "season",
    "date_from",
    "date_to",
    "universe",
    "observation_basis",
    "resolution",
    "pit_field",
    "entry_operation",
    "entry_parameters",
    "win_exit_operation",
    "win_exit_parameters",
    "loss_exit_operation",
    "loss_exit_parameters",
    "terminal_behavior",
    "plan_hash",
    "compiler_version",
    "warehouse_version",
    "identity_version",
    "catalog_version",
    "execution_version",
    "data_fingerprint",
    "backtest_status",
    "population",
    "wins",
    "losses",
    "win_rate",
    "loss_rate",
    "average_win",
    "average_loss",
    "risk_reward",
    "gross_ev",
    "result_hash",
)


def parse_labs_csv(text: str | bytes) -> dict[str, Any]:
    raw = text.decode("utf-8") if isinstance(text, bytes) else text
    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames is None:
        raise SuperasiError("LABS_CSV_INVALID", "Labs CSV has no header")
    header = list(reader.fieldnames)
    missing = [col for col in REQUIRED if col not in header]
    if missing:
        raise SuperasiError("LABS_CSV_INVALID", f"Labs CSV missing columns: {','.join(missing)}")
    schema_missing = [col for col in CSV_COLUMNS if col not in header]
    rows = [{k: (v if v is not None else "") for k, v in rec.items()} for rec in reader]
    by_type: dict[str, list[dict[str, str]]] = {}
    for rec in rows:
        kind = str(rec.get("record_type") or "").strip()
        by_type.setdefault(kind, []).append(rec)
    trade = list(by_type.get("row") or [])
    if not trade:
        raise SuperasiError("LABS_ROWS_REQUIRED", "SuperASI A Base requires record_type=row")
    meta_src = trade[0]
    if by_type.get("risk"):
        meta_src = by_type["risk"][0]
    meta = {col: str(meta_src.get(col) or "") for col in ROLLER_META}
    return {
        "header": header,
        "schema_missing": schema_missing,
        "rows": rows,
        "trade_rows": trade,
        "risk_rows": list(by_type.get("risk") or []),
        "weekly_rows": list(by_type.get("weekly") or []),
        "strategy_rows": list(by_type.get("strategy") or []),
        "meta": meta,
    }
