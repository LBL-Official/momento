# ROLLER Terminal — Operator Guide

Research OS over frozen empirical sports/market data.  
**Not a trading dashboard. Not live order entry.**

**UI generation: V2 research workstation** (sidebar + progressive disclosure).  
Phases **0–6** empirical stack unchanged. Do **not** start Phase 7 unless authorized.

---

## What this is

```text
WORDS → INTERPRET → research_spec → VALIDATE → RUN → measurements + provenance
```

| Workspace | Question it answers |
|-----------|---------------------|
| **Home** | What should I do next? |
| **Research** | Focused object: Overview → Define → Results → Evidence |
| **Library** | Local saved objects (browser only — not warehouse) |
| **Explore** | What existed at information set I(t)? |
| **Templates** | Catalog (~50) with honest IMPLEMENTED / STRUCTURAL status |
| **Phenomena** | Concept catalog (not runnable objects) |
| **Dictionary** | Authoritative vocabulary explorer |
| **Docs** | In-app operator documentation |

**Sans explains. Mono evidences.**  
Measurement ≠ edge. Survive ≠ terminal yes. Candle path ≠ fill.

---

## Start (two terminals)

### 1) API — `http://127.0.0.1:8791`

```bash
cd /Users/user/Desktop/Momento/ROLLER
.venv/bin/pip install -e ".[terminal]"   # once
.venv/bin/python scripts/terminal_api.py
```

### 2) UI — `http://127.0.0.1:5179`

```bash
cd /Users/user/Desktop/Momento/frontend/roller-terminal
npm install   # once
npm run dev
```

Open: **http://127.0.0.1:5179/**

Vite proxies `/api/*` → the API. If the UI loads but actions fail, the API is not running.

Vital is a **separate dashboard**, not a tab in this app:

```bash
cd /Users/user/Desktop/Momento/frontend/vital-terminal
npm install   # once
npm run dev
```

Open: **http://127.0.0.1:5180/**. Jump / ROLLER / SuperASI open that origin.

---

## Golden path (use capabilities today)

1. **Templates** → **FIRST80 Q3** (IMPLEMENTED) → Use template  
2. Research → **Define** → **VALIDATE** → wait for **CURRENT / RUNNABLE**  
3. **RUN RESEARCH** → Research → **Results** (n = **290**)  
4. Click a measurement on **Overview** for detail drawer · open **Evidence** for provenance  

**NCAAB:** same with **NCAAB FIRST80 P5** when API Phase 6 is running (**n = 721**).

Buttons stay gated:

| Button | Needs |
|--------|--------|
| INTERPRET | Non-empty text |
| APPLY | Successful interpret with `proposed_spec` |
| VALIDATE | Always (unless a request is in flight) |
| RUN RESEARCH | Validation **CURRENT** + **RUNNABLE** |

---

## V2 notes

- **Library** uses `localStorage` only — never deletes authoritative data  
- **Template catalog** marks STRUCTURAL / DRAFT / UNAVAILABLE honestly — only backend-backed IMPLEMENTED templates are runnable  
- **Analytics** classifies metrics AVAILABLE / NOT AVAILABLE / ASSUMPTION REQUIRED; scenario EV is user-supplied hypothetical only  
- Engineering notes: `docs/research/roller_dashboard/ROLLER_V2_SUMMARY.md`  
- V1 visual tokens: `docs/research/roller_dashboard/ROLLER_V1_VISUAL_SYSTEM.md`

---

## Tests (regression — expect 63+)

```bash
cd /Users/user/Desktop/Momento/ROLLER
.venv/bin/python -m pytest -q \
  tests/test_research_spec_v0.py \
  tests/test_first80_reconciliation_phase0.py \
  tests/test_terminal_explorer_phase1.py \
  tests/test_research_object_phase2.py \
  tests/test_vocabulary_compiler_phase3.py \
  tests/test_research_executor_phase4.py \
  tests/test_measurement_registry_phase5.py \
  tests/test_population_expansion_phase6.py \
  -m "not integration"
```

```bash
cd /Users/user/Desktop/Momento/frontend/roller-terminal
npm run typecheck
```

Empirical locks must not change: FIRST80_Q3 **n=290** · NCAAB_FIRST80_P5 **n=721**.

---

## Related docs

- `docs/research/roller_dashboard/ROLLER_V2_SUMMARY.md`
- `docs/research/roller_dashboard/ROLLER_V1_VISUAL_SYSTEM.md`
- `docs/research/roller_dashboard/RESEARCH_SPEC.md`
- `docs/research/roller_dashboard/RESEARCH_OBJECT_MODEL.md`
- Samples: `docs/research/roller_dashboard/samples/`
