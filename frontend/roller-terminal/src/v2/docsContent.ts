/** Short operator docs — links to repo markdown; no invented empirics. */

export type DocPage = {
  id: string;
  title: string;
  summary: string;
  what: string;
  why: string;
  can: string[];
  cannot: string[];
  example: string;
  repoPath?: string;
};

export const DOC_PAGES: DocPage[] = [
  {
    id: "getting-started",
    title: "Getting Started",
    summary: "Start API + UI, load FIRST80_Q3, validate, run, read Results.",
    what: "Operator onboarding for the Research Terminal.",
    why: "So researchers reach an authoritative measurement without parsing the whole system.",
    can: ["Load implemented templates", "Validate and run", "Inspect Results"],
    cannot: ["Trade", "Invent EV", "Skip validation"],
    example: "Templates → FIRST80 Q3 → Validate → Run → Results (n=290).",
    repoPath: "frontend/roller-terminal/README.md",
  },
  {
    id: "how-roller-works",
    title: "How ROLLER Works",
    summary: "WORDS → INTERPRET → research_spec → VALIDATE → RUN → measurements.",
    what: "The research lifecycle and authority hierarchy.",
    why: "Prevents treating measurements as edge or candles as fills.",
    can: ["Interpret vocabulary", "Validate specs", "Execute bound measurements"],
    cannot: ["LLM invent specs", "Bypass Risk/Execution in live trading"],
    example: "Interpret “first time price hits 80 in Q3” then APPLY and VALIDATE.",
    repoPath: "docs/research/roller_dashboard/RESEARCH_OBJECT_MODEL.md",
  },
  {
    id: "lifecycle",
    title: "Research Lifecycle",
    summary: "Validate → Run (202 job + poll) → Results. Freshness and reachability are separate.",
    what: "How Research State tracks fingerprints, and how execute stays off the API event loop.",
    why: "Edits after validate must not silently reuse old results. A long warehouse scan must not look like N=0.",
    can: [
      "Re-validate when STALE",
      "Compare fingerprints in Audit",
      "Poll GET /research-query/jobs/{id} until complete",
      "Keep Confirm on MEASURING while a job runs",
    ],
    cannot: [
      "Treat STALE as an error crash",
      "Claim PRIOR result is CURRENT",
      "Treat API_UNREACHABLE as an empty population",
      "Treat a failed job as {count: 0}",
    ],
    example:
      "POST /research-query/execute → 202 + job_id. /health stays reachable. Poll until result.hashes is present. Edit a slice → Execution STALE → re-validate → re-run.",
  },
  {
    id: "research-objects",
    title: "Research Objects",
    summary: "One research_spec defines one empirical phenomenon.",
    what: "The A–I object model: identity through bindings.",
    why: "Portfolio ≠ one object; FIRST80 is one object inside BBALL1.",
    can: ["Define conditions", "Request measurements", "Export JSON"],
    cannot: ["Silently change definition_versions"],
    example: "FIRST80_Q3_PATH_TERMINAL sample.",
    repoPath: "docs/research/roller_dashboard/RESEARCH_SPEC.md",
  },
  {
    id: "population-bindings",
    title: "Population Bindings",
    summary: "Populations come from authoritative adapters — not UI filters alone.",
    what: "How leagues/slices bind to warehouse or ROLLER populations.",
    why: "Membership locks (n=290 / n=721) must not drift.",
    can: ["Select leagues and slices", "Use locked templates"],
    cannot: ["Invent Phase 7 generic populations"],
    example: "FIRST80 warehouse_frozen_v1 with Q3 entry_slice.",
    repoPath: "docs/research/roller_dashboard/AUTHORITY_MATRIX.md",
  },
  {
    id: "measurements",
    title: "Measurements",
    summary: "REGISTERED ≠ IMPLEMENTED. MEASUREMENT ≠ EDGE.",
    what: "Measurement registry and executor routing.",
    why: "Honest capability preview before RUN.",
    can: ["Request t40_rate / kalshi_yes_rate when bound"],
    cannot: ["Treat rates as edge", "Fabricate unavailable metrics"],
    example: "t40_rate PATH PROPORTION via barrier_survival_v1.",
  },
  {
    id: "validation",
    title: "Validation",
    summary: "RUNNABLE / UNRESOLVED / INVALID with explicit unresolved fields.",
    what: "Structural validation of research_spec.",
    why: "Ambiguous thresholds stay unresolved — never invented.",
    can: ["Inspect unresolved reasons", "Fix builder sections"],
    cannot: ["Run without CURRENT+RUNNABLE"],
    example: "Magnitude UNRESOLVED on large-down-move sample.",
  },
  {
    id: "execution",
    title: "Execution",
    summary: "Executor binds populations and measurements with provenance.",
    what: "Phase 4–6 research execution.",
    why: "Results must cite artifacts and definition_versions.",
    can: ["Run locked templates", "Export results JSON"],
    cannot: ["Assume fills", "Assume live liquidity"],
    example: "FIRST80_Q3 COMPLETE with n=290.",
  },
  {
    id: "point-in-time",
    title: "Point-in-Time Data",
    summary: "Explorer assembles O_t under half-open as_of cutoffs.",
    what: "I(t) discovery and Object Inspector.",
    why: "Leakage prevention is the contract.",
    can: ["Explore games", "Inspect constructibility"],
    cannot: ["Pull future labels into O_t"],
    example: "as_of 2025-10-11 → NBA_20251010_BOS_TOR.",
  },
  {
    id: "capabilities",
    title: "Capabilities",
    summary: "Capability registry separates IMPLEMENTED from REGISTERED.",
    what: "/research-capabilities payload.",
    why: "UI must not imply every listed route is executable.",
    can: ["Preview capability on current spec"],
    cannot: ["Upgrade REGISTERED to IMPLEMENTED in UI"],
    example: "Capability preview on FIRST80_Q3 shows 2 IMPLEMENTED measurements.",
  },
  {
    id: "vocabulary",
    title: "Vocabulary Guide",
    summary: "Deterministic compiler — not free-form English.",
    what: "research_vocabulary_v0 concepts and aliases.",
    why: "WORDS ≠ RESEARCH SPEC.",
    can: ["Search Dictionary", "INTERPRET known phrases"],
    cannot: ["Claim arbitrary English works"],
    example: "“first time price hits 80 in Q3”.",
    repoPath: "docs/research/roller_dashboard/research_vocabulary_v0.json",
  },
  {
    id: "empirical-boundaries",
    title: "Empirical Boundaries",
    summary: "ROLLER ≠ alpha / strategy / execution.",
    what: "Hard non-goals for the Terminal.",
    why: "Preserves Phases 0–6 epistemic discipline.",
    can: ["Measure", "Document", "Organize locally"],
    cannot: ["Live trading", "Sharpe from missing returns", "Phase 7"],
    example: "Analytics marks EV as USER-SUPPLIED SCENARIO or NOT AVAILABLE.",
    repoPath: "docs/research/roller_dashboard/ROLLER_V1_VISUAL_SYSTEM.md",
  },
  {
    id: "api-reference",
    title: "API Reference",
    summary: "Terminal FastAPI on :8791. Jobs, health, saves, SuperASI import.",
    what: "The independently managed terminal API the UI calls directly in development.",
    why: "Frontend must not invent endpoints, spawn the API, or treat a dead hop as N=0.",
    can: [
      "GET /health (stays reachable during execute)",
      "POST /research-query/compile",
      "POST /research-query/execute → 202 + job_id, then GET /research-query/jobs/{id}",
      "POST/GET /research-library/saves",
      "POST /superasi/library/import",
    ],
    cannot: [
      "Call live Kalshi from this UI",
      "pkill or restart :8791 from the frontend",
      "Treat API_UNREACHABLE as an empty population",
      "Use the 200-row preview as N",
    ],
    example:
      "Confirm Run → 202 job → poll until complete → result.hashes.question_hash. Failed job returns error, not {count: 0}.",
    repoPath: "docs/research/roller_dashboard/API_ENDPOINT_RUNTIME_FIX.md",
  },
  {
    id: "candle-path-not-fill",
    title: "Candle path is not a fill",
    summary: "Tradable close-cross is an observation. CANDLE ≠ FILL. Path WIN ≠ settle YES.",
    what: "How Results numbers are observed on candle closes, not executed Kalshi fills.",
    why: "A close that crosses 90¢ or 55¢ is not a fill, a fee, or official settlement.",
    can: [
      "Read path WIN/LOSS on later candle closes",
      "Read terminal YES only from official W overlay or settlement fields",
      "See the 200-row preview as a sample, never as N",
    ],
    cannot: [
      "Treat a candle close-cross as a fill",
      "Map path WIN onto settle YES",
      "Use preview rows as population.count",
      "Invent L2 or last-trade as executable bid/ask",
    ],
    example:
      "N=788 TE-scoped. WIN 580/788 is first-exit on closes. Terminal YES 649/786 available is settlement, not path WIN. Two missing W stay missing.",
    repoPath: "docs/research/research_query/OPERATIONS.md",
  },
  {
    id: "library-saves-import",
    title: "Library, Saves, and Import",
    summary: "Local Library pointer vs API disk save vs SuperASI disk package.",
    what: "Three stores: browser Library metadata, API research-library saves, SuperASI library packages.",
    why: "Save does not invent authority. Move does not require Save, but both must carry the same question_hash.",
    can: [
      "Save a completed envelope to API disk (full trades + hashes)",
      "Reopen a Library pointer by hydrating the server save",
      "Move to SuperASI from live Results or a reloaded save",
      "Warehouse desk Move saves the lab and advances SuperASI A→B, reusing Final Results when they already exist (ITI is a separate click)",
    ],
    cannot: [
      "Fit a 788-trade envelope in localStorage",
      "Treat Save as changing the measurement",
      "Import the 200-row preview as N",
      "Assume SuperASI reprints ROLLER EV",
    ],
    example:
      "Save writes hashes + trades on API disk. Move sends the in-memory envelope (full trades + hashes). Import from either path stores the same question_hash.",
  },
  {
    id: "hashes-identity",
    title: "Hashes and identity",
    summary: "question_hash is the measurement. UI spec_fingerprint is only the editor.",
    what: "Server hashes.question_hash / entry_hash / state_hash / path_hash versus the UI fp_… spec fingerprint.",
    why: "TE chips change question_hash (via state_hash). The editor fingerprint must not be treated as the measurement.",
    can: [
      "Read hashes in the Audit drawer and on the result envelope",
      "See SuperASI show question_hash as ROLLER measurement identity",
      "Expect TE leading / |Δ| to change question_hash, not entry_hash",
    ],
    cannot: [
      "Call UI fp_… a question_hash",
      "Reuse a STALE spec fingerprint as the executed identity",
      "Change TE chips and keep the prior question_hash",
    ],
    example:
      "ASKED-SIX question_hash 6aca2c25… stays stable across compile and execute. Switching TE leading changes question_hash and state_hash; entry_hash stays.",
  },
  {
    id: "superasi-consumer",
    title: "SuperASI consumer",
    summary: "ROLLER measures. SuperASI decomposes those trades. Not a fill. Not live.",
    what: "Import copies trades + question_hash into a disk package, then decompose writes decomp.json.",
    why: "SuperASI numbers are fill/fee math on the imported population. They are not ROLLER WIN% and not executed P&L.",
    can: [
      "Move a COMPLETE/PARTIAL envelope with len(trades)==N",
      "See MEASUREMENT IMPORTED and the ROLLER question_hash on the package",
      "Change fill/fee mixes without mutating package.json",
    ],
    cannot: [
      "Submit orders (live_execution stays false)",
      "Re-execute when the client question_hash does not match",
      "Treat SuperASI S as terminal p or as a fill",
      "Invent L2 or start W9",
    ],
    example:
      "Move → package.question_hash = envelope.hashes.question_hash. decomp.json repeats that hash + checksums.trades. SuperASI EV is decompose-on-those-trades.",
    repoPath: "docs/research/superasi/",
  },
  {
    id: "te-official-w",
    title: "Terminal Efficiency and official W",
    summary: "TE scopes N. Official W is an overlay. Hold does not override a path exit.",
    what: "Leading / |Δ| chips restrict reported N. Official W comes from FIRST80 expiration_result_yes + asked-six CSV + binary complement.",
    why: "Missing score fails closed. Path WIN is never settlement YES. Same-minute generic ties are not TE exact-timestamp ties.",
    can: [
      "Scope N to leading (point_differential > 0)",
      "Read YES rate as yes / terminal_available",
      "Read WIN% on classified WIN+LOSS only",
      "Use official W for hold-YES when neither path barrier hit",
    ],
    cannot: [
      "Invent Kalshi settlement from PBP or box score",
      "Let hold-YES override an earlier LOSS_EXIT",
      "Count TIE_EXCLUDED in WIN%",
      "Treat TE AMBIGUOUS as generic TIE_EXCLUDED",
    ],
    example:
      "Same minute 90¢ and 55¢ → generic TIE_EXCLUDED (denom = WIN+LOSS, not N). Same timestamps → TE AMBIGUOUS. Path LOSS then official W YES stays LOSS_EXIT. 649/786 ≠ 649/788.",
    repoPath: "docs/research/research_query/OPERATIONS.md",
  },
  {
    id: "mlb1",
    title: "MLB research (MLB1)",
    summary: "Inning slices, YES batting, last-print honesty, PIT snap, and settlement.",
    what: "Generic query + Base TE on a canonical MLB warehouse. Inning/half filters, lead chips, outs/count/runners, last-trade or genuine yes_bid candles.",
    why: "Basketball clock grammar is not baseball. Last trade is not a YES bid. PBP state is not a prediction. Sport result is not market settlement.",
    can: [
      "Select Baseball → MLB → Last trade and run generic_query",
      "Filter T7 / B7 / I7 and T7 OR B7",
      "Scope N with leading exact 1–4, presets, custom, outs, count, RISP, YES batting",
      "Read PIT ENTRY STATE separately from market path and settlement",
      "See LAST_TRADE vs TRADABLE on Confirm and the result envelope",
    ],
    cannot: [
      "Invent yes_bid from a print or forward-fill a silent minute",
      "Treat a candle/print path as a fill",
      "Infer Kalshi settlement from the box score or last trade",
      "Run a 48-minute MLB game clock or a joint NBA+MLB universe",
      "Change live FIRST01 / 80/81/83/89 or start W9",
    ],
    example:
      "Quick Start Baseball / MLB / Last trade → Entry T7|B7, YES batting, leading exact 2, 2 outs, RISP → Reach / Hold → Run. Missing PIT fields are excluded, not guessed.",
  },
];

