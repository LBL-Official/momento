# DRE V3 — Exposure Objectives

All objects are **theoretical retained exposure**. They are not executable policies.

## Accounting

W(h) = 5000 + h × X cents, X ∈ {+20, −80} from the 80¢ entry proxy. No sale at the current bid is assumed.

## N1 — Expected utility

EU(h) = p U(W0+20h) + (1−p) U(W0−80h)

CRRA γ ∈ {0.5, 1, 2, 3, 5, 10} (log at 1). CARA α per dollar ∈ {0.005, 0.01, 0.02, 0.05}.

VALIDATION selects the (kind, param) whose h* maximizes realized CRRA γ=2 — not raw U of the candidate utility.

Selected: **crra** param=**2.0** (VALIDATION).

## N2 — Tail risk

CVaR_q of representative candle-path drawdown from exclusive bins.

- N2_LINEAR = h×E[X] − λ h CVaR — control; still linear → corners expected.
- N2_EU = EU(h) minus a utility-unit penalty for a sure candle-path CVaR hit of size λ h CVaR.

Selected: kind=**eu** q=**0.05** λ=**0.0**

## N3 — Recovery optionality

Path moments adjust theoretical wealth, then CRRA γ=2 is applied:

W_yes = W0 + 20h + λ_R h E[UU]
W_no  = W0 − 80h − λ_D h E[DD]

Bin representatives, not fills. λ_R / λ_D are weights, not premia.

Selected λ_R=**1.0** λ_D=**0.0**

## N4 — Asymmetric power

h E[X] − a h^p E[DD^p] + b h E[UU], p ∈ {2, 3}.

Selected p=**2.0** a=**0.01** b=**0.05**

## Grid and ties

h ∈ {0.00, 0.05, …, 1.00}. Near-optimal set within 1e-08. Ties preserve higher h. Plateaus are recorded, not hidden.

## Forbidden language

These are not optimal exits, hedges, or fills.
