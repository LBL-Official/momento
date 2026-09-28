"""MODULE B — P(~T40 | W) vs FIRST75, NON_FIRST80, and matched strata."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402

import config as C
import quotes as Q
import stats_util as S


def cond_not40_given_w(df: pd.DataFrame, label: str) -> dict:
    if df is None or len(df) == 0:
        return {"n": 0, "k": 0, "estimate": None, "label": label, "object": "P(not_T40 | W)"}
    w = df[df["W"].astype(bool)]
    n = int(len(w))
    k = int((~w["T40"].astype(bool)).sum()) if n else 0
    rec = S.rate_block(k, n)
    rec["label"] = label
    rec["object"] = "P(not_T40 | W)"
    rec["weighting"] = "ONE_OBSERVATION_PER_GAME"
    rec["n_total"] = int(len(df))
    rec["n_wins"] = n
    return rec


def first75_control(quotes, markets, games) -> pd.DataFrame:
    tab = Q.first_team_at_threshold(markets, games, quotes, 7500)
    settled = tab[(tab["status"] == "FIRST_REACH") & tab["W"].notna()].copy()
    settled["T40"] = settled["T40"].astype(bool)
    settled["W"] = settled["W"].astype(bool)
    settled["source"] = "FIRST75"
    return settled


def non_first80_control(df80: pd.DataFrame, quotes, markets, games) -> pd.DataFrame:
    """Other team in the same game that later makes a tradable 80 cross.

    Not a second FIRST80. Same-minute ties with FIRST80 are impossible here
    because frozen FIRST80 already excluded same-minute ties.
    """
    from collections import defaultdict

    by_event = defaultdict(list)
    for m in markets:
        by_event[m["event_id"]].append(m)
    rows = []
    dropped = {"no_opponent_reach": 0, "opponent_earlier_or_equal": 0, "unsettled": 0}
    for rec in df80.to_dict("records"):
        others = [m for m in by_event.get(rec["event_id"], []) if m["ticker"] != rec["ticker"]]
        if not others:
            dropped["no_opponent_reach"] += 1
            continue
        hits = []
        for m in others:
            q = Q.first_tradable_reach(quotes.get(m["ticker"], []), C.HIT80_E4)
            if q:
                hits.append((q["ts"], m, q))
        if not hits:
            dropped["no_opponent_reach"] += 1
            continue
        hits.sort(key=lambda x: x[0])
        ts, m0, q = hits[0]
        if ts <= rec["first_80_timestamp"]:
            dropped["opponent_earlier_or_equal"] += 1
            continue
        won = A.settled_yes(m0)
        if won is None:
            dropped["unsettled"] += 1
            continue
        t40 = Q.first_close_le_after(quotes.get(m0["ticker"], []), ts, C.HIT40_E4)
        rows.append(
            {
                "event_id": rec["event_id"],
                "game_date": rec["game_date"],
                "dataset_split": rec["dataset_split"],
                "ticker": m0["ticker"],
                "team": m0["team"],
                "reach_ts": ts,
                "first80_ticker": rec["ticker"],
                "first80_ts": rec["first_80_timestamp"],
                "delay_s": int(ts - rec["first_80_timestamp"]),
                "W": bool(won),
                "T40": t40 is not None,
                "source": "NON_FIRST80",
            }
        )
    out = pd.DataFrame(rows)
    out.attrs["dropped"] = dropped
    out.attrs["definition"] = (
        "NON_FIRST80 = opponent ticker's first tradable 80 cross strictly after the game's FIRST80 timestamp."
    )
    return out


def stratified(df: pd.DataFrame) -> dict:
    w = df[df["W"].astype(bool) & df["matchable"]].copy()
    out = {"n_winners_matchable": int(len(w))}
    for col in ("quarter_bin", "score_abs_bin", "lead_state", "dataset_split"):
        recs = []
        if col not in w.columns:
            continue
        for key, g in w.groupby(col, dropna=False):
            recs.append({"stratum": None if pd.isna(key) else str(key), **cond_not40_given_w(g, f"{col}={key}")})
        out[col] = recs
    return out


def matched_first75(df80: pd.DataFrame, f75: pd.DataFrame) -> dict:
    """Coarsened exact matching on locked bins. FIRST80 winners vs FIRST75 winners.

    FIRST75 rows that share event_id with FIRST80 on the same ticker are overlapping
    units at different timestamps. They are kept but counted separately as overlap.
    """
    a = df80[df80["W"].astype(bool) & df80["matchable"]].copy()
    # FIRST75 has no game-state join by default; match on split+regime only unless ticker join
    feat_map = df80.set_index("event_id")[["quarter_bin", "score_abs_bin", "lead_state", "home", "matchable"]]
    b = f75[f75["W"].astype(bool)].copy()
    b = b.join(feat_map, on="event_id", how="left", rsuffix="_80")
    overlap_same_ticker = int((b["ticker"].isin(set(df80["ticker"]))).sum()) if len(b) else 0
    keys = ["dataset_split", "quarter_bin", "score_abs_bin", "lead_state"]
    rows = []
    for key, ga in a.groupby(keys, dropna=False):
        gb = b
        for col, val in zip(keys, key if isinstance(key, tuple) else (key,)):
            if col in gb.columns:
                gb = gb[gb[col] == val] if not pd.isna(val) else gb[gb[col].isna()]
        if len(ga) == 0:
            continue
        pa = cond_not40_given_w(ga, "FIRST80")
        pb = cond_not40_given_w(gb, "FIRST75") if len(gb) else None
        diff = None
        if pb and pa["estimate"] is not None and pb["estimate"] is not None:
            diff = pa["estimate"] - pb["estimate"]
        rows.append(
            {
                "split": key[0] if isinstance(key, tuple) else key,
                "quarter_bin": key[1] if isinstance(key, tuple) and len(key) > 1 else None,
                "score_abs_bin": key[2] if isinstance(key, tuple) and len(key) > 2 else None,
                "lead_state": key[3] if isinstance(key, tuple) and len(key) > 3 else None,
                "n_first80_w": pa["n"],
                "p_first80": pa["estimate"],
                "n_first75_w": None if pb is None else pb["n"],
                "p_first75": None if pb is None else pb["estimate"],
                "diff": diff,
                "thin": (pb is None) or (pb["n"] < 15) or (pa["n"] < 15),
            }
        )
    tab = pd.DataFrame(rows)
    usable = tab[tab["thin"] == False] if len(tab) else tab
    oos = usable[usable["split"] == "OOS"] if len(usable) else usable
    return {
        "overlap_first75_tickers_in_first80": overlap_same_ticker,
        "n_strata": int(len(tab)),
        "n_strata_adequate": int(len(usable)),
        "n_oos_adequate": int(len(oos)),
        "mean_diff_adequate": None if not len(usable) else float(usable["diff"].mean()),
        "mean_diff_oos_adequate": None if not len(oos) else float(oos["diff"].mean()),
        "table": tab.to_dict("records"),
        "note": "Bins locked a priori. thin = either side n<15. Overlap means many FIRST75 units are the same games as FIRST80.",
    }


def run(df80: pd.DataFrame, quotes, markets, games) -> dict:
    f80 = cond_not40_given_w(df80, "FIRST80")
    f80_splits = {s: cond_not40_given_w(df80[df80["dataset_split"] == s], s) for s in ("TRAIN", "VALIDATION", "OOS")}
    f75 = first75_control(quotes, markets, games)
    C.write_parquet(C.DATA / "first75_observations.parquet", f75)
    f75_block = cond_not40_given_w(f75, "FIRST75")
    f75_splits = {s: cond_not40_given_w(f75[f75["dataset_split"] == s], s) for s in ("TRAIN", "VALIDATION", "OOS")}
    nf = non_first80_control(df80, quotes, markets, games)
    C.write_parquet(C.DATA / "non_first80_observations.parquet", nf if len(nf) else pd.DataFrame({"empty": []}))
    nf_block = cond_not40_given_w(nf, "NON_FIRST80") if len(nf) else {"n": 0, "estimate": None}
    nf_splits = {
        s: cond_not40_given_w(nf[nf["dataset_split"] == s], s) if len(nf) else {"n": 0}
        for s in ("TRAIN", "VALIDATION", "OOS")
    }
    strata = stratified(df80)
    matched = matched_first75(df80, f75)
    # Overlap diagnostic
    same = set(df80["event_id"]) & set(f75["event_id"]) if len(f75) else set()
    same_ticker = set(zip(df80["event_id"], df80["ticker"])) & set(zip(f75["event_id"], f75["ticker"])) if len(f75) else set()
    out = {
        "FIRST80": {"full": f80, "splits": f80_splits},
        "FIRST75": {
            "full": f75_block,
            "splits": f75_splits,
            "n": int(len(f75)),
            "n_shared_events": len(same),
            "n_shared_event_ticker": len(same_ticker),
            "n_shared_note": (
                "n_shared_event_ticker counts FIRST80 (event,ticker) pairs that are also the "
                "FIRST75 first-reach of that ticker, including losses. It is not comparable to "
                "FIRST75 n_wins."
            ),
        },
        "NON_FIRST80": {
            "full": nf_block,
            "splits": nf_splits,
            "n": int(len(nf)),
            "dropped": nf.attrs.get("dropped") if hasattr(nf, "attrs") else None,
            "definition": nf.attrs.get("definition") if hasattr(nf, "attrs") else None,
        },
        "stratified_first80_winners": strata,
        "matched": matched,
        "control_validity": {
            "first75_almost_identical_to_first80": len(same_ticker) >= 0.9 * C.FROZEN_N,
            "non_first80_is_comeback_select": True,
        },
    }
    # comparison table
    rows = []
    for name, blk, splits in (
        ("FIRST80", f80, f80_splits),
        ("FIRST75", f75_block, f75_splits),
        ("NON_FIRST80", nf_block, nf_splits),
    ):
        rows.append(
            {
                "control": name,
                "split": "FULL",
                "n_total": blk.get("n_total"),
                "n_wins": blk.get("n_wins", blk.get("n")),
                "k_never_t40": blk.get("k"),
                "p_not_t40_given_w": blk.get("estimate"),
                "wilson_lo": (blk.get("wilson") or {}).get("lo"),
                "wilson_hi": (blk.get("wilson") or {}).get("hi"),
            }
        )
        for s, b in splits.items():
            rows.append(
                {
                    "control": name,
                    "split": s,
                    "n_total": b.get("n_total"),
                    "n_wins": b.get("n_wins", b.get("n")),
                    "k_never_t40": b.get("k"),
                    "p_not_t40_given_w": b.get("estimate"),
                    "wilson_lo": (b.get("wilson") or {}).get("lo"),
                    "wilson_hi": (b.get("wilson") or {}).get("hi"),
                }
            )
    C.write_csv(C.RESULTS / "path_survival.csv", pd.DataFrame(rows))
    C.write_csv(C.RESULTS / "control_comparisons.csv", pd.DataFrame(rows))
    C.write_json(C.RESULTS / "path_survival.json", out)
    C.write_parquet(C.DATA / "matched_controls.parquet", pd.DataFrame(matched["table"]))
    C.write_parquet(C.DATA / "path_outcomes.parquet", df80[["event_id", "ticker", "dataset_split", "W", "T40", "win_and_not_T40", "quarter_bin", "score_abs_bin", "lead_state", "matchable"]])
    return out
