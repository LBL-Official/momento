# CTO-W8 SPEC

**Name:** Event Greeks / Market Greeks / Feature Research  
**Status:** DRAFT  
**PLAN alias:** PLAN-W9 + PLAN-W10 + PLAN-W17-A1

## Objective

Versioned empirical greeks and feature warehouse with availability classes.

## Inputs

Paths (W5); event state (W2) or UNAVAILABLE.

## Outputs

FeatureVector; greek parquet with method/version.

## Google Drive / Sheets (eventual)

Canonical truth remains the lake / research DB.

Later: greeks cohorts, feature dictionary.

Do not implement Google integration in this waterfall unless it is CTO-W11 and separately authorized.

## MLB-first

Implement MLB only. Adapter traits may be named for future sports; do not implement NBA/NHL/NCAAB/NFL.
