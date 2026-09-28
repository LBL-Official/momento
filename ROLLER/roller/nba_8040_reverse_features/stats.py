"""Descriptive stats. Not edge."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.catalog import spec_by_name
from roller.nba_8040_reverse_features.locks import GAIN_CENTS, LOSS_CENTS
from roller.choosin_texas.ev import book_cents, ev_payload


def population_row(labels: pd.DataFrame, *, name: str) -> dict[str, Any]:
    n = int(len(labels))
    s_n = int(labels["s"].sum())
    t40 = n - s_n
    payload = ev_payload(n=n, s_n=s_n, stop_cents=40)
    return {
        "period": name,
        "n": n,
        "survivors": s_n,
        "t40": t40,
        "survival_pct": float(s_n / n * 100) if n else None,
        "t40_pct": float(t40 / n * 100) if n else None,
        "ev_per_trade_display": payload["ev_per_trade_display"],
        "book_cents": book_cents(s_n, n, gain=GAIN_CENTS, loss=LOSS_CENTS),
        "w_and_t40": int(labels["w_and_t40"].sum()),
        "l_and_t40": int(labels["l_and_t40"].sum()),
    }


def _observed(features: pd.DataFrame, name: str) -> pd.Series:
    status = features.get(f"{name}__status")
    series = features[name]
    if status is None:
        return series.dropna()
    return series[status.eq("OBSERVED")].dropna()


def describe_feature(features: pd.DataFrame, name: str) -> dict[str, Any]:
    spec = spec_by_name()[name]
    series = _observed(features, name)
    n = int(len(features))
    avail = int(len(series))
    missing = n - avail
    body: dict[str, Any] = {
        "feature": name,
        "feature_class": spec.feature_class,
        "n": n,
        "available_n": avail,
        "missing_n": missing,
        "missing_rate": float(missing / n) if n else None,
        "source": spec.source,
    }
    if avail == 0:
        return body
    values = series.astype(float)
    if spec.kind == "binary":
        body["share"] = float(values.mean())
        body["count"] = int(values.sum())
        return body
    arr = values.to_numpy(dtype=float)
    body.update(
        {
            "mean": float(arr.mean()),
            "median": float(np.median(arr)),
            "std": float(arr.std(ddof=0)),
            "p10": float(np.quantile(arr, 0.10)),
            "p25": float(np.quantile(arr, 0.25)),
            "p75": float(np.quantile(arr, 0.75)),
            "p90": float(np.quantile(arr, 0.90)),
        }
    )
    return body


def smd(left: pd.Series, right: pd.Series) -> float | None:
    a = left.dropna().astype(float).to_numpy()
    b = right.dropna().astype(float).to_numpy()
    if len(a) < 2 or len(b) < 2:
        return None
    pooled = np.sqrt((a.var(ddof=0) + b.var(ddof=0)) / 2.0)
    if pooled < 1e-12:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)
