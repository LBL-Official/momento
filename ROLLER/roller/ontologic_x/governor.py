"""Credit governor. Measured response headers outrank the planned allowance."""

from __future__ import annotations

from datetime import date, datetime, timezone

STARTER_ALLOWANCE = 500
STARTER_BUCKETS = {
    "coverage_debug": 50,
    "preseason_snapshots": 350,
    "reserve": 100,
}
OCTOBER20_ALLOWANCE = 20_000
OCTOBER20_BUCKETS = {
    "broad_monitoring": 6_000,
    "detailed_markets": 10_000,
    "reserve": 4_000,
}
OCTOBER20_ON = date(2026, 10, 20)
DETAILED_INTERVAL_SECONDS = 120
PRIOR_PROBE = {
    "bucket": "coverage_debug",
    "purpose": "prior_manual_probe",
    "endpoint": "bulk_odds",
    "credits_last": 5,
    "credits_used": 5,
    "credits_remaining": 495,
    "season_phase": "unscoped",
}

ILLUSTRATIVE = (
    {"label": "10 market keys × 30 snapshots × 1 game", "market_keys": 10, "snapshots": 30, "games": 1},
    {"label": "10 market keys × 30 snapshots × 40 games", "market_keys": 10, "snapshots": 30, "games": 40},
    {"label": "25 market keys × 30 snapshots × 40 games", "market_keys": 25, "snapshots": 30, "games": 40},
)


def active_policy(today: date, plan: str) -> dict:
    """October 20 raises the ceiling only when that plan is explicitly selected."""
    if plan == "october20" and today >= OCTOBER20_ON:
        return {
            "name": "october20",
            "allowance": OCTOBER20_ALLOWANCE,
            "buckets": dict(OCTOBER20_BUCKETS),
            "detailed_interval_seconds": DETAILED_INTERVAL_SECONDS,
            "active": True,
        }
    return {
        "name": "starter",
        "allowance": STARTER_ALLOWANCE,
        "buckets": dict(STARTER_BUCKETS),
        "detailed_interval_seconds": None,
        "active": False,
    }


def spent_by_bucket(rows: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        bucket = str(row.get("bucket") or "")
        totals[bucket] = totals.get(bucket, 0) + int(row.get("credits_last") or 0)
    return totals


def latest_measurement(rows: list[dict]) -> dict:
    measured = [row for row in rows if row.get("credits_remaining") is not None]
    if not measured:
        return {"credits_used": None, "credits_remaining": None}
    last = measured[-1]
    return {
        "credits_used": last.get("credits_used"),
        "credits_remaining": last.get("credits_remaining"),
    }


def authorize(rows: list[dict], bucket: str, estimate: int, policy: dict) -> tuple[bool, str]:
    if estimate < 0:
        return False, "INVALID_ESTIMATE"
    if bucket == "reserve" or bucket not in policy["buckets"]:
        return False, "BUCKET_CLOSED"
    spent = spent_by_bucket(rows).get(bucket, 0)
    if spent + estimate > int(policy["buckets"][bucket]):
        return False, "BUCKET_EXHAUSTED"
    reserve_cap = int(policy["buckets"]["reserve"])
    reserve_spent = spent_by_bucket(rows).get("reserve", 0)
    reserve_left = reserve_cap - reserve_spent
    remaining = latest_measurement(rows).get("credits_remaining")
    if remaining is not None and estimate > int(remaining) - reserve_left:
        return False, "RESERVE_PROTECTION"
    return True, "OK"


def next_detailed_interval(rows: list[dict], policy: dict, estimate: int) -> int | None:
    """Two-minute polling exists only on the October 20 plan, and only inside its bucket."""
    if not policy.get("active"):
        return None
    allowed, _reason = authorize(rows, "detailed_markets", estimate, policy)
    if not allowed:
        return None
    return int(policy["detailed_interval_seconds"])


def illustrative_costs() -> list[dict]:
    from roller.ontologic_x.markets import scenario_cost

    rows = []
    for item in ILLUSTRATIVE:
        credits = scenario_cost(item["market_keys"], item["snapshots"], item["games"])
        rows.append(
            {
                "label": item["label"],
                "credits": credits,
                "exceeds_october20_detailed": credits > OCTOBER20_BUCKETS["detailed_markets"],
                "exceeds_october20_allowance": credits > OCTOBER20_ALLOWANCE,
                "basis": "unique returned market keys × snapshots × games, one bookmaker group",
            }
        )
    return rows


def stamp(moment: datetime | None = None) -> str:
    current = moment or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
