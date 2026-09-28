# ECONOMICS_CONTRACT

Default research-capital overlay (editable on Results, not written to a lock, not sent to Risk):

- Bankroll $20,000
- Allocation 5% = $1,000
- Contracts = `floor(allocation_cents / entry_ref_cents)`
- Example: `floor(100000 / 70) = 1428`, deployed $999.60, residual $0.40

Never round up. Allocation capital ≠ maximum contractual loss unless the payoff exposes the whole allocation. Not Kelly.

| EV | Source | Label |
|----|--------|-------|
| Observed path | mean `hyp_pnl_cents` | OBSERVED |
| Book-price | classified WIN/LOSS × (chip − entry_ref) | HYPOTHETICAL |
| Settlement | measured Kalshi YES/NO × (100−K, −K) | DERIVED or UNAVAILABLE |

Dollar observed EV uses `(Σ πᵢ × contracts) / n`, not a rounded mean × contracts.

Fees on rows are UNAVAILABLE. Cost grid is a symmetric per-contract overlay (0–5¢). Break-even cost = gross EV.

Hold-to-settlement with missing terminal: **TERMINAL DATA UNAVAILABLE**, not 0, not path EV.
