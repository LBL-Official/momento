"""Demo / production deploy adapter. Control command only. Does not submit orders."""

from __future__ import annotations

import os
from typing import Any

from roller.jump.bots.demo_host import observe_demo_unit, start_demo_unit
from roller.jump.errors import JumpError

DEMO_READY_ENV = "JUMP_BOT_DEMO_READY"
PROMOTE_READY_ENV = "JUMP_BOT_PROMOTE_READY"
DEMO_SSM_ENV = "JUMP_BOT_DEMO_SSM"


def demo_ready() -> bool:
    return os.environ.get(DEMO_READY_ENV) == "1"


def promote_ready() -> bool:
    return os.environ.get(PROMOTE_READY_ENV) == "1"


def ssm_forced() -> bool:
    return os.environ.get(DEMO_SSM_ENV) == "1"


def host_fetch_on() -> bool:
    raw = (os.environ.get("JUMP_BOT_ONE_HOST_FETCH") or "").strip().lower()
    return raw in {"1", "true", "yes", "ssm"}


def should_attempt_ssm() -> bool:
    if demo_ready() and not ssm_forced():
        return False
    return ssm_forced() or host_fetch_on()


def create_demo_runtime(bot: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("MOMENTO_KALSHI_ENV") == "production":
        raise JumpError("DEPLOY_REQUIRED", "create refuses a production environment tag")
    if not should_attempt_ssm():
        if demo_ready():
            runtime_id = f"demo-{bot['bot_id']}"
            return {
                "aws_runtime_id": runtime_id,
                "environment": "DEMO",
                "status": "CREATED",
                "kalshi_env": "demo",
                "live_enabled": False,
                "confirmation": None,
                "active": False,
            }
        raise JumpError(
            "DEPLOY_REQUIRED",
            "AWS session or demo credentials are not available; bot is not marked running",
        )
    started = start_demo_unit(bot)
    if not started.get("active"):
        raise JumpError(
            "DEPLOY_REQUIRED",
            str(started.get("reason") or "demo unit did not become active"),
        )
    return {
        "aws_runtime_id": started.get("aws_runtime_id") or f"momento-demo@{bot['bot_id']}.service",
        "environment": "DEMO",
        "status": "RUNNING_DEMO",
        "kalshi_env": "demo",
        "live_enabled": False,
        "confirmation": None,
        "active": True,
        "unit": started.get("unit"),
        "state_dir": started.get("state_dir"),
    }


def observe_demo(bot: dict[str, Any]) -> dict[str, Any]:
    bot_id = str(bot.get("bot_id") or "")
    if demo_ready() and not ssm_forced():
        return {
            "status": bot.get("status") or "CREATED",
            "environment": "DEMO",
            "live_armed_confirmed": False,
            "observed": False,
            "aws_runtime_id": bot.get("aws_runtime_id"),
        }
    if not bot.get("aws_runtime_id") and (bot.get("deploy") or {}).get("status") != "RUNNING_DEMO":
        return {
            "status": bot.get("status") or "CREATED",
            "environment": "DEMO",
            "live_armed_confirmed": False,
            "observed": False,
        }
    try:
        seen = observe_demo_unit(bot_id)
    except JumpError:
        return {
            "status": bot.get("status") or "CREATED",
            "environment": "DEMO",
            "live_armed_confirmed": False,
            "observed": False,
        }
    if seen.get("active"):
        return {
            "status": "RUNNING_DEMO",
            "environment": "DEMO",
            "live_armed_confirmed": False,
            "observed": True,
            "aws_runtime_id": seen.get("aws_runtime_id") or bot.get("aws_runtime_id"),
        }
    return {
        "status": bot.get("status") or "CREATED",
        "environment": "DEMO",
        "live_armed_confirmed": False,
        "observed": False,
        "aws_runtime_id": bot.get("aws_runtime_id"),
        "detail": seen.get("reason") or "demo unit not active",
    }


def promote_runtime(bot: dict[str, Any]) -> dict[str, Any]:
    if not promote_ready():
        raise JumpError(
            "DEPLOY_REQUIRED",
            "host did not confirm production switch; environment stays DEMO",
        )
    return {
        "aws_runtime_id": bot.get("aws_runtime_id") or f"live-{bot['bot_id']}",
        "environment": "PRODUCTION",
        "status": "PRODUCTION",
        "kalshi_env": "production",
        "live_enabled": True,
        "live_armed_confirmed": True,
        "second_live_engine": False,
        "note": "does not start a second momento-live.service",
    }
