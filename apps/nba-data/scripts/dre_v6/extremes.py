"""Pre-registered tail buckets of mean_SIR. Measurements only."""

from __future__ import annotations

from . import config as C
from .sir import split_trades


def _bucket(tr, mask, name: str) -> dict:
    sub = tr[mask]
    return {
        "name": name,
        "n_trades": int(len(sub)),
        "n_games": int(sub["event_id"].nunique()) if len(sub) else 0,
        "mean_sir": float(sub["mean_sir"].mean()) if len(sub) else None,
        "mean_pi": float(sub["pi_terminal"].mean()) if len(sub) else None,
        "p_settle_yes": float(sub["y_settle_yes"].mean()) if len(sub) else None,
        "mean_r": float(sub["mean_r"].mean()) if len(sub) else None,
        "sign_correct": (
            None
            if not len(sub) or sub["mean_r"].isna().all() or sub["mean_sir"].isna().all()
            else bool((sub["mean_sir"].mean() > 0 and sub["mean_r"].mean() > 0) or (sub["mean_sir"].mean() < 0 and sub["mean_r"].mean() < 0))
        ),
        "weighting": C.SURFACE_WEIGHTING_PRIMARY,
    }


def measure(trades) -> dict:
    by_split = {}
    for split in C.SPLITS:
        tr = split_trades(trades, split)
        base = _bucket(tr, tr["abs_mean_sir"] < C.BASELINE_ABS_CENTS, "abs_sir_lt_1")
        tails = []
        for k in C.TAIL_KS:
            pos = _bucket(tr, tr["mean_sir"] > k, f"mean_sir_gt_{int(k)}")
            neg = _bucket(tr, tr["mean_sir"] < -k, f"mean_sir_lt_{-int(k)}")
            tails.append({"k": k, "positive": pos, "negative": neg})
        by_split[split] = {"baseline": base, "tails": tails, "n_trades": int(len(tr)), "weighting": C.SURFACE_WEIGHTING_PRIMARY}
    return {
        "ks": list(C.TAIL_KS),
        "baseline_abs_cents": C.BASELINE_ABS_CENTS,
        "by_split": by_split,
        "note": "Pre-registered cuts. No post-OOS threshold search.",
    }
