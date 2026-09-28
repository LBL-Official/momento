"""GATE A — reproduce the frozen FIRST-80 universe. Do not redefine it."""

from __future__ import annotations

from . import config as C


def load_v1():
    """Import FIRST-80 V1 as a read-only library. Do not edit that file."""
    import importlib.util
    import sys

    path = C.NCAAB_SCRIPTS / "first80_realistic_exit_fee_audit_v1.py"
    if str(C.NBA_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(C.NBA_SCRIPTS))
    spec = importlib.util.spec_from_file_location("first80_exit_fee_v1_for_dre_v2", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["first80_exit_fee_v1_for_dre_v2"] = mod
    spec.loader.exec_module(mod)
    return mod


def gate_a() -> dict:
    v1a = load_v1()
    trades = v1a.load_frozen("nba")
    repro = v1a.reproduce_path("nba", trades)
    obs = repro.get("observed") or {}
    expected = C.GATES_F80
    ok = bool(repro.get("ok"))
    status = "PASS" if ok else "FAIL"
    return {
        "gate": "A",
        "status": status,
        "ok": ok,
        "observed": obs,
        "expected": expected,
        "n_trades": len(trades),
        "label": "CANDLE PATH — NOT ACTUAL FILL",
        "loader": "apps/ncaab-data/scripts/first80_realistic_exit_fee_audit_v1.py",
        "candidates": str(
            C.WAREHOUSE / "derived" / "nba" / "first80_execution_audit" / "candidates.json"
        ),
        "trades": trades,
        "reproduce": repro,
    }
