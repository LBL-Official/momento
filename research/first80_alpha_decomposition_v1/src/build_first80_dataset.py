"""Load frozen FIRST80. Join causal-at-entry game-state features. Identity gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402

import config as C


def load_frozen_candidates() -> pd.DataFrame:
    cands = json.loads((C.AUDIT / "candidates.json").read_text())
    first = [
        c
        for c in cands
        if c.get("status") == "FIRST_80" and c.get("expiration_result_yes") is not None
    ]
    df = pd.DataFrame(first)
    df["dataset_split"] = [C.canon_split(s) for s in df["dataset_split"]]
    df["W"] = df["expiration_result_yes"].astype(bool)
    df["T40"] = df["stop_close_triggered"].astype(bool)
    df["not_T40"] = ~df["T40"]
    df["win_and_not_T40"] = df["W"] & df["not_T40"]
    df["win_and_T40"] = df["W"] & df["T40"]
    df["loss_and_not_T40"] = (~df["W"]) & df["not_T40"]
    df["loss_and_T40"] = (~df["W"]) & df["T40"]
    df["home"] = df["team"] == df["home_team"]
    return df, cands


def identity_gate(df: pd.DataFrame) -> dict:
    n = len(df)
    w = int(df["W"].sum())
    t40 = int(df["T40"].sum())
    surv = int(df["win_and_not_T40"].sum())
    w_t = int(df["win_and_T40"].sum())
    l_n = int(df["loss_and_not_T40"].sum())
    l_t = int(df["loss_and_T40"].sum())
    ok = (
        n == C.FROZEN_N
        and w == C.FROZEN_WINS
        and t40 == C.FROZEN_STOPS
        and surv == C.FROZEN_SURVIVORS
        and w_t == C.FROZEN_WIN_AND_T40
        and l_n == C.FROZEN_LOSS_AND_NO40
        and l_t == C.FROZEN_LOSS_AND_T40
    )
    return {
        "gate": "FROZEN_IDENTITY",
        "status": "PASS" if ok else "FAIL",
        "observed": {
            "n": n,
            "W": w,
            "T40": t40,
            "W_and_not_T40": surv,
            "W_and_T40": w_t,
            "L_and_not_T40": l_n,
            "L_and_T40": l_t,
        },
        "expected": {
            "n": C.FROZEN_N,
            "W": C.FROZEN_WINS,
            "T40": C.FROZEN_STOPS,
            "W_and_not_T40": C.FROZEN_SURVIVORS,
            "W_and_T40": C.FROZEN_WIN_AND_T40,
            "L_and_not_T40": C.FROZEN_LOSS_AND_NO40,
            "L_and_T40": C.FROZEN_LOSS_AND_T40,
        },
        "definition_source": str(C.AUDIT / "candidates.json"),
        "note": "Candle path. Not fills.",
    }


def join_entry_state(df: pd.DataFrame) -> pd.DataFrame:
    feat = pq.read_table(C.GPE_V2 / "features_entry.parquet").to_pandas()
    keep = [
        "ticker",
        "event_id",
        "nba_game_id",
        "alignment_confidence",
        "feature_status",
        "quarter",
        "game_seconds_remaining",
        "game_seconds_elapsed",
        "score_differential",
        "absolute_score_differential",
        "team_is_leading",
        "team_is_trailing",
        "game_is_tied",
        "flag_Q4",
        "flag_OT",
        "spread_cents",
        "momentum_5m_cents",
        "vol_5m_cents",
        "minutes_from_70_to_80",
        "minutes_since_first_gw_candle",
        "Y_40_CLOSE",
    ]
    keep = [c for c in keep if c in feat.columns]
    sub = feat[keep].copy()
    out = df.merge(sub, on=["ticker", "event_id"], how="left", suffixes=("", "_feat"))
    if "Y_40_CLOSE" in out.columns:
        mismatch = int(((out["Y_40_CLOSE"].fillna(-1).astype(int) == 1) != out["T40"]).sum())
        out.attrs["y40_mismatch"] = mismatch
    out["score_abs_bin"] = [_score_bin(v) for v in out.get("absolute_score_differential", pd.Series([None] * len(out)))]
    out["lead_state"] = [
        "LEAD" if a is True else ("TRAIL" if b is True else ("TIE" if c is True else None))
        for a, b, c in zip(
            out.get("team_is_leading", pd.Series([None] * len(out))),
            out.get("team_is_trailing", pd.Series([None] * len(out))),
            out.get("game_is_tied", pd.Series([None] * len(out))),
        )
    ]
    q = out.get("quarter")
    out["quarter_bin"] = [
        None if pd.isna(v) else ("OT" if float(v) >= 5 else str(int(v))) for v in (q if q is not None else [None] * len(out))
    ]
    out["matchable"] = out["alignment_confidence"].isin(["HIGH", "MEDIUM"]) & out["score_differential"].notna()
    return out


def _score_bin(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    x = abs(float(v))
    for lo, hi, name in C.SCORE_ABS_BINS:
        if lo <= x <= hi:
            return name
    return None


def build() -> tuple[pd.DataFrame, dict]:
    df, cands = load_frozen_candidates()
    gate = identity_gate(df)
    if gate["status"] != "PASS":
        raise RuntimeError(f"HALT frozen identity {gate}")
    out = join_entry_state(df)
    y_mis = int(out.attrs.get("y40_mismatch") or 0)
    if y_mis:
        raise RuntimeError(f"HALT Y_40_CLOSE mismatch vs stop_close_triggered: {y_mis}")
    meta = {
        "identity": gate,
        "n_matchable_HIGH_MEDIUM": int(out["matchable"].sum()),
        "n_unusable_or_unaligned": int((~out["matchable"]).sum()),
        "splits": out.groupby("dataset_split").size().to_dict(),
        "feature_status_all_causal": bool((out["feature_status"] == "CAUSAL_AT_ENTRY").all())
        if "feature_status" in out
        else None,
        "cands_status_counts": pd.Series([c.get("status") for c in cands]).value_counts().to_dict(),
        "audit_functions": ["A.load_markets", "A.scan quality", "A.build_candidates"],
        "candle_path_not_fill": True,
    }
    C.write_parquet(C.DATA / "first80_observations.parquet", out)
    C.write_json(C.DATA / "identity_gate.json", meta)
    return out, meta
