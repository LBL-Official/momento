"""Ballhog — Hedging Analysis / exposure-removal optimizer.

Consumes Austin (N=604) and Choosin Texas (N=936) only.
Does not submit. Does not invent fills, λ, or Λα.
"""

from roller.ballhog.models import LIVE_EXECUTION, PRODUCT

__all__ = ("LIVE_EXECUTION", "PRODUCT")
