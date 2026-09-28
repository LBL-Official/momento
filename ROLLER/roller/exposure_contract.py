"""Strategy / backtest exposure contract.

Separate from the Results contract.

Results answers: what was measured, and which statistics are valid?
This contract answers: what is one strategy trade, and what population
cardinality is required?

Results can analyze any declared unit. It does not own the strategy default.

Momento strategy backtest default:

    EXPOSURE_UNIT = GAME
    MAX_ENTRIES_PER_GAME = 1

Default execution is results_verify_only. strategy_enforced must be requested
explicitly and runs in the research execution layer before Results.
Results verifies the retained population. Results never rewrites N.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = "1.0.0"
ENFORCEMENT_VERSION = "1.0.0"

MODE_VERIFY_ONLY = "results_verify_only"
MODE_STRATEGY_ENFORCED = "strategy_enforced"

POLICY_FIRST_CHRONO = "FIRST_CHRONOLOGICAL_UNIQUE_ENTRY"

STATUS_VALID = "VALID"
STATUS_AMBIGUOUS = "AMBIGUOUS_EXPOSURE"
STATUS_CARDINALITY = "CARDINALITY_VIOLATION"
STATUS_DATA_REQUIRED = "DATA_REQUIRED"

REASON_MAX_EXCEEDED = "MAX_ENTRIES_EXCEEDED"
REASON_AMBIGUOUS = "AMBIGUOUS_EXPOSURE"
REASON_DATA_REQUIRED = "DATA_REQUIRED"

GAME = "GAME"
MULTI_ENTRY_PER_GAME = "MULTI_ENTRY_PER_GAME"
TEAM = "TEAM"
TICKER = "TICKER"
EVENT = "EVENT"

UNITS = frozenset({GAME, MULTI_ENTRY_PER_GAME, TEAM, TICKER, EVENT})

# Historical Results alias. Canonical unit is GAME.
ONE_GAME_ONE_TRADE = "ONE_GAME_ONE_TRADE"

ALIASES = {
    ONE_GAME_ONE_TRADE: GAME,
    "ONE_GAME": GAME,
    "INTERNAL_GAME_ID": GAME,
}

CLUSTER_FIELD = {
    GAME: "internal_game_id",
    MULTI_ENTRY_PER_GAME: "internal_game_id",
    TEAM: "team_id",
    TICKER: "ticker",
    EVENT: "event_id",
}

ROW_KEYS = {
    GAME: ("internal_game_id", "game_id"),
    MULTI_ENTRY_PER_GAME: ("internal_game_id", "game_id"),
    TEAM: ("team_id", "team"),
    TICKER: ("ticker",),
    EVENT: ("event_id", "event_ticker", "kalshi_event_ticker"),
}


def normalize_unit(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    token = str(raw).strip().upper().replace(" ", "_").replace("-", "_")
    if token in ALIASES:
        return ALIASES[token]
    if token in UNITS:
        return token
    return token


def _declared_max(result: dict[str, Any] | None, question: Any) -> int | None:
    sources: list[Any] = []
    if result:
        sources.extend(
            [
                result.get("max_entries_per_game"),
                result.get("max_entries_per_unit"),
                (result.get("identity") or {}).get("max_entries_per_game"),
                (result.get("identity") or {}).get("max_entries_per_unit"),
                (result.get("research_spec") or {}).get("max_entries_per_game"),
                (result.get("exposure") or {}).get("max_entries_per_unit"),
                ((result.get("compile") or {}).get("question") or {}).get("max_entries_per_game"),
            ]
        )
    if question is not None:
        if isinstance(question, dict):
            sources.extend([question.get("max_entries_per_game"), question.get("max_entries_per_unit")])
        else:
            sources.extend(
                [
                    getattr(question, "max_entries_per_game", None),
                    getattr(question, "max_entries_per_unit", None),
                ]
            )
    for raw in sources:
        if raw is None or raw == "":
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _declared_unit(result: dict[str, Any] | None, question: Any) -> str | None:
    sources: list[Any] = []
    if result:
        sources.extend(
            [
                result.get("exposure_unit"),
                (result.get("identity") or {}).get("exposure_unit"),
                (result.get("research_spec") or {}).get("exposure_unit"),
                (result.get("exposure") or {}).get("exposure_unit"),
                ((result.get("compile") or {}).get("question") or {}).get("exposure_unit"),
            ]
        )
    if question is not None:
        if isinstance(question, dict):
            sources.append(question.get("exposure_unit"))
        else:
            sources.append(getattr(question, "exposure_unit", None))
    for raw in sources:
        unit = normalize_unit(raw)
        if unit:
            return unit
    return None


def strategy_default() -> dict[str, Any]:
    """Momento strategy backtest default. Not a Results inference."""
    return {
        "contract_version": CONTRACT_VERSION,
        "object_kind": "strategy",
        "exposure_unit": GAME,
        "max_entries_per_unit": 1,
        "max_entries_per_game": 1,
        "clustering_field": CLUSTER_FIELD[GAME],
        "source": "strategy_default",
        "enforced_by": MODE_VERIFY_ONLY,
        "execution_enforced": False,
        "enforcement_mode": MODE_VERIFY_ONLY,
        "selection_policy": POLICY_FIRST_CHRONO,
        "exposure_enforcement_version": ENFORCEMENT_VERSION,
        "rule": "EXPOSURE_UNIT = GAME · MAX_ENTRIES_PER_GAME = 1",
        "note": (
            "Strategy containment lives here. Default execution is results_verify_only. "
            "strategy_enforced must be requested explicitly. Results never rewrites N."
        ),
    }


def resolve_exposure_contract(
    result: dict[str, Any] | None = None,
    question: Any = None,
    *,
    object_kind: str = "strategy",
) -> dict[str, Any]:
    """Resolve the exposure contract. Explicit declaration wins. Strategy default is GAME/1."""
    declared_unit = _declared_unit(result, question)
    declared_max = _declared_max(result, question)
    if declared_unit is None:
        out = strategy_default()
        out["object_kind"] = object_kind
        return out
    unit = declared_unit
    if unit == MULTI_ENTRY_PER_GAME:
        max_n = declared_max
    elif declared_max is not None:
        max_n = declared_max
    elif unit == GAME:
        max_n = 1
    else:
        max_n = 1
    known = unit in UNITS
    return {
        "contract_version": CONTRACT_VERSION,
        "object_kind": object_kind,
        "exposure_unit": unit,
        "max_entries_per_unit": max_n,
        "max_entries_per_game": max_n if unit in {GAME, MULTI_ENTRY_PER_GAME} else None,
        "clustering_field": CLUSTER_FIELD.get(unit, "unknown"),
        "source": "declared",
        "enforced_by": MODE_VERIFY_ONLY,
        "execution_enforced": False,
        "enforcement_mode": MODE_VERIFY_ONLY,
        "selection_policy": POLICY_FIRST_CHRONO,
        "exposure_enforcement_version": ENFORCEMENT_VERSION,
        "known_unit": known,
        "rule": (
            f"EXPOSURE_UNIT = {unit}"
            + (f" · MAX_ENTRIES_PER_UNIT = {max_n}" if max_n is not None else " · MAX_ENTRIES_PER_UNIT = UNBOUNDED")
        ),
        "note": "Declared research exposure. Results verifies. Results does not rewrite N.",
    }


@dataclass(frozen=True)
class ExposureContract:
    exposure_unit: str = GAME
    max_entries_per_unit: int | None = 1
    enforcement_mode: str = MODE_VERIFY_ONLY
    selection_policy: str = POLICY_FIRST_CHRONO
    enforcement_version: str = ENFORCEMENT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "exposure_unit": self.exposure_unit,
            "max_entries_per_unit": self.max_entries_per_unit,
            "max_entries_per_game": self.max_entries_per_unit if self.exposure_unit in {GAME, MULTI_ENTRY_PER_GAME} else None,
            "enforcement_mode": self.enforcement_mode,
            "selection_policy": self.selection_policy,
            "exposure_enforcement_version": self.enforcement_version,
            "execution_enforced": self.enforcement_mode == MODE_STRATEGY_ENFORCED,
            "enforced_by": self.enforcement_mode,
            "clustering_field": CLUSTER_FIELD.get(self.exposure_unit, "unknown"),
            "rule": (
                f"EXPOSURE_UNIT = {self.exposure_unit}"
                + (
                    f" · MAX_ENTRIES_PER_UNIT = {self.max_entries_per_unit}"
                    if self.max_entries_per_unit is not None
                    else " · MAX_ENTRIES_PER_UNIT = UNBOUNDED"
                )
            ),
        }


def normalize_enforcement_mode(raw: Any) -> str:
    token = str(raw or "").strip().lower().replace("-", "_")
    if token == MODE_STRATEGY_ENFORCED:
        return MODE_STRATEGY_ENFORCED
    return MODE_VERIFY_ONLY


def enforcement_request_from_draft(draft: dict[str, Any] | None) -> tuple[str, str | None, int | None]:
    """Never infers strategy_enforced from sport, MLB, or Results."""
    if not isinstance(draft, dict):
        return MODE_VERIFY_ONLY, None, None
    mode = normalize_enforcement_mode(
        draft.get("exposure_enforcement_mode")
        or draft.get("exposureEnforcementMode")
        or draft.get("exposure_enforcement")
    )
    unit = draft.get("exposure_unit") or draft.get("exposureUnit")
    raw_max = (
        draft.get("max_entries_per_unit")
        or draft.get("maxEntriesPerUnit")
        or draft.get("max_entries_per_game")
        or draft.get("maxEntriesPerGame")
    )
    cap: int | None = None
    if raw_max not in (None, ""):
        try:
            cap = int(raw_max)
        except (TypeError, ValueError):
            cap = None
    return mode, (str(unit) if unit not in (None, "") else None), cap


def executable_strategy_contract(
    *,
    exposure_unit: str = GAME,
    max_entries_per_unit: int | None = 1,
    enforcement_mode: str = MODE_STRATEGY_ENFORCED,
) -> ExposureContract:
    unit = normalize_unit(exposure_unit) or GAME
    if unit not in UNITS:
        unit = GAME
    if unit == MULTI_ENTRY_PER_GAME and max_entries_per_unit is None:
        cap: int | None = None
    elif max_entries_per_unit is None and unit == GAME:
        cap = 1
    else:
        cap = max_entries_per_unit
    return ExposureContract(
        exposure_unit=unit,
        max_entries_per_unit=cap,
        enforcement_mode=enforcement_mode,
        selection_policy=POLICY_FIRST_CHRONO,
        enforcement_version=ENFORCEMENT_VERSION,
    )


def exposure_identity_payload(contract: ExposureContract | dict[str, Any] | None) -> dict[str, Any] | None:
    """Hash payload. None for results_verify_only so existing hashes stay stable."""
    if contract is None:
        return None
    raw = contract.to_dict() if isinstance(contract, ExposureContract) else dict(contract)
    mode = str(raw.get("enforcement_mode") or MODE_VERIFY_ONLY)
    if mode != MODE_STRATEGY_ENFORCED:
        return None
    return {
        "exposure_enforcement_version": raw.get("exposure_enforcement_version") or ENFORCEMENT_VERSION,
        "exposure_enforcement_mode": mode,
        "exposure_unit": raw.get("exposure_unit"),
        "max_entries_per_unit": raw.get("max_entries_per_unit"),
        "selection_policy": raw.get("selection_policy") or POLICY_FIRST_CHRONO,
    }


def unit_key(row: dict[str, Any], exposure_unit: str) -> str | None:
    """Grouping key. Never substitutes ticker for GAME. Missing → None."""
    unit = normalize_unit(exposure_unit) or str(exposure_unit)
    if unit not in UNITS:
        return None
    for field in ROW_KEYS[unit]:
        value = row.get(field)
        if value is not None and str(value).strip() != "":
            return str(value)
    return None


def _parse_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        ts = value
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    text = str(value).replace("Z", "+00:00")
    try:
        ts = datetime.fromisoformat(text)
    except ValueError:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _candidate_sort_key(row: dict[str, Any], key: str | None) -> tuple[datetime, str]:
    ts = _parse_ts(row.get("entry_ts")) or datetime.min.replace(tzinfo=timezone.utc)
    ident = str(row.get("candidate_id") or "")
    if not ident:
        ident = "|".join(
            [
                ts.isoformat(),
                str(row.get("ticker") or ""),
                key or "",
            ]
        )
    return (ts, ident)


def enforce_exposure(
    candidates: list[dict[str, Any]],
    contract: ExposureContract | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Retain a strategy population. Does not invent a same-timestamp tie-break."""
    if isinstance(contract, dict):
        contract = executable_strategy_contract(
            exposure_unit=str(contract.get("exposure_unit") or GAME),
            max_entries_per_unit=contract.get("max_entries_per_unit"),
            enforcement_mode=str(contract.get("enforcement_mode") or MODE_STRATEGY_ENFORCED),
        )
    contract = contract or executable_strategy_contract()
    unit = contract.exposure_unit
    max_n = contract.max_entries_per_unit
    raw_n = len(candidates)
    excluded: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    data_required: list[dict[str, Any]] = []
    ambiguous_units: list[str] = []

    if unit not in UNITS:
        return _ledger(
            contract,
            candidates,
            retained=[],
            excluded=[{"row": c, "reason": REASON_DATA_REQUIRED} for c in candidates],
            data_required=list(candidates),
            ambiguous_units=[],
            status=STATUS_DATA_REQUIRED,
            hard_failure=False,
        )

    keyed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        key = unit_key(row, unit)
        if key is None:
            data_required.append(row)
            excluded.append({"row": row, "reason": REASON_DATA_REQUIRED})
            continue
        keyed[key].append(row)

    for key, group in keyed.items():
        ordered = sorted(group, key=lambda row: _candidate_sort_key(row, key))
        remaining = max_n
        by_ts: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
        for row in ordered:
            ts, _ = _candidate_sort_key(row, key)
            by_ts[ts].append(row)
        for ts in sorted(by_ts):
            bucket = by_ts[ts]
            if remaining is not None and remaining <= 0:
                for row in bucket:
                    excluded.append({"row": row, "reason": REASON_MAX_EXCEEDED, "unit_key": key})
                continue
            if remaining is None or len(bucket) <= remaining:
                retained.extend(bucket)
                if remaining is not None:
                    remaining -= len(bucket)
                continue
            ambiguous_units.append(key)
            for row in bucket:
                excluded.append({"row": row, "reason": REASON_AMBIGUOUS, "unit_key": key})
            remaining = 0

    retained_keys = [unit_key(r, unit) for r in retained]
    counts = defaultdict(int)
    for k in retained_keys:
        if k:
            counts[k] += 1
    max_after = max(counts.values()) if counts else 0
    violates = max_n is not None and max_after > int(max_n)
    if violates:
        status = STATUS_CARDINALITY
    elif data_required:
        status = STATUS_DATA_REQUIRED
    elif ambiguous_units:
        status = STATUS_AMBIGUOUS
    else:
        status = STATUS_VALID
    return _ledger(
        contract,
        candidates,
        retained=retained,
        excluded=excluded,
        data_required=data_required,
        ambiguous_units=ambiguous_units,
        status=status,
        hard_failure=violates and contract.enforcement_mode == MODE_STRATEGY_ENFORCED,
        raw_n=raw_n,
        max_after=max_after,
        keyed=keyed,
    )


