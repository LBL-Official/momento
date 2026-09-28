KATY TEXAS — EXPERIMENT 2
Q4 12:00 / 2H 10:00 — RANGE × AUSTIN EV VS 80/40

RESEARCH ONLY
CANDLE PATH ≠ FILL
CONFIRMATION UNSPENT
AUSTIN NOT REFIT
SEARCH ≠ FREEZE
EXECUTION DISABLED

# 1. QUESTION

At the Q4 12:00 / 2H 10:00 on-grid mark, examine what eventual 80/40 losers look like, then search which yes_bid range and Austin EV cutoff would make mixed 80/40 beat always-80/40.

Grid declared before selection. Objective is mixed 80/40 versus always 80/40.
Houston lock is yes_bid − 80. Missing Austin EV does not hedge.
yes_bid < 41 or t40_already at the mark is already an 80/40 stop.

# 2. LOSER EXAM AT THE MARK

## NCAAB H1_2 Discovery
reached=96 losers=15 winners=81
losers open≥41=15 already<41=0 t40_already=0 terminal t40=15
loser price mean/median 75.73333333333333/74 buckets={'lt_41': 0, '41_50': 0, '51_60': 2, '61_70': 4, '71_80': 2, '81_90': 6, '91_99': 1}
winner price mean/median 83.14814814814815/84 buckets={'lt_41': 0, '41_50': 0, '51_60': 3, '61_70': 9, '71_80': 18, '81_90': 26, '91_99': 25}
loser Austin EV n/mean 15/-6.427957355102387 unavailable=0
winner Austin EV n/mean 81/-0.47064807462506963 unavailable=0

## NCAAB H2_1 Discovery
reached=69 losers=12 winners=57
losers open≥41=12 already<41=0 t40_already=0 terminal t40=12
loser price mean/median 68.08333333333333/73 buckets={'lt_41': 0, '41_50': 1, '51_60': 3, '61_70': 2, '71_80': 5, '81_90': 1, '91_99': 0}
winner price mean/median 63.43859649122807/67 buckets={'lt_41': 4, '41_50': 6, '51_60': 11, '61_70': 18, '71_80': 15, '81_90': 1, '91_99': 2}
loser Austin EV n/mean 0/None unavailable=12
winner Austin EV n/mean 4/-2.822489707015441 unavailable=53

## NBA 604 in-sample Q4
reached=603 losers=99 winners=504
losers open≥41=83 already<41=16 t40_already=22 terminal t40=99
loser price mean/median 62.95959595959596/66 buckets={'lt_41': 16, '41_50': 13, '51_60': 14, '61_70': 13, '71_80': 18, '81_90': 21, '91_99': 4}
winner price mean/median 85.60912698412699/90 buckets={'lt_41': 6, '41_50': 9, '51_60': 11, '61_70': 39, '71_80': 68, '81_90': 130, '91_99': 241}
loser Austin EV n/mean 83/-10.042021653472338 unavailable=16
winner Austin EV n/mean 498/8.983408590477396 unavailable=6

# 3. SELECTED CELLS (PER BOOK)

A: 41–75 / EV<-20.0 hedge=10 (L4/W6) Δmean=0.625 Δsum=60
B: NONE (best Δsum=0 at 41–50 EV<-20.0)
NBA: 41–79 / EV<-20.0 hedge=36 (L17/W19) Δmean=0.05970149253731343 Δsum=36

# 4. MIXED 80/40 UNDER SELECTED CELL OR NONE

A mixed 3.125 vs always 80/40 2.5 hedges=10
B mixed 5.217391304347826 vs always 80/40 5.217391304347826 hedges=0
NBA mixed 4.736318407960199 vs always 80/40 4.676616915422885 hedges=36

# 5. WHAT THIS DOES NOT PROVE

In-sample search. Not confirmation. Not a fill. Not a frozen policy.
Books are never combined. Phase 8 is not justified.

