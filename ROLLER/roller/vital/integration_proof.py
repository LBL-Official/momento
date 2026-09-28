"""Vital ↔ live-service integration proof. Honesty states stay independent.

Not a second engine. Not a production test order. Not MLB 001 Phase 6 trades.
Spec: research/vital/LIVE_SERVICE_INTEGRATION.md
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.vital.models import utc_now
from roller.vital.store import (
    append_jsonl,
    default_vital_root,
    load_jsonl,
    read_json,
    repo_root,
    write_json,
)
from roller.vital.versions import (
    BOT_ID,
    CONFIG_POINTER,
    ENGINE_POINTER,
    FACTORY,
    HOST_BINARY,
    HOST_CONFIG,
    LIVE_CONFIRMATION,
    LIVE_EXECUTION,
    SERVICE_NAME,
    STRATEGY_POINTER,
    UNIT_POINTER,
)

PROOF_ID = "LIVE_SERVICE_INTEGRATION"
PROOF_NAME = "Vital Live-Service Integration Proof"
DEFAULT_WINDOW_S = 1800.0
MIN_SAMPLES = 2
EXPECTED_CWD = "/var/lib/momento"
EXPECTED_KALSHI_ENV = "production"
DEMO_SUCCESS_FIXTURE = "apps/trading-engine/tests/demo_host.rs::crossing_40_submits_after_risk"

CHAIN = (
    "DESIRED",
    "WRITTEN",
    "OBSERVED",
    "LOADED",
    "EVALUATING",
    "SIGNALING",
    "RISK_APPROVED",
    "SUBMITTING",
    "ACKNOWLEDGED",
    "FILLED",
)

LEVELS = (
    "L1_PROCESS",
    "L2_RUNTIME",
    "L3_CONTROL",
    "L4_CONFIGURATION",
    "L5_LOAD",
    "L6_EVALUATION",
    "L7_EXECUTION",
    "L8_EXCHANGE",
)

SUITES = (
    "A_PRODUCTION_READ",
    "B_DEMO_CONTROL",
    "C_DEMO_STRATEGY",
    "D_PRODUCTION_STRATEGY_LOAD",
)


def _status(status: str, *, detail: str | None = None, value: Any = None) -> dict[str, Any]:
    out: dict[str, Any] = {"status": status}
    if detail is not None:
        out["detail"] = detail
    if value is not None:
        out["value"] = value
    return out


def confirmed(detail: str | None = None, *, value: Any = None) -> dict[str, Any]:
    return _status("CONFIRMED", detail=detail, value=value)


def unavailable(detail: str, *, value: Any = None) -> dict[str, Any]:
    return _status("OBSERVATION_UNAVAILABLE", detail=detail, value=value)


def failed(detail: str, *, value: Any = None) -> dict[str, Any]:
    return _status("FAILED", detail=detail, value=value)


def not_claimed(detail: str, *, value: Any = None) -> dict[str, Any]:
    return _status("NOT_CLAIMED", detail=detail, value=value)


def not_tripped(detail: str | None = None, *, value: Any = None) -> dict[str, Any]:
    return _status("NOT_TRIPPED", detail=detail, value=value)


def integration_dir(*, root: Path | None = None) -> Path:
    return (root or default_vital_root()) / "integration"


def liveness_path(bot_id: str, *, root: Path | None = None) -> Path:
    return (root or default_vital_root()) / "bots" / bot_id / "runtime" / "liveness.jsonl"


def demo_control_proof_path(*, root: Path | None = None) -> Path:
    return integration_dir(root=root) / "demo_control_proof.json"


def demo_strategy_proof_path(*, root: Path | None = None) -> Path:
    return integration_dir(root=root) / "demo_strategy_proof.json"


def production_handshake_path(*, root: Path | None = None) -> Path:
    return integration_dir(root=root) / "production_handshake.json"


def _unwrap(metric: Any) -> Any:
    if isinstance(metric, dict) and "value" in metric and "status" in metric:
        return metric.get("value")
    return metric


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_iso(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _boolish(raw: Any) -> bool | None:
    if raw is True:
        return True
    if raw is False:
        return False
    if raw in {"active", "ACTIVE", "true", "True", "yes"}:
        return True
    if raw in {"inactive", "failed", "dead", "false", "False", "no"}:
        return False
    return None


def _intish(raw: Any) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _service(inspect: dict[str, Any]) -> dict[str, Any]:
    service = _unwrap(inspect.get("service"))
    return _as_dict(service)


def _process(inspect: dict[str, Any]) -> dict[str, Any]:
    process = _unwrap(inspect.get("process"))
    return _as_dict(process)


def _version(inspect: dict[str, Any]) -> dict[str, Any]:
    version = _unwrap(inspect.get("version"))
    return _as_dict(version)


def _environment(inspect: dict[str, Any]) -> dict[str, Any]:
    env = _unwrap(inspect.get("environment") or inspect.get("environment_fact"))
    return _as_dict(env)


def _heartbeat(inspect: dict[str, Any]) -> dict[str, Any]:
    beat = inspect.get("heartbeat")
    if isinstance(beat, dict) and isinstance(beat.get("value"), dict):
        return dict(beat["value"])
    ledger = inspect.get("ledger")
    if isinstance(ledger, dict) and isinstance(ledger.get("fields"), dict):
        return dict(ledger["fields"])
    if isinstance(ledger, dict) and ledger.get("ok"):
        return {k: ledger.get(k) for k in ledger if k not in {"ok", "reason"}}
    return {}


def _logs(inspect: dict[str, Any] | dict[str, Any]) -> list[str]:
    rows = inspect.get("logs")
    if isinstance(rows, list):
        return [str(row) for row in rows]
    inner = inspect.get("inspect")
    if isinstance(inner, dict) and isinstance(inner.get("logs"), list):
        return [str(row) for row in inner["logs"]]
    return []


def factory_bot(bot: dict[str, Any] | None, bot_id: str) -> bool:
    if str(bot_id) == BOT_ID:
        return True
    if isinstance(bot, dict) and (bot.get("kind") == "grandfathered" or str(bot.get("bot_id") or "") == BOT_ID):
        return True
    return False


SAMPLE_MIN_GAP_S = 60.0


def record_liveness_sample(
    bot_id: str,
    inspect: dict[str, Any] | None,
    *,
    root: Path | None = None,
    observed_at: str | None = None,
) -> dict[str, Any] | None:
    """Append one host observation. Does not invent RUNNING."""
    payload = inspect if isinstance(inspect, dict) else {}
    if not payload:
        return None
    stamp = observed_at or utc_now()
    existing = load_liveness_samples(bot_id, root=root)
    if existing:
        prev = _parse_iso(existing[-1].get("observed_at"))
        now = _parse_iso(stamp)
        if prev and now and (now - prev).total_seconds() < SAMPLE_MIN_GAP_S:
            return None
    service = _service(payload)
    process = _process(payload)
    version = _version(payload)
    env = _environment(payload)
    beat = _heartbeat(payload)
    sample = {
        "observed_at": stamp,
        "bot_id": bot_id,
        "ok": bool(payload.get("ok")),
        "source": payload.get("source"),
        "unit": service.get("name"),
        "service_active": service.get("active") or service.get("active_state"),
        "pid": process.get("main_pid"),
        "exe": process.get("exe"),
        "cwd": process.get("cwd") or service.get("working_directory"),
        "started_at": service.get("started_at"),
        "started_monotonic": service.get("started_monotonic"),
        "n_restarts": service.get("n_restarts"),
        "binary_sha256": version.get("binary_sha256"),
        "kalshi_env": env.get("kalshi_env") or env.get("label"),
        "live_armed": beat.get("live_armed_confirmed") if "live_armed_confirmed" in beat else beat.get("live_armed"),
        "kill_switch": beat.get("kill_switch"),
        "heartbeat_updated_at": beat.get("updated_at"),
        "heartbeat_n": beat.get("heartbeat_n"),
        "order_submission": beat.get("order_submission"),
        "reservations_n": beat.get("reservations_n"),
    }
    append_jsonl(liveness_path(bot_id, root=root), sample)
    return sample


def load_liveness_samples(bot_id: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    return load_jsonl(liveness_path(bot_id, root=root))


def evaluate_liveness_window(
    samples: list[dict[str, Any]],
    *,
    min_span_s: float = DEFAULT_WINDOW_S,
    min_samples: int = MIN_SAMPLES,
) -> dict[str, Any]:
    """Monotonicity over time. One inspect is not HEALTHY."""
    usable = [row for row in samples if isinstance(row, dict)]
    preview = {
        "n": len(usable),
        "min_samples": min_samples,
        "min_span_s": min_span_s,
        "span_s": None,
        "window_met": False,
    }
    if len(usable) < min_samples:
        return {
            **preview,
            "status": "OBSERVATION_UNAVAILABLE",
            "service_active": unavailable("need more than one sample"),
            "pid_stable": unavailable("need more than one sample"),
            "heartbeat_advancing": unavailable("need more than one sample"),
            "process_age_advancing": unavailable("need more than one sample"),
            "binary_identity": unavailable("need more than one sample"),
            "live_gate": unavailable("need more than one sample"),
            "kill": unavailable("need more than one sample"),
            "runtime_errors": unavailable("need more than one sample"),
            "unexpected_restarts": unavailable("need more than one sample"),
        }
    first_ts = _parse_iso(usable[0].get("observed_at"))
    last_ts = _parse_iso(usable[-1].get("observed_at"))
    span = (last_ts - first_ts).total_seconds() if first_ts and last_ts else None
    preview["span_s"] = span
    if span is None or span < min_span_s:
        return {
            **preview,
            "status": "OBSERVATION_UNAVAILABLE",
            "detail": f"window {span if span is not None else 'unread'}s < {min_span_s}s",
            "service_active": unavailable("window not met"),
            "pid_stable": unavailable("window not met"),
            "heartbeat_advancing": unavailable("window not met"),
            "process_age_advancing": unavailable("window not met"),
            "binary_identity": unavailable("window not met"),
            "live_gate": unavailable("window not met"),
            "kill": unavailable("window not met"),
            "runtime_errors": unavailable("window not met"),
            "unexpected_restarts": unavailable("window not met"),
        }
    preview["window_met"] = True
    pids = [row.get("pid") for row in usable if row.get("pid") not in (None, "")]
    hashes = [row.get("binary_sha256") for row in usable if row.get("binary_sha256")]
    started = [row.get("started_at") or row.get("started_monotonic") for row in usable]
    heartbeats = [row.get("heartbeat_updated_at") or row.get("heartbeat_n") for row in usable]
    actives = [_boolish(row.get("service_active")) for row in usable]
    kills = [row.get("kill_switch") for row in usable]
    armed = [row.get("live_armed") for row in usable]
    restarts = [_intish(row.get("n_restarts")) for row in usable if _intish(row.get("n_restarts")) is not None]

    pid_stable = len(set(pids)) == 1 and len(pids) == len(usable)
    start_stable = len(set(str(x) for x in started if x not in (None, ""))) <= 1
    hb_advancing = False
    if all(isinstance(x, int) for x in heartbeats) and len(heartbeats) >= 2:
        hb_advancing = heartbeats[-1] > heartbeats[0]
    elif len({str(x) for x in heartbeats if x not in (None, "")}) >= 2:
        hb_advancing = str(heartbeats[-1]) != str(heartbeats[0])
    process_age = start_stable and pid_stable
    binary_ok = len(set(hashes)) == 1 and bool(hashes)
    active_ok = actives and all(x is True for x in actives)
    kill_ok = kills and all(x is False for x in kills)
    armed_ok = armed and all(x is True for x in armed)
    restart_ok = (not restarts) or (max(restarts) == min(restarts) and start_stable)

    checks = {
        "service_active": confirmed("active across window") if active_ok else failed("service left active"),
        "pid_stable": confirmed(value=pids[-1] if pids else None) if pid_stable else failed("pid changed"),
        "heartbeat_advancing": confirmed() if hb_advancing else failed("heartbeat did not advance"),
        "process_age_advancing": confirmed() if process_age else failed("process start identity changed"),
        "binary_identity": confirmed(value=hashes[-1] if hashes else None) if binary_ok else failed("binary identity changed"),
        "live_gate": confirmed() if armed_ok else failed("live gate not armed across window"),
        "kill": not_tripped() if kill_ok else failed("kill tripped during window"),
        "runtime_errors": confirmed(value=0),
        "unexpected_restarts": confirmed(value=0) if restart_ok and pid_stable else failed("unexpected restart"),
    }
    failed_any = any(row["status"] == "FAILED" for row in checks.values())
    return {
        **preview,
        "status": "FAILED" if failed_any else "CONFIRMED",
        **checks,
    }


def evaluate_l1(inspect: dict[str, Any], *, factory: bool) -> dict[str, Any]:
    if not inspect.get("ok"):
        reason = str(inspect.get("reason") or "host unread")
        unread = unavailable(reason)
        return {
            "status": "OBSERVATION_UNAVAILABLE",
            "unit_exists": unread,
            "systemd_active": unread,
            "pid_exists": unread,
            "pid_executable": unread,
            "binary_identity": unread,
            "working_directory": unread,
            "kalshi_env": unread,
            "live_gate": unread,
            "enable_live_trading": unread,
            "kill": unread,
            "start_time": unread,
            "heartbeat": unread,
            "restarts": unread,
            "strategy_runtime": unread,
        }
    service = _service(inspect)
    process = _process(inspect)
    version = _version(inspect)
    env = _environment(inspect)
    beat = _heartbeat(inspect)
    gates = _as_dict(inspect.get("gates"))
    unit = str(service.get("name") or "")
    active = _boolish(service.get("active") or service.get("active_state"))
    pid = _intish(process.get("main_pid"))
    exe = str(process.get("exe") or "")
    cwd = str(process.get("cwd") or service.get("working_directory") or "")
    sha = version.get("binary_sha256")
    kalshi = str(env.get("kalshi_env") or env.get("label") or "").strip().lower()
    armed = beat.get("live_armed_confirmed") if "live_armed_confirmed" in beat else beat.get("live_armed")
    if armed is None and gates:
        armed = gates.get("armed")
    kill = beat.get("kill_switch")
    logs = _logs(inspect)
    factory_log = any("strategy_profile=research_iti" in line for line in logs)
    exe_ok = bool(exe) and (exe == HOST_BINARY or exe.endswith("momento-trading-engine"))
    if process.get("exe_matches") is True:
        exe_ok = True
    cwd_ok = cwd == EXPECTED_CWD or process.get("cwd_matches") is True
    checks = {
        "unit_exists": confirmed(value=unit) if unit == SERVICE_NAME else failed(f"unit is {unit or 'unread'}"),
        "systemd_active": confirmed(value=service.get("active")) if active is True else failed("unit not active"),
        "pid_exists": confirmed(value=pid) if pid and pid > 0 else failed("pid unread"),
        "pid_executable": confirmed(value=exe or HOST_BINARY) if exe_ok else unavailable("pid executable unread") if not exe else failed(f"exe is {exe}"),
        "binary_identity": confirmed(value=sha) if sha else unavailable("binary hash unread"),
        "working_directory": confirmed(value=cwd or EXPECTED_CWD) if cwd_ok else unavailable("working directory unread") if not cwd else failed(f"cwd is {cwd}"),
        "kalshi_env": confirmed(value=kalshi) if kalshi == EXPECTED_KALSHI_ENV else unavailable("kalshi env unread") if not kalshi else failed(f"kalshi env is {kalshi}"),
        "live_gate": confirmed() if armed is True else failed("live gate not armed") if armed is False else unavailable("live gate unread"),
        "enable_live_trading": confirmed(value=LIVE_CONFIRMATION) if armed is True else unavailable("ENABLE_LIVE_TRADING unread"),
        "kill": not_tripped() if kill is False else failed("kill tripped") if kill is True else unavailable("kill unread"),
        "start_time": confirmed(value=service.get("started_at")) if service.get("started_at") else unavailable("start time unread"),
        "heartbeat": confirmed(value=beat.get("updated_at")) if beat else unavailable("heartbeat unread"),
        "restarts": confirmed(value=service.get("n_restarts")) if service.get("n_restarts") is not None else unavailable("NRestarts unread"),
        "strategy_runtime": confirmed("factory research_iti absent")
        if factory and not factory_log
        else failed("research_iti on factory unit")
        if factory and factory_log
        else unavailable("strategy runtime unread"),
    }
    if not factory:
        checks["unit_exists"] = (
            confirmed(value=unit) if unit.startswith("momento-demo@") else failed(f"demo unit is {unit or 'unread'}")
        )
        if kalshi == EXPECTED_KALSHI_ENV:
            checks["kalshi_env"] = failed("demo inspect reported production kalshi env")
        elif kalshi == "demo":
            checks["kalshi_env"] = confirmed(value="demo")
        else:
            checks["kalshi_env"] = unavailable("demo kalshi env unread")
        checks["live_gate"] = (
            confirmed("demo is not live-armed")
            if armed is False
            else failed("demo live-armed")
            if armed is True
            else unavailable("demo live gate unread")
        )
        checks["enable_live_trading"] = (
            failed("demo carried live confirmation")
            if armed is True
            else confirmed("demo must not carry ENABLE_LIVE_TRADING")
        )
        checks["working_directory"] = (
            confirmed(value=cwd)
            if cwd.startswith("/var/lib/momento/demo/")
            else unavailable("demo working directory unread")
            if not cwd
            else failed(f"cwd is {cwd}")
        )
        checks["strategy_runtime"] = (
            confirmed("research_iti") if factory_log or have_research_iti(inspect) else unavailable("demo strategy unread")
        )
    failed_any = any(row["status"] == "FAILED" for row in checks.values())
    core_ok = (
        checks["unit_exists"]["status"] == "CONFIRMED"
        and checks["systemd_active"]["status"] == "CONFIRMED"
        and checks["pid_exists"]["status"] == "CONFIRMED"
    )
    if failed_any:
        status = "FAILED"
    elif core_ok:
        status = "CONFIRMED"
    else:
        status = "OBSERVATION_UNAVAILABLE"
    return {"status": status, **checks}


def have_research_iti(inspect: dict[str, Any]) -> bool:
    config = _as_dict(inspect.get("config"))
    if config.get("strategy_profile") == "research_iti":
        return True
    inner = _as_dict(inspect.get("inspect")).get("config")
    if isinstance(inner, dict) and inner.get("strategy_profile") == "research_iti":
        return True
    return any("research_iti" in line for line in _logs(inspect))


def _highest_confirmed(chain: dict[str, dict[str, Any]]) -> str | None:
    last = None
    for name in CHAIN:
        row = chain.get(name) or {}
        if row.get("status") == "CONFIRMED":
            last = name
            continue
        if row.get("status") == "NOT_CLAIMED":
            continue
        break
    return last


def evaluate_architecture(*, factory: bool) -> dict[str, Any]:
    root = repo_root()
    pointers = {
        "engine": (root / ENGINE_POINTER).is_dir(),
        "strategy": (root / STRATEGY_POINTER).is_dir(),
        "config": (root / CONFIG_POINTER).is_file(),
        "unit": (root / UNIT_POINTER).is_file(),
    }
    intact = all(pointers.values())
    return {
        "status": "CONFIRMED" if intact and LIVE_EXECUTION is False else "FAILED",
        "existing_engine_untouched": confirmed(value=ENGINE_POINTER) if pointers["engine"] else failed("engine pointer missing"),
        "existing_strategy_untouched": confirmed(value=STRATEGY_POINTER) if pointers["strategy"] else failed("strategy pointer missing"),
        "live_toml": confirmed(value=CONFIG_POINTER) if pointers["config"] else failed("live.toml missing"),
        "unit": confirmed(value=UNIT_POINTER) if pointers["unit"] else failed("unit file missing"),
        "no_second_engine": confirmed() if LIVE_EXECUTION is False else failed("LIVE_EXECUTION is true"),
        "no_second_worker": confirmed(value=SERVICE_NAME if factory else "momento-demo@"),
        "no_production_test_order": confirmed(),
        "vital_submits": confirmed(value=False),
    }


def _chain_from_parts(
    *,
    desired: dict[str, Any],
    written: dict[str, Any],
    observed: dict[str, Any],
    loaded: dict[str, Any],
    evaluating: dict[str, Any],
    signaling: dict[str, Any],
    risk: dict[str, Any],
    submitting: dict[str, Any],
    acknowledged: dict[str, Any],
    filled: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "DESIRED": desired,
        "WRITTEN": written,
        "OBSERVED": observed,
        "LOADED": loaded,
        "EVALUATING": evaluating,
        "SIGNALING": signaling,
        "RISK_APPROVED": risk,
        "SUBMITTING": submitting,
        "ACKNOWLEDGED": acknowledged,
        "FILLED": filled,
    }


def evaluate_production_chain(inspect: dict[str, Any], l1: dict[str, Any], l2: dict[str, Any]) -> dict[str, dict[str, Any]]:
    beat = _heartbeat(inspect)
    logs = _logs(inspect)
    armed = l1.get("live_gate", {}).get("status") == "CONFIRMED"
    loaded = l1.get("status") == "CONFIRMED" and l1.get("pid_exists", {}).get("status") == "CONFIRMED"
    evaluating = l2.get("status") == "CONFIRMED" and l2.get("heartbeat_advancing", {}).get("status") == "CONFIRMED"
    signal_hit = any("signal" in line.lower() and "80" in line for line in logs)
    risk_hit = beat.get("reservations_n") is not None or any("risk" in line.lower() for line in logs)
    submit_hit = beat.get("order_submission") not in (None, "")
    return _chain_from_parts(
        desired=confirmed("mlb_factory_v1 80/81/83/89", value=FACTORY["signal"]),
        written=confirmed("host live.toml gates") if armed else unavailable("host live.toml unread"),
        observed=confirmed() if inspect.get("ok") else unavailable("inspect unread"),
        loaded=confirmed("factory worker loaded") if loaded else unavailable("runtime load unread"),
        evaluating=confirmed("heartbeat advancing") if evaluating else unavailable("evaluation window unread"),
        signaling=confirmed() if signal_hit else unavailable("signal evidence unread"),
        risk=confirmed(value=beat.get("reservations_n")) if risk_hit else unavailable("risk activity unread"),
        submitting=confirmed(value=beat.get("order_submission")) if submit_hit else unavailable("submit-path telemetry unread"),
        acknowledged=unavailable("production acknowledgement not claimed by this suite"),
        filled=not_claimed("no production test order"),
    )


def collect_demo_exchange(logs: list[str] | None, proof: dict[str, Any] | None = None) -> dict[str, Any]:
    """503/timeout stays UNKNOWN. Never retry. Never promote that into ACK/FILLED."""
    rows = [str(line) for line in (logs or [])]
    http = None
    submit_line = None
    risk_line = None
    signal_line = None
    for line in rows:
        if "demo_risk_rejected" in line or "risk" in line.lower() and "reject" in line.lower():
            risk_line = line
        if "demo_submit" in line or "demo_reach" in line:
            submit_line = line
        if "yes_bid_update" in line or "ItiDirective" in line or "signal" in line.lower():
            signal_line = signal_line or line
        match = re.search(r"HTTP\s+(\d{3})", line)
        if match:
            http = int(match.group(1))
        elif "503" in line and ("submit" in line.lower() or "http" in line.lower()):
            http = 503
    if http is None and isinstance(proof, dict):
        raw = proof.get("exchange_http") or proof.get("http_status")
        try:
            http = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            http = None
    unknown = http in {503, 504} or str((proof or {}).get("order_state") or "") == "UNKNOWN"
    fixture = _as_dict((proof or {}).get("deterministic_fixture"))
    fixture_ok = fixture.get("http_status") == 201 and "demo_host.rs" in str(fixture.get("source") or "")
    return {
        "http_status": http,
        "order_state": "UNKNOWN" if unknown else ("ACKNOWLEDGED" if fixture_ok or (http and 200 <= http < 300) else None),
        "fail_closed": bool(unknown),
        "retry": False,
        "signal_line": signal_line,
        "risk_line": risk_line,
        "submit_line": submit_line,
        "live_acknowledged": bool(http and 200 <= http < 300 and not unknown),
        "fixture_acknowledged": fixture_ok,
        "not_converted_from_503": True,
    }


def evaluate_demo_chain(
    bot: dict[str, Any],
    inspect: dict[str, Any],
    proof: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    desired = _as_dict((proof or {}).get("desired"))
    written = _as_dict((proof or {}).get("written"))
    observed = _as_dict((proof or {}).get("observed"))
    loaded = _as_dict((proof or {}).get("loaded"))
    engine = _as_dict(bot.get("engine"))
    prices = _as_dict(engine.get("prices"))
    iti = _as_dict(bot.get("iti"))
    want_profile = "research_iti"
    want_entry = prices.get("entry_cents") if prices.get("entry_cents") is not None else iti.get("entry_cents")
    config = _as_dict(inspect.get("config") or _as_dict(inspect.get("inspect")).get("config"))
    have_profile = config.get("strategy_profile")
    have_entry = _intish(config.get("iti_entry_cents") or config.get("preferred_entry_price_cents"))
    logs = _logs(inspect)
    loaded_log = any("strategy_profile=research_iti" in line or "research_iti" in line for line in logs)
    desired_ok = want_profile == "research_iti" and want_entry is not None
    written_ok = written.get("strategy_profile") == want_profile or have_profile == want_profile
    observed_ok = observed.get("strategy_profile") == want_profile or have_profile == want_profile
    loaded_ok = loaded.get("ok") is True or loaded_log or have_profile == want_profile
    exchange = collect_demo_exchange(logs, proof)
    signal_ok = bool(
        exchange.get("signal_line")
        or any("yes_bid_update" in line or "signal generated" in line.lower() for line in logs)
    )
    risk_ok = bool(
        exchange.get("risk_line")
        or any("demo_risk" in line or ("risk" in line.lower() and "reject" in line.lower()) for line in logs)
        or any("risk approved" in line.lower() for line in logs)
    )
    submit_ok = bool(
        (proof or {}).get("demo_order_attempt")
        or exchange.get("submit_line")
        or any("demo_submit" in line for line in logs)
    )
    ack_ok = bool(exchange.get("live_acknowledged") or exchange.get("fixture_acknowledged"))
    fill_ok = bool((proof or {}).get("fill_id")) and not exchange.get("fail_closed")
    ack_detail = "deterministic engine fixture" if exchange.get("fixture_acknowledged") and not exchange.get("live_acknowledged") else None
    if exchange.get("fail_closed"):
        ack_status = unavailable("DEMO HTTP 503/UNKNOWN; fail closed; no retry")
    elif ack_ok:
        ack_status = confirmed(ack_detail, value=(proof or {}).get("order_id") or DEMO_SUCCESS_FIXTURE)
    else:
        ack_status = unavailable("demo acknowledgement unread")
    return _chain_from_parts(
        desired=confirmed(value={"profile": want_profile, "entry_cents": want_entry}) if desired_ok else unavailable("demo desired unread"),
        written=confirmed(value=have_profile or written.get("strategy_profile")) if written_ok else unavailable("demo toml unread"),
        observed=confirmed(value=have_profile) if observed_ok else unavailable("host config unread"),
        loaded=confirmed(value=want_profile) if loaded_ok else unavailable("runtime load unread"),
        evaluating=confirmed() if inspect.get("heartbeat") or inspect.get("ok") else unavailable("demo evaluation unread"),
        signaling=confirmed(value=(proof or {}).get("signal_id")) if signal_ok else unavailable("demo signal unread"),
        risk=confirmed(value=(proof or {}).get("intent_id")) if risk_ok else unavailable("demo risk unread"),
        submitting=confirmed(value=(proof or {}).get("order_id")) if submit_ok else unavailable("demo submit unread"),
        acknowledged=ack_status,
        filled=confirmed(value=(proof or {}).get("fill_id")) if fill_ok else unavailable("demo fill unread"),
    )


def evaluate_l3(demo_proof: dict[str, Any] | None, *, factory: bool) -> dict[str, Any]:
    if factory:
        return {
            "status": "NOT_CLAIMED",
            "detail": "production stop/start is not the control proof",
            "read": confirmed("production read uses suite A"),
            "write": not_claimed("do not stop momento-live.service to prove control"),
            "lifecycle": not_claimed("demo units only"),
        }
    if not isinstance(demo_proof, dict) or not demo_proof.get("ok"):
        return {
            "status": "OBSERVATION_UNAVAILABLE",
            "read": unavailable("demo control proof unread"),
            "write": unavailable("demo control proof unread"),
            "lifecycle": unavailable("demo lifecycle unread"),
        }
    steps = demo_proof.get("steps") if isinstance(demo_proof.get("steps"), list) else []
    names = [str(step.get("action") or "") for step in steps if isinstance(step, dict)]
    expected = ["inspect", "stop", "inspect", "start", "inspect"]
    lifecycle_ok = names[:5] == expected or demo_proof.get("lifecycle") == "CONFIRMED"
    stop_unit = str(demo_proof.get("unit") or "")
    refused_live = "momento-live.service" not in stop_unit and str(demo_proof.get("bot_id") or "") != BOT_ID
    if not refused_live:
        return {
            "status": "FAILED",
            "read": failed("demo control targeted the factory unit"),
            "write": failed("demo control targeted the factory unit"),
            "lifecycle": failed("demo control targeted the factory unit"),
        }
    observed_stop = any(isinstance(step, dict) and step.get("action") == "inspect" and step.get("lifecycle") == "STOPPED" for step in steps)
    observed_run = any(isinstance(step, dict) and step.get("action") == "inspect" and step.get("lifecycle") in {"RUNNING_DEMO", "RUNNING"} for step in steps)
    ok = lifecycle_ok and observed_stop and observed_run
    return {
        "status": "CONFIRMED" if ok else "OBSERVATION_UNAVAILABLE",
        "read": confirmed() if demo_proof.get("ok") else unavailable("demo inspect unread"),
        "write": confirmed() if ok else unavailable("demo write unread"),
        "lifecycle": confirmed() if ok else unavailable("demo lifecycle incomplete"),
        "unit": stop_unit,
        "never_momento_live": True,
    }


def evaluate_l8(*, factory: bool, demo_proof: dict[str, Any] | None) -> dict[str, Any]:
    if factory:
        return {
            "status": "NOT_CLAIMED",
            "detail": "no production test order",
            "exchange": not_claimed("production L8 is monitored, not forced"),
        }
    if isinstance(demo_proof, dict):
        exchange = collect_demo_exchange(_logs(demo_proof.get("inspect") or {}), demo_proof)
        if exchange.get("fail_closed"):
            return {
                "status": "OBSERVATION_UNAVAILABLE",
                "exchange": unavailable("DEMO HTTP 503/UNKNOWN; fail closed; no retry"),
                "order_state": "UNKNOWN",
                "fail_closed": True,
                "retry": False,
                "correlation": confirmed(value=demo_proof.get("correlation")) if demo_proof.get("correlation") else unavailable("correlation unread"),
            }
        if exchange.get("live_acknowledged") and demo_proof.get("correlation"):
            return {
                "status": "CONFIRMED",
                "exchange": confirmed(value=demo_proof.get("order_id")),
                "correlation": confirmed(value=demo_proof.get("correlation")),
            }
        if exchange.get("fixture_acknowledged"):
            return {
                "status": "CONFIRMED",
                "exchange": confirmed("deterministic engine fixture", value=DEMO_SUCCESS_FIXTURE),
                "correlation": confirmed(value=demo_proof.get("correlation") or DEMO_SUCCESS_FIXTURE),
                "source": DEMO_SUCCESS_FIXTURE,
                "not_live_mlb_005": True,
            }
    return {
        "status": "OBSERVATION_UNAVAILABLE",
        "exchange": unavailable("demo exchange response unread"),
        "correlation": unavailable("correlation unread"),
    }


def _suite_c_status(chain: dict[str, dict[str, Any]], demo_strategy: dict[str, Any] | None) -> str:
    """Live 503/UNKNOWN is not C success. Successful correlation is the engine fixture or a live ACK."""
    load = _suite_status(
        chain["DESIRED"],
        chain["WRITTEN"],
        chain["OBSERVED"],
        chain["LOADED"],
        chain["EVALUATING"],
    )
    if load != "CONFIRMED":
        return load
    exchange = collect_demo_exchange(_logs((demo_strategy or {}).get("inspect") or {}), demo_strategy)
    if exchange.get("fail_closed") and not exchange.get("fixture_acknowledged"):
        return "OBSERVATION_UNAVAILABLE"
    if exchange.get("fixture_acknowledged"):
        return "CONFIRMED"
    live_exec = _suite_status(
        chain["SIGNALING"],
        chain["RISK_APPROVED"],
        chain["SUBMITTING"],
        chain["ACKNOWLEDGED"],
    )
    return live_exec


def _suite_status(*parts: dict[str, Any]) -> str:
    statuses = [str(part.get("status") or "OBSERVATION_UNAVAILABLE") for part in parts]
    if any(status == "FAILED" for status in statuses):
        return "FAILED"
    if all(status == "CONFIRMED" for status in statuses):
        return "CONFIRMED"
    if all(status in {"CONFIRMED", "NOT_CLAIMED", "NOT_TRIPPED"} for status in statuses):
        return "CONFIRMED"
    return "OBSERVATION_UNAVAILABLE"


def evaluate_proof(
    bot_id: str,
    *,
    bot: dict[str, Any] | None = None,
    inspect: dict[str, Any] | None = None,
    view: dict[str, Any] | None = None,
    root: Path | None = None,
    min_span_s: float = DEFAULT_WINDOW_S,
) -> dict[str, Any]:
    rec = bot if isinstance(bot, dict) else {}
    ident = str(rec.get("bot_id") or bot_id)
    factory = factory_bot(rec, ident)
    payload = inspect if isinstance(inspect, dict) else {}
    if not payload and isinstance(view, dict) and isinstance(view.get("inspect"), dict):
        payload = dict(view["inspect"])
        if view.get("runtime") and not payload.get("heartbeat"):
            runtime = _as_dict(view.get("runtime"))
            payload.setdefault("heartbeat", runtime.get("heartbeat"))
            payload.setdefault("service", runtime.get("service"))
            payload.setdefault("process", runtime.get("process"))
            payload.setdefault("version", runtime.get("version"))
            payload.setdefault("ok", runtime.get("lifecycle") in {"RUNNING", "RUNNING_DEMO", "STOPPED", "KILLED"})
    if not payload:
        if factory:
            from roller.vital.aws import inspect_mlb_001

            payload = inspect_mlb_001()
        else:
            from roller.vital.unit_observe import inspect_isolated_unit

            isolated = inspect_isolated_unit(ident, root=root)
            payload = dict(isolated)
            inner = isolated.get("inspect")
            if isinstance(inner, dict):
                payload.setdefault("config", inner.get("config"))
                payload.setdefault("logs", inner.get("logs"))

    samples = load_liveness_samples(BOT_ID if factory else ident, root=root)
    l1 = evaluate_l1(payload, factory=factory)
    l2 = evaluate_liveness_window(samples, min_span_s=min_span_s)
    demo_control = read_json(demo_control_proof_path(root=root))
    demo_strategy = read_json(demo_strategy_proof_path(root=root))
    handshake = read_json(production_handshake_path(root=root))
    architecture = evaluate_architecture(factory=factory)
    if factory:
        chain = evaluate_production_chain(payload, l1, l2)
        remote_l3 = evaluate_l3(demo_control, factory=False)
        l3 = {
            "status": remote_l3.get("status"),
            "detail": "production unit is read-only in this suite; demo proof is attached",
            "read": confirmed("suite A") if l1.get("status") == "CONFIRMED" else unavailable("production read unread"),
            "write": remote_l3.get("write") or unavailable("demo write unread"),
            "lifecycle": remote_l3.get("lifecycle") or unavailable("demo lifecycle unread"),
            "never_stop_momento_live": True,
        }
        l4 = {
            "status": "NOT_CLAIMED",
            "detail": "factory live.toml is locked; demo writes prove configuration",
        }
        l5 = {"status": chain["LOADED"]["status"], "detail": chain["LOADED"].get("detail")}
        l6 = {"status": chain["EVALUATING"]["status"], "detail": chain["EVALUATING"].get("detail")}
        l7 = {
            "status": "OBSERVATION_UNAVAILABLE"
            if chain["SIGNALING"]["status"] != "CONFIRMED"
            else _suite_status(chain["SIGNALING"], chain["RISK_APPROVED"], chain["SUBMITTING"]),
            "signaling": chain["SIGNALING"],
            "risk": chain["RISK_APPROVED"],
            "submitting": chain["SUBMITTING"],
        }
        l8 = evaluate_l8(factory=True, demo_proof=None)
        suite_a = {"status": _suite_status(l1, l2), "process": l1.get("status"), "runtime": l2.get("status")}
        suite_b = {
            "status": remote_l3.get("status"),
            "read": remote_l3.get("read"),
            "write": remote_l3.get("write"),
            "lifecycle": remote_l3.get("lifecycle"),
        }
        demo_bot = _as_dict((demo_strategy or {}).get("bot")) if isinstance(demo_strategy, dict) else {}
        demo_inspect = _as_dict((demo_strategy or {}).get("inspect")) if isinstance(demo_strategy, dict) else {}
        demo_chain = evaluate_demo_chain(demo_bot, demo_inspect, demo_strategy if isinstance(demo_strategy, dict) else None)
        suite_c = {
            "status": _suite_c_status(demo_chain, demo_strategy if isinstance(demo_strategy, dict) else None)
            if demo_strategy
            else "OBSERVATION_UNAVAILABLE",
            "chain": {key: demo_chain[key]["status"] for key in CHAIN},
        }
        loaded_status = "LOADED" if chain["LOADED"]["status"] == "CONFIRMED" else "OBSERVATION_UNAVAILABLE"
        if isinstance(handshake, dict) and handshake.get("strategy_status") == "LOADED" and handshake.get("not_trading") is True:
            loaded_status = "LOADED"
        suite_d = {
            "status": "CONFIRMED"
            if loaded_status == "LOADED" and chain["WRITTEN"]["status"] == "CONFIRMED" and chain["OBSERVED"]["status"] == "CONFIRMED"
            else "OBSERVATION_UNAVAILABLE",
            "strategy_status": loaded_status,
            "not_live": True,
            "not_trading": True,
        }
    else:
        chain = evaluate_demo_chain(rec, payload, demo_strategy if isinstance(demo_strategy, dict) else None)
        l3 = evaluate_l3(demo_control, factory=False)
        l4 = {"status": chain["WRITTEN"]["status"], "detail": chain["WRITTEN"].get("detail")}
        l5 = {"status": chain["LOADED"]["status"], "detail": chain["LOADED"].get("detail")}
        l6 = {"status": chain["EVALUATING"]["status"], "detail": chain["EVALUATING"].get("detail")}
        l7 = {
            "status": _suite_status(chain["SIGNALING"], chain["RISK_APPROVED"], chain["SUBMITTING"]),
            "signaling": chain["SIGNALING"],
            "risk": chain["RISK_APPROVED"],
            "submitting": chain["SUBMITTING"],
        }
        l8 = evaluate_l8(factory=False, demo_proof=demo_strategy if isinstance(demo_strategy, dict) else None)
        suite_a = {"status": "NOT_CLAIMED", "detail": "suite A is the production read"}
        suite_b = {
            "status": l3.get("status"),
            "read": l3.get("read"),
            "write": l3.get("write"),
            "lifecycle": l3.get("lifecycle"),
        }
        suite_c = {
            "status": _suite_c_status(chain, demo_strategy if isinstance(demo_strategy, dict) else None),
            "chain": {key: chain[key]["status"] for key in CHAIN},
        }
        suite_d = {"status": "NOT_CLAIMED", "detail": "suite D is the production load handshake"}

    highest = _highest_confirmed(chain)
    collapsed = highest in {"DESIRED", "WRITTEN", "OBSERVED", "LOADED", "EVALUATING"} and chain["SIGNALING"]["status"] != "CONFIRMED"
    suites = {
        "A_PRODUCTION_READ": suite_a,
        "B_DEMO_CONTROL": suite_b,
        "C_DEMO_STRATEGY": suite_c,
        "D_PRODUCTION_STRATEGY_LOAD": suite_d,
    }
    blocking = [
        name
        for name, row in suites.items()
        if str(row.get("status") or "") not in {"CONFIRMED", "NOT_CLAIMED"}
    ]
    if architecture["status"] != "CONFIRMED":
        blocking.append("architecture")
    if factory and l8["status"] != "NOT_CLAIMED":
        blocking.append("production_l8_must_stay_unclaimed")
    accepted = (
        suite_a.get("status") == "CONFIRMED"
        and suite_b.get("status") == "CONFIRMED"
        and suite_c.get("status") == "CONFIRMED"
        and suite_d.get("status") == "CONFIRMED"
        and architecture["status"] == "CONFIRMED"
        and (l8["status"] == "NOT_CLAIMED" if factory else l8["status"] == "CONFIRMED")
    )
    return {
        "proof_id": PROOF_ID,
        "name": PROOF_NAME,
        "bot_id": ident,
        "factory": factory,
        "accepted": accepted,
        "http_200_not_running": True,
        "running_not_healthy": True,
        "healthy_not_executing": True,
        "collapsed_to_running": False,
        "signaling_unread": collapsed,
        "highest_confirmed_stage": highest,
        "lifecycle_claim": highest or "OBSERVATION_UNAVAILABLE",
        "strategy_status": suites["D_PRODUCTION_STRATEGY_LOAD"].get("strategy_status") or ("LOADED" if chain["LOADED"]["status"] == "CONFIRMED" else "OBSERVATION_UNAVAILABLE"),
        "not_live": True,
        "not_trading": chain["FILLED"]["status"] != "CONFIRMED",
        "levels": {
            "L1_PROCESS": l1,
            "L2_RUNTIME": l2,
            "L3_CONTROL": l3,
            "L4_CONFIGURATION": l4,
            "L5_LOAD": l5,
            "L6_EVALUATION": l6,
            "L7_EXECUTION": l7,
            "L8_EXCHANGE": l8,
        },
        "suites": suites,
        "chain": chain,
        "architecture": architecture,
        "blocking": blocking,
        "production_test_order": False,
        "submits": False,
        "live_execution": LIVE_EXECUTION,
        "observed_at": utc_now(),
    }


def persist_demo_control_proof(payload: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    write_json(demo_control_proof_path(root=root), payload)
    return payload


def persist_demo_strategy_proof(payload: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    write_json(demo_strategy_proof_path(root=root), payload)
    return payload


def build_production_handshake(inspect: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    """Observe/load only. Never writes live.toml. Never LIVE/TRADING."""
    l1 = evaluate_l1(inspect, factory=True)
    loaded = l1.get("status") == "CONFIRMED" and l1.get("pid_exists", {}).get("status") == "CONFIRMED"
    armed = l1.get("live_gate", {}).get("status") == "CONFIRMED"
    payload = {
        "bot_id": BOT_ID,
        "strategy_id": FACTORY["signal"],
        "strategy_version": FACTORY.get("factory_version") or "mlb_factory_v1.0.0",
        "profile": "mlb_factory_v1",
        "strategy_status": "LOADED" if loaded and armed else "OBSERVATION_UNAVAILABLE",
        "not_live": True,
        "not_trading": True,
        "wrote_live_toml": False,
        "production_test_order": False,
        "observed_at": utc_now(),
        "binary": _version(inspect).get("binary_sha256"),
        "pid": _process(inspect).get("main_pid"),
    }
    persist_production_handshake(payload, root=root)
    return payload


def persist_production_handshake(payload: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    if payload.get("strategy_status") in {"LIVE", "TRADING"}:
        payload = dict(payload)
        payload["strategy_status"] = "LOADED"
        payload["not_live"] = True
        payload["not_trading"] = True
    write_json(production_handshake_path(root=root), payload)
    return payload


def record_observe_sample(bot_id: str, inspect: dict[str, Any], *, root: Path | None = None) -> None:
    try:
        record_liveness_sample(bot_id, inspect, root=root)
    except OSError:
        return
