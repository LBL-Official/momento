"""Construct DRE V2 state vector X_n from the frozen PADE panel.

As-of only. Does not rebuild possessions or alignment.
Does not interpret timeActual as modeled time.
"""

from __future__ import annotations

from collections import defaultdict

from . import config as C


def _f(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def build_state_panel(pade_rows: list[dict]) -> list[dict]:
    """Add DRE clocks and as-of features. Preserve PADE labels for evaluation."""
    by_trade: dict[str, list[dict]] = defaultdict(list)
    for r in pade_rows:
        by_trade[r["trade_id"]].append(r)
    out: list[dict] = []
    for _tid, rows in by_trade.items():
        rows.sort(key=lambda x: (x.get("possessions_since_entry") or 0, x.get("possession_index") or 0))
        unique_obs: list[tuple] = []
        peak_price = None
        last_poss_price = None
        last_poss_unique_n = 0
        price_hist_unique: list[float] = []
        for r in rows:
            s = dict(r)
            entry = _f(r.get("entry_price"))
            if entry is None:
                entry = float(C.ENTRY_CENTS)
            cur = _f(r.get("current_price"))
            bid = _f(r.get("A1_yes_bid"))
            ask = _f(r.get("A1_yes_ask"))
            det = _f(r.get("deterioration_absolute"))
            max_det = _f(r.get("max_deterioration_since_entry"))
            ts = r.get("market_observation_timestamp")

            if cur is not None:
                if peak_price is None or cur > peak_price:
                    peak_price = cur
            if ts is not None and (not unique_obs or unique_obs[-1][0] != ts):
                unique_obs.append((ts, cur))
                if cur is not None:
                    price_hist_unique.append(cur)

            unique_n = len(unique_obs)
            chg1 = chg2 = chg3 = None
            if len(price_hist_unique) >= 2:
                chg1 = price_hist_unique[-1] - price_hist_unique[-2]
            if len(price_hist_unique) >= 3:
                chg2 = price_hist_unique[-1] - price_hist_unique[-3]
            if len(price_hist_unique) >= 4:
                chg3 = price_hist_unique[-1] - price_hist_unique[-4]

            rec_from_max = None
            if max_det is not None and det is not None:
                rec_from_max = max_det - det
            dist_entry = None
            if cur is not None:
                dist_entry = cur - entry
            dist_peak = None
            if cur is not None and peak_price is not None:
                dist_peak = cur - peak_price

            vel_1p = None
            vel_1p_valid = False
            if (
                last_poss_price is not None
                and cur is not None
                and unique_n > last_poss_unique_n
            ):
                vel_1p = cur - last_poss_price
                vel_1p_valid = True

            age = _f(r.get("market_age_seconds"))
            entry_ts = _f(r.get("entry_timestamp"))
            pos_age = _f(r.get("position_age_wall_s"))
            real_ts = None
            if entry_ts is not None and pos_age is not None:
                real_ts = entry_ts + pos_age
            elif ts is not None:
                real_ts = float(ts)

            period = _i(r.get("period"))
            is_ot = bool(r.get("is_overtime"))
            a1_off = r.get("is_A1_team_offense")
            score_diff = _i(r.get("score_differential_from_A1"))
            team_score = None
            opp_score = None
            sh = _i(r.get("score_home"))
            sa = _i(r.get("score_away"))
            if sh is not None and sa is not None and score_diff is not None:
                # A1 differential is already from A1's perspective.
                if score_diff == (sh - sa) or score_diff == (sa - sh):
                    if score_diff == (sh - sa):
                        team_score, opp_score = sh, sa
                    else:
                        team_score, opp_score = sa, sh

            s.update(
                {
                    "schema_version_dre": C.SCHEMA_VERSION,
                    "entry_price_e4": C.ENTRY_E4,
                    "entry_price_cents": C.ENTRY_CENTS,
                    "current_price_e4": C.cents_to_e4(cur) if cur is not None else None,
                    "current_price_dollars": (cur / 100.0) if cur is not None else None,
                    "current_price_cents": int(round(cur)) if cur is not None else None,
                    "deterioration_e4": C.cents_to_e4(det) if det is not None else None,
                    "deterioration_cents": int(round(det)) if det is not None else None,
                    "deterioration_pct_of_entry": _f(r.get("deterioration_percent_of_entry")),
                    "position_side": "YES",
                    "original_notional_proxy_cents": C.ENTRY_CENTS,
                    "current_yes_bid_e4": C.cents_to_e4(bid) if bid is not None else None,
                    "current_yes_ask_e4": C.cents_to_e4(ask) if ask is not None else None,
                    "spread_e4": C.cents_to_e4((ask - bid) if ask is not None and bid is not None else None),
                    "unique_market_observations_since_entry": unique_n,
                    "market_price_change_1_observation": chg1,
                    "market_price_change_2_observations": chg2,
                    "market_price_change_3_observations": chg3,
                    "market_price_change_1_valid": chg1 is not None,
                    "market_price_change_2_valid": chg2 is not None,
                    "market_price_change_3_valid": chg3 is not None,
                    "deterioration_current": det,
                    "deterioration_max_to_date": max_det,
                    "deterioration_recent": chg1 if chg1 is not None and chg1 < 0 else (0.0 if chg1 is not None else None),
                    "recovery_from_max_drawdown": rec_from_max,
                    "distance_from_entry": dist_entry,
                    "distance_from_prior_peak": dist_peak,
                    "velocity_1_possession": vel_1p,
                    "velocity_1_possession_valid": vel_1p_valid,
                    "velocity_3_possessions": _f(r.get("v_3")),
                    "velocity_5_possessions": _f(r.get("v_5")),
                    "velocity_valid_1": bool(r.get("velocity_valid_1")),
                    "velocity_valid_3": bool(r.get("velocity_valid_3")),
                    "velocity_valid_5": bool(r.get("velocity_valid_5")),
                    "market_observation_velocity": _f(r.get("v_1")),
                    "acceleration_3_possessions": _f(r.get("a_3_1")),
                    "acceleration_5_possessions": _f(r.get("a_5_3")),
                    "acceleration_short": _f(r.get("a_short")),
                    "acceleration_valid_short": r.get("a_short") is not None,
                    "period_type": "OVERTIME" if is_ot else "REGULATION",
                    "game_clock_remaining_seconds": _f(r.get("game_seconds_remaining")),
                    "absolute_score_differential": _i(r.get("score_differential_absolute")),
                    "team_score": team_score,
                    "opponent_score": opp_score,
                    "possession_team": r.get("offensive_team"),
                    "is_position_team_in_possession": bool(a1_off) if a1_off is not None else None,
                    "raw_possessions_elapsed": r.get("possessions_since_entry"),
                    "estimated_remaining_possessions": _f(r.get("estimated_possessions_remaining_r2")),
                    "remaining_possessions_model_version": "PADE_V1_R2",
                    "remaining_possessions_confidence": "ESTIMATE_BIASED",
                    "actual_remaining_possessions_eval_only": r.get("actual_remaining_possessions"),
                    "real_time_timestamp": real_ts,
                    "real_time_source": "entry_timestamp + position_age_wall_s",
                    "market_implied_p_yes_proxy": (cur / 100.0) if cur is not None else None,
                    "stale_market_flag": bool(age is not None and age > 60.0),
                    "alignment_usable": (r.get("alignment_confidence") or "") in C.USABLE_ALIGNMENT,
                    "clock_real_time": real_ts,
                    "clock_game": r.get("game_clock"),
                    "clock_possession_index": r.get("possession_index"),
                    "clock_market_age_seconds": age,
                    "feature_availability": "AS_OF_STATE",
                    "execution_claim": "CANDLE_PATH_NOT_FILL",
                }
            )
            out.append(s)
            last_poss_price = cur
            last_poss_unique_n = unique_n
    return out


def panel_counts(rows: list[dict]) -> dict:
    trades = {r["trade_id"] for r in rows}
    events = {r["event_id"] for r in rows}
    splits = {}
    for s in ("TRAIN", "VALIDATION", "OOS"):
        xs = [r for r in rows if r.get("dataset_split") == s]
        splits[s] = {
            "rows": len(xs),
            "trades": len({r["trade_id"] for r in xs}),
            "games": len({r["event_id"] for r in xs}),
        }
    usable = [r for r in rows if r.get("alignment_usable") and r.get("current_price") is not None]
    return {
        "panel_rows": len(rows),
        "panel_trades": len(trades),
        "panel_games": len(events),
        "usable_high_medium_rows": len(usable),
        "usable_trades": len({r["trade_id"] for r in usable}),
        "splits": splits,
    }
