"""Katy experiment 2: Q4 12:00 / 2H 10:00 Austin range × EV search vs 80/40."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B
from roller.austin.store import load_json, write_json
from roller.choosin_texas.houston import houston_identity
from roller.choosin_texas.katy.common import (
    apply_rule,
    assert_confirmation_sealed,
    components,
    katy_root,
    measure_ncaab,
    measure_nba,
    score_cell,
    select_cell,
    summarize_rule,
)

EXPERIMENT_ID = "KATY_V2_Q4_OPEN_8040_SEARCH"
SLUG = "q4-open-8040-search"
TITLE = "Q4 12:00 / 2H 10:00 — range × Austin EV vs 80/40"
NUMBER = 2
PRICE_LO = 41
PRICE_HI_GRID = (50, 55, 60, 65, 70, 75, 79)
EV_LT_GRID = (-20, -10, 0, 5, 10, 15, 20)
NBA_MARK_REMAINING = 720
NCAAB_MARK_REMAINING = 600


def experiment_dir():
    return katy_root() / SLUG


def card(*, selected: dict[str, Any] | None = None, books: dict[str, Any] | None = None) -> dict[str, Any]:
    lines = []
    if selected:
        for key, label in (
            ("ncaab_h1_2_discovery", "A"),
            ("ncaab_h2_1_discovery", "B"),
            ("nba_604_in_sample", "NBA"),
        ):
            cell = selected.get(key) or {}
            if cell.get("status") == "SELECTED":
                lines.append(
                    f"{label} {cell['price_lo']}–{cell['price_hi']} / EV<{cell['austin_ev_lt']} Δ{cell['delta_mean_cents']}¢"
                )
            else:
                lines.append(f"{label} NONE")
    return {
        "number": NUMBER,
        "experiment_id": EXPERIMENT_ID,
        "slug": SLUG,
        "href": f"#/katy/{SLUG}",
        "title": TITLE,
        "question": "At NBA Q4 12:00 / NCAAB 2H 10:00, what yes_bid range and Austin EV cutoff would let a Houston lock beat always-80/40 by cutting losers?",
        "marks": {
            "nba": "4Q 12:00 remaining (720s; on-grid)",
            "ncaab": "2H 10:00 remaining (600s; on-grid)",
        },
        "rule": "Preregistered grid. PRICE_LO=41. PRICE_HI ∈ {50,55,60,65,70,75,79}. Austin EV < {-20,-10,0,5,10,15,20}. Maximize mixed 80/40 − always 80/40. Ties → fewer hedges, then tighter band.",
        "status": "MEASURED" if selected else "DECLARED",
        "one_line": None if not lines else "; ".join(lines) + ". Search ≠ freeze. Books never combined.",
    }


def _grid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cells = []
    for hi in PRICE_HI_GRID:
        for ev_lt in EV_LT_GRID:
            cells.append(score_cell(rows, lo=PRICE_LO, hi=hi, ev_lt=float(ev_lt)))
    return cells


def _book_search(measured: dict[str, Any], *, book_key: str) -> dict[str, Any]:
    rows = measured["rows"]
    cells = _grid(rows)
    selected = select_cell(cells)
    if selected.get("status") == "SELECTED":
        applied = apply_rule(
            rows,
            lo=int(selected["price_lo"]),
            hi=int(selected["price_hi"]),
            ev_lt=float(selected["austin_ev_lt"]),
            block_if_already_stopped=True,
        )
    else:
        applied = apply_rule(rows, lo=PRICE_LO, hi=PRICE_LO - 1, ev_lt=0.0, block_if_already_stopped=True)
    top = sorted(cells, key=lambda c: (-int(c["delta_sum_cents"]), int(c["n_hedge"]), int(c["price_hi"]), float(c["austin_ev_lt"])))[:5]
    return {
        "book_key": book_key,
        "experiment_id": measured.get("experiment_id"),
        "label": measured.get("label"),
        "loser_exam": measured["loser_exam"],
        "selected": selected,
        "top_cells": top,
        "n_cells": len(cells),
        "rows": applied,
        "summary": summarize_rule(applied, book=measured.get("label") or book_key),
        "cells": cells,
    }


def build_v2() -> dict[str, Any]:
    assert_confirmation_sealed()
    ncaab = measure_ncaab(mark_remaining=NCAAB_MARK_REMAINING)
    nba_m = measure_nba(mark_remaining=NBA_MARK_REMAINING, ev_when="open")
    a = _book_search(ncaab[EXPERIMENT_A], book_key="ncaab_h1_2_discovery")
    b = _book_search(ncaab[EXPERIMENT_B], book_key="ncaab_h2_1_discovery")
    nba = _book_search(nba_m, book_key="nba_604_in_sample")
    selected = {
        "ncaab_h1_2_discovery": a["selected"],
        "ncaab_h2_1_discovery": b["selected"],
        "nba_604_in_sample": nba["selected"],
    }
    books = {
        "ncaab_h1_2_discovery": a["summary"],
        "ncaab_h2_1_discovery": b["summary"],
        "nba_604_in_sample": nba["summary"],
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
        "optimize": "threshold_and_range_search",
        "not_a_retrain": True,
        "components": components(hedge_if="selected per-book cell from the preregistered grid, else NONE"),
        "question": (
            "At the Q4 12:00 / 2H 10:00 on-grid mark, examine what eventual 80/40 losers look like, "
            "then search which yes_bid range and Austin EV cutoff would make mixed 80/40 beat always-80/40."
        ),
        "marks": {
            "nba": {"period": 4, "remaining_s": NBA_MARK_REMAINING, "label": "NBA 4Q 12:00 remaining", "on_grid": True},
            "ncaab": {"period": 2, "remaining_s": NCAAB_MARK_REMAINING, "label": "NCAAB 2H 10:00 remaining", "on_grid": True},
        },
        "grid_declared": {
            "price_lo": PRICE_LO,
            "price_hi": list(PRICE_HI_GRID),
            "austin_ev_lt": list(EV_LT_GRID),
            "objective": "per-book maximize mixed_8040 − always_8040 (sum of cents)",
            "tie_break": "fewer hedges, then tighter price_hi, then lower EV cutoff",
            "fail_closed": "missing Austin EV → no hedge; t40_already or yes_bid < 41 → already stopped, not a hedge candidate",
            "declared_before_selection": True,
        },
        "loser_exam": {
            "ncaab_h1_2_discovery": a["loser_exam"],
            "ncaab_h2_1_discovery": b["loser_exam"],
            "nba_604_in_sample": nba["loser_exam"],
        },
        "selected": selected,
        "top_cells": {
            "ncaab_h1_2_discovery": a["top_cells"],
            "ncaab_h2_1_discovery": b["top_cells"],
            "nba_604_in_sample": nba["top_cells"],
        },
        "grid": {
            "ncaab_h1_2_discovery": a["cells"],
            "ncaab_h2_1_discovery": b["cells"],
            "nba_604_in_sample": nba["cells"],
        },
        "books": books,
        "ncaab_h1_2_discovery": {
            "experiment_id": EXPERIMENT_A,
            "label": a["label"],
            "cohort": "DISCOVERY",
            "confirmation_accessed": False,
            "run_mark": {"period": 2, "remaining_s": NCAAB_MARK_REMAINING, "label": "NCAAB 2H 10:00 remaining"},
            "selected": a["selected"],
            "summary": a["summary"],
        },
        "ncaab_h2_1_discovery": {
            "experiment_id": EXPERIMENT_B,
            "label": b["label"],
            "cohort": "DISCOVERY",
            "confirmation_accessed": False,
            "run_mark": {"period": 2, "remaining_s": NCAAB_MARK_REMAINING, "label": "NCAAB 2H 10:00 remaining"},
            "selected": b["selected"],
            "summary": b["summary"],
        },
        "nba_604_in_sample": {
            "experiment_id": "choosin_nba_2q3q_604",
            "label": nba["label"],
            "cohort": "IN_SAMPLE_604",
            "confirmation_accessed": False,
            "dallas_page_remains": "2Q/3Q snapshots only. Katy reads later path on the same 604 trades.",
            "run_mark": {"period": 4, "remaining_s": NBA_MARK_REMAINING, "label": "NBA 4Q 12:00 remaining"},
            "selected": nba["selected"],
            "summary": nba["summary"],
        },
        "row_counts": {
            "ncaab_h1_2": len(a["rows"]),
            "ncaab_h2_1": len(b["rows"]),
            "nba_604": len(nba["rows"]),
        },
        "ledgers": {
            "ncaab_h1_2_discovery": a["rows"],
            "ncaab_h2_1_discovery": b["rows"],
            "nba_604_in_sample": nba["rows"],
        },
        "card": card(selected=selected, books=books),
        "combined_headline_forbidden": True,
        "search_is_not_a_freeze": True,
        "note": (
            "Katy experiment 2. Austin is queried, not refit. Selected cells are in-sample search results, "
            "not a frozen DRE policy. Houston lock is declared, not a fill. Confirmation unspent."
        ),
    }
    _persist(payload)
    return payload


def _persist(payload: dict[str, Any]) -> None:
    root = experiment_dir()
    body = {k: payload[k] for k in payload if k not in {"ledgers", "grid"}}
    write_json(root / "MANIFEST.json", body)
    write_json(root / "statistics.json", payload["books"])
    write_json(root / "houston.json", houston_identity())
    write_json(root / "selected.json", payload["selected"])
    write_json(root / "loser_exam.json", payload["loser_exam"])
    write_json(root / "grid.json", payload["grid"])
    write_json(root / "ledgers.json", payload["ledgers"])
    (root / "REPORT.md").write_text(_report_md(payload), encoding="utf-8")


def _fmt_cell(cell: dict[str, Any] | None) -> str:
    if not cell:
        return "NONE"
    if cell.get("status") == "NONE":
        best = cell.get("best_nonpositive") or {}
        return f"NONE (best Δsum={best.get('delta_sum_cents')} at {best.get('price_lo')}–{best.get('price_hi')} EV<{best.get('austin_ev_lt')})"
    return (
        f"{cell.get('price_lo')}–{cell.get('price_hi')} / EV<{cell.get('austin_ev_lt')} "
        f"hedge={cell.get('n_hedge')} (L{cell.get('n_hedge_losers')}/W{cell.get('n_hedge_winners')}) "
        f"Δmean={cell.get('delta_mean_cents')} Δsum={cell.get('delta_sum_cents')}"
    )


def _fmt_exam(exam: dict[str, Any]) -> list[str]:
    losers = exam.get("losers") or {}
    winners = exam.get("winners") or {}
    return [
        f"reached={exam.get('n_reached')} losers={losers.get('n')} winners={winners.get('n')}",
        (
            f"losers open≥41={losers.get('n_open_ge_41')} already<41={losers.get('n_already_lt_41')} "
            f"t40_already={losers.get('n_t40_already_at_mark')} terminal t40={losers.get('n_t40_terminal')}"
        ),
        f"loser price mean/median {losers.get('price', {}).get('mean')}/{losers.get('price', {}).get('median')} buckets={losers.get('price_buckets')}",
        f"winner price mean/median {winners.get('price', {}).get('mean')}/{winners.get('price', {}).get('median')} buckets={winners.get('price_buckets')}",
        f"loser Austin EV n/mean {losers.get('ev', {}).get('n')}/{losers.get('ev', {}).get('mean')} unavailable={losers.get('n_ev_unavailable')}",
        f"winner Austin EV n/mean {winners.get('ev', {}).get('n')}/{winners.get('ev', {}).get('mean')} unavailable={winners.get('n_ev_unavailable')}",
    ]


def _report_md(payload: dict[str, Any]) -> str:
    a = payload["books"]["ncaab_h1_2_discovery"]
    b = payload["books"]["ncaab_h2_1_discovery"]
    nba = payload["books"]["nba_604_in_sample"]
    lines = [
        "KATY TEXAS — EXPERIMENT 2",
        TITLE.upper(),
        "",
        "RESEARCH ONLY",
        "CANDLE PATH ≠ FILL",
        "CONFIRMATION UNSPENT",
        "AUSTIN NOT REFIT",
        "SEARCH ≠ FREEZE",
        "EXECUTION DISABLED",
        "",
        "# 1. QUESTION",
        "",
        payload["question"],
        "",
        "Grid declared before selection. Objective is mixed 80/40 versus always 80/40.",
        "Houston lock is yes_bid − 80. Missing Austin EV does not hedge.",
        "yes_bid < 41 or t40_already at the mark is already an 80/40 stop.",
        "",
        "# 2. LOSER EXAM AT THE MARK",
        "",
        "## NCAAB H1_2 Discovery",
        * _fmt_exam(payload["loser_exam"]["ncaab_h1_2_discovery"]),
        "",
        "## NCAAB H2_1 Discovery",
        * _fmt_exam(payload["loser_exam"]["ncaab_h2_1_discovery"]),
        "",
        "## NBA 604 in-sample Q4",
        * _fmt_exam(payload["loser_exam"]["nba_604_in_sample"]),
        "",
        "# 3. SELECTED CELLS (PER BOOK)",
        "",
        f"A: {_fmt_cell(payload['selected']['ncaab_h1_2_discovery'])}",
        f"B: {_fmt_cell(payload['selected']['ncaab_h2_1_discovery'])}",
        f"NBA: {_fmt_cell(payload['selected']['nba_604_in_sample'])}",
        "",
        "# 4. MIXED 80/40 UNDER SELECTED CELL OR NONE",
        "",
        f"A mixed {a['katy_vs_8040']['mean_cents']} vs always 80/40 {a['always_8040']['mean_cents']} hedges={a['n_hedge_scenario']}",
        f"B mixed {b['katy_vs_8040']['mean_cents']} vs always 80/40 {b['always_8040']['mean_cents']} hedges={b['n_hedge_scenario']}",
        f"NBA mixed {nba['katy_vs_8040']['mean_cents']} vs always 80/40 {nba['always_8040']['mean_cents']} hedges={nba['n_hedge_scenario']}",
        "",
        "# 5. WHAT THIS DOES NOT PROVE",
        "",
        "In-sample search. Not confirmation. Not a fill. Not a frozen policy.",
        "Books are never combined. Phase 8 is not justified.",
        "",
    ]
    return "\n".join(lines) + "\n"


def load_v2() -> dict[str, Any] | None:
    manifest = load_json(experiment_dir() / "MANIFEST.json", required=False)
    if not manifest:
        return None
    ledgers = load_json(experiment_dir() / "ledgers.json", required=False) or {}
    grid = load_json(experiment_dir() / "grid.json", required=False) or {}
    return {**manifest, "ledgers": ledgers, "grid": grid}


def handle_v2() -> dict[str, Any]:
    payload = load_v2()
    if payload:
        return payload
    return build_v2()
