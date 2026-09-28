"""Demo-only MLB shard funding. Never production. Never a venue create."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from roller.jump.catalog.bankroll import (
    MLB_EXCHANGE_INDEX,
    breakdown_line_cents,
    dollars_to_truncated_cents,
)
from roller.jump.catalog.kalshi import fills_bin
from roller.jump.catalog.versions import DEMO_SECRET_ID, PRODUCTION_SECRET_ID
from roller.jump.library import repo_root

TRANSFER_CENTS = 1000
PROVISION_CENTS = 100
CENTICENTS_PER_CENT = 100
DEFAULT_SOURCE_INDEX = 0
DEMO_ORIGIN = "https://external-api.demo.kalshi.co"


def refuse_production_transfer(
    *,
    environment: str,
    secret_id: str | None = None,
    secret_path: str | None = None,
    origin: str | None = None,
) -> None:
    env = str(environment or "").strip().lower()
    if env in {"production", "prod", "live"}:
        raise ValueError("demo shard transfer refuses production")
    sid = str(secret_id or "").strip().lower()
    if "production" in sid or sid.endswith("/prod") or sid == PRODUCTION_SECRET_ID.lower():
        raise ValueError("demo shard transfer refuses a production secret id")
    path = str(secret_path or "").strip().lower()
    if "production" in path or "/prod" in path:
        raise ValueError("demo shard transfer refuses a production secret path")
    host = str(origin or "").strip().lower()
    if "kalshi.com" in host and "demo" not in host:
        raise ValueError("demo shard transfer refuses a production origin")


def _int(raw: Any) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def breakdown_rows(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def shard_cents(rows: list[dict[str, Any]], index: int) -> int | None:
    for row in rows:
        try:
            if int(row.get("exchange_index")) != index:
                continue
        except (TypeError, ValueError):
            continue
        cents = breakdown_line_cents(row)
        if cents is None:
            cents = dollars_to_truncated_cents(row.get("balance") or row.get("balance_dollars"))
        return cents
    return None


def plan_demo_mlb_transfer(
    body: dict[str, Any] | None,
    *,
    amount_cents: int = TRANSFER_CENTS,
) -> dict[str, Any]:
    """Decide a Demo-only $10 move onto the observed MLB shard. Missing is not $0."""
    if amount_cents <= 0:
        return {"ok": False, "transfer": False, "detail": "transfer amount must be a positive integer of cents"}
    payload = body if isinstance(body, dict) else {}
    env = str(payload.get("environment") or "DEMO").strip().upper()
    try:
        refuse_production_transfer(
            environment=env,
            secret_id=payload.get("secret_id"),
            origin=payload.get("origin") or DEMO_ORIGIN,
        )
    except ValueError as exc:
        return {"ok": False, "transfer": False, "detail": str(exc), "mlb_shard_cents": None}
    rows = breakdown_rows(payload.get("balance_breakdown"))
    top = _int(payload.get("balance_cents") if payload.get("balance_cents") is not None else payload.get("current_cents"))
    if not rows:
        return {
            "ok": False,
            "transfer": False,
            "detail": "Demo balance_breakdown unread",
            "mlb_shard_cents": None,
            "top_level_cents": top,
        }
    dest_cents = shard_cents(rows, MLB_EXCHANGE_INDEX)
    if dest_cents is None:
        return {
            "ok": False,
            "transfer": False,
            "detail": "MLB exchange_index 3 unread",
            "mlb_shard_cents": None,
            "top_level_cents": top,
            "exchange_index": None,
        }
    source_cents = shard_cents(rows, DEFAULT_SOURCE_INDEX)
    if dest_cents >= amount_cents:
        return {
            "ok": True,
            "transfer": False,
            "detail": "Demo MLB shard already has at least the requested cents",
            "mlb_shard_cents": dest_cents,
            "source_cents": source_cents,
            "top_level_cents": top,
            "exchange_index": MLB_EXCHANGE_INDEX,
            "amount_cents": amount_cents,
        }
    if source_cents is None:
        return {
            "ok": False,
            "transfer": False,
            "detail": "source exchange_index 0 unread",
            "mlb_shard_cents": dest_cents,
            "top_level_cents": top,
            "exchange_index": MLB_EXCHANGE_INDEX,
        }
    remaining = source_cents - amount_cents
    if remaining < 0:
        return {
            "ok": False,
            "transfer": False,
            "detail": "source shard has fewer than the requested cents",
            "mlb_shard_cents": dest_cents,
            "source_cents": source_cents,
            "top_level_cents": top,
            "exchange_index": MLB_EXCHANGE_INDEX,
        }
    return {
        "ok": True,
        "transfer": True,
        "detail": None,
        "mlb_shard_cents": dest_cents,
        "source_cents": source_cents,
        "source_remaining_cents": remaining,
        "top_level_cents": top,
        "source_exchange_shard": DEFAULT_SOURCE_INDEX,
        "destination_exchange_shard": MLB_EXCHANGE_INDEX,
        "amount_cents": amount_cents,
        "amount_centicents": amount_cents * CENTICENTS_PER_CENT,
        "environment": "DEMO",
        "origin": DEMO_ORIGIN,
        "submits": False,
        "not_create_v2": True,
    }


def plan_demo_mlb_ensure_user(
    body: dict[str, Any] | None,
    *,
    amount_cents: int = PROVISION_CENTS,
) -> dict[str, Any]:
    """Plan a Demo-only touch transfer so Kalshi EnsureUser runs. Missing is not $0.

    A non-zero MLB breakdown line is not a Predictions trading user. Official
    intra-transfer is what calls EnsureUser. Venue create-order is not used.
    """
    planned = plan_demo_mlb_transfer(body, amount_cents=amount_cents)
    if planned.get("transfer") or not planned.get("ok"):
        return planned
    if planned.get("mlb_shard_cents") is None:
        return planned
    payload = body if isinstance(body, dict) else {}
    rows = breakdown_rows(payload.get("balance_breakdown"))
    source_cents = shard_cents(rows, DEFAULT_SOURCE_INDEX)
    dest_cents = planned.get("mlb_shard_cents")
    top = _int(payload.get("balance_cents") if payload.get("balance_cents") is not None else payload.get("current_cents"))
    if source_cents is None:
        return {
            "ok": False,
            "transfer": False,
            "detail": "source exchange_index 0 unread",
            "mlb_shard_cents": dest_cents,
            "top_level_cents": top,
            "exchange_index": MLB_EXCHANGE_INDEX,
        }
    remaining = source_cents - amount_cents
    if remaining < 0:
        return {
            "ok": False,
            "transfer": False,
            "detail": "source shard has fewer than the requested cents",
            "mlb_shard_cents": dest_cents,
            "source_cents": source_cents,
            "top_level_cents": top,
            "exchange_index": MLB_EXCHANGE_INDEX,
        }
    return {
        "ok": True,
        "transfer": True,
        "ensure_user": True,
        "detail": None,
        "mlb_shard_cents": dest_cents,
        "source_cents": source_cents,
        "source_remaining_cents": remaining,
        "top_level_cents": top,
        "source_exchange_shard": DEFAULT_SOURCE_INDEX,
        "destination_exchange_shard": MLB_EXCHANGE_INDEX,
        "amount_cents": amount_cents,
        "amount_centicents": amount_cents * CENTICENTS_PER_CENT,
        "environment": "DEMO",
        "origin": DEMO_ORIGIN,
        "submits": False,
        "not_create_v2": True,
    }


def _run_fills(args: list[str], timeout: int = 45) -> dict[str, Any]:
    binary = fills_bin()
    if not binary:
        return {"ok": False, "detail": "momento-jump-fills-read unread"}
    try:
        proc = subprocess.run(
            [binary, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "detail": str(exc)[:200]}
    try:
        payload = json.loads(proc.stdout or "{}")
        if isinstance(payload, dict):
            if proc.returncode != 0:
                payload.setdefault("ok", False)
                payload.setdefault("detail", (proc.stderr or "").strip()[:240] or "fills-read failed")
            return payload
    except json.JSONDecodeError:
        pass
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "fills-read failed").strip()
        return {"ok": False, "detail": err[:240]}
    return {"ok": False, "detail": "fills-read output unreadable"}


def _resolve_demo_secret(secret_file: Path | None = None) -> tuple[Path | None, bool]:
    if secret_file is not None:
        return (secret_file if secret_file.is_file() else None), False
    from roller.jump.catalog.kalshi import _fetch_secret_to_temp, _secret_file

    existing = _secret_file("DEMO")
    if existing is not None:
        return existing, False
    fetched = _fetch_secret_to_temp("DEMO")
    return fetched, fetched is not None


def observe_demo_balance(*, secret_file: Path | None = None) -> dict[str, Any]:
    path, owned = _resolve_demo_secret(secret_file)
    try:
        if path is None or not path.is_file():
            return {"ok": False, "environment": "DEMO", "detail": "Demo secret file unread", "mlb_shard_cents": None}
        refuse_production_transfer(environment="DEMO", secret_id=DEMO_SECRET_ID, secret_path=str(path), origin=DEMO_ORIGIN)
        raw = _run_fills(
            ["balance", "--environment", "demo", "--secret-file", str(path)],
            timeout=45,
        )
        raw.setdefault("environment", "DEMO")
        if not raw.get("ok"):
            raw["mlb_shard_cents"] = None
            return raw
        planned = plan_demo_mlb_transfer(raw)
        raw["mlb_shard_cents"] = planned.get("mlb_shard_cents")
        raw["plan"] = planned
        raw["read_only"] = True
        raw["submits"] = False
        return raw
    finally:
        if owned and path is not None:
            try:
                path.unlink()
            except OSError:
                pass


def fund_demo_mlb_shard(
    *,
    amount_cents: int = TRANSFER_CENTS,
    secret_file: Path | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    """Observe Demo breakdown, optionally POST intra-transfer on Demo origin only."""
    path, owned = _resolve_demo_secret(secret_file)
    try:
        before = observe_demo_balance(secret_file=path)
        plan = plan_demo_mlb_transfer(before, amount_cents=amount_cents)
        out = {
            "ok": bool(plan.get("ok")),
            "environment": "DEMO",
            "origin": DEMO_ORIGIN,
            "read_only": not execute,
            "submits": False,
            "not_create_v2": True,
            "before": {
                "ok": before.get("ok"),
                "balance_cents": before.get("balance_cents"),
                "mlb_shard_cents": before.get("mlb_shard_cents"),
                "detail": before.get("detail"),
            },
            "plan": plan,
            "transferred": False,
            "after": None,
        }
        if not plan.get("ok"):
            out["detail"] = plan.get("detail")
            return out
        if not plan.get("transfer"):
            ensure = plan_demo_mlb_ensure_user(before)
            out["ensure_user_plan"] = ensure
            if ensure.get("ok") and ensure.get("transfer"):
                plan = ensure
                out["plan"] = plan
            else:
                out["detail"] = plan.get("detail")
                out["after"] = out["before"]
                return out
        if not execute:
            out["detail"] = "transfer planned; execute is false"
            return out
        if path is None or not path.is_file():
            out["ok"] = False
            out["detail"] = "Demo secret file unread"
            return out
        refuse_production_transfer(
            environment="DEMO",
            secret_id=DEMO_SECRET_ID,
            secret_path=str(path),
            origin=DEMO_ORIGIN,
        )
        sent: dict[str, Any] = {"ok": False}
        for attempt in range(3):
            sent = _run_fills(
                [
                    "demo-intra-transfer",
                    "--environment",
                    "demo",
                    "--secret-file",
                    str(path),
                    "--source-shard",
                    str(plan["source_exchange_shard"]),
                    "--destination-shard",
                    str(plan["destination_exchange_shard"]),
                    "--amount-centicents",
                    str(plan["amount_centicents"]),
                ],
                timeout=45,
            )
            if sent.get("ok"):
                break
            status = sent.get("http_status")
            if status not in {503, 504} or attempt == 2:
                break
            out["ensure_user_retries"] = attempt + 1
            time.sleep(5)
        after = observe_demo_balance(secret_file=path)
        out["transferred"] = bool(sent.get("ok"))
        out["transfer_result"] = {
            "ok": sent.get("ok"),
            "transfer_id": sent.get("transfer_id"),
            "detail": sent.get("detail"),
            "http_status": sent.get("http_status"),
        }
        out["after"] = {
            "ok": after.get("ok"),
            "balance_cents": after.get("balance_cents"),
            "mlb_shard_cents": after.get("mlb_shard_cents"),
            "detail": after.get("detail"),
        }
        if sent.get("ok") and after.get("mlb_shard_cents") is None:
            out["ok"] = False
            out["detail"] = "transfer HTTP accepted; Demo MLB shard still unread"
        elif sent.get("ok"):
            out["ok"] = True
            out["detail"] = None
        else:
            out["ok"] = False
            out["detail"] = sent.get("detail") or "Demo intra-transfer failed"
        return out
    finally:
        if owned and path is not None:
            try:
                path.unlink()
            except OSError:
                pass


def repo_fills_bin() -> str | None:
    env = (os.environ.get("JUMP_FILLS_BIN") or "").strip()
    if env:
        return env
    return fills_bin() or str(repo_root() / "target" / "debug" / "momento-jump-fills-read")
