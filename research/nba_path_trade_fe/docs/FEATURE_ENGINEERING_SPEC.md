# Kalshi NBA Path Trade — Feature Engineering Specification (v2)

| Field | Value |
|------:|:------|
| Document type | Normative implementation contract for a Cursor coding agent |
| Role | Aj — Feature Engineering |
| Strategy | NBA Kalshi path trade: first touch \(80\) → hold for settlement yes; hard risk at \(40\) via opposing-market limit |
| Objective | Lift kept \(P(\text{win-before-40})\) from \(\approx 0.74\) toward \(\approx 0.80\) under walk-forward evaluation **without overfitting** |
| Status | Ideology locked through **Amendment v3** (highest-level optimization mandate); raw data deferred; this file is the source of truth for FE |
| Spec version | **v3** (includes Amendments v1→v3) |

---

## 0. Values (non-negotiable design axioms)

These axioms override local cleverness. An implementation that violates them is incorrect even if in-sample metrics look strong.

1. **Second filter, not a new trade.** The touch-\(80\) signal is retained. Features exist only to *reject fragile members* of that set.
2. **Residual information only.** Conditioning on \(\{\text{first touch } 80\}\) already encodes much of “favorite / hot live side.” Features must target residual risk of path death through \(40\), not tip-off winner prediction.
3. **Point-in-time integrity.** Enter/skip uses \(\mathcal{F}_{t_{\mathrm{signal}}}\) only. Post-entry path may arm hedges; it may never train enter/skip.
4. **Complexity is a risk control.** Prefer a short reject rule or \(\leq 4\) PCA scores + KNN over rich black boxes. Capacity is part of the loss function.
5. **Honesty of economics.** Report win rate on **kept fills**, reject rate, fill failure (no \(78\)–\(82\) before \(89\)), fees, and opposing-limit bail feasibility. Paper labels without execution realism are not success.
6. **Temporal generalization over peak fit.** Promotion requires multi-era lift with game-purged walk-forward—not full-sample maximization.
7. **Opposing book is first-class.** Bail is a limit on the **other** market; opposing liquidity is a core feature family, not an appendix.
8. **Subtract losers.** Optimize a minority reject mass concentrated on high \(P(\mathrm{hit\,40})\) episodes; do not re-rank the entire book for vanity AUC.

---

## 1. Purpose, payoff geometry, and the filter problem

### 1.1 Base policy \(\pi_0\)

For contract mid (or last trade) process \((P_t)_{t \geq 0}\) on a fixed Kalshi NBA binary:

1. **Signal time**
   \[
   t_{\mathrm{s}} := \inf\{t : P_t \geq 80\}.
   \]
   Desk focus: \(t_{\mathrm{s}}\) falls in Q2 (policy filter; store all periods).

2. **Entry execution.** Rest/join limits on the traded contract in band \([L_e, U_e] = [78, 82]\). Define chase failure if price reaches \(P^{\mathrm{chase}} = 89\) with no fill in band. Let \(t_{\mathrm{e}}\) be fill time, or \(\varnothing\) if unfilled.

3. **Risk / bail.** Level \(B = 40\). Hedge/exit by resting a **limit on the opposing market** near \([L_h, U_h] = [38, 42]\) (not a market give-up on the long).

4. **Economic sketch (desk RR).** From a fill near \(80\): upside \(\approx +20\) to \(100\); downside \(\approx -40\) to \(40\) if bailed there. Hence risk:reward \(\approx 40:20 = 2:1\) **against** the winner, so breakeven win probability
   \[
   p^{\star} = \frac{R}{R+G} \approx \frac{40}{40+20} = \frac{2}{3} \approx 0.67
   \]
   with \(R\) cash risked and \(G\) cash gained on a win (fee-ignorant). Base empirical rate under \(\pi_0\) on filled episodes: \(p_0 \approx 0.74\). Target on **kept** fills: \(p_K \approx 0.80\).

> Implementation must parameterize \(L_e,U_e,P^{\mathrm{chase}},B,L_h,U_h\) and recompute \(p^{\star}\) when bands change. Do not hard-code \(0.67\) into metrics code.

### 1.2 Primary random variable (label)

On filled episodes, define path minimum after entry and settlement indicator \(S\in\{0,1\}\) (yes\(=1\)):

\[
M := \inf_{t > t_{\mathrm{e}}} P_t, \qquad
Y := \mathbf{1}\{S = 1\} \cdot \mathbf{1}\{M > 40\}.
\]

\(Y=1\) is **win-before-40** (settlement yes without printing \(\leq 40\) after entry). This is the sole primary supervised label for enter/skip.

