"""Safe JSON serialization for ROLLER Terminal.

Missing / NaN / NOT_CONSTRUCTIBLE must never become 0.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import pandas as pd


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def to_jsonable(value: Any) -> Any:
    """Convert nested ROLLER payloads to JSON-safe Python values.

    Rules:
    - None / NaN / NaT → null
    - datetime / date / Timestamp → ISO-8601 string
    - numpy / pandas scalars → Python scalars
    - Never coerce missing measurement to 0
    """
    if _is_missing(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        ts = pd.Timestamp(value)
        text = ts.isoformat()
        return text.replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (bytes, str)):
        try:
            return to_jsonable(value.item())
        except (ValueError, AttributeError):
            pass
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    # pandas / numpy integers
    try:
        if hasattr(value, "dtype") and str(getattr(value, "dtype", "")).startswith("int"):
            return int(value)
    except (TypeError, ValueError):
        pass
    return str(value)


def dataframe_records(df: pd.DataFrame, columns: list[str] | None = None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    cols = [c for c in (columns or list(df.columns)) if c in df.columns]
    out: list[dict[str, Any]] = []
    for row in df[cols].to_dict(orient="records"):
        out.append({k: to_jsonable(v) for k, v in row.items()})
    return out
