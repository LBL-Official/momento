#!/usr/bin/env python3
"""Run both windows. Contract files already exist; this script does not retune 78/67."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import random
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

EXP = Path(__file__).resolve().parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "research/first78_67_portfolio_v1/src"))
sys.path.insert(0, str(EXP / "src"))

from oos_adverse.eligibility import WINDOWS, local_day  # noqa: E402
from oos_adverse.inference import (  # noqa: E402
    account_sharpe,
    day_ends,
    holm,
    marked_drawdown,
    minute_marks,
    per_contract,
    studentized_cluster_p,
)
from oos_adverse.oracle import (  # noqa: E402
    oracle_tail_ids,
    random_acceptance,
    stop_fail_ids,
    worst_acceptance,
)
from oos_adverse.population import extract_window  # noqa: E402
from oos_adverse.scenarios import (  # noqa: E402
    BASELINE,
    SPECS,
    annotate,
    block_summaries,
    book_net,
    hold_candidates,
    latency_candidates,
    paired_rows,
    play,
    with_stop_failures,
)

LA = ZoneInfo("America/Los_Angeles")
RUN_ID = "oos_adverse_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RUN = EXP / "runs" / RUN_ID
SEEDS = {"OCT_2025": 20251015, "APR_2025": 20250401}


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("status\nEMPTY\n", encoding="utf-8")
        return
    flat = []
    for row in rows:
        flat.append({k: v for k, v in row.items() if not isinstance(v, (dict, list))})
    keys: list[str] = []
    seen = set()
    for row in flat:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat)


def stamp(rows: list[dict], **ids) -> list[dict]:
    out = []
    for row in rows:
        item = {k: v for k, v in row.items() if k != "bars"}
        item.update(ids)
        out.append(item)
    return out


def week_start(day: str) -> str:
    parsed = datetime.fromisoformat(day).date()
    return (parsed - timedelta(days=parsed.weekday())).isoformat()


def rollup(trades: list[dict], keyfn) -> list[dict]:
    groups = defaultdict(list)
    for trade in trades:
        groups[keyfn(trade)].append(trade)
    rows = []
    keys = sorted(groups, key=lambda key: int(key) if str(key).isdigit() else str(key))
    for key in keys:
        items = groups[key]
        nets = [int(t["net_pnl_cents"]) for t in items]
        rows.append(
            {
                "period": key,
                "n": len(items),
                "gross_pnl_cents": sum(int(t["gross_pnl_cents"]) for t in items),
                "fees_cents": sum(int(t["entry_fee_cents"]) + int(t["exit_fee_cents"]) for t in items),
                "net_pnl_cents": sum(nets),
                "book": "ONE_20000_BOOK_ATTRIBUTION",
            }
        )
    return rows


def period_tree(root: Path, trades: list[dict], **ids) -> None:
    scopes = {
        "Universe": trades,
        "NBA": [t for t in trades if t.get("sport") == "NBA"],
        "NCAAB": [t for t in trades if t.get("sport") == "NCAAB"],
    }
    for name, rows in scopes.items():
        if not rows:
            write_csv(root / name / "overall" / "summary.csv", stamp([{"status": "EMPTY"}], **ids, sport=name))
            continue
        write_csv(root / name / "daily" / "by_day.csv", stamp(rollup(rows, lambda t: t["local_day"]), **ids, sport=name))
        write_csv(root / name / "weekly" / "by_week.csv", stamp(rollup(rows, lambda t: week_start(t["local_day"])), **ids, sport=name))
        write_csv(root / name / "monthly" / "by_month.csv", stamp(rollup(rows, lambda t: t["local_day"][:7]), **ids, sport=name))
        write_csv(
            root / name / "batch" / "by_completion_batch.csv",
            stamp(rollup(rows, lambda t: str(int(t["completion_batch_id"]))), **ids, sport=name),
        )
        write_csv(
            root / name / "overall" / "summary.csv",
            stamp(
                [
                    {
                        "n": len(rows),
                        "net_pnl_cents": sum(int(t["net_pnl_cents"]) for t in rows),
                        "gross_pnl_cents": sum(int(t["gross_pnl_cents"]) for t in rows),
                        "fees_cents": sum(int(t["entry_fee_cents"]) + int(t["exit_fee_cents"]) for t in rows),
                    }
                ],
                **ids,
                sport=name,
            ),
        )


def identity(trades: list[dict]) -> dict:
    gross = sum(int(t["gross_pnl_cents"]) for t in trades)
    fees = sum(int(t["entry_fee_cents"]) + int(t["exit_fee_cents"]) for t in trades)
    net = sum(int(t["net_pnl_cents"]) for t in trades)
    nba = sum(int(t["net_pnl_cents"]) for t in trades if t.get("sport") == "NBA")
    ncaab = sum(int(t["net_pnl_cents"]) for t in trades if t.get("sport") == "NCAAB")
    return {
        "gross_minus_fees": gross - fees,
        "net": net,
        "identity_ok": gross - fees == net and nba + ncaab == net,
        "nba_net_cents": nba,
        "ncaab_net_cents": ncaab,
        "fees_cents": fees,
        "gross_pnl_cents": gross,
    }


def daily_equity(events: list[dict], marks: list[dict], start_ts: int, end_ts: int) -> tuple[list[float], list[float]]:
    realized = []
    marked = []
    carried = 2_000_000
    cursor = 0
    ordered = sorted(events, key=lambda row: int(row["ts"]))
    mark_cursor = 0
    last_mark = None
    ordered_marks = sorted(marks, key=lambda row: int(row["ts"]))
    for end in day_ends(start_ts, end_ts):
        while cursor < len(ordered) and int(ordered[cursor]["ts"]) <= end:
            carried = int(ordered[cursor]["equity_cents"])
            cursor += 1
        if ordered and end < int(ordered[0]["ts"]):
            realized.append(2_000_000.0)
        else:
            realized.append(float(carried))
        while mark_cursor < len(ordered_marks) and int(ordered_marks[mark_cursor]["ts"]) <= end:
            value = ordered_marks[mark_cursor].get("bid_marked_gross_equity_cents")
            if value is not None:
                last_mark = value
            mark_cursor += 1
        marked.append(float(last_mark) if last_mark is not None else float("nan"))
    return realized, marked


def judge(coverage: str, mean: float | None, adverse: float | None) -> dict:
    if coverage != "COMPLETE_FOR_NORMALIZED_WAREHOUSE":
        selection = "weakens" if mean is not None and mean <= 0 else "unresolved"
        execution = "weakens" if adverse is not None and adverse <= 0 else "unresolved"
        if mean is not None and mean > 0:
            selection = "unresolved"
        if adverse is not None and adverse > 0:
            execution = "unresolved"
        return {"sample_selection": selection, "execution": execution}
    return {
        "sample_selection": "unresolved" if mean is None else ("supports_sign" if mean > 0 else "weakens"),
        "execution": "unresolved" if adverse is None else ("supports_sign" if adverse > 0 else "weakens"),
    }


def scenario_rows(test_id: str, cands: list[dict]) -> tuple[list[dict], dict]:
    rows = []
    books = {}
    seed = SEEDS[test_id]
    for scenario_id in BASELINE:
        if scenario_id.startswith("ORACLE"):
            raise RuntimeError(scenario_id)
        spec = SPECS[scenario_id]
        used = cands
        note = None
        if scenario_id.startswith("LATENCY"):
            used, skipped = latency_candidates(cands, int(spec["latency"]))
            note = f"skipped {len(skipped)}"
        if scenario_id.startswith("STOP_FAIL"):
            stops = [c for c in cands if c["exit_reason"] == "STOP"]
            nets = []
            for rep in range(30):
                chosen = set(stop_fail_ids(stops, float(spec["fail_rate"]), seed + rep))
                altered = with_stop_failures(cands, chosen)
                nets.append(book_net(play(altered, "REF")))
            mean = sum(nets) / len(nets)
            var = sum((v - mean) ** 2 for v in nets) / (len(nets) - 1)
            example = with_stop_failures(cands, set(stop_fail_ids(stops, float(spec["fail_rate"]), seed)))
            book = play(example, "REF")
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "admitted": len(book.trades),
                    "net_pnl_cents": round(mean),
                    "reported_figure": "MEAN_OF_30_PATHS",
                    "monte_carlo_se_cents": math.sqrt(var / len(nets)),
                    "max_open_example_path": book.max_open,
                    "note": note,
                }
            )
            books[scenario_id] = book
            continue
        book = play(used, scenario_id)
        trades = annotate(book, used)
        rows.append(
            {
                "scenario_id": scenario_id,
                "admitted": len(trades),
                "rejected": len(book.rejections),
                "net_pnl_cents": book_net(book),
                "ending_equity_cents": book.ending_equity_cents,
                "max_open": book.max_open,
                "mean_net_cents_per_contract": per_contract(trades),
                "note": note,
            }
        )
        books[scenario_id] = book
    return rows, books


def oracle_rows(test_id: str, cands: list[dict]) -> list[dict]:
    seed = SEEDS[test_id]
    rows = []
    stops = [c for c in cands if c["exit_reason"] == "STOP"]
    tail_ids = set(oracle_tail_ids(stops, 0.05))
    tail = play(with_stop_failures(cands, tail_ids), "REF")
    rows.append(
        {
            "scenario_id": "ORACLE_TAIL_BOUND",
            "label": "ORACLE_TAIL_BOUND",
            "admitted": len(tail.trades),
            "net_pnl_cents": book_net(tail),
            "failures": len(tail_ids),
            "executable": False,
        }
    )
    for fraction in (1, 0.75, 0.5, 0.25):
        nets = []
        for rep in range(10):
            picked = random_acceptance(cands, fraction, seed + rep + int(fraction * 1000))
            nets.append(book_net(play(picked, "REF")))
        worst = worst_acceptance(cands, fraction)
        worst_book = play(worst, "REF")
        mean = sum(nets) / len(nets)
        var = sum((v - mean) ** 2 for v in nets) / (len(nets) - 1)
        rows.append(
            {
                "scenario_id": "RANDOM_ACCEPTANCE",
                "fraction": fraction,
                "label": "RANDOM_ACCEPTANCE_BENCHMARK",
                "mean_net_pnl_cents": mean,
                "monte_carlo_se_cents": math.sqrt(var / len(nets)),
                "oracle_net_pnl_cents": book_net(worst_book),
                "oracle_label": "ORACLE_ADVERSE_SELECTION_BOUND",
                "executable": False,
            }
        )
    return rows


def write_window(test_id: str, extracted: dict) -> dict:
    cands = extracted["candidates"]
    root = RUN / test_id
    root.mkdir(parents=True, exist_ok=True)
    for name in (
        "01_trade_logs",
        "02_portfolio_logs",
        "03_statistical_validation",
        "04_monte_carlo",
        "05_profitability_dissection",
        "06_markov_chains",
        "07_final_report",
    ):
        (root / name).mkdir(parents=True, exist_ok=True)
    ids = {
        "test_id": test_id,
        "population_id": "PRIMARY_EX_ANTE_FIRST78",
        "run_id": RUN_ID,
        "scenario_id": "REF",
    }
    stresses, books = scenario_rows(test_id, cands)
    ref = books["REF"]
    trades = annotate(ref, cands)
    for trade in trades:
        trade.update(ids)
    checked = identity(trades)
    events = [{**event, **ids} for event in ref.events]
    write_csv(root / "01_trade_logs" / "trades.csv", trades)
    write_csv(root / "02_portfolio_logs" / "portfolio_events.csv", events)
    write_csv(root / "02_portfolio_logs" / "sizing_epochs.csv", stamp(ref.epochs, **ids))
    batches = rollup(trades, lambda t: str(int(t["completion_batch_id"]))) if trades else []
    write_csv(root / "02_portfolio_logs" / "completion_batches.csv", stamp(batches, **ids))
    period_tree(root / "01_trade_logs", trades, **ids)
    start_ts = int(WINDOWS[test_id][0].timestamp())
    end_bound = int(WINDOWS[test_id][1].timestamp()) - 1
    last_ts = max([end_bound] + [int(t["cash_ts"]) for t in trades]) if trades else end_bound
    paths = extracted["paths"]
    marks = minute_marks(trades, ref.events, paths, start_ts, last_ts) if trades else []
    write_csv(root / "02_portfolio_logs" / "minute_equity.csv", stamp(marks, **ids))
    series = [2_000_000] + [int(row["bid_marked_gross_equity_cents"]) for row in marks if row["bid_marked_gross_equity_cents"] is not None]
    drawdown = marked_drawdown(marks)
    drawdown["with_initial_equity"] = max_drawdown_safe(series)
    realized_dd = max_drawdown_safe([2_000_000] + [int(event["equity_cents"]) for event in ref.events])
    (root / "02_portfolio_logs" / "drawdown.json").write_text(
        json.dumps({"marked": drawdown, "realized_event_equity": realized_dd}, indent=2),
        encoding="utf-8",
    )
    realized_days, marked_days = daily_equity(ref.events, marks, start_ts, last_ts)
    marked_clean = [v for v in marked_days if v == v]
    (root / "03_statistical_validation" / "sharpe.json").write_text(
        json.dumps(
            {
                "realized_account": account_sharpe(realized_days),
                "marked_account": account_sharpe(marked_clean) if len(marked_clean) >= 2 else {"status": "MARKS_UNAVAILABLE"},
                "marked_days_with_a_price": len(marked_clean),
                "calendar_days": len(realized_days),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    inference = studentized_cluster_p(trades, draws=2000, seed=SEEDS[test_id], min_days=10)
    adverse_trades = annotate(books["JOINT_2_FEE_007"], cands)
    adverse_inference = studentized_cluster_p(adverse_trades, draws=2000, seed=SEEDS[test_id] + 7, min_days=10)
    (root / "03_statistical_validation" / "primary_inference.json").write_text(
        json.dumps({"REF": inference, "JOINT_2_FEE_007": adverse_inference}, indent=2),
        encoding="utf-8",
    )
    (root / "04_monte_carlo" / "block_summaries.json").write_text(
        json.dumps(block_summaries(cands, n_paths=200, seed=SEEDS[test_id]), indent=2),
        encoding="utf-8",
    )
    write_csv(root / "05_profitability_dissection" / "stress_comparison.csv", stamp(stresses, **ids))
    paired = paired_rows(trades, cands)
    write_csv(root / "05_profitability_dissection" / "paired_stop_vs_hold.csv", stamp(paired, **ids))
    hold = play(hold_candidates(cands), "REF")
    hold_ids = {**ids, "scenario_id": "HOLD_REPLAY"}
    write_csv(
        root / "05_profitability_dissection" / "hold_replay.csv",
        stamp(
            [{"admitted": len(hold.trades), "net_pnl_cents": book_net(hold), "ending_equity_cents": hold.ending_equity_cents}],
            **hold_ids,
        ),
    )
    conditioned = [c for c in cands if c.get("diagnostic_conditioned")]
    omitted = [c for c in cands if not c.get("diagnostic_conditioned")]
    legacy = [c for c in cands if c.get("legacy_lock_intersection")]
    comparison = []
    for label, group in (
        ("FIRST80_CONDITIONED_DIAGNOSTIC", conditioned),
        ("OMITTED_NO_LATER_THRESHOLD", omitted),
        ("LEGACY_LOCK_INTERSECTION", legacy),
    ):
        book = play(group, "REF") if group else None
        comparison.append(
            {
                "population_id": label,
                "candidates": len(group),
                "admitted": 0 if book is None else len(book.trades),
                "portfolio_net_cents": None if book is None else book_net(book),
                "note": "separate book; not the original locked universe" if label == "LEGACY_LOCK_INTERSECTION" else "diagnostic label uses a later threshold",
            }
        )
    write_csv(root / "05_profitability_dissection" / "first80_selection_comparison.csv", stamp(comparison, test_id=test_id, run_id=RUN_ID, scenario_id="REF", sport=""))
    oracles = oracle_rows(test_id, cands)
    write_csv(root / "05_profitability_dissection" / "oracle_bound_results.csv", stamp(oracles, test_id=test_id, run_id=RUN_ID, population_id="PRIMARY_EX_ANTE_FIRST78", sport=""))
    write_csv(
        root / "05_profitability_dissection" / "fill_markouts.csv",
        [
            {
                "status": "MEASURED_ADVERSE_SELECTION_UNAVAILABLE",
                "reason": "No authorized order or fill log is in this study. Minute bids are not fills.",
                **ids,
            }
        ],
    )
    (root / "06_markov_chains" / "status.json").write_text(
        json.dumps(
            {
                "status": "NOT_APPLIED",
                "reason": "The development within-game model was fit on later 2025-26 dates. Scoring it here would be a backward transport. It is not trained on these windows.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    cutoff_row = next((row for row in marks if int(row["ts"]) >= end_bound - 60), None)
    summary = {
        "test_id": test_id,
        "coverage_status": extracted["coverage_status"],
        "sport_status": extracted["sport_status"],
        "candidates": len(cands),
        "admitted": len(trades),
        "rejected": len(ref.rejections),
        "max_open": ref.max_open,
        "identity": checked,
        "ending_equity_cents": ref.ending_equity_cents,
        "mean_net_cents_per_contract": per_contract(trades),
        "adverse_mean_net_cents_per_contract": per_contract(adverse_trades),
        "adverse_net_pnl_cents": book_net(books["JOINT_2_FEE_007"]),
        "hold_net_pnl_cents": book_net(hold),
        "paired_stop_minus_hold_cents": sum(int(row["stop_minus_hold_cents"]) for row in paired),
        "cutoff_marked_equity_cents": None if cutoff_row is None else cutoff_row.get("bid_marked_gross_equity_cents"),
        "final_equity_cents": ref.ending_equity_cents,
        "inference_ref": inference,
        "inference_adverse": adverse_inference,
        "comparison": comparison,
        "stresses": stresses,
        "complete_batches": sum(1 for row in batches if int(row["n"]) == 10),
        "partial_batches": sum(1 for row in batches if int(row["n"]) != 10),
        "marked_drawdown": drawdown,
        "realized_drawdown": realized_dd,
        "judgment": judge(extracted["coverage_status"], per_contract(trades), per_contract(adverse_trades)),
    }
    (root / "07_final_report" / "window_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    write_csv(root / "01_trade_logs" / "exclusions.csv", stamp(extracted["exclusions"], **ids))
    return summary


def max_drawdown_safe(series: list[int]) -> dict:
    from first78.stats import max_drawdown

    return max_drawdown([int(v) for v in series])


def manifest() -> dict:
    protected = [
        "ROLLER/roller/research/first80.py",
        "research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json",
    ]

    def sha(path: Path) -> str | None:
        if not path.exists():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True, stderr=subprocess.DEVNULL)
        git = {"commit": commit, "dirty": bool(dirty.strip()), "status": "OK"}
    except (subprocess.CalledProcessError, FileNotFoundError):
        git = {"commit": None, "dirty": None, "status": "GIT_UNAVAILABLE"}
    try:
        import pyarrow

        pyarrow_version = pyarrow.__version__
    except ImportError:
        pyarrow_version = None
    return {
        "run_id": RUN_ID,
        "git": git,
        "python": platform.python_version(),
        "pyarrow": pyarrow_version,
        "protected_sha256": {rel: sha(REPO / rel) for rel in protected},
        "austin_confirmation_outcomes": "not opened and not hashed",
        "live_execution": False,
    }


def findings(summaries: list[dict]) -> str:
    lines = [
        "# FIRST78→67 two-window findings",
        "",
        "Live execution is off. The headline is an assumed 78¢ fill and an assumed 67¢ sale on a minute bid close.",
        "The two accounts start over at $20,000. They are not pooled. A higher ending balance is not an out-of-sample pass.",
        "The November 2026–April 2027 launch assessment stays NOT_YET_IDENTIFIABLE.",
        "",
    ]
    for summary in summaries:
        lines.append(f"## {summary['test_id']}")
        lines.append("")
        lines.append(f"Coverage: `{summary['coverage_status']}`. Sport status: `{json.dumps(summary['sport_status'])}`.")
        lines.append(
            f"Ex-ante candidates {summary['candidates']}. REF admitted {summary['admitted']}. "
            f"Rejections {summary['rejected']}. Max open {summary['max_open']}."
        )
        lines.append(
            f"REF net {summary['identity']['net']} cents. Gross {summary['identity']['gross_pnl_cents']}. "
            f"Fees {summary['identity']['fees_cents']}. Identity holds: {summary['identity']['identity_ok']}."
        )
        lines.append(
            f"NBA attribution {summary['identity']['nba_net_cents']} cents. "
            f"NCAAB attribution {summary['identity']['ncaab_net_cents']} cents."
        )
        lines.append(
            f"Equal-weight mean net cents per admitted contract, REF: {summary['mean_net_cents_per_contract']}. "
            f"JOINT_2_FEE_007: {summary['adverse_mean_net_cents_per_contract']} "
            f"(portfolio net {summary['adverse_net_pnl_cents']} cents)."
        )
        lines.append(
            f"Cutoff marked equity {summary['cutoff_marked_equity_cents']} cents. "
            f"Final realized equity {summary['final_equity_cents']} cents."
        )
        lines.append(
            f"Complete batches {summary['complete_batches']}. Partial batches {summary['partial_batches']}."
        )
        lines.append(
            f"Same-quantity stop minus hold: {summary['paired_stop_minus_hold_cents']} cents. "
            f"Full hold replay net: {summary['hold_net_pnl_cents']} cents. Those are different comparisons."
        )
        ref_p = summary.get("inference_ref") or {}
        adv_p = summary.get("inference_adverse") or {}
        lines.append(
            f"Sample-selection reading: {summary['judgment']['sample_selection']}. "
            f"Execution reading: {summary['judgment']['execution']}."
        )
        lines.append(
            f"REF p-status {ref_p.get('status')} on {ref_p.get('n_days')} local days"
            + (f", one-sided p {ref_p.get('one_sided_p')}." if ref_p.get("one_sided_p") is not None else ".")
            + f" JOINT_2_FEE_007 p-status {adv_p.get('status')}"
            + (f", one-sided p {adv_p.get('one_sided_p')}." if adv_p.get("one_sided_p") is not None else ".")
        )
        lines.append(
            "supports_sign means the equal-weight mean stayed positive on this historical close proxy. "
            "weakens means that mean is at or below zero on the contracts that were actually available. "
            "A partial window does not describe the games that have no candles."
        )
        lines.append("")
    lines.append("## What this changes")
    lines.append("")
    lines.append(
        "October was already scanned in the 936-game study, including signals and settlement labels, and then left out of that book's P&L. "
        "A positive October sign would be a retrospective check on an ex-ante rule, not a forward confirmation. "
        "April is a partial raw ticker list. It cannot stand in for the April slate. "
        "The NCAAB market file has no 25APR event dates; its APR-stamped rows are 26APR, outside this window, and candlesticks are absent. "
        "On four April stops, the 1% and 5% stop-fail quotas round to zero failures, so those paths match REF."
    )
    lines.append(
        "Measured fill selection is unavailable. The oracle bounds are pessimistic constructions, not a queue and not a probability. "
        "Maker fills remain unavailable. Nothing here authorizes trading."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    if not (EXP / "contract.json").exists():
        raise SystemExit("contract.json is missing")
    RUN.mkdir(parents=True)
    for name in (
        "contract.json",
        "scenario_registry.csv",
        "prior_exposure_audit.csv",
        "assumptions.md",
        "requirements_traceability.csv",
        "null_test_spec.json",
        "source_inventory.csv",
        "source_coverage.csv",
        "corrections_vs_v1.md",
    ):
        shutil.copy(EXP / name, RUN / name)
    summaries = []
    funnel = []
    all_cands = []
    all_exclusions = []
    comparisons = []
    stresses = []
    oracles = []
    inference_rows = []
    for test_id in ("OCT_2025", "APR_2025"):
        print(test_id, "extract", flush=True)
        extracted = extract_window(test_id)
        print(test_id, "candidates", len(extracted["candidates"]), flush=True)
        summary = write_window(test_id, extracted)
        summaries.append(summary)
        funnel.append(
            {
                "test_id": test_id,
                "coverage_status": extracted["coverage_status"],
                "candidates": len(extracted["candidates"]),
                "exclusions": len(extracted["exclusions"]),
                "sport_status": json.dumps(extracted["sport_status"]),
            }
        )
        all_cands.extend(stamp(extracted["candidates"], test_id=test_id, population_id="PRIMARY_EX_ANTE_FIRST78", run_id=RUN_ID, scenario_id="REF"))
        all_exclusions.extend(stamp(extracted["exclusions"], test_id=test_id, population_id="PRIMARY_EX_ANTE_FIRST78", run_id=RUN_ID, scenario_id="REF"))
        comparisons.extend(summary["comparison"])
        for row in summary["stresses"]:
            stresses.append({**row, "test_id": test_id, "run_id": RUN_ID, "population_id": "PRIMARY_EX_ANTE_FIRST78"})
        inference_rows.append(
            {
                "test_id": test_id,
                "scenario_id": "REF",
                "mean_net_cents_per_contract": summary["mean_net_cents_per_contract"],
                "p_status": summary["inference_ref"].get("status"),
                "p_value": summary["inference_ref"].get("one_sided_p"),
                "n_days": summary["inference_ref"].get("n_days"),
            }
        )
        inference_rows.append(
            {
                "test_id": test_id,
                "scenario_id": "JOINT_2_FEE_007",
                "mean_net_cents_per_contract": summary["adverse_mean_net_cents_per_contract"],
                "p_status": summary["inference_adverse"].get("status"),
                "p_value": summary["inference_adverse"].get("one_sided_p"),
                "n_days": summary["inference_adverse"].get("n_days"),
            }
        )
    valid = [(f"{row['test_id']}:{row['scenario_id']}", row["p_value"]) for row in inference_rows if row.get("p_value") is not None]
    (RUN / "primary_inference_holm.json").write_text(
        json.dumps({"family": inference_rows, "holm": holm(valid) if valid else [], "note": "Holm uses only numeric primary p-values"}, indent=2),
        encoding="utf-8",
    )
    write_csv(RUN / "population_funnel.csv", funnel)
    write_csv(RUN / "all_candidates.csv", all_cands)
    write_csv(RUN / "exclusions.csv", all_exclusions)
    write_csv(RUN / "first80_selection_comparison.csv", comparisons)
    write_csv(RUN / "stress_comparison.csv", stresses)
    write_csv(RUN / "primary_inference.csv", inference_rows)
    # oracle files are already under each window; copy a combined view from those summaries is enough
    combined_oracle = []
    for test_id in ("OCT_2025", "APR_2025"):
        path = RUN / test_id / "05_profitability_dissection" / "oracle_bound_results.csv"
        if path.exists() and path.read_text().splitlines()[0] != "status":
            with path.open(newline="", encoding="utf-8") as handle:
                combined_oracle.extend(list(csv.DictReader(handle)))
    write_csv(RUN / "oracle_bound_results.csv", combined_oracle)
    write_csv(
        RUN / "fill_markouts.csv",
        [
            {
                "status": "MEASURED_ADVERSE_SELECTION_UNAVAILABLE",
                "reason": "No fill log. Minute bid closes are not fills.",
                "run_id": RUN_ID,
            }
        ],
    )
    write_csv(
        RUN / "adverse_selection_results.csv",
        [
            {
                "analysis": "FUTURE_THRESHOLD_SAMPLE",
                "where": "first80_selection_comparison.csv",
                "run_id": RUN_ID,
            },
            {
                "analysis": "MEASURED_FILL_SELECTION",
                "status": "MEASURED_ADVERSE_SELECTION_UNAVAILABLE",
                "run_id": RUN_ID,
            },
            {
                "analysis": "ACCEPTANCE_BOUNDS",
                "where": "oracle_bound_results.csv",
                "label": "not a queue and not a probability",
                "run_id": RUN_ID,
            },
        ],
    )
    text = findings(summaries)
    (RUN / "07_final_report").mkdir(exist_ok=True)
    (RUN / "findings.md").write_text(text, encoding="utf-8")
    (RUN / "07_final_report" / "findings.md").write_text(text, encoding="utf-8")
    limitations = """# Limitations

