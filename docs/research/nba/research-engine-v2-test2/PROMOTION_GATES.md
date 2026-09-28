# Promotion gates — Test 2

This spec’s **final scientific verdict is A–D** (see
`NBA_80_40_ENGINE_V2_TEST_2_REPORT.md`).

| Verdict | Meaning |
| --- | --- |
| A | Meaningful trade classes discovered and independently validated |
| B | Some descriptive structure exists, but not enough evidence for production filtering |
| C | No meaningful structure beyond the baseline has been demonstrated |
| D | The available data cannot answer the question reliably |

This run: **B**. Production: **NO FILTER**.

The earlier engine-internal A–F labels (simple-vs-complex, coupling, etc.) remain
in `TEST_2_REPORT.md` as a research note. They do not change live 80/40.

## Production status (exactly one)

`NO FILTER` | `RESEARCH-ONLY FILTER` | `CANDIDATE PRODUCTION FILTER`

A production candidate on OOS requires all of:

1. Risk-bucket or class separation (usable n)
2. Calibration in the traded region
3. `EV_accepted > EV_unconditional` (~+0.219 R)
4. Acceptance ≥ 50% of first-80 opportunities

V2 Test 2 never changes live execution.


## Production status (exactly one)

`NO FILTER` | `RESEARCH-ONLY FILTER` | `CANDIDATE PRODUCTION FILTER`

A production candidate on OOS requires all of:

1. Risk-bucket or class separation (usable n)
2. Calibration in the traded region
3. `EV_accepted > EV_unconditional` (~+0.219 R)
4. Acceptance ≥ 50% of first-80 opportunities

V2 Test 2 never changes live execution.

Failed hypotheses remain in the experiment registry as
`REJECTED — OVERFIT / NON-ROBUST` or `DISCOVERED AFTER MULTIPLE SEARCHES`.
