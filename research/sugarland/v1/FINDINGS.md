# Sugarland findings

Universe `SUGARLAND_PREGAME_V1`. Spec `dee6d030687de349f09b197a73cda05c945bdd5a48018525f20f150f0d865ccf`.

Research only. Execution disabled. Quote differences are not fills.

## First result — around 80¢ at 24h and 48h

Same contract, bid at the frozen horizon versus the bid at T−30. Return on entry ask is the quote-based spread comparison (exit bid minus entry ask, divided by entry ask). It is not an executable return.

| Sport | Horizon | Eligible N | Endpoint N | Mean Δpp | Median Δpp | 95% interval | Share rising | Return on entry ask | Discovery mean (N) | Validation mean (N) |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---|
| WNBA | 48h | 20 | 8 | 15.1250 | 18.0000 | [9.4286, 17.8892] | 0.8750 | 0.1659 | UNAVAILABLE (0) | 15.1250 (8) |
| WNBA | 24h | 32 | 17 | 5.7059 | 15.0000 | [-5.3337, 13.8130] | 0.7647 | 0.0556 | UNAVAILABLE (0) | 5.7059 (17) |
| WNBA | union 48h else 24h | 45 | 20 | 6.5500 | 15.0000 | [-0.7004, 13.1149] | 0.7500 | 0.0626 | UNAVAILABLE (0) | 6.5500 (20) |
| NBA | 48h | 63 | 63 | 3.3651 | 4.0000 | [2.2539, 4.4167] | 0.7143 | -0.0004 | 5.0000 (23) | 2.4250 (40) |
| NBA | 24h | 133 | 133 | 0.4361 | 0.0000 | [0.0142, 0.8832] | 0.4887 | -0.0151 | 0.6353 (85) | 0.0833 (48) |
| NBA | union 48h else 24h | 172 | 172 | 1.5407 | 1.0000 | [0.9869, 2.0970] | 0.5814 | -0.0093 | 1.5800 (100) | 1.4861 (72) |
| NCAAB | 48h | 1 | 1 | -2.0000 | -2.0000 | INSUFFICIENT_SAMPLE | 0.0000 | -0.0476 | UNAVAILABLE (0) | -2.0000 (1) |
| NCAAB | 24h | 35 | 34 | 3.8824 | 2.0000 | [2.5585, 5.7783] | 0.7941 | -0.0136 | 6.4000 (5) | 3.4483 (29) |
| NCAAB | union 48h else 24h | 35 | 34 | 3.8529 | 2.0000 | [2.5119, 5.7600] | 0.7941 | -0.0143 | 6.4000 (5) | 3.4138 (29) |
| MLB | 48h | 0 | 0 | UNAVAILABLE | UNAVAILABLE | [UNAVAILABLE, UNAVAILABLE] | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE (0) | UNAVAILABLE (0) |
| MLB | 24h | 0 | 0 | UNAVAILABLE | UNAVAILABLE | [UNAVAILABLE, UNAVAILABLE] | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE (0) | UNAVAILABLE (0) |
| MLB | union 48h else 24h | 0 | 0 | UNAVAILABLE | UNAVAILABLE | [UNAVAILABLE, UNAVAILABLE] | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE (0) | UNAVAILABLE (0) |

Return on entry ask divides each contract by its own entry ask. Whether appreciation exceeded the spread is the unweighted cent comparison in the audit below, on the same complete endpoint sample.

A one-contract interval is labeled INSUFFICIENT_SAMPLE. It is not a confidence interval.

## Cohort A — first observed above 70¢

Membership uses the first valid pregame quote only. A later crossing of 70¢ does not enter.

| Sport | Eligible N | Endpoint N | Mean Δpp | Median Δpp | 95% interval | Share rising | Return on entry ask | Discovery mean (N) | Validation mean (N) |
|---|---:|---:|---:|---:|---|---:|---:|---|---|
| WNBA | 180 | 134 | 0.6791 | 1.5000 | [-2.7262, 3.8070] | 0.5746 | -0.0452 | 1.8081 (99) | -2.5143 (35) |
| NBA | 359 | 359 | 3.6462 | 6.0000 | [2.2954, 4.9012] | 0.7827 | -0.0197 | 4.6289 (159) | 2.8650 (200) |
| NCAAB | 322 | 312 | 3.1923 | 4.0000 | [2.2747, 4.1530] | 0.7404 | -0.0434 | 1.3482 (112) | 4.2250 (200) |
| MLB | 83 | 83 | -5.2410 | -1.0000 | [-7.7213, -2.5641] | 0.3614 | -0.0938 | -0.5333 (60) | -17.5217 (23) |

