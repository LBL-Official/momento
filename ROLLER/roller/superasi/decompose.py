"""Deterministic SuperASI decomposition. No RNG, ML, clustering, or signals."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.superasi.adverse_terminal import stress
from roller.superasi.exit_mixes import all_mixes, loss_for_trade, summarize_mix
from roller.superasi.fees import estimate, scenario_book
from roller.superasi.four_cell import as_fractions, cells_from_counts, cells_from_trades
from roller.superasi.library import load_package, write_decomp
from roller.superasi.liquidity import classify_path_loss
from roller.superasi.models import SuperasiError
from roller.superasi.path_windows import aggregate
from roller.superasi.versions import (
    CAVEATS,
    CODE_VERSION,
    DEFAULT_ADVERSE_P,
    DEFAULT_FEE,
    DEFAULT_FILL,
    SEMANTICS_VERSION,
)
from roller.superasi.package import utc_now


def decompose(
    package_id: str,
    *,
    fill_algorithm: str = DEFAULT_FILL,
    fee_scenario: str = DEFAULT_FEE,
    adverse_p: str = DEFAULT_ADVERSE_P,
    root=None,
    persist: bool = True,
) -> dict[str, Any]:
    loaded = load_package(package_id, root=root)
    pkg = loaded["package"]
    trades = loaded["trades"]
    windows = loaded["path_windows"]
    if pkg.get("price_basis") == "LAST_TRADE_PRINT":
        fee_block: dict[str, Any] = {
            "status": "DATA_REQUIRED",
            "code": "LAST_TRADE_PRINT_DATA_REQUIRED",
            "reason": "Last-trade prints do not establish an executable bid/ask exit.",
        }
        stop_ok = False
    else:
        fee_block = {}
        stop_ok = True

    if pkg.get("source") == "seed_asked_six" and pkg.get("empirical_four_cell"):
        four = pkg["empirical_four_cell"]
        locked = four["cells"]
        four = cells_from_counts(
            locked["W_and_not_T40"],
            locked["W_and_T40"],
            locked["L_and_not_T40"],
            locked["L_and_T40"],
        )
    else:
        four = cells_from_trades(trades)

    fr = as_fractions(four)
    if "S" not in fr:
        raise SuperasiError("DATA_REQUIRED", "cannot form S from path or four-cell")
    entry_cents, gain, gain_status = _entry_and_gain(trades)
    mixes = all_mixes(trades, fr["S"], gain=gain, entry=entry_cents)
    active = summarize_mix(trades, fr["S"], fill_algorithm, gain=gain, entry=entry_cents)
    mix_rows = [
        loss_for_trade(t, fill_algorithm, entry=entry_cents) for t in trades if _path_loss(t)
    ]
    liq = [classify_path_loss(t) for t in trades if _path_loss(t)]
    fees = scenario_book(str(pkg.get("price_basis")), trades, mix_rows)
    if fee_block:
        fees = fee_block
    mean_l = None
    if active.get("mean_L"):
        mean_l = Fraction(active["mean_L"]["numer"], active["mean_L"]["denom"])
    adverse = stress(four, adverse_p, gain=gain, loss=mean_l)

    net = None
    if stop_ok and active.get("EV") and fee_scenario:
        try:
            exit_cents = None
            if active.get("mean_exit"):
                me = active["mean_exit"]
                exit_cents = int(me["numer"] // me["denom"]) if me["denom"] else None
            fee_q = estimate(
                scenario=fee_scenario,
                contracts=1,
                entry_cents=entry_cents,
                exit_cents=exit_cents if exit_cents is not None else 40,
                price_basis=str(pkg.get("price_basis")),
            )
            ev = Fraction(active["EV"]["numer"], active["EV"]["denom"])
            # Fee is ESTIMATED cents (float from schedule). Keep separate; do not
            # silently fold into the exact EV fraction as if it were observed.
            net = {
                "gross_EV": active["EV"],
                "estimated_fee_cents": fee_q["total_cents"],
                "fee_status": "ESTIMATED",
                "note": "NET ESTIMATE = research EV minus ESTIMATED fee. Not executed P&L.",
            }
        except SuperasiError as exc:
            net = exc.as_dict()

    window_agg = aggregate(windows) if windows else {"status": "UNAVAILABLE", "path_loss_n": 0}
    dist = _distribution(trades)

    decomp = {
        "package_id": pkg["package_id"],
        "decomposed_at": utc_now(),
        "code_version": CODE_VERSION,
        "semantics_version": SEMANTICS_VERSION,
        "live_execution": False,
        "settings": {
            "fill_algorithm": fill_algorithm,
            "fee_scenario": fee_scenario,
            "adverse_p": adverse_p,
            "window": "±5",
        },
        "four_cell": four,
        "gross_pre_superasi": pkg.get("analysis_gross_pre_superasi"),
        "fill_algorithms": mixes,
        "active_mix": active,
        "entry_cents": entry_cents,
        "gain_cents": gain,
        "gain_status": gain_status,
        "fees": fees,
        "net_estimate": net,
        "adverse_terminal": adverse,
        "path_windows": window_agg,
        "liquidity": {
            "taker": sum(1 for x in liq if x.get("classification") == "TAKER"),
            "maker": sum(1 for x in liq if x.get("classification") == "MAKER"),
            "unavailable": sum(1 for x in liq if x.get("classification") == "UNAVAILABLE"),
            "rows": liq[:50],
            "note": "Sample of classifications. FAST_GAP = TAKER. bid≥limit is NOT A STOP.",
        },
        "distribution": dist,
        "capital_overlay": {
            "status": "MODEL-ASSUMED",
            "bankroll_dollars": 20000,
            "allocation_pct": 5,
            "allocation_dollars": 1000,
            "note": "FIXED ALLOCATION. NOT COMPOUNDED. NOT RISK ENGINE. NOT EXECUTED P&L.",
        },
        "caveats": list(CAVEATS),
        "stop_path_status": "OK" if stop_ok else "DATA_REQUIRED",
        "question_hash": pkg.get("question_hash"),
        "dataset_version": pkg.get("dataset_version"),
        "checksums": {"trades": (pkg.get("checksums") or {}).get("trades")},
    }
    if persist:
        write_decomp(package_id, decomp, root=root)
    return decomp


def _entry_and_gain(trades: list[dict[str, Any]]) -> tuple[int, int, str]:
    """Median observed entry. G = 20 only for 80-family. Else 100−entry is hypothetical."""
    def _cents(v: Any) -> int:
        iv = int(v)
        return iv // 100 if abs(iv) >= 200 else iv

    xs = sorted(_cents(t["entry_close"]) for t in trades if t.get("entry_close") is not None)
    if not xs:
        return 80, 20, "MODEL-ASSUMED"
    entry = xs[len(xs) // 2]
    if 79 <= entry <= 83:
        return 80, 20, "OBSERVED"
    return entry, 100 - entry, "HYPOTHETICAL"


def _path_loss(t: dict[str, Any]) -> bool:
    return t.get("loss_exit") is True or t.get("T40") is True or t.get("path_true") is False


def _distribution(trades: list[dict[str, Any]]) -> dict[str, Any]:
    rets = []
    for t in trades:
        entry = t.get("entry_close")
        exit_px = t.get("exit_close")
        if entry is None or exit_px is None:
            continue
        rets.append(int(exit_px) - int(entry))
    if not rets:
        return {"status": "UNAVAILABLE", "n": 0}
    xs = sorted(rets)
    n = len(xs)
    mean = Fraction(sum(xs), n)
    # Sample SD is display-only (DERIVED). Do not invent Rf or annualize.
    sd = None
    if n > 1:
        mu = sum(xs) / n
        sd = (sum((x - mu) ** 2 for x in xs) / (n - 1)) ** 0.5
    def q(p: float) -> int:
        return xs[min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))]

    return {
        "status": "DERIVED",
        "n": n,
        "mean": {"numer": mean.numerator, "denom": mean.denominator},
        "median": xs[n // 2],
        "sample_sd": sd,
        "p5": q(5),
        "p25": q(25),
        "p50": xs[n // 2],
        "p75": q(75),
        "p95": q(95),
        "worst": xs[0],
        "best": xs[-1],
        "note": "Observed candle exit−entry cents. CANDLE PATH ≠ FILL.",
    }
