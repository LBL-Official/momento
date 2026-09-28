"""Calendar-block resampling. A B-day block advances B local days."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from repair.ledger import replay

LA = ZoneInfo("America/Los_Angeles")


def local_date(ts: int) -> date:
    return datetime.fromtimestamp(int(ts), tz=LA).date()


def local_midnight(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=LA).timestamp())


def complete_days(candidates: list[dict]) -> list[date]:
    days = [local_date(int(c["signal_ts"])) for c in candidates]
    if not days:
        return []
    start, end = min(days), max(days)
    out = []
    cursor = start
    while cursor <= end:
        out.append(cursor)
        cursor += timedelta(days=1)
    return out


def _shift_candidate(cand: dict, src_day: date, dest_day: date, instance_id: str) -> dict:
    action = int(cand.get("action_ts") or cand["signal_ts"])
    placed_action = local_midnight(dest_day) + (action - local_midnight(src_day))
    delta = placed_action - action
    nxt = {k: v for k, v in cand.items() if k != "bars"}
    nxt["signal_ts"] = int(cand["signal_ts"]) + delta
    nxt["action_ts"] = placed_action
    if cand.get("exit_ts") is not None:
        nxt["exit_ts"] = int(cand["exit_ts"]) + delta
    if cand.get("cash_ts") is not None:
        nxt["cash_ts"] = int(cand["cash_ts"]) + delta
    nxt["game_id"] = instance_id
    nxt["stable_event_id"] = instance_id
    nxt["local_day"] = dest_day.isoformat()
    if nxt.get("exit_ts") is not None and int(nxt["exit_ts"]) < int(nxt["action_ts"]):
        raise RuntimeError("negative lifecycle interval")
    return nxt


def map_identity(candidates: list[dict]) -> list[dict]:
    built = []
    for cand in candidates:
        day = local_date(int(cand["signal_ts"]))
        built.append(_shift_candidate(cand, day, day, str(cand["game_id"])))
    return built


def sample_paths(
    candidates: list[dict],
    *,
    block: int,
    n_paths: int,
    seed: int,
    balance_cents: int = 2_000_000,
) -> dict:
    days = complete_days(candidates)
    by_day: dict[date, list[dict]] = {}
    for cand in candidates:
        by_day.setdefault(local_date(int(cand["signal_ts"])), []).append(cand)
    if len(days) < 1:
        return {"status": "NO_DAYS", "paths": []}
    span = max(1, len(days) - block + 1)
    horizon_end = days[-1]
    horizon_ts = local_midnight(horizon_end + timedelta(days=1)) - 1
    rng = random.Random(seed)
    paths = []
    maps = []
    for i in range(n_paths):
        dest_cursor = days[0]
        built = []
        used = 0
        copy_n = 0
        while used < len(days):
            start = rng.randrange(span)
            source = days[start : start + block]
            take = min(len(source), len(days) - used)
            source = source[:take]
            for offset, src_day in enumerate(source):
                dest_day = dest_cursor + timedelta(days=offset)
                if dest_day > horizon_end:
                    continue
                for cand in by_day.get(src_day, []):
                    instance = f"{cand['game_id']}#p{i}#c{copy_n}"
                    copy_n += 1
                    built.append(_shift_candidate(cand, src_day, dest_day, instance))
                    maps.append(
                        {
                            "path": i,
                            "source_day": src_day.isoformat(),
                            "dest_day": dest_day.isoformat(),
                            "instance_id": instance,
                            "block_days": block,
                        }
                    )
            dest_cursor = dest_cursor + timedelta(days=take)
            used += take
        book = replay(built, balance_cents=balance_cents, horizon_ts=horizon_ts)
        series = [balance_cents] + [int(row["realized_equity_cents"]) for row in book["events"]]
        peak = series[0]
        max_dd = 0.0
        for value in series:
            peak = max(peak, value)
            if peak:
                max_dd = max(max_dd, 1 - value / peak)
        paths.append(
            {
                "path": i,
                "block_days": block,
                "ending_equity_cents": book["ending_equity_cents"],
                "horizon_marked_equity_cents": book["horizon_marked_equity_cents"],
                "max_drawdown_fraction": max_dd,
                "admitted": len(book["trades"]),
                "seed": seed,
            }
        )
    return {"status": "DESCRIPTIVE_HISTORICAL_RESAMPLE", "block_days": block, "n_days": len(days), "paths": paths, "maps": maps}
