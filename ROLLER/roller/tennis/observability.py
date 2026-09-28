"""Per-layer tennis availability. Not a compile gate. Not a fill.

Identity, settlement, yes-bid, prints, sequence PBP, and PIT point-state
are separate observational layers. Missing one layer is not DATA_REQUIRED
for the others, and is never N=0.

RESEARCH ONLY. SEQUENCE-ONLY PBP ≠ PIT PBP. LAST TRADE ≠ YES BID.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roller.config import RollerConfig

AVAILABLE = "AVAILABLE"
PARTIAL = "PARTIAL"
MISSING = "MISSING"
NO_POINT_DATA = "NO_POINT_DATA"

LAYER_ORDER = (
    "event_identity",
    "kalshi_settlement",
    "yes_bid_candles",
    "trade_ticks",
    "last_trade_1m",
    "mcp_pbp",
    "pit_point_state",
)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dataset_exists(cfg: RollerConfig, name: str) -> bool:
    try:
        path = cfg.dataset_path("ATP", "2025-2026", name)
    except (KeyError, FileNotFoundError):
        return False
    p = Path(path)
    if p.is_file():
        return True
    if p.is_dir():
        return any(p.rglob("*"))
    return False


def _coverage_status(have: int, universe: int, *, present: bool) -> str:
    if not present or have <= 0 or universe <= 0:
        return MISSING
    if have < universe:
        return PARTIAL
    return AVAILABLE


def _layer(status: str, *, have: int | None = None, universe: int | None = None, note: str = "") -> dict[str, Any]:
    return {
        "status": status,
        "have": have,
        "universe": universe,
        "note": note,
    }


def load_tennis_manifest(cfg: RollerConfig | None = None) -> dict[str, Any] | None:
    cfg = cfg or RollerConfig()
    try:
        games = cfg.dataset_path("ATP", "2025-2026", "games")
    except (KeyError, FileNotFoundError):
        return None
    path = Path(games).parent / "dataset_version.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def tennis_observation_layers(cfg: RollerConfig | None = None) -> dict[str, Any]:
    """Warehouse-level layer matrix. Compile status is independent of this."""
    cfg = cfg or RollerConfig()
    manifest = load_tennis_manifest(cfg) or {}
    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    coverage = manifest.get("coverage") if isinstance(manifest.get("coverage"), dict) else {}

    games = _int(counts.get("games"))
    markets = _int(counts.get("markets"))
    settled = _int(coverage.get("markets_with_official_yes_no"))
    linked = _int(coverage.get("kalshi_games_linked_to_pbp"))
    pbp_matches = _int(counts.get("pbp_matches"))
    candle_tickers = _int(counts.get("candle_files_read"))
    last_trade_tickers = _int(counts.get("trade_tickers_read"))
    last_trade_bars = _int(counts.get("last_trade_bars"))
    candles_n = _int(counts.get("genuine_candles"))

    identity_ok = _dataset_exists(cfg, "games") and games > 0
    candles_ok = _dataset_exists(cfg, "kalshi_candles") and candles_n > 0
    last_ok = _dataset_exists(cfg, "kalshi_last_trade") and last_trade_bars > 0
    ticks_ok = _dataset_exists(cfg, "kalshi_trade_ticks")
    pbp_ok = _dataset_exists(cfg, "pbp") and pbp_matches > 0
    markets_ok = _dataset_exists(cfg, "kalshi_markets") and markets > 0

    layers = {
        "event_identity": _layer(
            AVAILABLE if identity_ok else MISSING,
            have=games,
            universe=games,
            note="Kalshi match-winner event identities. This is the tennis universe.",
        ),
        "kalshi_settlement": _layer(
            _coverage_status(settled, markets, present=markets_ok),
            have=settled,
            universe=markets,
            note="OFFICIAL W = Kalshi result yes/no only. scalar is not coerced.",
        ),
        "yes_bid_candles": _layer(
            _coverage_status(candle_tickers, markets, present=candles_ok),
            have=candle_tickers,
            universe=markets,
            note="Native Kalshi yes_bid/yes_ask. LAST TRADE ≠ YES BID. Missing minutes are absent.",
        ),
        "trade_ticks": _layer(
            AVAILABLE if ticks_ok else MISSING,
            have=None,
            universe=markets if markets else None,
            note="Canonical trade-tick dataset. Raw warehouse pages are not this layer.",
        ),
        "last_trade_1m": _layer(
            _coverage_status(last_trade_tickers, markets, present=last_ok),
            have=last_trade_tickers,
            universe=markets,
            note="Last chronological print per UTC minute. Never forward-filled. Not a bid.",
        ),
        "mcp_pbp": _layer(
            _coverage_status(linked, games, present=pbp_ok),
            have=linked,
            universe=games,
            note="Identity-linked MCP sequence only. Unlisted competitions stay unmatched.",
        ),
        "pit_point_state": _layer(
            NO_POINT_DATA,
            have=0,
            universe=games if games else None,
            note="SEQUENCE-ONLY PBP ≠ PIT PBP. MCP has no point timestamps.",
        ),
    }
    return {
        "layers": layers,
        "order": list(LAYER_ORDER),
        "summary": "identity-complete, market-acquisition incomplete, PBP sequence-complete where MCP exists, PIT unavailable by design"
        if identity_ok
        else "tennis warehouse identity missing",
        "notes": [
            "Layers are independent. One MISSING/PARTIAL/NO_POINT_DATA layer is not DATA_REQUIRED for the others.",
            "Missing layer ≠ N=0.",
            "CANDLE PATH ≠ FILL",
            "LAST TRADE ≠ YES BID",
            "SEQUENCE-ONLY PBP ≠ PIT PBP",
            "OFFICIAL W = KALSHI SETTLEMENT",
        ],
        "dataset_version": manifest.get("dataset_version"),
        "generated_at": manifest.get("generated_at"),
    }


def build_tennis_observability(
    cfg: RollerConfig | None = None,
    *,
    observation_basis: str | None = None,
) -> dict[str, Any]:
    out = tennis_observation_layers(cfg)
    out["observation_basis"] = observation_basis
    return out
