"""Per-ticker pregame state. Cohort A uses the first valid quote only."""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.sugarland.constants import (
    ABOVE_70_LO,
    AROUND_80_HI,
    AROUND_80_LO,
    BELOW_100,
    CROSS_80,
    CROSS_THRESHOLDS,
    ENDPOINT_AGE_SEC,
    ENDPOINT_AGE_SENSITIVITIES,
    FIRST_THRESHOLDS,
    GRID_LOOKBACK_SEC,
    GRID_SEC,
    HORIZONS_H,
    SLOPE_AGE_SEC,
)
from roller.choosin_texas.sugarland.metrics import (
    dpp,
    gross_dollars,
    log_odds_change,
    relative_return,
    return_on_ask,
    upside_share,
)
from roller.choosin_texas.sugarland.quotes import (
    endpoint_reject_reason,
    is_boundary_arithmetic_mark,
    is_valid_quote,
    lead_bucket,
    price_band,
)
from roller.choosin_texas.sugarland.slope import path_from_grid


class TickerState:
    def __init__(
        self,
        *,
        ticker: str,
        game_id: str,
        sport: str,
        season: str,
        team_side: str,
        game_date: str,
        clock_label: str,
        t_start: int,
        t_end: int,
        t_end_sched: int | None,
        quarantine: str,
        schedule_relation: str,
        partition: str = "",
        result: str = "",
        settlement_e4: int | None = None,
    ) -> None:
        self.ticker = ticker
        self.game_id = game_id
        self.sport = sport
        self.season = season
        self.team_side = team_side
        self.game_date = game_date
        self.clock_label = clock_label
        self.t_start = t_start
        self.t_end = t_end
        self.t_end_sched = t_end_sched
        self.quarantine = quarantine
        self.schedule_relation = schedule_relation
        self.partition = partition
        self.result = result
        self.settlement_e4 = settlement_e4
        self.first_raw_ts: int | None = None
        self.n_raw = 0
        self.n_rows_before_valid = 0
        self.n_invalid_before_valid = 0
        self.first_valid: tuple[int, int, int, int | None, int] | None = None
        self.seen_below = {thr: False for thr in CROSS_THRESHOLDS}
        self.crossing: dict[int, tuple[int, int, int]] = {}
        self.time_reversal = False
        self.last_ts: int | None = None
        self.grid: dict[int, tuple[int, int]] = {}
        self.endpoints: dict[int, tuple[int, int, int]] = {}
        self.endpoints_sched: dict[int, tuple[int, int, int]] = {}
        self.horizons: dict[int, tuple[int, int, int]] = {}
        self.n_window_rows = 0
        self.n_window_boundary = 0
        self.n_window_excessive = 0
        self.n_window_other = 0
        self.window_latest_reason: str | None = None
        self.stale_valid_ts: int | None = None
        self.boundary_mark: tuple[int, int, int] | None = None
        self.store_until = t_end
        if t_end_sched is not None:
            self.store_until = max(self.store_until, t_end_sched)

    def consume(self, ts: int, bid: int | None, ask: int | None, volume: int | None) -> None:
        if self.last_ts is not None and ts < self.last_ts:
            self.time_reversal = True
            return
        self.last_ts = ts
        self.n_raw += 1
        if self.first_raw_ts is None:
            self.first_raw_ts = ts
        valid = is_valid_quote(bid, ask)
        if ts <= self.t_end:
            self._note_endpoint_window(ts, bid, ask, valid)
        if valid and bid is not None and ask is not None and ts <= self.store_until:
            self._remember(ts, bid, ask)
        if ts >= self.t_end:
            return
        if self.first_valid is None:
            if not valid or bid is None or ask is None:
                self.n_rows_before_valid += 1
                self.n_invalid_before_valid += 1
                return
            spread = ask - bid
            self.first_valid = (ts, bid, ask, volume, spread)
            self._note_path(ts, bid, ask)
            return
        if valid and bid is not None and ask is not None:
            self._note_path(ts, bid, ask)

    def _note_endpoint_window(self, ts: int, bid: int | None, ask: int | None, valid: bool) -> None:
        """Record why the frozen T−30 rule would drop a candle. Does not select the endpoint."""
        window_start = self.t_end - ENDPOINT_AGE_SEC
        if valid and ts < window_start:
            self.stale_valid_ts = ts
        if ts < window_start:
            return
        self.n_window_rows += 1
        reason = endpoint_reject_reason(bid, ask)
        self.window_latest_reason = reason
        if reason == "BOUNDARY_QUOTE" and bid is not None and ask is not None and is_boundary_arithmetic_mark(bid, ask):
            self.n_window_boundary += 1
            self.boundary_mark = (ts, bid, ask)
        elif reason == "EXCESSIVE_SPREAD":
            self.n_window_excessive += 1
        elif reason == "OTHER_EXCLUSION":
            self.n_window_other += 1

    def _endpoint_exclusion(self, observed: bool) -> str:
        if observed:
            return ""
        if self.quarantine:
            return "CLOCK_PROBLEM"
        if self.boundary_mark is not None:
            return "BOUNDARY_QUOTE"
        if self.n_window_rows == 0:
            if self.stale_valid_ts is not None:
                return "STALE_OBSERVATION"
            return "ABSENT_CANDLES"
        if self.window_latest_reason in {"EXCESSIVE_SPREAD", "OTHER_EXCLUSION"}:
            return self.window_latest_reason
        return "OTHER_EXCLUSION"

    def _remember(self, ts: int, bid: int, ask: int) -> None:
        self._cover_grid(ts, bid)
        for cap in ENDPOINT_AGE_SENSITIVITIES:
            self._cover_target(self.endpoints, self.t_end, cap, ts, bid, ask)
            if self.t_end_sched is not None:
                self._cover_target(self.endpoints_sched, self.t_end_sched, cap, ts, bid, ask)
        for hours in HORIZONS_H:
            target = self.t_start - hours * 3600
            self._cover_target(self.horizons, target, ENDPOINT_AGE_SEC, ts, bid, ask, slot=hours)

    def _cover_grid(self, ts: int, bid: int) -> None:
        first = ((ts + GRID_SEC - 1) // GRID_SEC) * GRID_SEC
        last = ts + SLOPE_AGE_SEC
        grid_t = first
        while grid_t <= last and grid_t <= self.store_until:
            if grid_t < self.t_end - GRID_LOOKBACK_SEC:
                grid_t += GRID_SEC
                continue
            if ts <= grid_t and grid_t - ts <= SLOPE_AGE_SEC:
                prev = self.grid.get(grid_t)
                if prev is None or ts >= prev[0]:
                    self.grid[grid_t] = (ts, bid)
            grid_t += GRID_SEC

    @staticmethod
    def _cover_target(
        store: dict[int, tuple[int, int, int]],
        target: int,
        cap: int,
        ts: int,
        bid: int,
        ask: int,
        *,
        slot: int | None = None,
    ) -> None:
        if not (target - cap <= ts <= target):
            return
        key = slot if slot is not None else cap
        prev = store.get(key)
        if prev is None or ts >= prev[0]:
            store[key] = (ts, bid, ask)

    def _note_path(self, ts: int, bid: int, ask: int) -> None:
        for thr in CROSS_THRESHOLDS:
            if bid < thr:
                self.seen_below[thr] = True
            elif self.seen_below[thr] and thr not in self.crossing:
                self.crossing[thr] = (ts, bid, ask)

    def finalize(self) -> dict[str, Any]:
        exclusion = self.quarantine
        if self.time_reversal and not exclusion:
            exclusion = "TIME_ORDER_VIOLATION"
        first = self.first_valid
        missing_minutes = None
        if self.first_raw_ts is not None and first is not None:
            span = max(0, (first[0] - self.first_raw_ts) // 60)
            missing_minutes = max(0, span - self.n_rows_before_valid)
        row: dict[str, Any] = {
            "ticker": self.ticker,
            "game_id": self.game_id,
            "sport": self.sport,
            "season": self.season,
            "team_side": self.team_side,
            "game_date": self.game_date,
            "clock_label": self.clock_label,
            "schedule_relation": self.schedule_relation,
            "partition": self.partition,
            "quarantine": self.quarantine,
            "history_before_first_raw": "UNKNOWN",
            "first_raw_ts": self.first_raw_ts,
            "n_raw": self.n_raw,
            "n_rows_before_valid": self.n_rows_before_valid,
            "n_invalid_before_valid": self.n_invalid_before_valid,
            "missing_minutes_before_valid": missing_minutes,
            "listing_time": "UNAVAILABLE",
            "t_start": self.t_start,
            "t_end": self.t_end,
            "in_a": False,
            "in_b": False,
            "already_above_80": False,
            "exclusion": exclusion,
            "endpoint_exclusion": self._endpoint_exclusion(self.endpoints.get(ENDPOINT_AGE_SEC) is not None),
            "endpoint_window_rows": self.n_window_rows,
            "endpoint_window_boundary": self.n_window_boundary,
            "endpoint_window_excessive_spread": self.n_window_excessive,
            "endpoint_window_other": self.n_window_other,
        }
        if self.boundary_mark is None:
            row["boundary_p30_ts"] = None
            row["boundary_p30_bid_e4"] = None
            row["boundary_p30_ask_e4"] = None
        else:
            row["boundary_p30_ts"] = self.boundary_mark[0]
            row["boundary_p30_bid_e4"] = self.boundary_mark[1]
            row["boundary_p30_ask_e4"] = self.boundary_mark[2]
        boundary_bid = None if self.boundary_mark is None else self.boundary_mark[1]
        row["boundary_log_odds_defined"] = boundary_bid is not None and 0 < boundary_bid < BELOW_100
        if first is None:
            if not exclusion:
                row["exclusion"] = "NO_PREGAME_VALID_QUOTE"
            return row
        ts, bid, ask, volume, spread = first
        row.update(
            {
                "p0_ts": ts,
                "p0_bid_e4": bid,
                "p0_ask_e4": ask,
                "p0_volume": volume,
                "p0_spread_e4": spread,
                "band": price_band(bid),
                "lead_hours_descriptive": (self.t_start - ts) / 3600.0,
                "lead_bucket_descriptive": lead_bucket((self.t_start - ts) / 3600.0),
                "lead_time_role": "DESCRIPTIVE_ACTUAL_START",
            }
        )
        for thr in FIRST_THRESHOLDS:
            row[f"first_above_{thr}"] = thr < bid < BELOW_100
        in_a = (not exclusion) and (ABOVE_70_LO < bid < BELOW_100)
        row["in_a"] = in_a
        if not exclusion and not in_a:
            row["exclusion"] = "FIRST_OBSERVED_NOT_ABOVE_70"
        row["already_above_80"] = (not exclusion) and bid >= CROSS_80
        cross = self.crossing.get(CROSS_80)
        if cross and not exclusion and not row["already_above_80"]:
            row["in_b"] = True
            row["b_ts"], row["b_bid_e4"], row["b_ask_e4"] = cross
        for thr in CROSS_THRESHOLDS:
            hit = self.crossing.get(thr)
            row[f"cross_{thr}_bid_e4"] = None if hit is None else hit[1]
        row["first_in_50_70"] = (not exclusion) and 5000 < bid <= 7000
        row["first_in_60_70"] = (not exclusion) and 6000 < bid <= 7000

        end = self.endpoints.get(ENDPOINT_AGE_SEC)
        self._attach_mark(row, end, prefix="p30")
        for cap in ENDPOINT_AGE_SENSITIVITIES:
            alt = self.endpoints.get(cap)
            row[f"p30_age_{cap}_bid_e4"] = None if alt is None else alt[1]
        sched = self.endpoints_sched.get(ENDPOINT_AGE_SEC)
        row["sched_endpoint_bid_e4"] = None if sched is None else sched[1]
        row["sched_endpoint_role"] = "STORED_SCHEDULE_SENSITIVITY" if self.t_end_sched is not None else "UNAVAILABLE"

        for hours in HORIZONS_H:
            quote = self.horizons.get(hours)
            if quote is None or quote[0] >= self.t_end:
                row[f"h{hours}_bid_e4"] = None
                row[f"h{hours}_ask_e4"] = None
                row[f"h{hours}_ts"] = None
                row[f"h{hours}_above70"] = False
                row[f"h{hours}_around80"] = False
                continue
            _hts, hbid, hask = quote
            row[f"h{hours}_ts"] = quote[0]
            row[f"h{hours}_bid_e4"] = hbid
            row[f"h{hours}_ask_e4"] = hask
            row[f"h{hours}_above70"] = ABOVE_70_LO < hbid < BELOW_100
            row[f"h{hours}_around80"] = AROUND_80_LO <= hbid <= AROUND_80_HI
            end_bid = self.endpoints.get(ENDPOINT_AGE_SEC)
            if end_bid is not None:
                row[f"h{hours}_dpp"] = dpp(hbid, end_bid[1])
                row[f"h{hours}_return_on_ask"] = return_on_ask(hask, end_bid[1])
                row[f"h{hours}_gross_positive"] = gross_dollars(hask, end_bid[1]) > 0

        if end is not None:
            self._outcome(row, bid, ask, ts, end)
        if in_a and end is not None:
            path = path_from_grid(self.grid, ts, bid, self.t_end)
            row["slope_status"] = path["status"]
            row["slope_pp_per_hour"] = path["beta_pp_per_hour"]
            row["covered_hours"] = path["covered_hours"]
            row["uncovered_hours"] = path["uncovered_hours"]
            row["share_time_above"] = path["share_above"]
            row["share_time_below"] = path["share_below"]
            row["max_appreciation_pp"] = path["max_appreciation_pp"]
            row["max_drawdown_pp"] = path["max_drawdown_pp"]
            row["peak_to_trough_pp"] = path["peak_to_trough_pp"]
            row["slope_n_weights"] = path["n_positive_weights"]
            row["slope_coverage"] = path["coverage_fraction"]
        elif in_a:
            row["endpoint_status"] = "MISSING_ENDPOINT"
            if row["exclusion"] in ("", "FIRST_OBSERVED_NOT_ABOVE_70"):
                row["exclusion"] = "MISSING_ENDPOINT"
        return row

    def _attach_mark(self, row: dict[str, Any], quote: tuple[int, int, int] | None, prefix: str) -> None:
        if quote is None:
            row[f"{prefix}_ts"] = None
            row[f"{prefix}_bid_e4"] = None
            row[f"{prefix}_ask_e4"] = None
            row["endpoint_status"] = "MISSING_ENDPOINT"
            return
        row[f"{prefix}_ts"] = quote[0]
        row[f"{prefix}_bid_e4"] = quote[1]
        row[f"{prefix}_ask_e4"] = quote[2]
        row["endpoint_age_sec"] = self.t_end - quote[0]
        row["endpoint_status"] = "OBSERVED"

    def _outcome(
        self,
        row: dict[str, Any],
        bid: int,
        ask: int,
        ts: int,
        end: tuple[int, int, int],
    ) -> None:
        end_ts, end_bid, _end_ask = end
        change = dpp(bid, end_bid)
        row["dpp"] = change
        row["dpp_e4"] = end_bid - bid
        row["r"] = relative_return(bid, end_bid)
        row["u"] = upside_share(bid, end_bid) if bid < 9000 else None
        row["u_including_high_band"] = upside_share(bid, end_bid)
        row["l"] = log_odds_change(bid, end_bid)
        elapsed = (end_ts - ts) / 3600.0
        row["h_elapsed"] = elapsed
        if elapsed > 0:
            row["s_pp"] = float(change) / elapsed
            rel = relative_return(bid, end_bid)
            row["r_per_h"] = None if rel is None else float(rel) / elapsed
            row["l_per_h"] = None if row["l"] is None else row["l"] / elapsed
        gross = gross_dollars(ask, end_bid)
        row["gross_dollars"] = gross
        row["return_on_ask"] = return_on_ask(ask, end_bid)
        row["gross_positive"] = gross > 0
        row["quote_benchmark_role"] = "QUOTE_BASED_NOT_EXECUTABLE"
        if self.settlement_e4 is not None:
            row["hypothetical_settlement_dollars"] = gross_dollars(ask, self.settlement_e4)
            row["settlement_role"] = "HYPOTHETICAL_SETTLEMENT"
        else:
            row["hypothetical_settlement_dollars"] = None
            row["settlement_role"] = "UNAVAILABLE"
        if row.get("exclusion") == "MISSING_ENDPOINT":
            row["exclusion"] = ""
