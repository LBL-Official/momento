# 77 → Economic Ridge / EV Surface

```text
RESEARCH ADDENDUM / THESIS
LIVE EXECUTION CHANGED          = FALSE
DOES NOT CHANGE LIVE FIRST01 / 80 / 81 / 83 / 89
DOES NOT AUTHORIZE NBA OR MLB LIVE ENTRY
DOES NOT START W9
DOES NOT CREATE AN 18TH SYSTEM
NOT_ARMED
RESEARCH_REGISTERED             ≠ LIVE_ARMED
CANDLE PATH                     ≠ FILL
FIRST77 THEORETICAL EV          = DERIVED FOUR  N=933
FIRST80 THEORETICAL EV          = DERIVED FOUR  N=936
FIRST75 THEORETICAL EV          = DERIVED FOUR  N=913
                                ≠ ASKED-SIX     N=1182
FIRST77 933                     ≠ FIRST75 913 ≠ FIRST80 936
FIRST81 940                     ≠ FIRST83 973
74 / 76 / 78 / 79 BOOKS         = NOT_RUN
EXITS 27 / 53                   = NOT_RUN
COMMON-INTERSECTION LADDER      = NOT_RUN
82¢ AND 76¢ VWAP EXAMPLES       = ILLUSTRATIVE  NOT OBSERVED
MISSING L2                      = SOURCE_UNAVAILABLE
```

Desk: `BDR # MOMENTO SYSTEMS`  
Route: `http://127.0.0.1:5190/#/bdr/77-ridge`  
Owner system: `hedging_analysis`

Follow-on to [`BDR_ACQUISITION_CORRIDOR.md`](BDR_ACQUISITION_CORRIDOR.md) (75 vs wait-80) and [`BDR_LIQUIDATION_CORRIDOR.md`](BDR_LIQUIDATION_CORRIDOR.md) (exit 45→35). Staged-acquisition update: [`BDR_STAGED_ACQUISITION.md`](BDR_STAGED_ACQUISITION.md). This note does not replace those theses. It does not arm live trading.

Texas integer sources: `#/texas-77` (FIRST77), `#/` (FIRST80), `#/texas-75` (FIRST75). Ledger EV ≠ fill ≠ live EV.

---

## 77 is now the most interesting entry threshold shown

Not because a production bot should become `BUY @ 77 / STOP @ 40`.

Because the locked FIRST77 candle-path book is already in the same economic neighborhood as FIRST80 — **and** 77 gives about three cents more acquisition runway than waiting for 80.

That is stronger than the 75 argument, which needed a 0.4–0.6¢ execution hurdle to offset a weaker path population.

```text
75  →  signal dilution; local mid-tile jaggedness
77  →  ridge already ≈ FIRST80, plus runway
80  →  still the confirmation phenomenon, later to start working
```

---

## Locked FIRST77 path ladder (N=933, gain 23)

Derived four. Not asked-six. `EV = 23S − L(1−S)`, `L = 77 − stop`. Same N=933 on 77/25–77/50. Verified against `/choosin-texas/universe-77`.

Texas path-ladder rank on this 25–50 grid is `77/40`, then `77/45`, `77/35`, `77/30`, `77/50`, `77/25`. **77/40 is the boxed maximum on that ladder.**

| Cell | Survivors | EV / trade | Δ vs 77/40 |
| ---: | ---: | ---: | ---: |
| **77/40** | **655/933** | **+5.1222¢** | boxed max |
| 77/45 | 629/933 | +5.0793¢ | −0.0429 |
| 77/35 | 675/933 | +5.0257¢ | −0.0965 |
| 77/30 | 693/933 | +4.9936¢ | −0.1286 |
| 77/50 | 595/933 | +4.8864¢ | −0.2358 |
| 77/25 | 700/933 | +4.2701¢ | −0.8521 |

Survivors on the same N=933:

```text
25  700/933
30  693/933
35  675/933
40  655/933
45  629/933
50  595/933
```

