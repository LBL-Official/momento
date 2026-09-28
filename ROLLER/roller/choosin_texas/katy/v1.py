"""Katy experiment 1: late-clock underwater 41–70 / Austin EV < 5."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B
from roller.austin.store import load_json, write_json
from roller.choosin_texas.houston import HOUSTON_ID, houston_identity
from roller.choosin_texas.katy.common import (
    apply_rule,
    assert_confirmation_sealed,
    components,
    katy_root,
    measure_ncaab,
    measure_nba_in_band,
    summarize_rule,
)
from roller.choosin_texas.sources import repo_root

EXPERIMENT_ID = "KATY_TEXAS_V1"
SLUG = "late-underwater-41-70-ev5"
TITLE = "Late underwater 41–70 / EV < 5"
NUMBER = 1
PRICE_LO = 41
PRICE_HI = 70
EV_HEDGE_LT = 5
NBA_MARK_REMAINING = 540
NCAAB_MARK_REMAINING = 450


def experiment_dir():
    return repo_root() / "research" / "choosin_texas" / "library" / "katy_texas_v1"


def catalog_dir():
    return katy_root() / SLUG


def card(*, books: dict[str, Any] | None = None) -> dict[str, Any]:
    a = None if not books else books.get("ncaab_h1_2_discovery") or {}
    b = None if not books else books.get("ncaab_h2_1_discovery") or {}
    nba = None if not books else books.get("nba_604_in_sample") or {}
    return {
        "number": NUMBER,
        "experiment_id": EXPERIMENT_ID,
        "slug": SLUG,
        "href": f"#/katy/{SLUG}",
        "title": TITLE,
        "question": "If FIRST80 is already on and yes_bid is 41–70 at 4Q 9:00 / 2H 7:30, does Austin EV < 5 plus a Houston taker lock cut loser damage?",
        "marks": {
            "nba": "4Q 9:00 remaining (540s; off-grid, first remaining ≤ 540)",
            "ncaab": "2H 7:30 remaining (450s; off-grid, first remaining ≤ 450)",
        },
        "rule": f"yes_bid in [{PRICE_LO}, {PRICE_HI}] and Austin EV < {EV_HEDGE_LT}",
        "status": "MEASURED",
        "one_line": None
        if not books
        else (
            "Loser tails improve on A/NBA; net path EV loses to hold on all three books "
            f"(A {a.get('katy_path', {}).get('mean_cents')} vs hold {a.get('always_hold', {}).get('mean_cents')}; "
            f"B {b.get('katy_path', {}).get('mean_cents')} vs {b.get('always_hold', {}).get('mean_cents')}; "
            f"NBA {nba.get('katy_path', {}).get('mean_cents')} vs {nba.get('always_hold', {}).get('mean_cents')})."
        ),
    }


def build_v1() -> dict[str, Any]:
    assert_confirmation_sealed()
    ncaab = measure_ncaab(mark_remaining=NCAAB_MARK_REMAINING)
    nba_m = measure_nba_in_band(mark_remaining=NBA_MARK_REMAINING, lo=PRICE_LO, hi=PRICE_HI)
    a_rows = apply_rule(ncaab[EXPERIMENT_A]["rows"], lo=PRICE_LO, hi=PRICE_HI, ev_lt=EV_HEDGE_LT)
    b_rows = apply_rule(ncaab[EXPERIMENT_B]["rows"], lo=PRICE_LO, hi=PRICE_HI, ev_lt=EV_HEDGE_LT)
    nba_rows = apply_rule(nba_m["rows"], lo=PRICE_LO, hi=PRICE_HI, ev_lt=EV_HEDGE_LT)
    a_sum = summarize_rule(a_rows, book=ncaab[EXPERIMENT_A]["label"])
    b_sum = summarize_rule(b_rows, book=ncaab[EXPERIMENT_B]["label"])
    nba_sum = summarize_rule(nba_rows, book="NBA_604")
    books = {
        "ncaab_h1_2_discovery": a_sum,
        "ncaab_h2_1_discovery": b_sum,
        "nba_604_in_sample": nba_sum,
    }
    payload = {
        "status": "OBSERVED",
        "kind": "experiment",
        "product": "Katy Texas",
        "experiment_id": EXPERIMENT_ID,
        "slug": SLUG,
        "number": NUMBER,
        "title": TITLE,
        "href": f"#/katy/{SLUG}",
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
        "austin_refit": False,
        "components": components(hedge_if="austin_ev_cents < 5 and yes_bid in [41, 70]"),
        "rule": {
            "entry": "FIRST80 already happened. Katy does not skip or create entry.",
            "nba_run_mark": "4Q, 9:00 remaining (540s); first snapshot remaining<=540",
            "ncaab_run_mark": "2H, 7:30 remaining (450s); first snapshot remaining<=450",
            "price_band": [PRICE_LO, PRICE_HI],
            "underwater_min_cents": 10,
            "austin_ev_lt": EV_HEDGE_LT,
            "houston_action": "full other-side taker scenario at declared 100-yes_bid",
            "not_fort_worth": "Fort Worth is maker-40 at 41-42. Katy is a different scenario.",
        },
        "books": books,
        "ncaab_h1_2_discovery": {
            "experiment_id": EXPERIMENT_A,
            "label": ncaab[EXPERIMENT_A]["label"],
            "cohort": "DISCOVERY",
            "confirmation_accessed": False,
            "run_mark": {"period": 2, "remaining_s": NCAAB_MARK_REMAINING, "label": "NCAAB 2H 7:30 remaining"},
            "grid_note": "7:30 is off the 2-minute PRIMARY_GRID. First period=2 remaining<=450 is used; modal clock is 360 (6:00).",
            "summary": a_sum,
        },
        "ncaab_h2_1_discovery": {
            "experiment_id": EXPERIMENT_B,
            "label": ncaab[EXPERIMENT_B]["label"],
            "cohort": "DISCOVERY",
            "confirmation_accessed": False,
            "run_mark": {"period": 2, "remaining_s": NCAAB_MARK_REMAINING, "label": "NCAAB 2H 7:30 remaining"},
            "grid_note": "7:30 is off the 2-minute PRIMARY_GRID. First period=2 remaining<=450 is used; modal clock is 360 (6:00).",
            "summary": b_sum,
        },
        "nba_604_in_sample": {
            "experiment_id": "choosin_nba_2q3q_604",
            "label": nba_m["label"],
            "cohort": "IN_SAMPLE_604",
            "confirmation_accessed": False,
            "dallas_page_remains": "2Q/3Q snapshots only. Katy reads later path on the same 604 trades.",
            "run_mark": {"period": 4, "remaining_s": NBA_MARK_REMAINING, "label": "NBA 4Q 9:00 remaining"},
            "grid_note": "9:00 is off the 2-minute clock grid. First Q4 remaining<=540 is used; typical clock is near 480 (8:00).",
            "summary": nba_sum,
        },
        "row_counts": {
            "ncaab_h1_2": len(a_rows),
            "ncaab_h2_1": len(b_rows),
            "nba_604": len(nba_rows),
        },
        "ledgers": {
            "ncaab_h1_2_discovery": a_rows,
            "ncaab_h2_1_discovery": b_rows,
            "nba_604_in_sample": nba_rows,
        },
        "card": card(books=books),
        "combined_headline_forbidden": True,
        "note": "Katy experiment 1. Houston taker lock is declared, not a fill. Confirmation unspent. Execution disabled.",
    }
    _persist(payload)
    return payload


def _persist(payload: dict[str, Any]) -> None:
    body = {k: payload[k] for k in payload if k != "ledgers"}
    for root in (experiment_dir(), catalog_dir()):
        write_json(root / "MANIFEST.json", body)
        write_json(root / "statistics.json", payload["books"])
        write_json(root / "houston.json", houston_identity())
        write_json(root / "ledgers.json", payload["ledgers"])
        (root / "REPORT.md").write_text(_report_md(payload), encoding="utf-8")


def _report_md(payload: dict[str, Any]) -> str:
    a = payload["books"]["ncaab_h1_2_discovery"]
    b = payload["books"]["ncaab_h2_1_discovery"]
    nba = payload["books"]["nba_604_in_sample"]
    return "\n".join(
        [
            "KATY TEXAS — EXPERIMENT 1",
            TITLE.upper(),
            "",
            "RESEARCH ONLY",
            "CANDLE PATH ≠ FILL",
            "CONFIRMATION UNSPENT",
            "EXECUTION DISABLED",
            "",
            "# 1. WHAT THIS EXPERIMENT IS",
            "",
            "Labeled Katy experiment 1 of many. Not a new Momento system.",
            "Dallas supplies the run-mark clock and yes_bid path.",
            f"Houston ({HOUSTON_ID}) declares a full other-side taker at 100 − yes_bid.",
            "Austin supplies hold-80-to-settlement EV. Hedge only if that EV is observed and < 5¢",
            "and yes_bid is in [41, 70]. Missing EV does not hedge.",
            "",
            "# 2. RUN MARKS",
            "",
            "NBA: 4Q 9:00 remaining. Off-grid. First Q4 remaining ≤ 540.",
            "NCAAB: 2H 7:30 remaining. Off-grid. First period-2 remaining ≤ 450.",
            "H2_2 is not a transfer member. H2_1 trades may be observed later in the same game.",
            "",
            "# 3. NCAAB H1_2 DISCOVERY",
            "",
            f"N={a['n_trades']} reached={a['n_run_mark_reached']} band={a['n_in_price_band']} hedge={a['n_hedge_scenario']} EV-unavailable={a['n_ev_unavailable_in_band']}",
            f"Katy path mean {a['katy_path']['mean_cents']} vs hold {a['always_hold']['mean_cents']} vs 80/40 {a['always_8040']['mean_cents']}",
            "",
            "# 4. NCAAB H2_1 DISCOVERY",
            "",
            f"N={b['n_trades']} reached={b['n_run_mark_reached']} band={b['n_in_price_band']} hedge={b['n_hedge_scenario']} EV-unavailable={b['n_ev_unavailable_in_band']}",
            f"Katy path mean {b['katy_path']['mean_cents']} vs hold {b['always_hold']['mean_cents']} vs 80/40 {b['always_8040']['mean_cents']}",
            "",
            "# 5. NBA 604 IN-SAMPLE 4Q",
            "",
            f"N={nba['n_trades']} reached={nba['n_run_mark_reached']} band={nba['n_in_price_band']} hedge={nba['n_hedge_scenario']} EV-unavailable={nba['n_ev_unavailable_in_band']}",
            f"Katy path mean {nba['katy_path']['mean_cents']} vs hold {nba['always_hold']['mean_cents']} vs 80/40 {nba['always_8040']['mean_cents']}",
            "This book is in-sample. It is not confirmation and not a live 2026-27 result.",
            "",
            "# 6. WHAT THIS DOES NOT PROVE",
            "",
            "No taker fill. No NO ask. No fees. No combined headline. Phase 8 is not justified.",
            "",
        ]
    ) + "\n"


def load_v1() -> dict[str, Any] | None:
    manifest = load_json(experiment_dir() / "MANIFEST.json", required=False)
    if not manifest:
        return None
    ledgers = load_json(experiment_dir() / "ledgers.json", required=False) or {}
    return {**manifest, "ledgers": ledgers}


def handle_v1() -> dict[str, Any]:
    payload = load_v1()
    if payload:
        return payload
    return build_v1()
