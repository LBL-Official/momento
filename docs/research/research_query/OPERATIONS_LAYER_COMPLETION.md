# Operation layer — completion report

Nine previously blocked Entry operations are implemented on the existing full-scan engine:

1. Cross  
2. Break  
3. Reversion  
4. Bounce  
5. Recovery  
6. Above  
7. Below  
8. Maximum Touch  
9. Minimum Touch  

`EntryOp` is First–Nth Touch plus those nine. `operation_semantics_version = 1.0.0`. `CODE_VERSION = research_query_v1.2_ops`.

Locked Bounce: examples win. `next` is the next tradable candle. Timestamp = confirmation bar. `79→80→79` and `81→80→81` count.

Locked Recovery: AND uses the prior entry bar as anchor. Standalone uses the first tradable close. Equality at P does not invent a side. Standalone Recovery without direction is INVALID, not n=0.

Locked extrema: running max/min over the full game/ticker tradable-close series, then snap + period/clock.

Exit is two books: WIN and LOSS. Hold-to-expiration is settlement YES on WIN and NO on LOSS. WIN prices cannot be under the entry reference; LOSS prices cannot be over it. First later hit classifies the trade. Untagged drafts keep `path_true`.

Frozen FIRST80 remains the exact current tuple. Tagged WIN/LOSS drafts are `generic_query`.

Exit-path bounce / revert / maximum_move / minimum_move / never_reach execute on post-entry tradable close (`operation_semantics_version = 1.1.0`).

Confirmations:

- FIRST80 unchanged
- Frozen executor unchanged
- Live trading unchanged
- No L2
- No fills
- No Terminal Efficiency
- No new Phase 7 features
