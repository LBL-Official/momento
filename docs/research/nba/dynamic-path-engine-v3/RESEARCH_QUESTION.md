# Research question

V1: Can pre-entry **market** state predict the 40 barrier? Not robustly.

V2: Can **static game path at first-80** predict the 40 barrier? Not robustly.

V3 does not rescue those entry filters.

The object is the **conditional evolution of the market path after entry**:

```text
P(K_{t+Δ} | K_t, G_t, H_t, τ_t)
```

specifically the short-horizon barrier hazard

```text
P(hit 40 during next Δ minutes | alive above 40 at t, Z_t)
```

and whether a **research** early-warning / exit policy could improve
risk-adjusted economics versus hold-to-40.

Momento does not need to predict the NBA winner.

A negative result (no robust dynamic signal) is a successful outcome.

Prediction quality ≠ trading utility. A model that fires one minute before
40 may be economically useless; a well-calibrated warning 15 minutes early
with acceptable false-positive cost might not be.
