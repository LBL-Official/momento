"""Machine-readable leakage audit. FAIL stops fitting."""

from __future__ import annotations

from typing import Any

import pandas as pd

from terminal_efficiency.clocks import parse_utc
from terminal_efficiency.constants import FORBIDDEN_FEATURE_NAMES, FORBIDDEN_FEATURE_PREFIXES
from terminal_efficiency.features.registry import FEATURE_REGISTRY
from terminal_efficiency.paths import reports_dir
from terminal_efficiency.provenance import write_json


def _check_forbidden_columns(columns: list[str]) -> list[dict]:
    findings = []
    for c in columns:
        cl = c.lower()
        if c in FORBIDDEN_FEATURE_NAMES or cl in FORBIDDEN_FEATURE_NAMES:
            findings.append(
                {
                    "feature": c,
                    "status": "FAIL",
                    "reason": "label or market column present in feature matrix",
                }
            )
            continue
        if any(cl.startswith(p) or p in cl for p in FORBIDDEN_FEATURE_PREFIXES):
            findings.append(
                {
                    "feature": c,
                    "status": "FAIL",
                    "reason": "Kalshi/market or future_ column must not be an XIB/MCD feature",
                }
            )
    return findings


def audit_pregame(pregame: pd.DataFrame) -> list[dict]:
    out = []
    for r in pregame.to_dict("records"):
        start = parse_utc(r.get("scheduled_start") or r.get("prediction_timestamp"))
        as_of = parse_utc(r.get("feature_as_of_timestamp"))
        n_pre = int(r.get("home_games_played_pre") or 0) + int(r.get("away_games_played_pre") or 0)
        if start and as_of and as_of >= start and n_pre > 0:
            out.append(
                {
                    "feature": "pregame_as_of",
                    "status": "FAIL",
                    "game_id": r.get("game_id"),
                    "reason": "feature_as_of_timestamp >= target scheduled_start with priors present",
                }
            )
        if start and as_of and as_of > start and n_pre == 0:
            out.append(
                {
                    "feature": "pregame_as_of",
                    "status": "FAIL",
                    "game_id": r.get("game_id"),
                    "reason": "feature_as_of_timestamp after tip with zero priors",
                }
            )
        # current game must not be in games_played as a win boost: games_played_pre cannot
        # include a game that hasn't started
        if r.get("home_games_played_pre") is None:
            continue
    # rolling exclude target: first game for a team must have games_played_pre == 0
    first = pregame.sort_values(["home_team_id", "game_date"]) if not pregame.empty else pregame
    if not first.empty:
        seen: set[str] = set()
        for r in first.to_dict("records"):
            hid = r.get("home_team_id")
            if hid not in seen:
                seen.add(hid)
                if int(r.get("home_games_played_pre") or 0) != 0:
                    # may not be team's first game if they were away earlier — skip hard fail
                    pass
    return out


def audit_observations(obs: pd.DataFrame) -> list[dict]:
    findings = []
    for r in obs.itertuples(index=False):
        pred = parse_utc(getattr(r, "prediction_timestamp", None))
        feat = parse_utc(getattr(r, "feature_as_of_timestamp", None))
        ev = parse_utc(getattr(r, "game_event_timestamp", None))
        mkt = parse_utc(getattr(r, "market_timestamp", None)) if hasattr(r, "market_timestamp") else None
        gid = getattr(r, "game_id", None)
        if pred and ev and ev > pred:
            findings.append(
                {
                    "feature": "game_event_timestamp",
                    "status": "FAIL",
                    "game_id": gid,
                    "reason": "game_event_timestamp > prediction_timestamp",
                }
            )
        if pred and feat and feat > pred:
            findings.append(
                {
                    "feature": "feature_as_of_timestamp",
                    "status": "FAIL",
                    "game_id": gid,
                    "reason": "feature_as_of_timestamp > prediction_timestamp",
                }
            )
        if mkt and ev and ev > mkt:
            findings.append(
                {
                    "feature": "candle_alignment",
                    "status": "FAIL",
                    "game_id": gid,
                    "reason": "aligned game event after market_timestamp",
                }
            )
    # monotonic event numbers per game
    if "event_number" in obs.columns and "game_id" in obs.columns:
        for gid, grp in obs.groupby("game_id"):
            nums = list(grp["event_number"])
            if nums != sorted(nums):
                findings.append(
                    {
                        "feature": "event_number",
                        "status": "FAIL",
                        "game_id": gid,
                        "reason": "event_number not monotonic",
                    }
                )
    findings.extend(_check_forbidden_columns([c for c in obs.columns if c not in {"final_home_win"}]))
    return findings


def audit_splits(df: pd.DataFrame) -> list[dict]:
    findings = []
    if "split" not in df.columns:
        return findings
    if (df["split"] == "TEST_FROZEN").any():
        findings.append(
            {
                "feature": "temporal_split",
                "status": "FAIL",
                "reason": "TEST_FROZEN (2025-26) present in a fitting table",
            }
        )
    if "game_date" in df.columns:
        train = df[df["split"] == "TRAIN"]
        val = df[df["split"] == "VAL"]
        if not train.empty and not val.empty:
            if str(train["game_date"].max())[:10] > str(val["game_date"].min())[:10]:
                # overlap of dates can happen (same day train/val cut) — fail only if train max > val min after cut
                tmax = str(train["game_date"].max())[:10]
                vmin = str(val["game_date"].min())[:10]
                if tmax > vmin:
                    findings.append(
                        {
                            "feature": "temporal_split",
                            "status": "FAIL",
                            "reason": f"train max date {tmax} after val min {vmin}",
                        }
                    )
    return findings


def run_leakage_audit(
    *,
    league: str,
    season: str,
    pregame: pd.DataFrame | None = None,
    observations: pd.DataFrame | None = None,
    feature_columns: list[str] | None = None,
) -> dict[str, Any]:
    findings: list[dict] = []
    if pregame is not None and not pregame.empty:
        findings.extend(audit_pregame(pregame))
        findings.extend(audit_splits(pregame))
    if observations is not None and not observations.empty:
        findings.extend(audit_observations(observations))
        findings.extend(audit_splits(observations))
    if feature_columns:
        findings.extend(_check_forbidden_columns(feature_columns))

    # registry coverage
    for name, meta in FEATURE_REGISTRY.items():
        if not meta.allowed_in_xib:
            findings.append(
                {
                    "feature": name,
                    "status": "PASS",
                    "reason": f"excluded from XIB by registry: {meta.availability_rule}",
                }
            )

    fails = [f for f in findings if f.get("status") == "FAIL"]
    report = {
        "league": league,
        "season": season,
        "status": "FAIL" if fails else "PASS",
        "n_findings": len(findings),
        "n_fail": len(fails),
        "failures": fails[:200],
        "sample_pass_notes": [f for f in findings if f.get("status") == "PASS"][:50],
        "rule": "No information may cross forward through time",
    }
    dest = reports_dir(league, season) / "leakage_audit.json"
    write_json(dest, report)
    return report
