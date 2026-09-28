"""Rates and 2×2 partition from the SAME eligible rows. A+B+C+D = N."""

from __future__ import annotations

from typing import Any


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    if value is True or value is False:
        return bool(value)
    if value in (1, "1", "true", "True", "YES", "yes"):
        return True
    if value in (0, "0", "false", "False", "NO", "no"):
        return False
    return None


def measure_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Each row: path_true, terminal_yes (None if missing)."""
    eligible = list(rows)
    n = len(eligible)
    path_true = 0
    path_avail = 0
    yes = 0
    yes_avail = 0
    a = b = c = d = 0
    terminal_missing = 0
    for r in eligible:
        pt = _bool(r.get("path_true"))
        ty = _bool(r.get("terminal_yes"))
        if pt is not None:
            path_avail += 1
            if pt:
                path_true += 1
        if ty is None:
            terminal_missing += 1
        else:
            yes_avail += 1
            if ty:
                yes += 1
        if pt is None or ty is None:
            continue
        if pt and ty:
            a += 1
        elif pt and not ty:
            b += 1
        elif (not pt) and ty:
            c += 1
        else:
            d += 1
    joint_n = a + b + c + d
    path_false = path_avail - path_true
    win_n = sum(1 for r in eligible if r.get("exit_outcome") == "WIN_EXIT")
    loss_n = sum(1 for r in eligible if r.get("exit_outcome") == "LOSS_EXIT")
    classified = win_n + loss_n
    return {
        "n": n,
        "path_true": path_true,
        "path_false": path_false,
        "path_available": path_avail,
        "path_rate": (path_true / path_avail) if path_avail else None,
        "terminal_yes": yes,
        "terminal_available": yes_avail,
        "terminal_missing": terminal_missing,
        "yes_rate": (yes / yes_avail) if yes_avail else None,
        "partition": {
            "T_AND_W": a,
            "T_AND_NOT_W": b,
            "NOT_T_AND_W": c,
            "NOT_T_AND_NOT_W": d,
            "joint_n": joint_n,
        },
        "win_exit": win_n,
        "loss_exit": loss_n,
        "exit_classified": classified,
        "win_exit_rate": (win_n / classified) if classified else None,
        "loss_exit_rate": (loss_n / classified) if classified else None,
        "win_on_n": (win_n / n) if n else None,
        "loss_on_n": (loss_n / n) if n else None,
        "unclassified_on_n": ((n - classified) / n) if n and classified is not None else None,
    }


# $50 research snapshot. Not a live account. HYPOTHETICAL ruin math only.
RESEARCH_BANKROLL_CENTS = 5000


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def max_drawdown_cents(pnls: list[int]) -> int | None:
    """Peak-to-trough on the chronological P&L sequence. None if no trades."""
    if not pnls:
        return None
    peak = 0
    equity = 0
    max_dd = 0
    for pnl in pnls:
        equity += pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return max_dd


def risk_of_ruin(
    p_win: float,
    avg_win: float,
    avg_loss: float,
    bankroll_cents: int = RESEARCH_BANKROLL_CENTS,
) -> float | None:
    """
    Asymptotic gambler's-ruin approximation.

    ratio = ((1-p)/p) × (avg_loss/avg_win)
    RoR = 1 if ratio ≥ 1 (no positive edge), else ratio ** (bankroll / avg_loss)

    HYPOTHETICAL. Infinite independent trials. Not a live-account forecast.
    """
    if avg_loss <= 0 or bankroll_cents <= 0:
        return None
    if p_win <= 0:
        return 1.0
    if p_win >= 1:
        return 0.0
    if avg_win <= 0:
        return 1.0
    q = 1.0 - p_win
    ratio = (q / p_win) * (avg_loss / avg_win)
    if ratio >= 1.0:
        return 1.0
    units = bankroll_cents / avg_loss
    return min(1.0, max(0.0, ratio**units))


def measure_finite_math(
    rows: list[dict[str, Any]],
    *,
    model_a_8040: bool = False,
    path_rate: float | None = None,
    path_true: int = 0,
    path_available: int = 0,
) -> dict[str, Any]:
    """Hypothetical candle-path P&L. CANDLE PATH ≠ FILL. Do not invent settlement."""
    dated: list[tuple[str, int]] = []
    for r in rows:
        pnl = _int_or_none(r.get("hyp_pnl_cents"))
        if pnl is None:
            continue
        dated.append((str(r.get("entry_ts") or ""), pnl))
    dated.sort(key=lambda x: x[0])
    observed = [p for _, p in dated]

    out: dict[str, Any] = {
        "observed_n": len(observed),
        "mean_hyp_pnl_cents": (sum(observed) / len(observed)) if observed else None,
        "max_drawdown_cents": max_drawdown_cents(observed) if observed else None,
        "model_a_8040": model_a_8040,
        "model_a_ev_cents": None,
        "risk_of_ruin": None,
        "risk_of_ruin_source": None,
        "bankroll_cents": RESEARCH_BANKROLL_CENTS,
    }

    if model_a_8040 and path_rate is not None and path_available:
        # FIRST80_8040 Model A: +20 survive / −40 close-40 stop / 0 leak
        # EV_gross (R) = 1 − 3q ; 1R = 20¢ ⇒ EV_cents = 20 − 60q
        q = float(path_rate)
        out["model_a_ev_cents"] = 20.0 - 60.0 * q
        out["model_a_q"] = q
        out["model_a_formula"] = "EV_cents = 20 - 60q = 20*(1-3q); q = P(hit 40)"
        p_win = (path_available - path_true) / path_available
        out["risk_of_ruin"] = risk_of_ruin(p_win, 20.0, 40.0)
        out["risk_of_ruin_source"] = "model_a_8040"
        if not observed:
            synth = []
            for r in sorted(rows, key=lambda x: str(x.get("entry_ts") or "")):
                pt = r.get("path_true")
                if pt is True:
                    synth.append(-40)
                elif pt is False:
                    synth.append(20)
            out["max_drawdown_cents"] = max_drawdown_cents(synth)
            out["max_drawdown_source"] = "model_a_synthesized_sequence"
        else:
            out["max_drawdown_source"] = "observed_hyp_pnl"
        return out

    if observed:
        wins = [p for p in observed if p > 0]
        losses = [-p for p in observed if p < 0]
        p_win = len(wins) / len(observed)
        avg_win = (sum(wins) / len(wins)) if wins else 0.0
        avg_loss = (sum(losses) / len(losses)) if losses else 0.0
        out["risk_of_ruin"] = risk_of_ruin(p_win, avg_win, avg_loss)
        out["risk_of_ruin_source"] = "observed_hyp_pnl"
        out["max_drawdown_source"] = "observed_hyp_pnl"
    return out
