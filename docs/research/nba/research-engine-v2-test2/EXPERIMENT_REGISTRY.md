# Experiment registry schema

Append-only. Failed hypotheses stay in the ledger.

| Field | Required |
| --- | --- |
| experiment_id | yes |
| timestamp | yes |
| dataset_version | `NBA_RESEARCH_ENGINE_V2_TEST2` |
| feature_set | family name or `full` |
| target | `Y_40_CLOSE` |
| model | model0 / l2_logistic / l1_logistic / tree / knn / blend |
| hyperparameters | yes when fitted |
| train_period | `game_date ≤ 2025-12-31` BUILD |
| validation_period | through `2026-03-15` CHOOSE |
| oos_period | after `2026-03-15` VERIFY |
| random_seed | 42 |
| git_commit_hash | when available |
| results | brier / AUC / ECE / EV / acceptance |
| class | `EXPLORATORY` \| `CONFIRMATORY` \| `PRODUCTION_CANDIDATE` |

Exploratory univariate tests use Benjamini–Hochberg FDR at `q = 0.10`.
Mark `DISCOVERED AFTER MULTIPLE SEARCHES` on search-derived claims.

Never fit weights, Platt, or isotonic on VALIDATION or OOS.