Auxiliary labels (always stored): \(\mathbf{1}\{M\leq 40\}\), \(M\), \(S\), fill indicators, times-to-event.

### 1.3 Enter/skip as a selection operator

Let \(X \in \mathbb{R}^d\) be point-in-time features measurable w.r.t. \(\mathcal{F}_{t_{\mathrm{s}}}\). A filter is a measurable rule

\[
a(X) \in \{0,1\}, \qquad a=1 \Rightarrow \text{take under }\pi_0,\quad a=0 \Rightarrow \text{skip}.
\]

Kept set \(K=\{a=1\}\), reject mass \(r=\mathbb{P}(a=0)\). Denote

\[
p_0 = \mathbb{E}[Y], \quad
p_K = \mathbb{E}[Y \mid a=1], \quad
p_R = \mathbb{E}[Y \mid a=0].
\]

Law of total expectation:

\[
p_0 = (1-r)\, p_K + r\, p_R
\quad\Rightarrow\quad
p_K - p_0 = \frac{r}{1-r}\,(p_0 - p_R).
\]

**Design implication (core math of our values):** lift on kept trades equals reject mass times how *enriched for failures* the rejects are. To move \(p_0=0.74\to p_K=0.80\),

\[
\frac{r}{1-r}(0.74 - p_R) = 0.06
\quad\Rightarrow\quad
r = \frac{0.06}{0.80 - p_R}.
\]

| If rejects have \(p_R\) | Required reject rate \(r\) |
|------------------------|---------------------------|
| \(0.50\) | \(0.06/0.30 = 20\%\) |
| \(0.55\) | \(0.06/0.25 = 24\%\) |
| \(0.60\) | \(0.06/0.20 = 30\%\) |
| \(0.65\) | \(0.06/0.15 = 40\%\) |

**Normative target:** achieve \(p_K\approx 0.80\) with \(r\in[0.15,0.25]\) by driving \(p_R\) toward \(\approx 0.50\)–\(0.55\) (fragile 80s), **not** by rejecting \(40\%+\) of average trades. If OOS \(p_R\) stays near \(p_0\), the features have no residual signal—stop adding capacity.

### 1.4 Decision-theoretic objective (fee-aware later)

Let \(\Pi(Y)\) be PnL of taking \(\pi_0\) on an episode (including fees when wired). Naive filter objective:

\[
\max_a \; \mathbb{E}\big[a(X)\,\Pi(Y)\big]
\quad\text{s.t.}\quad
\mathrm{Complexity}(a)\leq C_{\max},\;
\text{walk-forward constraints}.
\]

Proxy used until full PnL simulator exists:

\[
\max_a \; p_K(a)
\quad\text{s.t.}\quad
r(a)\in[r_{\min}, r_{\max}],\;
\mathrm{Complexity}(a)\leq C_{\max}.
\]

Default: \(r_{\min}=0.10\), \(r_{\max}=0.30\), \(C_{\max}=\) “\(\leq 8\) raw enter features or \(\leq 4\) PCs + KNN.”

### 1.5 Non-goals (explicit)

- Replacing touch-\(80\) with pregame/tip-off classifiers.
- Maximizing full-sample accuracy, unconstrained AUC, or path aesthetics.
- Deep nets / large untuned boosted trees for enter/skip.
- Using \(t>t_{\mathrm{s}}\) information for \(a(X)\).
- Jointly optimizing execution bands and high-dimensional FE in one search.

---

## 2. Filtration, episodes, and leakage

### 2.1 Filtration

Let \(\mathcal{F}_t\) be the desk-observable σ-algebra at time \(t\): trades, books (own + mapped opposing market), and game state if available. Features for enter/skip must be \(\mathcal{F}_{t_{\mathrm{s}}}\)-measurable (or documented \(\mathcal{F}_{t_{\mathrm{e}}-}\) execution features that are **not** used in the pre-signal skip model).

### 2.2 Episode spine

One row = one path episode (never tick-level for modeling):

| Field | Definition |
|-------|------------|
| `episode_id` | Unique id |
| `game_id` | Purge key |
| `market_id` / `opp_market_id` | Traded and opposing contracts |
| `side` | Yes/No (team) side |
| `t_s`, `t_e` | Signal; fill or null |
| `period_at_signal` | Period at \(t_{\mathrm{s}}\) |

**Dedup:** ≤1 episode per `(game_id, market_id, side)` at first qualifying touch.

### 2.3 Labels

