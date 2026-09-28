#!/usr/bin/env python3
"""Build S_t blocks at FIRST-80 and on the alive post-entry panel.

Categories are preserved: game_ market_ path_ dyn_ econ_ coupling_ alignment_.
No post-horizon information in features. Coupling β frozen from TRAIN.
"""

from __future__ import annotations

import bisect
import pickle
import sys
from collections import defaultdict
from functools import lru_cache

import numpy as np

from common import (
    BARRIERS_CENTS,
    FEAT,
    MAX_ALIVE_MINUTES,
    OBS,
    OUT,
    Q_UNCONDITIONAL,
    audit,
    e4_to_cents,
    ev_from_q,
    load_crosswalk,
    read_parquet_rows,
    roc_auc,
    utc_now,
    write_json,
    write_parquet,
)
from pbp_align import (
    box_header,
    classify_confidence,
    enrich_actions,
    load_box,
    load_pbp,
    replay_residuals,
    snap_to_entry,
    team_scores,
)
from state_math import dstar, lsi, minutes_since_below, mom, pe, rng, stdev, u_game, vol_proxy


@lru_cache(maxsize=2048)
def enriched(nba_id: str):
    pbp = load_pbp(nba_id)
    header = box_header(load_box(nba_id))
    actions = enrich_actions((pbp or {}).get("game", {}).get("actions") or [], header)
    index = [i for i, a in enumerate(actions) if a["modeled_wall_ts"] is not None]
    ts = [actions[i]["modeled_wall_ts"] for i in index]
    return actions, tuple(index), tuple(ts), header, tuple(replay_residuals(actions))


def snap_at(actions, index, ts_list, t):
    if not ts_list:
        return None
    k = bisect.bisect_right(ts_list, t) - 1
    if k < 0:
        return None
    return actions[index[k]]


def game_remaining_s(row):
    if row is None:
        return None
    p, rem = row.get("period"), row.get("remaining_s")
    if p is None or rem is None:
        return None
    p = int(p)
    if p <= 4:
        return float(rem) + (4 - p) * 720.0
    return float(rem)


def score_at(pack, team_home, t):
    if pack is None or team_home is None:
        return None, None, None, None, None
    actions, index, ts_list, header, _ = pack
    row = snap_at(actions, list(index), list(ts_list), t)
    ts_, os_ = team_scores(row, team_home)
    return ts_, os_, row, game_remaining_s(row), row.get("period") if row else None


def window_scores(score_hist, t, minutes):
    """score_hist: list (ts, d, total) with ts<=current, last is now."""
    lo = t - minutes * 60
    return [h for h in score_hist if h[0] >= lo]


def vel_from_hist(hist, minutes):
    if len(hist) < 2:
        return None
    dt = (hist[-1][0] - hist[0][0]) / 60.0
    if dt <= 0:
        return None
    return (hist[-1][1] - hist[0][1]) / dt


def ols_beta(X, y):
    y = np.asarray(y, dtype=float)
    try:
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        return b
    except np.linalg.LinAlgError:
        return np.zeros(X.shape[1])


def pred_dk(beta, dd, tau):
    return float(beta[0] + beta[1] * dd + beta[2] * tau + beta[3] * dd * tau)


def prefix_write(path, rows, prefixes):
    out = []
    keys = {"trade_id", "state_timestamp", "dataset_split", "Y_40_CLOSE"}
    for r in rows:
        rec = {k: r.get(k) for k in keys if k in r}
        for k, v in r.items():
            if any(k.startswith(p) for p in prefixes):
                rec[k] = v
        out.append(rec)
    write_parquet(path, out)


