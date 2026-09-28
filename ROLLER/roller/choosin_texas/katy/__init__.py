"""Katy Texas: labeled research experiments. Not a fill. Not a live desk."""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.katy.catalog import build_catalog, handle_catalog, handle_experiment
from roller.choosin_texas.katy.common import classify
from roller.choosin_texas.katy.v1 import (
    EV_HEDGE_LT,
    EXPERIMENT_ID as KATY_ID,
    PRICE_HI,
    PRICE_LO,
    build_v1,
    experiment_dir as katy_dir,
    handle_v1,
)

__all__ = [
    "EV_HEDGE_LT",
    "KATY_ID",
    "PRICE_HI",
    "PRICE_LO",
    "_classify",
    "build_katy",
    "build_katy_catalog",
    "handle_katy",
    "handle_katy_experiment",
    "katy_dir",
]


def _classify(price, ev):
    return classify(price, ev, lo=PRICE_LO, hi=PRICE_HI, ev_lt=EV_HEDGE_LT)


def build_katy() -> dict[str, Any]:
    return build_v1()


def build_katy_catalog() -> dict[str, Any]:
    return build_catalog()


def handle_katy() -> dict[str, Any]:
    return handle_catalog()


def handle_katy_experiment(key: str) -> dict[str, Any]:
    return handle_experiment(key)
