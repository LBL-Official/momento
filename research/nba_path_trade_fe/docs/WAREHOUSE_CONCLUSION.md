# Warehouse close — enter/skip representation archived

Research close for A+B+C + ≤4 PCs + KNN on 2025–26 warehouse touch-80s.
Not a live rule. Candle path ≠ fill. L2 = SOURCE_UNAVAILABLE. Fee EV = null.

## What was tested
Game-purged WF, pooled n=797, frozen features. Baseline τ=0.77: p0=0.715,
p_K=0.691, p_R=0.726, r=0.695. Filter is anti-edge.

One decision-layer grid only (k=25, no adaptive-k, no new features):
τ ∈ {0.80, 0.82, 0.84, 0.86, 0.88, 0.90}. Higher τ raised r (0.78→0.99)
and never produced p_K>p0 or p_R<p0.

## Conclusion
Residual enter/skip does not raise EV vs take-all touch-80. Rejects are
not failure-enriched. EV-max under no-overfit:

**BASELINE: enter/skip=ALWAYS (unfiltered touch-80), desk 78–82 / bail-40.**

`filter_status=INACTIVE_NO_RESIDUAL_EDGE`. `promotion=FAILED`.
Ambition p_K≥0.82 is not claimable and is not the next milestone.
Do not add features, PCs, residuals, or L2 proxies. Halt.

See `artifacts/walkforward/summary.json` (`conclusion`, `decision_grid`).
