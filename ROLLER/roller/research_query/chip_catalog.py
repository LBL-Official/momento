"""Discrete Quick Start chips and the combos they may form.

A combo is MEASURE (warehouse pull returns N) or REFUSE (no number).
Price and dates are parameters, not a cartesian axis.

Does not edit FIRST80. Does not invent L2. CANDLE ≠ FILL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from roller.research_query.models import (
    ENTRY_OP_FAMILIES,
    TOUCH_FAMILIES,
    UNSUPPORTED_PATH,
)

Expect = Literal["MEASURE", "REFUSE"]

IMPLEMENTED_LEAGUES = ("NBA", "NCAAB", "MLB", "ATP", "WTA")
REFUSE_LEAGUES = ("WNBA",)

SPORT_FOR_LEAGUE = {
    "NBA": "basketball",
    "NCAAB": "basketball",
    "WNBA": "basketball",
    "MLB": "baseball",
    "ATP": "tennis",
    "WTA": "tennis",
}

DEFAULT_BASIS = {
    "NBA": "candles",
    "NCAAB": "candles",
    "WNBA": "candles",
    "MLB": "last_trade",
    "ATP": "candles",
    "WTA": "candles",
}

ENTRY_FAMILIES = (
    "first_touch",
    "second_touch",
    "third_touch",
    "fourth_touch",
    "nth_touch",
    "cross",
    "break",
    "reversion",
    "bounce",
    "recovery",
    "above",
    "below",
    "maximum_touch",
    "minimum_touch",
)

DIRECTION_FAMILIES = frozenset({"cross", "break", "reversion", "bounce", "recovery"})

PATH_FAMILIES = (
    "reach",
    "drop_to",
    "rise_to",
    "recover",
    "bounce",
    "revert",
    "maximum_move",
    "minimum_move",
    "never_reach",
)
REFUSE_PATH_FAMILIES = tuple(sorted(UNSUPPORTED_PATH))

NBA_PERIODS = (
    {"id": "Q1", "period": "Q1"},
    {"id": "Q2", "period": "Q2"},
    {"id": "Q3", "period": "Q3"},
    {"id": "Q4", "period": "Q4"},
    {"id": "OT", "period": "OT"},
)
NBA_CLOCKS = tuple(
    {
        "id": f"{q}_{a}_{b}",
        "period": q,
        "clockFrom": f"{a}:00",
        "clockTo": f"{b}:00",
    }
    for q in ("Q1", "Q2", "Q3", "Q4")
    for a, b in (("12", "08"), ("08", "04"), ("04", "00"))
)
NCAAB_PERIODS = (
    {"id": "H1", "period": "H1"},
    {"id": "H2", "period": "H2"},
    {"id": "OT", "period": "OT"},
    {"id": "P5", "period": "P5"},
    {"id": "H1_1", "period": "H1_1"},
    {"id": "H1_2", "period": "H1_2"},
    {"id": "H2_1", "period": "H2_1"},
    {"id": "H2_2", "period": "H2_2"},
)
NCAAB_CLOCKS = tuple(
    {
        "id": f"{half}_{a}_{b}",
        "period": half,
        "clockFrom": f"{a}:00",
        "clockTo": f"{b}:00",
    }
    for half in ("H1", "H2")
    for a, b in (("20", "15"), ("15", "10"), ("10", "05"), ("05", "00"))
)
MLB_PERIODS = tuple(
    {"id": f"{side}{n}", "period": f"{side}{n}"}
    for n in range(1, 10)
    for side in ("T", "B")
) + (
    {"id": "TX", "period": "TX"},
    {"id": "BX", "period": "BX"},
    {"id": "I7", "period": "I7"},
)
TENNIS_PERIODS = (
    {"id": "S1", "period": "S1"},
    {"id": "S2", "period": "S2"},
    {"id": "S3", "period": "S3"},
    {"id": "S4", "period": "S4"},
    {"id": "S5", "period": "S5"},
    {"id": "G1-3", "period": "G1-3"},
    {"id": "G4-6", "period": "G4-6"},
    {"id": "G7-9", "period": "G7-9"},
    {"id": "G10+", "period": "G10+"},
)

PERIODS_FOR_LEAGUE = {
    "NBA": NBA_PERIODS + NBA_CLOCKS,
    "NCAAB": NCAAB_PERIODS + NCAAB_CLOCKS,
    "MLB": MLB_PERIODS,
    "ATP": TENNIS_PERIODS,
    "WTA": TENNIS_PERIODS,
}

# Custom window so FIRST80 / P5 locks never steal the generic pull.
MEASURE_DATES = ("2025-11-01", "2026-02-01")
ENTRY_CENTS = 80
PATH_WIN_CENTS = 90
PATH_LOSS_CENTS = 40


@dataclass(frozen=True)
class ChipCombo:
    """One discrete chip tuple. Price/dates are fixed parameters."""

    league: str
    entry_family: str
    expect: Expect
    market_data: str = "candles"
    period: str | None = None
    clock_from: str | None = None
    clock_to: str | None = None
    direction: str | None = None
    path_family: str = "reach"
    path_cents: int = PATH_WIN_CENTS
    path_outcome: str | None = "win"
    terminal: str = "both"
    horizon_family: str | None = None
    horizon_minutes: int | None = None
    hold_family: str | None = None
    te_filters: dict[str, Any] | None = None
    markets: tuple[str, ...] = ("kalshi",)
    refuse_status: str | None = None
    period_id: str | None = None

    @property
    def sport(self) -> str:
        return SPORT_FOR_LEAGUE[self.league]

    @property
    def combo_id(self) -> str:
        bits = [
            self.league,
            self.market_data,
            self.entry_family,
            self.direction or "-",
            self.period_id or self.period or "any",
            self.path_family,
            self.horizon_family or "-",
            self.expect,
        ]
        return "|".join(bits)


def period_chips(league: str) -> tuple[dict[str, str], ...]:
    return PERIODS_FOR_LEAGUE.get(league, ())


def draft_from_combo(combo: ChipCombo) -> dict[str, Any]:
    """WorkflowDraft JSON for this combo. Dates stay off the FIRST80 lock."""
    entry: dict[str, Any] = {
        "id": "e1",
        "family": combo.entry_family,
        "priceCents": ENTRY_CENTS,
    }
    if combo.entry_family == "first_touch":
        entry["touchN"] = 1
    elif combo.entry_family == "second_touch":
        entry["touchN"] = 2
    elif combo.entry_family == "third_touch":
        entry["touchN"] = 3
    elif combo.entry_family == "fourth_touch":
        entry["touchN"] = 4
    elif combo.entry_family == "nth_touch":
        entry["touchN"] = "N"
        entry["touchNValue"] = 5
    if combo.direction:
        entry["direction"] = combo.direction
    if combo.period:
        entry["period"] = combo.period
    if combo.clock_from or combo.clock_to:
        entry["clockFrom"] = combo.clock_from
        entry["clockTo"] = combo.clock_to
    exits: list[dict[str, Any]] = []
    if combo.path_family:
        if combo.path_family in REFUSE_PATH_FAMILIES:
            exits.append(
                {
                    "id": "p1",
                    "kind": "path",
                    "family": combo.path_family,
                    "priceCents": combo.path_cents,
                    "outcome": combo.path_outcome,
                }
            )
        elif combo.path_family in PATH_FAMILIES:
            exits.append(
                {
                    "id": "p1",
                    "kind": "path",
                    "family": combo.path_family,
                    "priceCents": combo.path_cents,
                    "outcome": combo.path_outcome,
                }
            )
    if combo.horizon_family:
        row: dict[str, Any] = {
            "id": "h1",
            "kind": "horizon",
            "family": combo.horizon_family,
            "outcome": "win" if combo.horizon_family.endswith("_win") else "loss",
        }
        if combo.horizon_minutes is not None:
            row["horizonMinutes"] = combo.horizon_minutes
        exits.append(row)
    if combo.hold_family:
        exits.append(
            {
                "id": "t",
                "kind": "terminal",
                "family": combo.hold_family,
                "outcome": "win" if combo.hold_family.endswith("_win") else "loss",
            }
        )
    else:
        exits.append({"id": "t", "kind": "terminal", "family": combo.terminal})
    date_from, date_to = MEASURE_DATES
    draft: dict[str, Any] = {
        "universe": {
            "sports": [combo.sport],
            "leagues": [combo.league],
            "seasons": ["2025-26"],
            "markets": list(combo.markets),
            "marketData": [combo.market_data],
            "dateFrom": date_from,
            "dateTo": date_to,
        },
        "entryConditions": [entry],
        "exitConditions": exits,
    }
    if combo.te_filters:
        draft["teFilters"] = combo.te_filters
    return draft


def _entry_combo(
    league: str,
    family: str,
    *,
    market_data: str | None = None,
    period: dict[str, str] | None = None,
    direction: str | None = None,
    path_family: str = "reach",
    path_cents: int = PATH_WIN_CENTS,
    path_outcome: str | None = "win",
    **extra: Any,
) -> ChipCombo:
    md = market_data or DEFAULT_BASIS[league]
    period_row = period or {}
    return ChipCombo(
        league=league,
        entry_family=family,
        market_data=md,
        period=period_row.get("period"),
        clock_from=period_row.get("clockFrom"),
        clock_to=period_row.get("clockTo"),
        period_id=period_row.get("id"),
        direction=direction if family in DIRECTION_FAMILIES else None,
        path_family=path_family,
        path_cents=path_cents,
        path_outcome=path_outcome,
        expect="MEASURE",
        **extra,
    )


def measure_combos() -> list[ChipCombo]:
    """Every implemented chip appears in at least one MEASURE combo.

    NBA: full entry × period × default path, plus first_touch × each path.
    Other leagues: entry × period × default path on the native basis.
    Last-trade basketball is first_touch × native periods only.
    """
    out: list[ChipCombo] = []
    seen: set[str] = set()

    def add(combo: ChipCombo) -> None:
        if combo.combo_id not in seen:
            seen.add(combo.combo_id)
            out.append(combo)

    for family in ENTRY_FAMILIES:
        direction = "up" if family in DIRECTION_FAMILIES else None
        add(_entry_combo("NBA", family, direction=direction))
        for period in period_chips("NBA"):
            add(_entry_combo("NBA", family, period=period, direction=direction))
    for path in PATH_FAMILIES:
        cents = PATH_LOSS_CENTS if path in ("drop_to", "minimum_move") else PATH_WIN_CENTS
        outcome = "win" if cents >= ENTRY_CENTS else "loss"
        add(
            _entry_combo(
                "NBA",
                "first_touch",
                path_family=path,
                path_cents=cents,
                path_outcome=outcome,
            )
        )
    add(
        _entry_combo(
            "NBA",
            "first_touch",
            period={"id": "Q3", "period": "Q3"},
            hold_family="hold_expiration_win",
        )
    )
    add(
        _entry_combo(
            "NBA",
            "first_touch",
            horizon_family="horizon_market_win",
            horizon_minutes=5,
        )
    )
    add(
        _entry_combo(
            "NBA",
            "first_touch",
            horizon_family="horizon_game_win",
            horizon_minutes=5,
        )
    )
    add(_entry_combo("NBA", "first_touch", market_data="last_trade"))
    add(
        _entry_combo(
            "NBA",
            "cross",
            direction="down",
            period={"id": "Q3", "period": "Q3"},
        )
    )

    for league in ("NCAAB", "MLB", "ATP", "WTA"):
        for family in ENTRY_FAMILIES:
            direction = "up" if family in DIRECTION_FAMILIES else None
            add(_entry_combo(league, family, direction=direction))
            for period in period_chips(league):
                add(_entry_combo(league, family, period=period, direction=direction))
        if league in ("NBA", "NCAAB"):
            add(_entry_combo(league, "first_touch", market_data="last_trade"))
        if league in ("ATP", "WTA"):
            add(_entry_combo(league, "first_touch", market_data="last_trade"))

    return out


def refuse_combos() -> list[ChipCombo]:
    """Selectable chips that must not return a number."""
    out: list[ChipCombo] = [
        ChipCombo(
            league="NBA",
            entry_family="first_touch",
            market_data="tick",
            expect="REFUSE",
            refuse_status="DATA_REQUIRED",
        ),
        ChipCombo(
            league="NBA",
            entry_family="recovery",
            expect="REFUSE",
            refuse_status="OPERATION_REQUIRED",
        ),
        ChipCombo(
            league="MLB",
            entry_family="first_touch",
            period="Q3",
            period_id="foreign_Q3",
            expect="REFUSE",
            refuse_status="OPERATION_REQUIRED",
        ),
        ChipCombo(
            league="MLB",
            entry_family="first_touch",
            period="T7",
            period_id="T7_clock",
            clock_from="08:00",
            clock_to="04:00",
            expect="REFUSE",
            refuse_status="OPERATION_REQUIRED",
        ),
        ChipCombo(
            league="ATP",
            entry_family="first_touch",
            horizon_family="horizon_game_win",
            horizon_minutes=5,
            expect="REFUSE",
            refuse_status="OPERATION_REQUIRED",
        ),
        ChipCombo(
            league="MLB",
            entry_family="first_touch",
            horizon_family="horizon_game_win",
            horizon_minutes=5,
            expect="REFUSE",
            refuse_status="OPERATION_REQUIRED",
        ),
        ChipCombo(
            league="NBA",
            entry_family="first_touch",
            horizon_family="horizon_game_win",
            expect="REFUSE",
            refuse_status="OPERATION_REQUIRED",
        ),
    ]
    for fam in REFUSE_PATH_FAMILIES:
        out.append(
            ChipCombo(
                league="NBA",
                entry_family="first_touch",
                path_family=fam,
                expect="REFUSE",
                refuse_status="OPERATION_REQUIRED",
            )
        )
    return out


def all_combos() -> list[ChipCombo]:
    return measure_combos() + refuse_combos()


def catalog_entry_families() -> tuple[str, ...]:
    return ENTRY_FAMILIES


def implemented_entry_bindings() -> frozenset[str]:
    return frozenset(TOUCH_FAMILIES) | frozenset(ENTRY_OP_FAMILIES)
