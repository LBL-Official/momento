"""Katy Texas experiment catalog. Homepage payload."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.store import load_json, write_json
from roller.choosin_texas.katy.common import assert_confirmation_sealed, components, katy_root
from roller.choosin_texas.katy import v1, v2, v3, v4, v5

EXPERIMENTS = (
    {"id": v1.EXPERIMENT_ID, "slug": v1.SLUG, "aliases": ("1", "v1", "KATY_TEXAS_V1", "late-underwater-41-70-ev5")},
    {"id": v2.EXPERIMENT_ID, "slug": v2.SLUG, "aliases": ("2", "v2", "KATY_V2_Q4_OPEN_8040_SEARCH", "q4-open-8040-search")},
    {"id": v3.EXPERIMENT_ID, "slug": v3.SLUG, "aliases": ("3", "v3", "KATY_V3_2H_LAST10_FOUR_UNIVERSE", "2h-last-10-price-search")},
    {"id": v4.EXPERIMENT_ID, "slug": v4.SLUG, "aliases": ("4", "v4", "KATY_V4_LAST10_CLOCK_TRAIL", "last10-clock-trail-55-45")},
    {"id": v5.EXPERIMENT_ID, "slug": v5.SLUG, "aliases": ("5", "v5", "KATY_V5_LAST10_AUSTIN_FOUR_BOOK", "last10-austin-four-book")},
)


def resolve(key: str) -> str:
    raw = str(key or "").strip().strip("/")
    for item in EXPERIMENTS:
        if raw in {item["id"], item["slug"], *item["aliases"]}:
            return item["slug"]
    raise AustinError("DATA_REQUIRED", f"unknown Katy experiment: {key}")


def _ensure_v1() -> dict[str, Any]:
    return v1.load_v1() or v1.build_v1()


def _ensure_v2() -> dict[str, Any]:
    return v2.load_v2() or v2.build_v2()


def _ensure_v3() -> dict[str, Any]:
    return v3.load_v3() or v3.build_v3()


def _ensure_v4() -> dict[str, Any]:
    return v4.load_v4() or v4.build_v4()


def _ensure_v5() -> dict[str, Any]:
    return v5.load_v5() or v5.build_v5()


def build_catalog() -> dict[str, Any]:
    assert_confirmation_sealed()
    first = _ensure_v1()
    second = _ensure_v2()
    third = _ensure_v3()
    fourth = _ensure_v4()
    fifth = _ensure_v5()
    cards = [
        first.get("card") or v1.card(books=first.get("books")),
        second.get("card") or v2.card(selected=second.get("selected")),
        third.get("card") or v3.card(selected=third.get("selected")),
        fourth.get("card") or v4.card(books=fourth.get("books")),
        fifth.get("card") or v5.card(selected=fifth.get("selected")),
    ]
    payload = {
        "status": "OBSERVED",
        "kind": "catalog",
        "product": "Katy Texas",
        "title": "Katy experiments",
        "live_execution": False,
        "submits": False,
        "fill_status": "FILL_UNAVAILABLE",
        "candle_path_not_fill": True,
        "policy_frozen": False,
        "confirmation_accessed": False,
        "confirmation_A": "SEALED_UNSPENT",
        "confirmation_B": "SEALED_UNSPENT",
        "phase5_policy": "NONE",
        "austin_never_filters_entry": True,
        "components": components(hedge_if="per experiment"),
        "experiments": cards,
        "combined_headline_forbidden": True,
        "note": (
            "Katy is a labeled research-experiment index. Each card is its own page. "
            "Houston lock is declared, not a fill. Experiments 1, 2, and 5 query frozen Austin. "
            "Experiments 3 and 4 do not. Confirmation unspent."
        ),
    }
    write_json(katy_root() / "CATALOG.json", payload)
    return payload


def load_catalog() -> dict[str, Any] | None:
    return load_json(katy_root() / "CATALOG.json", required=False)


def handle_catalog() -> dict[str, Any]:
    payload = load_catalog()
    slugs = [row.get("slug") for row in (payload or {}).get("experiments") or []]
    if payload and v4.SLUG in slugs and v5.SLUG in slugs:
        return payload
    return build_catalog()


def handle_experiment(key: str) -> dict[str, Any]:
    slug = resolve(key)
    if slug == v1.SLUG:
        return v1.handle_v1()
    if slug == v2.SLUG:
        return v2.handle_v2()
    if slug == v3.SLUG:
        return v3.handle_v3()
    if slug == v4.SLUG:
        return v4.handle_v4()
    if slug == v5.SLUG:
        return v5.handle_v5()
    raise AustinError("DATA_REQUIRED", f"unknown Katy experiment: {key}")
