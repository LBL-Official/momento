"""Shared Katy measurement. Frozen Austin. Houston lock is declared, not a fill."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B
from roller.austin.experiments.persistence.load import confirmation_files_absent, load_discovery_cohort, refuse_confirmation_path
from roller.austin.knn import match_query
from roller.austin.locks import N_Q2, N_Q3
from roller.austin.outcomes import hold_pnl_cents, taker_8040_pnl_cents
from roller.austin.paths import experiment_dir
from roller.austin.pca import transform_row
from roller.austin.query import _meta_from_frame
from roller.austin.store import load_pca_model, load_snapshots
from roller.choosin_texas.houston import declared_lock_vs_entry_cents, declared_no_taker_cents, houston_identity
from roller.choosin_texas.sources import repo_root

ENTRY_CENTS = 80
NBA_PERIOD = 4
NCAAB_PERIOD = 2
PRICE_BUCKETS = (
    ("lt_41", lambda p: p < 41),
    ("41_50", lambda p: 41 <= p <= 50),
    ("51_60", lambda p: 51 <= p <= 60),
    ("61_70", lambda p: 61 <= p <= 70),
    ("71_80", lambda p: 71 <= p <= 80),
    ("81_90", lambda p: 81 <= p <= 90),
    ("91_99", lambda p: p >= 91),
)


def katy_root() -> Path:
    return repo_root() / "research" / "choosin_texas" / "library" / "katy"


def as_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:
        return None
    return num


def mean_cents(vals: list[int]) -> dict[str, Any]:
    if not vals:
        return {"n": 0, "sum_cents": 0, "mean_cents": None}
    total = int(sum(vals))
    return {"n": len(vals), "sum_cents": total, "mean_cents": total / len(vals)}


def mean_float(vals: list[float]) -> float | None:
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def median_int(vals: list[int]) -> int | None:
    if not vals:
        return None
    ordered = sorted(vals)
    return ordered[len(ordered) // 2]


def first_at_or_after(rows: list[dict[str, Any]], *, period: int, mark: int, period_key: str, rem_key: str) -> dict[str, Any] | None:
    eligible = []
    for row in rows:
        per = as_int(row.get(period_key))
        rem = as_int(row.get(rem_key))
        if per != period or rem is None or rem > mark:
            continue
        eligible.append((rem, row))
    if not eligible:
        return None
    eligible.sort(key=lambda item: -item[0])
    return eligible[0][1]


def classify(price: int | None, ev: float | None, *, lo: int, hi: int, ev_lt: float) -> str:
    if price is None:
        return "PRICE_UNAVAILABLE"
    if price > hi:
        return "NOT_UNDERWATER"
    if price < lo:
        return "THROUGH_BAND"
    if ev is None:
        return "AUSTIN_EV_UNAVAILABLE"
    if ev < ev_lt:
        return "HEDGE_SCENARIO"
    return "HOLD"


def assert_confirmation_sealed() -> None:
    if confirmation_files_absent().get("status") != "PASS":
        raise AustinError("LOCK_MISMATCH", "confirmation result artifacts present")


def components(*, hedge_if: str) -> dict[str, Any]:
    return {
        "dallas": {
            "role": "clock + yes_bid path at the run mark",
            "page": "#/dallas",
            "note": "Dallas UI stays 2Q/3Q. Katy may read later 4Q path on the same 604 trades.",
        },
        "houston": houston_identity(),
        "austin": {
            "role": "frozen hold-80-to-settlement EV at the run-mark snapshot. Model is not refit.",
            "hedge_if": hedge_if,
            "missing_ev": "AUSTIN_EV_UNAVAILABLE → no hedge",
            "page": "#/austin",
            "optimize": "threshold and price-range search only. Not a retrain.",
        },
    }


def _price_buckets(prices: list[int]) -> dict[str, int]:
    out = {name: 0 for name, _ in PRICE_BUCKETS}
    for price in prices:
        for name, pred in PRICE_BUCKETS:
            if pred(price):
                out[name] += 1
                break
    return out


def _side_exam(group: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [int(r["yes_bid"]) for r in group if r.get("yes_bid") is not None]
    evs = [float(r["austin_ev_cents"]) for r in group if r.get("austin_ev_cents") is not None]
    open_rows = [r for r in group if r.get("yes_bid") is not None and int(r["yes_bid"]) >= 41]
    open_evs = [float(r["austin_ev_cents"]) for r in open_rows if r.get("austin_ev_cents") is not None]
    scores = [as_int(r.get("score_differential")) for r in group]
    scores_ok = [s for s in scores if s is not None]
    return {
        "n": len(group),
        "n_open_ge_41": len(open_rows),
        "n_already_lt_41": sum(1 for r in group if r.get("yes_bid") is not None and int(r["yes_bid"]) < 41),
        "n_t40_already_at_mark": sum(1 for r in group if r.get("t40_already_at_mark")),
        "n_t40_terminal": sum(1 for r in group if r.get("t40")),
        "n_ev_available": len(evs),
        "n_ev_unavailable": len(group) - len(evs),
        "n_open_ev_available": len(open_evs),
        "price": {"n": len(prices), "mean": mean_float([float(p) for p in prices]), "median": median_int(prices)},
        "open_price": {
            "n": len(open_rows),
            "mean": mean_float([float(r["yes_bid"]) for r in open_rows]),
            "median": median_int([int(r["yes_bid"]) for r in open_rows]),
        },
        "ev": {"n": len(evs), "mean": mean_float(evs)},
        "open_ev": {"n": len(open_evs), "mean": mean_float(open_evs)},
        "score_differential": {"n": len(scores_ok), "mean": mean_float([float(s) for s in scores_ok]), "median": median_int(scores_ok)},
        "price_buckets": _price_buckets(prices),
    }


def examine_at_mark(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reached = [r for r in rows if r.get("run_mark_reached")]
    losers = [r for r in reached if r.get("won") is False]
    winners = [r for r in reached if r.get("won") is True]
    return {
        "n_reached": len(reached),
        "losers": _side_exam(losers),
        "winners": _side_exam(winners),
        "note": "Terminal loser/winner identity is settlement. Mark stats are first snapshot at or after the clock.",
    }


def apply_rule(
    base_rows: list[dict[str, Any]],
    *,
    lo: int,
    hi: int,
    ev_lt: float,
    block_if_already_stopped: bool = False,
) -> list[dict[str, Any]]:
    out = []
    for raw in base_rows:
        row = dict(raw)
        if not raw.get("run_mark_reached"):
            row["action"] = "RUN_MARK_MISSING"
            row["in_price_band"] = False
            row["katy_pnl_cents"] = raw.get("hold_pnl_cents")
            row["katy_8040_pnl_cents"] = raw.get("taker_8040_pnl_cents")
            out.append(row)
            continue
        price = as_int(raw.get("yes_bid"))
        ev = as_float(raw.get("austin_ev_cents"))
        action = classify(price, ev, lo=lo, hi=hi, ev_lt=ev_lt)
        if block_if_already_stopped and raw.get("t40_already_at_mark") and action == "HEDGE_SCENARIO":
            action = "THROUGH_BAND"
        lock = raw.get("lock_pnl_cents")
        hedge = action == "HEDGE_SCENARIO" and lock is not None
        row["in_price_band"] = price is not None and lo <= price <= hi
        row["action"] = action
        row["katy_pnl_cents"] = lock if hedge else raw.get("hold_pnl_cents")
        row["katy_8040_pnl_cents"] = lock if hedge else raw.get("taker_8040_pnl_cents")
        out.append(row)
    return out


def summarize_rule(rows: list[dict[str, Any]], *, book: str) -> dict[str, Any]:
    reached = [r for r in rows if r.get("run_mark_reached")]
    hedges = [r for r in reached if r.get("action") == "HEDGE_SCENARIO"]
    clocks = [as_int(r.get("used_remaining")) for r in reached]
    clocks_ok = [c for c in clocks if c is not None]
    katy = [int(r["katy_pnl_cents"]) for r in reached if r.get("katy_pnl_cents") is not None]
    katy_8040 = [int(r["katy_8040_pnl_cents"]) for r in reached if r.get("katy_8040_pnl_cents") is not None]
    hold = [int(r["hold_pnl_cents"]) for r in reached if r.get("hold_pnl_cents") is not None]
    taker = [int(r["taker_8040_pnl_cents"]) for r in reached if r.get("taker_8040_pnl_cents") is not None]
    losers = [r for r in reached if r.get("won") is False]
    return {
        "book": book,
        "n_trades": len(rows),
        "n_run_mark_reached": len(reached),
        "n_in_price_band": sum(1 for r in reached if r.get("in_price_band")),
        "n_hedge_scenario": len(hedges),
        "n_hedge_losers": sum(1 for r in hedges if r.get("won") is False),
        "n_hedge_winners": sum(1 for r in hedges if r.get("won") is True),
        "n_hold_in_band": sum(1 for r in reached if r.get("action") == "HOLD"),
        "n_ev_unavailable_in_band": sum(1 for r in reached if r.get("action") == "AUSTIN_EV_UNAVAILABLE"),
        "n_not_underwater": sum(1 for r in reached if r.get("action") == "NOT_UNDERWATER"),
        "n_through_band": sum(1 for r in reached if r.get("action") == "THROUGH_BAND"),
        "used_remaining": {
            "min": None if not clocks_ok else min(clocks_ok),
            "median": None if not clocks_ok else median_int(clocks_ok),
            "max": None if not clocks_ok else max(clocks_ok),
        },
        "katy_path": mean_cents(katy),
        "katy_vs_8040": mean_cents(katy_8040),
        "always_hold": mean_cents(hold),
        "always_8040": mean_cents(taker),
        "hedge_subset_lock": mean_cents([int(r["lock_pnl_cents"]) for r in hedges if r.get("lock_pnl_cents") is not None]),
        "hedge_subset_had_held": mean_cents([int(r["hold_pnl_cents"]) for r in hedges if r.get("hold_pnl_cents") is not None]),
        "hedge_subset_had_8040": mean_cents([int(r["taker_8040_pnl_cents"]) for r in hedges if r.get("taker_8040_pnl_cents") is not None]),
        "losers_hold": mean_cents([int(r["hold_pnl_cents"]) for r in losers if r.get("hold_pnl_cents") is not None]),
        "losers_katy": mean_cents([int(r["katy_pnl_cents"]) for r in losers if r.get("katy_pnl_cents") is not None]),
        "losers_katy_8040": mean_cents([int(r["katy_8040_pnl_cents"]) for r in losers if r.get("katy_8040_pnl_cents") is not None]),
        "note": "SCENARIO — NOT OBSERVED FILL. Members are never combined with another book.",
    }


def score_cell(base_rows: list[dict[str, Any]], *, lo: int, hi: int, ev_lt: float) -> dict[str, Any]:
    applied = apply_rule(base_rows, lo=lo, hi=hi, ev_lt=ev_lt, block_if_already_stopped=True)
    reached = [r for r in applied if r.get("run_mark_reached") and r.get("taker_8040_pnl_cents") is not None and r.get("katy_8040_pnl_cents") is not None]
    base = [int(r["taker_8040_pnl_cents"]) for r in reached]
    mixed = [int(r["katy_8040_pnl_cents"]) for r in reached]
    hedges = [r for r in reached if r.get("action") == "HEDGE_SCENARIO"]
    delta = int(sum(mixed) - sum(base)) if base else 0
    return {
        "price_lo": lo,
        "price_hi": hi,
        "austin_ev_lt": ev_lt,
        "n_hedge": len(hedges),
        "n_hedge_losers": sum(1 for r in hedges if r.get("won") is False),
        "n_hedge_winners": sum(1 for r in hedges if r.get("won") is True),
        "baseline_8040": mean_cents(base),
        "mixed_8040": mean_cents(mixed),
        "delta_sum_cents": delta,
        "delta_mean_cents": None if not base else delta / len(base),
    }


def select_cell(cells: list[dict[str, Any]]) -> dict[str, Any]:
    viable = [c for c in cells if int(c.get("delta_sum_cents") or 0) > 0]
    ranked = sorted(
        cells,
        key=lambda c: (-int(c.get("delta_sum_cents") or 0), int(c.get("n_hedge") or 0), int(c.get("price_hi") or 99), float(c.get("austin_ev_lt") or 0)),
    )
    if not viable:
        return {
            "status": "NONE",
            "reason": "NO_CELL_BEATS_ALWAYS_8040",
            "best_nonpositive": None if not ranked else ranked[0],
        }
    chosen = sorted(
        viable,
        key=lambda c: (-int(c["delta_sum_cents"]), int(c["n_hedge"]), int(c["price_hi"]), float(c.get("austin_ev_lt") or 0)),
    )[0]
    return {"status": "SELECTED", **chosen}


def _measured_row(
    *,
    tid: str,
    first: dict[str, Any] | None,
    won: bool | None,
    t40: bool,
    price: int | None,
    ev: float | None,
    remaining: int | None,
    period: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hold = None if won is None else hold_pnl_cents(won=bool(won))
    taker = None if won is None else taker_8040_pnl_cents(won=bool(won), hit_40=t40)
    if first is None:
        missing = {
            "trade_id": tid,
            "run_mark_reached": False,
            "won": None if won is None else bool(won),
            "t40": t40,
            "hold_pnl_cents": hold,
            "taker_8040_pnl_cents": taker,
        }
        if extra:
            missing.update({k: v for k, v in extra.items() if k != "t40_already"})
        return missing
    t40_already = bool((price is not None and price < 41) or (extra or {}).get("t40_already"))
    row = {
        "trade_id": tid,
        "run_mark_reached": True,
        "period": period,
        "used_remaining": remaining,
        "yes_bid": price,
        "austin_ev_cents": ev,
        "houston_no_taker_cents": None if price is None else declared_no_taker_cents(price),
        "lock_pnl_cents": None if price is None else declared_lock_vs_entry_cents(price, entry_cents=ENTRY_CENTS),
        "won": None if won is None else bool(won),
        "t40": t40,
        "t40_already_at_mark": t40_already,
        "hold_pnl_cents": hold,
        "taker_8040_pnl_cents": taker,
        "fill_status": "FILL_UNAVAILABLE",
    }
    if extra:
        row.update({k: v for k, v in extra.items() if k != "t40_already"})
    return row


def measure_ncaab(*, mark_remaining: int) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    labels = {
        EXPERIMENT_A: "NCAAB H1_2 DISCOVERY",
        EXPERIMENT_B: "NCAAB H2_1 DISCOVERY",
    }
    for experiment_id, label in labels.items():
        path = refuse_confirmation_path(experiment_dir(experiment_id) / "discovery" / "state_queries.csv")
        if not path.is_file():
            raise AustinError("DATA_REQUIRED", f"{experiment_id} discovery queries missing")
        cohort = load_discovery_cohort(experiment_id)
        trades = {str(t.get("trade_id")): t for t in cohort.get("trades") or []}
        by_trade: dict[str, list[dict[str, Any]]] = {}
        with path.open(encoding="utf-8", newline="") as fh:
            for rec in csv.DictReader(fh):
                by_trade.setdefault(str(rec.get("trade_id") or ""), []).append(rec)
        rows = []
        for tid, recs in by_trade.items():
            trade = trades.get(tid) or {}
            first = first_at_or_after(recs, period=NCAAB_PERIOD, mark=mark_remaining, period_key="period", rem_key="game_clock_remaining")
            won = trade.get("won")
            t40 = bool(trade.get("t40"))
            price = None if first is None else as_int(first.get("current_price_cents"))
            ev = None if first is None else as_float(first.get("conditional_ev_cents"))
            rem = None if first is None else as_int(first.get("game_clock_remaining"))
            extra = None
            if first is not None:
                extra = {
                    "home_score": as_int(first.get("home_score")),
                    "away_score": as_int(first.get("away_score")),
                }
            rows.append(
                _measured_row(
                    tid=tid,
                    first=first,
                    won=None if won is None else bool(won),
                    t40=t40,
                    price=price,
                    ev=ev,
                    remaining=rem,
                    period=NCAAB_PERIOD,
                    extra=extra,
                )
            )
        out[experiment_id] = {
            "experiment_id": experiment_id,
            "label": label,
            "cohort": "DISCOVERY",
            "rows": rows,
            "loser_exam": examine_at_mark(rows),
        }
    return out


class NbaAustin:
    def __init__(self) -> None:
        import numpy as np

        snaps = load_snapshots()
        model = load_pca_model()
        names = list(model["names"])
        complete = snaps.dropna(subset=names)
        mat = complete[names].to_numpy(dtype=float)
        mu = np.array([model["mu"][n] for n in names])
        sd = np.array([model["sd"][n] for n in names])
        sd = np.where(sd == 0.0, 1.0, sd)
        self.model = model
        self.names = names
        self.scores = ((mat - mu) / sd) @ np.asarray(model["components"]).T
        self.meta = _meta_from_frame(complete)
        self.path = snaps[snaps["kind"] == "path"].copy()

    def ev(self, snapshot: dict[str, Any]) -> float | None:
        numeric = {name: as_float(snapshot.get(name)) for name in self.names}
        vec = transform_row(numeric, self.model)
        if vec is None:
            return None
        match = match_query(
            vec,
            self.scores,
            self.meta,
            exclude_trade_id=str(snapshot.get("trade_id") or ""),
            exclude_snapshot_id=str(snapshot.get("snapshot_id") or ""),
        )
        if match.get("status") != "OBSERVED":
            return None
        ev = match.get("weighted_mean_EV")
        return None if ev is None else float(ev)


def _nba_slice(sample: dict[str, Any]) -> str:
    raw = sample.get("slice")
    if raw is not None and raw == raw:
        text = str(raw).strip().upper()
        if text in {"Q2", "Q3", "2", "3"}:
            return {"2": "Q2", "3": "Q3"}.get(text, text)
    return {2: "Q2", 3: "Q3"}.get(as_int(sample.get("entry_quarter")) or as_int(sample.get("quarter")), "")


def measure_nba(*, mark_remaining: int, ev_when: str) -> dict[str, Any]:
    engine = NbaAustin()
    by_trade: dict[str, list[dict[str, Any]]] = {}
    for rec in engine.path.to_dict("records"):
        by_trade.setdefault(str(rec.get("trade_id")), []).append(rec)
    rows = []
    for tid, recs in by_trade.items():
        first = first_at_or_after(recs, period=NBA_PERIOD, mark=mark_remaining, period_key="quarter", rem_key="current_seconds_remaining")
        sample = recs[0]
        won = bool(sample.get("won"))
        t40 = bool(sample.get("csv_t40"))
        price = None if first is None else as_int(first.get("current_price_cents"))
        rem = None if first is None else as_int(first.get("current_seconds_remaining"))
        ev = None
        if first is not None:
            if ev_when == "always":
                ev = engine.ev(first)
            elif ev_when == "open" and price is not None and price >= 41:
                ev = engine.ev(first)
            elif ev_when == "in_band":
                raise AustinError("OPERATION_REQUIRED", "measure_nba in_band needs an explicit band")
        extra = {
            "snapshot_id": None if first is None else first.get("snapshot_id"),
            "t40_already": bool(first.get("t40_already")) if first is not None else False,
            "score_differential": None if first is None else as_int(first.get("score_differential")),
            "in_sample": True,
            "slice": _nba_slice(sample),
        }
        rows.append(
            _measured_row(
                tid=tid,
                first=first,
                won=won,
                t40=t40,
                price=price,
                ev=ev,
                remaining=rem,
                period=NBA_PERIOD,
                extra=extra,
            )
        )
    return {
        "experiment_id": "choosin_nba_2q3q_604",
        "label": "NBA 604 Q2/Q3 FIRST80 continued to 4Q",
        "cohort": "IN_SAMPLE_604",
        "rows": rows,
        "loser_exam": examine_at_mark(rows),
    }


def measure_nba_slices(*, mark_remaining: int, ev_when: str) -> dict[str, dict[str, Any]]:
    """Same frozen Austin path, split into locked NBA 2Q / 3Q books."""
    full = measure_nba(mark_remaining=mark_remaining, ev_when=ev_when)
    grouped: dict[str, list[dict[str, Any]]] = {"Q2": [], "Q3": []}
    for row in full["rows"]:
        slice_id = str(row.get("slice") or "")
        if slice_id not in grouped:
            raise AustinError("LOCK_MISMATCH", f"unexpected NBA slice {slice_id!r}")
        grouped[slice_id].append(row)
    if len(grouped["Q2"]) != N_Q2 or len(grouped["Q3"]) != N_Q3:
        raise AustinError(
            "LOCK_MISMATCH",
            f"NBA slice N {len(grouped['Q2'])}/{len(grouped['Q3'])} != {N_Q2}/{N_Q3}",
        )
    return {
        "nba_2q": {
            "experiment_id": "choosin_nba_2q",
            "label": "NBA 2Q FIRST80 continued to 2H last 10",
            "cohort": "IN_SAMPLE_Q2",
            "rows": grouped["Q2"],
            "loser_exam": examine_at_mark(grouped["Q2"]),
        },
        "nba_3q": {
            "experiment_id": "choosin_nba_3q",
            "label": "NBA 3Q FIRST80 continued to 2H last 10",
            "cohort": "IN_SAMPLE_Q3",
            "rows": grouped["Q3"],
            "loser_exam": examine_at_mark(grouped["Q3"]),
        },
    }


def measure_nba_in_band(*, mark_remaining: int, lo: int, hi: int) -> dict[str, Any]:
    engine = NbaAustin()
    by_trade: dict[str, list[dict[str, Any]]] = {}
    for rec in engine.path.to_dict("records"):
        by_trade.setdefault(str(rec.get("trade_id")), []).append(rec)
    rows = []
    for tid, recs in by_trade.items():
        first = first_at_or_after(recs, period=NBA_PERIOD, mark=mark_remaining, period_key="quarter", rem_key="current_seconds_remaining")
        sample = recs[0]
        won = bool(sample.get("won"))
        t40 = bool(sample.get("csv_t40"))
        price = None if first is None else as_int(first.get("current_price_cents"))
        rem = None if first is None else as_int(first.get("current_seconds_remaining"))
        ev = None
        if first is not None and price is not None and lo <= price <= hi:
            ev = engine.ev(first)
        extra = {
            "snapshot_id": None if first is None else first.get("snapshot_id"),
            "t40_already": bool(first.get("t40_already")) if first is not None else False,
            "score_differential": None if first is None else as_int(first.get("score_differential")),
            "in_sample": True,
        }
        rows.append(
            _measured_row(
                tid=tid,
                first=first,
                won=won,
                t40=t40,
                price=price,
                ev=ev,
                remaining=rem,
                period=NBA_PERIOD,
                extra=extra,
            )
        )
    return {
        "experiment_id": "choosin_nba_2q3q_604",
        "label": "NBA 604 Q2/Q3 FIRST80 continued to 4Q",
        "cohort": "IN_SAMPLE_604",
        "rows": rows,
        "loser_exam": examine_at_mark(rows),
    }
