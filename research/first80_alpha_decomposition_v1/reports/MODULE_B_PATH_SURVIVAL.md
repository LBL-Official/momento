# MODULE B — Path survival conditional on winning

P(¬T40|W,FIRST80)=0.8930 n_wins=1019 / n_total=1230.

FIRST75 settled first-reach n=1176; among winners p=0.8536 n_wins=915. Shared games 1175; shared event+ticker 1084/1230 (FIRST80 units that were also first-to-75 on the same ticker, including losses — not comparable to FIRST75 n_wins).

OOS P(¬T40|W) FIRST80=0.8756 n=209 vs FIRST75=0.8359 n=195. Difference 0.0397 approx 95% [-0.0289, 0.1083].

NON_FIRST80: opponent first tradable 80 strictly after FIRST80. n_units=247; among winners p=0.9479 n_wins=211. Comeback-selected; not a FIRST80 clone.

NON_FIRST80 = opponent ticker's first tradable 80 cross strictly after the game's FIRST80 timestamp.

Matched FIRST75 strata: n_strata_adequate=21 n_oos_adequate=4 (thin OOS matching).

Path token: `NO_OOS_CI_SEPARATION`.

A high P(¬T40|W) is not independent edge by itself. Dependence with W is measured in Module C.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
