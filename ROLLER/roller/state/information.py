"""I_t — information / starters. Schema-only or not supported. No new scrapers."""

from __future__ import annotations

from roller.state.capabilities import capability
from roller.state.missingness import section


def information_state_section(sport: str) -> dict:
    cap = capability(sport, "information")
    return section(
        cap,
        None,
        note="starters, injuries, and news are an extension point; V2 does not scrape new sources",
    )
