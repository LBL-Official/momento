"""Persisted ROLLER desk capital. Integer cents and basis points only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.paths import find_root

SCHEMA_VERSION = "desk_settings_v1.0.0"
DEFAULT_BANKROLL_CENTS = 2_000_000  # $20,000
DEFAULT_ALLOCATION_BPS = 500  # 5%
FLOOR_NUM = 3
FLOOR_DEN = 4  # 0.75 × bankroll
TARGET_NUM = 3
TARGET_DEN = 2  # 1.50 × bankroll


class DeskSettingsError(ValueError):
    pass


def settings_path(*, root: Path | None = None, cfg: RollerConfig | None = None) -> Path:
    base = Path(root).resolve() if root is not None else (cfg.root if cfg is not None else find_root())
    return base / "config" / "desk_settings.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_ints(*, bankroll_cents: object, allocation_bps: object) -> tuple[int, int]:
    try:
        bankroll = int(bankroll_cents)
        allocation = int(allocation_bps)
    except (TypeError, ValueError) as exc:
        raise DeskSettingsError("invalid_desk_settings") from exc
    if bankroll <= 0:
        raise DeskSettingsError("invalid_bankroll")
    if not 0 < allocation <= 10_000:
        raise DeskSettingsError("invalid_allocation")
    return bankroll, allocation


def default_settings() -> dict[str, Any]:
    bankroll, allocation = DEFAULT_BANKROLL_CENTS, DEFAULT_ALLOCATION_BPS
    return {
        "schema_version": SCHEMA_VERSION,
        "bankroll_cents": bankroll,
        "allocation_bps": allocation,
        "updated_at": "",
        "source": "defaults",
    }


def _from_disk(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise DeskSettingsError("corrupt_desk_settings")
    bankroll, allocation = _validate_ints(
        bankroll_cents=raw.get("bankroll_cents"),
        allocation_bps=raw.get("allocation_bps"),
    )
    return {
        "schema_version": str(raw.get("schema_version") or SCHEMA_VERSION),
        "bankroll_cents": bankroll,
        "allocation_bps": allocation,
        "updated_at": str(raw.get("updated_at") or ""),
        "source": "disk",
    }


def load_desk_settings(*, root: Path | None = None, cfg: RollerConfig | None = None) -> dict[str, Any]:
    path = settings_path(root=root, cfg=cfg)
    if not path.is_file():
        return default_settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeskSettingsError("corrupt_desk_settings") from exc
    return _from_disk(raw)


def save_desk_settings(
    *,
    bankroll_cents: int,
    allocation_bps: int,
    root: Path | None = None,
    cfg: RollerConfig | None = None,
) -> dict[str, Any]:
    bankroll, allocation = _validate_ints(bankroll_cents=bankroll_cents, allocation_bps=allocation_bps)
    rec = {
        "schema_version": SCHEMA_VERSION,
        "bankroll_cents": bankroll,
        "allocation_bps": allocation,
        "updated_at": _utc_now(),
    }
    path = settings_path(root=root, cfg=cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**rec, "source": "disk"}


def bankroll_dollars(settings: dict[str, Any]) -> float:
    return int(settings["bankroll_cents"]) / 100.0


def allocation_rate(settings: dict[str, Any]) -> float:
    return int(settings["allocation_bps"]) / 10_000.0


def floor_cents(settings: dict[str, Any]) -> int:
    return (int(settings["bankroll_cents"]) * FLOOR_NUM) // FLOOR_DEN


def target_cents(settings: dict[str, Any]) -> int:
    return (int(settings["bankroll_cents"]) * TARGET_NUM) // TARGET_DEN


def snapshot(*, root: Path | None = None, cfg: RollerConfig | None = None) -> dict[str, Any]:
    settings = load_desk_settings(root=root, cfg=cfg)
    return {
        "schema_version": settings["schema_version"],
        "bankroll_cents": int(settings["bankroll_cents"]),
        "allocation_bps": int(settings["allocation_bps"]),
        "updated_at": settings.get("updated_at") or "",
        "source": settings.get("source") or "defaults",
        "floor_cents": floor_cents(settings),
        "target_cents": target_cents(settings),
    }


def public_settings(settings: dict[str, Any] | None = None, *, root: Path | None = None, cfg: RollerConfig | None = None) -> dict[str, Any]:
    rec = dict(settings) if settings is not None else snapshot(root=root, cfg=cfg)
    rec["floor_cents"] = int(rec.get("floor_cents") or floor_cents(rec))
    rec["target_cents"] = int(rec.get("target_cents") or target_cents(rec))
    return {
        **rec,
        "bankroll_dollars": bankroll_dollars(rec),
        "allocation_pct": int(rec["allocation_bps"]) / 100.0,
        "floor_dollars": rec["floor_cents"] / 100.0,
        "target_dollars": rec["target_cents"] / 100.0,
    }


def risk_config_defaults(*, root: Path | None = None, cfg: RollerConfig | None = None) -> dict[str, float]:
    rec = load_desk_settings(root=root, cfg=cfg)
    return {
        "initial_bankroll": bankroll_dollars(rec),
        "trade_allocation": allocation_rate(rec),
    }


def scaled_levels(*, root: Path | None = None, cfg: RollerConfig | None = None) -> dict[str, float]:
    rec = load_desk_settings(root=root, cfg=cfg)
    return {
        "initial_bankroll": bankroll_dollars(rec),
        "trade_allocation": allocation_rate(rec),
        "bankroll_floor": floor_cents(rec) / 100.0,
        "target_bankroll": target_cents(rec) / 100.0,
    }


def from_ui(*, bankroll_dollars: object, allocation_pct: object) -> tuple[int, int]:
    try:
        dollars = float(bankroll_dollars)
        pct = float(allocation_pct)
    except (TypeError, ValueError) as exc:
        raise DeskSettingsError("invalid_desk_settings") from exc
    if dollars != dollars or pct != pct:
        raise DeskSettingsError("invalid_desk_settings")
    cents = int(round(dollars * 100.0))
    bps = int(round(pct * 100.0))
    return _validate_ints(bankroll_cents=cents, allocation_bps=bps)


def stamp(*, root: Path | None = None, cfg: RollerConfig | None = None) -> dict[str, int | str]:
    rec = snapshot(root=root, cfg=cfg)
    return {
        "bankroll_cents": int(rec["bankroll_cents"]),
        "allocation_bps": int(rec["allocation_bps"]),
        "floor_cents": int(rec["floor_cents"]),
        "target_cents": int(rec["target_cents"]),
        "desk_settings_source": str(rec.get("source") or "defaults"),
    }
