# Mathematical foundation

The contract resolves \(X_T\in\{0,1\}\). The trader experiences the path
\(K_0,K_1,\ldots,K_T\). Those are different prediction objects.

Entry is the frozen FIRST-80 event \(\tau_{80}\). The critical path event is

\[
\tau_{40}=\inf\{u>\tau_{80}:K_u\le 0.40\}.
\]

Primary object:

\[
q=P(\tau_{40}<T\mid\mathcal{F}_{\tau_{80}}).
\]

Dynamic object:

\[
P(\tau_{40}\le t+\Delta\mid \tau_{40}>t,\mathcal{F}_t).
\]

Frozen baseline (do not rebuild): \(n=1230\), \(k=320\),
\(q_0=26.016\%\), survival \(73.984\%\).

Gross research payoff \(+1R\) survive / \(-2R\) barrier:

\[
EV=1-3q,\qquad q^*=1/3.
\]

At baseline \(EV\approx +0.2195R\). Barrier-risk margin \(=1/3-q\approx 7.3\) pp.

Classification accuracy is not the objective. A classifier that predicts
“no 40 for everyone” can be ~74% accurate and economically empty.

Information set \(\mathcal{F}_t\) may only use timestamps \(\le t\).
1-minute candles cannot order events inside a minute (`SAME_BAR_1M_LIMITATION`).
Per-play wall clock is unavailable; game time uses
`PERIOD_BOUNDED_LINEAR_GAME_CLOCK`. Tip is `gameTimeUTC`, never Kalshi open.