77/55 is **not** on this ladder for ranking. It is entry `< 83` only, N=883, +3.8381¢. Not apples-to-apples.

Texas also locks extra mid-tiles 33/37/43/47. They are not mixed into the boxed path-ladder rank. They appear in the surface below because they are already locked. They are not a reason to freeze a bot on 43.

---

## Shape: 77/35–45 is one ridge

```text
77/35  +5.0257¢
77/40  +5.1222¢
77/45  +5.0793¢
```

All three sit inside **0.10¢**. That is one broad economic ridge, not three competing stops.

Do **not** optimize a production bot to an exact 40¢ stop.

40 is the center of the exit corridor. It is not a sacred price.

---

## FIRST80 contrast (N=936, gain 20) — different population

Label stays on. 933 ≠ 936. Do not stack these as one book.

Verified against `/choosin-texas/universe`. Path-ladder:

| Cell | EV / trade |
| ---: | ---: |
| 80/35 | +5.0694¢ |
| 80/30 | +5.0427¢ |
| 80/45 | +4.9573¢ |
| 80/40 | +4.8718¢ |
| 80/25 | +4.7756¢ |
| 80/50 | +4.7222¢ |

80/55 is entry `< 86` only, N=905, +3.7901¢. Not apples-to-apples.

---

## 77 vs 80 at the same barriers

Their arithmetic. Keep it. Label the N split.

```text
77/40 − 80/40  =  5.1222 − 4.8718  =  +0.2504¢
77/45 − 80/45  =  5.0793 − 4.9573  =  +0.1220¢
77/35 − 80/35  =  5.0257 − 5.0694  =  −0.0437¢
```

Candle-path economics are already ≈ FIRST80.

**And** 77 gives ~3¢ more acquisition runway.

That pair is the claim. It is stronger than the 75 argument (which needed a 0.4–0.6¢ live-execution hurdle just to break even with wait-until-80 on the 35–45 corridor).

---

## FIRST75 is signal dilution, not a magical 33

N=913, gain 25. Verified against `/choosin-texas/universe-75`.

Best mid-tile they cite: **75/33 +4.7459¢**.

That jump above 75/35 (+4.4962¢), 75/37 (+4.4370¢), and 75/40 (+4.4962¢) is **local jaggedness**. Discrete barrier noise on ~900 games. It is not a magical stop and not a reason to retarget live liquidation to 33.

75 remains the weaker path population. It opens a window. It is not the ridge.

---

## Production interpretation — research concept, NOT_ARMED

```text
LIVE EXECUTION = FALSE
NOT BUY @ 77 / STOP @ 40
```

```text
FIRST77
  → ACQUISITION WINDOW 77 → 80-ish (work maker liquidity; do not chase 84–86)
  → POSITION / NORMAL HOLD
  → DISTRESS / LIQUIDATION WINDOW 45 → 35 (direct sell / opponent hedge / passive→aggressive)
  → FLAT / NEUTRAL
```

77 = start of execution, not a promise every contract fills at 77.

40 = center of the exit corridor, not a sacred stop.

Do not treat the older acquisition-corridor 82¢ / 76¢ VWAP examples as measured. Those remain illustrative. `P_acq` is still `NOT_RUN`.

---

## EV surface — complete matrix is NOT_RUN

Desired collector (do **not** start it from this note):

```text
Entry ∈ {74, 75, 76, 77, 78, 79, 80, 81}
Exit  ∈ {25, 27, 30, 33, 35, 37, 40, 43, 45, 47, 50, 53, 55}
```

Then find a plateau, not a single max.

```text
EV_max  =  max measured cell on the finished surface
robust 0.10  =  { cells | EV ≥ EV_max − 0.10¢ }
robust 0.25  =  { cells | EV ≥ EV_max − 0.25¢ }
```

ROLLER's job is to discover a **broad region**. Momento Live must not crush that region back into two brittle point estimates.

Research rectangle already visible on the locked books:

