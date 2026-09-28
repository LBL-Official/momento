# DRE V4 — Model Card

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V4`
**Date:** 2026-09-03

## Intended use

Offline research into state-conditional forward candle-path distributions.

Not for order routing, stops, hedges, exposure, or live risk.

## Data

Frozen FIRST-80 + PADE V1 panel + DRE V2 comparison probabilities. Chronological game-level TRAIN/VAL/OOS.

## Features

Nested B0–M5 as-of families. No future labels. No `h*`. No `target_delta`.

## Limitations

Candle resolution. Clustered rows. Elapsed-time clock horizons. Last-possession path labels absent.

## Safety

LIVE DEPLOYMENT: **NOT AUTHORIZED**
