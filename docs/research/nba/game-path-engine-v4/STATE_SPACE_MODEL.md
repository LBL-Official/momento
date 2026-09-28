# State-space model

Do not treat the table as an unexplained bag of columns.

At each aligned time \(t\),

\[
S_t=[G_t,M_t,P_t,D_t,E_t]
\]

| Block | Meaning | Implementation prefix |
| --- | --- | --- |
| \(G_t\) | Basketball physical state | `game_` |
| \(M_t\) | Contract / microstructure | `market_` |
| \(P_t\) | How game and market arrived | `path_` |
| \(D_t\) | Velocities, accelerations, instability | `dyn_` |
| \(E_t\) | Economics of continuing the trade | `econ_` |

Coupling terms (`coupling_`) are derived from \(G\) and \(M\) jointly.
They are not a sixth independent physical system; they are the map
\(\partial K/\partial G\) estimated empirically.

Every game block carries alignment provenance:

```text
alignment_method
alignment_confidence
alignment_reason
feature_maximum_source_timestamp
state_timestamp
entry_timestamp
```

MEDIUM is never upgraded to HIGH.

Primary modeling sample: **one \(S_{\tau_{80}}\) per first-80 trade**.
The post-entry panel exists to estimate coupling, path integrals after
entry, barrier timing, and dynamic descriptions — not to pretend 95k
minutes are 95k independent games.
