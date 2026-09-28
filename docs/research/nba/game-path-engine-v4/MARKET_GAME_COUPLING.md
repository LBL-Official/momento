# Market–game coupling

Central object: empirical sensitivity, **not** a Black–Scholes Greek.

TRAIN (pre-80 consecutive 1-minute steps with observed \(\Delta d\neq 0\)
or including zeros with a robust specification):

\[
\Delta K_t=\beta_0+\beta_1\Delta d_t+\beta_2\tau_t+\beta_3(\Delta d_t\,\tau_t)+\varepsilon_t.
\]

Coefficients frozen after TRAIN. Applied out of sample to form

\[
\text{Market-Game Residual}=\Delta K^{obs}-E[\Delta K\mid\Delta d,\tau].
\]

Optional curvature term \(\beta_4(\Delta d)^2\) is fit on TRAIN and kept
only if VALIDATION Brier of the residual feature improves vs the linear
coupling — otherwise dropped. Sparse cells are not differentiated.

Empirical theta: mean \(\Delta K\) in TRAIN minutes with \(\Delta d=0\),
by remaining-time buckets. Holding score approximately constant.

Do not call these \(\Delta,\Gamma,\Theta\) of an option model. They are
coordinate names for empirical maps.
