"""Build the Results analysis envelope. Does not change N or query semantics."""

from __future__ import annotations

from typing import Any

from roller.results_math.dependence import cluster_info
from roller.results_math.economics import capitalize
from roller.results_math.ev_contract import ev_contract, settlement_uses_path_rates
from roller.results_math.hurdle import economic_hurdle
from roller.results_math.inference import inference_block
from roller.results_math.last_trade_display import last_trade_analysis_overlay
from roller.results_math.results_contract import build_results_contract
from roller.results_math.models import (
    HYPOTHETICAL,
    INSUFFICIENT_PROCESS,
    MODEL_ASSUMED,
    NOT_COMPUTED,
    OBSERVED,
    UNAVAILABLE,
)
from roller.results_math.observations import e4_to_cents, normalize_rows, return_vector
from roller.results_math.payoff import (
    binary_entry_continuum,
    binary_entry_sensitivity,
    binary_trade_on_n,
    book_entry_sensitivity,
    book_payoffs,
    decompose,
    decompose_on_n,
    ev_vs_zero,
    payoff_chip_sensitivity,
    settlement_payoff,
)
from roller.results_math.power import minimum_detectable_ev
from roller.results_math.proportions import rate, wilson_interval
from roller.results_math.provenance import analysis_provenance
from roller.results_math.returns import observed_from_rows
from roller.results_math.robustness import (
    adjacent_entry_buckets,
    cost_sensitivity,
    excursion,
    holding_time_ev_buckets,
    holding_time_stats,
    season_partitions,
    temporal_partitions,
    time_to_event,
)
from roller.results_math.sequence import capitalized_equity, classification_streaks, sequence_report
from roller import desk_settings
from roller.results_math.survivability import survivability_summary
from roller.results_math.versions import CODE_VERSION, SCHEMA_VERSION, SEMANTICS_VERSION


def _entry_ref_cents(question: Any) -> int | None:
    entries = getattr(question, "entry_conditions", None) or []
    if not entries:
        return None
    e = entries[0]
    e4 = getattr(e, "price_e4", None)
    return e4_to_cents(int(e4)) if e4 is not None else None


def _book_prices(question: Any) -> tuple[int | None, int | None]:
    paths = getattr(question, "path_conditions", None) or []
    win_c = loss_c = None
    for p in paths:
        oc = getattr(p, "outcome", None)
        val = getattr(oc, "value", oc)
        price = e4_to_cents(getattr(p, "price_e4", None))
        if val in ("WIN", "win") and price is not None:
            win_c = price
        if val in ("LOSS", "loss") and price is not None:
            loss_c = price
    return win_c, loss_c


def _exit_definition(question: Any) -> str:
    paths = getattr(question, "path_conditions", None) or []
    bits = []
    for p in paths:
        oc = getattr(getattr(p, "outcome", None), "value", getattr(p, "outcome", None))
        op = getattr(getattr(p, "op", None), "value", getattr(p, "op", None))
        bits.append(f"{oc or 'path'}:{op}:{getattr(p, 'price_e4', None)}")
    return " · ".join(bits) or "unspecified"


def exclusion_ledger(
    *,
    identity: dict[str, Any] | None,
    funnel: list[dict[str, Any]] | None,
    n: int,
    n_missing_exit: int,
    terminal_missing: int,
) -> dict[str, Any]:
    ident = identity or {}
    universe = ident.get("universe_tickers")
    if universe is None and funnel:
        universe = (funnel[0] or {}).get("n")
    exclusions = dict(ident.get("exclusions") or {})
    return {
        "status": OBSERVED,
        "universe": universe,
        "qualifying_entry": n,
        "exclusions": exclusions,
        "missing_exit": n_missing_exit,
        "terminal_missing": terminal_missing,
        "note": "Every rate states its own denominator. Missing is not zero.",
        "funnel": funnel or [],
    }


