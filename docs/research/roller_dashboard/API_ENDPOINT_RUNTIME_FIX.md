# ROLLER API endpoint / process-ownership fix

Status: current behavior as of 2026-09-10.

This is an infrastructure/runtime note. It does not change research-query
definitions, FIRST80 lock semantics, SuperASI fill/fee math, or live trading.

**Current contract**

- Browser → frontend `:5179` → independently managed terminal API `:8791`.
- Frontend does not start, stop, or reclaim the API.
- `POST /research-query/execute` returns **202** + `job_id`. The scan runs
  off the event loop. Poll `GET /research-query/jobs/{id}`.
- `GET /health` stays reachable during execute (`reachable_during_execute`).
- A completed job includes `result.hashes`. A failed job is an error, not
  `{count: 0}`.
- `API_UNREACHABLE` is infrastructure, not N=0.
- Named Results persist on API disk (`/research-library/saves`), not in
  localStorage.
- SuperASI import pins `question_hash` from the executed envelope. UI
  `fp_…` is `spec_fingerprint` only. Re-execute refuses a hash mismatch.
- Result cache may be on (`ROLLER_QUERY_RESULT_CACHE=1`). Cache hit is
  still that `question_hash`.

---

## 1. Root cause

Two separate runtime problems were stacked:

1. **Agent/dev launchers killed a healthy API.** Historical start recipes
   used `pkill -f scripts/terminal_api.py` (or `kill <pid>`) immediately
   before `python scripts/terminal_api.py`. That pattern terminated the
   replacement process that already owned `127.0.0.1:8791` and held the
   settlement probes. Observed: PID 91759 received SIGTERM mid
   `POST /research-query/execute` (`curl: (52) Empty reply from server`
   at 2026-09-10T23:03:40Z). The frontend did not issue that kill.

2. **The browser called same-origin `/api/...` and relied on the Vite
   proxy.** Development defaulted to `http://127.0.0.1:5179/api/...` →
   proxy rewrite → `:8791`. That hid API ownership: Network panel showed
   `:5179`, and a dead/replaced API looked like an empty research result
   rather than an infrastructure failure.

Port `8788` is not a current runtime API port. It does not appear in
frontend source or `terminal_api.py`.

---

## 2. Old API lifecycle behavior

Observed launcher pattern (agent terminals, not frontend source):

```text
pkill -f "scripts/terminal_api.py" || true
sleep 1
.venv/bin/python scripts/terminal_api.py
```

The frontend never spawned `terminal_api.py` and never called `pkill`.
Vite (`127.0.0.1:5179`, node PID 41366) is a long-running static/HMR
server only.

`GET /health` already existed on the terminal API.

---

## 3. Why it was incorrect

The replacement API at `:8791` is independently managed. Killing it to
"restart with new code" drops in-flight research-query executes, loses
settlement-probe process state, and can replace a healthy listener with
a different process. The frontend must not decide API validity by PID
or by performing port cleanup.

Proxy-only `/api` calls also made it look as if the frontend owned the
API hop. Infrastructure failure was easy to misread as `N = 0` /
`DATA_REQUIRED` / empty population.

---

## 4. New API ownership model

```text
Browser / Electron
        |
        v
ROLLER frontend :5179     (does not start, stop, or reclaim the API)
        |
        v
terminal API :8791        (independently managed)
```

Rules:

- If `http://127.0.0.1:8791/health` returns `{status:"ok"}`, **use it**.
- Do not `pkill`, `lsof -ti`, or reclaim `:8791`.
- If the API is down, surface `API_UNREACHABLE`. Do not silently spawn a
  second server from the frontend.
- Optional helper `ROLLER/scripts/ensure_terminal_api.py` starts the API
  only when health fails. It never kills a process. The frontend must
  not invoke it.

---

## 5. Runtime API-base configuration

Single source: `frontend/roller-terminal/src/api/base.ts`

Precedence:

1. `VITE_API_BASE_URL` (runtime/environment override)
2. Development default: `http://127.0.0.1:8791`
3. Production build without override: same-origin `/api` (existing Vite
   proxy; not hard-coded `:8791`)

All research and SuperASI fetches go through `apiFetch` / `apiUrl`.
No component uses a second port.

Vite `server.proxy["/api"]` still targets
`VITE_API_BASE_URL || ROLLER_API_URL || http://127.0.0.1:8791` as a
fallback only. Development browser calls go **directly** to `:8791`.
No extra proxy layer and no new CORS policy were added. Existing
`CORSMiddleware` already allows `http://127.0.0.1:5179`.

---

## 6. Port 5179 → 8791 request path

Observed from the ROLLER tab (`viewId` d6f252) after the fix:

| Request | URL | Status |
|---|---|---|
| Health | `http://127.0.0.1:8791/health` | 200 |
| Capabilities | `http://127.0.0.1:8791/research-capabilities` | 200 |
| Compile | `http://127.0.0.1:8791/research-query/compile` | 200 |
| Execute | `http://127.0.0.1:8791/research-query/execute` | **202** + `job_id` (poll `/research-query/jobs/{id}`) |

