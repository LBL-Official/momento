# Jump — current research filesystem

**Date:** 2026-09-20
**LIVE EXECUTION = FALSE**

Jump is the Data Modeling Drive inside `frontend/roller-terminal`
(`http://127.0.0.1:5179/?app=jump`). It is not a new Vite app and not
an 18th Momento system.

```text
ROLLER = measurements
SuperASI = analysis
Jump = organization, display names, generated document projections,
       warehouse catalog / read-only workbench
```

Workbench recon: `docs/jump/WAREHOUSE_RECON.md`.
Canonical NBA desk: `ROLLER/data/nba/2025_2026/derived/warehouse/`.
Jump does not copy that tree. Confirm & Run still reads CSV.

## Layout

Sport-first. Default landing is NBA.

```text
/?app=jump
/?app=jump#/nba
/?app=jump#/nba/FIRST80_ASKED_SIX_80_40
/?app=jump#/nba/FIRST80_ASKED_SIX_80_40/roller-measurement
```

One folder per canonical research articulation. Asked-six
(`FIRST80_ASKED_SIX_80_40`, display `FIRST80 Asked Six 80→40`) is MIXED
N=1182 (NBA 604 + NCAAB 332 + WNBA 246). Homed under NBA. The same
object is listed under NCAAB and WNBA (`SHARED`, not a copy). Choosin
asked-six locks and `first80_asked_six.csv` are provenance, not a second
folder.

`superasi_vfgifapk` repeats `package_id=asked_six_first80_80_40` but the
folder name is not the package id. Jump does **not** silently merge it.
It is `NEEDS_RESOLUTION` on the canonical object.

UUID SuperASI packages with null `research_object_id` stay separate.
Primary name is `identity.name` or `Untitled research object`. UUID is
metadata only.

## API

- `GET /jump` — library root, default sport NBA
- `GET /jump/sports`
- `GET /jump/research?sport=NBA`
- `GET /jump/research/{canonical_key}`
- `GET /jump/research/{canonical_key}/children`
- `GET /jump/documents/{doc_id}`
- `GET /jump/artifacts/{id}/preview`
- `GET /jump/search?q=`
- `GET /jump/recent`
- `POST /jump/index/refresh`
- `GET /jump/warehouses` and `/jump/warehouses/{id}/*` — read-only desk workbench
- `GET|POST|PATCH|DELETE /jump/queries` — Jump-owned saved SQL

Warehouse hash routes (`#/nba/warehouses/nba`, tables, queries) sit beside
the research filesystem. Landing remains `#/nba`.

`/jump/bots*` and `/jump/iti*` remain compatibility HTTP. Generated
markdown is rebuilt from sources on index. Not writable. Missing fields
render `Unavailable`.