## Did the bid usually rise?

- WNBA at 48h: mean bid change 15.1250¢ on endpoint N 8 (eligible 20), share rising 0.8750. A majority of endpoint contracts rose.
- WNBA at 24h: mean bid change 5.7059¢ on endpoint N 17 (eligible 32), share rising 0.7647. A majority of endpoint contracts rose.
- NBA at 48h: mean bid change 3.3651¢ on endpoint N 63 (eligible 63), share rising 0.7143. A majority of endpoint contracts rose.
- NBA at 24h: mean bid change 0.4361¢ on endpoint N 133 (eligible 133), share rising 0.4887. Fewer than half of endpoint contracts rose.
- NCAAB at 48h: endpoint N is 1. The interval is INSUFFICIENT_SAMPLE.
- NCAAB at 24h: mean bid change 3.8824¢ on endpoint N 34 (eligible 35), share rising 0.7941. A majority of endpoint contracts rose.
- MLB at 48h: endpoint N is 0. The fresh around-80 quote at that horizon is UNAVAILABLE. That is not a zero return.
- MLB at 24h: endpoint N is 0. The fresh around-80 quote at that horizon is UNAVAILABLE. That is not a zero return.

## Endpoint and spread audit

This section does not replace the frozen primary tables. Quote-based cents per contract are `b30 − a0`. That equals bid appreciation `b30 − b0` minus entry spread `a0 − b0`, on the same complete endpoint sample.

### Spread-adjusted cents

| Sport | Horizon | Complete N | Mean bid change ¢ | Mean entry spread ¢ | Mean quote profit ¢ | Profit 95% interval |
|---|---:|---:|---:|---:|---:|---|
| WNBA | 48 | 8 | 15.1250 | 1.6250 | 13.5000 | [8.1393, 16.4286] |
| WNBA | 24 | 17 | 5.7059 | 1.2353 | 4.4706 | [-6.6886, 12.6260] |
| NBA | 48 | 63 | 3.3651 | 3.3810 | -0.0159 | [-0.9302, 0.8889] |
| NBA | 24 | 133 | 0.4361 | 1.6692 | -1.2331 | [-1.6385, -0.7879] |
| NCAAB | 48 | 1 | -2.0000 | 2.0000 | -4.0000 | INSUFFICIENT_SAMPLE |
| NCAAB | 24 | 34 | 3.8824 | 5.0588 | -1.1765 | [-2.4752, 0.4483] |
| MLB | 48 | 0 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| MLB | 24 | 0 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |

### Missing endpoints

Each missing primary endpoint has one label. A boundary candle is a two-sided mark inside the spread cap that the frozen rule drops because a side is 0 or 10000.

| Sport | Horizon | Eligible | Endpoint | Missing | Absent | Stale | Boundary | Excessive spread | Clock | Other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| WNBA | 48 | 20 | 8 | 12 | 0 | 0 | 12 | 0 | 0 | 0 |
| WNBA | 24 | 32 | 17 | 15 | 0 | 0 | 14 | 1 | 0 | 0 |
| NBA | 48 | 63 | 63 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| NBA | 24 | 133 | 133 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| NCAAB | 48 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| NCAAB | 24 | 35 | 34 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| MLB | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| MLB | 24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### Boundary-bid arithmetic sensitivity

Label `BOUNDARY_BID_ARITHMETIC_SENSITIVITY`. Primary endpoints stay. Contracts whose only fresher mark is a boundary bid are added for cent arithmetic. Log-odds stay unavailable when that bid is 0 or 10000.

