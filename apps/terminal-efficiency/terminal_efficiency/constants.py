"""Sport constants and NCAAB P5 membership. Copied from ncaab ESPN ingest; not invented."""

from __future__ import annotations

P5_CODES = frozenset(
    {
        "ALA",
        "ARIZ",
        "ARK",
        "ASU",
        "AUB",
        "BAY",
        "BC",
        "BYU",
        "CAL",
        "CIN",
        "CLEM",
        "COLO",
        "DUKE",
        "FLA",
        "FSU",
        "GT",
        "HOU",
        "ILL",
        "IND",
        "IOWA",
        "ISU",
        "KSU",
        "KU",
        "LOU",
        "LSU",
        "MD",
        "MIA",
        "MICH",
        "MINN",
        "MISS",
        "MIZZ",
        "MSST",
        "MSU",
        "NCST",
        "ND",
        "NEB",
        "NW",
        "OKLA",
        "OKST",
        "ORE",
        "ORST",
        "OSU",
        "PITT",
        "PSU",
        "PUR",
        "RUTG",
        "SCAR",
        "SMU",
        "STAN",
        "SYR",
        "TCU",
        "TENN",
        "TEX",
        "TTU",
        "TXAM",
        "UCF",
        "UCLA",
        "UGA",
        "UK",
        "UNC",
        "USC",
        "UTAH",
        "UVA",
        "VAN",
        "VT",
        "WAKE",
        "WASH",
        "WIS",
        "WSU",
        "WVU",
    }
)

ESPN_ABBR_TO_P5: dict[str, str] = {c: c for c in P5_CODES}
ESPN_ABBR_TO_P5.update(
    {
        "SC": "SCAR",
        "OU": "OKLA",
        "TA&M": "TXAM",
        "TAMU": "TXAM",
        "MIZ": "MIZZ",
        "NCSU": "NCST",
        "MICHST": "MSU",
    }
)

# Exact feature names (or prefixes) that must never enter XIB/MCD design matrices.
FORBIDDEN_FEATURE_NAMES = frozenset(
    {
        "final_home_win",
        "home_win",
        "away_win",
        "winner",
        "kalshi_yes_price_e4",
        "kalshi_no_price_e4",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "actual_remaining",
        "season_final_offensive_rating",
    }
)
FORBIDDEN_FEATURE_PREFIXES = ("future_", "kalshi_yes", "kalshi_no", "yes_bid", "yes_ask")

QUALITY_OBSERVED = "OBSERVED"
QUALITY_MODELED = "MODELED"
QUALITY_UNAVAILABLE = "UNAVAILABLE"
QUALITY_AMBIGUOUS = "AMBIGUOUS"
QUALITY_DERIVED = "DERIVED"