def _declared_exposure_result(identity: dict[str, Any] | None) -> dict[str, Any] | None:
    """Pass execution-declared exposure to Results verify. Does not rewrite N."""
    if not identity:
        return None
    if not identity.get("exposure_unit") and not identity.get("exposure"):
        return None
    return {"identity": identity, "exposure": identity.get("exposure")}


def analyze_result(
    rows: list[dict[str, Any]] | None,
    *,
    question: Any = None,
    funnel: list[dict[str, Any]] | None = None,
    hashes: dict[str, Any] | None = None,
    dataset_version: str | None = None,
    last_trade: bool = False,
    metrics: dict[str, Any] | None = None,
    identity: dict[str, Any] | None = None,
    bankroll_cents: int | None = None,
    allocation_cents: int | None = None,
) -> dict[str, Any]:
    desk = desk_settings.load_desk_settings()
    if bankroll_cents is None:
        bankroll_cents = int(desk["bankroll_cents"])
    if allocation_cents is None:
        allocation_cents = (int(bankroll_cents) * int(desk["allocation_bps"])) // 10_000
    obs = normalize_rows(rows)
    n = len(obs)
    entry_ref = _entry_ref_cents(question)
    win_px, loss_px = _book_prices(question)

    if last_trade:
        mets = metrics or {}
        win_n = int(mets.get("win_exit") or 0)
        loss_n = int(mets.get("loss_exit") or 0)
        path_true = int(mets.get("path_true") or 0)
        wins = win_n if (win_n or loss_n) else path_true
        trade = binary_trade_on_n(win_n=wins if n else None, n=n if n else None, entry_cents=entry_ref)
        book_out = None
        if win_px is not None and loss_px is not None and n and entry_ref is not None:
            wp, lp = book_payoffs(entry_ref, win_px, loss_px)
            book_out = decompose_on_n(
                win_n=wins,
                loss_n=loss_n,
                n=n,
                win_payoff_cents=wp,
                loss_payoff_cents=lp,
            )
        overlay = last_trade_analysis_overlay(rows, metrics, identity)
        overlay["trade_breakeven"] = trade
        if book_out is not None:
            overlay["book_price"] = book_out
            overlay["hypothetical_payoff"] = book_out
        contract = build_results_contract(
            last_trade=True,
            observation_basis="LAST_TRADE_PRINT",
            metrics=metrics,
            identity=identity,
            rows=rows,
            question=question,
            n=n,
            result=_declared_exposure_result(identity),
            book_price=book_out,
            trade_breakeven=trade,
        )
        return {
            "semantics_version": SEMANTICS_VERSION,
            "schema_version": SCHEMA_VERSION,
            "code_version": CODE_VERSION,
            "results_math_semantics_version": SEMANTICS_VERSION,
            "results_math_schema_version": SCHEMA_VERSION,
            "results_math_code_version": CODE_VERSION,
            "version": SEMANTICS_VERSION,
            "observed_returns": {
                "status": UNAVAILABLE,
                "reason": "LAST TRADE ≠ EXECUTABLE PRICE. No P&L / EV / Sharpe on this basis.",
            },
            "observed_path": {
                "status": UNAVAILABLE,
                "reason": "LAST TRADE ≠ EXECUTABLE PRICE. No P&L / EV / Sharpe on this basis.",
            },
            "risk_of_ruin": {
                "status": NOT_COMPUTED,
                "reason": "No explicit stochastic bankroll model. LAST TRADE ≠ FILL.",
            },
            "provenance": analysis_provenance(
                hashes=hashes,
                dataset_version=dataset_version,
                entry_definition="last_trade_close",
                exit_definition=_exit_definition(question),
                last_trade=True,
                assumptions={},
            ),
            "ev_contract": ev_contract(),
            "results_contract": contract,
            **overlay,
        }

    dist = observed_from_rows(obs)
    xs = [float(r["return_cents"]) for r in obs if r.get("return_cents") is not None]
    clusters = cluster_info(obs)

    win_n = int((metrics or {}).get("win_exit") or 0)
    loss_n = int((metrics or {}).get("loss_exit") or 0)
    if not win_n and not loss_n:
        win_n = sum(1 for r in obs if r.get("exit_outcome") == "WIN_EXIT" or r.get("path_true") is True)
        loss_n = sum(1 for r in obs if r.get("exit_outcome") == "LOSS_EXIT" or r.get("path_true") is False)
    classified = win_n + loss_n
    path_true = int((metrics or {}).get("path_true") or 0)
    path_avail = int((metrics or {}).get("path_available") or n)
    yes_n = (metrics or {}).get("terminal_yes")
    term_avail = int((metrics or {}).get("terminal_available") or 0)
    _raw_missing = (metrics or {}).get("terminal_missing")
    term_missing = n if _raw_missing is None else int(_raw_missing)
    no_n = (term_avail - int(yes_n)) if yes_n is not None and term_avail else None
    if term_avail == 0:
        yes_n = None
        no_n = None

    empirical = {
        "n": n,
        "successes": win_n if classified else path_true,
        "failures": loss_n if classified else (path_avail - path_true),
        "denominator": classified or path_avail,
        "rate": rate(win_n if classified else path_true, classified or path_avail),
        "wilson": wilson_interval(win_n if classified else path_true, classified or path_avail),
        "win_exit": win_n,
        "loss_exit": loss_n,
        "path_true": path_true,
        "path_available": path_avail,
    }

    book = None
    if entry_ref is not None and win_px is not None and loss_px is not None and classified:
        rw, rl = book_payoffs(entry_ref, win_px, loss_px)
        book = decompose(win_n=win_n, loss_n=loss_n, win_payoff_cents=rw, loss_payoff_cents=rl)
        book["entry_ref_cents"] = entry_ref
        book["win_price_cents"] = win_px
        book["loss_price_cents"] = loss_px
        book["formula"] = "P(WIN)×(WIN_price − entry) + P(LOSS)×(LOSS_price − entry)"

    settle = settlement_payoff(
        yes_n=int(yes_n) if yes_n is not None and term_avail else None,
        no_n=int(no_n) if no_n is not None and term_avail else None,
        missing=term_missing,
        entry_cents=entry_ref or 0,
    )
    settle["formula"] = "P(YES)×(100¢ − entry) + P(NO)×(0¢ − entry)"

    ev_ci = dist.get("ev_ci") if dist.get("status") == OBSERVED else None
    significance = ev_vs_zero(ev_ci, dist.get("mean_cents") if dist.get("status") == OBSERVED else None)

    mean_close = None
    closes_i = [c for c in (e4_to_cents(r.get("entry_price_e4")) for r in obs) if c is not None]
    if closes_i:
        mean_close = sum(closes_i) / len(closes_i)

    capital = capitalize(
        observed_sum_cents=dist.get("sum_cents") if dist.get("status") == OBSERVED else None,
        observed_n=int(dist.get("n") or 0),
        observed_mean_cents=dist.get("mean_cents") if dist.get("status") == OBSERVED else None,
        observed_std_cents=dist.get("std_cents") if dist.get("status") == OBSERVED else None,
        observed_ci=ev_ci,
        max_dd_cents=None,
        book_ev_cents=(book or {}).get("ev_cents"),
        settlement_ev_cents=settle.get("ev_cents") if settle.get("status") != UNAVAILABLE else None,
        book_ci=(book or {}).get("wilson_ev_ci") if book else None,
        entry_cents=entry_ref,
        bankroll_cents=bankroll_cents,
        allocation_cents=allocation_cents,
        quantiles_cents=dist.get("quantiles") if dist.get("status") == OBSERVED else None,
        returns_cents=xs,
        mean_observed_entry_cents=mean_close,
    )

    chrono = dist.get("chronological_returns") or []
    seq = sequence_report(chrono)
    dd_cents = (seq.get("drawdown") or {}).get("max_drawdown_cents")
    if capital.get("observed") and dd_cents is not None:
        contracts = (capital.get("sizing") or {}).get("contracts")
        if contracts:
            capital["observed"]["max_dd_allocation_cents"] = dd_cents * contracts
            capital["observed"]["max_dd_allocation_dollars"] = (dd_cents * contracts) / 100.0
            alloc = (capital.get("sizing") or {}).get("allocation_cents") or 1
            capital["observed"]["max_dd_pct_allocation"] = (dd_cents * contracts) / alloc
            bank = (capital.get("sizing") or {}).get("bankroll_cents") or bankroll_cents
            capital["observed"]["max_dd_pct_bankroll"] = (dd_cents * contracts) / bank

    contracts = (capital.get("sizing") or {}).get("contracts") or 0
    equity = capitalized_equity(
        chrono,
        contracts=int(contracts),
        bankroll_cents=bankroll_cents,
        allocation_cents=allocation_cents,
    )

    hold_s = [int(r["holding_seconds"]) for r in obs if r.get("holding_seconds") is not None]
    hold = holding_time_stats(hold_s)
    win_hold = holding_time_stats(
        [
            int(r["holding_seconds"])
            for r in obs
            if r.get("holding_seconds") is not None and r.get("exit_outcome") == "WIN_EXIT"
        ]
    )
    loss_hold = holding_time_stats(
        [
            int(r["holding_seconds"])
            for r in obs
            if r.get("holding_seconds") is not None and r.get("exit_outcome") == "LOSS_EXIT"
        ]
    )
    exc = excursion(obs)

    p_win = (empirical.get("rate") or {}).get("p_hat")
    binary_sens = binary_entry_sensitivity(p_win)
    book_sens = book_entry_sensitivity(p_win, win_px, loss_px)
    entry_continuum = binary_entry_continuum(p_win)
    chip_grid = payoff_chip_sensitivity(p_win) if classified else {
        "status": UNAVAILABLE,
        "reason": "No explicit WIN/LOSS payoff classification.",
    }
    hold_ev = holding_time_ev_buckets(obs)
    class_streaks = classification_streaks(
        [
            True if r.get("exit_outcome") == "WIN_EXIT" or r.get("path_true") is True else
            False if r.get("exit_outcome") == "LOSS_EXIT" or r.get("path_true") is False else None
            for r in obs
        ]
    )

    if settlement_uses_path_rates(settle, path_true, path_avail):
        raise RuntimeError("EV contract violation: settlement EV substituted path rates.")

    uncertainty = inference_block(
        successes=empirical["successes"],
        n=empirical["denominator"],
        returns=xs,
        groups=clusters.get("return_groups"),
        date_groups=clusters.get("date_return_groups"),
        ev_ci=ev_ci,
    )
    boot = uncertainty.get("bootstrap") or {}
    if equity.get("status") != UNAVAILABLE and contracts:
        end_ci = boot.get("ending_pnl_cents") or {}
        dd_ci = boot.get("max_drawdown_cents") or {}
        min_ci = boot.get("min_cumulative_cents") or {}
        streak_ci = boot.get("longest_loss_streak") or {}

        def _cap(v: Any) -> float | None:
            if v is None:
                return None
            return bankroll_cents + float(v) * int(contracts)

        def _dd(v: Any) -> float | None:
            if v is None:
                return None
            return float(v) * int(contracts)

        equity["bootstrap"] = {
            "status": boot.get("status"),
            "label": "HISTORICAL-DISTRIBUTION RESAMPLE · not a forecast of future account performance",
            "ending_capital_cents": {
                "observed": equity.get("ending_bankroll_cents"),
                "median": _cap(end_ci.get("median")),
                "p5": _cap(end_ci.get("lower")),
                "p95": _cap(end_ci.get("upper")),
            },
            "min_capital_cents": {
                "median": _cap(min_ci.get("median")),
                "p5": _cap(min_ci.get("lower")),
                "p95": _cap(min_ci.get("upper")),
            },
            "max_drawdown_cents": {
                "observed": equity.get("max_drawdown_cents"),
                "median": _dd(dd_ci.get("median")),
                "p5": _dd(dd_ci.get("lower")),
                "p95": _dd(dd_ci.get("p95") if dd_ci.get("p95") is not None else dd_ci.get("upper")),
            },
            "longest_loss_streak": streak_ci,
        }

    assumptions = {
        "allocation": "FIXED $1,000 default · 5% of $20,000 · not compounding · not Risk engine",
        "entry_reference_cents": entry_ref,
        "mean_actual_entry_cents": mean_close,
        "payoff": "book chips if tagged; settlement only when measured",
        "fees": "UNAVAILABLE on rows · cost grid is hypothetical overlay",
        "sizing_price_cents": entry_ref,
    }
    hurdle = economic_hurdle(dist.get("mean_cents") if dist.get("status") == OBSERVED else None)
    power = minimum_detectable_ev(
        n=int(dist.get("n") or 0),
        sample_std_cents=dist.get("std_cents") if dist.get("status") == OBSERVED else None,
    )
    survive = survivability_summary(
        observed_ev_cents=dist.get("mean_cents") if dist.get("status") == OBSERVED else None,
        observed_ci=ev_ci,
        book_ev_cents=(book or {}).get("ev_cents") if book else None,
        book_wilson_ev_ci=(book or {}).get("wilson_ev_ci") if book else None,
        break_even_cost_cents=hurdle.get("break_even_total_cost_cents"),
        capitalized_ev_dollars=(capital.get("observed") or {}).get("expected_allocation_dollars"),
        capitalized_ci=(capital.get("observed") or {}).get("ev_ci_dollars"),
        sharpe=dist.get("observed_path_sharpe") if dist.get("status") == OBSERVED else None,
        sharpe_ci=boot.get("sharpe") if boot.get("status") != UNAVAILABLE else None,
        max_dd_dollars=(capital.get("observed") or {}).get("max_dd_allocation_dollars"),
        terminal_status=settle.get("status"),
        observed_win=p_win if classified else None,
        book_win=win_px,
        book_loss=loss_px,
    )
    dep = {k: v for k, v in clusters.items() if k not in ("return_groups", "date_return_groups")}
    book_out = book or {
        "status": UNAVAILABLE,
        "reason": "No explicit WIN/LOSS payoff. Tagged WIN/LOSS chip prices required for book-price EV.",
    }
    observed_path = {
        **dist,
        "vector": return_vector(obs),
        "inference": significance,
        "formula": "E[exit_close − entry_close]",
    }
    return {
        "semantics_version": SEMANTICS_VERSION,
        "schema_version": SCHEMA_VERSION,
        "code_version": CODE_VERSION,
        "results_math_semantics_version": SEMANTICS_VERSION,
        "results_math_schema_version": SCHEMA_VERSION,
        "results_math_code_version": CODE_VERSION,
        "version": SEMANTICS_VERSION,
        "empirical": empirical,
        "observed_returns": dist,
        "observed_path": observed_path,
        "ev_contract": ev_contract(),
        "observed_ev": {
            "status": OBSERVED if dist.get("status") == OBSERVED else UNAVAILABLE,
            "label": "OBSERVED PATH EV / CONTRACT",
            "formula": "E[exit_close − entry_close]",
            "estimate_cents": dist.get("mean_cents") if dist.get("status") == OBSERVED else None,
            "ci95": ev_ci,
            "method": "student_t",
            "n": dist.get("n"),
            "significance": significance,
        },
        "book_price": book_out,
        "hypothetical_payoff": book_out,
        "settlement": settle,
        "settlement_payoff": settle,
        "allocation": capital,
        "capitalization": capital,
        "mean_actual_entry_cents": mean_close,
        "excursion": exc,
        "holding_time": {"overall": hold, "win": win_hold, "loss": loss_hold, "ev_buckets": hold_ev},
        "time_to_event": time_to_event(hold_s, n),
        "sequence": {**seq, "classification_streaks": class_streaks},
        "drawdown": {
            "price_path": seq.get("drawdown"),
            "fixed_allocation": {
                "status": equity.get("status"),
                "max_drawdown_cents": equity.get("max_drawdown_cents"),
                "max_drawdown_dollars": (equity.get("max_drawdown_cents") or 0) / 100.0
                if equity.get("max_drawdown_cents") is not None
                else None,
            },
            "bankroll_share": equity.get("max_drawdown_pct_bankroll"),
        },
        "equity": equity,
        "bootstrap": boot,
        "uncertainty": uncertainty,
        "clusters": {
            "observation": uncertainty.get("observation_ci"),
            "game": boot.get("game_cluster"),
            "date": boot.get("date_cluster"),
            "dependence": dep,
        },
        "dependence": dep,
        "economic_hurdle": hurdle,
        "robustness": {
            "cost_sensitivity": cost_sensitivity(dist.get("mean_cents") if dist.get("status") == OBSERVED else None),
            "binary_entry_sensitivity": binary_sens,
            "binary_entry_continuum": entry_continuum,
            "book_entry_sensitivity": book_sens,
            "payoff_chip_sensitivity": chip_grid,
            "adjacent_entry_buckets": adjacent_entry_buckets(obs),
            "season_partitions": season_partitions(obs),
            "temporal_partitions": temporal_partitions(obs),
            "holding_time_ev": hold_ev,
            "wilson_ev_ci": (book or {}).get("wilson_ev_ci") if book else None,
            "exact_binomial_ev_ci": (book or {}).get("exact_binomial_ev_ci") if book else None,
        },
        "diagnostics": {
            "power": power,
            "survivability": survive,
            "slippage": {"status": UNAVAILABLE, "reason": "not measured"},
            "fill_impact": {"status": UNAVAILABLE, "reason": "not measured · CANDLE PATH ≠ FILL"},
        },
        "risk_of_ruin": {
            "status": NOT_COMPUTED,
            "reason": "No explicit stochastic bankroll model (sizing, dependence, stopping, compounding). $50 snapshot is not used.",
            "process": INSUFFICIENT_PROCESS,
        },
        "exclusion_ledger": exclusion_ledger(
            identity=identity,
            funnel=funnel,
            n=n,
            n_missing_exit=int(dist.get("n_missing_exit") or 0),
            terminal_missing=term_missing,
        ),
        "data_quality": {
            "n": n,
            "valid_returns": dist.get("n"),
            "missing_exit": dist.get("n_missing_exit"),
            "terminal_coverage": term_avail,
            "terminal_missing": term_missing,
            "holding_time_n": len(hold_s),
            "mae_n": (exc.get("mae") or {}).get("n") if exc.get("status") == OBSERVED else 0,
            "price_basis": "tradable_yes_bid_close",
        },
        "provenance": analysis_provenance(
            hashes=hashes,
            dataset_version=dataset_version,
            entry_definition=f"entry_ref={entry_ref}¢",
            exit_definition=_exit_definition(question),
            last_trade=False,
            assumptions=assumptions,
        ),
        "labels": {
            "observed_path_ev": OBSERVED,
            "book_payoff_ev": HYPOTHETICAL,
            "settlement_ev": settle.get("status"),
            "capital": MODEL_ASSUMED,
        },
        "results_contract": build_results_contract(
            last_trade=False,
            observation_basis="TRADABLE_YES_BID",
            metrics=metrics,
            identity=identity,
            rows=rows,
            question=question,
            n=n,
            result=_declared_exposure_result(identity),
            observed_returns=dist,
            settlement=settle,
            book_price=book_out,
            capitalization=capital,
            hurdle=hurdle,
        ),
    }
