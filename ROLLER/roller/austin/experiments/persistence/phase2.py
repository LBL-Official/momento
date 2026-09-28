"""Phase 2 descriptive objects: recovery, downfall, intervention window, support, dynamics."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.persistence.ids import PERSISTENT_NEGATIVE_EV, TEMPORARY_NEGATIVE_EV
from roller.austin.experiments.persistence.landmarks import landmark_states
from roller.austin.experiments.persistence.util import as_float, clock_minutes_between
from roller.austin.experiments.persistence.warning import _first_t40, _worst_price_row


def _score(row: dict[str, Any] | None) -> int | None:
    if row is None or row.get("home_score") is None or row.get("away_score") is None:
        return None
    return int(row["home_score"]) - int(row["away_score"])


def _vel(a: dict[str, Any] | None, b: dict[str, Any] | None) -> float | None:
    if a is None or b is None:
        return None
    dt = clock_minutes_between(a, b)
    ev_a = as_float(a.get("conditional_ev_cents"))
    ev_b = as_float(b.get("conditional_ev_cents"))
    if dt in (None, 0) or ev_a is None or ev_b is None:
        return None
    return (ev_b - ev_a) / dt


def attach_dynamics(event: dict[str, Any], trajectory: list[dict[str, Any]]) -> dict[str, Any]:
    states = landmark_states(event)
    t0, t1, t2, t3 = states["t0"], states["t1"], states["t2"], states["t3"]
    v01 = _vel(t0, t1)
    v12 = _vel(t1, t2)
    acc = None
    dt = clock_minutes_between(t1, t2)
    if v01 is not None and v12 is not None and dt not in (None, 0):
        acc = (v12 - v01) / dt
    depths = [r["EV_DEPTH"] for r in trajectory if r.get("EV_DEPTH") is not None]
    vels = [r["EV_VELOCITY"] for r in trajectory if r.get("EV_VELOCITY") is not None]
    accs = [r["EV_ACCELERATION"] for r in trajectory if r.get("EV_ACCELERATION") is not None]
    event["EV_velocity_t0_to_t1"] = v01
    event["EV_velocity_t1_to_t2"] = v12
    event["EV_acceleration_t0_t2"] = acc
    event["mean_EV_depth"] = None if not depths else sum(depths) / len(depths)
    event["mean_EV_velocity"] = None if not vels else sum(vels) / len(vels)
    event["mean_EV_acceleration"] = None if not accs else sum(accs) / len(accs)
    return event


def recovery_row(event: dict[str, Any]) -> dict[str, Any]:
    first = event["_first"]
    later_valid = event["_later_valid"]
    later = event["_later"]
    recover_ev = next((r for r in later_valid if as_float(r.get("conditional_ev_cents")) is not None and float(r["conditional_ev_cents"]) >= 0), None)
    later_prices = [(r, r.get("current_price_cents")) for r in later if r.get("current_price_cents") is not None]

    def first_price(threshold: int) -> dict[str, Any] | None:
        for row, px in later_prices:
            if int(px) >= threshold:
                return row
        return None

    p50 = first_price(50)
    p60 = first_price(60)
    p70 = first_price(70)
    p80 = first_price(80)
    return {
        "trade_id": event["trade_id"],
        "internal_game_id": event.get("internal_game_id"),
        "source_experiment_id": event["source_experiment_id"],
        "negative_ev_class": event["negative_ev_class"],
        "won": event.get("won"),
        "EV_recovered_ge_0": recover_ev is not None,
        "time_to_EV_recovery": clock_minutes_between(first, recover_ev),
        "future_recover_ge_50": event.get("future_recover_ge_50"),
        "future_recover_ge_60": event.get("future_recover_ge_60"),
        "future_recover_ge_70": event.get("future_recover_ge_70"),
        "future_recover_ge_80": event.get("future_recover_ge_80"),
        "time_to_price_50": clock_minutes_between(first, p50),
        "time_to_price_60": clock_minutes_between(first, p60),
        "time_to_price_70": clock_minutes_between(first, p70),
        "time_to_price_80": clock_minutes_between(first, p80),
        "future_MFE": event.get("future_MFE"),
        "future_max_price": event.get("future_max_price"),
    }


def downfall_row(event: dict[str, Any]) -> dict[str, Any]:
    first = event["_first"]
    t40 = _first_t40(event)
    worst = _worst_price_row(event)
    later = event.get("_later") or []
    settle = later[-1] if later else first
    return {
        "trade_id": event["trade_id"],
        "internal_game_id": event.get("internal_game_id"),
        "source_experiment_id": event["source_experiment_id"],
        "negative_ev_class": event["negative_ev_class"],
        "won": event.get("won"),
        "terminal_loss": not bool(event.get("won")),
        "future_T40": event.get("future_T40"),
        "future_MAE": event.get("future_MAE"),
        "future_min_price": event.get("future_min_price"),
        "time_to_T40": clock_minutes_between(first, t40),
        "time_to_worst_price": clock_minutes_between(first, worst),
        "time_to_settlement": clock_minutes_between(first, settle),
        "pnl_hold_after_t0": event.get("pnl_hold_after_t0") if event.get("pnl_hold_after_t0") is not None else event.get("pnl_hold_after_first_negative"),
    }


def _after(event: dict[str, Any], landmark: dict[str, Any] | None) -> list[dict[str, Any]]:
    if landmark is None:
        return []
    started = False
    out = []
    for row in [event["_first"], *(event.get("_later") or [])]:
        if row is landmark:
            started = True
            continue
        if started:
            out.append(row)
    return out


def intervention_rows(event: dict[str, Any]) -> list[dict[str, Any]]:
    states = landmark_states(event)
    t40 = _first_t40(event)
    out = []
    for name in ("t0", "t1", "t2", "t3"):
        row = states.get(name)
        if row is None:
            continue
        ev = as_float(row.get("conditional_ev_cents"))
        if ev is None or ev >= 0 and name != "t0":
            if name != "t0":
                continue
        later = _after(event, row)
        prices = [int(r["current_price_cents"]) for r in later if r.get("current_price_cents") is not None]
        price = row.get("current_price_cents")
        future_min = None if not prices else min(prices)
        worst = None if not prices else next(r for r in later if r.get("current_price_cents") is not None and int(r["current_price_cents"]) == future_min)
        t40_later = next((r for r in later if r.get("t40_already") or r.get("hit_40_after")), t40)
        out.append(
            {
                "trade_id": event["trade_id"],
                "internal_game_id": event.get("internal_game_id"),
                "source_experiment_id": event["source_experiment_id"],
                "negative_ev_class": event["negative_ev_class"],
                "landmark": name,
                "price_at_landmark": price,
                "future_minimum_price": future_min,
                "adverse_cents_remaining": None if price is None or future_min is None else int(price) - int(future_min),
                "game_clock_minutes_to_worst_price": clock_minutes_between(row, worst),
                "game_clock_minutes_to_T40": clock_minutes_between(row, t40_later),
                "note": "INTERVENTION_WINDOW_REMAINING is descriptive. Not a trading instruction.",
            }
        )
    return out


def support_row(event: dict[str, Any]) -> dict[str, Any]:
    pit = event.get("pit") or {}
    return {
        "trade_id": event["trade_id"],
        "internal_game_id": event.get("internal_game_id"),
        "source_experiment_id": event["source_experiment_id"],
        "negative_ev_class": event["negative_ev_class"],
        "ESS": pit.get("ESS") if pit.get("ESS") is not None else event.get("ESS"),
        "effective_neighbors": event.get("effective_neighbors"),
        "mean_distance": event.get("mean_distance"),
        "median_distance": event.get("median_distance"),
        "feature_coverage": event.get("feature_coverage"),
        "support_status": event.get("support_status"),
        "LOW_HISTORICAL_SUPPORT": event.get("support_status") == "LOW_HISTORICAL_SUPPORT",
        "path_coverage": event.get("path_coverage"),
    }


def support_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    def pack(group: list[dict[str, Any]]) -> dict[str, Any]:
        rows = [support_row(e) for e in group]
        n = len(rows)
        low = sum(1 for r in rows if r["LOW_HISTORICAL_SUPPORT"])
        return {
            "n": n,
            "LOW_HISTORICAL_SUPPORT_rate": None if not n else low / n,
            "mean_ESS": _mean([r["ESS"] for r in rows]),
            "mean_median_distance": _mean([r["median_distance"] for r in rows]),
            "mean_feature_coverage": _mean([r["feature_coverage"] for r in rows]),
        }

    temp = [e for e in events if e["negative_ev_class"] == TEMPORARY_NEGATIVE_EV]
    pers = [e for e in events if e["negative_ev_class"] == PERSISTENT_NEGATIVE_EV]
    return {
        "temporary": pack(temp),
        "persistent": pack(pers),
        "question": "Is apparent persistence merely an artifact of Austin being off-manifold?",
    }


def _mean(values: list[Any]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    return None if not nums else sum(nums) / len(nums)


def recovery_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    def pack(group: list[dict[str, Any]]) -> dict[str, Any]:
        rows = [recovery_row(e) for e in group]
        n = len(rows)
        if not n:
            return {"n": 0}
        return {
            "n": n,
            "EV_recovery_rate": sum(1 for r in rows if r["EV_recovered_ge_0"]) / n,
            "recover_ge_50": _mean([1.0 if r.get("future_recover_ge_50") else 0.0 for r in rows if r.get("future_recover_ge_50") is not None]),
            "recover_ge_60": _mean([1.0 if r.get("future_recover_ge_60") else 0.0 for r in rows if r.get("future_recover_ge_60") is not None]),
            "recover_ge_70": _mean([1.0 if r.get("future_recover_ge_70") else 0.0 for r in rows if r.get("future_recover_ge_70") is not None]),
            "recover_ge_80": _mean([1.0 if r.get("future_recover_ge_80") else 0.0 for r in rows if r.get("future_recover_ge_80") is not None]),
            "mean_time_to_EV_recovery": _mean([r["time_to_EV_recovery"] for r in rows]),
            "mean_future_MFE": _mean([r["future_MFE"] for r in rows]),
        }

    temp = [e for e in events if e["negative_ev_class"] == TEMPORARY_NEGATIVE_EV]
    pers = [e for e in events if e["negative_ev_class"] == PERSISTENT_NEGATIVE_EV]
    return {"temporary": pack(temp), "persistent": pack(pers)}


def downfall_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    def pack(group: list[dict[str, Any]]) -> dict[str, Any]:
        rows = [downfall_row(e) for e in group]
        n = len(rows)
        if not n:
            return {"n": 0}
        return {
            "n": n,
            "loss_rate": sum(1 for r in rows if r["terminal_loss"]) / n,
            "T40_rate": sum(1 for r in rows if r.get("future_T40")) / n,
            "mean_future_MAE": _mean([r["future_MAE"] for r in rows]),
            "mean_future_min_price": _mean([r["future_min_price"] for r in rows]),
            "mean_time_to_T40": _mean([r["time_to_T40"] for r in rows]),
            "mean_time_to_worst_price": _mean([r["time_to_worst_price"] for r in rows]),
        }

    temp = [e for e in events if e["negative_ev_class"] == TEMPORARY_NEGATIVE_EV]
    pers = [e for e in events if e["negative_ev_class"] == PERSISTENT_NEGATIVE_EV]
    return {"temporary": pack(temp), "persistent": pack(pers)}


def window_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("t0", "t1", "t2", "t3"):
        subset = [r for r in rows if r.get("landmark") == name]
        pers = [r for r in subset if r.get("negative_ev_class") == PERSISTENT_NEGATIVE_EV]
        out[name] = {
            "n": len(subset),
            "n_persistent": len(pers),
            "mean_price_at_landmark": _mean([r.get("price_at_landmark") for r in pers]),
            "mean_future_minimum_price": _mean([r.get("future_minimum_price") for r in pers]),
            "mean_adverse_cents_remaining": _mean([r.get("adverse_cents_remaining") for r in pers]),
            "mean_minutes_to_worst_price": _mean([r.get("game_clock_minutes_to_worst_price") for r in pers]),
            "mean_minutes_to_T40": _mean([r.get("game_clock_minutes_to_T40") for r in pers]),
        }
    return out


def warning_timing_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    losses = [r for r in rows if r.get("won") is False]
    pers = [r for r in rows if r.get("negative_ev_class") == PERSISTENT_NEGATIVE_EV]

    def rate(group: list[dict[str, Any]], key: str, label: str) -> dict[str, Any]:
        known = [r for r in group if r.get(key) not in (None, "UNAVAILABLE")]
        n = len(known)
        hit = sum(1 for r in known if r.get(key) == label)
        return {"n": n, "n_label": hit, "rate": None if not n else hit / n}

    return {
        "n_rows": len(rows),
        "n_losses": len(losses),
        "losses_t0_to_T40_before_damage": rate(losses, "t0_to_T40_class", "BEFORE_DAMAGE"),
        "losses_t1_to_T40_before_damage": rate(losses, "t1_negative_to_T40_class", "BEFORE_DAMAGE"),
        "losses_t2_to_T40_before_damage": rate(losses, "t2_negative_to_T40_class", "BEFORE_DAMAGE"),
        "losses_t0_to_worst_before_damage": rate(losses, "t0_to_worst_class", "BEFORE_DAMAGE"),
        "persistent_t0_to_T40_before_damage": rate(pers, "t0_to_T40_class", "BEFORE_DAMAGE"),
        "persistent_t1_to_T40_before_damage": rate(pers, "t1_negative_to_T40_class", "BEFORE_DAMAGE"),
        "persistent_t2_to_T40_before_damage": rate(pers, "t2_negative_to_T40_class", "BEFORE_DAMAGE"),
        "note": "Phase 2 mechanism timing. Does not replace Discovery AVAILABLE warning among losses.",
    }


def dynamics_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    def pack(group: list[dict[str, Any]], key: str) -> dict[str, Any]:
        vals = [e.get(key) for e in group if e.get(key) is not None]
        return {"n": len(vals), "mean": _mean(vals)}

    temp = [e for e in events if e["negative_ev_class"] == TEMPORARY_NEGATIVE_EV]
    pers = [e for e in events if e["negative_ev_class"] == PERSISTENT_NEGATIVE_EV]
    keys = ("mean_EV_depth", "mean_EV_velocity", "mean_EV_acceleration", "EV_velocity_t0_to_t1", "EV_acceleration_t0_t2")
    return {
        "temporary": {k: pack(temp, k) for k in keys},
        "persistent": {k: pack(pers, k) for k in keys},
        "note": "Descriptive only. Missing derivatives stay UNAVAILABLE. No cutoff search.",
    }


RECOVERY_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "negative_ev_class",
    "won",
    "EV_recovered_ge_0",
    "time_to_EV_recovery",
    "future_recover_ge_50",
    "future_recover_ge_60",
    "future_recover_ge_70",
    "future_recover_ge_80",
    "time_to_price_50",
    "time_to_price_60",
    "time_to_price_70",
    "time_to_price_80",
    "future_MFE",
    "future_max_price",
]

DOWNFALL_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "negative_ev_class",
    "won",
    "terminal_loss",
    "future_T40",
    "future_MAE",
    "future_min_price",
    "time_to_T40",
    "time_to_worst_price",
    "time_to_settlement",
    "pnl_hold_after_t0",
]

WINDOW_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "negative_ev_class",
    "landmark",
    "price_at_landmark",
    "future_minimum_price",
    "adverse_cents_remaining",
    "game_clock_minutes_to_worst_price",
    "game_clock_minutes_to_T40",
    "note",
]

SUPPORT_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "negative_ev_class",
    "ESS",
    "effective_neighbors",
    "mean_distance",
    "median_distance",
    "feature_coverage",
    "support_status",
    "LOW_HISTORICAL_SUPPORT",
    "path_coverage",
]
