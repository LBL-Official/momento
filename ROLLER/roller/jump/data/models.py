"""Jump data-plane constants. Consumer only. LIVE EXECUTION = FALSE."""

from __future__ import annotations

from datetime import datetime, timezone

LIVE_EXECUTION = False
PRODUCT = "Jump"
SCHEMA = "jump.data.v0"
CONTEXT_SCHEMA = "jump.research_context.v0"
LINEAGE_SCHEMA = "jump.lineage.v0"
HANDLE_SCHEMA = "jump.dataset_handle.v0"
DEFAULT_TRADE_ID = "f84fd059fc0e1429"
AUSTIN_N = 604
AUSTIN_UNIVERSE = "choosin_nba_2q3q_604"
CHOOSIN_N = 936
CHOOSIN_UNIVERSE = "derived_four_936"
UNAVAILABLE = "UNAVAILABLE"
NBA_WAREHOUSE = "nba"

WRITE_DENIED = frozenset({"WRITE", "CONTROL"})
READ_OK = frozenset({"READ", "QUERY"})


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