- WNBA 48h: added 12 boundary marks (endpoint N 20 of eligible 20). Mean bid change 17.5000¢ (N 20, 95% [15.5412, 18.8947]). Mean quote profit 15.7000¢ (N 20, 95% [13.9037, 17.0563]). Log-odds unavailable on 0 retained bids.
- WNBA 24h: added 14 boundary marks (endpoint N 31 of eligible 32). Mean bid change 12.0645¢ (N 31, 95% [5.1551, 16.6452]). Mean quote profit 10.8065¢ (N 31, 95% [3.8497, 15.4843]). Log-odds unavailable on 0 retained bids.
- NBA 48h: added 0 boundary marks (endpoint N 63 of eligible 63). Mean bid change 3.3651¢ (N 63, 95% [2.2539, 4.4167]). Mean quote profit -0.0159¢ (N 63, 95% [-0.9302, 0.8889]). Log-odds unavailable on 0 retained bids.
- NBA 24h: added 0 boundary marks (endpoint N 133 of eligible 133). Mean bid change 0.4361¢ (N 133, 95% [0.0142, 0.8832]). Mean quote profit -1.2331¢ (N 133, 95% [-1.6385, -0.7879]). Log-odds unavailable on 0 retained bids.
- NCAAB 48h: added 0 boundary marks (endpoint N 1 of eligible 1). Mean bid change -2.0000¢ (N 1, 95% INSUFFICIENT_SAMPLE). Mean quote profit -4.0000¢ (N 1, 95% INSUFFICIENT_SAMPLE). Log-odds unavailable on 0 retained bids.
- NCAAB 24h: added 0 boundary marks (endpoint N 34 of eligible 35). Mean bid change 3.8824¢ (N 34, 95% [2.5585, 5.7783]). Mean quote profit -1.1765¢ (N 34, 95% [-2.4752, 0.4483]). Log-odds unavailable on 0 retained bids.
- MLB 48h: added 0 boundary marks (endpoint N 0 of eligible 0). Mean bid change UNAVAILABLE (N 0). Mean quote profit UNAVAILABLE (N 0). Log-odds unavailable on 0 retained bids.
- MLB 24h: added 0 boundary marks (endpoint N 0 of eligible 0). Mean bid change UNAVAILABLE (N 0). Mean quote profit UNAVAILABLE (N 0). Log-odds unavailable on 0 retained bids.

### Paired 48h → 24h → T−30

Selection uses the 48h around-80 bid only. A contract that leaves that band by 24h stays in the pair. The separate 48h and 24h headline rows are different populations.

| Sport | Paired N | Dropped missing 24h | Dropped missing T−30 | Left the band by 24h | 48h→24h ¢ | 24h→T−30 ¢ | 48h→T−30 ¢ |
|---|---:|---:|---:|---:|---|---|---|
| WNBA | 8 | 0 | 12 | 3 | 1.2500¢ (N 8, 95% [-1.8917, 4.7143]) | 13.8750¢ (N 8, 95% [9.5714, 17.1675]) | 15.1250¢ (N 8, 95% [9.4286, 17.8892]) |
| NBA | 63 | 0 | 0 | 39 | 2.4286¢ (N 63, 95% [1.3280, 3.5073]) | 0.9365¢ (N 63, 95% [0.1663, 1.7657]) | 3.3651¢ (N 63, 95% [2.2539, 4.4167]) |
| NCAAB | 1 | 0 | 0 | 0 | -1.0000¢ (N 1, 95% INSUFFICIENT_SAMPLE) | -1.0000¢ (N 1, 95% INSUFFICIENT_SAMPLE) | -2.0000¢ (N 1, 95% INSUFFICIENT_SAMPLE) |
| MLB | 0 | 0 | 0 | 0 | UNAVAILABLE (N 0) | UNAVAILABLE (N 0) | UNAVAILABLE (N 0) |


## Concentration of positive cohort-A bid changes

- WNBA: top 10 positive contracts account for 0.3417 of the summed positive Δpp (positive N 77).
- NBA: top 10 positive contracts account for 0.0813 of the summed positive Δpp (positive N 281).
- NCAAB: top 10 positive contracts account for 0.1040 of the summed positive Δpp (positive N 231).
- MLB: top 10 positive contracts account for 0.5000 of the summed positive Δpp (positive N 30).

## What this does not show

- Listing time is UNAVAILABLE. First observed is not the market open.
- Stored scheduled start is a sensitivity. It is not an entry-time snapshot, including when it matches actual start.
- The quote-based benchmark has no depth, latency, or fill. Estimated fees are a separate labeled layer and are not in the tables above.
- WNBA ledger fees are UNAVAILABLE. Realized P&L is reported only with exit linkage and settlement evidence. Otherwise the ledger section is confirmed acquisition cost plus a hypothetical valuation.
- Lead time from the primary clock is descriptive. It is not an entry-time feature.
- Injury, lineup, and pitching timestamps were not used. If that feed is absent, the price path is unexplained.
- MLB uses FIRST_PBP_EVENT when a play timestamp exists. That is not a schedule snapshot. Games without a clock stay UNMEASURABLE.
- NCAAB cohort N is the canonical candle subset. Phase 8 parquet counts are inventory only.
- Dashboard `#/sugarland` shows NBA and NCAAB. WNBA and MLB are in this file and are not that dashboard.

A null or negative bid change is a completed result.
