"""Feature catalog. Timing is the leakage authority."""

from __future__ import annotations

from dataclasses import dataclass

BEFORE = "AVAILABLE_BEFORE_ENTRY"
AT = "AVAILABLE_AT_ENTRY"
POST = "POST_EVENT_DIAGNOSTIC"
FUTURE = "FUTURE_OUTCOME"

PREDICTIVE_TIMING = frozenset({BEFORE, AT})
FORBIDDEN_TIMING = frozenset({POST, FUTURE})

FORBIDDEN_NAMES = frozenset(
    {
        "t40",
        "s",
        "s_n",
        "w_and_t40",
        "l_and_t40",
        "terminal_yes",
        "post_entry_min",
        "time_to_40",
        "hit_90",
        "min_after",
        "max_after",
        "next_close",
        "price_1m_after",
        "price_3m_after",
        "price_5m_after",
        "ev_contribution",
        "w",
    }
)


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    feature_class: str
    timing: str
    source: str
    units: str
    formula: str
    semantic_basis: str
    availability_rule: str
    include_in_matrix: bool = True
    kind: str = "continuous"


CATALOG: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        "entry_bid_cents", "B", AT, "asked_six.market_yes_bid", "cents",
        "tradable yes bid close at FIRST80 candle", "TRADABLE_YES_BID",
        "required on every instance",
    ),
    FeatureSpec(
        "entry_ask_cents", "L", AT, "asked_six.market_yes_ask", "cents",
        "yes ask at FIRST80 candle", "YES_ASK",
        "null if blank",
    ),
    FeatureSpec(
        "spread_cents", "L", AT, "asked_six bid/ask", "cents",
        "ask − bid at entry", "QUOTE_AT_ENTRY",
        "null if ask missing; not L2",
    ),
    FeatureSpec(
        "entry_last_cents", "B", AT, "asked_six.market_last_price", "cents",
        "last print on entry candle if present", "LAST_TRADE_PRINT",
        "null if blank; not interchangeable with bid",
    ),
    FeatureSpec(
        "entry_volume", "B", AT, "asked_six.market_volume", "contracts",
        "volume on the FIRST80 candle if present", "CANDLE_VOLUME",
        "null if blank; not a fill",
    ),
    FeatureSpec(
        "pregame_cents", "M", BEFORE, "asked_six.pregame_*_win_prob", "cents",
        "Kalshi last pre-tip yes bid × 100", "KALSHI_LAST_PRE_TIP_YES_BID",
        "required on NBA 604",
    ),
    FeatureSpec(
        "distance_from_open", "M", AT, "entry_bid − pregame", "cents",
        "entry_bid_cents − pregame_cents", "TRADABLE_YES_BID vs pre-tip",
        "required",
    ),
    FeatureSpec(
        "bought_margin", "G", AT, "asked_six.bought_team_margin", "points",
        "bought-team lead at CSV 80 snapshot", "CSV_ENTRY_SNAPSHOT",
        "required; not warehouse PIT",
    ),
    FeatureSpec(
        "abs_margin", "G", AT, "abs(bought_margin)", "points",
        "absolute bought-team margin", "CSV_ENTRY_SNAPSHOT",
        "required",
    ),
    FeatureSpec(
        "score_home", "G", AT, "asked_six.score_home", "points",
        "home score at CSV 80 snapshot", "CSV_ENTRY_SNAPSHOT",
        "required", include_in_matrix=False,
    ),
    FeatureSpec(
        "score_away", "G", AT, "asked_six.score_away", "points",
        "away score at CSV 80 snapshot", "CSV_ENTRY_SNAPSHOT",
        "required", include_in_matrix=False,
    ),
    FeatureSpec(
        "leading", "G", AT, "bought_margin > 0", "bool",
        "1 if bought team leads", "CSV_ENTRY_SNAPSHOT",
        "required", kind="binary",
    ),
    FeatureSpec(
        "tie", "G", AT, "bought_margin == 0", "bool",
        "1 if tied", "CSV_ENTRY_SNAPSHOT",
        "required", kind="binary",
    ),
    FeatureSpec(
        "favorite_leading", "G", AT, "pregame and margin", "bool",
        "1 if pregame≥50 and margin>0", "CSV_ENTRY_SNAPSHOT",
        "required", kind="binary",
    ),
    FeatureSpec(
        "period_remaining_s", "F", AT, "asked_six.period_remaining_s", "seconds",
        "modeled seconds left in period", "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
        "required; not warehouse PIT",
    ),
    FeatureSpec(
        "game_seconds_remaining", "F", AT, "asked_six.game_seconds_remaining", "seconds",
        "modeled seconds left in regulation", "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
        "required; not warehouse PIT",
    ),
    FeatureSpec(
        "frac_period_remaining", "F", AT, "period_remaining_s / 720", "fraction",
        "seconds left / 12-minute quarter", "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
        "required",
    ),
    FeatureSpec(
        "frac_game_elapsed", "F", AT, "1 − remaining/2880", "fraction",
        "1 − game_seconds_remaining / 48 minutes", "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
        "required on regulation",
    ),
    FeatureSpec(
        "regular_season", "A", AT, "asked_six.season_phase", "bool",
        "1 if REGULAR_SEASON", "CSV_METADATA",
        "required", kind="binary",
    ),
    FeatureSpec(
        "jump_through_80", "D", AT, "entry_bid > 80", "bool",
        "1 if entry close > 80", "TRADABLE_YES_BID",
        "required; not a fill", kind="binary",
    ),
    FeatureSpec(
        "exact_80", "D", AT, "entry_bid == 80", "bool",
        "1 if entry close is exactly 80", "TRADABLE_YES_BID",
        "required", kind="binary",
    ),
    FeatureSpec(
        "prior_close_cents", "D", BEFORE, "warehouse yes_bid_close", "cents",
        "last TRADABLE_YES_BID close with available_at < entry", "TRADABLE_YES_BID",
        "OBSERVATION_UNAVAILABLE if no pre-entry bar",
    ),
    FeatureSpec(
        "came_from_below", "D", BEFORE, "prior_close < 80", "bool",
        "1 if prior close < 80", "TRADABLE_YES_BID",
        "null if prior missing", kind="binary",
    ),
    FeatureSpec(
        "bars_before_n", "C", BEFORE, "warehouse count", "count",
        "pre-entry 1m bars for ticker", "TRADABLE_YES_BID",
        "0 allowed; not imputed",
    ),
    FeatureSpec(
        "period_q2", "O", AT, "asked_six.slice", "bool",
        "1 if period is Q2", "CSV_METADATA",
        "grouping column; not an explanatory cause of Q2 vs Q3",
        include_in_matrix=False, kind="binary",
    ),
    FeatureSpec(
        "period_q3", "O", AT, "asked_six.slice", "bool",
        "1 if period is Q3", "CSV_METADATA",
        "grouping column; not an explanatory cause of Q2 vs Q3",
        include_in_matrix=False, kind="binary",
    ),
    FeatureSpec(
        "overtime_flag", "F", AT, "game_seconds_remaining", "bool",
        "1 if modeled remaining implies OT or elapsed>48m", "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
        "flag only; Q2/Q3 asked-six should be regulation",
        include_in_matrix=False, kind="binary",
    ),
)

