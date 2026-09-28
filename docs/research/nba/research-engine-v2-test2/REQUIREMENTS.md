# Research-venv dependencies (not production crates)

Interpreter: `/tmp/momento-nba-venv/bin/python`

Always required for Test 2:

- `numpy`, `pyarrow` (already used by Path Engine V1 / GPE V2)

Authorized for Phases 4–5 of this engine only:

- `scikit-learn` — clustering, PCA, logistic, trees, KNN, calibration

Not installed unless a later authorized step needs them:

- `umap-learn`, `hdbscan`, `xgboost` / `lightgbm`

Game Path Engine V2 keeps its **no sklearn** rule. Test 2 does not add
sklearn to production Rust crates or live trading.