Confirm UI copy (unchanged question):

> Across 2025-2026 NBA and NCAAB population between 2025-10-10 and
> 2026-06-13, when the First Touch 80¢ Q2 or Q3 or 1H 2nd 10 or 2H 1st 10
> on the Kalshi market path occurs, with Base Terminal Efficiency scoped
> to the YES side leading and |point differential| 6–10, how frequently
> the first later exit is LOSS by reaching 35¢, and how do those
> [hold-to-expiration WIN / settle YES].

Server compile remains authoritative. Client `execution_path=frozen_reference`
is ignored. Live compile against `:8791` returned
`execution_path=generic_query`, `reference_match=null`, `status=READY`.

---

## 7. Settlement probe verification

The replacement API already contains the generic `kalshi_markets` load
probe in `execute.py` (`_load_one_scope` / `_debug_settlement_snapshot`).
This task did not duplicate or rewrite those probes.

Live execute on `:8791` wrote:

```text
execute.py:_load_one_scope  kalshi_markets load
  sport=NBA   season=2025-2026
  path=ROLLER/data/nba/2025_2026/canonical/kalshi_markets.csv
  exists=false  n_rows=0

execute.py:_load_one_scope  kalshi_markets load
  sport=NCAAB season=2025-2026
  path=ROLLER/data/ncaab/2025_2026/canonical/kalshi_markets.csv
  exists=false  n_rows=0

execute.py:settlement_snapshot
  win_hold=true  n_loss_path_steps=1  n_markets=0
  n_rows=315  terminal_yes.none=315
  te_terminal.MISSING=315
  exit_outcomes: None=235, LOSS_EXIT=80
```

API access log (PID 97838, `127.0.0.1:8791`):

```text
POST /research-query/compile HTTP/1.1  200
POST /research-query/execute HTTP/1.1  200
```

Result retained **TERMINAL_MISSING** (`terminal_missing=315`,
`terminal_yes=0`, `terminal_no=0`). Settlement was not inferred from
PBP, score, path WIN, last trade, or candles.

`terminal_api.py` now also emits a request-received line and a completion
line (`method`, `route`, `query_hash`, `execution_path`, `status`, `n`,
`terminal_missing`, `duration_ms`) for `/research-query/*` and
`/superasi/*`. The process that served this verification was started
before that logger `basicConfig` landed; observability for this run is
the uvicorn access log plus the existing settlement-probe debug lines.

---

## 8. Tests run

```text
cd ROLLER
.venv/bin/python -m pytest tests/test_api_endpoint_runtime.py -q --tb=short
# 6 passed

.venv/bin/python -m pytest \
  tests/test_research_query_engine.py \
  tests/test_research_query_harden.py \
  tests/test_research_query_increment2.py \
  -q --tb=line
# 50 passed in 225.10s

.venv/bin/python -m pytest \
  tests/test_research_executor_phase4.py \
  tests/test_population_expansion_phase6.py \
  -q --tb=line
# 17 passed

cd frontend/roller-terminal
npx tsc --noEmit
# exit 0
```

Coverage of the requested checks:

| ID | Check | How |
|---|---|---|
| A | Dev API base is `:8791` | `base.ts` + `vite.config.ts` assertions |
| B | Runtime does not kill a healthy API | frontend scan + `ensure_terminal_api.py` forbids `pkill` / `lsof -ti` |
| C | Requests use the authoritative base | no leftover `fetch("/api/` in `src/` |
| D | Unreachable API ≠ empty research | `API_UNREACHABLE` / `API_REQUEST_FAILED` copy; Confirm blocks run |
| E | Same query identity | compile+execute `question_hash` match |
| F | Settlement probe reached `:8791` | live `kalshi_markets load` + snapshot on PID 97838 |
| G | Server-authoritative metadata | compile ignores client `execution_path=frozen_reference` |

---

## 9. Browser verification

| Step | Result |
|---|---|
| UI | `http://127.0.0.1:5179/` |
| API | `http://127.0.0.1:8791/` PID **97838** (single LISTEN) |
| Same object | ASKED-SIX draft restored; Confirm showed the same question text |
| Browser compile | `http://127.0.0.1:8791/research-query/compile` **200** (58 ms) |
| Browser execute | `http://127.0.0.1:8791/research-query/execute` **200** (3131 ms; cache after the cold execute) |
| API logged the execute | `POST /research-query/execute` 200 on PID 97838 |
| Settlement probe | `kalshi_markets` NBA+NCAAB `exists=false` on that process |
| Results render | COMPLETE · N = 315 TE-scoped · 885 entry events · NBA 182 · NCAAB 133 |
| Query hash | unchanged (`6aca2c25…5c1ee9`) |
| Second API spawned | no — still one LISTEN on 8791 |
| Old `:8788` required | no |
| Research semantics | unchanged (see §12) |

Cold execute (curl, same draft, same API) before the UI cache hit:

- `POST http://127.0.0.1:8791/research-query/execute`
- HTTP **200**
- wall time **412.409 s**
- `execution_status=COMPLETE`
- `compile.status=READY`
- `execution_path=generic_query`

---

## 10. Files changed

- `frontend/roller-terminal/src/api/base.ts` (new)
- `frontend/roller-terminal/src/vite-env.d.ts`
- `frontend/roller-terminal/vite.config.ts`
- `frontend/roller-terminal/src/App.tsx`
- `frontend/roller-terminal/src/v2/researchStatus.ts`
- `frontend/roller-terminal/src/v2/workflow/ConfirmScreen.tsx`
- `frontend/roller-terminal/src/ResearchObjectBuilder.tsx`
- `frontend/roller-terminal/src/v2/views/DictionaryView.tsx`
- `frontend/roller-terminal/src/superasi/api/superasiApi.ts`
- `ROLLER/scripts/terminal_api.py` (request logging + compile `hashes` headers only)
- `ROLLER/scripts/ensure_terminal_api.py` (new; start-if-unhealthy, never kill)
- `ROLLER/tests/test_api_endpoint_runtime.py` (new)
- `docs/research/roller_dashboard/API_ENDPOINT_RUNTIME_FIX.md` (this file)

`terminal_api.py` compile still recompiles the draft on the server.
Adding `hashes` to the compile body does not change the question AST.

---

## 11. Files intentionally not changed

- `ROLLER/roller/research/first80.py`
- `ROLLER/tests/test_research_executor_phase4.py`
- `ROLLER/tests/test_population_expansion_phase6.py`
- `ROLLER/roller/research_query/` semantic modules (entry / path / terminal / population)
- `apps/terminal-efficiency/`
- `frontend/roller-terminal/` research-result math / FIRST80 lock UI
- FIRST01 / FIRST80 / 81 / 83 / 89
- W9
- Risk / Execution / live trading
- `crates/research-engine`
- SuperASI decomposition math

---

## 12. Research semantics unchanged

Identity before endpoint migration (local compile) and after (`:8791`
compile + execute) is the same:

| Field | Value |
|---|---|
| `question_hash` | `6aca2c25a9de51fe393b500e13da5abe058012cf087a52b4a7389ddde45c1ee9` |
| `entry_hash` | `31f88c47003f6cfac75e2a6ac3a0ed6a8971a52c45becd34bd7cf08f31e3258c` |
| `state_hash` | `499135481b07897b6bf61aa3406d179a5c5e5cebd9b8bfcc61377ca5b976b8c2` |
| `path_hash` | `9e521eb9688f3325fe3fe2f70d6482067e3b1815a249a2c063379a8a43605df8` |
| `dataset_version` | `2ee3a69c76e60f99d6a25b5c16c9d5415f16da2100dfa6601e88d18c22fa9121` |
| `research_object_id` | absent (`null`) — generic query, not a lock object |
| `execution_path` | `generic_query` |
| `reference_match` | `null` |

Measured result (unchanged vs the prior settlement-probe investigation):

- N = 315 TE-scoped · 885 entry events · NBA 182 · NCAAB 133
- Funnel: Universe 4402 → FIRST_TOUCH 8000 n=885 → TE scope 315
- Classified path exits: WIN 0/80 · LOSS 80/80
- Path TRUE 0 / PATH FALSE 315
- Terminal UNAVAILABLE · `terminal_missing=315`
- Settlement EV UNAVAILABLE · `kalshi_markets` empty · not 0 · not path WIN

`TERMINAL_MISSING` is retained because settlement data is absent. This
fix does not manufacture terminal coverage.

---

## 13. Jobs, disk save, and hash pin (current)

These landed after the original endpoint-ownership fix. They are current
behavior, not leftover incident notes.

**Jobs.** `ROLLER/roller/research_query/jobs.py` runs execute on a
one-worker thread pool. `/health` is async. Confirm shows MEASURING
while the job runs. Do not start the API as a command line that matches
`pkill -f scripts/terminal_api.py`.

**Disk save.** `POST /research-library/saves` writes the envelope
(including `hashes`) to API disk. The browser Library stores a compact
pointer + `server_save_id`. Save does not invent measurement authority.

**Hash pin.** Move to SuperASI sends envelope `hashes.question_hash` and
the UI `spec_fingerprint`. Import stores `question_hash`, the full
`hashes` layer, and `dataset_version` on the SuperASI package and on
`decomp.json`. If import re-executes and the client hash does not match,
it returns `QUESTION_HASH_MISMATCH`. SuperASI decompose is still
fill/fee math on those trades — not a reprint of ROLLER EV.

## Remaining warehouse note

Generic `kalshi_markets.csv` is still missing for NBA/NCAAB 2025-2026.
Hold-YES now uses the official-W overlay (FIRST80
`expiration_result_yes` + asked-six CSV + complement) when those sources
have a result. Missing tickers stay missing. Do not infer settlement
from path, PBP, or box score.