WINDOWS = (1, 3, 5, 10, 15, 30)


def _window_specs() -> tuple[FeatureSpec, ...]:
    out: list[FeatureSpec] = []
    for w in WINDOWS:
        out.extend(
            (
                FeatureSpec(
                    f"close_{w}m_before", "C", BEFORE, "warehouse yes_bid_close", "cents",
                    f"close of bar nearest to entry−{w}m among pre-entry bars",
                    "TRADABLE_YES_BID", f"null if no bar in [{w}m, 0)",
                ),
                FeatureSpec(
                    f"delta_{w}m", "J", BEFORE, "entry − close_wm", "cents",
                    f"entry_bid − close_{w}m_before", "TRADABLE_YES_BID",
                    "null if window empty",
                ),
                FeatureSpec(
                    f"velocity_{w}m", "J", BEFORE, f"delta_{w}m / {w}", "cents/min",
                    f"delta_{w}m / {w}", "TRADABLE_YES_BID",
                    "null if window empty",
                ),
                FeatureSpec(
                    f"accel_{w}m", "J", BEFORE, "second-half minus first-half velocity",
                    "cents/min",
                    f"window split in half; (v2 − v1) for {w}m if n≥4",
                    "TRADABLE_YES_BID", "null if n<4",
                ),
                FeatureSpec(
                    f"min_{w}m", "C", BEFORE, "min close in window", "cents",
                    f"min yes_bid_close in ({w}m, 0)", "TRADABLE_YES_BID",
                    "null if window empty",
                ),
                FeatureSpec(
                    f"max_{w}m", "C", BEFORE, "max close in window", "cents",
                    f"max yes_bid_close in ({w}m, 0)", "TRADABLE_YES_BID",
                    "null if window empty",
                ),
                FeatureSpec(
                    f"range_{w}m", "K", BEFORE, "max−min", "cents",
                    f"max_{w}m − min_{w}m", "TRADABLE_YES_BID",
                    "null if window empty",
                ),
                FeatureSpec(
                    f"std_{w}m", "K", BEFORE, "std of closes", "cents",
                    f"sample std of closes in {w}m if n≥3", "TRADABLE_YES_BID",
                    "null if n<3",
                ),
                FeatureSpec(
                    f"direction_changes_{w}m", "C", BEFORE, "sign flips", "count",
                    f"sign changes of consecutive close diffs in {w}m", "TRADABLE_YES_BID",
                    "null if n<3",
                ),
                FeatureSpec(
                    f"n_bars_{w}m", "C", BEFORE, "count", "count",
                    f"bars with available_at in (entry−{w}m, entry)", "TRADABLE_YES_BID",
                    "0 if empty",
                ),
            )
        )
    return tuple(out)


