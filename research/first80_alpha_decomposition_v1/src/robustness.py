"""Clustered bootstrap. Games are not automatically independent."""

from __future__ import annotations

import numpy as np
import pandas as pd

import config as C
import stats_util as S


def _rate(values, _clusters):
    return float(np.mean(values))


def run(df: pd.DataFrame) -> dict:
    w = df["W"].astype(float).to_numpy()
    event = df["event_id"].to_numpy()
    team = df["team"].fillna("UNK").to_numpy()
    date = df["game_date"].fillna("UNK").to_numpy()
    iid = S.rate_block(int(df["W"].sum()), len(df), C.NULL_P_W)
    boot_game = S.cluster_bootstrap_mean(w, event, _rate)
    boot_team = S.cluster_bootstrap_mean(w, team, _rate)
    boot_date = S.cluster_bootstrap_mean(w, date, _rate)
    # path term among winners
    ww = df[df["W"].astype(bool)]
    surv = (~ww["T40"]).astype(float).to_numpy()
    boot_surv = S.cluster_bootstrap_mean(surv, ww["event_id"].to_numpy(), _rate)
    out = {
        "P_W": {
            "iid": iid,
            "bootstrap_game": boot_game,
            "bootstrap_team": boot_team,
            "bootstrap_date": boot_date,
        },
        "P_not_T40_given_W": {
            "iid_n": int(len(ww)),
            "iid_p": float(surv.mean()) if len(surv) else None,
            "bootstrap_game": boot_surv,
        },
        "repeat_teams": int(df["team"].value_counts().gt(1).sum()),
        "note": "If cluster intervals are materially wider than iid, do not treat n=1230 as independent Bernoulli trials.",
    }
    C.write_json(C.RESULTS / "robustness_bootstrap.json", out)
    return out
