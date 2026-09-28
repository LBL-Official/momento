"""Gate A — reproduce frozen FIRST-80. Do not redefine it."""

from __future__ import annotations

import importlib.util
import sys

from . import config as C


def load_v1():
    path = C.NCAAB_SCRIPTS / "first80_realistic_exit_fee_audit_v1.py"
    if str(C.NBA_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(C.NBA_SCRIPTS))
    spec = importlib.util.spec_from_file_location("first80_exit_fee_v1_for_dre_v4", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["first80_exit_fee_v1_for_dre_v4"] = mod
    spec.loader.exec_module(mod)
    return mod


def gate_a() -> dict:
    v1a = load_v1()
    trades = v1a.load_frozen("nba")
    repro = v1a.reproduce_path("nba", trades)
    ok = bool(repro.get("ok"))
    return {
        "gate": "A",
        "status": "PASS" if ok else "FAIL",
        "ok": ok,
        "observed": repro.get("observed"),
        "expected": C.GATES_F80,
        "n_trades": len(trades),
        "label": "CANDLE PATH — NOT ACTUAL FILL",
        "trades": trades,
    }
