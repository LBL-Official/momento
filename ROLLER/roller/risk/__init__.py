"""Bankroll & Risk Engine — consumer of ROLLER research results.

Does not modify ConditionalBacktest. Does not invent fills, fees, or Sigma.
"""

from roller.risk.engine import run_risk
from roller.risk.formulas import (
    break_even_probability,
    required_win_probability,
    trade_capital,
    trade_ev,
    weekly_ev,
    weekly_return_from_wins,
    weekly_volatility,
)

__all__ = [
    "run_risk",
    "break_even_probability",
    "required_win_probability",
    "trade_capital",
    "trade_ev",
    "weekly_ev",
    "weekly_return_from_wins",
    "weekly_volatility",
]