CATALOG = CATALOG + _window_specs()

LABEL_SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec("t40", "P", FUTURE, "asked_six.T40", "bool", "post-entry close ≤ 40", "CANDLE_PATH", "required"),
    FeatureSpec("s", "P", FUTURE, "not T40", "bool", "1 if survived 40", "CANDLE_PATH", "required"),
    FeatureSpec("w_and_t40", "P", FUTURE, "W and T40", "bool", "terminal yes after T40", "CANDLE_PATH", "required"),
    FeatureSpec("l_and_t40", "P", FUTURE, "not W and T40", "bool", "terminal no after T40", "CANDLE_PATH", "required"),
    FeatureSpec("terminal_yes", "P", FUTURE, "asked_six.terminal_yes", "bool", "settlement YES", "SETTLEMENT", "required"),
    FeatureSpec("post_entry_min", "P", FUTURE, "asked_six.post_entry_min_yes_bid_cents", "cents", "min close after entry", "TRADABLE_YES_BID", "required"),
    FeatureSpec("ev_contribution", "P", FUTURE, "20 if S else -40", "cents", "candle-path 80/40 contribution", "ROLLER EV 20S−40(1−S)", "required"),
    FeatureSpec("time_to_40", "P", FUTURE, "exit − entry if T40", "seconds", "CSV exit stamp minus entry", "CANDLE_PATH", "null if not T40 or stamp missing"),
    FeatureSpec("hit_90", "P", FUTURE, "post-entry close ≥ 90", "bool", "any later warehouse close ≥ 90", "TRADABLE_YES_BID", "OBSERVATION_UNAVAILABLE if no post bars"),
    FeatureSpec("min_after", "P", FUTURE, "min post-entry close", "cents", "warehouse min after entry", "TRADABLE_YES_BID", "null if no post bars"),
    FeatureSpec("max_after", "P", FUTURE, "max post-entry close", "cents", "warehouse max after entry", "TRADABLE_YES_BID", "null if no post bars"),
)


def spec_by_name() -> dict[str, FeatureSpec]:
    return {spec.name: spec for spec in CATALOG}


def matrix_specs() -> tuple[FeatureSpec, ...]:
    return tuple(spec for spec in CATALOG if spec.include_in_matrix and spec.timing in PREDICTIVE_TIMING)