- October was already present in the v1 identity audit. Signals and settlement labels were computed there. This is a retrospective validation.
- April NBA coverage is the raw ticker subset on disk. The NCAAB market file has no 25APR dates; its APR stamps are 26APR, and candlesticks are absent.
- April stop-fail quotas on four triggered stops round to zero, so STOP_FAIL_1 and STOP_FAIL_5 match REF on that window.
- October Holm-adjusted p-values are in primary_inference_holm.json. A positive sign is not a 5% rejection after Holm.
- Assumed 78/67 fills are not maker fills. Depth flags are not a queue.
- Oracle acceptance uses later outcomes on purpose. It is a bound, not a policy.
- Random stop-failure rates are assumptions. The reported figure is the mean of 30 paths.
- With short calendars, dependence-aware intervals are fragile. A missing p-value is `P_VALUE_NOT_ESTIMABLE`.
- The launch window is not identified from these tests.
"""
    (RUN / "limitations.md").write_text(limitations, encoding="utf-8")
    (RUN / "07_final_report" / "limitations.md").write_text(limitations, encoding="utf-8")
    oos = """# OOS status

OCT_2025: PREVIOUSLY_EXAMINED_RETROSPECTIVE_VALIDATION. Spent for further selection once this file exists.

APR_2025: HISTORICAL_HOLDOUT_NOT_USED_IN_SELECTION relative to first78_67_portfolio_v1. Not a forward-time test. Coverage is partial. Spent for further selection once this file exists.

