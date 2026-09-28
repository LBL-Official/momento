"""Katy experiment 4: independent 55/45 last-10 clock trail. No Austin."""

from __future__ import annotations

import json
from typing import Any

from roller.choosin_texas.houston import houston_identity
from roller.choosin_texas.katy.common import katy_root
from roller.choosin_texas.katy.four_universe import LAST10, measure_clock_trail

EXPERIMENT_ID = "KATY_V4_LAST10_CLOCK_TRAIL"
SLUG = "last10-clock-trail-55-45"
TITLE = "2H last 10 clock trail — 55 / 45 / 40 vs 80/40"
NUMBER = 4
BOOK_KEYS = ("nba_2q", "nba_3q", "ncaab_h1_2", "ncaab_h2_1")
LABELS = {
    "nba_2q": "NBA 2Q",
    "nba_3q": "NBA 3Q",
    "ncaab_h1_2": "NCAAB 1H second 10",
    "ncaab_h2_1": "NCAAB 2H first 10",
}


def experiment_dir():
    return katy_root() / SLUG


def _write_json(path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_json(path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def card(*, books: dict[str, Any] | None = None) -> dict[str, Any]:
    lines = []
    if books:
        for key in BOOK_KEYS:
            row = books.get(key) or {}
            delta = row.get("delta_theo_mean")
            lines.append(
                f"{LABELS[key]} Δ{delta}¢ vs 80/40"
                if delta is not None
                else f"{LABELS[key]} UNAVAILABLE"
            )
    return {
        "number": NUMBER,
        "experiment_id": EXPERIMENT_ID,
        "slug": SLUG,
        "href": f"#/katy/{SLUG}",
        "title": TITLE,
        "question": (
            "On the locked NBA 2Q/3Q and NCAAB 1H/2H FIRST80 books, does a converted "
            "2H last 10 clock trail (≤55 early, ≤45 mid, else 80/40) raise candle-path EV vs always-80/40? No Austin."
        ),
        "marks": {
            "nba": "2H last 10 = Q4 12:00; early ≤55 while rem>6:00; mid ≤45 from 6:00–3:00",
            "ncaab": "2H last 10 = 2H 10:00; early ≤55 while rem>5:00; mid ≤45 from 5:00–2:30",
        },
        "rule": "Independent path trail. FIRST80 entry kept. T40 kept. Extra last-10 sells at 55 then 45. Houston lock is declared at the triggering close. No Austin EV.",
        "status": "MEASURED" if books else "DECLARED",
        "one_line": None if not lines else "; ".join(lines) + ". Not a freeze. Books never combined.",
    }


def build_v4() -> dict[str, Any]:
    measured = measure_clock_trail()
    books = {key: measured[key]["summary"] for key in BOOK_KEYS}
    payload = {
        "status": "OBSERVED",
        "kind": "experiment",
        "surface": "trail",
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
        "pbp_sequence_not_pit": True,
        "policy_frozen": False,
        "confirmation_accessed": False,
        "austin_used": False,
        "austin_refit": False,
        "independent_study": True,
        "universe": "derived_four_936",
        "season": "2025-2026",
        "components": {
            "path": {
                "role": "warehouse 1m TRADABLE_YES_BID + PBP clock on the converted last-10 trail",
                "note": "PBP sequence is not candle PIT. Zero/non-positive closes are skipped.",
            },
            "houston": houston_identity(),
            "austin": {
                "role": "NOT USED",
                "hedge_if": "clock trail only",
                "missing_ev": "Austin EV is not a member of this experiment",
            },
        },
        "question": (
            "Does the converted 2H last 10 55→45→40 trail beat always-80/40 on each locked book?"
        ),
        "marks": {
            "nba": "2H last 10 = Q4 12:00; early ≤55 while rem>6:00; mid ≤45 from 6:00–3:00",
            "ncaab": "2H last 10 = 2H 10:00; early ≤55 while rem>5:00; mid ≤45 from 5:00–2:30",
        },
        "conversion": {
            "label": "2H last 10",
            "nba": LAST10["NBA"],
            "ncaab": LAST10["NCAAB"],
            "rows": [
                {"label": "last-10 open", "nba": "Q4 12:00 remaining", "ncaab": "2H 10:00 remaining"},
                {"label": "early last-10 sell ≤55", "nba": "Q4 remaining > 6:00", "ncaab": "2H remaining > 5:00"},
                {"label": "mid last-10 sell ≤45", "nba": "Q4 6:00–3:00 remaining", "ncaab": "2H 5:00–2:30 remaining"},
                {"label": "else", "nba": "80/40 T40", "ncaab": "80/40 T40"},
            ],
        },
        "loser_exam": {key: measured[key]["loser_exam"] for key in BOOK_KEYS},
        "books": books,
        "book_order": list(BOOK_KEYS),
        "row_counts": {key: len(measured[key]["rows"]) for key in BOOK_KEYS},
        "ledgers": {key: measured[key]["rows"] for key in BOOK_KEYS},
        "card": card(books=books),
        "combined_headline_forbidden": True,
        "search_is_not_a_freeze": True,
        "note": (
            "Katy experiment 4. Independent of Austin. Converted 2H last 10 clock trail. "
            "Houston lock is declared, not a fill. Candle path ≠ fill."
        ),
    }
    for key in BOOK_KEYS:
        payload[key] = {
            "partition_id": key,
            "label": LABELS[key],
            "summary": books[key],
        }
    _persist(payload)
    return payload


def _persist(payload: dict[str, Any]) -> None:
    root = experiment_dir()
    body = {k: payload[k] for k in payload if k != "ledgers"}
    _write_json(root / "MANIFEST.json", body)
    _write_json(root / "statistics.json", payload["books"])
    _write_json(root / "houston.json", houston_identity())
    _write_json(root / "loser_exam.json", payload["loser_exam"])
    _write_json(root / "ledgers.json", payload["ledgers"])
    (root / "REPORT.md").write_text(_report_md(payload), encoding="utf-8")


def _fmt_exam(exam: dict[str, Any]) -> list[str]:
    losers = exam.get("losers") or {}
    winners = exam.get("winners") or {}
    return [
        f"reached={exam.get('n_reached')} losers={losers.get('n')} winners={winners.get('n')}",
        (
            f"losers open≥41={losers.get('n_open_ge_41')} already<41={losers.get('n_already_lt_41')} "
            f"already stopped={losers.get('n_t40_already_at_mark')} terminal t40={losers.get('n_t40_terminal')}"
        ),
        f"loser price mean/median {losers.get('price', {}).get('mean')}/{losers.get('price', {}).get('median')} buckets={losers.get('price_buckets')}",
        f"winner price mean/median {winners.get('price', {}).get('mean')}/{winners.get('price', {}).get('median')} buckets={winners.get('price_buckets')}",
        f"loser score-diff n/mean {losers.get('score_differential', {}).get('n')}/{losers.get('score_differential', {}).get('mean')}",
        f"winner score-diff n/mean {winners.get('score_differential', {}).get('n')}/{winners.get('score_differential', {}).get('mean')}",
    ]


def _report_md(payload: dict[str, Any]) -> str:
    lines = [
        "KATY TEXAS — EXPERIMENT 4",
        TITLE.upper(),
        "",
        "RESEARCH ONLY",
        "INDEPENDENT OF AUSTIN",
        "CANDLE PATH ≠ FILL",
        "PBP SEQUENCE ≠ PIT",
        "EXECUTION DISABLED",
        "",
        "# 1. QUESTION",
        "",
        payload["question"],
        "",
        "2H last 10 conversion: NBA Q4 12:00 ≡ NCAAB 2H 10:00.",
        "Early ≤55: NBA Q4 rem>6:00 ≡ NCAAB 2H rem>5:00.",
        "Mid ≤45: NBA Q4 6:00–3:00 ≡ NCAAB 2H 5:00–2:30.",
        "Else keep 80/40. Books: NBA 2Q 314, NBA 3Q 290, NCAAB 1H 193, NCAAB 2H 139.",
        "",
        "# 2. LOSER EXAM AT LAST-10 OPEN",
        "",
    ]
    for key in BOOK_KEYS:
        lines.append(f"## {LABELS[key]}")
        lines.extend(_fmt_exam(payload["loser_exam"][key]))
        lines.append("")
    lines.extend(["# 3. TRAIL VS ALWAYS 80/40", ""])
    for key in BOOK_KEYS:
        book = payload["books"][key]
        lines.append(
            f"{LABELS[key]} theo {book['overlay_theo']['mean_cents']} obs {book['overlay_obs']['mean_cents']} "
            f"vs 80/40 {book['always_8040']['mean_cents']} Δtheo={book['delta_theo_mean']} "
            f"stops 55/45/40={book['n_stop_55']}/{book['n_stop_45']}/{book['n_stop_40']} "
            f"cut winning survivors={book['cut_survivors_who_won']}"
        )
    lines.extend(
        [
            "",
            "# 4. WHAT THIS DOES NOT PROVE",
            "",
            "In-sample path trail on 2025-26 locked books. Not a fill. Not Austin. Not 2026-27.",
            "Books are never combined.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def load_v4() -> dict[str, Any] | None:
    manifest = _load_json(experiment_dir() / "MANIFEST.json")
    if not manifest:
        return None
    ledgers = _load_json(experiment_dir() / "ledgers.json") or {}
    return {**manifest, "ledgers": ledgers}


def handle_v4() -> dict[str, Any]:
    payload = load_v4()
    if payload:
        return payload
    return build_v4()