| Name | Definition |
|------|------------|
| `Y` / `win_before_40` | \(S=1\) and \(M>40\) on **filled** episodes; else null |
| `hit_40` | \(M\leq 40\) |
| `filled_in_band` | Fill in \([78,82]\) before any print \(\geq 89\) |

Default modeling population: filled episodes only. Optionally learn a separate \(P(\mathrm{fill})\) head; do not mix heads.

### 2.4 Decision heads (do not collapse)

| Head | Action | Measurable w.r.t. |
|------|--------|-------------------|
| `enter_skip` | \(a(X)\) | \(\mathcal{F}_{t_{\mathrm{s}}}\) |
| `fill_quality` | \(P(\mathrm{fill\ in\ band})\) | \(\mathcal{F}_{t_{\mathrm{s}}}\) |
| `hedge_arm` | When to rest opposing \(38\)–\(42\) | \(\mathcal{F}_t\), \(t\ge t_{\mathrm{e}}\) |

### 2.5 Hard leakage rules (agent must enforce)

1. Registry fields: `asof_time ∈ {signal, entry, post_entry}`, `leakage_ok_for_entry: bool`.
2. **Game purge:** if `game_id` intersects a test fold, it is absent from that fold’s train (features, PCA fit, scaler, neighbor index).
3. Walk-forward by game date only for headline metrics; random K-fold forbidden for promotion.
4. Fit scalers / PCA / KNN indexes **inside** each training fold only.
5. Unit test: perturb any tick with stamp \(>t_{\mathrm{s}}\) ⇒ enter_skip feature vector unchanged.

---

## 3. What “good features” mean mathematically

### 3.1 Residual predictive content

We care about features \(X\) that reduce uncertainty in \(Y\) **conditional on the selection event** \(E=\{\text{first touch }80\}\):

\[
I(Y; X \mid E) > 0
\]

(in practice: OOS lift in \(p_K\) under the reject-mass constraint). Features that predict \(S\) unconditionally but are nearly independent of \(Y\mid E\) are **rejected by this spec** (classic favorite bias).

### 3.2 Failure modes we are trying to observe

Define latent fragility archetypes (guides FE; not required latent-variable EM in v1):

1. **Impulse 80:** large short-horizon velocity, discontinuous upticks, low prior time spent ≥70.
2. **Thin-book 80:** wide spreads / tiny size on own or opposing book; volume share spikes on emptiness.
3. **Disagreement 80:** \(P_{t_{\mathrm{s}}}\) far ahead of a versioned state-fair proxy given score/clock.
4. **Bail-infeasible 80:** opposing book cannot realistically rest near \(40\) (execution risk masquerading as “alpha”).

Features are organized to identify these archetypes. PCA should recover directions aligned with them; KNN should find historical episodes with similar archetype mix.

### 3.3 Complexity penalty (operational)

Let \(d_{\mathrm{enter}}\) be the number of enter_skip inputs after selection. Constraint:

\[
d_{\mathrm{enter}} \leq 8 \quad\text{or}\quad d_{\mathrm{PCA}}\leq 4\text{ with KNN on scores}.
\]

Amendments that raise capacity require an explicit RFC in the amendment log and a fresh sealed holdout plan.

---

## 4. Feature store contract

```
data/raw/                 # ticks, books, state (user-provided later)
data/episodes/            # spine
data/features/            # PIT tables by episode_id
data/labels/
artifacts/pca|clusters|knn|walkforward/
features/registry.yaml    # normative registry
```

Each registry entry **must** include: `name`, `family`, `dtype`, `asof_time`, `leakage_ok_for_entry`, `nullable`, `description`, `dependencies`, optional `formula_id`.

---

## 5. Feature families (normative)

Implement **in order A→E**. No orphan enter_skip features outside A–D without amending this document.

Notation: mid process \(P_t\); if mid absent, last trade with `price_source` flagged. Windows are \((t_{\mathrm{s}}-w, t_{\mathrm{s}}]\) unless noted. \(\varepsilon>0\) tiny stabilizer.

---

### Family A — Path-to-trigger (shape of the journey to 80)

**Intent:** \(I(Y; \text{path shape}\mid E)\). Grind-confirmed vs impulse.  
**asof:** `signal` · **leakage_ok_for_entry:** `true`

Let \(P^{(w)}\) be the mid path on \((t_{\mathrm{s}}-w,t_{\mathrm{s}}]\).