Neither status is independent confirmation created by a new folder.
"""
    (RUN / "oos_status.md").write_text(oos, encoding="utf-8")
    info = manifest()
    info["summaries"] = [{k: s[k] for k in ("test_id", "candidates", "admitted", "judgment", "coverage_status")} for s in summaries]
    (RUN / "manifest.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (RUN / "validation_report.md").write_text(
        "\n".join(
            [
                "# Validation",
                "",
                "Unit tests: `ROLLER/.venv/bin/python -m unittest research/first78_67_oos_adverse_v1/tests/test_oos.py`",
                "",
                "Identity checks are in each window summary under `identity`.",
                "",
                f"Run id `{RUN_ID}`.",
                "",
                "Git: " + json.dumps(info["git"]),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    review = {
        "run_id": RUN_ID,
        "launch_expectation": "NOT_YET_IDENTIFIABLE",
        "windows": info["summaries"],
        "measured_adverse_selection": "UNAVAILABLE",
        "live_execution": False,
    }
    (RUN / "review_bundle").mkdir()
    (RUN / "review_summary.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
    (RUN / "review_bundle" / "review_summary.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
    (RUN / "review_bundle" / "review_index.md").write_text(
        "\n".join(
            [
                "# Review index",
                "",
                f"Run `{RUN_ID}`.",
                "",
                "- `findings.md`",
                "- `oos_status.md`",
                "- `population_funnel.csv`",
                "- `primary_inference.csv`",
                "- `stress_comparison.csv`",
                "- `oracle_bound_results.csv`",
                "- `fill_markouts.csv`",
                "- `OCT_2025/` and `APR_2025/`",
                "",
                "Measured fills are unavailable. Oracle rows are bounds. The launch window is not identified.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (RUN / "spent_for_selection.json").write_text(
        json.dumps({"OCT_2025": "spent", "APR_2025": "spent", "run_id": RUN_ID}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(info["summaries"], indent=2), flush=True)


if __name__ == "__main__":
    main()
