"""Γ_t — how S_t was reached. Backward-looking only."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.canonical.events import events_visible, project_events
from roller.state.missingness import section
from roller.state.sequences import event_type_sequence
from roller.state.volatility import margin_volatility


def _margin(rec: dict[str, Any]) -> int | None:
    raw = rec.get("score_differential_home")
    if raw not in (None, ""):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    try:
        h = int(rec.get("home_score") or 0)
        a = int(rec.get("away_score") or 0)
        return h - a
    except (TypeError, ValueError):
        return None


def trajectory_features(events, as_of, end_of_day: bool = False) -> dict[str, Any]:
    if isinstance(events, pd.DataFrame):
        vis = events_visible(project_events(events), as_of, end_of_day=end_of_day) if not events.empty else events
        recs = vis.to_dict("records") if vis is not None and not vis.empty else []
    else:
        df = pd.DataFrame(list(events or []))
        if df.empty:
            recs = []
        else:
            if "available_at" not in df.columns:
                raise ValueError("trajectory events require available_at")
            vis = events_visible(project_events(df), as_of, end_of_day=end_of_day)
            recs = vis.to_dict("records") if vis is not None and not vis.empty else []

    if not recs:
        return section("PARTIAL", {"n_events": 0, "margin_path": [], "score_margin": None})

    margins = []
    for rec in recs:
        m = _margin(rec)
        if m is not None:
            margins.append(m)
    data = {
        "n_events": len(recs),
        "score_margin": margins[-1] if margins else None,
        "margin_path": margins[-16:],
        "event_type_sequence": event_type_sequence(recs),
        "volatility": margin_volatility(margins),
        "lookahead": False,
    }
    return section("REAL", data)
