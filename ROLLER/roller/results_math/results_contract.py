"""Universal basis-aware Results contract.

Authority lives here. Sport name is never a branch. Observation basis selects
economic mode. Quantities that cannot be measured fail closed.

LAST TRADE ≠ YES BID. LAST TRADE ≠ FILL. CANDLE PATH ≠ FILL.
PATH FALSE ≠ LOSS. PATH WIN ≠ TERMINAL YES. Missing is not NO.
"""

from __future__ import annotations

from typing import Any

from roller.results_math.exposure import verify_exposure
from roller.results_math.payoff import binary_trade_on_n, book_payoffs, decompose_on_n
from roller.results_math.models import (
    CARDINALITY_VIOLATION,
    DATA_REQUIRED,
    HYPOTHETICAL,
    INCOMPLETE,
    NOT_APPLICABLE,
    OBSERVED,
    UNAVAILABLE,
)

CONTRACT_VERSION = "1.0.0"

MODE_LAST_TRADE = "LAST_TRADE_PRINT"
MODE_TRADABLE = "TRADABLE_YES_BID"
MODE_UNKNOWN = "UNKNOWN"

LAST_TRADE_UNAVAILABLE = "LAST TRADE ≠ EXECUTABLE PRICE"
CANDLE_NOT_FILL = "CANDLE PATH ≠ FILL"
HOLD_VALID = "HOLD_TO_EXPIRATION · exit_close is None by definition · not missing candle data"
PRINT_DIAGNOSTIC = "LOSS-EXIT PRINT DISPLACEMENT"
MODEL_A_FORMULA = "EV_cents = 20 - 60q = 20*(1-3q); q = P(hit 40)"

RATE_LABELS = {
    "path_rate": "PATH RATE · path_true / N",
    "win_on_n": "BACKTEST WIN · WIN_EXIT / N",
    "loss_on_n": "BACKTEST LOSS · LOSS_EXIT / N",
    "classified_win": "CLASSIFIED EXIT WIN · WIN / (WIN+LOSS)",
    "classified_loss": "CLASSIFIED EXIT LOSS · LOSS / (WIN+LOSS)",
    "terminal_yes": "TERMINAL YES · CONDITIONAL ON OBSERVED KALSHI SETTLEMENT",
    "path_false": "PATH FALSE · not LOSS_EXIT",
    "coverage": "SETTLEMENT COVERAGE · settled / N",
    "missing": "TERMINAL MISSING · missing / N",
}


