#!/usr/bin/env python3
"""Can F_τ predict the FIRST_q four-cell better than the unconditional rate?

Information set F_τ = observables at the FIRST75 / FIRST80 timestamp.
W and T40 are future labels and are never features.

Locked a priori (alpha-decomp matching bins; not retuned):
  quarter_bin ∈ {1,2,3,4,OT}
  score_abs_bin ∈ {0-4, 5-9, 10-19, 20+}
  lead_state ∈ {LEAD, TRAIL, TIE}
  home ∈ {H, A}

Model: TRAIN empirical multinomial by stratum, Laplace +1.
Baseline: TRAIN unconditional four-cell, Laplace +1.
Unaligned / missing score: fallback to the TRAIN unconditional.

Decision (locked before OOS inspection):
  ESTABLISHED only if VAL and OOS both have lower log-loss than baseline
  AND the OOS paired log-loss delta CI (mean ± 1.96 se) excludes 0.

NBA 2025-26 frozen tape only. Research. Not a live model.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

NBA_SCRIPTS = Path(__file__).resolve().parent
GPE = NBA_SCRIPTS / "game_path_engine_v2"
if str(GPE) not in sys.path:
    sys.path.insert(0, str(GPE))
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))

import first75_slice_not40_given_w as F75  # noqa: E402
import first80_quarter_barrier_survival as Q  # noqa: E402
import nba_80_40_execution_audit as A  # noqa: E402
from pbp import snap_to_entry, team_scores  # noqa: E402

CELLS = ("WIN_SURVIVE", "WIN_T40", "LOSE_SURVIVE", "LOSE_T40")
SCORE_ABS_BINS = ((0, 4, "0-4"), (5, 9, "5-9"), (10, 19, "10-19"), (20, 10**9, "20+"))
LAPLACE = 1.0
P_CLIP = 1e-12
PRIMARY_ALIGN = frozenset({"HIGH", "MEDIUM"})
SPLIT_RESEARCH_END = "2025-12-31"
SPLIT_VAL_END = "2026-03-15"

REPO = Path("/Users/user/Desktop/Momento")
OUT = (
    REPO
    / "Backtesting Suite"
    / "Data"
    / "NBA"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "nba"
    / "firstq_fourcell_asof_predictor"
)
REPORTS = REPO / "research" / "firstq_fourcell_asof_predictor"
DOCS = REPO / "docs" / "research" / "firstq_fourcell_asof_predictor"


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cell_of(w: bool, t40: bool) -> str:
    if w and not t40:
        return "WIN_SURVIVE"
    if w and t40:
        return "WIN_T40"
    if (not w) and not t40:
        return "LOSE_SURVIVE"
    return "LOSE_T40"


def score_abs_bin(v) -> str | None:
    if v is None:
        return None
    x = abs(float(v))
    for lo, hi, name in SCORE_ABS_BINS:
        if lo <= x <= hi:
            return name
    return None


def split_of(game_date: str | None) -> str:
    if not game_date:
        return "UNSPLIT"
    if game_date <= SPLIT_RESEARCH_END:
        return "TRAIN"
    if game_date <= SPLIT_VAL_END:
        return "VALIDATION"
    return "OOS"


def lead_state(team_score, opp_score) -> str | None:
    if team_score is None or opp_score is None:
        return None
    if team_score > opp_score:
        return "LEAD"
    if team_score < opp_score:
        return "TRAIL"
    return "TIE"


def quarter_bin(period) -> str | None:
    if period is None:
        return None
    p = int(period)
    if p >= 5:
        return "OT"
    if 1 <= p <= 4:
        return str(p)
    return None


def snap_asof(rec: dict, xwalk: dict, cache: dict) -> dict:
    """Clock + score at reach_ts. No post-τ fields."""
    align = Q.align_entry(rec, xwalk, cache)
    team = rec.get("team")
    home = rec.get("home_team")
    team_is_home = None if not team or not home else team == home
    team_score = opp_score = None
    nba_id = align.get("nba_game_id")
    if nba_id and rec.get("first_80_timestamp") is not None:
        packed = Q._pbp_pack(nba_id, cache)
        if packed is not None:
            actions, _header = packed
            snap = snap_to_entry(actions, int(rec["first_80_timestamp"]))
            idx = snap.get("snap_idx")
            row = actions[idx] if idx is not None and 0 <= idx < len(actions) else None
            if team_is_home is not None:
                team_score, opp_score = team_scores(row, team_is_home)
    conf = align.get("alignment_confidence")
    qbin = quarter_bin(align.get("entry_period"))
    sbin = score_abs_bin(
        None if team_score is None or opp_score is None else team_score - opp_score
    )
    lead = lead_state(team_score, opp_score)
    home_flag = None if team_is_home is None else ("H" if team_is_home else "A")
    matchable = (
        conf in PRIMARY_ALIGN
        and qbin is not None
        and sbin is not None
        and lead is not None
        and home_flag is not None
    )
    stratum = (
        f"{qbin}|{sbin}|{lead}|{home_flag}"
        if matchable
        else "UNALIGNED"
    )
    return {
        "alignment_confidence": conf,
        "entry_quarter_bucket": align.get("entry_quarter_bucket"),
        "quarter_bin": qbin,
        "score_abs_bin": sbin,
        "lead_state": lead,
        "home": home_flag,
        "team_score": team_score,
        "opp_score": opp_score,
        "matchable": matchable,
        "stratum": stratum,
        "feature_status": "CAUSAL_AT_ENTRY" if matchable else "UNALIGNED_FALLBACK",
    }


def attach_asof(rows: list[dict]) -> list[dict]:
    xwalk = Q.load_crosswalk()
    cache: dict = {}
    out = []
    for r in rows:
        rec = dict(r)
        rec.update(snap_asof(rec, xwalk, cache))
        rec["cell"] = cell_of(bool(rec["W"]), bool(rec["T40"]))
        rec["dataset_split"] = split_of(rec.get("game_date"))
        out.append(rec)
    return out


def counts_by_stratum(rows: list[dict]) -> dict[str, Counter]:
    by: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by[r["stratum"]][r["cell"]] += 1
    return dict(by)


def probs_from_counts(c: Counter, laplace: float = LAPLACE) -> dict[str, float]:
    tot = sum(c[k] for k in CELLS) + laplace * len(CELLS)
    return {k: (c[k] + laplace) / tot for k in CELLS}


def fit(train: list[dict]) -> dict:
    uncond = Counter(r["cell"] for r in train)
    by = counts_by_stratum([r for r in train if r["stratum"] != "UNALIGNED"])
    return {
        "unconditional": probs_from_counts(uncond),
        "unconditional_counts": {k: uncond[k] for k in CELLS},
        "n_train": len(train),
        "n_train_matchable": sum(1 for r in train if r["matchable"]),
        "strata": {s: probs_from_counts(c) for s, c in by.items()},
        "strata_n": {s: int(sum(c.values())) for s, c in by.items()},
        "laplace": LAPLACE,
        "features": ("quarter_bin", "score_abs_bin", "lead_state", "home"),
    }


def predict_row(row: dict, model: dict) -> dict[str, float]:
    if row["stratum"] != "UNALIGNED" and row["stratum"] in model["strata"]:
        return model["strata"][row["stratum"]]
    return model["unconditional"]


def logloss(p_true: float) -> float:
    return -math.log(max(p_true, P_CLIP))


def brier(probs: dict[str, float], cell: str) -> float:
    return sum((probs[k] - (1.0 if k == cell else 0.0)) ** 2 for k in CELLS)


def eval_split(rows: list[dict], model: dict) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    ll_m = ll_b = br_m = br_b = 0.0
    deltas = []
    hits_m = hits_b = 0
    pred_cells = Counter()
    for r in rows:
        cell = r["cell"]
        pm = predict_row(r, model)
        pb = model["unconditional"]
        pred_cells[max(CELLS, key=lambda k: pm[k])] += 1
        lm, lb = logloss(pm[cell]), logloss(pb[cell])
        ll_m += lm
        ll_b += lb
        br_m += brier(pm, cell)
        br_b += brier(pb, cell)
        deltas.append(lm - lb)
        hits_m += int(max(CELLS, key=lambda k: pm[k]) == cell)
        hits_b += int(max(CELLS, key=lambda k: pb[k]) == cell)
    mean_d = sum(deltas) / n
    var = sum((x - mean_d) ** 2 for x in deltas) / n
    se = math.sqrt(var / n)
    lo, hi = mean_d - 1.96 * se, mean_d + 1.96 * se
    return {
        "n": n,
        "logloss_model": round(ll_m / n, 6),
        "logloss_uncond": round(ll_b / n, 6),
        "logloss_delta": round(mean_d, 6),
        "logloss_delta_se": round(se, 6),
        "logloss_delta_ci95": [round(lo, 6), round(hi, 6)],
        "delta_ci_excludes_0": bool(hi < 0 or lo > 0),
        "model_better_logloss": (ll_m / n) < (ll_b / n),
        "brier_model": round(br_m / n, 6),
        "brier_uncond": round(br_b / n, 6),
        "acc_model": round(hits_m / n, 4),
        "acc_uncond": round(hits_b / n, 4),
        "predicted_mode_counts": {k: pred_cells[k] for k in CELLS},
        "observed_cells": {k: sum(1 for r in rows if r["cell"] == k) for k in CELLS},
    }


def decision(val: dict, oos: dict) -> dict:
    ok = bool(
        val.get("n")
        and oos.get("n")
        and val.get("model_better_logloss")
        and oos.get("model_better_logloss")
        and oos.get("delta_ci_excludes_0")
        and (oos.get("logloss_delta_ci95") or [1, 1])[1] < 0
    )
    return {
        "token": "ASOF_FOURCELL_LIFT" if ok else "NO_ASOF_LIFT",
        "rule": (
            "VAL and OOS log-loss both beat TRAIN unconditional, "
            "and OOS paired delta CI excludes 0 on the negative side."
        ),
        "established": ok,
    }


def load_nba_first80() -> list[dict]:
    rows = F75.as_first80_rows(
        F75.frozen_first80(
            A.ROOT / "derived" / "nba" / "first80_execution_audit" / "candidates.json"
        )
    )
    F75.halt_joints(F75.joints(rows), F75.NBA_F80, "NBA frozen FIRST80")
    return rows


def load_nba_first75() -> list[dict]:
    markets = A.load_markets()
    games = A.load_games()
    games_by = {g["event_id"]: g for g in games}
    quotes = F75.load_quotes(A.NORM / "candles_1m", F75.quote_meta_nba_style(markets, games))
    raw = F75.build_first_reach(markets, games, quotes, F75.HIT75, "FIRST_75")
    f75 = F75.settled(raw, "FIRST_75")
    j = F75.joints(f75)
    if j["n"] != F75.NBA_F75_N or j["W"] != F75.NBA_F75_W or j["W_not_T40"] != F75.NBA_F75_NOT40_GIVEN_W:
        raise IdentityHalt(f"HALT NBA FIRST75 {j}")
    for r in f75:
        g = games_by.get(r["event_id"], {})
        r["home_team"] = g.get("home_team") or g.get("home_team_code")
    return f75


def run_threshold(rows: list[dict], label: str, quote_k: float) -> dict:
    labeled = attach_asof(rows)
    cells = Counter(r["cell"] for r in labeled)
    if sum(cells.values()) != len(labeled):
        raise IdentityHalt("HALT cell coverage")
    train = [r for r in labeled if r["dataset_split"] == "TRAIN"]
    val = [r for r in labeled if r["dataset_split"] == "VALIDATION"]
    oos = [r for r in labeled if r["dataset_split"] == "OOS"]
    model = fit(train)
    ev = {
        "TRAIN": eval_split(train, model),
        "VALIDATION": eval_split(val, model),
        "OOS": eval_split(oos, model),
        "FULL": eval_split(labeled, model),
        "OOS_matchable": eval_split([r for r in oos if r["matchable"]], model),
        "OOS_Q2Q3": eval_split(
            [r for r in oos if r.get("entry_quarter_bucket") in ("Q2", "Q3")],
            model,
        ),
    }
    dec = decision(ev["VALIDATION"], ev["OOS"])
    return {
        "label": label,
        "quote_k": quote_k,
        "n": len(labeled),
        "n_matchable": sum(1 for r in labeled if r["matchable"]),
        "cells": {k: cells[k] for k in CELLS},
        "cell_probs": {k: cells[k] / len(labeled) for k in CELLS},
        "splits": {s: sum(1 for r in labeled if r["dataset_split"] == s) for s in ("TRAIN", "VALIDATION", "OOS")},
        "n_strata_train": len(model["strata"]),
        "model": {
            "unconditional": model["unconditional"],
            "n_train": model["n_train"],
            "n_train_matchable": model["n_train_matchable"],
            "n_strata": len(model["strata"]),
            "features": list(model["features"]),
            "laplace": model["laplace"],
            "forbidden_in_F": ["W", "T40", "expiration", "first_40_close_ts"],
        },
        "eval": ev,
        "decision": dec,
        "information_set": "F_tau = {quarter, |score_diff| bin, lead/trail/tie, home} at reach_ts",
    }


def write_report(summary: dict) -> None:
    lines = [
        "# As-of four-cell predictor at FIRST_q",
        "",
        "Question: given only information at the threshold timestamp, does the four-cell",
        "distribution differ from the unconditional TRAIN rate in a way that",
        "improves VAL and OOS log-loss?",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "NO FUTURE LABELS IN F_TAU",
        "```",
        "",
        "Locked features: quarter, score-abs bin, lead state, home.",
        "Locked bins are the 2026-09-04 alpha-decomp matching bins.",
        "Unaligned rows use the TRAIN unconditional. Laplace +1.",
        "W and T40 are labels only.",
        "",
        f"Decision token: **{summary['first80']['decision']['token']}** (FIRST80), "
        f"**{summary['first75']['decision']['token']}** (FIRST75).",
        "",
        summary["first80"]["decision"]["rule"],
        "",
    ]
    for key, title in (("first80", "FIRST80"), ("first75", "FIRST75")):
        b = summary[key]
        ev = b["eval"]
        lines.extend(
            [
                f"## {title}",
                "",
                f"n={b['n']} matchable={b['n_matchable']} TRAIN strata={b['n_strata_train']}",
                f"Four-cell: {b['cells']}",
                "",
                "| Split | n | logloss model | logloss uncond | Δ | Δ 95% | beats? |",
                "|---|---:|---:|---:|---:|---|---|",
            ]
        )
        for split in ("TRAIN", "VALIDATION", "OOS", "OOS_matchable", "OOS_Q2Q3"):
            e = ev[split]
            if not e.get("n"):
                continue
            ci = e["logloss_delta_ci95"]
            lines.append(
                f"| {split} | {e['n']} | {e['logloss_model']} | {e['logloss_uncond']} | "
                f"{e['logloss_delta']:+.4f} | {ci[0]:+.4f}–{ci[1]:+.4f} | "
                f"{'yes' if e['model_better_logloss'] else 'no'} |"
            )
        lines.extend(
            [
                "",
                f"Token: **{b['decision']['token']}** "
                f"(established={b['decision']['established']})",
                "",
            ]
        )
    lines.extend(
        [
            "## What this is not",
            "",
            "- Not a live order, fill, or 2026–27 deployment.",
            "- Not a claim that any stratum should be traded.",
            "- Not a new FIRST75 / FIRST80 definition.",
            "- Beating TRAIN in-sample is not evidence.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    for dest in (OUT, REPORTS, DOCS):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(text)


def analyze() -> dict:
    print("FIRST80 as-of", flush=True)
    f80 = run_threshold(load_nba_first80(), "FIRST80", 0.80)
    print("FIRST75 as-of", flush=True)
    f75 = run_threshold(load_nba_first75(), "FIRST75", 0.75)
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "candle_path_not_fill": True,
        "no_future_in_F": True,
        "first80": f80,
        "first75": f75,
    }


def write_outputs(summary: dict) -> None:
    for dest in (OUT, REPORTS, DOCS):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_report(summary)
    print(
        json.dumps(
            {
                "first80": summary["first80"]["decision"],
                "first75": summary["first75"]["decision"],
                "first80_oos": summary["first80"]["eval"]["OOS"],
                "first75_oos": summary["first75"]["eval"]["OOS"],
            },
            indent=2,
        )
    )


def main() -> int:
    write_outputs(analyze())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
