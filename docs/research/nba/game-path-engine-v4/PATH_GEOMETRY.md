# Path geometry

Two contracts at 80¢ can have different histories.

**Arrival path (pre \(\tau_{80}\)).** Time from 50/60/70 to 80, reversals,
total variation, path efficiency

\[
PE=\frac{|K_{\tau_{80}}-K_{start}|}{\sum|\Delta K|}.
\]

Near 1: directional. Near 0: turbulent. Same construction for score
differential \(PE_G\).

**Post-entry integrals** (discrete, only while alive above 40):

\[
A_t=\sum_{s=\tau_{80}}^t \max(K_{s-1}-K_s,0),\quad
F_t=\sum \max(K_s-K_{s-1},0),\quad
PA_t=\frac{A_t}{A_t+F_t+\varepsilon}.
\]

MAE / MFE from entry bid. Drawdown \(DD_t=K^{max}_t-K_t\) with velocity
and acceleration on the 1-minute grid.

80→75→80 is not 80→95→80 even if both sit at 80 later.
