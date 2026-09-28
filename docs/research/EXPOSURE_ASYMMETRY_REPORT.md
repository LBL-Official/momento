# DRE V2 — Exposure Asymmetry Report

**Date:** 2026-09-03

Question: do states with similar current prices have different conditional distributions once game clock, score, and possession differ?

OOS asymmetry exists (pre-declared: gap ≥ 0.08, n≥40 each side): **TRUE**

RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — THEORETICAL TARGET DELTA ≠ EXECUTED DELTA — THEORETICAL EXPOSURE ≠ ACTUAL EXECUTION — LIVE DEPLOYMENT: NOT AUTHORIZED

## Notes

- OOS price≈60 early vs late P(settle) gap=0.425

## Contrasts

| Split | Band | Slice | n | mean px | P(settle) | P(rec≥10/5) | P(det≥10 end) | P_B0 | P_M3 | h*_B0 A | h*_M3 A |
|-------|------|-------|--:|--------:|----------:|------------:|--------------:|-----:|-----:|--------:|--------:|
| TRAIN | price_60 | early | 393 | 60.2 | 0.611 | 0.066 | 0.758 | 0.277 | 0.200 | 0.000 | 0.000 |
| TRAIN | price_60 | late | 289 | 60.2 | 0.640 | 0.482 | 0.621 | 0.277 | 0.360 | 0.000 | 0.000 |
| TRAIN | price_60 | leading | 8 | — | — | — | — | — | — | — | — |
| TRAIN | price_60 | trailing | 43 | 59.5 | 0.674 | 0.000 | 0.930 | 0.268 | 0.133 | 0.000 | 0.000 |
| TRAIN | price_60 | offense | 787 | 60.1 | 0.648 | 0.216 | 0.713 | 0.276 | 0.271 | 0.000 | 0.003 |
| TRAIN | price_60 | defense | 757 | 60.1 | 0.633 | 0.195 | 0.728 | 0.275 | 0.267 | 0.000 | 0.001 |
| TRAIN | price_50 | early | 125 | 50.0 | 0.464 | 0.056 | 0.656 | 0.169 | 0.107 | 0.000 | 0.000 |
| TRAIN | price_50 | late | 247 | 50.2 | 0.462 | 0.339 | 0.682 | 0.171 | 0.236 | 0.000 | 0.008 |
| TRAIN | price_50 | trailing | 87 | 49.7 | 0.414 | 0.069 | 0.828 | 0.167 | 0.096 | 0.000 | 0.000 |
| TRAIN | price_50 | offense | 445 | 50.1 | 0.452 | 0.238 | 0.751 | 0.170 | 0.180 | 0.000 | 0.009 |
| TRAIN | price_50 | defense | 442 | 50.1 | 0.462 | 0.193 | 0.734 | 0.170 | 0.179 | 0.000 | 0.002 |
| TRAIN | price_70 | early | 1127 | 70.4 | 0.769 | 0.035 | 0.642 | 0.419 | 0.308 | 0.000 | 0.004 |
| TRAIN | price_70 | late | 386 | 70.0 | 0.738 | 0.389 | 0.627 | 0.413 | 0.477 | 0.000 | 0.005 |
| TRAIN | price_70 | leading | 109 | 70.8 | 0.826 | 0.303 | 0.578 | 0.425 | 0.517 | 0.000 | 0.000 |
| TRAIN | price_70 | trailing | 4 | — | — | — | — | — | — | — | — |
| TRAIN | price_70 | offense | 1505 | 70.3 | 0.751 | 0.163 | 0.631 | 0.417 | 0.392 | 0.000 | 0.009 |
| TRAIN | price_70 | defense | 1437 | 70.3 | 0.731 | 0.122 | 0.653 | 0.417 | 0.385 | 0.000 | 0.011 |
| VALIDATION | price_60 | early | 223 | 60.2 | 0.717 | 0.054 | 0.610 | 0.277 | 0.205 | 0.000 | 0.049 |
| VALIDATION | price_60 | late | 215 | 60.2 | 0.614 | 0.439 | 0.670 | 0.277 | 0.323 | 0.000 | 0.000 |
| VALIDATION | price_60 | leading | 9 | — | — | — | — | — | — | — | — |
| VALIDATION | price_60 | trailing | 25 | 60.4 | 0.440 | 0.000 | 0.920 | 0.279 | 0.167 | 0.000 | 0.040 |
| VALIDATION | price_60 | offense | 597 | 60.2 | 0.623 | 0.235 | 0.686 | 0.277 | 0.279 | 0.000 | 0.032 |
| VALIDATION | price_60 | defense | 613 | 60.2 | 0.608 | 0.167 | 0.700 | 0.276 | 0.270 | 0.000 | 0.021 |
| VALIDATION | price_50 | early | 110 | 50.0 | 0.391 | 0.018 | 0.718 | 0.169 | 0.086 | 0.000 | 0.000 |
| VALIDATION | price_50 | late | 183 | 50.1 | 0.486 | 0.432 | 0.710 | 0.170 | 0.214 | 0.000 | 0.000 |
| VALIDATION | price_50 | trailing | 76 | 49.4 | 0.408 | 0.013 | 0.658 | 0.164 | 0.080 | 0.000 | 0.000 |
| VALIDATION | price_50 | offense | 348 | 50.1 | 0.451 | 0.279 | 0.767 | 0.170 | 0.173 | 0.000 | 0.003 |
| VALIDATION | price_50 | defense | 330 | 50.1 | 0.418 | 0.197 | 0.809 | 0.170 | 0.166 | 0.000 | 0.003 |
| VALIDATION | price_70 | early | 992 | 70.3 | 0.715 | 0.023 | 0.659 | 0.418 | 0.317 | 0.000 | 0.015 |
| VALIDATION | price_70 | late | 301 | 70.0 | 0.678 | 0.401 | 0.532 | 0.413 | 0.465 | 0.000 | 0.000 |
| VALIDATION | price_70 | leading | 134 | 71.1 | 0.754 | 0.119 | 0.724 | 0.430 | 0.491 | 0.000 | 0.000 |
| VALIDATION | price_70 | trailing | 61 | 70.5 | 0.672 | 0.016 | 0.377 | 0.421 | 0.191 | 0.000 | 0.000 |
| VALIDATION | price_70 | offense | 1364 | 70.2 | 0.696 | 0.147 | 0.640 | 0.417 | 0.389 | 0.000 | 0.022 |
| VALIDATION | price_70 | defense | 1303 | 70.2 | 0.678 | 0.106 | 0.655 | 0.416 | 0.382 | 0.000 | 0.022 |
| OOS | price_60 | early | 161 | 60.4 | 0.379 | 0.087 | 0.776 | 0.279 | 0.174 | 0.000 | 0.000 |
| OOS | price_60 | late | 102 | 60.1 | 0.804 | 0.420 | 0.520 | 0.276 | 0.327 | 0.000 | 0.000 |
| OOS | price_60 | trailing | 27 | 59.6 | 0.556 | 0.148 | 0.704 | 0.269 | 0.139 | 0.000 | 0.000 |
| OOS | price_60 | offense | 321 | 60.1 | 0.648 | 0.191 | 0.778 | 0.276 | 0.259 | 0.000 | 0.000 |
| OOS | price_60 | defense | 321 | 60.2 | 0.657 | 0.128 | 0.762 | 0.276 | 0.254 | 0.000 | 0.000 |
| OOS | price_50 | early | 65 | 51.1 | 0.462 | 0.123 | 0.815 | 0.178 | 0.086 | 0.000 | 0.000 |
| OOS | price_50 | late | 87 | 50.0 | 0.678 | 0.276 | 0.655 | 0.169 | 0.206 | 0.000 | 0.000 |
| OOS | price_50 | trailing | 41 | 50.7 | 0.537 | 0.122 | 0.732 | 0.176 | 0.082 | 0.000 | 0.000 |
| OOS | price_50 | offense | 206 | 50.1 | 0.573 | 0.248 | 0.767 | 0.170 | 0.169 | 0.000 | 0.000 |
| OOS | price_50 | defense | 199 | 50.2 | 0.533 | 0.171 | 0.804 | 0.171 | 0.161 | 0.000 | 0.000 |
| OOS | price_70 | early | 538 | 70.4 | 0.563 | 0.033 | 0.704 | 0.418 | 0.314 | 0.000 | 0.000 |
| OOS | price_70 | late | 127 | 69.9 | 0.819 | 0.448 | 0.520 | 0.412 | 0.458 | 0.000 | 0.000 |
| OOS | price_70 | leading | 108 | 70.4 | 0.806 | 0.194 | 0.528 | 0.419 | 0.491 | 0.000 | 0.000 |
| OOS | price_70 | trailing | 8 | — | — | — | — | — | — | — | — |
| OOS | price_70 | offense | 754 | 70.1 | 0.679 | 0.166 | 0.637 | 0.415 | 0.389 | 0.000 | 0.020 |
| OOS | price_70 | defense | 715 | 70.2 | 0.669 | 0.116 | 0.666 | 0.416 | 0.385 | 0.000 | 0.022 |
| ALL | price_60 | early | 777 | 60.2 | 0.593 | 0.067 | 0.719 | 0.277 | 0.196 | 0.000 | 0.014 |
| ALL | price_60 | late | 606 | 60.2 | 0.658 | 0.456 | 0.621 | 0.277 | 0.341 | 0.000 | 0.000 |
| ALL | price_60 | leading | 17 | — | — | — | — | — | — | — | — |
| ALL | price_60 | trailing | 95 | 59.7 | 0.579 | 0.042 | 0.863 | 0.271 | 0.144 | 0.000 | 0.011 |
| ALL | price_60 | offense | 1705 | 60.2 | 0.639 | 0.218 | 0.716 | 0.276 | 0.272 | 0.000 | 0.012 |
| ALL | price_60 | defense | 1691 | 60.1 | 0.629 | 0.172 | 0.725 | 0.276 | 0.266 | 0.000 | 0.008 |
| ALL | price_50 | early | 300 | 50.3 | 0.437 | 0.057 | 0.713 | 0.171 | 0.095 | 0.000 | 0.000 |
| ALL | price_50 | late | 517 | 50.2 | 0.507 | 0.361 | 0.687 | 0.171 | 0.223 | 0.000 | 0.004 |
| ALL | price_50 | trailing | 204 | 49.8 | 0.436 | 0.059 | 0.745 | 0.167 | 0.087 | 0.000 | 0.000 |
| ALL | price_50 | offense | 999 | 50.1 | 0.476 | 0.254 | 0.760 | 0.170 | 0.175 | 0.000 | 0.005 |
| ALL | price_50 | defense | 971 | 50.1 | 0.461 | 0.190 | 0.774 | 0.170 | 0.171 | 0.000 | 0.002 |
| ALL | price_70 | early | 2657 | 70.4 | 0.707 | 0.030 | 0.661 | 0.418 | 0.313 | 0.000 | 0.008 |
| ALL | price_70 | late | 814 | 70.0 | 0.729 | 0.402 | 0.575 | 0.413 | 0.470 | 0.000 | 0.003 |
| ALL | price_70 | leading | 351 | 70.8 | 0.792 | 0.199 | 0.618 | 0.425 | 0.499 | 0.000 | 0.000 |
| ALL | price_70 | trailing | 73 | 70.4 | 0.712 | 0.014 | 0.425 | 0.418 | 0.204 | 0.000 | 0.000 |
| ALL | price_70 | offense | 3623 | 70.2 | 0.715 | 0.158 | 0.636 | 0.416 | 0.390 | 0.000 | 0.016 |
| ALL | price_70 | defense | 3455 | 70.2 | 0.698 | 0.115 | 0.657 | 0.416 | 0.384 | 0.000 | 0.018 |

Interpretation is observational. Same-price buckets that differ in terminal rate support a state-conditional exposure architecture **in theory**. They do not authorize execution.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
