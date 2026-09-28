# Agent rules — Kalshi NBA Path Trade FE

**Source of truth:** `FEATURE_ENGINEERING_SPEC.md` (v3) + high-priority `AMENDMENT_v3.md`.  
**Mode:** Obey §0 axioms first; use Amendment v3 to raise the ceiling without breaking doctrine.

## Hard constraints

| Item | Bound |
|------|-------|
| Reject mass \(r\) | \([0.12, 0.25]\) |
| Reject win rate \(p_R\) | \(\leq 0.55\) |
| Complexity | \(\leq 8\) raw enter features **or** \(\leq 4\) PCs + KNN |
| Ambition | OOS \(p_K \geq 0.82\) at \(r \approx 0.18\) |
| Validation | Game-purged walk-forward; ≥3-era lift; sealed holdout for world-class claims |

## Non-negotiables

1. Second filter only — do not rebuild tip-off / favorite models.  
2. Enter/skip is \(\mathcal{F}_{t_s}\)-measurable; Family E / `hedge_*` never imported into enter_skip.  
3. Versioned state-fair \(f_\nu\) + required `impulse_x_disagreement`, `thin_x_disagreement`.  
4. Residual mining: fold-inner; A/B only; ≤2 features / major version; nested WF.  
5. PCA on A+B+C; pin PC1 impulse / PC2 thin-book; stability ≥ 0.70.  
6. KNN small grid; adaptive \(k\) + train isotonic + regime \(\tau\) only if global \(r\) in band; else skip.  
7. Fee-EV and opposing-bail feasibility are promotion gates, not afterthoughts.  
8. On failed promotion: tighten or return to A–C — **never expand capacity to chase fit**.

## Binding execution order

1. State-fair \(f_\nu\) + interactions → walk-forward  
2. Residual mining / sparse-robust PCA (only if warranted)  
3. Adaptive KNN + regime gates  
4. Lock representation before neighbor/execution search  

No real data ⇒ synthetic E2E only. Deterministic seeds. Write `artifacts/walkforward/summary.json` on every change.
