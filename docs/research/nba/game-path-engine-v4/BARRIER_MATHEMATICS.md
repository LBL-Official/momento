# Barrier mathematics

Primary economic barrier remains 40¢ close-path after FIRST-80.

Also store the **adverse-path distribution** at entry:

\[
P(\min_{u>\tau_{80}}K_u\le x\mid S_{\tau_{80}})
\]

for \(x\in\{75,70,65,60,55,50,45,40\}\) using post-entry **close** prices.
Wick-40 is secondary and not mixed into the primary 40 definition.

Time-to-40: minutes from entry to first close \(\le 40\), else censored
at last alive / close.

Competing **overlapping** post-entry events (not a partition):

- A: hit close-path 40
- B: recover to 90 (post-entry close \(\ge 90\))
- C: settle YES
- D: settle NO

A and D can coincide. Do not treat them as independent.

Dynamic short-horizon labels on the alive panel: barrier in next 5/10/20/30/60
minutes. Features at \(t\) must not use those future minutes.
