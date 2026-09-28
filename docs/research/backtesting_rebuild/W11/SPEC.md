# CTO-W11 SPEC

**Name:** Production Research-to-Execution Integration  
**Status:** DRAFT  
**PLAN alias:** PLAN-W20 … PLAN-W26

## Objective

Drive archive, Sheets index, artifact packs, dashboard, model registry, optional live bridge, forward capture.

## Inputs

Research artifacts from earlier W (aggregates, not raw warehouse).

## Outputs

Human archive + index. Bridge only after explicit approval.

## Google Drive / Sheets (eventual)

Canonical truth remains the lake / research DB.

THIS waterfall implements Drive/Sheets. Earlier W only define payload types.

Do not implement Google integration in this waterfall unless it is CTO-W11 and separately authorized.

## MLB-first

Implement MLB only. Adapter traits may be named for future sports; do not implement NBA/NHL/NCAAB/NFL.
