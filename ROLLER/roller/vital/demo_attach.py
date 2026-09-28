"""Autonomous DEMO attach for Jump ITI bots.

On create, Vital observes the Kalshi Demo book, inspects AWS, then starts
momento-demo@{bot} with an ITI toml (not factory 80–83).
RUNNING_DEMO only after systemctl is-active. Missing secret is DEPLOY_REQUIRED.
Does not start momento-live. HTTP 200 is not RUNNING. Candle path is not a fill.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from roller.vital.mlb_001.kalshi_observe import kalshi_observe_skipped, observe_kalshi
from roller.vital.models import utc_now
from roller.vital.store import append_event, bot_dir, save_bot, write_json
from roller.vital.versions import BOT_ID

ACTIVATION_ATTACHED = "DEMO_ATTACHED"
ACTIVATION_UNAVAILABLE = "DEMO_ATTACH_UNAVAILABLE"
ACTIVATION_RUNNING = "RUNNING_DEMO"
ACTIVATION_DEPLOY = "DEPLOY_REQUIRED"


def attach_io_skipped() -> bool:
    return kalshi_observe_skipped()


def _int_or_none(raw: Any) -> int | None:
    try:
        if raw is None or raw == "":
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _demo_book_from_disk() -> dict[str, Any]:
    try:
        from roller.jump.catalog.store import load_kalshi_book

        disk = load_kalshi_book()
        packed = (disk or {}).get("books") if isinstance(disk, dict) else {}
        if isinstance(packed, dict) and isinstance(packed.get("DEMO"), dict):
            return packed["DEMO"]
    except Exception:
        return {}
    return {}


def _observe_demo_book() -> dict[str, Any]:
    raw = observe_kalshi(environment="DEMO")
    books = raw.get("books") if isinstance(raw.get("books"), dict) else {}
    demo = books.get("DEMO") if isinstance(books.get("DEMO"), dict) else {}
    persisted = _demo_book_from_disk()
    ok = bool(raw.get("ok") or persisted.get("ok"))
    return {
        "status": "CONFIRMED" if ok else "OBSERVATION_UNAVAILABLE",
        "ok": ok,
        "read_only": True,
        "submits": False,
        "environment": "DEMO",
        "observed_at": persisted.get("observed_at"),
        "balance_cents": _int_or_none(persisted.get("current_cents") or demo.get("current_cents")),
        "fill_n": _int_or_none(demo.get("fill_n") if demo.get("fill_n") is not None else persisted.get("fill_n")),
        "position_n": _int_or_none(
            demo.get("position_n") if demo.get("position_n") is not None else persisted.get("position_n")
        ),
        "detail": None if ok else (raw.get("detail") or demo.get("detail") or "Kalshi Demo book unread"),
        "http_200_not_running": True,
    }


def inspect_aws_demo() -> dict[str, Any]:
    """Read-only AWS session + demo secret presence. Does not start a unit."""
    base = {
        "read_only": True,
        "unit_started": False,
        "unit": None,
        "factory_toml_refused": True,
        "momento_live_untouched": True,
        "http_200_not_running": True,
    }
    if attach_io_skipped():
        return {
            **base,
            "status": "OBSERVATION_UNAVAILABLE",
            "session": "OBSERVATION_UNAVAILABLE",
            "demo_secret": "OBSERVATION_UNAVAILABLE",
            "detail": "AWS inspect skipped",
        }
    from roller.jump.catalog.versions import DEMO_SECRET_ID
    from roller.vital.aws import instance_id, region

    host_region = region()
    host_instance = instance_id()

    def _aws(args: list[str], timeout: int = 12) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                ["aws", *args, "--region", host_region, "--output", "json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "detail": str(exc)[:200]}
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "aws unread").strip()[:200]
            return {"ok": False, "detail": err}
        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return {"ok": False, "detail": "aws output unreadable"}
        return {"ok": True, "payload": payload if isinstance(payload, dict) else {}}

    sts = _aws(["sts", "get-caller-identity"])
    if not sts.get("ok"):
        return {
            **base,
            "status": "OBSERVATION_UNAVAILABLE",
            "session": "OBSERVATION_UNAVAILABLE",
            "demo_secret": "OBSERVATION_UNAVAILABLE",
            "instance_id": host_instance,
            "region": host_region,
            "detail": sts.get("detail") or "AWS session unread",
        }
    secret = _aws(["secretsmanager", "describe-secret", "--secret-id", DEMO_SECRET_ID])
    secret_ok = bool(secret.get("ok"))
    secret_payload = secret.get("payload") if isinstance(secret.get("payload"), dict) else {}
    return {
        **base,
        "status": "CONFIRMED",
        "session": "CONFIRMED",
        "demo_secret": "CONFIRMED" if secret_ok else "OBSERVATION_UNAVAILABLE",
        "demo_secret_name": secret_payload.get("Name") if secret_ok else None,
        "account": (sts.get("payload") or {}).get("Account"),
        "instance_id": host_instance,
        "region": host_region,
        "detail": None if secret_ok else (secret.get("detail") or "demo secret unread"),
    }


def _mark_engine(bot: dict[str, Any], *, worker: str) -> dict[str, Any]:
    engine = dict(bot.get("engine") or {}) if isinstance(bot.get("engine"), dict) else {}
    impl = dict(engine.get("implementation") or {}) if isinstance(engine.get("implementation"), dict) else {}
    impl["spec"] = impl.get("spec") or "IMPLEMENTED"
    impl["worker"] = worker
    impl["submit"] = False
    impl["not_mlb_factory"] = True
    impl["not_80_81"] = True
    engine["implementation"] = impl
    bot["engine"] = engine
    return engine


def _activation(kalshi: dict[str, Any], aws: dict[str, Any], unit: dict[str, Any]) -> str:
    if unit.get("active"):
        return ACTIVATION_RUNNING
    if unit.get("attempted"):
        return ACTIVATION_DEPLOY
    kalshi_ok = bool(kalshi.get("ok") or kalshi.get("status") == "CONFIRMED")
    aws_ok = str(aws.get("session") or aws.get("status") or "") == "CONFIRMED"
    return ACTIVATION_ATTACHED if kalshi_ok or aws_ok else ACTIVATION_UNAVAILABLE


def _deploy(aws: dict[str, Any], activation: str, unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "RUNNING_DEMO" if unit.get("active") else "DEPLOY_REQUIRED",
        "environment": "DEMO",
        "kalshi_env": "demo",
        "unit_started": bool(unit.get("active")),
        "unit": unit.get("unit"),
        "factory_toml_refused": True,
        "live_enabled": False,
        "activation": activation,
        "message": unit.get("reason") if not unit.get("active") else None,
        "state_dir": unit.get("state_dir"),
    }


def start_iti_unit(bot: dict[str, Any]) -> dict[str, Any]:
    """Start the isolated ITI demo unit. Never factory start_demo_unit. Never momento-live."""
    from roller.jump.bots.demo_host import start_iti_demo_unit

    try:
        started = start_iti_demo_unit(bot)
    except Exception as exc:
        return {
            "attempted": True,
            "active": False,
            "unit_started": False,
            "aws_runtime_id": None,
            "reason": str(exc)[:240],
            "factory_path_used": False,
        }
    return {
        "attempted": True,
        "active": bool(started.get("active")),
        "unit_started": bool(started.get("active")),
        "ok": bool(started.get("ok")),
        "secret_missing": bool(started.get("secret_missing")),
        "aws_runtime_id": started.get("aws_runtime_id") if started.get("active") else None,
        "unit": started.get("unit") if started.get("active") else None,
        "state_dir": started.get("state_dir"),
        "reason": started.get("reason"),
        "factory_path_used": False,
    }


def _sync_jump(vital: dict[str, Any], *, jump_root: Path | None, jump_bot: dict[str, Any] | None) -> None:
    jump_id = str(vital.get("jump_bot_id") or "")
    if not jump_id:
        return
    from roller.jump.bots.store import load_bot as jump_load
    from roller.jump.bots.store import save_bot as jump_save

    rec = jump_bot if isinstance(jump_bot, dict) and str(jump_bot.get("bot_id") or "") == jump_id else None
    if rec is None:
        try:
            rec = jump_load(jump_id, root=jump_root)
        except Exception:
            return
    rec["activation"] = vital.get("activation")
    rec["vital_bot_id"] = vital.get("bot_id")
    rec["deploy"] = vital.get("deploy")
    rec["attach"] = vital.get("attach")
    rec["aws_runtime_id"] = vital.get("aws_runtime_id")
    rec["status"] = vital.get("status") or rec.get("status") or "CREATED"
    jump_save(rec, root=jump_root)


def _bot_sport(bot: dict[str, Any]) -> str:
    engine = bot.get("engine") if isinstance(bot.get("engine"), dict) else {}
    return str(bot.get("sport") or engine.get("sport") or "").strip().lower()


def fund_mlb_demo_shard_on_attach(bot: dict[str, Any]) -> dict[str, Any]:
    """Demo-only intra-transfer onto Predictions shard 3. Never venue create-order."""
    if _bot_sport(bot) != "mlb":
        return {
            "ok": True,
            "skipped": True,
            "transfer": False,
            "not_create_v2": True,
            "detail": "not MLB",
        }
    if attach_io_skipped():
        return {
            "ok": False,
            "skipped": True,
            "transfer": False,
            "not_create_v2": True,
            "mlb_shard_cents": None,
            "detail": "Demo shard fund skipped",
        }
    try:
        from roller.vital.demo_shard import fund_demo_mlb_shard

        return fund_demo_mlb_shard(execute=True)
    except Exception as exc:
        return {
            "ok": False,
            "execute_error": True,
            "transfer": False,
            "not_create_v2": True,
            "detail": str(exc)[:200],
        }


def attach_demo(
    bot: dict[str, Any],
    *,
    vital_root: Path | None = None,
    jump_root: Path | None = None,
    jump_bot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Observe Kalshi Demo + inspect AWS + start ITI demo unit. HTTP 200 is not RUNNING."""
    if str(bot.get("bot_id") or "") == BOT_ID or bot.get("kind") == "grandfathered":
        return bot
    kalshi = _observe_demo_book()
    aws = inspect_aws_demo()
    shard = fund_mlb_demo_shard_on_attach(bot)
    unit = start_iti_unit(bot)
    activation = _activation(kalshi, aws, unit)
    worker = str(unit.get("unit") or "OPERATION_REQUIRED") if unit.get("active") else "OPERATION_REQUIRED"
    engine = _mark_engine(bot, worker=worker)
    attach = {
        "attempted_at": utc_now(),
        "autonomous": True,
        "environment": "DEMO",
        "kalshi_demo": kalshi,
        "aws": aws,
        "unit": unit,
        "worker": worker,
        "submit": False,
        "unit_started": bool(unit.get("active")),
        "not_mlb_factory": True,
        "not_80_81": True,
        "http_200_not_running": True,
        "factory_path_used": False,
        "mlb_shard": shard,
        "not_create_v2": True,
    }
    bot["activation"] = activation
    bot["status"] = "RUNNING_DEMO" if unit.get("active") else "CREATED"
    bot["environment"] = "DEMO"
    bot["live_armed_confirmed"] = False
    bot["aws_runtime_id"] = unit.get("aws_runtime_id")
    bot["attach"] = attach
    bot["deploy"] = _deploy(aws, activation, unit)
    bot["updated_at"] = utc_now()
    save_bot(bot, root=vital_root)
    write_json(bot_dir(str(bot["bot_id"]), root=vital_root) / "source" / "attach.json", attach)
    append_event(
        str(bot["bot_id"]),
        {
            "kind": "demo_attach",
            "activation": activation,
            "kalshi": kalshi.get("status"),
            "aws": aws.get("status"),
            "unit_started": bool(unit.get("active")),
            "worker": worker,
        },
        root=vital_root,
    )
    _sync_jump(bot, jump_root=jump_root, jump_bot=jump_bot)
    bot["_attach_engine"] = engine
    return bot