| ID | Mathematical definition | Fragility direction (hypothesis) |
|----|-------------------------|----------------------------------|
| `minutes_since_tip` | \((t_{\mathrm{s}} - t_{\mathrm{tip}})/60\) | context |
| `minutes_in_period` | elapsed in current period | context |
| `seconds_since_first_70` | \(t_{\mathrm{s}} - \inf\{t: P_t\geq 70\}\) | small ⇒ fragile |
| `seconds_since_first_75` | analogous for 75 | small ⇒ fragile |
| `n_prints_75_80_10m` | \(\#\{t\in(t_{\mathrm{s}}-10m,t_{\mathrm{s}}]: P_t\in[75,80)\}\) | |
| `drawup_tip` | \(P_{t_{\mathrm{s}}} - \inf_{t\in[t_{\mathrm{tip}},t_{\mathrm{s}}]} P_t\) | |
| `drawup_period` | same within period | |
| `velocity_1m` | \(\big(P_{t_{\mathrm{s}}}-P_{t_{\mathrm{s}}-1m}\big)/1\) | high ⇒ fragile |
| `velocity_5m` | \(\big(P_{t_{\mathrm{s}}}-P_{t_{\mathrm{s}}-5m}\big)/5\) | |
| `velocity_ratio_1_5` | \(\texttt{velocity_1m}/(\|\texttt{velocity_5m}\|+\varepsilon)\) | high ⇒ impulse |
| `path_r2_10m` | \(R^2\) of OLS of \(P_t\) on time in last 10m | low ⇒ chop/spike |
| `max_uptick_gap_5m` | \(\max\) positive jump of mid in last 5m | high ⇒ gap-through |
| `frac_time_ge_70_period` | Lebesgue fraction of period-to-date with \(P\geq 70\) | low ⇒ fragile |
| `path_window_incomplete` | \(1\) if any required window truncated | missingness flag |

**Incomplete windows:** set flag; impute train-fold medians only inside fold.

---

### Family B — Liquidity / microstructure (own + opposing)

**Intent:** false 80s and failed \(40\)-bails cluster in thin/wide books; opposing book is mandatory because bail is opposing-limit.  
**asof:** `signal` · **leakage_ok_for_entry:** `true`

| ID | Definition | Fragility direction |
|----|------------|---------------------|
| `spread_own` | \(a^{\mathrm{own}}-b^{\mathrm{own}}\) at \(t_{\mathrm{s}}\) | high |
| `bid_size_own`, `ask_size_own` | top-of-book sizes | low |
| `volume_1m`, `volume_5m` | traded volume/notional | |
| `volume_share_1m` | \(\mathrm{vol}_{1m}/(\mathrm{vol}_{since\ tip}+\varepsilon)\) | high on thin book |
| `spread_opp` | opposing spread | high |
| `bid_size_opp`, `ask_size_opp` | opposing TOB | low |
| `opp_book_imbalance` | signed opposing imbalance (config side) | |
| `own_opp_spread_ratio` | `spread_own/(spread_opp+ε)` | |
| `book_features_missing` | \(1\) if L2 absent | degrade gracefully—**never fabricate L2** |

Config must map `market_id → opp_market_id` explicitly.

---

### Family C — State–price disagreement

**Intent:** measure \(P_{t_{\mathrm{s}}} - f_{\nu}(\mathrm{score},\mathrm{clock})\), a **versioned** heuristic fair \(f_{\nu}\), not a vendor truth.  
**asof:** `signal` · **leakage_ok_for_entry:** `true` · **Disabled** (all null + `state_features_missing=1`) if score/clock absent—do not noise-fill.

| ID | Definition | Notes |
|----|------------|-------|
| `score_diff` | lead from contract side’s perspective | sign contract |
| `secs_left_period`, `secs_left_game` | | |
| `state_fair` | \(f_{\nu}(\cdot)\in(0,1)\) scaled to cents \([0,100]\) | version `ν` in registry |
| `price_minus_state_fair` | \(P_{t_{\mathrm{s}}} - \texttt{state_fair}\) | high ⇒ market ahead of state |
| `abs_price_minus_state_fair` | absolute | |
| `lead_chg_3m` | Δ score_diff over 3m | |

**Versioning:** changing \(f_{\nu}\) bumps `state_fair_version`, invalidates PCA/KNN artifacts, forces refit.

**Interaction (required reporting):** fragility of disagreement is strongest jointly with Family A impulse metrics—report bivariate OOS tables, not only univariate AUC.

---

### Family D — Regime covariates (strata, not hero predictors)

**Intent:** stratification and regime keys; **not** high-capacity predictors.  
**asof:** `signal` · **leakage_ok_for_entry:** `true` (as covariates)

Examples: `period`, `is_q2`, `home_away`, `back_to_back`, `season_phase`, coarse `dow`/`tip_bucket`, `pregame_favorite_flag`.

**Rules**

- High-cardinality team IDs / embeddings **discouraged** for enter_skip.
- Default: **exclude** raw D categoricals from PCA; use for stratified metrics and regime-specific \(\tau\).
- Cap influence if included (e.g., target encoding with nested CV only—optional, not v1 required).

---

### Family E — Post-entry (hedge arm only)

**asof:** `post_entry` · **leakage_ok_for_entry:** `false`

Examples: running min since entry; time spent ≤60/≤50; hover score in \([38,46]\); rebound from local min; `opp_limit_feasible`.

**Agent rule:** artifacts consuming E must be named `hedge_*` and must not be importable by `enter_skip` pipelines (CI grep / import lints).

---

## 6. Representation: standardization, PCA, regimes

### 6.1 Standardization

Inside each train fold, for continuous enter features with finite variance:

\[
\tilde{X}_j = \frac{X_j - \hat\mu_j}{\hat\sigma_j}.
\]

Binary missingness flags may remain unscaled or separately handled; document choice.

### 6.2 PCA

Let \(\hat\Sigma\) be the train-fold covariance of selected \(\tilde X\) (Families A+B+C; D excluded by default). Eigen-decomposition \(\hat\Sigma = V\Lambda V^\top\), scores \(Z = \tilde X V_{1:m}\), \(m\in\{2,3,4\}\).

**Requirements**

- Export scree (\(\lambda_j\), explained variance ratios).
- Export loadings; **pin orientation** across folds (e.g., force \(\mathrm{loading}(\texttt{velocity_ratio_1_5})\geq 0\) on PC1).
- Measure loading stability across eras (absolute cosine similarity of pinned loadings); warn if \(<0.7\).
- Attempt naming: e.g., PC1 “impulse-to-80”, PC2 “thin/wide book”, PC3 “price ahead of state”.
- **Forbid** \(m>4\) for live enter_skip distance without amendment.

### 6.3 Clustering (regime map)

Cluster on \(Z\) (k-means default). Per cluster report: \(n\), fill rate, \(\hat p(Y=1)\), \(\hat p(M\leq 40)\), medians of key A/B/C features. Regime-specific \(\tau\) allowed; single global \(\tau\) is the baseline control.

---

## 7. Decision layer: KNN as local conditional expectation

### 7.1 Estimator

In standardized score space, for a query \(z\), let \(\mathcal{N}_k(z)\) be the \(k\) training neighbors with distance \(d_i=\|z-z_i\|\) and optional cap \(d_i\leq d_{\max}\). Distance-weighted estimate:

\[
\hat p(z) = \frac{\sum_{i\in\mathcal{N}} w_i Y_i}{\sum_{i\in\mathcal{N}} w_i}, \qquad
w_i = \frac{1}{d_i+\varepsilon}
\]
(or uniform weights as ablation).

If \( |\mathcal{N}| < k_{\min}\) after capping, **abstain** (skip) or fall back to \(\pi_0\)—choice must be config- Explicit; default **skip** (conservative).

### 7.2 Canonical enter rule

\[
a(z)=1 \iff
\big(\text{desk filters pass}\big)
\land \big(\hat p(z)\geq \tau\big)
\land \big(|\mathcal{N}|\geq k_{\min}\big)
\land \big(\text{optional regime gate}\big).
\]

Search \(\tau\) near \(0.78\)–\(0.82\), \(k\) in a **small** grid (e.g., \(\{15,25,35,51\}\)). Fragile regimes may require higher \(\tau\).

### 7.3 Why KNN (value alignment)

KNN estimates \(\mathbb{E}[Y\mid Z=z]\) nonparametrically with capacity controlled by \(k\) and \(d_{\max}\). It matches the doctrine: **borrow only local historical destiny**, rather than fitting a global ranking model that relearns “favorites win.”

### 7.4 Forbidden stacks

GBM+KNN+net stacking for enter_skip; unrestricted \(k,\tau,m\) grids; inventing features from rejected cohort post-hoc without a new walk-forward lock.

---

## 8. Validation, search separation, promotion

### 8.1 Separated search stages (mandatory)

| Stage | Knobs | Freeze before next |
|-------|-------|--------------------|
| A Representation | ≤8 features or PCA \(m\in[2,4]\) | Yes |
| B Neighbor policy | \(k,d_{\max},\tau,k_{\min}\) | Yes |
| C Execution bands | \([L_e,U_e]\), chase \(89\), hedge \([L_h,U_h]\) | Yes on frozen A/B |

### 8.2 Walk-forward

Sort by game date; expanding or rolling train; **purge `game_id`**; optional embargo. Per fold report:

- \(n_{\mathrm{filled}}\), \(r\), \(p_0^{\mathrm{fold}}\), \(p_K\), \(p_R\)
- fill failure rate; fee-aware PnL when simulator exists
- era tag (season phase / year)

### 8.3 Promotion rule (claim ≈80%)

All required:

1. Mean OOS \(p_K \geq 0.80\) **or** pre-registered lift hurdle cleared with bootstrap/CI on sealed holdout.
2. \(r\in[0.10,0.30]\) unless written exception.
3. Lift in **≥2 disjoint eras**.
4. Final holdout segment evaluated **once** for the claim.
5. Complexity constraint held.

**Failure diagnosis:** if \(p_K\) rises only when \(r>0.35\) and \(p_R\approx p_0\), features lack residual signal—return to Families A–C, do not add capacity.

---

## 9. Metrics catalog (implement exactly)

| Metric | Definition |
|--------|------------|
| `base_win_rate` | \(\hat{\mathbb{E}}[Y]\) on fold filled episodes |
| `kept_win_rate` | \(\hat{\mathbb{E}}[Y\mid a=1]\) |
| `rejected_win_rate` | \(\hat{\mathbb{E}}[Y\mid a=0]\) |
| `reject_rate` | \(\hat{\mathbb{P}}(a=0)\) |
| `lift_kept` | `kept_win_rate - base_win_rate` |
| `implied_r_for_target` | \(0.06/(0.80-p_R)\) diagnostic using OOS \(p_R\) |
| `fill_rate` | fraction filled in band before chase fail |
| `neighbor_calibration` | reliability of \(\hat p(z)\) vs realized \(Y\) in bins |

Primary promotion metric: **`kept_win_rate`** under reject-rate constraint.

---

## 10. Cursor agent implementation requirements

### 10.1 Deliverables

1. Episode builder + labeler (§2)  
2. Registry + builders Families A–E (§5)  
3. PIT leakage tests (§2.5)  
4. PCA + cluster reports (§6)  
5. KNN enter_skip + walk-forward (§7–8)  
6. README: how to drop raw paths into `data/raw/`  
7. Synthetic generator for CI when real data absent  

### 10.2 Engineering constraints

- Python package; typed configs; deterministic seeds  
- Asof joins only; no look-ahead  
- Explicit opposing-market map  
- Import lint: `enter_skip` must not import `hedge_*`  

### 10.3 Definition of done

- `pytest` covers first-touch episode logic, \(Y\), leakage immutability  
- One command: synthetic E2E → `artifacts/walkforward/summary.json` with `base_win_rate`, `kept_win_rate`, `rejected_win_rate`, `reject_rate`, era splits  

---

## 11. Doctrine (canonical)

> Engineer \(\mathcal{F}_{t_{\mathrm{s}}}\)-measurable features to expose **fragile first-touch-80** episodes (impulse path, thin own/opposing books, state–price disagreement). Compress with a small, orientation-pinned PCA. Decide with **distance-capped KNN** estimates of \(\mathbb{E}[Y\mid Z]\). Reject a **minority** mass with low \(p_R\) so that
> \[
> p_K = p_0 + \frac{r}{1-r}(p_0-p_R)
> \]
> moves from \(\approx 0.74\) toward \(\approx 0.80\) under game-purged walk-forward. Never rebuild tip-off prediction; never leak post-entry paths into enter/skip; never claim success from full-sample hyperparameter theater; never treat opposing liquidity as optional.

---

## 12. Amendment log

| Date (PT) | Version | Change |
|-----------|---------|--------|
| 2026-09-17 | v1 | Initial FE contract from desk ideology lock |
| 2026-09-17 | v2 | Mathematical payoff/filter identities; residual-information doctrine; formal families; PCA/KNN estimators; separated search; promotion math; values axioms |
| 2026-09-17 | **v3** | Highest-level optimization mandate: upgraded state-fair \(f_\nu\), residual mining protocol, pinned/stability-gated PCA, adaptive calibrated KNN, fee/bail realism gates, sealed-holdout fortress, raised promotion bar \(p_K\geq 0.82\) |

---

## 13. Amendment v3 — Highest-Level Optimization Mandate

**Priority:** HIGH — treat as binding agent instructions.  
**Scope:** Append-only. Does **not** repeal §0 axioms (residual information only, point-in-time integrity, complexity control, minority reject mass, walk-forward honesty).  
**Ceiling raise:** Maximize OOS kept win-before-40 without unconstrained models, post-entry leakage, or full-sample optimization.

### 13.0 Agent copy-block (read first)

```
GOAL: max OOS p_K  s.t.  r∈[0.12,0.25], p_R≤0.55, multi-era lift,
      game-purged WF, d_enter≤8 raw OR ≤4 PCs+KNN
TARGET: stable OOS p_K≥0.82 at r≈0.18

ORDER (do not reorder):
  1) state-fair f_ν + required interactions
  2) full walk-forward; measure lift
  3) residual mining + sparse/robust PCA (only if warranted)
  4) adaptive KNN + regime gates
  5) LOCK representation before further neighbor/execution search

ON FAILURE: residual-signal deficiency → return to Families A–C;
            capacity/overfit → tighten, do NOT expand.
```

### 13.1 Goal, constraints, and filter math

Maximize out-of-sample kept win-before-40 rate \(p_K\) subject to:

| Constraint | Bound |
|------------|-------|
| Reject mass | \(r \in [0.12, 0.25]\) |
| Reject cohort quality | \(p_R \leq 0.55\) |
| Enter complexity | \(d_{\mathrm{enter}} \leq 8\) raw **or** \(\leq 4\) PCs + KNN |
| Validation | Game-purged walk-forward; multi-era lift |
| Ambition target | Stable OOS \(p_K \geq 0.82\) with \(r \approx 0.18\) |

Filter identity (doctrine-invariant):

\[
p_K = p_0 + \frac{r}{1-r}\,(p_0 - p_R)
\quad\Leftrightarrow\quad
p_R = p_0 - \frac{1-r}{r}\,(p_K - p_0).
\]

**Implication at** \(p_0=0.74\), \(r=0.18\), \(p_K=0.82\):

\[
p_R = 0.74 - \frac{0.82}{0.18}\cdot 0.08 \approx 0.376.
\]

Rejects must be **strongly** failure-enriched. If OOS \(p_R\) cannot break \(\approx 0.55\), **do not** chase \(p_K\geq 0.82\) by inflating \(r\).

### 13.2 Family C — versioned state-fair \(f_\nu\) (highest leverage)

1. Implement \(f_\nu\) strictly better than naive score/clock heuristics.
2. **Minimum viable:** logistic or isotonic regression trained **only** on historical games through the **previous season** relative to the evaluation game (no same-season weight leakage).
3. **PIT inputs:** score differential from contract side; seconds left in period; seconds left in game; period; possession if available.
4. **Output:** scaled to \([0, 100]\).
5. Registry field: `state_fair_version` (\(\nu\)). **Any change invalidates all PCA/KNN artifacts and forces full refit.**
6. **Required interactions** (must be \(\mathcal{F}_{t_s}\)-measurable):

| Feature ID | Formula |
|------------|---------|
| `impulse_x_disagreement` | `velocity_ratio_1_5 * max(0, price_minus_state_fair)` |
| `thin_x_disagreement` | `(spread_own + spread_opp) * abs_price_minus_state_fair` |

7. **Reporting mandate:** bivariate OOS tables of each interaction vs \(Y\) in **every** walk-forward fold (quintile or bin heat rates).

### 13.3 Residual feature mining (Families A+B only; train-fold inner)

Inside **each training fold only**:

1. Fit a small elastic-net or sparse logistic on current A+B+C predicting \(Y\).
2. Score residual correlations against a **pre-declared** transform library: log, rank, winsorized, ratios, short rolling ranks (candidates must already be \(\mathcal{F}_{t_s}\)-measurable A/B constructs).
3. Promote **≤ 2** new features per major version **iff** they survive **nested** walk-forward **and** improve \(p_R\) enrichment (lower \(p_R\) at fixed \(r\) band).

**Forbidden:** post-\(t_s\) information; team embeddings; high-cardinality IDs; full-sample mining; >2 promotions per major version.

### 13.4 Representation (still \(\leq 4\) PCs)

1. After fold-inner standardization, fit PCA on A+B+C (**Family D excluded** from PCA columns).
2. Optional ablation: sparse PCA or robust PCA; keep the variant with higher **loading stability** (pinned-loading cosine \(\geq 0.75\) across eras).
3. **Forced orientation pinning:**
   - **PC1:** positive on `velocity_ratio_1_5` and `max_uptick_gap_5m` (impulse).
   - **PC2:** positive on `spread_own + spread_opp`; negative on size features (thin book).
4. Export and version the pinned loading matrix with artifacts.
5. **Warn** if era-wise stability \(< 0.70\); do not promote a representation that fails sealed-evaluation stability.

### 13.5 Decision layer — highest-performance KNN (capacity controlled)

Default: distance-weighted KNN in \(m\in\{3,4\}\) PC space.

| Upgrade | Rule |
|---------|------|
| Adaptive \(k\) | Global \(k\) baseline; ↑\(k\) in dense regions; ↓\(k\) or **abstain** in sparse regions |
| Local calibration | Isotonic regression of \(\hat p(z)\) vs realized \(Y\), **train-fold only** |
| Regime-gated \(\tau\) | Cluster-specific \(\tau\) via k-means on PCs **iff** global \(r\) stays in \([0.12, 0.25]\) |

**Small grid only:** \(k\in\{15,25,35,51\}\), \(\tau\in[0.77,0.84]\), \(d_{\max}\) from a training distance percentile.  
**Insufficient neighbors:** **skip** (conservative default).

### 13.6 Economic & execution realism (first-class)

Lightweight path simulator for every filled episode must compute:

1. Realized PnL **including Kalshi fees**
2. Feasibility of opposing-limit bail near \([38,42]\) given opposing book when the long first reaches **55 / 50 / 45**
3. Fill-quality metrics

**Primary** promotion metric: `kept_win_rate` (\(p_K\)).

**Secondary gates (required for highest-level promotion):**

- Fee-adjusted EV(kept) \(>\) fee-adjusted EV(base policy \(\pi_0\))
- Opposing-limit bail success on **rejected** set is not materially worse than on **kept** set

### 13.7 Validation & anti-overfit fortress

1. Walk-forward: expanding or rolling by game date; full `game_id` purge; **1–2 game embargo**.
2. Lift required in **≥ 3 disjoint eras** (e.g., early / mid / late season; playoffs as an era if available).
3. “World-class” claim ⇒ **single** evaluation on a **sealed holdout season** never touched during feature or hyperparameter search.
4. Every feature/representation change must write `artifacts/walkforward/summary.json` with at least:

| Field | Meaning |
|-------|---------|
| `base_win_rate` | \(p_0\) |
| `kept_win_rate` | \(p_K\) |
| `rejected_win_rate` | \(p_R\) |
| `reject_rate` | \(r\) |
| `lift_kept` | \(p_K - p_0\) |
| `implied_r_for_target` | \(r\) implied by identity for target \(p_K\) given observed \(p_R\) |
| era breakdowns | per-era \(p_0,p_K,p_R,r\) |
| `loading_stability` | pinned-loading cosines |
| `ev_kept_fee_adj`, `ev_base_fee_adj` | secondary gate inputs |
| `bail_success_kept`, `bail_success_rejected` | secondary gate inputs |

### 13.8 Agent engineering requirements

1. Pass leakage unit tests: perturb any tick \(> t_s\) ⇒ enter/skip vector **unchanged**.
2. Import lint: `enter_skip` must not import `hedge_*` or post-entry modules.
3. Deterministic seeds everywhere.
4. One-command synthetic E2E produces full walk-forward summary with **no real data**.
5. `registry.yaml` is sole source of truth; every feature declares `asof_time`, `leakage_ok_for_entry`, and `dependencies`. State-fair features also declare `state_fair_version`.

### 13.9 Promotion rule — “highest level” (sealed holdout)

Promote **only if all** hold on the sealed holdout:

1. \(p_K \geq 0.82\) **or** clear pre-registered lift with bootstrap CI  
2. \(r \in [0.12, 0.25]\)  
3. \(p_R \leq 0.55\)  
4. Positive lift in \(\geq 3\) eras  
5. Complexity constraint satisfied  
6. Fee-aware EV(kept) \(>\) EV(base)  
7. Loading stability \(\geq 0.70\) and neighbor calibration reasonable  

**On any failure:** diagnose residual-signal deficiency → return to Families A–C; or capacity/overfit → **tighten, do not expand**.

### 13.10 Binding execution order

1. Upgraded state-fair \(f_\nu\) + interaction features  
2. Full walk-forward; measure lift  
3. Residual mining + sparse/robust PCA (only if step 2 warrants)  
4. Adaptive KNN + regime gates  
5. **Lock representation** before further neighbor or execution-band search  

### 13.11 Still forbidden

- Unconstrained enter/skip models (large GBMs, deep nets)  
- Post-entry leakage into enter/skip  
- Full-sample optimization / sealed-holdout peeking during search  
- Inflating \(r\) outside \([0.12, 0.25]\) to cosmeticize \(p_K\)  
- Team embeddings / high-cardinality identity features  

---

*End of specification (v3).*
