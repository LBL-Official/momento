# Market dynamics

\(M_t\) uses 1-minute candle top-of-book. No L2. No invented last-trade
if the warehouse last-print is unused.

`estimated_mid=(bid+ask)/2` is **estimated**, not a transaction.

Velocity / acceleration of bid-close \(K_t\) in cents, windows 1/3/5/10/15m.

Normalized momentum:

\[
v^*_{t,w}=\frac{K_t-K_{t-w}}{\sigma_{K,w}+\varepsilon}.
\]

Volatility is a **1-MINUTE CANDLE VOLATILITY PROXY**, not true RV.
V3 showed raw vol is not a robust filter. V4 asks whether vol is
dangerous **conditional on game state**:

\[
\sigma_K\times|d|,\quad \sigma_K\times v^{score},\quad \sigma_K\times\tau.
\]

Those interactions live in Model 3. They are not automatic trading rules.
