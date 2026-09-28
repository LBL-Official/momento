# Amendment v3 — Highest-Level Optimization Mandate

**Use:** High-priority instruction set for a Grok/Cursor coding agent implementing Kalshi NBA Path Trade FE.  
**Doctrine lock:** Residual information only · point-in-time integrity · complexity control · minority reject mass · walk-forward honesty.  
**Parent:** `FEATURE_ENGINEERING_SPEC.md` (§0 axioms still win on conflict).

---

## Goal

Maximize OOS \(p_K\) (kept win-before-40) under:

- \(r \in [0.12, 0.25]\)
- \(p_R \leq 0.55\)
- multi-era lift
- game-purged walk-forward
- \(d_{\mathrm{enter}} \leq 8\) raw **or** \(\leq 4\) PCs + KNN

**Target:** stable OOS \(p_K \geq 0.82\) with \(r \approx 0.18\).

\[
p_K = p_0 + \frac{r}{1-r}(p_0 - p_R)
\]

At \(p_0=0.74\), \(r=0.18\), \(p_K=0.82\) ⇒ \(p_R \approx 0.376\). If you cannot enrich failures that hard, do not fake the target by raising \(r\).

---

## 1. State-fair model (Family C — highest leverage)

- Versioned PIT model \(f_\nu\) strictly better than naive score/clock.
- **MV:** logistic or isotonic; train only through **previous season**; inputs: score diff (contract side), seconds left period, seconds left game, period, possession if available; output \([0,100]\).
- Registry: `state_fair_version`. Change ⇒ invalidate PCA/KNN; full refit.
- **Required interactions:**
  - `impulse_x_disagreement = velocity_ratio_1_5 * max(0, price_minus_state_fair)`
  - `thin_x_disagreement = (spread_own + spread_opp) * abs_price_minus_state_fair`
- Report bivariate OOS tables of these vs \(Y\) every walk-forward fold.

## 2. Residual feature mining (A+B only)

- **Train-fold inner only:** elastic-net / sparse logistic on A+B+C → residual correlations vs pre-declared transforms (log, rank, winsorized, ratios, short rolling ranks).
- Promote **≤2** features per major version if nested WF survives and \(p_R\) enrichment improves.
- **Forbidden:** post-\(t_s\), team embeddings, high-cardinality IDs, full-sample mining.

## 3. Representation (≤4 PCs)

- PCA on standardized A+B+C (D excluded).
- Optional sparse/robust PCA; keep higher loading stability (cosine ≥ 0.75 across eras).
- Pin: PC1 ← +`velocity_ratio_1_5`, +`max_uptick_gap_5m`; PC2 ← +spreads, −size.
- Version pinned loadings; warn if stability < 0.70.

## 4. KNN decision layer

- Distance-weighted KNN in 3–4 D PC space.
- Upgrades: adaptive \(k\); train-fold isotonic calibration; regime-gated \(\tau\) (k-means) iff global \(r\) stays in band.
- Grid: \(k\in\{15,25,35,51\}\), \(\tau\in[0.77,0.84]\), \(d_{\max}\) from train percentile.
- Insufficient neighbors → **skip**.

## 5. Economic & execution realism

- Path simulator per fill: fee-inclusive PnL; opposing-limit feasibility near [38,42] when long first hits 55/50/45; fill quality.
- Primary: `kept_win_rate`. Secondary: fee-EV(kept) > fee-EV(base); bail success on rejects not materially worse than kept.

## 6. Validation fortress

- Expanding/rolling by game date; full `game_id` purge; 1–2 game embargo.
- Lift in ≥3 disjoint eras.
- World-class claim ⇒ one sealed holdout season never touched in search.
- Each change updates `artifacts/walkforward/summary.json`:
  `base_win_rate`, `kept_win_rate`, `rejected_win_rate`, `reject_rate`, `lift_kept`, `implied_r_for_target`, era breakdowns, loading stability (+ EV and bail fields).

## 7. Agent engineering

- Leakage tests: perturb tick \(>t_s\) ⇒ enter/skip unchanged.
- Import lint: no `hedge_*` / post-entry in `enter_skip`.
- Deterministic seeds; one-command synthetic E2E summary without real data.
- `registry.yaml` SSOT: `asof_time`, `leakage_ok_for_entry`, `dependencies` (+ `state_fair_version` where applicable).

## 8. Promotion (“highest level”) — sealed holdout

All required:

1. \(p_K \geq 0.82\) (or pre-registered bootstrap CI lift)  
2. \(r \in [0.12, 0.25]\)  
3. \(p_R \leq 0.55\)  
4. Positive lift in ≥3 eras  
5. Complexity OK  
6. Fee-aware EV(kept) > EV(base)  
7. Loading stability ≥ 0.70; neighbor calibration reasonable  

Else: diagnose signal deficiency (A–C) vs overfit (**tighten, don’t expand**).

## Execution order (binding)

1. State-fair \(f_\nu\) + interactions  
2. Full walk-forward; measure lift  
3. Residual mining + sparse/robust PCA  
4. Adaptive KNN + regime gates  
5. Lock representation before further neighbor/execution search  

**Do not** add unconstrained models, post-entry leakage, or full-sample optimization.
