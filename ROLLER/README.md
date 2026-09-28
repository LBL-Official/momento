# ROLLER

The warehouse knows what data exists. ROLLER knows what could have been known at a particular time.

```text
I(t) = { x | available_at(x) < t }
```

ROLLER is Momento's point-in-time research database. It sits on top of the existing Kalshi warehouse and sport PBP ingest. It does not replace them. It does not invent L2. It does not change live trading.

```text
Existing warehouse (READ ONLY)
  → ingest adapters
  → raw pointer + sha256 + ingested_at
  → canonical CSV
  → derived D2D / team features
  → public as_of choke point I(t)
  → future research (not in ROLLER)
```

```text
ROLLER ≠ ALPHA
ROLLER ≠ STRATEGY
ROLLER ≠ EXECUTION
```

## What ROLLER answers

What information actually existed at time `t`?

Later systems ask what that implied, and only later whether it could be traded.

## Public API

```python
from roller import Roller

db = Roller()  # reads ROLLER/roller.json
state = db.as_of("2025-12-19")            # I(2025-12-19T00:00:00Z)
db.get_team_state(team="LAL", as_of="2025-12-19")
db.dataset("NBA", "2025-2026", "team_features", as_of="2025-12-19")
db.game_state("NBA_20251219_LAL_BOS", as_of="2025-12-19T18:30:00Z")
obs = db.observation("NBA_20251219_LAL_BOS", as_of="2025-12-19T18:30:00Z")  # S_t + Γ_t + M_{≤t}
db.response(obs["observation_id"], measurement="market_response_5m", horizon="5m")
db.baseline(obs["observation_id"], measurement="market_response_5m", horizon="5m")
db.residual(obs["observation_id"], measurement="market_response_5m", horizon="5m")
db.fundamental(obs["observation_id"])  # prior-only F_t; not truth or edge
db.greeks(obs["observation_id"])  # V4B query-time measurements; not part of O_t
db.greeks(obs["observation_id"], schema_version="4.0.0-C")  # V4C taxonomy overlay; zero new numbers
db.labels(observation_id=obs["observation_id"])  # L_{t→} only; includes first80_* and kalshi_yes_settled
db.clock_snap(gid, ts, as_of=ts)  # last PBP ≤ timestamp
db.first80(internal_game_id=gid, as_of=ts)  # frozen 80→40 book; off O_t
db.dataset("NBA", "2025-2026", "kalshi_trades", as_of=ts)  # prints, not fills
db.dataset("NBA", "2025-2026", "games", full_history=True)  # explicit only
```

Every public read requires `as_of` or `full_history=True`. Admin/build loaders used by scripts are unrestricted.

The filter is always half-open: `available_at < cutoff`.

- `as_of("2025-12-19")` → `2025-12-19T00:00:00Z`
- `as_of("2025-12-19", end_of_day=True)` → `2025-12-20T00:00:00Z`

## Update (offline by default)

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python scripts/update_roller.py --sport NBA --season 2025-2026
.venv/bin/python scripts/validate_roller.py
.venv/bin/python -m pytest -q
```

`--fetch` optionally shells existing warehouse CLIs. Tests do not require the 4 GB warehouse.

Polymarket 1-minute last-trade history (NBA / NCAAB / WNBA) is ingested with
`scripts/ingest_polymarket.py`. It joins Kalshi candles and PBP on
`internal_game_id`. It does not invent bid/ask and does not substitute Kalshi.

Forward-only orderbook snapshots (October NBA / NCAAB P5 vs P5; no historical L2):

```bash
.venv/bin/python scripts/ingest_orderbook_snapshots.py --once --sport NBA --sport NCAAB
```

## Layout

- `config/` — sports, seasons, schemas, sources, features, conferences, team aliases
- `meta/` — `game_identity.csv`, `teams.csv`, `update_log.csv`, `dataset_registry.json`
- `data/{sport}/{season}/canonical/` — games, monthly PBP, monthly candles
- `data/{sport}/{season}/derived/` — team features, D2D, terminal game-state labels
- `docs/` — point-in-time, D2D, lineage
- `reports/` — audit and daily update reports

## Sports in V1

| Sport | Season keys | Warehouse |
|-------|-------------|-----------|
| NBA | `2025-2026` | `NBA/2025-2026` |
| WNBA | `2025`, `2026` | `WNBA/2025-2026` (campaign split) |
| NCAAB | `2025-2026` | `NCAAB/2025-2026` (research D2D/features default `P5_vs_P5`) |

## Research Terminal (UI)

Operator guide (start API + UI, golden path FIRST80, pytest):

[`../frontend/roller-terminal/README.md`](../frontend/roller-terminal/README.md)

Full V1 can / can’t / visual system + screenshots (for engineering):

[`../docs/research/roller_dashboard/ROLLER_V1_VISUAL_SYSTEM.md`](../docs/research/roller_dashboard/ROLLER_V1_VISUAL_SYSTEM.md)

V2 workstation summary:

[`../docs/research/roller_dashboard/ROLLER_V2_SUMMARY.md`](../docs/research/roller_dashboard/ROLLER_V2_SUMMARY.md)

```bash
# API
.venv/bin/python scripts/terminal_api.py

# UI (separate shell)
cd ../frontend/roller-terminal && npm run dev
# → http://127.0.0.1:5179/

# Vital dashboard (separate instance; Jump opens this origin)
cd ../frontend/vital-terminal && npm run dev
# → http://127.0.0.1:5180/
```

## Docs

- [FIRST80 research objects](docs/RESEARCH_OBJECTS.md)
- [What the Greeks do](docs/RESEARCH_GREEKS.md)
- [Point-in-time contract](docs/POINT_IN_TIME.md)
- [D2D / information states](docs/D2D.md)
- [Data lineage and revisions](docs/DATA_LINEAGE.md)
- [V4A fundamental probability](docs/V4A_FUNDAMENTAL_PROBABILITY.md)
- [V4B empirical Greeks](docs/V4B_EMPIRICAL_GREEKS.md)
- [V4B information boundaries](docs/V4B_INFORMATION_BOUNDARIES.md)
- [V4C Greek architecture](docs/V4C_GREEK_ARCHITECTURE.md)
- [V4C information regimes](docs/V4C_INFORMATION_REGIMES.md)
- [V4C constructibility matrix](docs/V4C_CONSTRUCTIBILITY_MATRIX.md)
- [Roller V4 Greeks — architecture vs measurement](docs/ROLLER_V4_GREEKS.md)
- [V4C measurement constitution](docs/V4C_MEASUREMENT_CONSTITUTION.md)
- [V1 build report](reports/ROLLER_V1_BUILD_REPORT.md)
