"""MODULE A — terminal calibration vs 80% and threshold surface."""

from __future__ import annotations

import pandas as pd

import config as C
import stats_util as S
import quotes as Q


def terminal_block(df: pd.DataFrame, label: str) -> dict:
    k = int(df["W"].sum())
    n = int(len(df))
    rec = S.rate_block(k, n, C.NULL_P_W)
    rec["label"] = label
    rec["split"] = label
    rec["weighting"] = "ONE_OBSERVATION_PER_GAME"
    return rec


def by_split(df: pd.DataFrame) -> dict:
    out = {"FULL": terminal_block(df, "FULL")}
    for s in ("TRAIN", "VALIDATION", "OOS"):
        out[s] = terminal_block(df[df["dataset_split"] == s], s)
    for r in ("EARLY", "MIDDLE", "LATE"):
        out[f"regime_{r}"] = terminal_block(df[df["regime"] == r], r)
    return out


def threshold_surface(quotes, markets, games) -> pd.DataFrame:
    rows = []
    for q in C.THRESHOLDS_CENTS:
        tab = Q.first_team_at_threshold(markets, games, quotes, int(q * 100))
        reached = tab[tab["status"] == "FIRST_REACH"].copy()
        settled = reached[reached["W"].notna()]
        k = int(settled["W"].sum()) if len(settled) else 0
        n = int(len(settled))
        blk = S.rate_block(k, n, q / 100.0)
        blk.update(
            {
                "threshold_cents": q,
                "n_events": int(len(tab)),
                "n_reach": int(len(reached)),
                "n_tie_same_minute": int((tab["status"] == "TIE_SAME_MINUTE").sum()),
                "n_no_reach": int((tab["status"] == "NO_REACH").sum()),
                "n_settled": n,
                "p_hat": blk["estimate"],
                "q": q / 100.0,
                "calibration_deviation": None if blk["estimate"] is None else blk["estimate"] - q / 100.0,
                "label": "FirstReach(q) terminal win rate minus q",
            }
        )
        for s in ("TRAIN", "VALIDATION", "OOS"):
            sub = settled[settled["dataset_split"] == s]
            sb = S.rate_block(int(sub["W"].sum()) if len(sub) else 0, int(len(sub)), q / 100.0)
            blk[f"{s}_n"] = sb["n"]
            blk[f"{s}_p"] = sb["estimate"]
            blk[f"{s}_dev"] = None if sb["estimate"] is None else sb["estimate"] - q / 100.0
        rows.append(blk)
        C.write_parquet(C.DATA / f"first_reach_{q}.parquet", settled if len(settled) else reached)
    return pd.DataFrame(rows)


def verify_reconstructed_first80(df80: pd.DataFrame, quotes, markets, games) -> dict:
    tab = Q.first_team_at_threshold(markets, games, quotes, C.HIT80_E4)
    rec = tab[tab["status"] == "FIRST_REACH"]
    rec = rec[rec["W"].notna()]
    left = df80[["event_id", "ticker", "first_80_timestamp"]].copy()
    right = rec[["event_id", "ticker", "reach_ts"]].copy()
    m = left.merge(right, on="event_id", how="outer", suffixes=("_frozen", "_recon"))
    n_mismatch = int((m["ticker_frozen"] != m["ticker_recon"]).fillna(True).sum())
    ts_mis = int((m["first_80_timestamp"] != m["reach_ts"]).fillna(True).sum())
    ok = n_mismatch == 0 and ts_mis == 0 and len(rec) == C.FROZEN_N
    return {
        "gate": "RECONSTRUCTED_FIRST80",
        "status": "PASS" if ok else "FAIL",
        "n_recon": int(len(rec)),
        "ticker_mismatch": n_mismatch,
        "timestamp_mismatch": ts_mis,
        "note": "Same tradable-cross rule. Must match frozen candidates.",
    }


def run(df: pd.DataFrame, quotes, markets, games) -> dict:
    recon = verify_reconstructed_first80(df, quotes, markets, games)
    if recon["status"] != "PASS":
        raise RuntimeError(f"HALT {recon}")
    cal = by_split(df)
    surf = threshold_surface(quotes, markets, games)
    C.write_json(C.RESULTS / "terminal_calibration.json", cal)
    rows = []
    for k, v in cal.items():
        rows.append({"split": k, **{kk: vv for kk, vv in v.items() if not isinstance(vv, dict)}, "wilson_lo": (v.get("wilson") or {}).get("lo"), "wilson_hi": (v.get("wilson") or {}).get("hi"), "p_one_sided": (v.get("vs_null") or {}).get("p_one_sided")})
    C.write_csv(C.RESULTS / "terminal_calibration.csv", pd.DataFrame(rows))
    oos_rows = pd.DataFrame([{"split": s, **{kk: vv for kk, vv in cal[s].items() if not isinstance(vv, dict)}, "wilson_lo": (cal[s].get("wilson") or {}).get("lo"), "wilson_hi": (cal[s].get("wilson") or {}).get("hi")} for s in ("TRAIN", "VALIDATION", "OOS")])
    C.write_csv(C.RESULTS / "terminal_calibration_oos.csv", oos_rows)
    C.write_parquet(C.DATA / "threshold_calibration.parquet", surf)
    C.write_csv(C.RESULTS / "threshold_calibration.csv", flatten_threshold_surface(surf))
    return {"calibration": cal, "surface": surf, "recon": recon}


def flatten_threshold_surface(surf: pd.DataFrame) -> pd.DataFrame:
    """CSV-friendly columns. Nested CI dicts stay in parquet/JSON only."""
    from collections.abc import Mapping

    def _get(x, key):
        if x is None:
            return None
        if isinstance(x, Mapping):
            return x.get(key)
        if hasattr(x, "__getitem__"):
            try:
                return x[key]
            except Exception:
                return None
        return None

    out = surf.copy()
    if "wilson" in out.columns:
        out["wilson_lo"] = out["wilson"].apply(lambda x: _get(x, "lo"))
        out["wilson_hi"] = out["wilson"].apply(lambda x: _get(x, "hi"))
        out = out.drop(columns=["wilson"])
    if "clopper_pearson" in out.columns:
        out["clopper_pearson_lo"] = out["clopper_pearson"].apply(lambda x: _get(x, "lo"))
        out["clopper_pearson_hi"] = out["clopper_pearson"].apply(lambda x: _get(x, "hi"))
        out = out.drop(columns=["clopper_pearson"])
    if "vs_null" in out.columns:
        out["p_one_sided_vs_q"] = out["vs_null"].apply(lambda x: _get(x, "p_one_sided"))
        out["excess_k_vs_q"] = out["vs_null"].apply(lambda x: _get(x, "excess_k"))
        out = out.drop(columns=["vs_null"])
    keep = [
        "threshold_cents",
        "q",
        "n_events",
        "n_reach",
        "n_tie_same_minute",
        "n_no_reach",
        "n_settled",
        "n",
        "k",
        "p_hat",
        "estimate",
        "calibration_deviation",
        "se_iid",
        "wilson_lo",
        "wilson_hi",
        "clopper_pearson_lo",
        "clopper_pearson_hi",
        "p_one_sided_vs_q",
        "excess_k_vs_q",
        "TRAIN_n",
        "TRAIN_p",
        "TRAIN_dev",
        "VALIDATION_n",
        "VALIDATION_p",
        "VALIDATION_dev",
        "OOS_n",
        "OOS_p",
        "OOS_dev",
        "label",
    ]
    cols = [c for c in keep if c in out.columns]
    return out[cols]
