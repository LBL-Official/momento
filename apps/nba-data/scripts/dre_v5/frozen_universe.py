"""Gate A — reproduce frozen FIRST-80. Do not redefine it."""

from __future__ import annotations

import importlib.util
import json
import sys

from . import config as C


def load_v1():
    path = C.NCAAB_SCRIPTS / "first80_realistic_exit_fee_audit_v1.py"
    if str(C.NBA_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(C.NBA_SCRIPTS))
    spec = importlib.util.spec_from_file_location("first80_exit_fee_v1_for_dre_v5", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["first80_exit_fee_v1_for_dre_v5"] = mod
    spec.loader.exec_module(mod)
    return mod


def load_pade_common():
    path = C.NBA_SCRIPTS / "pade_v1" / "common.py"
    spec = importlib.util.spec_from_file_location("pade_common_for_dre_v5", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pade_common_for_dre_v5"] = mod
    spec.loader.exec_module(mod)
    return mod


def enrich_trades(trades: list[dict]) -> list[dict]:
    v1a = load_v1()
    pade_c = load_pade_common()
    games = v1a.V1.load_games(v1a.V1.SPORTS["nba"])
    crosswalk = pade_c.load_crosswalk()
    out = []
    for rec in trades:
        t = dict(rec)
        v1a.attach_scan_window(t, games.get(t["event_id"]))
        cw = crosswalk.get(t["event_id"]) or {}
        t["nba_game_id"] = cw.get("nba_game_id")
        t["match_status"] = cw.get("match_status")
        t["a1_team"] = pade_c.team_code_from_ticker(t.get("ticker"))
        t["opponent_ticker"] = v1a.V1.opponent_of(games.get(t["event_id"]) or {}, t["ticker"])
        t["a2_team"] = pade_c.team_code_from_ticker(t.get("opponent_ticker"))
        out.append(t)
    return out


def gate_a() -> dict:
    v1a = load_v1()
    trades = v1a.load_frozen("nba")
    repro = v1a.reproduce_path("nba", trades)
    ok = bool(repro.get("ok"))
    enriched = enrich_trades(trades)
    return {
        "gate": "A",
        "status": "PASS" if ok else "FAIL",
        "ok": ok,
        "observed": repro.get("observed"),
        "expected": C.GATES_F80,
        "n_trades": len(enriched),
        "label": "CANDLE PATH — NOT ACTUAL FILL",
        "trades": enriched,
        "v1": v1a,
    }


def unresolved() -> dict:
    return json.loads((C.V2_OUT / "14_diagnostics" / "unresolved.json").read_text())