def _ledger(
    contract: ExposureContract,
    candidates: list[dict[str, Any]],
    *,
    retained: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    data_required: list[dict[str, Any]],
    ambiguous_units: list[str],
    status: str,
    hard_failure: bool,
    raw_n: int | None = None,
    max_after: int = 0,
    keyed: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    unit = contract.exposure_unit
    keyed = keyed or {}
    before_counts = {k: len(v) for k, v in keyed.items()}
    dupes_before = sum(1 for n in before_counts.values() if n > 1)
    max_before = max(before_counts.values()) if before_counts else 0
    unique_before = len(before_counts)
    unique_after = len({unit_key(r, unit) for r in retained if unit_key(r, unit)})
    excluded_n = len(excluded)
    return {
        **contract.to_dict(),
        "status": status,
        "exposure_status": status,
        "hard_failure": hard_failure,
        "selection_policy": contract.selection_policy,
        "raw_entry_candidates": raw_n if raw_n is not None else len(candidates),
        "exposure_eligible": (raw_n if raw_n is not None else len(candidates)) - len(data_required),
        "exposure_retained": len(retained),
        "exposure_excluded": excluded_n,
        "exposure_ambiguous": len(set(ambiguous_units)),
        "exposure_data_required": len(data_required),
        "unique_units_before": unique_before,
        "unique_units_after": unique_after,
        "unique_games_before_exposure": unique_before if unit in {GAME, MULTI_ENTRY_PER_GAME} else None,
        "unique_games_after_exposure": unique_after if unit in {GAME, MULTI_ENTRY_PER_GAME} else None,
        "duplicate_game_candidates": dupes_before,
        "max_entries_per_game_observed": max_after if unit in {GAME, MULTI_ENTRY_PER_GAME} else None,
        "max_entries_observed": max_after,
        "max_entries_observed_before": max_before,
        "retained": retained,
        "excluded": [
            {
                "ticker": (item["row"].get("ticker") if isinstance(item, dict) and "row" in item else None),
                "internal_game_id": unit_key(item["row"], unit) if isinstance(item, dict) and "row" in item else None,
                "entry_ts": (item["row"].get("entry_ts") if isinstance(item, dict) and "row" in item else None),
                "reason": item.get("reason"),
            }
            for item in excluded
        ],
        "invariants": {
            "retained_le_unique_units": (
                contract.max_entries_per_unit != 1 or len(retained) <= unique_after
            ),
            "max_entries_respected": (
                contract.max_entries_per_unit is None or max_after <= int(contract.max_entries_per_unit)
            ),
            "clean_retained_eq_units": (
                not ambiguous_units
                and contract.max_entries_per_unit == 1
                and len(retained) == unique_after
            ),
        },
    }