def _meas(result: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
    if not result:
        return None
    for m in result.get("measurements") or []:
        if m.get("name") == name:
            return m
    return None


def _count(m: dict[str, Any] | None, key: str) -> int | None:
    if not m:
        return None
    d = m.get("detail") or {}
    v = d.get(key)
    return int(v) if isinstance(v, (int, float)) else None


def _int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _status(status: str, reason: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"status": status, "reason": reason}
    out.update(extra)
    return out


def observation_basis_of(result: dict[str, Any] | None) -> str | None:
    if not result:
        return None
    basis = result.get("observation_basis")
    if basis:
        return str(basis)
    compile_b = (result.get("compile") or {}).get("observation_basis")
    if compile_b:
        return str(compile_b)
    mlb = result.get("mlb") or {}
    if mlb.get("observation_basis"):
        return str(mlb["observation_basis"])
    return None


def is_last_trade_print(result: dict[str, Any] | None) -> bool:
    return economic_mode(result=result) == MODE_LAST_TRADE


def economic_mode(
    *,
    last_trade: bool = False,
    observation_basis: str | None = None,
    result: dict[str, Any] | None = None,
) -> str:
    """Mode from observation basis only. Sport is irrelevant."""
    if last_trade:
        return MODE_LAST_TRADE
    basis = observation_basis or observation_basis_of(result)
    if basis and "LAST_TRADE" in str(basis):
        return MODE_LAST_TRADE
    if result:
        prov = result.get("provenance") or {}
        if str(prov.get("price_basis") or "").find("LAST_TRADE") >= 0:
            return MODE_LAST_TRADE
        if str(prov.get("market_data_type") or "").find("LAST_TRADE") >= 0:
            return MODE_LAST_TRADE
        if str(prov.get("market_data") or "").find("last_trade") >= 0:
            return MODE_LAST_TRADE
        observed = (result.get("analysis") or {}).get("observed_returns") or {}
        if "LAST TRADE" in str(observed.get("reason") or ""):
            return MODE_LAST_TRADE
    if basis and ("TRADABLE" in str(basis) or "YES_BID" in str(basis)):
        return MODE_TRADABLE
    if result is None and not last_trade and observation_basis is None:
        return MODE_TRADABLE
    if result is not None and not last_trade and not basis:
        return MODE_TRADABLE
    if not last_trade and observation_basis is None and result is None:
        return MODE_TRADABLE
    return MODE_UNKNOWN


def is_exact_model_a_8040(question: Any = None, result: dict[str, Any] | None = None) -> bool:
    """Exact 80¢ entry / 40¢ LOSS REACH. Not a family of nearby prices."""
    q = question
    if q is None and result is not None:
        q = (result.get("compile") or {}).get("question")
    if q is None:
        return False
    if isinstance(q, dict):
        entries = q.get("entry_conditions") or []
        paths = q.get("path_conditions") or []
        if len(entries) != 1 or not paths:
            return False
        if _int(entries[0].get("price_e4")) != 8000:
            return False
        return any(
            str(p.get("op") or "").upper() == "REACH" and _int(p.get("price_e4")) == 4000 for p in paths
        )
    entries = getattr(q, "entry_conditions", None) or []
    paths = getattr(q, "path_conditions", None) or []
    if len(entries) != 1 or not paths:
        return False
    if getattr(entries[0], "price_e4", None) != 8000:
        return False
    return any(
        str(getattr(getattr(p, "op", None), "value", getattr(p, "op", None)) or "").upper() == "REACH"
        and getattr(p, "price_e4", None) == 4000
        for p in paths
    )


def collect_rate_counts(
    result: dict[str, Any] | None = None,
    *,
    metrics: dict[str, Any] | None = None,
    identity: dict[str, Any] | None = None,
    n: int | None = None,
) -> dict[str, Any]:
    ident = identity or ((result or {}).get("identity") or {})
    mets = metrics or {}
    if n is None:
        n = (result or {}).get("summary", {}).get("population_n") if result else None
        if n is None and result:
            n = ident.get("reported_n")
        if n is None and result:
            n = (result.get("population") or {}).get("count")
    n = _int(n)
    entry = ident.get("n_entry_events") or ident.get("entry_eligible")
    te = ident.get("te_scope") or {}
    if entry is None:
        entry = te.get("n_entry")
    path = _meas(result, "path_rate") if result else None
    win = _meas(result, "win_exit_rate") if result else None
    loss = _meas(result, "loss_exit_rate") if result else None
    yes_m = (_meas(result, "kalshi_yes_rate") or _meas(result, "terminal_yes_rate")) if result else None
    path_true = mets.get("path_true")
    if path_true is None:
        path_true = _count(path, "count_true") if path else ident.get("path_true")
    path_avail = mets.get("path_available")
    if path_avail is None:
        path_avail = _count(path, "count_available") if path else n
    win_n = mets.get("win_exit")
    if win_n is None:
        win_n = _count(win, "count_true")
    classified = None
    if win is not None:
        classified = _count(win, "count_available")
    loss_n = mets.get("loss_exit")
    if loss_n is None:
        loss_n = _count(loss, "count_true")
    if classified is None and win_n is not None and loss_n is not None:
        classified = int(win_n) + int(loss_n)
    yes = ident.get("terminal_yes")
    no = ident.get("terminal_no")
    missing = ident.get("terminal_missing")
    if yes is None:
        yes = mets.get("terminal_yes")
    if missing is None:
        missing = mets.get("terminal_missing")
    if yes is None and yes_m:
        yes = _count(yes_m, "count_true")
    if no is None and mets.get("terminal_available") is not None and yes is not None:
        no = int(mets["terminal_available"]) - int(yes)
    settled = None
    if yes is not None and no is not None:
        settled = int(yes) + int(no)
    elif yes_m:
        settled = _count(yes_m, "count_available")
    elif mets.get("terminal_available") is not None:
        settled = _int(mets.get("terminal_available"))
    path_false = ident.get("path_false")
    if path_false is None and mets.get("path_false") is not None:
        path_false = mets.get("path_false")
    if path_false is None and path_true is not None and path_avail is not None:
        path_false = int(path_avail) - int(path_true)
    unclassified = None
    if n is not None and classified is not None and int(n) - int(classified) >= 0:
        unclassified = int(n) - int(classified)
    return {
        "n": n,
        "n_entry": _int(entry),
        "path_true": _int(path_true),
        "path_false": _int(path_false),
        "path_available": _int(path_avail),
        "win_exit": _int(win_n),
        "loss_exit": _int(loss_n),
        "classified": _int(classified),
        "unclassified": unclassified,
        "terminal_yes": _int(yes),
        "terminal_no": _int(no),
        "terminal_missing": _int(missing),
        "settled": _int(settled),
        "labels": dict(RATE_LABELS),
    }


def _rate(num: int | None, den: int | None, label: str) -> dict[str, Any]:
    if num is None or den is None:
        return _status(DATA_REQUIRED, "Numerator or denominator not measured.", label=label)
    if den <= 0:
        return _status(UNAVAILABLE, "Denominator is zero.", label=label, numerator=num, denominator=den)
    return {
        "status": OBSERVED,
        "label": label,
        "numerator": int(num),
        "denominator": int(den),
        "value": int(num) / int(den),
    }


def print_displacement(rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Observational LOSS-exit print travel. Must not feed EV / Sharpe / capital."""
    trades = rows or []
    xs: list[float] = []
    win_hold = 0
    win_with_exit = 0
    loss_with_exit = 0
    for row in trades:
        win = row.get("win_exit") is True
        loss = row.get("loss_exit") is True
        exit_e4 = row.get("exit_close")
        entry_e4 = row.get("entry_close")
        if entry_e4 is None:
            entry_e4 = row.get("entry_price_e4")
        if win and exit_e4 is None:
            win_hold += 1
        if win and exit_e4 is not None:
            win_with_exit += 1
        if loss and exit_e4 is not None:
            loss_with_exit += 1
            if entry_e4 is not None:
                xs.append((int(exit_e4) - int(entry_e4)) / 100.0)
    if not xs:
        return {
            "status": UNAVAILABLE,
            "label": PRINT_DIAGNOSTIC,
            "n": 0,
            "feeds_population_ev": False,
            "feeds_capitalization": False,
            "feeds_sharpe": False,
            "win_hold_no_exit": win_hold,
            "reason": "No LOSS-exit print closes to inspect.",
        }
    return {
        "status": OBSERVED,
        "label": PRINT_DIAGNOSTIC,
        "n": len(xs),
        "mean_cents": sum(xs) / len(xs),
        "subset": "LOSS_EXIT_ONLY",
        "feeds_population_ev": False,
        "feeds_capitalization": False,
        "feeds_sharpe": False,
        "win_hold_no_exit": win_hold,
        "win_with_exit": win_with_exit,
        "loss_with_exit": loss_with_exit,
        "hold_note": HOLD_VALID,
        "reason": (
            "LAST-TRADE PRINT SUBSET · NOT POPULATION EV · NOT FILL P&L · NOT SETTLEMENT EV. "
            + LAST_TRADE_UNAVAILABLE
        ),
    }


def _hold_block() -> dict[str, Any]:
    return {
        "win_hold_to_expiration_valid": True,
        "exit_close_null_is_valid_for_win_hold": True,
        "unclassified_is_not_loss": True,
        "path_false_is_not_loss": True,
        "note": HOLD_VALID,
    }


def _entry_cents(question: Any) -> int | None:
    if question is None:
        return None
    if isinstance(question, dict):
        entries = question.get("entry_conditions") or []
        if not entries:
            return None
        first = entries[0] if isinstance(entries[0], dict) else None
        e4 = first.get("price_e4") if first else None
        return int(e4) // 100 if e4 is not None else None
    entries = getattr(question, "entry_conditions", None) or []
    if not entries:
        return None
    first = entries[0]
    e4 = first.get("price_e4") if isinstance(first, dict) else getattr(first, "price_e4", None)
    return int(e4) // 100 if e4 is not None else None


def _book_chip_prices(question: Any) -> tuple[int | None, int | None]:
    if question is None:
        return None, None
    paths = question.get("path_conditions") if isinstance(question, dict) else getattr(question, "path_conditions", None)
    paths = paths or []
    win_c = loss_c = None
    for p in paths:
        if isinstance(p, dict):
            oc = p.get("outcome")
            val = oc.get("value") if isinstance(oc, dict) else oc
            e4 = p.get("price_e4")
        else:
            oc = getattr(p, "outcome", None)
            val = getattr(oc, "value", oc)
            e4 = getattr(p, "price_e4", None)
        if e4 is None:
            continue
        cents = int(e4) // 100
        token = str(val or "").upper()
        if token in ("WIN",):
            win_c = cents
        if token in ("LOSS",):
            loss_c = cents
    return win_c, loss_c


def _same_n_wins(rates: dict[str, Any]) -> int | None:
    win_n = rates.get("win_exit")
    loss_n = rates.get("loss_exit")
    if win_n or loss_n:
        return int(win_n or 0)
    path_true = rates.get("path_true")
    return int(path_true) if path_true is not None else None


def _last_trade_economics(
    *,
    rates: dict[str, Any],
    rows: list[dict[str, Any]] | None,
    settlement: dict[str, Any] | None,
    question: Any = None,
    book_price: dict[str, Any] | None = None,
    trade_breakeven: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reason = f"{LAST_TRADE_UNAVAILABLE}. No P&L / EV / Sharpe on this basis."
    missing = rates.get("terminal_missing")
    yes = rates.get("terminal_yes")
    no = rates.get("terminal_no")
    if missing is not None and int(missing) > 0:
        settle_status = INCOMPLETE
        settle_reason = "TERMINAL DATA INCOMPLETE · missing is not NO · PATH WIN ≠ SETTLEMENT YES"
    elif yes is None or no is None:
        settle_status = DATA_REQUIRED
        settle_reason = "Authoritative Kalshi settlement required."
    else:
        settle_status = (settlement or {}).get("status") or OBSERVED
        settle_reason = "Settled population is complete."
    unavailable = _status(UNAVAILABLE, reason)
    if trade_breakeven is None:
        trade_breakeven = binary_trade_on_n(
            win_n=_same_n_wins(rates),
            n=rates.get("n"),
            entry_cents=_entry_cents(question),
        )
    if book_price is None:
        win_px, loss_px = _book_chip_prices(question)
        entry = _entry_cents(question)
        n = rates.get("n")
        if win_px is not None and loss_px is not None and entry is not None and n:
            wp, lp = book_payoffs(entry, win_px, loss_px)
            book_price = decompose_on_n(
                win_n=int(_same_n_wins(rates) or 0),
                loss_n=int(rates.get("loss_exit") or 0),
                n=int(n),
                win_payoff_cents=wp,
                loss_payoff_cents=lp,
            )
    if trade_breakeven and trade_breakeven.get("breakeven_probability") is not None:
        brk = {
            "status": HYPOTHETICAL,
            "label": "BREAKEVEN BEFORE FEES",
            "estimate": trade_breakeven.get("breakeven_probability"),
            "p_win": trade_breakeven.get("p_win"),
            "rate_margin_vs_breakeven": trade_breakeven.get("rate_margin_vs_breakeven"),
            "estimate_cents": trade_breakeven.get("ev_cents"),
            "entry_cents": trade_breakeven.get("entry_cents"),
            "n": trade_breakeven.get("n"),
            "formula": trade_breakeven.get("formula"),
            "reason": (
                "Binary 100/0 before fees. BE = entry/100. EV = 100·P(win) − entry. "
                "Non-win treated as 0 settlement. LAST TRADE ≠ FILL. Fees are not subtracted."
            ),
        }
    else:
        brk = _status(UNAVAILABLE, "Need wins, N, and an entry chip for pre-fee breakeven.")
    if book_price and book_price.get("status") in (HYPOTHETICAL, OBSERVED) and book_price.get("ev_cents") is not None:
        book = {
            "status": HYPOTHETICAL,
            "estimate_cents": book_price.get("ev_cents"),
            "breakeven_probability": book_price.get("breakeven_probability"),
            "rate_margin_vs_breakeven": book_price.get("rate_margin_vs_breakeven"),
            "win_probability": book_price.get("win_probability"),
            "loss_probability": book_price.get("loss_probability"),
            "win_payoff_cents": book_price.get("win_payoff_cents"),
            "loss_payoff_cents": book_price.get("loss_payoff_cents"),
            "n": book_price.get("n"),
            "reason": (
                "Tagged WIN/LOSS chip payoffs × rates on the same N. Residual payoff 0. "
                "Not a fill. LAST TRADE ≠ FILL."
            ),
        }
    else:
        book = _status(
            UNAVAILABLE,
            "Tagged WIN and LOSS path prices required. Binary breakeven before fees is separate.",
        )
    return {
        "observed_path_ev": unavailable,
        "strategy_pnl": unavailable,
        "sharpe": unavailable,
        "sortino": unavailable,
        "break_even_edge": brk,
        "trade_breakeven": trade_breakeven,
        "capitalization": unavailable,
        "risk_of_ruin": _status(UNAVAILABLE, "No explicit stochastic bankroll model. LAST TRADE ≠ FILL."),
        "book_price_ev": book,
        "model_a_8040_ev": _status(
            NOT_APPLICABLE,
            "Model A is an exact 80/40 subtype and is not defined on LAST_TRADE_PRINT.",
        ),
        "fill_adjusted_ev": _status(UNAVAILABLE, "LAST TRADE ≠ FILL. Execution data required."),
        "settlement_ev": _status(
            settle_status,
            settle_reason,
            terminal_yes=yes,
            terminal_no=no,
            terminal_missing=missing,
            settled=rates.get("settled"),
            n=rates.get("n"),
        ),
        "print_displacement": print_displacement(rows),
    }


def _tradable_economics(
    *,
    rates: dict[str, Any],
    question: Any,
    result: dict[str, Any] | None,
    observed_returns: dict[str, Any] | None,
    settlement: dict[str, Any] | None,
    book_price: dict[str, Any] | None,
    capitalization: dict[str, Any] | None,
    hurdle: dict[str, Any] | None,
) -> dict[str, Any]:
    dist = observed_returns or {}
    analysis = (result or {}).get("analysis") or {}
    if not dist:
        dist = analysis.get("observed_returns") or analysis.get("observed_path") or {}
    if settlement is None:
        settlement = analysis.get("settlement_payoff") or analysis.get("settlement")
    if book_price is None:
        book_price = analysis.get("book_price") or analysis.get("hypothetical_payoff")
    if capitalization is None:
        capitalization = analysis.get("capitalization") or analysis.get("allocation")
    if hurdle is None:
        hurdle = analysis.get("economic_hurdle")

    vector_ok = dist.get("status") == OBSERVED and dist.get("n")
    if vector_ok:
        observed = {
            "status": OBSERVED,
            "label": "OBSERVED CANDLE-PATH EV · not a fill",
            "formula": "E[exit_close − entry_close]",
            "estimate_cents": dist.get("mean_cents"),
            "n": dist.get("n"),
            "reason": CANDLE_NOT_FILL,
        }
        sharpe = {
            "status": OBSERVED,
            "estimate": dist.get("observed_path_sharpe") or dist.get("sharpe_trade"),
            "reason": "Unannualized path Sharpe on the observed return vector. " + CANDLE_NOT_FILL,
        }
        sortino = {
            "status": OBSERVED if dist.get("sortino") is not None else UNAVAILABLE,
            "estimate": dist.get("sortino"),
            "reason": CANDLE_NOT_FILL,
        }
        cap_obs = (capitalization or {}).get("observed") if isinstance(capitalization, dict) else None
        if cap_obs:
            cap = {
                "status": OBSERVED,
                "expected_allocation_dollars": cap_obs.get("expected_allocation_dollars"),
                "reason": "Fixed-allocation scale of observed candle-path returns. " + CANDLE_NOT_FILL,
            }
        else:
            cap = _status(UNAVAILABLE, "No capitalized observed path. " + CANDLE_NOT_FILL)
        if hurdle and hurdle.get("break_even_total_cost_cents") is not None:
            brk = {
                "status": OBSERVED,
                "break_even_total_cost_cents": hurdle.get("break_even_total_cost_cents"),
                "reason": "Break-even overlay on observed candle-path EV. " + CANDLE_NOT_FILL,
            }
        else:
            brk = _status(UNAVAILABLE, "No observed return vector for a break-even cost.")
    else:
        observed = _status(UNAVAILABLE, "No valid observed return vector. Missing exit is not 0. " + CANDLE_NOT_FILL)
        sharpe = _status(UNAVAILABLE, "Sharpe requires a declared return vector. " + CANDLE_NOT_FILL)
        sortino = _status(UNAVAILABLE, "Sortino requires a declared return vector. " + CANDLE_NOT_FILL)
        cap = _status(UNAVAILABLE, "Capitalization requires a declared return vector. " + CANDLE_NOT_FILL)
        brk = _status(UNAVAILABLE, "Break-even requires a declared return vector.")

    named_obs = _meas(result, "observed_hyp_ev_cents") if result else None
    if observed.get("status") != OBSERVED and named_obs and isinstance(named_obs.get("value"), (int, float)):
        observed = {
            "status": OBSERVED,
            "label": "OBSERVED CANDLE-PATH EV · not a fill",
            "formula": "E[hyp_pnl_cents]",
            "estimate_cents": float(named_obs["value"]),
            "reason": CANDLE_NOT_FILL,
        }

    if book_price and book_price.get("status") in (HYPOTHETICAL, OBSERVED) and book_price.get("ev_cents") is not None:
        book = {
            "status": book_price.get("status"),
            "estimate_cents": book_price.get("ev_cents"),
            "reason": "Explicit WIN/LOSS payoff chips. Not a fill.",
        }
    else:
        book = _status(UNAVAILABLE, "No explicit WIN/LOSS payoff chips.")

    missing = rates.get("terminal_missing")
    yes = rates.get("terminal_yes")
    no = rates.get("terminal_no")
    if missing is not None and int(missing) > 0:
        settle = _status(
            INCOMPLETE,
            "TERMINAL DATA INCOMPLETE · missing is not NO · do not apply settled rates to N.",
            terminal_yes=yes,
            terminal_no=no,
            terminal_missing=missing,
            settled=rates.get("settled"),
            n=rates.get("n"),
        )
    elif yes is None or no is None:
        settle = _status(DATA_REQUIRED, "Authoritative Kalshi settlement required.")
    else:
        settle = {
            "status": (settlement or {}).get("status") or OBSERVED,
            "estimate_cents": (settlement or {}).get("ev_cents"),
            "reason": "Measured Kalshi YES/NO only. Missing is not NO.",
            "terminal_yes": yes,
            "terminal_no": no,
            "terminal_missing": missing or 0,
            "settled": rates.get("settled"),
            "n": rates.get("n"),
        }

    model_ok = is_exact_model_a_8040(question, result)
    named_a = _meas(result, "model_a_8040_ev_cents") if result else None
    q = None
    if rates.get("path_true") is not None and rates.get("n"):
        q = int(rates["path_true"]) / int(rates["n"])
    elif rates.get("path_true") is not None and rates.get("path_available"):
        q = int(rates["path_true"]) / int(rates["path_available"])
    if model_ok and q is not None:
        model_a = {
            "status": HYPOTHETICAL,
            "eligible": True,
            "estimate_cents": float(named_a["value"]) if named_a and isinstance(named_a.get("value"), (int, float)) else 20.0 - 60.0 * q,
            "q": q,
            "formula": MODEL_A_FORMULA,
            "reason": "Exact 80¢ entry / 40¢ LOSS on TRADABLE_YES_BID. " + CANDLE_NOT_FILL,
        }
    elif model_ok:
        model_a = _status(DATA_REQUIRED, "Model A eligible but path rate is missing.", eligible=True)
    else:
        model_a = _status(
            NOT_APPLICABLE,
            "Model A is exact 80¢ entry / 40¢ LOSS on TRADABLE_YES_BID only.",
            eligible=False,
        )

    return {
        "observed_path_ev": observed,
        "strategy_pnl": _status(UNAVAILABLE, "Strategy P&L requires fills. " + CANDLE_NOT_FILL),
        "sharpe": sharpe,
        "sortino": sortino,
        "break_even_edge": brk,
        "capitalization": cap,
        "risk_of_ruin": _status(
            UNAVAILABLE if not model_ok else (OBSERVED if _meas(result, "risk_of_ruin") else UNAVAILABLE),
            "RoR is not a live-account forecast. " + CANDLE_NOT_FILL,
        ),
        "book_price_ev": book,
        "model_a_8040_ev": model_a,
        "fill_adjusted_ev": _status(UNAVAILABLE, CANDLE_NOT_FILL + ". Execution data required."),
        "settlement_ev": settle,
        "print_displacement": None,
    }


def _unknown_economics() -> dict[str, Any]:
    reason = "Observation basis unknown. Fail closed."
    block = _status(UNAVAILABLE, reason)
    return {
        "observed_path_ev": block,
        "strategy_pnl": block,
        "sharpe": block,
        "sortino": block,
        "break_even_edge": block,
        "capitalization": block,
        "risk_of_ruin": block,
        "book_price_ev": block,
        "model_a_8040_ev": block,
        "fill_adjusted_ev": block,
        "settlement_ev": _status(DATA_REQUIRED, reason),
        "print_displacement": None,
    }


def _rate_blocks(counts: dict[str, Any]) -> dict[str, Any]:
    n = counts.get("n")
    settled = counts.get("settled")
    return {
        "path_rate": _rate(counts.get("path_true"), n, RATE_LABELS["path_rate"]),
        "win_on_n": _rate(counts.get("win_exit") if (counts.get("win_exit") or counts.get("loss_exit")) else counts.get("path_true"), n, RATE_LABELS["win_on_n"]),
        "loss_on_n": _rate(counts.get("loss_exit"), n, RATE_LABELS["loss_on_n"]),
        "classified_win_rate": _rate(counts.get("win_exit"), counts.get("classified"), RATE_LABELS["classified_win"]),
        "classified_loss_rate": _rate(counts.get("loss_exit"), counts.get("classified"), RATE_LABELS["classified_loss"]),
        "terminal_yes_rate": _rate(counts.get("terminal_yes"), settled, RATE_LABELS["terminal_yes"]),
        "terminal_coverage": _rate(settled, n, RATE_LABELS["coverage"]),
        "terminal_missing_rate": _rate(counts.get("terminal_missing"), n, RATE_LABELS["missing"]),
    }


def _invariants(mode: str, counts: dict[str, Any], economics: dict[str, Any]) -> dict[str, Any]:
    yes, no, missing, n = (
        counts.get("terminal_yes"),
        counts.get("terminal_no"),
        counts.get("terminal_missing"),
        counts.get("n"),
    )
    win, loss, classified = counts.get("win_exit"), counts.get("loss_exit"), counts.get("classified")
    diag = economics.get("print_displacement") or {}
    model = economics.get("model_a_8040_ev") or {}
    return {
        "yes_plus_no_plus_missing_eq_n": (
            yes is not None and no is not None and missing is not None and n is not None
            and int(yes) + int(no) + int(missing) == int(n)
        ),
        "win_plus_loss_eq_classified": (
            win is not None and loss is not None and classified is not None
            and int(win) + int(loss) == int(classified)
        ),
        "path_false_is_not_loss": counts.get("path_false") != counts.get("loss_exit"),
        "loss_only_print_not_population_ev": (
            mode != MODE_LAST_TRADE or diag.get("feeds_population_ev") is False
        ),
        "model_a_only_on_tradable_8040": (
            mode == MODE_LAST_TRADE
            and model.get("status") == UNAVAILABLE
            or mode != MODE_LAST_TRADE
        ),
        "no_sport_branch": True,
    }


def _disclaimers(mode: str, counts: dict[str, Any]) -> list[str]:
    bits = [
        "PATH WIN ≠ TERMINAL YES",
        "PATH LOSS ≠ TERMINAL NO",
        "PATH FALSE ≠ LOSS",
        "MEASUREMENT ≠ EDGE",
    ]
    if mode == MODE_LAST_TRADE:
        bits = [
            "LAST TRADE ≠ YES BID",
            "LAST TRADE ≠ FILL",
            *bits,
        ]
        if counts.get("terminal_missing"):
            bits.append("TERMINAL DATA INCOMPLETE")
            bits.append("EXECUTION DATA REQUIRED")
    else:
        bits = ["CANDLE PATH ≠ FILL", *bits]
        if counts.get("terminal_missing"):
            bits.append("TERMINAL DATA INCOMPLETE")
    return bits


def build_results_contract(
    *,
    last_trade: bool = False,
    observation_basis: str | None = None,
    metrics: dict[str, Any] | None = None,
    identity: dict[str, Any] | None = None,
    rows: list[dict[str, Any]] | None = None,
    question: Any = None,
    result: dict[str, Any] | None = None,
    n: int | None = None,
    observed_returns: dict[str, Any] | None = None,
    settlement: dict[str, Any] | None = None,
    book_price: dict[str, Any] | None = None,
    capitalization: dict[str, Any] | None = None,
    hurdle: dict[str, Any] | None = None,
    trade_breakeven: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mode = economic_mode(last_trade=last_trade, observation_basis=observation_basis, result=result)
    basis = observation_basis or observation_basis_of(result) or mode
    if rows is None and result is not None:
        pop = result.get("population") or {}
        rows = pop.get("trades") or pop.get("rows") or []
    counts = collect_rate_counts(result, metrics=metrics, identity=identity, n=n)
    if mode == MODE_LAST_TRADE:
        economics = _last_trade_economics(
            rates=counts,
            rows=rows,
            settlement=settlement,
            question=question,
            book_price=book_price,
            trade_breakeven=trade_breakeven,
        )
    elif mode == MODE_TRADABLE:
        economics = _tradable_economics(
            rates=counts,
            question=question,
            result=result,
            observed_returns=observed_returns,
            settlement=settlement,
            book_price=book_price,
            capitalization=capitalization,
            hurdle=hurdle,
        )
    else:
        economics = _unknown_economics()
    exposure = verify_exposure(
        rows=rows,
        n=counts.get("n"),
        result=result,
        question=question,
    )
    if exposure.get("status") == CARDINALITY_VIOLATION:
        blocked = _status(
            CARDINALITY_VIOLATION,
            str(exposure.get("reason") or "1 GAME = 1 TRADE MAX violated. Strategy statistics withheld."),
        )
        for key in (
            "observed_path_ev",
            "strategy_pnl",
            "sharpe",
            "sortino",
            "break_even_edge",
            "capitalization",
            "risk_of_ruin",
            "book_price_ev",
            "model_a_8040_ev",
            "fill_adjusted_ev",
        ):
            economics[key] = blocked
        settle = dict(economics.get("settlement_ev") or {})
        settle["estimate_cents"] = None
        settle["strategy_statistics_permitted"] = False
        settle["cardinality"] = CARDINALITY_VIOLATION
        economics["settlement_ev"] = settle
    rates = {**_rate_blocks(counts), "counts": counts}
    limitations = {
        "last_trade_not_executable": mode == MODE_LAST_TRADE,
        "candle_path_not_fill": mode == MODE_TRADABLE,
        "settlement_incomplete": (economics.get("settlement_ev") or {}).get("status") == INCOMPLETE,
        "missing_terminal": bool(counts.get("terminal_missing")),
        "cardinality_unverified": exposure.get("status") == "UNVERIFIED",
        "cardinality_violation": exposure.get("status") == CARDINALITY_VIOLATION,
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "schema_version": CONTRACT_VERSION,
        "economic_mode": mode,
        "observation_basis": basis,
        "exposure": exposure,
        "rates": rates,
        "economics": {
            k: v
            for k, v in economics.items()
            if k != "print_displacement"
        },
        "hold": _hold_block(),
        "print_displacement": economics.get("print_displacement"),
        "limitations": limitations,
        "invariants": {
            **_invariants(mode, counts, economics),
            "strategy_game_exposure_verified": exposure.get("status") == OBSERVED
            and exposure.get("exposure_unit") == "GAME"
            and exposure.get("max_entries_per_unit") == 1,
        },
        "disclaimers": _disclaimers(mode, counts),
    }


def results_contract(result: dict[str, Any]) -> dict[str, Any]:
    """Authoritative contract from a result envelope. Does not invent fills."""
    analysis = result.get("analysis") or {}
    return build_results_contract(
        result=result,
        last_trade=False,
        observation_basis=observation_basis_of(result),
        identity=result.get("identity"),
        rows=(result.get("population") or {}).get("trades")
        or (result.get("population") or {}).get("rows"),
        question=(result.get("compile") or {}).get("question"),
        n=(result.get("summary") or {}).get("population_n"),
        observed_returns=analysis.get("observed_returns") or analysis.get("observed_path"),
        settlement=analysis.get("settlement_payoff") or analysis.get("settlement"),
        book_price=analysis.get("book_price") or analysis.get("hypothetical_payoff"),
        capitalization=analysis.get("capitalization") or analysis.get("allocation"),
        hurdle=analysis.get("economic_hurdle"),
        trade_breakeven=analysis.get("trade_breakeven"),
    )
