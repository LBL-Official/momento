# Unresolved decisions

Do not invent answers in code. Interfaces exist; behavior is blocked until review.

## Venue (Kalshi)

Inspected official docs in M4 (`docs/architecture/kalshi.md`). Still **UNRESOLVED**:

1. Exact pre-trade fee formula (quadratic / maker / combo / multiplier / event override). Fill rounding is documented; estimation is not fully specified for `FeeModel`.
2. Mapping sub-cent prices and sub-cent fees into integer-cent domain `Price`/`Money`.
3. Fractional contract fills (venue minimum 0.01) vs integer `Contracts`.
4. **Resolved (2026-08-24):** Kalshi does **not** provide an official mid.
   REST Market / Get Markets / WS ticker / orderbook have no `mid` field.
   Adapter leaves `mid = None`. Do not invent `(bid+ask)/2` or substitute last.
5. **Resolved (production MLB stop):** Create V2 `side=ask`, `reduce_only=true`,
   `post_only=false`, `time_in_force=immediate_or_cancel`, limit at the
   official orderbook best YES bid. Not a market order. Fills only from fill ingest.
6. Settlement details beyond yes/no $1 per contract (scalar, `MiscFeeAmt`, timing).
7. Available-balance definition for the weekly snapshot (`GET /portfolio/balance` exists; which field is “available” is unresolved).
8. **Resolved for production live transport:** sequence gap fail-closes and
   reconnects (fresh snapshot). Duplicate fills are ignored by fill id.
   Remaining UNRESOLVED: whether a partial in-place `get_snapshot` without
   reconnect is required for every gap.
9. Amend / decrease vs new `ClientOrderId` and risk-approval validity.
10. Create V2 `type=market` (GET Order enum includes `market`; create body has no `type` field).
11. `resting` with `remaining=0` (race vs `executed`) — fail closed.
12. HTTP 409 after timeout: Found vs Ambiguous until GET succeeds.
13. Ticker → `GameId` sports identity (host/adapter; MLB strategy consumes `GameId` on `MarketEvent` and does not map tickers).

## Position / P&L (M5)

26. Automatic application of yes/no `$1` per contract into `SettlementEvent.proceeds`. Proceeds must be supplied from verified venue data.
27. Unrealized / mark-to-market using Kalshi bid/ask/last/mid. `PnlBreakdown.unrealized_pnl` stays `None`.
28. Whether Kalshi reports a portfolio “position” object usable as `VenueReportedExposure` (interface exists; no invented endpoint).
29. HTTP 409 after timeout during tracker reconciliation: Found vs Ambiguous until GET succeeds (same as venue item 12).

## Strategy / M6

30. **Resolved (2026-08-24):** MLB qualifying observation is Kalshi
    `yes_bid_dollars` (`MarketEvent.bid`). Not last. Not ask. Not
    `(bid+ask)/2`. Not a venue mid. Missing/sub-cent/off-grid YES bid fails
    closed. 80/81/89 thresholds, 83¢ cap, $6.25 budget, and the 5-position
    cap are unchanged.
31. Staleness threshold in seconds (host supplies `data_stale`; strategy does not pick a timeout).
32. Whether opposite-side 89% should lock a candidate-side opportunity (M6 locks only the relevant candidate market after first 80).

## Strategy / risk

14. Multi-fill stop basis: **proposed VWAP of actual entry fills** (`ProposedVwapEntryBasis`). Not approved.
15. **Resolved:** 50% of entry VWAP uses integer division of hundredths of a
    cent (`ProposedHalfEntryStop`). Executable sell price is the venue best
    YES bid (already tick-aligned).
16. Reservation ledger replace/amend validity across ClientOrderId changes.
17. Whether a risk approval remains valid across replaces.
18. Simultaneous 89% and stop; exchange vs local timestamp ordering; stale data.
19. Fill racing with 89% cancel.
20. **Resolved:** Partial IOC liquidation is supported. Remainder is retried
    after the working/UNKNOWN liquidation order is terminal. Do not declare
    FLAT without venue fill evidence of zero remaining quantity.
21. Daily “1 MLB position per day” remains unresolved. Confirmed separately:
    at most five simultaneously open MLB positions, one PositionId per GameId,
    and $6.25 per GameId from the weekly snapshot.
22. Multiple games per week each at 12.5% of the same snapshot are permitted,
    subject to the Risk-enforced 5-open-position cap.
23. `PositionId` key: `(strategy, game)` vs including market/side.
24. DST fall-back if Monday 00:00 were ever ambiguous (normally it is not).
25. Economic exposure vs contract quantity when leftover budget cannot buy a whole contract.

## Marked as proposed in code

- VWAP entry basis
- Half-of-basis stop (integer hundredths; executable price = best YES bid)

Fee estimation is injected via `FeeModel`. `ZeroFeeModel` is a **temporary
paper placeholder** and is **not** confirmed Kalshi economics.
