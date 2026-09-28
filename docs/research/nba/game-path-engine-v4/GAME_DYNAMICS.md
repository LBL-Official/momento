# Game dynamics

\(G_t\) is the physical basketball state for the FIRST-80 team.

**Score differential.** \(d_t=\) team score \(-\) opponent score.

**Time-normalized experimental form** (not assumed truth):

\[
d_t^*=\frac{d_t}{\sqrt{\tau^{\text{game remaining}}+c}},\quad c=60\text{s}.
\]

A 10-point lead with 2 minutes left is not the same state as a 10-point
lead with 32 minutes left.

**Velocity / acceleration** (discrete, on the 1-minute market grid):

\[
v^{score}_{t,w}=\frac{d_t-d_{t-w}}{w},\qquad
a^{score}_{t,w}=\frac{v_{t,w}-v_{t-w,w}}{w}.
\]

Windows: 1m, 5m, 10m, current quarter. “One possession” is **not**
observed; a 24-second proxy is not invented. Last-two-scoring-event
velocity is stored separately when PBP snaps exist.

**Volatility.** Rolling stdev and range of \(d\) over 3m/5m/10m, plus
stdev of \(\Delta d\). This is a score-path volatility proxy, not a
continuous-time diffusion parameter.

**Lead-stability index** (candidate; coefficients frozen on TRAIN):

\[
LSI_t=\frac{|d_t|}{1+\sigma_{d,5m}+\lambda|v^{score}_{5m}|+\gamma|a^{score}|}.
\]

\(\lambda,\gamma\) are chosen on TRAIN from \(\{0.5,1,2\}\). Not a unique
physical law.

**Uncertainty proxy** (experimental):

\[
U^{game}_t=\frac{\sqrt{\tau^{game}+c}\,(1+\sigma_{d,5m})\,(1+n^{lead\ changes}_{10m})}{1+|d_t|}.
\]

This is not a market probability.

Pace: total points and points per elapsed game minute when clocks exist.
