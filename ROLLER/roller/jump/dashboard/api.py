"""Jump C HTTP handlers. Dashboard reads Vital. Browser is not the engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.config import RollerConfig
from roller.jump.bots.pipeline import list_control_plane
from roller.jump.bots.status import apply_observation
from roller.jump.bots.versions import BOT_ONE_ID
from roller.jump.dashboard.heartbeat import confirmed, field_metric, unavailable
from roller.jump.dashboard.rollup import rollup_tracks
from roller.jump.dashboard.store import list_logs, load_notes
from roller.jump.dashboard.tracks import activity_for_track, filter_tracks, track_from_bot
from roller.jump.catalog.analysis import metric_bundle
from roller.jump.catalog.store import load_analysis, load_origin
from roller.jump.catalog.versions import CATALOG_VERSION
from roller.jump.dashboard.versions import CAVEATS, DASHBOARD_VERSION, HONESTY
from roller.jump.vital_client import (
    jump_heartbeat_from_vital,
    vital_bankroll,
    vital_id_for_jump_bot,
    vital_observe,
)
from roller.vital.versions import BOT_ID


def _issues(tracks: list[dict[str, Any]], heartbeat: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not heartbeat.get("observed"):
        issues.append(
            {
                "code": "OBSERVATION_UNAVAILABLE",
                "message": heartbeat.get("detail") or "Vital host unread",
            }
        )
    kill = (heartbeat.get("fields") or {}).get("kill_switch")
    if kill is True:
        issues.append({"code": "KILL_SWITCH", "message": "kill switch confirmed on Vital observe"})
    for row in tracks:
        status = str(row.get("bot_status") or "")
        if status == "OBSERVATION_UNAVAILABLE":
            issues.append(
                {
                    "code": "OBSERVATION_UNAVAILABLE",
                    "bot_id": row.get("bot_id"),
                    "message": (row.get("observation") or {}).get("detail") or "observation unavailable",
                }
            )
        if row.get("deploy_status") == "DEPLOY_REQUIRED":
            issues.append(
                {
                    "code": "DEPLOY_REQUIRED",
                    "bot_id": row.get("bot_id"),
                    "message": "demo deploy not confirmed",
                }
            )
    return issues


def _metric_has_fills(metrics: dict[str, Any]) -> bool:
    trades = metrics.get("trade_n") or {}
    last = metrics.get("last_trade") or {}
    try:
        trade_n = int(trades.get("value")) if trades.get("status") == "CONFIRMED" and trades.get("value") is not None else 0
    except (TypeError, ValueError):
        trade_n = 0
    return trade_n > 0 or (last.get("status") == "CONFIRMED" and last.get("value") not in {None, ""})


def _vital_metric(raw: Any, *, missing: str = "OBSERVATION_UNAVAILABLE") -> dict[str, Any]:
    if not isinstance(raw, dict):
        return unavailable(missing)
    if raw.get("status") == "CONFIRMED" and raw.get("value") is not None:
        return confirmed(raw.get("value"))
    status = str(raw.get("status") or missing)
    return {"value": None, "status": status}


def _int_confirmed(raw: Any) -> int | None:
    if not isinstance(raw, dict) or raw.get("status") != "CONFIRMED":
        return None
    try:
        return int(raw["value"]) if raw.get("value") is not None else None
    except (TypeError, ValueError):
        return None


def _book_pack(account: dict[str, Any] | None, *, environment: str) -> dict[str, Any]:
    row = account if isinstance(account, dict) else {}
    shard = _vital_metric(row.get("mlb_shard_cents"))
    top = _vital_metric(row.get("top_level_cents"))
    breakdown = row.get("balance_breakdown")
    if not isinstance(breakdown, list):
        breakdown = []
    return {
        "environment": environment,
        "top_level_cents": top,
        "sports_shard_cents": shard,
        "mlb_shard_cents": shard,
        "catch_all_shard_cents": _vital_metric(row.get("catch_all_shard_cents")),
        "exchange_index": _vital_metric(row.get("exchange_index")),
        "origin_pnl_cents": _vital_metric(row.get("origin_pnl_cents")),
        "day_delta_cents": _vital_metric(row.get("day_delta_cents")),
        "week_delta_cents": _vital_metric(row.get("week_delta_cents")),
        "observed_at": _vital_metric(row.get("observed_at")),
        "source": _vital_metric(row.get("source")),
        "balance_breakdown": breakdown,
        "shard_label": "sports shard 3 (baseball / basketball / tennis)",
    }


def _origin_pnl(account: dict[str, Any] | None, *, missing: str = "OBSERVATION_UNAVAILABLE") -> dict[str, Any]:
    row = account if isinstance(account, dict) else {}
    packed = row.get("origin_pnl_cents")
    if isinstance(packed, dict) and packed.get("status") == "CONFIRMED":
        return confirmed(packed.get("value"))
    shard = _int_confirmed(row.get("mlb_shard_cents"))
    factory = _int_confirmed(row.get("factory_bankroll_cents"))
    if shard is None or factory is None:
        return unavailable(missing)
    return confirmed(shard - factory)


def _apply_vital_book(row: dict[str, Any], book: dict[str, Any], *, production: bool) -> None:
    actual = dict(row.get("actual") or {})
    shard = book.get("sports_shard_cents") or unavailable("OBSERVATION_UNAVAILABLE")
    top = book.get("top_level_cents") or unavailable("OBSERVATION_UNAVAILABLE")
    if shard.get("status") == "CONFIRMED":
        actual["bankroll"] = shard
    elif production and top.get("status") == "CONFIRMED" and actual.get("bankroll", {}).get("status") != "CONFIRMED":
        actual["bankroll"] = top
    if not production:
        if shard.get("status") == "CONFIRMED":
            actual["bankroll"] = shard
        actual["top_level_cents"] = top
        actual["sports_shard_cents"] = shard
    origin = book.get("origin_from_factory") or book.get("origin_pnl_cents")
    if isinstance(origin, dict) and origin.get("status") == "CONFIRMED":
        actual["origin_pnl"] = origin
        actual["pnl"] = origin
    if book.get("day_delta_cents", {}).get("status") == "CONFIRMED":
        actual["day_pnl"] = book["day_delta_cents"]
    if book.get("week_delta_cents", {}).get("status") == "CONFIRMED":
        actual["week_pnl"] = book["week_delta_cents"]
    actual["sharpe"] = unavailable()
    actual["day_sharpe"] = unavailable()
    actual["week_sharpe"] = unavailable()
    row["actual"] = actual


def _overlay_catalog_fills_only(row: dict[str, Any], bucket: dict[str, Any]) -> None:
    missing = "OBSERVATION_UNAVAILABLE" if str(row.get("environment") or "").upper() == "PRODUCTION" else "UNAVAILABLE"
    packed = metric_bundle(bucket, missing=missing)
    actual = dict(row.get("actual") or {})
    actual["trades"] = packed.get("trade_n") or unavailable(missing)
    actual["weekly_trades"] = packed.get("weekly_n") or unavailable(missing)
    actual["last_trade"] = packed.get("last_trade") or unavailable("UNAVAILABLE")
    actual["win_loss"] = packed.get("win_loss") or unavailable(missing)
    actual["realized_win_rate"] = packed.get("realized_win_rate") or unavailable(missing)
    row["actual"] = actual
    row["activity"] = activity_for_track(row, has_fills=_metric_has_fills(packed))


def handle_dashboard(
    *,
    root=None,
    cfg: RollerConfig | None = None,
    by: str = "all",
    value: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    plane = list_control_plane(root=root, cfg=cfg, observe=False)
    try:
        bankroll = vital_bankroll(now=now)
    except Exception:
        bankroll = {}
    production_account = bankroll.get("account") if isinstance(bankroll.get("account"), dict) else {}
    demo_account = bankroll.get("demo_account") if isinstance(bankroll.get("demo_account"), dict) else {}
    production_book = _book_pack(production_account, environment="PRODUCTION")
    production_book["origin_from_factory"] = _origin_pnl(production_account)
    demo_book = _book_pack(demo_account, environment="DEMO")
    if isinstance(demo_account.get("origin_pnl_cents"), dict):
        demo_book["origin_pnl_cents"] = _vital_metric(demo_account.get("origin_pnl_cents"))

    tracks: list[dict[str, Any]] = []
    bot_one_hb: dict[str, Any] = {
        "observed": False,
        "fields": {},
        "status": "OBSERVATION_UNAVAILABLE",
        "source": "vital",
    }
    for bot in plane.get("bots") or []:
        apply_observation(bot)
        vital_id = vital_id_for_jump_bot(bot)
        try:
            view = vital_observe(vital_id, now=now)
            runtime = view.get("runtime") if isinstance(view.get("runtime"), dict) else {}
            hb = jump_heartbeat_from_vital(runtime, bot_id=vital_id, now=now)
            kalshi = view.get("kalshi") if isinstance(view.get("kalshi"), dict) else {}
        except Exception:
            runtime = {}
            hb = {"observed": False, "fields": {}, "status": "OBSERVATION_UNAVAILABLE", "source": "vital"}
            kalshi = {}
        if vital_id == BOT_ID:
            bot_one_hb = hb
        row = track_from_bot(bot, hb)
        env = str(row.get("environment") or "").upper()
        if vital_id == BOT_ID or env == "PRODUCTION":
            _apply_vital_book(row, production_book, production=True)
            positions = kalshi.get("positions")
            if isinstance(positions, dict) and positions.get("status") == "CONFIRMED":
                actual = dict(row.get("actual") or {})
                actual["positions"] = positions
                actual["open_mlb_positions"] = positions
                row["actual"] = actual
        else:
            _apply_vital_book(row, demo_book, production=False)
        tracks.append(row)

    catalog_analysis = load_analysis()
    if not catalog_analysis:
        from roller.jump.catalog.analysis import analyze
        from roller.jump.catalog.store import load_trades

        catalog_analysis = analyze(load_trades(), now=now or datetime.now(timezone.utc))
    if catalog_analysis:
        for row in tracks:
            bot_id = str(row.get("bot_id") or "")
            bucket = (catalog_analysis.get("by_bot") or {}).get(bot_id)
            if not bucket:
                continue
            if int(bucket.get("trade_n") or 0) <= 0 and not bucket.get("last_trade"):
                continue
            _overlay_catalog_fills_only(row, bucket)

    visible = filter_tracks(tracks, by=by, value=value)
    host_bankroll = field_metric(bot_one_hb.get("fields") or {}, "bankroll_cents", missing="OBSERVATION_UNAVAILABLE")
    header_bankroll = production_book["sports_shard_cents"]
    if header_bankroll.get("status") != "CONFIRMED":
        header_bankroll = host_bankroll
    header_day = production_book["day_delta_cents"]
    header_week = production_book["week_delta_cents"]
    if header_day.get("status") != "CONFIRMED":
        header_day = field_metric(bot_one_hb.get("fields") or {}, "day_pnl_cents", missing="OBSERVATION_UNAVAILABLE")
    if header_week.get("status") != "CONFIRMED":
        header_week = field_metric(bot_one_hb.get("fields") or {}, "week_pnl_cents", missing="OBSERVATION_UNAVAILABLE")
    header = {
        "bankroll": header_bankroll,
        "day_pnl": header_day,
        "week_pnl": header_week,
        "origin_pnl": production_book.get("origin_from_factory") or unavailable("OBSERVATION_UNAVAILABLE"),
        "day_sharpe": unavailable(),
        "week_sharpe": unavailable(),
        "factory": plane.get("factory"),
        "kalshi_observed_at": production_book.get("observed_at") or unavailable("OBSERVATION_UNAVAILABLE"),
        "books": {
            "PRODUCTION": production_book,
            "DEMO": demo_book,
        },
        "source": "vital",
    }
    return {
        "status": "ok",
        "product": "Jump C",
        "dashboard_version": DASHBOARD_VERSION,
        "bot_one_id": BOT_ONE_ID,
        "header": header,
        "tracks": visible,
        "track_n": len(visible),
        "rollup": rollup_tracks(visible),
        "issues": _issues(tracks, bot_one_hb),
        "notes": load_notes(),
        "filter": {"by": by or "all", "value": value or ""},
        "heartbeat": {
            "observed": bool(bot_one_hb.get("observed")),
            "status": bot_one_hb.get("status"),
            "detail": bot_one_hb.get("detail"),
            "source": "vital",
        },
        "catalog": {
            "version": CATALOG_VERSION,
            "origin": load_origin(),
            "analysis": catalog_analysis,
            "bankroll": None,
            "kalshi": None,
            "fills_only": True,
        },
        "honesty": dict(HONESTY),
        "caveats": list(CAVEATS),
    }


def handle_logs(*, root=None) -> dict[str, Any]:
    return {
        "status": "ok",
        "events": list_logs(bots_root=root),
        "source": "jump_b_events_jsonl",
        "honesty": {"trading_log": False, "control_events_only": True},
    }
