# Research invariants

LIVE_EXECUTION_CHANGED = False

## NBA

- `INV5_UNIVERSE` ok=True nba n=1230
- `INV1_NO_FAKE_L4` ok=True 
- `INV3_MODEL_ID` ok=True 
- `INV2_NO_GAP_FILL_E1` ok=True 
- `INV6_NO_LOOKAHEAD` ok=True same_or_prior_bar_touches=0

INV4 identity_ok=True

## NCAAB P5

- `INV5_UNIVERSE` ok=True ncaab n=721
- `INV1_NO_FAKE_L4` ok=True 
- `INV3_MODEL_ID` ok=True 
- `INV2_NO_GAP_FILL_E1` ok=True 
- `INV6_NO_LOOKAHEAD` ok=True same_or_prior_bar_touches=0

INV4 identity_ok=True

Splits remain TRAIN ≤2025-12-31, VAL ≤2026-03-15, else OOS. No parameter was selected on OOS. DRE_BASELINE_V1 uses pre-registered H=40 exact.