def main() -> int:
    trades = read_parquet_rows(OBS / "first80_trades.parquet")
    if len(trades) != 1230:
        print("need 1230", file=sys.stderr)
        return 1
    quotes = pickle.loads((OUT / "_quotes_cache.pkl").read_bytes())
    xwalk = load_crosswalk()

    packed = []
    couple_y = []
    couple_X = []
    theta_zero = defaultdict(list)

    for tr in trades:
        series = quotes.get(tr["ticker"], [])
        entry = int(tr["entry_decision_time"])
        barrier = tr.get("first_40_close_ts")
        pre = [q for q in series if q["ts"] <= entry]
        post = [q for q in series if q["ts"] > entry]
        if barrier is not None:
            post = [q for q in post if q["ts"] < int(barrier)]
        if tr.get("close_ts") is not None:
            post = [q for q in post if q["ts"] <= int(tr["close_ts"])]
        post = post[:MAX_ALIVE_MINUTES]
        cw = xwalk.get(tr["event_id"]) or {}
        nba_id = cw.get("nba_game_id")
        code = (tr.get("team_code") or "").upper()
        home = (tr.get("home_team_code") or "").upper()
        team_home = True if code and code == home else (False if code else None)
        pack = None
        conf, reason, phase = "UNUSABLE", "NO_PBP", None
        if nba_id and cw.get("match_status") == "MATCHED":
            pack = enriched(nba_id)
            actions, index, ts_list, header, residuals = pack
            pack = (actions, list(index), list(ts_list), header, list(residuals))
            snap_meta = snap_to_entry(actions, entry)
            conf, reason = classify_confidence(actions, snap_meta, entry, header, list(residuals))
            phase = snap_meta.get("game_phase")
        packed.append((tr, pre, post, pack, team_home, conf, reason, phase))

        if tr["dataset_split"] != "TRAIN" or pack is None or team_home is None:
            continue
        seq = pre + post
        prev_k = prev_d = None
        prev_ts = None
        for q in seq:
            if q["bid_c"] is None:
                continue
            k = e4_to_cents(q["bid_c"])
            ts_s, os_, row, tau_g, _p = score_at(pack, team_home, q["ts"])
            d = None if ts_s is None else ts_s - os_
            tau_c = None if tr.get("close_ts") is None else (int(tr["close_ts"]) - q["ts"]) / 60.0
            if prev_k is not None and prev_d is not None and d is not None and tau_c is not None and prev_ts is not None:
                dtm = (q["ts"] - prev_ts) / 60.0
                if 0.5 <= dtm <= 2.5:
                    dk = k - prev_k
                    dd = d - prev_d
                    couple_y.append(dk)
                    couple_X.append([1.0, dd, tau_c, dd * tau_c, dd * dd])
                    if abs(dd) < 1e-9:
                        bucket = int(min(max(tau_c, 0), 179) // 15)
                        theta_zero[bucket].append(dk)
            prev_k, prev_d, prev_ts = k, d, q["ts"]

    Xc = np.asarray(couple_X, dtype=float) if couple_X else np.zeros((1, 5))
    yc = np.asarray(couple_y, dtype=float) if couple_y else np.zeros(1)
    beta_lin = ols_beta(Xc[:, :4], yc)
    beta_curv = ols_beta(Xc, yc)
    theta_by = {str(k): float(np.mean(v)) for k, v in sorted(theta_zero.items()) if v}
    write_json(
        OUT / "models" / "coupling" / "empirical_delta.json",
        {
            "written_utc": utc_now(),
            "n_train_steps": int(len(yc)),
            "beta_linear": ["intercept", "dd", "tau_contract_min", "dd_x_tau"],
            "beta": beta_lin.tolist(),
            "beta_curvature": beta_curv.tolist(),
            "empirical_theta_dK_given_dd0_by_15m_tau_bucket": theta_by,
            "not_black_scholes": True,
        },
    )

    entry_rows = []
    panel_rows = []
    barrier_rows = []

    for tr, pre, post, pack, team_home, conf, reason, phase in packed:
        entry = int(tr["entry_decision_time"])
        close_ts = tr.get("close_ts")
        y40 = int(tr["Y_40_CLOSE"])
        eidx = next((i for i, q in enumerate(pre) if q["ts"] == entry), len(pre) - 1 if pre else None)
        pre_c = [e4_to_cents(q["bid_c"]) for q in pre if q["bid_c"] is not None]
        # score history along pre
        score_hist = []
        lead_ch = 0
        prev_sign = None
        max_lead = max_def = None
        time_lead = time_trail = 0
        if pack is not None and team_home is not None:
            for q in pre:
                ts_s, os_, row, tau_g, per = score_at(pack, team_home, q["ts"])
                if ts_s is None:
                    continue
                d = ts_s - os_
                tot = ts_s + os_
                score_hist.append((q["ts"], d, tot, tau_g, per, ts_s, os_))
                if max_lead is None or d > max_lead:
                    max_lead = d
                if max_def is None or d < max_def:
                    max_def = d
                if d > 0:
                    time_lead += 1
                elif d < 0:
                    time_trail += 1
                sg = 0 if d == 0 else (1 if d > 0 else -1)
                if prev_sign is not None and sg != 0 and prev_sign != 0 and sg != prev_sign:
                    lead_ch += 1
                if sg != 0:
                    prev_sign = sg
        last_g = score_hist[-1] if score_hist else None
        d0 = last_g[1] if last_g else None
        tot0 = last_g[2] if last_g else None
        tau_g0 = last_g[3] if last_g else None
        per0 = last_g[4] if last_g else None
        hist5 = window_scores(score_hist, entry, 5)
        hist10 = window_scores(score_hist, entry, 10)
        hist3 = window_scores(score_hist, entry, 3)
        v5 = vel_from_hist(hist5, 5)
        v10 = vel_from_hist(hist10, 10)
        v1 = vel_from_hist(window_scores(score_hist, entry, 1), 1)
        # acceleration: 5m vel now vs 5m vel ending 5m earlier
        earlier = [h for h in score_hist if h[0] <= entry - 300]
        v5_prev = vel_from_hist(window_scores(earlier, entry - 300 if earlier else entry, 5), 5) if earlier else None
        acc = None if v5 is None or v5_prev is None else (v5 - v5_prev) / 5.0
        ds = [h[1] for h in hist5]
        ds10 = [h[1] for h in hist10]
        dds = np.diff(ds) if len(ds) >= 3 else None
        qe = pre[eidx] if eidx is not None and eidx >= 0 and pre else None
        k0 = e4_to_cents(qe["bid_c"]) if qe and qe["bid_c"] is not None else None
        a0 = e4_to_cents(qe["ask_c"]) if qe and qe["ask_c"] is not None else None
        mid = None if k0 is None or a0 is None else 0.5 * (k0 + a0)
        tau_c0 = None if close_ts is None else (int(close_ts) - entry) / 60.0
        dk1 = mom(pre, eidx, 1) if eidx is not None else None
        dk3 = mom(pre, eidx, 3) if eidx is not None else None
        dk5 = mom(pre, eidx, 5) if eidx is not None else None
        dk10 = mom(pre, eidx, 10) if eidx is not None else None
        dk15 = mom(pre, eidx, 15) if eidx is not None else None
        vol5 = vol_proxy(pre, eidx, 5) if eidx is not None else None
        vol15 = vol_proxy(pre, eidx, 15) if eidx is not None else None
        vol1 = vol_proxy(pre, eidx, 1) if eidx is not None else None
        vstar = None if dk5 is None or vol5 in (None, 0) else dk5 / (vol5 + 1e-6)
        # last-step residual
        dd1 = None
        if len(score_hist) >= 2:
            dd1 = score_hist[-1][1] - score_hist[-2][1]
        residual = None
        if dk1 is not None and dd1 is not None and tau_c0 is not None:
            residual = dk1 - pred_dk(beta_lin, dd1, tau_c0)
        # path to 80
        m50 = minutes_since_below(pre_c, 50)
        m60 = minutes_since_below(pre_c, 60)
        m70 = minutes_since_below(pre_c, 70)
        revs = 0
        if len(pre_c) >= 3:
            dlt = np.diff(pre_c)
            revs = int(sum(1 for a, b in zip(dlt[:-1], dlt[1:]) if a * b < 0))
        pe_m = pe(pre_c)
        pe_g = pe([h[1] for h in score_hist]) if len(score_hist) >= 2 else None
        swing = None
        if score_hist:
            ddpath = [h[1] for h in score_hist]
            swing = float(max(ddpath) - min(ddpath))
        game_ok = conf in ("HIGH", "MEDIUM") and d0 is not None
        rec = {
            "trade_id": tr["trade_id"],
            "event_id": tr["event_id"],
            "ticker": tr["ticker"],
            "game_date": tr["game_date"],
            "dataset_split": tr["dataset_split"],
            "Y_40_CLOSE": y40,
            "Y_40_WICK": tr["Y_40_WICK"],
            "eventual_winner": tr["eventual_winner"],
            "entry_timestamp": entry,
            "state_timestamp": entry,
            "feature_maximum_source_timestamp": entry,
            "same_bar_limitation": "SAME_BAR_1M_LIMITATION",
            "alignment_method": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
            "alignment_confidence": conf,
            "alignment_reason": reason,
            "game_phase": phase,
            "per_play_wall_clock_observed": False,
            "game_feature_status": "AVAILABLE" if game_ok else "UNAVAILABLE",
            "game_score_differential": d0,
            "game_abs_score_differential": None if d0 is None else abs(d0),
            "game_lead_indicator": None if d0 is None else int(d0 > 0),
            "game_trailing_indicator": None if d0 is None else int(d0 < 0),
            "game_largest_lead_so_far": max_lead,
            "game_largest_deficit_so_far": max_def,
            "game_d_star": dstar(d0, tau_g0),
            "game_total_points": tot0,
            "game_quarter": per0,
            "game_tau_remaining_s": tau_g0,
            "game_points_per_game_minute": None
            if tot0 is None or tau_g0 is None
            else tot0 / max((2880.0 - tau_g0) / 60.0, 0.25) if tau_g0 is not None and tau_g0 <= 2880 else None,
            "game_lead_changes_total": lead_ch,
            "game_lead_changes_last_5m": None,
            "game_lead_changes_last_10m": None,
            "game_time_spent_leading_candles": time_lead,
            "game_time_spent_trailing_candles": time_trail,
            "game_largest_swing": swing,
            "game_score_std_3m": stdev([h[1] for h in hist3]),
            "game_score_std_5m": stdev(ds),
            "game_score_std_10m": stdev(ds10),
            "game_score_range_3m": rng([h[1] for h in hist3]),
            "game_score_range_5m": rng(ds),
            "game_score_range_10m": rng(ds10),
            "game_delta_d_std": None if dds is None or len(dds) < 2 else float(np.std(dds, ddof=1)),
            "dyn_score_vel_1m": v1,
            "dyn_score_vel_5m": v5,
            "dyn_score_vel_10m": v10,
            "dyn_score_acc_5m": acc,
            "dyn_u_game": u_game(None if d0 is None else abs(d0), tau_g0, stdev(ds), lead_ch),
            "market_yes_bid_cents": k0,
            "market_yes_ask_cents": a0,
            "market_estimated_mid_cents": mid,
            "market_spread_cents": None if k0 is None or a0 is None else a0 - k0,
            "market_volume_hundredths": None if qe is None else qe.get("vol"),
            "market_distance_from_80_cents": None if k0 is None else k0 - 80.0,
            "market_distance_from_40_cents": None if k0 is None else k0 - 40.0,
            "dyn_market_mom_1m": dk1,
            "dyn_market_mom_3m": dk3,
            "dyn_market_mom_5m": dk5,
            "dyn_market_mom_10m": dk10,
            "dyn_market_mom_15m": dk15,
            "dyn_market_vol_1m": vol1,
            "dyn_market_vol_5m": vol5,
            "dyn_market_vol_15m": vol15,
            "dyn_market_mom_5m_normalized": vstar,
            "dyn_market_acc_5m": (
                None
                if dk5 is None or mom(pre, eidx, 10) is None
                else (2.0 * dk5 - mom(pre, eidx, 10)) / 5.0
            ),
            "path_minutes_50_to_80": m50,
            "path_minutes_60_to_80": m60,
            "path_minutes_70_to_80": m70,
            "path_n_reversals_pre80": revs,
            "path_efficiency_market": pe_m,
            "path_efficiency_game": pe_g,
            "path_n_pre80_candles": len(pre_c),
            "path_total_variation_cents": None
            if len(pre_c) < 2
            else float(sum(abs(b - a) for a, b in zip(pre_c, pre_c[1:]))),
            "econ_tau_contract_min": tau_c0,
            "econ_unrealized_mark_R": None if k0 is None else (k0 - 80.0) / 20.0,
            "econ_baseline_q": Q_UNCONDITIONAL,
            "econ_baseline_ev": ev_from_q(Q_UNCONDITIONAL),
            "econ_barrier_margin": (1.0 / 3.0) - Q_UNCONDITIONAL,
            "coupling_dd_last": dd1,
            "coupling_dK_last": dk1,
            "coupling_residual": residual,
            "coupling_sigma_x_abs_d": None if vol5 is None or d0 is None else vol5 * abs(d0),
            "coupling_sigma_x_vscore": None if vol5 is None or v5 is None else vol5 * v5,
            "coupling_sigma_x_tau": None if vol5 is None or tau_c0 is None else vol5 * tau_c0,
            "volatility_kind": "1-MINUTE CANDLE VOLATILITY PROXY",
        }
        # lead changes last 5/10m
        def lc_window(hist):
            n = 0
            ps = None
            for h in hist:
                sg = 0 if h[1] == 0 else (1 if h[1] > 0 else -1)
                if ps is not None and sg != 0 and ps != 0 and sg != ps:
                    n += 1
                if sg != 0:
                    ps = sg
            return n

        rec["game_lead_changes_last_5m"] = lc_window(hist5)
        rec["game_lead_changes_last_10m"] = lc_window(hist10)
        rec["game_reversal_10m"] = None if not hist10 or d0 is None else int(
            (hist10[0][1] > 0) != (d0 > 0) and hist10[0][1] != 0 and d0 != 0
        )
        rec["game_directional_asymmetry"] = None
        if len(score_hist) >= 3 and d0 is not None:
            rec["game_directional_asymmetry"] = float(d0 - score_hist[0][1]) - float(
                score_hist[-1][1] - score_hist[max(0, len(score_hist) // 2)][1]
            )
        entry_rows.append(rec)

        # barriers from quality post-entry closes (same rule family as frozen 40)
        full_post = [q for q in quotes.get(tr["ticker"], []) if q["ts"] > entry]
        if close_ts is not None:
            full_post = [q for q in full_post if q["ts"] <= int(close_ts)]
        post_c = []
        had_q = True
        for q in full_post:
            if not audit.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
                continue
            had_q = True
            c = e4_to_cents(q["bid_c"])
            if c is not None:
                post_c.append(c)
        brec = {
            "trade_id": tr["trade_id"],
            "dataset_split": tr["dataset_split"],
            "Y_40_CLOSE": y40,
            "hit_90_recover": int(any(c >= 90 for c in post_c)),
            "settle_yes": int(bool(tr["eventual_winner"])),
            "settle_no": int(not bool(tr["eventual_winner"])),
            "min_post_close_cents": None if not post_c else float(min(post_c)),
            "time_to_40_min": None
            if not y40 or tr.get("first_40_close_ts") is None
            else (int(tr["first_40_close_ts"]) - entry) / 60.0,
            "barrier_quote_rule": "audit.quality then yes_bid_close",
        }
        for x in BARRIERS_CENTS:
            brec[f"hit_{x}"] = int(any(c <= x for c in post_c))
        barrier_rows.append(brec)

        # panel (alive minutes after entry, before close-path 40)
        A = F = 0.0
        k_ent = k0
        kmax = k0
        kmin = k0
        prev_k = k0
        prev_dd = 0.0
        sh = list(score_hist)
        for q in post:
            if q["bid_c"] is None:
                continue
            k = e4_to_cents(q["bid_c"])
            ts = int(q["ts"])
            if prev_k is not None:
                dlt = k - prev_k
                A += max(-dlt, 0)
                F += max(dlt, 0)
            if kmax is None or k > kmax:
                kmax = k
            if kmin is None or k < kmin:
                kmin = k
            dd = None if kmax is None else kmax - k
            dd_v = None if prev_dd is None or dd is None else dd - prev_dd
            ts_s, os_, row, tau_g, per = (
                score_at(pack, team_home, ts) if pack else (None, None, None, None, None)
            )
            d = None if ts_s is None else ts_s - os_
            if d is not None:
                sh.append((ts, d, (ts_s + os_), tau_g, per, ts_s, os_))
            h5 = window_scores(sh, ts, 5)
            v5p = vel_from_hist(h5, 5)
            tau_c = None if close_ts is None else (int(close_ts) - ts) / 60.0
            dk1p = None if prev_k is None else k - prev_k
            ddp = None
            if len(sh) >= 2:
                ddp = sh[-1][1] - sh[-2][1]
            resid = None
            if dk1p is not None and ddp is not None and tau_c is not None:
                resid = dk1p - pred_dk(beta_lin, ddp, tau_c)
            b40 = tr.get("first_40_close_ts")

            def hz(mins):
                if b40 is None:
                    return 0
                dt = int(b40) - ts
                return int(0 < dt <= mins * 60)

            panel_rows.append(
                {
                    "trade_id": tr["trade_id"],
                    "dataset_split": tr["dataset_split"],
                    "entry_timestamp": entry,
                    "state_timestamp": ts,
                    "feature_maximum_source_timestamp": ts,
                    "minutes_since_entry": (ts - entry) / 60.0,
                    "alive_above_40": 1,
                    "Y_40_CLOSE": y40,
                    "H_40_5M": hz(5),
                    "H_40_10M": hz(10),
                    "H_40_20M": hz(20),
                    "H_40_30M": hz(30),
                    "H_40_60M": hz(60),
                    "alignment_confidence": conf,
                    "game_feature_status": (
                        "AVAILABLE"
                        if conf in ("HIGH", "MEDIUM") and d is not None
                        else "UNAVAILABLE"
                    ),
                    "game_score_differential": d,
                    "dyn_score_vel_5m": v5p,
                    "market_yes_bid_cents": k,
                    "market_distance_from_40_cents": None if k is None else k - 40.0,
                    "path_A_adverse": A,
                    "path_F_favorable": F,
                    "path_PA": A / (A + F + 1e-9),
                    "path_MAE_cents": None if k_ent is None or kmin is None else kmin - k_ent,
                    "path_MFE_cents": None if k_ent is None or kmax is None else kmax - k_ent,
                    "path_DD_cents": dd,
                    "dyn_DD_velocity": dd_v,
                    "econ_unrealized_mark_R": None if k is None else (k - 80.0) / 20.0,
                    "econ_tau_contract_min": tau_c,
                    "coupling_residual": resid,
                    "same_bar_limitation": "SAME_BAR_1M_LIMITATION",
                }
            )
            prev_k = k
            prev_dd = dd if dd is not None else prev_dd

    # LSI TRAIN grid
    tr_mask = np.array([r["dataset_split"] == "TRAIN" for r in entry_rows])
    y = np.array([r["Y_40_CLOSE"] for r in entry_rows], dtype=float)
    best = (None, None, -1.0)
    for lam in (0.5, 1.0, 2.0):
        for gam in (0.5, 1.0, 2.0):
            xs = np.array(
                [
                    lsi(
                        r.get("game_abs_score_differential"),
                        r.get("game_score_std_5m"),
                        r.get("dyn_score_vel_5m"),
                        r.get("dyn_score_acc_5m"),
                        lam,
                        gam,
                    )
                    if r["dataset_split"] == "TRAIN"
                    else np.nan
                    for r in entry_rows
                ],
                dtype=float,
            )
            m = tr_mask & np.isfinite(xs)
            if np.sum(m) < 200:
                continue
            auc = roc_auc(y[m], -xs[m])  # high LSI → lower barrier risk
            if auc is not None and auc > best[2]:
                best = (lam, gam, auc)
    lam_f, gam_f = (1.0, 1.0) if best[0] is None else (best[0], best[1])
    for r in entry_rows:
        r["game_lsi"] = lsi(
            r.get("game_abs_score_differential"),
            r.get("game_score_std_5m"),
            r.get("dyn_score_vel_5m"),
            r.get("dyn_score_acc_5m"),
            lam_f,
            gam_f,
        )
        r["game_lsi_lambda"] = lam_f
        r["game_lsi_gamma"] = gam_f
        vol = r.get("dyn_market_vol_5m")
        ad = r.get("game_abs_score_differential")
        vs = r.get("dyn_score_vel_5m")
        res = r.get("coupling_residual")
        tau = r.get("econ_tau_contract_min")
        lsi_v = r.get("game_lsi")
        d80 = r.get("market_distance_from_80_cents")
        r["ix_vol_mkt_x_abs_d"] = None if vol is None or ad is None else vol * ad
        r["ix_vol_mkt_x_vscore"] = None if vol is None or vs is None else vol * vs
        r["ix_residual_x_tau"] = None if res is None or tau is None else res * tau
        r["ix_lsi_x_dist80"] = None if lsi_v is None or d80 is None else lsi_v * d80

    # TRAIN percentile regimes
    def pctl(key, p, lo=None, hi=None):
        xs = [
            r[key]
            for r, t in zip(entry_rows, tr_mask)
            if t and r.get(key) is not None
        ]
        if len(xs) < 20:
            return None
        return float(np.quantile(xs, p))

    d_hi = pctl("game_score_differential", 0.75) or 8.0
    sig_lo = pctl("game_score_std_5m", 0.50) or 2.0
    sig_hi = pctl("game_score_std_5m", 0.75) or 4.0
    v_lo = pctl("dyn_score_vel_5m", 0.25) or -0.5
    r_med = pctl("coupling_residual", 0.50) or 0.0
    r_hi = pctl("coupling_residual", 0.10) or -2.0  # large negative residual
    vm_hi = pctl("dyn_market_mom_5m", 0.10) or -3.0
    d_lo = pctl("game_abs_score_differential", 0.25) or 3.0
    lc_hi = pctl("game_lead_changes_last_10m", 0.75) or 2
    vol_hi = pctl("dyn_market_vol_5m", 0.75) or 2.0
    for r in entry_rows:
        d = r.get("game_score_differential")
        sig = r.get("game_score_std_5m")
        vs = r.get("dyn_score_vel_5m")
        res = r.get("coupling_residual")
        vm = r.get("dyn_market_mom_5m")
        lc = r.get("game_lead_changes_last_10m")
        vol = r.get("dyn_market_vol_5m")
        ad = r.get("game_abs_score_differential")
        label = "OTHER"
        if (
            d is not None
            and d >= d_hi
            and sig is not None
            and sig <= sig_lo
            and (vs is None or vs >= -0.05)
            and (res is None or abs(res) <= abs(r_med) + 2)
        ):
            label = "A_STABLE_DOMINANCE"
        elif d is not None and d > 0 and vs is not None and vs < v_lo and sig is not None and sig > sig_hi and vm is not None and vm < 0:
            label = "B_FRAGILE_LEAD"
        elif vs is not None and abs(vs) < 0.05 and res is not None and res < r_hi and vm is not None and vm < vm_hi:
            label = "C_MARKET_SHOCK"
        elif vs is not None and vs < v_lo and vm is not None and vm < vm_hi:
            label = "D_GAME_SHOCK"
        elif ad is not None and ad <= d_lo and lc is not None and lc >= lc_hi and vol is not None and vol >= vol_hi:
            label = "E_TURBULENT"
        r["regime"] = label
        r["regime_source"] = "TRAIN_PERCENTILES_FROZEN"

    write_json(
        OUT / "models" / "regimes" / "boundaries.json",
        {
            "written_utc": utc_now(),
            "lsi_lambda": lam_f,
            "lsi_gamma": gam_f,
            "lsi_train_auc_negated": None if best[0] is None else best[2],
            "d_hi": d_hi,
            "sig_lo": sig_lo,
            "sig_hi": sig_hi,
            "v_lo": v_lo,
            "residual_hi_adverse": r_hi,
            "note": "Boundaries from TRAIN only. Interpretable, not K-means.",
        },
    )
    write_parquet(OBS / "first80_game_state.parquet", entry_rows)
    write_parquet(OBS / "dynamic_state_panel.parquet", panel_rows)
    write_parquet(OBS / "barrier_distribution.parquet", barrier_rows)
    prefix_write(FEAT / "game_state_features.parquet", entry_rows, ("game_", "dyn_score", "dyn_u"))
    prefix_write(FEAT / "market_state_features.parquet", entry_rows, ("market_", "dyn_market"))
    prefix_write(FEAT / "path_features.parquet", entry_rows, ("path_",))
    prefix_write(FEAT / "coupling_features.parquet", entry_rows, ("coupling_", "ix_"))
    prefix_write(FEAT / "economic_features.parquet", entry_rows, ("econ_", "regime"))
    write_json(
        OUT / "state_build_summary.json",
        {
            "written_utc": utc_now(),
            "n_entry": len(entry_rows),
            "n_panel": len(panel_rows),
            "game_available": sum(1 for r in entry_rows if r.get("game_feature_status") == "AVAILABLE"),
            "coupling_n_train_steps": int(len(yc)),
            "lsi_lambda": lam_f,
            "lsi_gamma": gam_f,
        },
    )
    print(f"entry={len(entry_rows)} panel={len(panel_rows)} couple_n={len(yc)} LSI λ={lam_f} γ={gam_f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
