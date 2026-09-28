# NBA Research Engine V2 — Test 2 dashboard

Vite + React. **Not** MLB `frontend/research-console`. **Not** a Cursor canvas.

```text
npm install
npm run dev          # http://127.0.0.1:5174
```

Research API (parquet/JSON, no trading):

```text
/tmp/momento-nba-venv/bin/python \
  apps/nba-data/scripts/research_engine_v2_test2/api_server.py
```

Static artifacts live in `public/data/` after `export_dashboard.py`.
The trade explorer splits possession sequences at `ENTRY_DECISION_TIME`.
After-entry path is labeled and is **not** a live feature.
