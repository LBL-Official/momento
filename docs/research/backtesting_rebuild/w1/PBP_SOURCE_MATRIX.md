# PLAN-W1-A6 — PBP source matrix (catalog only)

**Status:** COMPLETE as a **catalog**. No files downloaded.  
**PLAN-W1-A8 Kalshi re-query is not this document.**

W1 does not acquire play-by-play. Local lake PBP = **UNAVAILABLE**.

| Candidate | Kind | License / ToS | Download in W1 | Notes |
|-----------|------|---------------|----------------|-------|
| MLB Stats API | Official HTTP JSON | MLB ToS; not approved for this program | **Forbidden** | Common `gamePk` identity source. Not present in-repo. |
| Baseball Savant / Statcast | Public web + files | Site ToS; redistribution unclear | **Forbidden** | Not a substitute for licensed PBP. |
| Licensed MLB feed (TBD) | Vendor | Requires CEO + legal | **Forbidden** | Not chosen. |
| Invented / scraped sample PBP | — | — | **Forbidden** | Would fail the waterfall. |
| Kalshi historical REST | Market, not PBP | Kalshi API terms | Not PBP | Trades/candles/metadata only. |

## License gate (PLAN-W1-A6-S2)

Download is **forbidden** until:

1. CEO authorizes a named source.
2. License/ToS for that source is recorded as approved.
3. A later waterfall (CTO-W2) owns ingest into a **new** raw tree (never overwrite Data-Real gzip).

`IdentityStubV1.mlb_game_pk` remains **null**. Mapping is not W1.

Recovery query rows in `availability_audit.json` have `launched=false`.
