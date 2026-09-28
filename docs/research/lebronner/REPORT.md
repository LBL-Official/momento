# Lebronner

Named archive of the FIRST75 terminal × path experiment: locked
four-cell, α₇₅, as-of `NO_ASOF_LIFT`, the p=73% held-path
counterfactual S ≈ 62.96%, and the named candle-path EV cases.

Successor name: **SuperASI**. ROLLER +EV alpha decomposition and
in-production 80/40 stop-path EV live in `research/superasi/`.
Lebronner keeps the FIRST75 named −0.37¢ archive.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY
NO FUTURE LABELS IN F_τ
```

Does not change live FIRST01 / 80/81/83/89. Does not retune FIRST75,
FIRST80, or T40. Reconstructs from locked integers; does not rescan
the tape.

Source reports:

- Decomposition: `research/first75_terminal_path_decomp/REPORT.md`
- As-of four-cell: `research/firstq_fourcell_asof_predictor/REPORT.md`
- Slice script: `apps/nba-data/scripts/first75_slice_not40_given_w.py`
- 2026–27 selection program (spec only): `research/lebronner/PROGRAM.md`
- Lossless FIRST75 / FIRST80 tables: `research/lebronner/TABLES.md`
- SuperASI (rename / in-production EV): `research/superasi/README.md`

## 1. Named Lebronner number

FIRST75 is the trigger. The 75¢ quote is assumed to have **cost 80¢**,
so a survivor to expiration yes is **+20¢**. The user-stated stop is
**−35¢**. That −35 is not an 80→40 exit (that would be −40¢).
**s_L = 0**: ¬T40 means expire yes.

S is not the historical pooled 66.70%. It is the held-path
counterfactual at p = 73%: **62.96%**
(exact 0.629647; published display 62.96%).

**EV = 20S − 35(1 − S) = 55S − 35 = -0.37¢** per contract.

Display S = 62.96% gives **-0.37¢** (same to the cent).
Breakeven S = 35/55 = **63.64%**.
62.96% is just under that.

Same S, other locked candle-path payoffs (still s_L = 0, not fills):

| Case | Win | Stop | Formula | EV at S≈62.96% | Breakeven S |
|---|---:|---:|---|---:|---:|
| **Lebronner** | +20¢ | −35¢ | 55S − 35 | **-0.37¢** | 63.64% |
| Native FIRST75 | +25¢ | −35¢ | 60S − 35 | **+2.78¢** | 58.33% |
| True 80→40 | +20¢ | −40¢ | 60S − 40 | **-2.22¢** | 66.67% |

Do not plug 62.96% into the FIRST80 +20/−40 formula and call it
Lebronner. That is a different entry. That row is **−2.22¢**.

If the measured loser-survivor mix is kept (1 of 751 ¬T40 prints,
i.e. P(W|¬T40)=750/751) at this same S, native EV is
**+2.69¢**, not materially
different from the s_L = 0 native +2.78¢. Holding s_L instead of the
survivor mix gives +2.67¢.

Historical pooled tape (S = 66.70%), same native +25/−35/−75 path:
**+4.93¢** per FIRST75.
Not a live number. Not 2026–27.

## 2. Locked historical four-cell (six asked rows)

N = **1126**. One observation per FIRST75 event.

| | ¬T40 | T40 | Terminal |
|---|---:|---:|---:|
| W | **750** (66.6075%) | 121 (10.7460%) | 77.3535% |
| L | 1 (0.0888%) | 254 (22.5577%) | 22.6465% |
| | 66.6963% | 33.3037% | 100% |

p = P(W | FIRST75) = **77.3535%** (871/1126).
α₇₅ = p − 0.75 = **+2.35 pp**.
Wilson 74.82%–79.70% **includes 75%**. Clopper–Pearson 74.79–79.77.
Two-sided exact p = 0.06824. One-sided greater 0.03571, less 0.9695.
Nonzero terminal residual is not established.

s_W = P(¬T40 | W) = **86.1079%** (750/871).
s_L = P(¬T40 | L) = **0.3922%** (1/255); Wilson 0.07–2.19.
S = P(¬T40) = **66.6963%** (751/1126).
P(W ∩ ¬T40) = p · s_W = **66.6075%**.
P(W | ¬T40) = **99.8668%** (750/751) in this
minute-close sample. That is after the path; it is not in F_τ.

The single L ∩ ¬T40 is NBA 2Q. Everywhere else in this table, every
measured loser close-touched 40. Minute-close fact, not a continuity
proof. That is why S is 0.09 pp above the product p · s_W.

## 3. Per-slice FIRST75 (locked)

| Sport | Slice | N | W | P(W) | α₇₅ | Wilson | two-sided p | CI vs 75% | s_W | s_L | W∩¬T40 | joint | S |
|---|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|
| WNBA | 2Q | 128 | 105 | 82.0312% | +7.03 | 74.4782–87.7176 | 0.06665 | includes K | 86.6667% | 0.0000% | 91 | 71.0938% | 71.0938% |
| WNBA | 3Q | 85 | 70 | 82.3529% | +7.35 | 72.9042–89.0037 | 0.1329 | includes K | 84.2857% | 0.0000% | 59 | 69.4118% | 69.4118% |
| NBA | 2Q | 318 | 242 | 76.1006% | +1.10 | 71.1194–80.4588 | 0.6977 | includes K | 85.9504% | 1.3158% | 208 | 65.4088% | 65.7233% |
| NBA | 3Q | 258 | 192 | 74.4186% | -0.58 | 68.7633–79.3574 | 0.8293 | includes K | 86.9792% | 0.0000% | 167 | 64.7287% | 64.7287% |
| NCAAB P5 | 1H second 10 | 204 | 152 | 74.5098% | -0.49 | 68.1146–79.999 | 0.8716 | includes K | 82.8947% | 0.0000% | 126 | 61.7647% | 61.7647% |
| NCAAB P5 | 2H first 10 | 133 | 110 | 82.7068% | +7.71 | 75.3858–88.1913 | 0.04463 | excludes K | 90.0000% | 0.0000% | 99 | 74.4361% | 74.4361% |

Only NCAAB P5 2H first 10 has a Wilson interval that excludes 75%.
The other five include 75%. Weighting is one observation per FIRST75
event, not an unweighted mean of the six rates.

## 4. Held-path counterfactual at p = 73%

Hold s_W and s_L at the historical pooled values. **Not a forecast.**
Asks: if terminal probability deteriorated to 73% while the
conditional path distributions stayed exactly as observed, what is
the new four-cell?

S(p) = s_L + p(s_W − s_L).  dS/dp = s_W − s_L = **0.857158**.
A 1 pp drop in p moves S by about 0.857 pp if path conditionals stay fixed.
Δp from 77.3535% to 73% is −4.3535 pp, so ΔS ≈ −3.73 pp.

| Cell | Historical (p=77.35%) | p=73% held path |
|---|---:|---:|
| W∩¬T40 | 66.6075% | 62.8588% |
| W∩T40 | 10.7460% | 10.1412% |
| L∩¬T40 | 0.0888% | 0.1059% |
| L∩T40 | 22.5577% | 26.8941% |
| **S = P(¬T40)** | **66.6963%** | **62.9647%** |

That 62.96% is this S(0.73), not a new measurement on the tape.

| Terminal P(W) | S(p) if path held |
|---:|---:|
| 80% | 68.9648% |
| 77.35% (hist display) | 66.6963% |
| 75% | 64.6790% |
| **73%** | **62.9647%** |
| 70% | 60.3932% |

If p were set to K = 0.75 and s_W held: joint → 64.58%
(Δ −2.03 pp). **Not a forecast.**

## 5. FIRST80 on the same slices (not retuned)

N = **1182**. Four-cell 883 / 108 / 0 / 191.

p₈₀ = **83.8409%**, s_W,₈₀ = **89.1019%**, s_L,₈₀ = **0.0000%**, joint₈₀ = **74.7039%**.

FIRST80 null for α is K = 0.80, not 0.75.

| Sport | Slice | p₇₅ | s_W,₇₅ | joint₇₅ | p₈₀ | s_W,₈₀ | joint₈₀ |
|---|---|---:|---:|---:|---:|---:|---:|
| WNBA | 2Q | 82.0312% | 86.6667% | 71.0938% | 82.6772% | 84.7619% | 70.0787% |
| WNBA | 3Q | 82.3529% | 84.2857% | 69.4118% | 84.0336% | 94.0000% | 78.9916% |
| NBA | 2Q | 76.1006% | 85.9504% | 65.4088% | 85.0318% | 89.5131% | 76.1146% |
| NBA | 3Q | 74.4186% | 86.9792% | 64.7287% | 82.0690% | 88.6555% | 72.7586% |
| NCAAB P5 | 1H second 10 | 74.5098% | 82.8947% | 61.7647% | 84.4560% | 87.1166% | 73.5751% |
| NCAAB P5 | 2H first 10 | 82.7068% | 90.0000% | 74.4361% | 84.8921% | 91.5254% | 77.6978% |
| **pooled six** | asked rows | 77.3535% | 86.1079% | 66.6075% | 83.8409% | 89.1019% | 74.7039% |

The FIRST80 joint is higher mostly because p is higher (83.8% vs
77.4%), not because s_W is a different kind of object. If 2026–27
terminal p moves toward K, watch whether s_W and s_L stay put.

## 6. As-of four-cell test

The object is P(four-cell | FIRST_q, F_τ), not another retrospective
rate. Locked F_τ: quarter, |score| bin, lead/trail/tie, home — the
same alpha-decomp bins. W and T40 are labels only. Model = TRAIN
empirical four-cell by stratum, Laplace +1. Baseline = TRAIN
unconditional four-cell. Unaligned rows get the unconditional.

Locked rule: ESTABLISHED only if VAL and OOS both beat the baseline
on log-loss, and the OOS paired Δ CI excludes 0 on the negative side.

**Result: `NO_ASOF_LIFT` on both tapes.**

| Tape | OOS n | log-loss model | log-loss uncond | Δ (model − uncond) | Δ 95% |
|---|---:|---:|---:|---:|---|
| FIRST80 | 243 | 0.836 | 0.740 | **+0.096** | +0.052 to +0.139 |
| FIRST75 | 233 | 0.978 | 0.845 | **+0.132** | +0.086 to +0.178 |

The CIs exclude 0 the wrong way: the stratum table is worse than
“ignore the scoreboard and use the historical four-cell.” VALIDATION
says the same. FIRST75 TRAIN is a tiny in-sample dip; that is not
evidence. Q2∪Q3 OOS does not reverse it.

So: we know the pooled four-cell. We do not yet have an as-of state,
from these bins, that estimates a different expected future
distribution better than the unconditional rates.

Details: `research/firstq_fourcell_asof_predictor/REPORT.md`

## 7. What this is not

- Not a live order, fill, or realized P&L.
- Not proof of a tradable inefficiency.
- Lebronner −35¢ is not an 80→40 exit.
- 62.96% is S(p=73%) with path conditionals held, not measured S.
- A high s_W is not an independent FIRST80 path edge.
- L∩¬T40 = 0 is a minute-close measurement, not proof losers cannot skip 40.
- ¬T40 is future information. It is not in F_τ.
- Adding more scoreboard bins after NO_ASOF_LIFT is fishing.
- Path-phenomenon / ITI work is a separate locked program, spec only.
- Not MLB FIRST01.

## 8. Conditional selection program

The 2026–27 research objective is to convert this uncertain,
marginal unconditional edge into a **conditional selection problem**.
Full spec: `research/lebronner/PROGRAM.md`.

Status: **SPEC_ONLY**. Implementation is not authorized. Live is false.
Strategy viability should not require terminal miscalibration.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