```text
77–80  →  35–45
```

Execution should exploit flexibility **inside** that rectangle.

74 / 76 / 78 / 79 books do not exist in Texas. Exits 27 and 53 are not locked. Those cells stay `?` / `NOT_RUN`. FIRST81 and FIRST83 now exist as companion tiles; their cells are filled below. Do not invent 74/76/78/79. Common-intersection audit is `NOT_RUN` — see [`BDR_STAGED_ACQUISITION.md`](BDR_STAGED_ACQUISITION.md).

---

## Surface table — locked Texas cells only

Candle-path ledger ¢ / trade. Different rows are different populations.

`*` = 55 uses the entry-cap subset (75/55 N=868, 77/55 N=883, 80/55 N=905, 81/55 N=917, 83/55 N=959). Not the same N as the rest of that row.

| τ \ stop | 25 | 27 | 30 | 33 | 35 | 37 | 40 | 43 | 45 | 47 | 50 | 53 | 55* |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 74 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 75 | +3.5597 | NOT_RUN | +4.3757 | +4.7459 | +4.4962 | +4.4370 | +4.4962 | +4.4600 | +4.4578 | +4.2760 | +4.1347 | NOT_RUN | +3.3295 |
| 76 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 77 | +4.2701 | NOT_RUN | +4.9936 | +5.1190 | +5.0257 | +4.9035 | +5.1222 | +5.1608 | +5.0793 | +4.9925 | +4.8864 | NOT_RUN | +3.8381 |
| 78 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 79 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 80 | +4.7756 | NOT_RUN | +5.0427 | +5.0395 | +5.0694 | +5.0577 | +4.8718 | +5.1410 | +4.9573 | +4.7682 | +4.7222 | NOT_RUN | +3.7901 |
| 81 | +5.3564 | NOT_RUN | +5.4468 | +5.4574 | +5.4468 | +5.3947 | +5.1489 | +5.4170 | +5.2500 | +4.9606 | +4.8511 | NOT_RUN | +3.9346 |
| 83 | +5.4378 | NOT_RUN | +5.4173 | +5.3628 | +5.5098 | +5.6043 | +5.4687 | +5.5766 | +5.2425 | +4.9620 | +4.6156 | NOT_RUN | +4.0959 |

33 / 37 / 43 / 47 on 75 / 77 / 80 are Texas extra mid-tiles, already locked. They are filled because they exist. They are not a 74–81 collector. 77/43 (+5.1608) sitting next to boxed 77/40 (+5.1222) is more ridge, not a new point estimate.

---

## Caveat — keep this on the desk

**Candle-path theoretical EV ≠ fill EV.**

Path survival ≠ settlement ≠ fills.

The ~5¢ gross plateau is a candle-path identity on three different FIRST books. Fees, queue, gap, maker fill rate, and missed max-entry trades are not in any cell.

Next measured phase: how much of that ~5¢ survives realistic maker entry plus dynamic exit.

Missing L2 = `SOURCE_UNAVAILABLE`. Do not fabricate Kalshi depth. Do not treat a candle path as a fill.

---

## Head-quant conclusion

> **77 is the most interesting locked entry threshold shown. On the derived-four path ladder, 77/40 is +5.1222¢ (N=933) and 77/35–45 is one ridge inside 0.10¢. That book already ≈ FIRST80 (N=936) at the same barriers — 77/40 beats 80/40 by +0.2504¢ — and 77 adds ~3¢ of acquisition runway. That is stronger than the 75 dilution argument. The production concept is not BUY@77 / STOP@40. It is FIRST77 → work 77→80-ish → hold → liquidate 45→35 → flat. The unfinished 74–81 × 25–55 surface stays NOT_RUN. ROLLER should find the plateau; Momento Live must not turn a rectangle back into two brittle points. RESEARCH_REGISTERED ≠ LIVE_ARMED. LIVE EXECUTION = FALSE.**

Strategy still proposes. Risk still approves. Execution still executes.
