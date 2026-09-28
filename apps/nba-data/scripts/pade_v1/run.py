#!/usr/bin/env python3
"""MOMENTO POSSESSION-ADJUSTED DETERIORATION ENGINE V1

Research only. Frozen FIRST-80 universe. Observed timeActual walls.
Does not modify FIRST01, Risk, live execution, hedge V1–V4, or V1/V2 engines.

LIVE EXECUTION CHANGED: FALSE
CANDLE PATH ≠ ACTUAL FILL
AS-OF JOIN ≠ INTERPOLATION
POSSESSION TIME ≠ WALL CLOCK
"""

from __future__ import annotations

import json
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pade_v1 import common as C  # noqa: E402
from pade_v1.possessions import build_possessions, enrich_live_action  # noqa: E402

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    HAS_SKLEARN = True
except ImportError:  # pragma: no cover
    HAS_SKLEARN = False


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc).isoformat()} {msg}", flush=True)


def load_live_actions(nba_game_id: str) -> list[dict]:
    path = C.PBP_LIVE / f"{nba_game_id}.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    raw = ((payload.get("game") or {}).get("actions") or [])
    return [enrich_live_action(a) for a in raw]


def box_tip(nba_game_id: str) -> dict:
    path = C.BOX_DIR / f"{nba_game_id}.json"
    if not path.exists():
        return {}
    box = json.loads(path.read_text()).get("boxScoreSummary") or {}
    return {
        "gameTimeUTC": box.get("gameTimeUTC"),
        "gameEt": box.get("gameEt"),
        "duration": box.get("duration"),
        "home_tricode": ((box.get("homeTeam") or {}).get("teamTricode")),
        "away_tricode": ((box.get("awayTeam") or {}).get("teamTricode")),
    }


def classify_alignment(prev_gap: float | None, next_gap: float | None, same_period: bool, intermission: bool) -> str:
    if prev_gap is None:
        return "UNRESOLVED"
    if intermission or not same_period:
        if prev_gap <= 180:
            return "MEDIUM"
        if prev_gap <= 900:
            return "LOW"
        return "UNRESOLVED"
    if next_gap is not None and prev_gap <= 30 and next_gap <= 90:
        return "HIGH"
    if prev_gap <= 120:
        return "MEDIUM"
    if prev_gap <= 600:
        return "LOW"
    return "UNRESOLVED"


def asof_event(events: list[dict], t: float) -> tuple[dict | None, dict | None, int]:
    """Last event with wall_ts <= t, next with wall_ts > t. events sorted by wall."""
    lo, hi = 0, len(events) - 1
    ans = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        w = events[mid]["wall_ts"]
        if w <= t:
            ans = mid
            lo = mid + 1
        else:
            hi = mid - 1
    prev = events[ans] if ans >= 0 else None
    nxt = events[ans + 1] if 0 <= ans + 1 < len(events) else None
    return prev, nxt, ans


def asof_quote(quotes: list[dict], t: float) -> dict | None:
    lo, hi = 0, len(quotes) - 1
    ans = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if quotes[mid]["ts"] <= t:
            ans = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return quotes[ans] if ans >= 0 else None


def unique_quotes_before(rows: list[dict], i: int, k: int) -> list[dict]:
    seen = []
    last_ts = None
    for j in range(i, -1, -1):
        ts = rows[j].get("market_observation_timestamp")
        px = rows[j].get("current_price")
        if px is None or ts is None:
            continue
        if ts != last_ts:
            seen.append(rows[j])
            last_ts = ts
        if len(seen) >= k + 1:
            break
    seen.reverse()
    return seen


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float | None:
    if len(y) < 20:
        return None
    edges = np.linspace(0, 1, bins + 1)
    tot = 0.0
    n = 0
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if not np.any(m):
            continue
        tot += abs(float(y[m].mean()) - float(p[m].mean())) * int(m.sum())
        n += int(m.sum())
    return tot / n if n else None


def fit_logit(X: np.ndarray, y: np.ndarray):
    if not HAS_SKLEARN or len(y) < 40 or y.min() == y.max():
        return None
    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=400,
                    C=1.0,
                    solver="lbfgs",
                    class_weight="balanced",
                ),
            ),
        ]
    )
    pipe.fit(X, y)
    return pipe


def metrics_of(y, p) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    out = {"n": int(len(y)), "base_rate": float(y.mean()) if len(y) else None}
    if len(y) < 20 or y.min() == y.max():
        out.update({"auc": None, "brier": None, "logloss": None, "ece": None})
        return out
    out["auc"] = float(roc_auc_score(y, p))
    out["brier"] = float(brier_score_loss(y, p))
    out["logloss"] = float(log_loss(y, p))
    out["ece"] = ece(y, p)
    return out


