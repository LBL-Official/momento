"""Recover TRAIN-frozen M0/M1 from V5 m0_m1. Persist. Score only from disk after persist."""

from __future__ import annotations

import json
import math

import pandas as pd

from . import config as C


def _isna(x) -> bool:
    if x is None:
        return True
    try:
        return bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def price_key(p) -> str:
    if _isna(p):
        return "NA"
    return f"{float(p):.1f}"


def cat_key(x) -> str:
    if _isna(x):
        return "NA"
    return str(x)


def m1_key(price, score, clock, nhat) -> str:
    return "|".join((price_key(price), cat_key(score), cat_key(clock), cat_key(nhat)))


def serialize_lookup(lookup: dict) -> dict:
    m0 = {}
    for k, v in (lookup.get("m0") or {}).items():
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            continue
        m0[price_key(k)] = float(v)
    m1 = {}
    for k, v in (lookup.get("m1") or {}).items():
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            continue
        if isinstance(k, (tuple, list)) and len(k) == 4:
            m1[m1_key(*k)] = float(v)
        else:
            raise RuntimeError(f"HALT: unexpected M1 key shape {k!r}. Do not invent a key encoding.")
    g = lookup.get("global_mean")
    if g is None:
        raise RuntimeError("HALT: TRAIN global_mean missing from V5 lookup.")
    if len(m0) != C.V5_PUBLISHED["n_m0_cells"] or len(m1) != C.V5_PUBLISHED["n_m1_cells"]:
        raise RuntimeError(
            f"HALT: serialized map cells {len(m0)}/{len(m1)} != "
            f"{C.V5_PUBLISHED['n_m0_cells']}/{C.V5_PUBLISHED['n_m1_cells']}. "
            "Do not invent a key encoding."
        )
    return {"m0": m0, "m1": m1, "global_mean": float(g)}


def predict_m0(price_bin, maps: dict) -> float:
    v = maps["m0"].get(price_key(price_bin))
    return maps["global_mean"] if v is None else float(v)


def predict_m1(price_bin, score, clock, nhat, maps: dict) -> float:
    v = maps["m1"].get(m1_key(price_bin, score, clock, nhat))
    if v is None:
        return predict_m0(price_bin, maps)
    return float(v)


def identity_check(m01: dict) -> dict:
    oos = (m01.get("by_split") or {}).get("OOS") or {}
    checks = {
        "mae_m0_oos": C.close(oos.get("mae_m0_trade_balanced"), C.V5_PUBLISHED["mae_m0_oos"]),
        "mae_m1_oos": C.close(oos.get("mae_m1_trade_balanced"), C.V5_PUBLISHED["mae_m1_oos"]),
        "delta_mae_oos": C.close(oos.get("delta_mae_m0_minus_m1"), C.V5_PUBLISHED["delta_mae_oos"]),
        "n_m0_cells": int(m01.get("n_m0_cells") or -1) == C.V5_PUBLISHED["n_m0_cells"],
        "n_m1_cells": int(m01.get("n_m1_cells") or -1) == C.V5_PUBLISHED["n_m1_cells"],
    }
    return {
        "gate": "C",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "observed": {
            "mae_m0_oos": oos.get("mae_m0_trade_balanced"),
            "mae_m1_oos": oos.get("mae_m1_trade_balanced"),
            "delta_mae_oos": oos.get("delta_mae_m0_minus_m1"),
            "n_m0_cells": m01.get("n_m0_cells"),
            "n_m1_cells": m01.get("n_m1_cells"),
        },
        "expected": C.V5_PUBLISHED,
        "note": "Map recovery identity. Not a V6 scientific table.",
    }


def persist(maps: dict, identity: dict, train_only: bool) -> dict:
    payload = {
        "program": C.PROGRAM,
        "source": "dre_v5.surfaces.m0_m1 TRAIN lookup",
        "train_only": train_only,
        "n_m0": len(maps["m0"]),
        "n_m1": len(maps["m1"]),
        "global_mean": maps["global_mean"],
        "fallback": "missing M1 -> M0(price) -> TRAIN global trade-mean",
        "identity": identity,
        "m0": maps["m0"],
        "m1": maps["m1"],
        "written_utc": C.utc_now(),
        "note": "Persisted before VAL/OOS SIR tables. Subsequent scoring uses this file only.",
    }
    C.write_json(C.OUT / "02_train_frozen_m0_m1.json", payload)
    return payload


def load_persisted() -> dict:
    path = C.OUT / "02_train_frozen_m0_m1.json"
    if not path.exists():
        raise RuntimeError("HALT: persisted TRAIN M0/M1 maps missing. Do not rescore from memory.")
    obj = json.loads(path.read_text())
    return {"m0": obj["m0"], "m1": obj["m1"], "global_mean": float(obj["global_mean"])}
