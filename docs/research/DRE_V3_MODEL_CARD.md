# DRE V3 — Model Card

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V3`
**Date:** 2026-09-03

## Intended use

Offline research into theoretical retained-exposure surfaces under nonlinear objectives.

Not for order routing, stops, hedges, or live risk.

## Data

Frozen FIRST-80 + PADE V1 + DRE V2 predictions. Chronological game-level TRAIN/VAL/OOS.

## Features

As-of only: current price, deterioration, market age, period, game clock, score differential, offense flag, possessions since entry.

## Models

TRAIN-only logistic / multinomial. Hyperparameters for **objectives** selected on VALIDATION only.

## Limitations

Complete-case feature rows. Last-possession path labels absent. Representative bin midpoints, not full continuous path densities. No L2. No fills.

## Safety

LIVE DEPLOYMENT: **NOT AUTHORIZED**
