"""Frozen interval helpers. Does not choose a headline."""

from __future__ import annotations

from . import config as C


def sign(x) -> int | None:
    if x is None:
        return None
    v = float(x)
    if v == 0.0:
        return 0
    return 1 if v > 0 else -1


def zero_compatible(interval: dict | None) -> bool | None:
    if not interval or interval.get("p05") is None or interval.get("p95") is None:
        return None
    return float(interval["p05"]) <= 0.0 <= float(interval["p95"])


def train_direction_compatible(train_effect, interval: dict | None) -> bool | None:
    if train_effect is None or not interval:
        return None
    if interval.get("p05") is None or interval.get("p95") is None:
        return None
    t = float(train_effect)
    p05 = float(interval["p05"])
    p95 = float(interval["p95"])
    if t > 0 and p95 < 0:
        return False
    if t < 0 and p05 > 0:
        return False
    return True


def directional(train_effect, oos_effect) -> bool | None:
    st = sign(train_effect)
    so = sign(oos_effect)
    if st is None or so is None or st == 0:
        return None
    return st == so


def val_confirmed(train_effect, val_effect, val_adequate: bool) -> bool:
    if not val_adequate:
        return True
    st = sign(train_effect)
    sv = sign(val_effect)
    if st is None or sv is None or st == 0:
        return False
    return st == sv


def coverage_adequate(n_a: int, n_b: int) -> bool:
    return int(n_a) >= C.MIN_SIDE_TRADES and int(n_b) >= C.MIN_SIDE_TRADES


def replication_directional(
    train_effect,
    val_effect,
    oos_effect,
    bootstrap_interval: dict | None,
    coverage: dict,
) -> dict:
    """Measurement of the frozen conjunction. Does not classify A/B/C/D."""
    adequate_train_oos = bool(coverage.get("adequate_train_oos"))
    val_adequate = bool(coverage.get("adequate_val"))
    d = directional(train_effect, oos_effect)
    tdc = train_direction_compatible(train_effect, bootstrap_interval)
    vc = val_confirmed(train_effect, val_effect, val_adequate)
    if d is None or not adequate_train_oos:
        token = "INCONCLUSIVE"
        ok = False
    elif d is False:
        token = "FAIL"
        ok = False
    else:
        ok = bool(d) and bool(tdc) and bool(vc) and adequate_train_oos
        token = "TRUE" if ok else "FALSE"
    return {
        "ok": ok,
        "token": token,
        "DIRECTIONAL": d,
        "TRAIN_DIRECTION_COMPATIBLE": tdc,
        "VAL_CONFIRMATION_REQUIRED": val_adequate,
        "VAL_CONFIRMED": vc,
        "adequate_train_oos": adequate_train_oos,
        "ZERO_COMPATIBLE": zero_compatible(bootstrap_interval),
        "train_effect": train_effect,
        "val_effect": val_effect,
        "oos_effect": oos_effect,
        "bootstrap": bootstrap_interval,
        "weighting": C.SURFACE_WEIGHTING_PRIMARY,
    }
