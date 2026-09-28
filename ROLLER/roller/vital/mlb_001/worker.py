"""MLB 001 worker contract. Observe momento-live.service. Do not spawn a submitter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.vital.bots import get_bot
from roller.vital.honesty import observation_unavailable
from roller.vital.mlb_001.identity import (
    BINARY_NAME,
    BOT_ID,
    ENGINE_POINTER,
    HOST_BINARY,
    HOST_CONFIG,
    HOST_RUNTIME,
    HOST_STATE_DIR,
    SECRET_FETCH_POINTER,
    SERVICE_NAME,
    UNIT_POINTER,
)
from roller.vital.observe import observe_bot


def worker_view(bot_id: str, *, root: Path | None = None) -> dict[str, Any]:
    get_bot(bot_id, root=root)
    observed = observe_bot(bot_id, root=root, persist=False)
    runtime = observed["runtime"]
    inspect = observed.get("inspect") or {}
    return {
        "bot_id": BOT_ID,
        "phase": 4,
        "layer": "worker",
        "kind": "existing_host_unit",
        "independent_of_vital": True,
        "vital_ui_required": False,
        "vital_api_required": False,
        "jump_required": False,
        "vital_submits": False,
        "second_worker": False,
        "moved": False,
        "if_vital_down": "continues",
        "if_vital_ui_down": "continues",
        "unit": SERVICE_NAME,
        "unit_pointer": UNIT_POINTER,
        "binary": HOST_BINARY,
        "binary_name": BINARY_NAME,
        "cwd": "/var/lib/momento",
        "host_config": HOST_CONFIG,
        "host_state_dir": HOST_STATE_DIR,
        "host_runtime": HOST_RUNTIME,
        "repo_pointer": ENGINE_POINTER,
        "secret_fetch_pointer": SECRET_FETCH_POINTER,
        "vital_role": "observe_and_fail_closed_control",
        "submitter": HOST_BINARY,
        "observed": {
            "ok": inspect.get("ok"),
            "source": inspect.get("source"),
            "reason": inspect.get("reason"),
            "lifecycle": runtime.get("lifecycle"),
            "health": runtime.get("health"),
            "host": runtime.get("host") or observation_unavailable("host unread"),
            "service": runtime.get("service") or observation_unavailable("service unread"),
            "process": runtime.get("process") or observation_unavailable("process unread"),
        },
        "http_200_not_running": True,
        "note": (
            "Canonical runtime is systemd momento-live.service. "
            "Vital does not create a Python or Jump worker that submits orders."
        ),
    }