def attach_demo_if_needed(
    bot: dict[str, Any],
    *,
    vital_root: Path | None = None,
    jump_root: Path | None = None,
    jump_bot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(bot.get("attach"), dict) and bot.get("activation") in {
        ACTIVATION_ATTACHED,
        ACTIVATION_UNAVAILABLE,
        ACTIVATION_RUNNING,
        ACTIVATION_DEPLOY,
    }:
        return bot
    return attach_demo(bot, vital_root=vital_root, jump_root=jump_root, jump_bot=jump_bot)


def update_kalshi_attach(
    bot: dict[str, Any],
    observed: dict[str, Any] | None = None,
    *,
    vital_root: Path | None = None,
    jump_root: Path | None = None,
) -> dict[str, Any]:
    """Write a just-pulled DEMO book onto an existing attach. Does not start a unit."""
    if str(bot.get("bot_id") or "") == BOT_ID or bot.get("kind") == "grandfathered":
        return bot
    kalshi = _observe_demo_book() if observed is None else None
    if kalshi is None:
        books = observed.get("books") if isinstance((observed or {}).get("books"), dict) else {}
        demo = books.get("DEMO") if isinstance(books.get("DEMO"), dict) else {}
        ok = bool((observed or {}).get("ok") or demo.get("ok"))
        kalshi = {
            "status": "CONFIRMED" if ok else "OBSERVATION_UNAVAILABLE",
            "ok": ok,
            "read_only": True,
            "submits": False,
            "environment": "DEMO",
            "fill_n": demo.get("fill_n"),
            "position_n": demo.get("position_n"),
            "detail": None if ok else ((observed or {}).get("detail") or demo.get("detail")),
            "http_200_not_running": True,
        }
        disk = _demo_book_from_disk()
        if disk.get("ok"):
            kalshi["balance_cents"] = _int_or_none(disk.get("current_cents"))
            kalshi["observed_at"] = disk.get("observed_at")
    attach = dict(bot.get("attach") or {}) if isinstance(bot.get("attach"), dict) else {}
    aws = attach.get("aws") if isinstance(attach.get("aws"), dict) else {
        "status": "OBSERVATION_UNAVAILABLE",
        "session": "OBSERVATION_UNAVAILABLE",
        "unit_started": False,
        "factory_toml_refused": True,
    }
    unit = attach.get("unit") if isinstance(attach.get("unit"), dict) else {
        "attempted": False,
        "active": False,
        "unit_started": False,
        "aws_runtime_id": bot.get("aws_runtime_id"),
    }
    activation = _activation(kalshi, aws, unit)
    worker = str(unit.get("unit") or bot.get("aws_runtime_id") or "OPERATION_REQUIRED") if unit.get("active") else "OPERATION_REQUIRED"
    attach.update(
        {
            "attempted_at": utc_now(),
            "autonomous": True,
            "environment": "DEMO",
            "kalshi_demo": kalshi,
            "aws": aws,
            "unit": unit,
            "worker": worker,
            "submit": False,
            "unit_started": bool(unit.get("active")),
            "http_200_not_running": True,
        }
    )
    bot["attach"] = attach
    bot["activation"] = activation
    bot["deploy"] = _deploy(aws, activation, unit)
    bot["status"] = "RUNNING_DEMO" if unit.get("active") else (bot.get("status") or "CREATED")
    if not unit.get("active"):
        bot["aws_runtime_id"] = None
    bot["updated_at"] = utc_now()
    save_bot(bot, root=vital_root)
    write_json(bot_dir(str(bot["bot_id"]), root=vital_root) / "source" / "attach.json", attach)
    _sync_jump(bot, jump_root=jump_root, jump_bot=None)
    return bot


def attach_result(bot: dict[str, Any]) -> dict[str, Any]:
    engine = bot.get("engine") if isinstance(bot.get("engine"), dict) else bot.get("_attach_engine") or {}
    return {
        "bot_id": bot.get("bot_id"),
        "jump_bot_id": bot.get("jump_bot_id"),
        "environment": "DEMO",
        "desired_environment": bot.get("desired_environment") or "DEMO",
        "activation": bot.get("activation"),
        "status": bot.get("status") or "CREATED",
        "engine": engine,
        "attach": bot.get("attach"),
        "deploy": bot.get("deploy"),
        "aws_runtime_id": bot.get("aws_runtime_id"),
        "http_200_not_running": True,
        "live_armed_confirmed": False,
        "detail": (
            "Vital attached DEMO on create. Kalshi Demo book observe is separate from the "
            "momento-demo unit. RUNNING_DEMO only after is-active. Browser does not submit."
        ),
    }