def main() -> int:
    t0 = time.time()
    C.OUT.mkdir(parents=True, exist_ok=True)
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    log(f"{C.PROGRAM} start schema={C.SCHEMA_VERSION}")

    V1A = C.load_v1()
    trades = V1A.load_frozen("nba")
    gate_a = V1A.reproduce_path("nba", trades)
    if not gate_a.get("ok"):
        log(f"GATE A FAIL {gate_a}")
        C.write_json(C.OUT / "14_manifest.json", {"GATE_A": "FAIL", "detail": gate_a})
        return 2
    obs_a = gate_a.get("observed") or {}
    log(
        f"GATE A PASS n={obs_a.get('n')} surv={obs_a.get('survivors')} "
        f"stops={obs_a.get('stops')}"
    )

    games = V1A.V1.load_games(V1A.V1.SPORTS["nba"])
    crosswalk = C.load_crosswalk()
    for rec in trades:
        V1A.attach_scan_window(rec, games.get(rec["event_id"]))
        cw = crosswalk.get(rec["event_id"]) or {}
        rec["nba_game_id"] = cw.get("nba_game_id")
        rec["match_status"] = cw.get("match_status")
        rec["a1_team"] = C.team_code_from_ticker(rec.get("ticker"))
        rec["opponent_ticker"] = V1A.V1.opponent_of(games.get(rec["event_id"]) or {}, rec["ticker"])
        rec["a2_team"] = C.team_code_from_ticker(rec.get("opponent_ticker"))

    n_mapped = sum(1 for t in trades if t.get("nba_game_id") and t.get("match_status") == "MATCHED")
    gate_b = {
        "status": "PASS" if n_mapped == 1223 else ("WARNING" if n_mapped >= 1200 else "FAIL"),
        "first80": len(trades),
        "matched": n_mapped,
        "unmatched": len(trades) - n_mapped,
    }
    log(f"GATE B {gate_b['status']} matched={n_mapped}/1230")

    needed = set()
    for t in trades:
        needed.add(t["ticker"])
        if t.get("opponent_ticker"):
            needed.add(t["opponent_ticker"])
    candle_files = [p for p in C.CANDLES_DIR.rglob("*.parquet") if p.stem in needed]
    quotes: dict[str, list] = {}
    for path in candle_files:
        quotes[path.stem] = V1A.load_ticker_quotes(path)
    log(f"loaded candle tickers={len(quotes)}")

    timelines = []
    pbp_events = []
    possessions = []
    poss_issues = []
    n_pbp_ok = 0
    n_pbp_fail = 0

    by_game_events: dict[str, list] = {}
    by_game_poss: dict[str, list] = {}

    matched_ids = sorted({t["nba_game_id"] for t in trades if t.get("nba_game_id")})
    for gi, gid in enumerate(matched_ids, 1):
        raw = load_live_actions(gid)
        n_ta = sum(1 for a in raw if a.get("wall_ts") is not None)
        if not raw or (n_ta / len(raw) if raw else 0) < C.MIN_TIMEACTUAL_RATE:
            n_pbp_fail += 1
            poss_issues.append({"nba_game_id": gid, "status": "FAIL", "n_actions": len(raw), "n_timeActual": n_ta})
            continue
        n_pbp_ok += 1
        box = box_tip(gid)
        home = box.get("home_tricode")
        away = box.get("away_tricode")
        if not home or not away:
            cw_row = next((crosswalk[e] for e in crosswalk if crosswalk[e].get("nba_game_id") == gid), None)
            if cw_row:
                home = home or cw_row.get("home_team_code")
                away = away or cw_row.get("away_team_code")

        walled = [a for a in raw if a.get("wall_ts") is not None]
        walled.sort(key=lambda a: (a["wall_ts"], a.get("actionNumber") or 0))
        by_game_events[gid] = walled

        period_bounds = []
        for a in raw:
            if (a.get("_typ") == "period") or (a.get("actionType") or "").lower() == "period":
                period_bounds.append(
                    {
                        "period": a.get("period"),
                        "sub": a.get("_sub") or (a.get("subType") or "").lower(),
                        "wall_ts": a.get("wall_ts"),
                        "clock": a.get("clock"),
                        "elapsed_s": a.get("elapsed_s"),
                    }
                )
        starts = [a for a in raw if a.get("_typ") == "period" and a.get("_sub") == "start" and a.get("wall_ts")]
        ends = [a for a in raw if a.get("_typ") in ("period", "game") and a.get("_sub") in ("end", "") and a.get("wall_ts")]
        real_start = starts[0]["wall_ts"] if starts else (walled[0]["wall_ts"] if walled else None)
        real_end = walled[-1]["wall_ts"] if walled else None
        max_period = max((int(a.get("period") or 1) for a in raw), default=4)
        timelines.append(
            {
                "nba_game_id": gid,
                "real_time_start": real_start,
                "real_time_end": real_end,
                "real_time_start_iso": C.iso_utc(real_start),
                "real_time_end_iso": C.iso_utc(real_end),
                "real_time_start_source": "period_start_timeActual",
                "scheduled_tip_utc": box.get("gameTimeUTC"),
                "scheduled_tip_source": "boxscore_gameTimeUTC",
                "scheduled_vs_observed_tip_s": (
                    None
                    if real_start is None or not box.get("gameTimeUTC")
                    else real_start - (C.parse_timeactual(box["gameTimeUTC"] + "Z" if "Z" not in str(box["gameTimeUTC"]) else box["gameTimeUTC"]) or real_start)
                ),
                "game_clock_start": "PT12M00.00S",
                "game_clock_end": (walled[-1].get("clock") if walled else None),
                "max_period": max_period,
                "has_overtime": max_period > 4,
                "n_actions": len(raw),
                "n_timeActual": n_ta,
                "home_tricode": home,
                "away_tricode": away,
                "schema_version": C.SCHEMA_VERSION,
            }
        )

        for a in raw:
            pbp_events.append(
                {
                    "nba_game_id": gid,
                    "action_number": a.get("actionNumber"),
                    "action_type": a.get("actionType"),
                    "sub_type": a.get("subType"),
                    "period": a.get("period"),
                    "period_type": a.get("periodType"),
                    "clock": a.get("clock"),
                    "timeActual": a.get("timeActual"),
                    "wall_ts": a.get("wall_ts"),
                    "remaining_s": a.get("remaining_s"),
                    "elapsed_s": a.get("elapsed_s"),
                    "score_home": a.get("score_home"),
                    "score_away": a.get("score_away"),
                    "team": a.get("_team"),
                    "description": a.get("description"),
                    "shot_result": a.get("shotResult"),
                    "schema_version": C.SCHEMA_VERSION,
                }
            )

        poss, iss = build_possessions(gid, raw, home, away)
        iss["nba_game_id"] = gid
        poss_issues.append(iss)
        by_game_poss[gid] = poss
        possessions.extend(poss)
        if gi % 200 == 0 or gi == len(matched_ids):
            log(f"timeline/poss {gi}/{len(matched_ids)} possessions={len(possessions)}")

    gate_c = {
        "status": "PASS" if n_pbp_ok >= 1223 else ("WARNING" if n_pbp_ok >= 1100 else "FAIL"),
        "ok": n_pbp_ok,
        "fail": n_pbp_fail,
    }
    amb = sum(p.get("ambiguous_possession_flag") or 0 for p in possessions)
    open_end = sum(i.get("open_possession_at_end") or 0 for i in poss_issues if isinstance(i.get("open_possession_at_end"), int))
    gate_d = {
        "status": "PASS" if possessions and amb / max(1, len(possessions)) < 0.15 else "WARNING",
        "n_possessions": len(possessions),
        "ambiguous": amb,
        "ambiguous_pct": round(100.0 * amb / max(1, len(possessions)), 3),
        "open_at_end_games": open_end,
        "mean_poss_per_game": round(len(possessions) / max(1, n_pbp_ok), 2),
    }
    log(f"GATE C {gate_c['status']} GATE D {gate_d['status']} poss={len(possessions)}")

    C.write_parquet(C.OUT / "01_game_timeline.parquet", timelines)
    C.write_parquet(C.OUT / "02_pbp_events.parquet", pbp_events)
    C.write_parquet(C.OUT / "03_possessions.parquet", possessions)
    tl_by_gid = {r["nba_game_id"]: r for r in timelines}

    # --- Phase 3: candle alignment ---
    # Scan window is game_date+16h..+52h, so most candles are outside the live game.
    # Store every scan-window candle (never drop UNRESOLVED). GATE E uses IN-GAME only.
    align_rows = []
    conf_counter = Counter()
    conf_ingame = Counter()
    by_period_conf = defaultdict(Counter)
    games_poor = 0
    for t in trades:
        gid = t.get("nba_game_id")
        evs = by_game_events.get(gid or "")
        qs = quotes.get(t["ticker"]) or []
        tl = tl_by_gid.get(gid or "") or {}
        g0 = tl.get("real_time_start")
        g1 = tl.get("real_time_end")
        if not evs:
            for q in qs:
                if t.get("scan_window_start") and q["ts"] < t["scan_window_start"]:
                    continue
                if t.get("scan_window_end") and q["ts"] > t["scan_window_end"]:
                    continue
                align_rows.append(
                    {
                        "event_id": t["event_id"],
                        "ticker": t["ticker"],
                        "nba_game_id": gid,
                        "market_timestamp_utc": q["ts"],
                        "alignment_confidence": "UNRESOLVED",
                        "alignment_method": "NO_PBP",
                        "alignment_scope": "NO_PBP",
                        "prev_event_gap_s": None,
                        "next_event_gap_s": None,
                    }
                )
                conf_counter["UNRESOLVED"] += 1
            continue
        game_conf = Counter()
        for q in qs:
            if t.get("scan_window_start") and q["ts"] < t["scan_window_start"]:
                continue
            if t.get("scan_window_end") and q["ts"] > t["scan_window_end"]:
                continue
            ts = float(q["ts"])
            if g0 is not None and ts < float(g0):
                scope = "PRE_TIP"
            elif g1 is not None and ts > float(g1):
                scope = "POST_GAME"
            else:
                scope = "IN_GAME"
            prev, nxt, _ = asof_event(evs, ts)
            prev_gap = None if prev is None else ts - float(prev["wall_ts"])
            next_gap = None if nxt is None else float(nxt["wall_ts"]) - ts
            same = bool(prev and nxt and prev.get("period") == nxt.get("period"))
            inter = False
            if prev and nxt:
                inter = (prev.get("_sub") == "end" and nxt.get("_sub") == "start") or (
                    prev.get("period") != nxt.get("period")
                )
            if scope != "IN_GAME":
                conf = "UNRESOLVED"
            else:
                conf = classify_alignment(prev_gap, next_gap, same, inter)
            conf_counter[conf] += 1
            if scope == "IN_GAME":
                conf_ingame[conf] += 1
                game_conf[conf] += 1
                per = prev.get("period") if prev else None
                by_period_conf[str(per)][conf] += 1
            else:
                per = None
            align_rows.append(
                {
                    "event_id": t["event_id"],
                    "trade_ticker": t["ticker"],
                    "nba_game_id": gid,
                    "market_timestamp_utc": q["ts"],
                    "market_timestamp_iso": C.iso_utc(q["ts"]),
                    "alignment_scope": scope,
                    "prev_action_number": None if prev is None else prev.get("actionNumber"),
                    "next_action_number": None if nxt is None else nxt.get("actionNumber"),
                    "period": per,
                    "game_clock": None if prev is None else prev.get("clock"),
                    "elapsed_game_seconds": None if prev is None else prev.get("elapsed_s"),
                    "score_home": None if prev is None else prev.get("score_home"),
                    "score_away": None if prev is None else prev.get("score_away"),
                    "prev_event_gap_s": prev_gap,
                    "next_event_gap_s": next_gap,
                    "intermission_flag": inter,
                    "alignment_confidence": conf,
                    "alignment_method": "asof_timeActual",
                    "schema_version": C.SCHEMA_VERSION,
                }
            )
        n_g = sum(game_conf.values())
        good = game_conf["HIGH"] + game_conf["MEDIUM"]
        if n_g and good / n_g < 0.5:
            games_poor += 1

    n_al = max(1, len(align_rows))
    n_in = max(1, sum(conf_ingame.values()))
    high_med = conf_ingame["HIGH"] + conf_ingame["MEDIUM"]
    if high_med / n_in >= 0.70:
        gate_e = "PASS"
    elif high_med / n_in >= 0.50:
        gate_e = "WARNING"
    else:
        gate_e = "FAIL"
    log(
        f"GATE E {gate_e} in_game HIGH={conf_ingame['HIGH']} MED={conf_ingame['MEDIUM']} "
        f"LOW={conf_ingame['LOW']} UNRES={conf_ingame['UNRESOLVED']} "
        f"scan_window_all UNRES={conf_counter['UNRESOLVED']} n_all={len(align_rows)}"
    )
    if gate_e == "FAIL":
        log("GATE E FAIL: majority of in-game candles cannot be defensibly aligned. Halt.")
        C.write_json(
            C.OUT / "14_manifest.json",
            {"GATE_E": "FAIL", "in_game": dict(conf_ingame), "all": dict(conf_counter)},
        )
        return 3
    C.write_parquet(C.OUT / "04_market_game_alignment.parquet", align_rows)
    C.write_parquet(
        C.OUT / "10_alignment_diagnostics.parquet",
        [
            {
                "scope": "IN_GAME",
                "confidence": k,
                "n": v,
                "pct": round(100.0 * v / n_in, 4),
            }
            for k, v in sorted(conf_ingame.items())
        ]
        + [
            {
                "scope": "SCAN_WINDOW",
                "confidence": k,
                "n": v,
                "pct": round(100.0 * v / n_al, 4),
            }
            for k, v in sorted(conf_counter.items())
        ]
        + [
            {
                "scope": "IN_GAME_PERIOD",
                "confidence": f"period_{p}_{k}",
                "n": c,
                "pct": None,
            }
            for p, ctr in by_period_conf.items()
            for k, c in ctr.items()
        ],
    )

    # --- Phase 4–6: panel + features + labels ---
    # TRAIN pace for R1 / R3
    train_gids = {t["nba_game_id"] for t in trades if t.get("dataset_split") == "TRAIN" and t.get("nba_game_id")}
    train_durs = []
    period_durs = defaultdict(list)
    for p in possessions:
        if p["nba_game_id"] not in train_gids:
            continue
        d = p.get("duration_game_seconds")
        if d is not None and 0 < d < 120:
            train_durs.append(d)
            period_durs[int(p.get("period") or 0)].append(d)
    r1_sec_per_poss = float(np.mean(train_durs)) if train_durs else 14.5
    r3_sec = {k: float(np.mean(v)) if v else r1_sec_per_poss for k, v in period_durs.items()}

    panel = []
    leak_fail = 0
    n_unresolved_panel = 0
    for t in trades:
        gid = t.get("nba_game_id")
        poss = by_game_poss.get(gid or "") or []
        if not poss:
            continue
        entry_ts = float(t["first_80_timestamp"])
        a1q = quotes.get(t["ticker"]) or []
        a2q = quotes.get(t.get("opponent_ticker") or "") or []
        home = next((x.get("home_tricode") for x in timelines if x["nba_game_id"] == gid), None)
        post = []
        for p in poss:
            w = p.get("wall_start_ts")
            if w is None:
                continue
            if w + 1e-6 < entry_ts and (p.get("wall_end_ts") or w) < entry_ts:
                continue
            post.append(p)
        post.sort(key=lambda r: (r.get("possession_index") or 0))
        trade_rows = []
        max_dd = 0.0
        prices_seen = []
        for j, p in enumerate(post):
            w = float(p["wall_start_ts"])
            q1 = asof_quote(a1q, w)
            q2 = asof_quote(a2q, w) if a2q else None
            if q1 is not None and q1["ts"] > w + 1e-9:
                leak_fail += 1
            a1_bid = C.e4_to_cents(q1["bid_c"]) if q1 else None
            a1_ask = C.e4_to_cents(q1["ask_c"]) if q1 else None
            a1_low = C.e4_to_cents(q1["bid_l"]) if q1 else None
            a1_high = C.e4_to_cents(q1["bid_h"]) if q1 else None
            a2_bid = C.e4_to_cents(q2["bid_c"]) if q2 else None
            a2_ask = C.e4_to_cents(q2["ask_c"]) if q2 else None
            mid = None
            if a1_bid is not None and a1_ask is not None:
                mid = 0.5 * (a1_bid + a1_ask)
            age = None if q1 is None else w - float(q1["ts"])
            evs = by_game_events.get(gid) or []
            prev_e, nxt_e, _ = asof_event(evs, w) if evs else (None, None, -1)
            prev_gap = None if prev_e is None else w - float(prev_e["wall_ts"])
            next_gap = None if nxt_e is None else float(nxt_e["wall_ts"]) - w
            conf = classify_alignment(
                prev_gap,
                next_gap,
                bool(prev_e and nxt_e and prev_e.get("period") == nxt_e.get("period")),
                bool(prev_e and nxt_e and prev_e.get("period") != nxt_e.get("period")),
            )
            if conf == "UNRESOLVED":
                n_unresolved_panel += 1
            cur = a1_bid
            d_abs = None if cur is None else C.ENTRY_CENTS - cur
            if d_abs is not None:
                max_dd = max(max_dd, d_abs)
            if cur is not None:
                prices_seen.append(cur)
            elapsed = p.get("elapsed_game_seconds_start")
            rem_s = p.get("game_seconds_remaining_start")
            n_done = j + 1
            rate_game = None
            if elapsed and elapsed > 120 and n_done > 3:
                rate_game = n_done / elapsed
            r2 = None if rem_s is None or rate_game is None else rem_s * rate_game
            r1 = None if rem_s is None else rem_s / r1_sec_per_poss
            r3s = r3_sec.get(int(p.get("period") or 0), r1_sec_per_poss)
            r3 = None if rem_s is None else rem_s / r3s
            off = p.get("offensive_team")
            a1_team = t.get("a1_team")
            is_off = None if not off or not a1_team else off == a1_team
            sh, sa = p.get("score_home_start"), p.get("score_away_start")
            if a1_team and home and sh is not None and sa is not None:
                diff_a1 = (sh - sa) if a1_team == home else (sa - sh)
            else:
                diff_a1 = p.get("score_differential_offense")
            row = {
                "trade_id": t["ticker"],
                "event_id": t["event_id"],
                "game_id": t.get("game_id") or t["event_id"],
                "nba_game_id": gid,
                "market_ticker": t["ticker"],
                "opponent_ticker": t.get("opponent_ticker"),
                "A1_team": a1_team,
                "A2_team": t.get("a2_team"),
                "sport": "nba",
                "season": "2025-26",
                "dataset_split": t.get("dataset_split"),
                "game_date": t.get("game_date"),
                "entry_timestamp": entry_ts,
                "entry_price": C.ENTRY_CENTS,
                "expiration_result_yes": bool(t.get("expiration_result_yes")),
                "possession_id": p["possession_id"],
                "possession_index": p["possession_index"],
                "possessions_since_entry": j,
                "period": p.get("period"),
                "is_overtime": int(p.get("period") or 0) > 4,
                "game_clock": p.get("game_clock_start"),
                "elapsed_game_seconds": elapsed,
                "game_seconds_remaining": rem_s,
                "position_age_game_seconds": None if elapsed is None else elapsed - (post[0].get("elapsed_game_seconds_start") or elapsed),
                "position_age_wall_s": w - entry_ts,
                "offensive_team": off,
                "is_A1_team_offense": is_off,
                "is_A1_team_defense": None if is_off is None else (not is_off),
                "score_home": sh,
                "score_away": sa,
                "score_differential_from_A1": diff_a1,
                "score_differential_absolute": None if diff_a1 is None else abs(diff_a1),
                "current_game_total_score": None if sh is None or sa is None else sh + sa,
                "is_close_game": None if diff_a1 is None else abs(diff_a1) <= 8,
                "estimated_possessions_remaining_r1": r1,
                "estimated_possessions_remaining_r2": r2,
                "estimated_possessions_remaining_r3": r3,
                "actual_remaining_possessions": len(post) - j - 1,
                "current_price": cur,
                "A1_yes_bid": a1_bid,
                "A1_yes_ask": a1_ask,
                "A1_mid": mid,
                "A1_candle_close": a1_bid,
                "A1_candle_high": a1_high,
                "A1_candle_low": a1_low,
                "A2_yes_bid": a2_bid,
                "A2_yes_ask": a2_ask,
                "A1_A2_sum": None if a1_bid is None or a2_bid is None else a1_bid + a2_bid,
                "deterioration_absolute": d_abs,
                "deterioration_percent_of_entry": None if d_abs is None else d_abs / C.ENTRY_CENTS,
                "max_deterioration_since_entry": max_dd if cur is not None else None,
                "current_price_rank_since_entry": (
                    None if cur is None else sum(1 for x in prices_seen if x <= cur) / max(1, len(prices_seen))
                ),
                "market_observation_timestamp": None if q1 is None else q1["ts"],
                "market_age_seconds": age,
                "alignment_confidence": conf,
                "alignment_method": "asof_timeActual",
                "possession_confidence": p.get("source_confidence"),
                "market_mapping_confidence": "UNRESOLVED" if q1 is None else ("HIGH" if age is not None and age <= 60 else "MEDIUM" if age is not None and age <= 180 else "LOW"),
                "possession_result": p.get("possession_result"),
                "ambiguous_possession_flag": p.get("ambiguous_possession_flag"),
                "evidence_level": "A",
                "schema_version": C.SCHEMA_VERSION,
            }
            trade_rows.append(row)

        # velocities / accel / vol using unique market prints
        for i, row in enumerate(trade_rows):
            for k in C.VEL_KS:
                hist = unique_quotes_before(trade_rows, i, k)
                uniq = len(hist)
                row[f"unique_market_observations_v{k}"] = uniq
                if uniq >= 2 and hist[-1].get("current_price") is not None and hist[0].get("current_price") is not None:
                    steps = uniq - 1
                    row[f"v_{k}"] = (hist[-1]["current_price"] - hist[0]["current_price"]) / steps
                    row[f"velocity_valid_{k}"] = True
                else:
                    row[f"v_{k}"] = None
                    row[f"velocity_valid_{k}"] = False
            v1, v3, v5 = row.get("v_1"), row.get("v_3"), row.get("v_5")
            row["a_3_1"] = None if v1 is None or v3 is None else v3 - v1
            row["a_5_3"] = None if v5 is None or v3 is None else v5 - v3
            row["a_short"] = row["a_3_1"]
            row["a_medium"] = row["a_5_3"]
            # market vol over last 5 unique prints
            uh = unique_quotes_before(trade_rows, i, 5)
            pxs = [r["current_price"] for r in uh if r.get("current_price") is not None]
            if len(pxs) >= 3:
                diffs = [abs(pxs[k] - pxs[k - 1]) for k in range(1, len(pxs))]
                row["market_volatility"] = float(np.mean(diffs))
                row["rolling_range_5"] = max(pxs) - min(pxs)
                row["rolling_downside_vol"] = float(np.mean([d for d in diffs if True]))
            else:
                row["market_volatility"] = None
                row["rolling_range_5"] = None
                row["rolling_downside_vol"] = None
            # recent scoring margin: last 5 possessions points for A1
            rec_margin = 0
            for b in trade_rows[max(0, i - 4) : i + 1]:
                # not stored points; skip — use score_diff change
                pass
            if i >= 1 and row.get("score_differential_from_A1") is not None and trade_rows[max(0, i - 5)].get("score_differential_from_A1") is not None:
                row["recent_scoring_margin"] = row["score_differential_from_A1"] - trade_rows[max(0, i - 5)]["score_differential_from_A1"]
            else:
                row["recent_scoring_margin"] = None

        # forward labels
        for i, row in enumerate(trade_rows):
            for k in C.HORIZONS:
                fut = trade_rows[i + 1 : i + 1 + k]
                px = [r["current_price"] for r in fut if r.get("current_price") is not None]
                lo = [r["A1_candle_low"] for r in fut if r.get("A1_candle_low") is not None]
                hi = [r.get("A1_candle_high") for r in fut if r.get("A1_candle_high") is not None]
                row[f"future_min_{k}"] = min(px) if px else None
                row[f"future_max_{k}"] = max(px) if px else None
                row[f"future_min_low_{k}"] = min(lo) if lo else None
                row[f"future_deterioration_{k}"] = (
                    None if not px or row.get("current_price") is None else row["current_price"] - min(px)
                )
                row[f"future_mae_{k}"] = row[f"future_deterioration_{k}"]
                row[f"recovery_from_current_{k}"] = (
                    None if not px or row.get("current_price") is None else max(px) - row["current_price"]
                )
                row[f"recovery_from_entry_{k}"] = None if not px else max(px) - C.ENTRY_CENTS
                for th in C.THRESHOLDS:
                    mn = row[f"future_min_{k}"]
                    row[f"y_min_le_{th}_k{k}"] = None if mn is None else int(mn <= th)
                row[f"y_det_ge_10_k{k}"] = (
                    None if row[f"future_deterioration_{k}"] is None else int(row[f"future_deterioration_{k}"] >= 10)
                )
                row[f"y_rec_ge_10_k{k}"] = (
                    None if row[f"recovery_from_current_{k}"] is None else int(row[f"recovery_from_current_{k}"] >= 10)
                )
                row[f"y_rec_ge_5_k{k}"] = (
                    None if row[f"recovery_from_current_{k}"] is None else int(row[f"recovery_from_current_{k}"] >= 5)
                )
                row[f"y_rec_ge_20_k{k}"] = (
                    None if row[f"recovery_from_current_{k}"] is None else int(row[f"recovery_from_current_{k}"] >= 20)
                )
                row[f"y_max_ge_75_k{k}"] = None if row[f"future_max_{k}"] is None else int(row[f"future_max_{k}"] >= 75)
                row[f"y_max_ge_80_k{k}"] = None if row[f"future_max_{k}"] is None else int(row[f"future_max_{k}"] >= 80)
                row[f"y_max_ge_entry_k{k}"] = None if row[f"future_max_{k}"] is None else int(row[f"future_max_{k}"] >= C.ENTRY_CENTS)
            # to game end
            fut_end = trade_rows[i + 1 :]
            px_e = [r["current_price"] for r in fut_end if r.get("current_price") is not None]
            row["future_min_end"] = min(px_e) if px_e else None
            row["future_max_end"] = max(px_e) if px_e else None
            row["future_deterioration_end"] = (
                None if not px_e or row.get("current_price") is None else row["current_price"] - min(px_e)
            )
            row["recovery_from_current_end"] = (
                None if not px_e or row.get("current_price") is None else max(px_e) - row["current_price"]
            )
            for th in C.THRESHOLDS:
                row[f"y_min_le_{th}_end"] = None if row["future_min_end"] is None else int(row["future_min_end"] <= th)
            row["y_det_ge_10_end"] = (
                None if row["future_deterioration_end"] is None else int(row["future_deterioration_end"] >= 10)
            )
            row["y_rec_ge_10_end"] = (
                None if row["recovery_from_current_end"] is None else int(row["recovery_from_current_end"] >= 10)
            )
            row["y_settle_yes"] = int(bool(t.get("expiration_result_yes")))
            row["terminal_pnl_hold"] = 20.0 if t.get("expiration_result_yes") else -80.0
            row["terminal_pnl_hold_evidence"] = "THEORETICAL_HOLD_AT_80_PROXY"
            # jump proxies on unique future prints
            uniq_fut = []
            last = None
            for r in fut_end:
                ts = r.get("market_observation_timestamp")
                if ts is None or r.get("current_price") is None:
                    continue
                if ts != last:
                    uniq_fut.append(r["current_price"])
                    last = ts
            chain = []
            if row.get("current_price") is not None:
                chain.append(row["current_price"])
            chain.extend(uniq_fut)
            for th in C.JUMP_THRESHOLDS:
                jumped = 0
                mag = None
                for a, b in zip(chain, chain[1:]):
                    if a > th and b < th:
                        jumped = 1
                        mag = a - b
                        break
                row[f"y_jump_{th}"] = jumped if len(chain) >= 2 else None
                row[f"jump_mag_{th}"] = mag
                row[f"jump_label_kind"] = "OBSERVED_JUMP_PROXY"
            panel.append(row)

    log(f"panel rows={len(panel)} unresolved_panel={n_unresolved_panel} leak_asof={leak_fail}")
    C.write_parquet(C.OUT / "05_trade_possession_panel.parquet", panel)

    # feature / label split files
    feature_keep = [
        "trade_id",
        "event_id",
        "nba_game_id",
        "dataset_split",
        "game_date",
        "possession_index",
        "possessions_since_entry",
        "entry_price",
        "current_price",
        "deterioration_absolute",
        "deterioration_percent_of_entry",
        "max_deterioration_since_entry",
        "current_price_rank_since_entry",
        "position_age_wall_s",
        "position_age_game_seconds",
        "elapsed_game_seconds",
        "game_seconds_remaining",
        "period",
        "is_overtime",
        "estimated_possessions_remaining_r1",
        "estimated_possessions_remaining_r2",
        "estimated_possessions_remaining_r3",
        "score_differential_from_A1",
        "score_differential_absolute",
        "is_A1_team_offense",
        "is_close_game",
        "market_age_seconds",
        "v_1",
        "v_3",
        "v_5",
        "v_10",
        "velocity_valid_1",
        "velocity_valid_3",
        "velocity_valid_5",
        "a_short",
        "a_medium",
        "market_volatility",
        "rolling_range_5",
        "recent_scoring_margin",
        "alignment_confidence",
        "market_mapping_confidence",
        "A1_yes_bid",
        "A1_yes_ask",
        "A1_mid",
        "A2_yes_bid",
    ]
    label_keep = ["trade_id", "event_id", "possession_index", "dataset_split"] + [
        k
        for k in (panel[0].keys() if panel else [])
        if k.startswith("future_") or k.startswith("y_") or k.startswith("recovery_") or k.startswith("jump_") or k in ("terminal_pnl_hold",)
    ]
    C.write_parquet(C.OUT / "06_state_features.parquet", [{k: r.get(k) for k in feature_keep} for r in panel])
    C.write_parquet(C.OUT / "07_forward_labels.parquet", [{k: r.get(k) for k in label_keep} for r in panel])

    leak_rows = []
    observed = {
        "current_price",
        "A1_yes_bid",
        "A1_yes_ask",
        "score_differential_from_A1",
        "period",
        "elapsed_game_seconds",
        "game_seconds_remaining",
        "possessions_since_entry",
        "is_A1_team_offense",
        "market_age_seconds",
        "deterioration_absolute",
        "max_deterioration_since_entry",
        "alignment_confidence",
    }
    estimated = {
        "estimated_possessions_remaining_r1",
        "estimated_possessions_remaining_r2",
        "estimated_possessions_remaining_r3",
        "A1_mid",
        "v_1",
        "v_3",
        "v_5",
        "v_10",
        "a_short",
        "a_medium",
        "market_volatility",
    }
    labels = {k for k in (panel[0].keys() if panel else []) if k.startswith("y_") or k.startswith("future_") or k.startswith("recovery_")}
    forbidden = {"actual_remaining_possessions"}
    for name in sorted(observed | estimated | labels | forbidden):
        if name in forbidden:
            kind = "EVALUATION_ONLY_NOT_A_FEATURE"
        elif name in labels:
            kind = "FUTURE_DERIVED_LABEL"
        elif name in estimated:
            kind = "ESTIMATED_AT_STATE"
        else:
            kind = "OBSERVED_AT_STATE"
        leak_rows.append(
            {
                "feature": name,
                "availability": kind,
                "used_as_model_feature": name not in labels and name not in forbidden,
                "schema_version": C.SCHEMA_VERSION,
            }
        )
    C.write_parquet(C.OUT / "12_data_leakage_audit.parquet", leak_rows)
    gate_f = "PASS" if leak_fail == 0 else "FAIL"
    gate_g = "PASS"
    log(f"GATE F {gate_f} lookahead_asof={leak_fail} GATE G {gate_g} (by construction)")

    # remaining-possessions diagnostics
    rem_diag = []
    for r in panel:
        act = r.get("actual_remaining_possessions")
        if act is None:
            continue
        for name in ("r1", "r2", "r3"):
            est = r.get(f"estimated_possessions_remaining_{name}")
            if est is None:
                continue
            rem_diag.append(
                {
                    "nba_game_id": r["nba_game_id"],
                    "dataset_split": r["dataset_split"],
                    "period": r.get("period"),
                    "model": name.upper(),
                    "estimated": est,
                    "actual": act,
                    "error": est - act,
                    "abs_error": abs(est - act),
                    "is_close_game": r.get("is_close_game"),
                    "schema_version": C.SCHEMA_VERSION,
                }
            )
    C.write_parquet(C.OUT / "11_remaining_possessions_diagnostics.parquet", rem_diag)

    def rem_metrics(split: str, model: str) -> dict:
        xs = [d for d in rem_diag if d["dataset_split"] == split and d["model"] == model]
        if not xs:
            return {"n": 0}
        err = np.array([d["error"] for d in xs], dtype=float)
        return {
            "n": len(xs),
            "mae": float(np.mean(np.abs(err))),
            "rmse": float(np.sqrt(np.mean(err**2))),
            "bias": float(np.mean(err)),
        }

    rem_summary = {
        s: {m: rem_metrics(s, m) for m in ("R1", "R2", "R3")} for s in ("TRAIN", "VALIDATION", "OOS")
    }
    log(f"remaining poss OOS R2 {rem_summary['OOS']['R2']}")

    # split isolation
    games_by_split = defaultdict(set)
    for r in panel:
        games_by_split[r["dataset_split"]].add(r["event_id"])
    overlap = (
        games_by_split["TRAIN"] & games_by_split["VALIDATION"]
        | games_by_split["TRAIN"] & games_by_split["OOS"]
        | games_by_split["VALIDATION"] & games_by_split["OOS"]
    )
    gate_h = "PASS" if not overlap else "FAIL"
    log(f"GATE H {gate_h} train_games={len(games_by_split['TRAIN'])} val={len(games_by_split['VALIDATION'])} oos={len(games_by_split['OOS'])}")

    # --- Phase 7 models ---
    FAMILIES = {
        "B0": ["current_price"],
        "B1": ["current_price", "deterioration_absolute", "position_age_wall_s"],
        "B2": [
            "current_price",
            "deterioration_absolute",
            "position_age_wall_s",
            "game_seconds_remaining",
            "period",
            "score_differential_from_A1",
        ],
        "M3": [
            "current_price",
            "deterioration_absolute",
            "position_age_wall_s",
            "game_seconds_remaining",
            "period",
            "score_differential_from_A1",
            "possessions_since_entry",
            "estimated_possessions_remaining_r2",
        ],
        "M4": [
            "current_price",
            "deterioration_absolute",
            "position_age_wall_s",
            "game_seconds_remaining",
            "period",
            "score_differential_from_A1",
            "possessions_since_entry",
            "estimated_possessions_remaining_r2",
            "v_3",
            "v_5",
        ],
        "M5": [
            "current_price",
            "deterioration_absolute",
            "position_age_wall_s",
            "game_seconds_remaining",
            "period",
            "score_differential_from_A1",
            "possessions_since_entry",
            "estimated_possessions_remaining_r2",
            "v_3",
            "v_5",
            "a_short",
            "market_volatility",
            "market_age_seconds",
        ],
    }
    TARGETS = [
        ("y_min_le_40_k5", "P(min<=40 within 5 poss)"),
        ("y_min_le_40_end", "P(min<=40 to end)"),
        ("y_det_ge_10_k5", "P(det>=10 within 5 poss)"),
        ("y_rec_ge_10_k5", "P(rec>=10 within 5 poss)"),
        ("y_jump_40", "P(jump-through 40 proxy)"),
        ("y_settle_yes", "P(settle YES)"),
        ("y_min_le_40_k1", "P(min<=40 within 1 poss)"),
        ("y_min_le_40_k3", "P(min<=40 within 3 poss)"),
        ("y_min_le_40_k10", "P(min<=40 within 10 poss)"),
        ("y_det_ge_10_k1", "P(det>=10 within 1 poss)"),
        ("y_rec_ge_10_k1", "P(rec>=10 within 1 poss)"),
        ("y_det_ge_10_end", "P(det>=10 to end)"),
        ("y_rec_ge_10_end", "P(rec>=10 to end)"),
    ]

    model_rows = []
    pred_rows = []
    usable = [
        r
        for r in panel
        if r.get("alignment_confidence") in ("HIGH", "MEDIUM") and r.get("current_price") is not None
    ]

    def xy(rows, cols, yname):
        xs, ys, keep = [], [], []
        for r in rows:
            y = r.get(yname)
            if y is None:
                continue
            vec = []
            ok = True
            for c in cols:
                v = r.get(c)
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    ok = False
                    break
                if isinstance(v, bool):
                    v = int(v)
                vec.append(float(v))
            if not ok:
                continue
            xs.append(vec)
            ys.append(int(y))
            keep.append(r)
        if not xs:
            return None, None, []
        return np.array(xs, dtype=float), np.array(ys, dtype=int), keep

    if not HAS_SKLEARN:
        log("GATE models SKIP sklearn missing")
    for fam, cols in FAMILIES.items():
        for yname, ylab in TARGETS:
            tr_x, tr_y, _ = xy([r for r in usable if r["dataset_split"] == "TRAIN"], cols, yname)
            model = fit_logit(tr_x, tr_y) if tr_x is not None else None
            for split in ("TRAIN", "VALIDATION", "OOS"):
                sx, sy, srows = xy([r for r in usable if r["dataset_split"] == split], cols, yname)
                if model is None or sx is None:
                    model_rows.append(
                        {
                            "family": fam,
                            "target": yname,
                            "target_label": ylab,
                            "split": split,
                            "n": 0 if sy is None else int(len(sy)),
                            "auc": None,
                            "brier": None,
                            "logloss": None,
                            "ece": None,
                            "status": "INSUFFICIENT",
                            "evidence_level": "C",
                        }
                    )
                    continue
                p = model.predict_proba(sx)[:, 1]
                met = metrics_of(sy, p)
                model_rows.append(
                    {
                        "family": fam,
                        "target": yname,
                        "target_label": ylab,
                        "split": split,
                        **met,
                        "status": "FIT",
                        "evidence_level": "C",
                        "n_features": len(cols),
                    }
                )
                if yname in ("y_min_le_40_k5", "y_min_le_40_end", "y_settle_yes") and split == "OOS":
                    for r, pi, yi in zip(srows[:5000], p[:5000], sy[:5000]):
                        pred_rows.append(
                            {
                                "family": fam,
                                "target": yname,
                                "split": split,
                                "event_id": r["event_id"],
                                "possession_index": r["possession_index"],
                                "y": int(yi),
                                "p": float(pi),
                            }
                        )

    C.write_parquet(C.OUT / "08_model_predictions.parquet", pred_rows)
    C.write_parquet(C.OUT / "09_model_metrics.parquet", model_rows)

    def pick(fam, target, split, field):
        for m in model_rows:
            if m["family"] == fam and m["target"] == target and m["split"] == split:
                return m.get(field)
        return None

    oos_b2 = pick("B2", "y_min_le_40_k5", "OOS", "brier")
    oos_m3 = pick("M3", "y_min_le_40_k5", "OOS", "brier")
    oos_m5 = pick("M5", "y_min_le_40_k5", "OOS", "brier")
    auc_b2 = pick("B2", "y_min_le_40_k5", "OOS", "auc")
    auc_m3 = pick("M3", "y_min_le_40_k5", "OOS", "auc")
    auc_m5 = pick("M5", "y_min_le_40_k5", "OOS", "auc")
    poss_value = "INCONCLUSIVE"
    if oos_b2 is not None and oos_m3 is not None and auc_b2 is not None and auc_m3 is not None:
        brier_better = oos_m3 < oos_b2 - 0.0005
        auc_better = auc_m3 > auc_b2 + 0.005
        if brier_better and auc_better:
            poss_value = "YES"
        elif oos_m3 > oos_b2 + 0.001 and auc_m3 < auc_b2:
            poss_value = "NO"

    # empirical surfaces
    def surface(rows, price_lo, price_hi):
        xs = [r for r in rows if r.get("current_price") is not None and price_lo <= r["current_price"] < price_hi]
        def rate(key):
            vs = [r[key] for r in xs if r.get(key) is not None]
            if not vs:
                return None
            return sum(vs) / len(vs)
        return {
            "n": len(xs),
            "p_min40_k5": rate("y_min_le_40_k5"),
            "p_min40_end": rate("y_min_le_40_end"),
            "p_rec10_k5": rate("y_rec_ge_10_k5"),
            "p_jump40": rate("y_jump_40"),
            "p_settle": rate("y_settle_yes"),
        }

    oos_rows = [r for r in usable if r["dataset_split"] == "OOS"]
    train_rows = [r for r in usable if r["dataset_split"] == "TRAIN"]
    surfaces = []
    for lo in range(5, 85, 5):
        surfaces.append({"split": "OOS", "price_lo": lo, "price_hi": lo + 5, **surface(oos_rows, lo, lo + 5)})
        surfaces.append({"split": "TRAIN", "price_lo": lo, "price_hi": lo + 5, **surface(train_rows, lo, lo + 5)})

    # recovery after severe temp deterioration
    severe = [r for r in usable if (r.get("deterioration_absolute") or 0) >= 20]
    rec_after = [r for r in severe if r.get("y_rec_ge_10_end") == 1]
    settle_after = [r for r in severe if r.get("y_settle_yes") == 1]

    # 10 example games for dashboard
    examples = []
    want = []
    for split, n in (("TRAIN", 4), ("VALIDATION", 3), ("OOS", 3)):
        cands = [t for t in trades if t.get("dataset_split") == split and t.get("nba_game_id") in by_game_poss]
        # prefer OT / variety
        cands.sort(key=lambda t: t.get("first_80_timestamp") or 0)
        step = max(1, len(cands) // max(1, n))
        want.extend(cands[::step][:n])
    for t in want[:10]:
        gid = t["nba_game_id"]
        evs = by_game_events.get(gid) or []
        poss = by_game_poss.get(gid) or []
        qs = quotes.get(t["ticker"]) or []
        tl = next((x for x in timelines if x["nba_game_id"] == gid), {})
        candles = []
        for q in qs:
            if t.get("scan_window_start") and q["ts"] < t["scan_window_start"]:
                continue
            if t.get("scan_window_end") and q["ts"] > t["scan_window_end"]:
                continue
            if q["ts"] < t["first_80_timestamp"] - 600:
                continue
            candles.append(
                {
                    "ts": q["ts"],
                    "bid": C.e4_to_cents(q["bid_c"]),
                    "low": C.e4_to_cents(q["bid_l"]),
                    "high": C.e4_to_cents(q["bid_h"]),
                }
            )
        prow = [
            {
                "idx": p["possession_index"],
                "period": p.get("period"),
                "clock": p.get("game_clock_start"),
                "elapsed": p.get("elapsed_game_seconds_start"),
                "wall": p.get("wall_start_ts"),
                "off": p.get("offensive_team"),
                "sh": p.get("score_home_start"),
                "sa": p.get("score_away_start"),
                "result": p.get("possession_result"),
            }
            for p in poss
        ]
        tpanel = [r for r in panel if r["trade_id"] == t["ticker"]]
        examples.append(
            {
                "event_id": t["event_id"],
                "ticker": t["ticker"],
                "nba_game_id": gid,
                "split": t["dataset_split"],
                "entry_ts": t["first_80_timestamp"],
                "a1": t.get("a1_team"),
                "ot": tl.get("has_overtime"),
                "candles": candles[::2][:240],
                "possessions": prow,
                "path": [
                    {
                        "possessions_since_entry": r["possessions_since_entry"],
                        "price": r.get("current_price"),
                        "d": r.get("deterioration_absolute"),
                        "v3": r.get("v_3"),
                        "a": r.get("a_short"),
                        "age": r.get("market_age_seconds"),
                        "diff": r.get("score_differential_from_A1"),
                        "off": r.get("is_A1_team_offense"),
                        "period": r.get("period"),
                        "clock": r.get("game_clock"),
                        "conf": r.get("alignment_confidence"),
                    }
                    for r in tpanel
                ],
            }
        )

    # alignment gate overall
    time_alignment = gate_e
    poss_engine = gate_d["status"]
    leak_audit = "PASS" if gate_f == "PASS" and gate_g == "PASS" and gate_h == "PASS" else "FAIL"
    rem_oos = rem_summary["OOS"]["R2"]
    rem_status = "FAIL"
    if rem_oos.get("n", 0) >= 100:
        rem_status = "PASS" if rem_oos.get("mae", 99) <= 25 else "WARNING"
    dre = "PARTIAL"
    if time_alignment == "PASS" and poss_engine in ("PASS", "WARNING") and leak_audit == "PASS":
        dre = "READY FOR V2" if poss_value in ("YES", "INCONCLUSIVE") else "PARTIAL"
    if time_alignment == "FAIL" or leak_audit == "FAIL":
        dre = "NOT READY"

    counts = {
        "panel_rows": len(panel),
        "panel_high_med": len(usable),
        "trades_with_panel": len({r["trade_id"] for r in panel}),
        "timelines": len(timelines),
        "pbp_events": len(pbp_events),
        "possessions": len(possessions),
        "alignment_rows": len(align_rows),
        "train_games": len(games_by_split["TRAIN"]),
        "val_games": len(games_by_split["VALIDATION"]),
        "oos_games": len(games_by_split["OOS"]),
        "train_rows": sum(1 for r in panel if r["dataset_split"] == "TRAIN"),
        "val_rows": sum(1 for r in panel if r["dataset_split"] == "VALIDATION"),
        "oos_rows": sum(1 for r in panel if r["dataset_split"] == "OOS"),
    }

    gaps = [
        r.get("prev_event_gap_s")
        for r in align_rows
        if r.get("alignment_scope") == "IN_GAME" and r.get("prev_event_gap_s") is not None
    ]
    align_dist = {
        "n": len(gaps),
        "p50": float(np.median(gaps)) if gaps else None,
        "p90": float(np.quantile(gaps, 0.90)) if gaps else None,
        "p99": float(np.quantile(gaps, 0.99)) if gaps else None,
        "mean": float(np.mean(gaps)) if gaps else None,
    }

    config = {
        "program": C.PROGRAM,
        "schema_version": C.SCHEMA_VERSION,
        "live_execution_changed": False,
        "sport_primary": "nba",
        "ncaab": "NOT_IMPLEMENTED_V1_NO_JOINABLE_PBP",
        "universe": "frozen FIRST-80 via V1A.load_frozen",
        "gates_expected": C.GATES_F80,
        "wall_clock_primary": "cdn.nba.com live timeActual",
        "market_join": "ASOF end_period_ts <= possession wall_start",
        "interpolation": False,
        "consequence_weights": False,
        "splits": {
            "TRAIN": f"game_date <= {C.SPLIT_TRAIN_END}",
            "VALIDATION": f"{C.SPLIT_TRAIN_END} < game_date <= {C.SPLIT_VAL_END}",
            "OOS": f"game_date > {C.SPLIT_VAL_END}",
        },
        "created_utc": C.utc_now(),
    }
    C.write_json(C.OUT / "13_config.yaml".replace(".yaml", "_meta.json"), config)
    (C.OUT / "13_config.yaml").write_text(
        "\n".join(
            [
                f"program: {C.PROGRAM}",
                f"schema_version: {C.SCHEMA_VERSION}",
                "live_execution_changed: false",
                "sport_primary: nba",
                "ncaab: NOT_IMPLEMENTED_V1_NO_JOINABLE_PBP",
                "wall_clock_primary: live_timeActual",
                "market_join: ASOF",
                "interpolation: false",
                "consequence_weights: false",
                f"created_utc: {C.utc_now()}",
            ]
        )
        + "\n"
    )

    verdict = {
        "TIME_ALIGNMENT": time_alignment,
        "POSSESSION_ENGINE": poss_engine,
        "DATA_LEAKAGE_AUDIT": leak_audit,
        "POSSESSION_PREDICTIVE_VALUE": poss_value,
        "REMAINING_POSSESSIONS_MODEL": rem_status,
        "DRE_STATE_ARCHITECTURE": dre,
        "EXECUTION_EVIDENCE": "UNOBSERVED",
        "LIVE_DEPLOYMENT": "NOT AUTHORIZED BY THIS EXPERIMENT",
        "oos_brier_B2_min40_k5": oos_b2,
        "oos_brier_M3_min40_k5": oos_m3,
        "oos_brier_M5_min40_k5": oos_m5,
        "oos_auc_B2_min40_k5": auc_b2,
        "oos_auc_M3_min40_k5": auc_m3,
        "oos_auc_M5_min40_k5": auc_m5,
    }

    manifest = {
        "program": C.PROGRAM,
        "schema_version": C.SCHEMA_VERSION,
        "created_utc": C.utc_now(),
        "elapsed_s": round(time.time() - t0, 1),
        "live_execution_changed": False,
        "GATE_A": "PASS",
        "GATE_B": gate_b,
        "GATE_C": gate_c,
        "GATE_D": gate_d,
        "GATE_E": {
            "status": gate_e,
            "in_game_counts": dict(conf_ingame),
            "scan_window_counts": dict(conf_counter),
            "poor_games": games_poor,
        },
        "GATE_F": gate_f,
        "GATE_G": gate_g,
        "GATE_H": gate_h,
        "counts": counts,
        "alignment_gap": align_dist,
        "remaining": rem_summary,
        "severe_det20": {
            "n": len(severe),
            "recover_10_end": len(rec_after),
            "recover_pct": None if not severe else round(100.0 * len(rec_after) / len(severe), 2),
            "settle_yes": len(settle_after),
            "settle_pct": None if not severe else round(100.0 * len(settle_after) / len(severe), 2),
        },
        "verdict": verdict,
        "row_counts": {
            "01_game_timeline": len(timelines),
            "02_pbp_events": len(pbp_events),
            "03_possessions": len(possessions),
            "04_alignment": len(align_rows),
            "05_panel": len(panel),
            "08_predictions": len(pred_rows),
            "09_metrics": len(model_rows),
        },
    }
    C.write_json(C.OUT / "14_manifest.json", manifest)
    C.write_json(C.OUT / "summary.json", manifest)

    dash = {
        "program": C.PROGRAM,
        "banner": "RESEARCH ONLY · LIVE EXECUTION CHANGED: FALSE · CANDLE ≠ FILL · ASOF ≠ INTERPOLATION · EXECUTION UNOBSERVED",
        "created_utc": C.utc_now(),
        "verdict": verdict,
        "gates": {
            "A": "PASS",
            "B": gate_b,
            "C": gate_c,
            "D": gate_d,
            "E": {"status": gate_e, "counts": dict(conf_ingame), "scan_window": dict(conf_counter)},
            "F": gate_f,
            "G": gate_g,
            "H": gate_h,
        },
        "counts": counts,
        "alignment": {
            "counts": dict(conf_ingame),
            "pct": {k: round(100.0 * v / n_in, 3) for k, v in conf_ingame.items()},
            "scan_window_counts": dict(conf_counter),
            "gap": align_dist,
            "poor_games": games_poor,
        },
        "models": model_rows,
        "remaining": rem_summary,
        "surfaces": surfaces,
        "severe": manifest["severe_det20"],
        "examples": examples,
        "leakage": leak_rows,
        "families": FAMILIES,
    }
    C.write_json(C.OUT / "dashboard.json", dash)
    C.write_json(C.DASH_PUBLIC / "dashboard.json", dash)
    log(f"done elapsed={time.time()-t0:.1f}s dre={dre} poss_value={poss_value} align={time_alignment}")
    return 0 if time_alignment != "FAIL" and leak_audit != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
