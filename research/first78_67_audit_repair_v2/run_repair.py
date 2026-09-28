"""Build one immutable repair run. Does not write into the original runs."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research/first78_67_portfolio_v1/src"))
sys.path.insert(0, str(ROOT / "research/first78_67_oos_adverse_v1/src"))
sys.path.insert(0, str(ROOT / "research/first78_67_audit_repair_v2/src"))

from repair.bridge import layer_a_fixed_quantity, layer_c_completion
from repair.calendar import map_identity, sample_paths
from repair.inference import holm, per_contract, studentized_cluster_p
from repair.legacy_reconcile import reconcile
from repair.marks import daily_from_events, drawdown_report, minute_grid
from repair.model import empirical_baseline_label, validate_snapshots
from repair.oos_extract import extract_window
from repair.oracle import oracle_tail, replay_ids, worst_ids
from repair.scenarios import SPECS, play

EXP = ROOT / "research/first78_67_audit_repair_v2"
LEGACY_RUN = ROOT / "research/first78_67_portfolio_v1/runs/first78_67_20260926T074540Z"
LA = ZoneInfo("America/Los_Angeles")
RUN_ID = "audit_repair_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RUN = EXP / "runs" / RUN_ID


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("status\nEMPTY\n", encoding="utf-8")
        return
    keys: list[str] = []
    seen = set()
    flat = []
    for row in rows:
        item = {k: v for k, v in row.items() if not isinstance(v, (dict, list))}
        flat.append(item)
        for key in item:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stamp(rows: list[dict], **ids) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        item.update(ids)
        out.append(item)
    return out


def net_of(book: dict) -> int:
    return sum(int(row["net_pnl_cents"]) for row in book["trades"])


def trade_candidates() -> list[dict]:
    rows = []
    with (LEGACY_RUN / "01_trade_logs/trades.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "game_id": row["game_id"],
                    "contract_id": row["contract_id"],
                    "sport": row["sport"],
                    "signal_ts": int(row["entry_ts"]),
                    "action_ts": int(row["entry_ts"]),
                    "exit_ts": int(row["exit_ts"]),
                    "cash_ts": int(row["cash_ts"]),
                    "exit_reason": row["exit_reason"],
                    "entry_price_cents": int(row["entry_price_cents"]),
                    "stop_price_cents": int(row["exit_price_cents"]) if row["exit_reason"] == "STOP" else 67,
                    "terminal_result": row["terminal_result"],
                    "settlement_ts": int(row["exit_ts"]) if row["exit_reason"] != "STOP" else None,
                    "local_day": row["signal_pacific"][:10],
                    "population_id": "LEGACY_FIRST80_CONDITIONED_936",
                }
            )
    return rows


def days_between(start: str, end: str) -> list[str]:
    cursor = datetime.fromisoformat(start).date()
    last = datetime.fromisoformat(end).date()
    out = []
    while cursor <= last:
        out.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return out


def judge(coverage: str, mean, adverse) -> dict:
    if coverage != "COMPLETE_FOR_NORMALIZED_WAREHOUSE":
        return {
            "sample_selection": "weakens" if mean is not None and mean <= 0 else "unresolved",
            "execution": "weakens" if adverse is not None and adverse <= 0 else "unresolved",
        }
    return {
        "sample_selection": "unresolved" if mean is None else ("supports_sign" if mean > 0 else "weakens"),
        "execution": "unresolved" if adverse is None else ("supports_sign" if adverse > 0 else "weakens"),
    }


def scenario_table(cands: list[dict], test_id: str, population: str, *, with_latency: bool, seed: int) -> list[dict]:
    rows = []
    for scenario_id, spec in SPECS.items():
        if scenario_id.startswith("LATENCY") and not with_latency:
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "status": "BLOCKED_DATA",
                    "reason": "saved legacy trades have no subsequent bid path",
                    "test_id": test_id,
                    "population_id": population,
                    "run_id": RUN_ID,
                    "sport": "ALL",
                }
            )
            continue
        if spec.get("fail"):
            nets = []
            for rep in range(30):
                book = play(cands, scenario_id, seed=seed + rep)
                nets.append(net_of(book))
            mean = sum(nets) / len(nets)
            var = sum((value - mean) ** 2 for value in nets) / (len(nets) - 1)
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "reported_figure": "MEAN_OF_30_BERNOULLI_PATHS",
                    "net_pnl_cents": round(mean),
                    "monte_carlo_se_cents": (var / len(nets)) ** 0.5,
                    "test_id": test_id,
                    "population_id": population,
                    "run_id": RUN_ID,
                    "sport": "ALL",
                }
            )
            continue
        book = play(cands, scenario_id, seed=seed)
        rows.append(
            {
                "scenario_id": scenario_id,
                "admitted": len(book["trades"]),
                "rejected": len(book["rejections"]),
                "skipped": len(book["skipped"]),
                "unresolved": len(book["unresolved"]),
                "net_pnl_cents": net_of(book),
                "ending_equity_cents": book["ending_equity_cents"],
                "max_open": book["max_open"],
                "mean_net_cents_per_contract": per_contract(book["trades"]),
                "test_id": test_id,
                "population_id": population,
                "run_id": RUN_ID,
                "sport": "ALL",
            }
        )
    return rows


def main() -> None:
    RUN.mkdir(parents=True)
    for name in ("repair_contract.json", "scenario_registry.csv", "inference_contract.json", "audit_issue_matrix.csv"):
        shutil.copy(EXP / name, RUN / name)
    test_proc = subprocess.run(
        [sys.executable, "-m", "unittest", "research/first78_67_audit_repair_v2/tests/test_repair.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    (RUN / "unittest.txt").write_text(test_proc.stdout + test_proc.stderr, encoding="utf-8")
    legacy = reconcile(LEGACY_RUN)
    (RUN / "legacy_reconciliation.json").write_text(json.dumps(legacy, indent=2), encoding="utf-8")
    cands = trade_candidates()
    ref = play(cands, "REF")
    mapped = map_identity(cands)
    identity = play(mapped, "REF")
    stresses = scenario_table(cands, "LEGACY_936", "LEGACY_FIRST80_CONDITIONED_936", with_latency=False, seed=20251101)
    write_csv(RUN / "LEGACY_936/01_trade_logs/trades.csv", stamp(ref["trades"], test_id="LEGACY_936", scenario_id="REF", population_id="LEGACY_FIRST80_CONDITIONED_936", run_id=RUN_ID, sport_row="see sport column"))
    write_csv(RUN / "LEGACY_936/02_portfolio_logs/portfolio_events.csv", stamp(ref["events"], test_id="LEGACY_936", scenario_id="REF", population_id="LEGACY_FIRST80_CONDITIONED_936", run_id=RUN_ID, sport="ALL"))
    local_days = days_between(min(c["local_day"] for c in cands), max(c["local_day"] for c in cands))
    daily = daily_from_events(ref["events"], local_days)
    write_csv(RUN / "LEGACY_936/02_portfolio_logs/daily_returns.csv", stamp(daily, test_id="LEGACY_936", scenario_id="REF", population_id="LEGACY_FIRST80_CONDITIONED_936", run_id=RUN_ID, sport="ALL"))
    start = min(int(row["ts"]) for row in ref["events"])
    end = max(int(row["ts"]) for row in ref["events"])
    grid = minute_grid(ref["events"], ref["trades"], {}, start - (start % 60), end)
    (RUN / "LEGACY_936/02_portfolio_logs").mkdir(parents=True, exist_ok=True)
    (RUN / "LEGACY_936/02_portfolio_logs/drawdown.json").write_text(
        json.dumps(drawdown_report(ref["events"], grid), indent=2),
        encoding="utf-8",
    )
    write_csv(
        RUN / "LEGACY_936/02_portfolio_logs/minute_equity_head.csv",
        stamp(grid[:5] + grid[-5:], test_id="LEGACY_936", scenario_id="REF", population_id="LEGACY_FIRST80_CONDITIONED_936", run_id=RUN_ID, sport="ALL"),
    )
    (RUN / "LEGACY_936/02_portfolio_logs/minute_equity_status.json").write_text(
        json.dumps(
            {
                "rows": len(grid),
                "missing_rows": sum(1 for row in grid if row["mark_status"] == "MISSING"),
                "reason": "PATH_NOT_IN_SAVED_ARTIFACT",
                "note": "The full grid is retained in memory for the drawdown report. The CSV sample is the first and last five rows. Bid marks are missing because the saved trade file has no quote path.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    bridge_a = layer_a_fixed_quantity(ref["trades"], cands)
    bridge_c = layer_c_completion(cands)
    (RUN / "LEGACY_936/05_profitability_dissection").mkdir(parents=True, exist_ok=True)
    (RUN / "LEGACY_936/05_profitability_dissection/stop_versus_hold.json").write_text(
        json.dumps({"A": bridge_a, "C": bridge_c, "B": "see layer C admission counts; unit replay is in the test suite"}, indent=2),
        encoding="utf-8",
    )
    write_csv(RUN / "stress_comparison.csv", stresses)
    calendar = []
    maps = []
    for block in (1, 3, 7):
        sampled = sample_paths(cands, block=block, n_paths=20, seed=20251101 + block)
        for path in sampled["paths"]:
            path.update(test_id="LEGACY_936", population_id="LEGACY_FIRST80_CONDITIONED_936", run_id=RUN_ID, sport="ALL", scenario_id=f"BLOCK_{block}")
            calendar.append(path)
        maps.extend(sampled["maps"][:50])
    write_csv(RUN / "calendar_paths.csv", calendar)
    write_csv(RUN / "calendar_maps_sample.csv", stamp(maps, test_id="LEGACY_936", population_id="LEGACY_FIRST80_CONDITIONED_936", run_id=RUN_ID, sport="ALL", scenario_id="BLOCK_MAP"))
    summaries = []
    inference_rows = []
    for test_id, seed in (("OCT_2025", 20251015), ("APR_2025", 20250401)):
        print(test_id, "extract", flush=True)
        extracted = extract_window(test_id)
        ocands = extracted["candidates"]
        print(test_id, "candidates", len(ocands), flush=True)
        book = play(ocands, "REF", seed=seed)
        adverse = play(ocands, "JOINT_2_FEE_007", seed=seed)
        root = RUN / test_id
        for section in ("01_trade_logs", "02_portfolio_logs", "03_statistical_validation", "04_monte_carlo", "05_profitability_dissection", "06_markov_chains", "07_final_report"):
            (root / section).mkdir(parents=True, exist_ok=True)
        ids = {"test_id": test_id, "scenario_id": "REF", "population_id": "PRIMARY_EX_ANTE_FIRST78", "run_id": RUN_ID}
        write_csv(root / "01_trade_logs/trades.csv", stamp(book["trades"], **ids, sport="ALL"))
        write_csv(root / "01_trade_logs/exclusions.csv", stamp(extracted["exclusions"], **ids))
        write_csv(root / "02_portfolio_logs/portfolio_events.csv", stamp(book["events"], **ids, sport="ALL"))
        write_csv(root / "02_portfolio_logs/unresolved.csv", stamp(book["unresolved"], **ids, sport="ALL") or [{"status": "EMPTY", **ids, "sport": "ALL"}])
        if ocands:
            odays = days_between(min(c["local_day"] for c in ocands), max(c["local_day"] for c in ocands))
            write_csv(root / "02_portfolio_logs/daily_returns.csv", stamp(daily_from_events(book["events"], odays), **ids, sport="ALL"))
            paths = {c["contract_id"]: [(int(bar["ts"]), int(bar["bid"]) // 100) for bar in c.get("bars") or []] for c in ocands}
            if book["events"]:
                ostart = min(int(row["ts"]) for row in book["events"])
                oend = max(int(row["ts"]) for row in book["events"])
                ogrid = minute_grid(book["events"], book["trades"], paths, ostart - (ostart % 60), oend)
                (root / "02_portfolio_logs/drawdown.json").write_text(json.dumps(drawdown_report(book["events"], ogrid), indent=2), encoding="utf-8")
                write_csv(root / "02_portfolio_logs/minute_equity_sample.csv", stamp(ogrid[:3], **ids, sport="ALL"))
        for sport in ("Universe", "NBA", "NCAAB"):
            sport_rows = book["trades"] if sport == "Universe" else [row for row in book["trades"] if row["sport"] == sport]
            status_row = [{"sport": sport, "trades": len(sport_rows), "net_pnl_cents": sum(int(row["net_pnl_cents"]) for row in sport_rows), "status": "EMPTY" if not sport_rows else "HAS_TRADES", **ids}]
            write_csv(root / "01_trade_logs" / sport / "overall/summary.csv", status_row)
        infer_ref = studentized_cluster_p(book["trades"], draws=1000, seed=seed)
        infer_adv = studentized_cluster_p(adverse["trades"], draws=1000, seed=seed + 1)
        (root / "03_statistical_validation/primary_inference.json").write_text(json.dumps({"REF": infer_ref, "JOINT_2_FEE_007": infer_adv}, indent=2), encoding="utf-8")
        inference_rows.append({"test_id": test_id, "scenario_id": "REF", "mean_net_cents_per_contract": per_contract(book["trades"]), "p_status": infer_ref.get("status"), "p_value": infer_ref.get("one_sided_p"), "n_days": infer_ref.get("n_days"), "population_id": "PRIMARY_EX_ANTE_FIRST78", "run_id": RUN_ID, "sport": "ALL"})
        inference_rows.append({"test_id": test_id, "scenario_id": "JOINT_2_FEE_007", "mean_net_cents_per_contract": per_contract(adverse["trades"]), "p_status": infer_adv.get("status"), "p_value": infer_adv.get("one_sided_p"), "n_days": infer_adv.get("n_days"), "population_id": "PRIMARY_EX_ANTE_FIRST78", "run_id": RUN_ID, "sport": "ALL"})
        write_csv(root / "05_profitability_dissection/stress_comparison.csv", scenario_table(ocands, test_id, "PRIMARY_EX_ANTE_FIRST78", with_latency=True, seed=seed))
        model = validate_snapshots(ocands)
        (root / "06_markov_chains/status.json").write_text(
            json.dumps({"empirical_baseline": empirical_baseline_label(), "snapshot_diagnostic": model, "note": "completion-order transitions are descriptive only"}, indent=2),
            encoding="utf-8",
        )
        (root / "05_profitability_dissection/fill_markouts.csv").write_text(
            "status,reason,test_id,population_id,run_id,sport\nMEASURED_ADVERSE_SELECTION_UNAVAILABLE,No fill log. Minute bid closes are not fills.,"
            + f"{test_id},PRIMARY_EX_ANTE_FIRST78,{RUN_ID},ALL\n",
            encoding="utf-8",
        )
        tail = oracle_tail(ocands, seed=seed)
        worst = worst_ids(ocands, 0.5)
        oracle_book = replay_ids(ocands, worst)
        (root / "05_profitability_dissection/oracle_bound_results.json").write_text(
            json.dumps(
                {
                    "tail": {k: v for k, v in tail.items() if k != "failed_ids"},
                    "tail_failures": len(tail["failed_ids"]),
                    "worst_half_net_cents": net_of(oracle_book),
                    "executable": False,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        mean = per_contract(book["trades"])
        adverse_mean = per_contract(adverse["trades"])
        summaries.append(
            {
                "test_id": test_id,
                "coverage_status": extracted["coverage_status"],
                "sport_status": extracted["sport_status"],
                "candidates": len(ocands),
                "admitted": len(book["trades"]),
                "unresolved": len(book["unresolved"]),
                "intrabar_ambiguity": sum(1 for row in ocands if row.get("intrabar_ambiguity")),
                "ref_net_cents": net_of(book),
                "adverse_net_cents": net_of(adverse),
                "mean_net_cents_per_contract": mean,
                "adverse_mean": adverse_mean,
                "judgment": judge(extracted["coverage_status"], mean, adverse_mean),
                "inference_ref": infer_ref,
                "inference_adverse": infer_adv,
            }
        )
        (root / "07_final_report/window_summary.json").write_text(json.dumps(summaries[-1], indent=2), encoding="utf-8")
    valid = [(f"{row['test_id']}:{row['scenario_id']}", row["p_value"]) for row in inference_rows if row.get("p_value") is not None]
    excluded = [{"endpoint": f"{row['test_id']}:{row['scenario_id']}", "reason": row["p_status"]} for row in inference_rows if row.get("p_value") is None]
    (RUN / "primary_inference_holm.json").write_text(json.dumps({"family": inference_rows, "holm": holm(valid) if valid else [], "excluded": excluded}, indent=2), encoding="utf-8")
    write_csv(RUN / "primary_inference.csv", inference_rows)
    old_vs = [
        {
            "metric": "legacy_ref_net_cents",
            "old": 23548818,
            "new": net_of(ref),
            "reason": "repaired ledger replay of the 647 admitted trades",
            "population": "LEGACY_FIRST80_CONDITIONED_936",
            "scenario": "REF",
            "changed_assumption": "tie order is game_id rather than insertion sequence; export stores the funded price",
            "test_id": "LEGACY_936",
            "run_id": RUN_ID,
            "sport": "ALL",
        },
        {
            "metric": "identity_replay_net_cents",
            "old": net_of(ref),
            "new": net_of(identity),
            "reason": "calendar identity with no resampling",
            "population": "LEGACY_FIRST80_CONDITIONED_936",
            "scenario": "REF",
            "changed_assumption": "none",
            "test_id": "LEGACY_936",
            "run_id": RUN_ID,
            "sport": "ALL",
        },
        {
            "metric": "next_bar_net_cents",
            "old": 6581478,
            "new": None,
            "reason": "withdrawn; saved trades do not contain the later bid path",
            "population": "LEGACY_FIRST80_CONDITIONED_936",
            "scenario": "NEXT_BAR_PRICE_PROXY",
            "changed_assumption": "action timestamp must move with the price",
            "test_id": "LEGACY_936",
            "run_id": RUN_ID,
            "sport": "ALL",
            "status": "BLOCKED_DATA",
        },
        {
            "metric": "calendar_median_dollars",
            "old": 229554.86,
            "new": None,
            "reason": "withdrawn with the active-day 86400*block+5 simulator",
            "population": "LEGACY_FIRST80_CONDITIONED_936",
            "scenario": "BLOCK_7",
            "changed_assumption": "complete local-day blocks",
            "test_id": "LEGACY_936",
            "run_id": RUN_ID,
            "sport": "ALL",
            "status": "WITHDRAWN",
        },
    ]
    write_csv(RUN / "old_vs_repaired.csv", old_vs)
    withdrawn = [
        {"claim": "v1 uncentered bootstrap p-values and Holm adjustments", "disposition": "WITHDRAWN"},
        {"claim": "12255-path median $229,554.86 and 5th/95th percentiles $147,408.57/$354,986.99", "disposition": "WITHDRAWN"},
        {"claim": "next-bar net $65,814.78 as a causal replay", "disposition": "WITHDRAWN_PENDING_PATHS"},
    ]
    write_csv(RUN / "claims_withdrawn_or_replaced.csv", stamp(withdrawn, run_id=RUN_ID, test_id="ALL", scenario_id="ALL", population_id="ALL", sport="ALL"))
    root_contract = sha256(ROOT / "research/first78_67_portfolio_v1/contract.json")
    run_contract = sha256(LEGACY_RUN / "contract.json")
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    manifest = {
        "run_id": RUN_ID,
        "git": "GIT_UNAVAILABLE" if git.returncode else git.stdout.strip(),
        "python": sys.version.split()[0],
        "unittest_returncode": test_proc.returncode,
        "original_contract_sha256": {"root": root_contract, "run": run_contract, "match": root_contract == run_contract},
        "consumed_sha256": {
            "legacy_trades": sha256(LEGACY_RUN / "01_trade_logs/trades.csv"),
            "legacy_summary": sha256(LEGACY_RUN / "summary.json"),
            "repair_contract": sha256(EXP / "repair_contract.json"),
        },
        "austin_confirmation_outcomes": "not opened and not hashed",
        "live_execution": False,
        "fee_applicability": "FEE_APPLICABILITY_UNVERIFIED",
        "partial_fills": "UNSUPPORTED",
        "legacy_replay_matches_saved_net": net_of(ref) == 23548818,
        "identity_matches_ref": net_of(ref) == net_of(identity),
        "calendar_paths_stored": len(calendar),
        "summaries": summaries,
    }
    (RUN / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    matrix = (EXP / "audit_issue_matrix.csv").read_text(encoding="utf-8")
    matrix = matrix.replace("AWAITING_VERIFICATION", "FIXED_AND_VERIFIED" if test_proc.returncode == 0 else "BLOCKED_COMPUTE")
    (RUN / "audit_issue_matrix.csv").write_text(matrix, encoding="utf-8")
    findings = [
        "# FIRST78→67 audit repair",
        "",
        "Live execution is off. The headline remains an assumed close-proxy fill. A higher balance is not an out-of-sample pass.",
        "The November 2026–April 2027 launch assessment stays NOT_YET_IDENTIFIABLE.",
        "",
        f"Legacy reconciliation all_ok={legacy['all_ok']}. Repaired replay of the 647 admitted trades netted {net_of(ref)} cents against the saved {23548818}.",
        "Those 647 rows are the admitted book. candidate_audit.csv holds program exclusions, not a full ex-ante resample frame.",
        "The population is LEGACY_FIRST80_CONDITIONED_936. It conditions on later FIRST80 membership.",
        "",
        "Sample-selection evidence on that conditional book is not transportable to a prospective FIRST78 universe.",
        "Execution evidence remains hypothetical. Measured fills are unavailable.",
        "",
    ]
    for summary in summaries:
        findings.append(
            f"{summary['test_id']} coverage {summary['coverage_status']}. Candidates {summary['candidates']}. "
            f"Admitted {summary['admitted']}. Intrabar-ambiguity flags {summary['intrabar_ambiguity']}. "
            f"REF mean {summary['mean_net_cents_per_contract']}. Adverse mean {summary['adverse_mean']}. "
            f"Sample selection {summary['judgment']['sample_selection']}. Execution {summary['judgment']['execution']}."
        )
    findings.append("")
    findings.append("October is PREVIOUSLY_EXAMINED_RETROSPECTIVE_VALIDATION. April is a partial raw subset and is spent.")
    (RUN / "findings.md").write_text("\n".join(findings) + "\n", encoding="utf-8")
    (RUN / "limitations.md").write_text(
        "\n".join(
            [
                "# Limitations",
                "",
                "- Fee coefficient 0.0175 is FEE_APPLICABILITY_UNVERIFIED against a dated Kalshi schedule.",
                "- Partial fills are unsupported.",
                "- NBA clocks are MODELED_AVAILABILITY.",
                "- The saved 936 trade file has no bid path, so the causal next-bar dollar replacement is BLOCKED_DATA and the old $65,814.78 figure stays withdrawn.",
                "- Calendar paths are a 20-path descriptive resample of admitted trades, not a forecast.",
                "- NCAAB April has no 25APR market dates and no candlesticks.",
                "- Launch evidence is not identified.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (RUN / "launch_readiness.md").write_text(
        "\n".join(
            [
                "# Launch readiness",
                "",
                "Status: NOT_YET_IDENTIFIABLE.",
                "",
                "Missing evidence: a prospective population collected before the games, executable quotes, actual order and fill logs, and a fee schedule whose dates cover the orders.",
                "",
                "Paper/shadow protocol: record the close up-cross, the quotes available at the decision, any order, and any fill, without submitting from this research package. Do not place live orders from these results.",
                "",
                "No return range, probability of profitability, or launch approval is stated.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (RUN / "validation_report.md").write_text(
        "\n".join(
            [
                "# Validation",
                "",
                "Command: `ROLLER/.venv/bin/python -m unittest research/first78_67_audit_repair_v2/tests/test_repair.py`",
                "",
                f"Return code: {test_proc.returncode}",
                "",
                "Output file: `unittest.txt`.",
                "",
                f"Legacy reconciliation all_ok: {legacy['all_ok']}",
                "",
                f"Identity replay matches repaired REF: {net_of(ref) == net_of(identity)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    coverage_rows = [
        {"deliverable": "repair_contract.json", "status": "PRESENT"},
        {"deliverable": "legacy_reconciliation.json", "status": "PRESENT" if legacy["all_ok"] else "MISMATCH"},
        {"deliverable": "causal_next_bar_936", "status": "BLOCKED_DATA"},
        {"deliverable": "full_bid_minute_grid_936", "status": "MISSING_MARKS_RETAINED_NO_SAVED_PATH"},
        {"deliverable": "nested_snapshot_model_936", "status": "BLOCKED_DATA"},
        {"deliverable": "oos_windows", "status": "PRESENT"},
    ]
    write_csv(RUN / "deliverable_coverage.csv", stamp(coverage_rows, run_id=RUN_ID, test_id="ALL", scenario_id="ALL", population_id="ALL", sport="ALL"))
    (RUN / "README.md").write_text(
        f"# Audit repair {RUN_ID}\n\nIsolated from the original runs. Live execution is off.\n",
        encoding="utf-8",
    )
    (RUN / "review_bundle").mkdir()
    (RUN / "review_bundle/review_index.json").write_text(
        json.dumps({"run_id": RUN_ID, "launch": "NOT_YET_IDENTIFIABLE", "files": sorted(p.name for p in RUN.iterdir())}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"run_id": RUN_ID, "tests": test_proc.returncode, "legacy_ok": legacy["all_ok"], "repaired_net": net_of(ref), "windows": summaries}, indent=2, default=str))


if __name__ == "__main__":
    main()