export const QUERY_WRITING_GUIDE = {
  title: "How to write a query",
  intro:
    "The interpreter understands a finite vocabulary. Unknown terms stay unresolved — they are never invented into thresholds.",
  categories: [
    {
      name: "FAMILIES",
      words: ["ORDINAL_TOUCH", "DROP_TO", "BOUNCE_TO", "RECOVER_TO", "EVER_TOUCH", "SEQUENCE"],
    },
    {
      name: "TIME WORDS",
      words: ["first", "before", "after", "during", "at", "Q3"],
    },
    {
      name: "PRICE WORDS",
      words: ["touch", "cross", "above", "below", "80", "40"],
    },
    {
      name: "GAME STRUCTURE",
      words: ["Q1", "Q2", "Q3", "Q4", "half", "H1_2", "H2_1", "T7", "B7", "I7", "RISP"],
    },
    {
      name: "MEASUREMENT WORDS",
      words: ["rate", "terminal", "path", "survival", "yes"],
    },
    {
      name: "DISTINCTIONS",
      words: ["TOUCH ≠ CROSS ≠ STATE", "SEARCH ≠ COMPILER", "SURVIVE ≠ YES"],
    },
  ],
  examples: [
    "first time price hits 80 in Q3",
    "FIRST80 Q3 survive T40",
    "kalshi yes rate",
  ],
};
