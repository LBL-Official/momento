/** Download report of what actually happened — not an app-state dump. */

import type { Spec } from "../../researchTypes";
import { asObj } from "../../researchTypes";
import type { AnswerResult } from "./ResultsAnswer";
import { lockedTemplateKind } from "../define/defineCatalog";
import type { ConstructibilityResolution, WorkflowDraft } from "../workflow/types";
import { composeQuestionFromDraft } from "../workflow/questionFromDraft";
import { wilsonCi } from "./wilson";
import { deriveObservedStats, hasObservedVector, pickObserved, pickObservedEv } from "./deriveObserved";
import { coveragePct, fmtRate } from "./lastTradeResults";
import { LAST_TRADE_UNAVAILABLE } from "./lastTradeBasis";
import { readResultsContract } from "./resultsContract";

function pct(v: number | null | undefined): string {
  return typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(2)}%` : "—";
}

export function buildMarkdownReport(input: {
  question: string;
  spec: Spec;
  result: AnswerResult;
}): string {
  const { question, spec, result } = input;
  const lock = lockedTemplateKind(spec);
  const n = result.summary?.population_n ?? result.population?.count ?? null;
  const t40 = result.measurements?.find((m) => m.name === "t40_rate" || m.name === "path_rate");
  const yes = result.measurements?.find((m) => m.name === "kalshi_yes_rate");
  const partition = result.empirical_partition;
  const caveats = result.caveats?.length ? result.caveats : (asObj(spec).caveats as string[] | undefined) ?? [];

  return [
    "# Research report",
    "",
    "## Question",
    question,
    "",
    "## Population",
    `- Lock: ${lock || String(asObj(spec.identity).name || "unspecified")}`,
    `- Description: ${result.summary?.population_description || "—"}`,
    `- Observations N: ${n ?? "—"}`,
    "",
    "## Conditions",
    "Implied by the executed lock. Overlay conditions are not constructible and are not applied.",
    "",
    "## Measurements",
    `- Path T40: ${pct(t40?.value ?? null)}` +
      (t40?.detail ? ` (${String(t40.detail.count_true ?? "—")} / ${String(t40.detail.count_available ?? "—")})` : ""),
    `- Terminal Kalshi YES: ${pct(yes?.value ?? null)}` +
      (yes?.detail ? ` (${String(yes.detail.count_true ?? "—")} / ${String(yes.detail.count_available ?? "—")})` : ""),
    "",
    "## Base Terminal Efficiency",
    result.base_terminal_efficiency
      ? [
          `- TE N: ${result.base_terminal_efficiency.n_te_scoped ?? 0} scoped / ${result.base_terminal_efficiency.n_te_attached ?? 0} attached`,
          `- TE WIN exits: ${result.base_terminal_efficiency.overall?.n_win_exit ?? 0}`,
          `- TE LOSS exits: ${result.base_terminal_efficiency.overall?.n_loss_exit ?? 0}`,
          `- TE AMBIGUOUS: ${result.base_terminal_efficiency.overall?.n_ambiguous ?? 0}`,
          `- Note: ${result.base_terminal_efficiency.note || "PIT observation. CANDLE ≠ FILL."}`,
        ].join("\n")
      : "Not attached on this result.",
    "",
    "## Empirical state space",
    partition?.status === "COMPLETE"
      ? `Joint partition measured. Population N = ${partition.n_population ?? n ?? "—"}.`
      : "JOINT PARTITION NOT CURRENTLY MEASURED.",
    "",
    "## Results",
    `- Execution: ${result.execution_status || "—"}`,
    `- Research object: ${result.research_object_id || "—"}`,
    "",
    analysisMarkdown(result),
    "",
    "## Caveats",
    ...caveats.map((c) => `- ${c}`),
    "- CANDLE PATH ≠ EXECUTABLE FILL",
    "- OBSERVED PATH EV ≠ HYPOTHETICAL PAYOFF EV",
    "",
    "## Evidence",
    `- T40 source: ${t40?.source?.artifact || "—"} / ${t40?.source?.field || "—"}`,
    `- YES source: ${yes?.source?.artifact || "—"} / ${yes?.source?.field || "—"}`,
    `- Definition T40: ${t40?.definition_version || "—"}`,
    `- Definition YES: ${yes?.definition_version || "—"}`,
    "",
    "## Provenance",
    "```json",
    JSON.stringify(result.provenance ?? {}, null, 2),
    "```",
    "",
    "This report describes the measurement that ran. It is not a trading signal.",
    "",
  ].join("\n");
}

export function buildJsonReport(input: {
  question: string;
  spec: Spec;
  result: AnswerResult;
}): string {
  return JSON.stringify(
    {
      question: input.question,
      population: {
        lock: lockedTemplateKind(input.spec),
        identity: input.spec.identity,
        n: input.result.summary?.population_n ?? input.result.population?.count ?? null,
        description: input.result.summary?.population_description ?? null,
      },
      conditions: "implied_by_lock",
      measurements: input.result.measurements ?? [],
      analysis: (input.result as { analysis?: unknown }).analysis ?? null,
      empirical_state_space: input.result.empirical_partition ?? {
        status: "JOINT_PARTITION_NOT_CURRENTLY_MEASURED",
      },
      results: {
        execution_status: input.result.execution_status,
        research_object_id: input.result.research_object_id ?? null,
      },
      caveats: input.result.caveats ?? [],
      evidence: (input.result.measurements ?? []).map((m) => ({
        name: m.name,
        definition_version: m.definition_version,
        source: m.source,
      })),
      provenance: input.result.provenance ?? {},
    },
    null,
    2,
  );
}

export function downloadText(filename: string, text: string, mime: string): void {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function measurementLine(result: AnswerResult, name: string, label: string): string {
  const m = result.measurements?.find((x) => x.name === name);
  const trueN = typeof m?.detail?.count_true === "number" ? m.detail.count_true : null;
  const avail = typeof m?.detail?.count_available === "number" ? m.detail.count_available : null;
  const ci =
    trueN != null && avail != null ? wilsonCi(trueN, avail) : null;
  return `- ${label}: ${pct(m?.value ?? null)}${
    trueN != null && avail != null ? ` (${trueN} / ${avail})` : ""
  }${ci ? ` · Wilson 95% [${(ci.lower * 100).toFixed(2)}% — ${(ci.upper * 100).toFixed(2)}%]` : ""}`;
}

export function buildWorkflowMarkdown(input: {
  draft: WorkflowDraft;
  resolution: ConstructibilityResolution;
  spec: Spec;
  result?: AnswerResult | null;
  question?: string;
}): string {
  const question =
    input.question ?? composeQuestionFromDraft(input.draft, input.resolution);
  const n =
    input.result?.summary?.population_n ?? input.result?.population?.count ?? null;
  const partition = input.result?.empirical_partition;
  const caveats = input.result?.caveats ?? [];
  return [
    "# Research report",
    "",
    "## Research question",
    question,
    "",
    "## Universe",
    `- Sports: ${input.draft.universe.sports.join(", ") || "—"}`,
    `- Leagues: ${input.draft.universe.leagues.join(", ") || "—"}`,
    `- Seasons: ${input.draft.universe.seasons.join(", ") || "full selected seasons"}`,
    `- Markets: ${input.draft.universe.markets.join(", ") || "—"}`,
    `- Market data: ${input.draft.universe.marketData.join(", ") || "—"}`,
    `- Game data: ${input.draft.universe.dataSources.join(", ") || "—"}`,
    "",
    "## Entry conditions",
    ...input.draft.entryConditions.map((e) => `- ${e.family} ${e.priceCents ?? ""} ${e.period ?? ""}`),
    "",
    "## Exit / observation conditions",
    ...input.draft.exitConditions.map((e) => `- ${e.kind} ${e.family} ${e.priceCents ?? ""}`),
    "",
    "## Constructibility",
    `- Status: ${input.resolution.status}`,
    `- Matched template: ${input.resolution.matchedTemplate ?? "none"}`,
    ...input.resolution.blockingReasons.map((r) => `- ${r}`),
    "",
    "## Population N",
    String(n ?? "No measurement yet"),
    "",
    "## Authoritative measurements",
    input.result
      ? [
          measurementLine(input.result, pathMeasurementName(input.result), "Path"),
          measurementLine(input.result, "kalshi_yes_rate", "Terminal Kalshi YES"),
          measurementLine(input.result, "model_a_8040_ev_cents", "Model A EV (¢)"),
          measurementLine(input.result, "observed_hyp_ev_cents", "Observed path EV (¢)"),
          measurementLine(input.result, "max_drawdown_cents", "Observed path drawdown (¢)"),
          "- Risk of ruin: NOT COMPUTED (no explicit stochastic bankroll model)",
          analysisMarkdown(input.result),
        ].join("\n")
      : "No run.",
    "",
    "## Joint partition",
    partition?.status === "COMPLETE"
      ? `Measured. Population N = ${partition.n_population ?? n ?? "—"}.`
      : "JOINT PARTITION NOT CURRENTLY MEASURED.",
    "",
    "## Caveats",
    ...caveats.map((c) => `- ${c}`),
    "- CANDLE PATH ≠ EXECUTABLE FILL",
    "- HYPOTHETICAL PAYOFF ≠ EMPIRICAL RESULT",
    "",
    "## Provenance",
    "```json",
    JSON.stringify(input.result?.provenance ?? {}, null, 2),
    "```",
    "",
  ].join("\n");
}

export function buildConstraintsJson(input: {
  draft: WorkflowDraft;
  resolution: ConstructibilityResolution;
}): string {
  return JSON.stringify(
    {
      workflowDraft: input.draft,
      recognizedIntent: input.draft.recognizedIntent,
      constructibility: input.resolution.status,
      matchedTemplate: input.resolution.matchedTemplate ?? null,
      blockingReasons: input.resolution.blockingReasons,
    },
    null,
    2,
  );
}

function pathMeasurementName(result: AnswerResult): string {
  return result.measurements?.some((m) => m.name === "t40_rate") ? "t40_rate" : "path_rate";
}

function rec(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
}

function analysisMarkdown(result: AnswerResult): string {
  const contract = readResultsContract(result);
  if (contract.lastTrade) {
    const lt = contract.rates;
    return [
      "",
      "## Finite-sample analysis",
      `- Observation basis: LAST_TRADE_PRINT · TradableBar.bid is last_close_e4 · not yes_bid_close`,
      `- Observed executable-path EV: UNAVAILABLE · ${LAST_TRADE_UNAVAILABLE}`,
      `- Capitalized observed path: UNAVAILABLE`,
      `- Sharpe / Sortino / sequence drawdown: UNAVAILABLE`,
      `- Break-even total cost: UNAVAILABLE`,
      `- PATH RATE: ${fmtRate(lt.pathTrue, lt.n)}`,
      `- CLASSIFIED WIN: ${fmtRate(lt.winExit, lt.classified)}`,
      `- CLASSIFIED LOSS: ${fmtRate(lt.lossExit, lt.classified)}`,
      `- PATH FALSE: ${lt.pathFalse ?? "—"} / ${lt.n ?? "—"} · not LOSS_EXIT`,
      `- TERMINAL YES: ${lt.terminalYes ?? "—"} / ${lt.settled ?? "—"} · conditional on observed Kalshi settlement`,
      `- SETTLEMENT COVERAGE: ${coveragePct(lt.settled, lt.n)}`,
      `- TERMINAL MISSING: ${lt.terminalMissing ?? "—"} / ${lt.n ?? "—"}`,
      `- Settlement EV: INCOMPLETE`,
      `- Exposure: ${contract.exposure.status} · EXPOSURE_UNIT=${contract.exposure.declaredUnit} · MAX_ENTRIES_PER_UNIT=${contract.exposure.maxEntriesPerUnit ?? "—"} · do not assume N is unique games`,
      `- Book-price EV: UNAVAILABLE unless explicit payoff chips exist`,
      `- LAST TRADE ≠ YES BID. LAST TRADE ≠ FILL. PATH WIN ≠ TERMINAL YES. PATH LOSS ≠ TERMINAL NO.`,
    ].join("\n");
  }
  const a = (result as { analysis?: Record<string, unknown> }).analysis;
  const derived = deriveObservedStats(result);
  const picked = pickObserved(a ?? null, derived);
  const pickedEv = pickObservedEv(a ?? null, derived);
  if (!hasObservedVector(picked) && !hasObservedVector(pickedEv)) {
    return "- Observed return vector absent (no valid exit). Missing exit is not 0. Envelope not required once πᵢ exists.";
  }
  const obs = { ...rec(a?.observed_ev), ...rec(pickedEv) };
  const book = rec(a?.hypothetical_payoff);
  const settle = rec(a?.settlement_payoff);
  const cap = rec(a?.capitalization);
  const sizing = rec(cap.sizing);
  const prices = rec(cap.prices);
  const observed = rec(cap.observed);
  const dist = rec(observed.distribution);
  const sig = rec(obs.significance);
  const ci = rec(obs.ci95);
  const evCi = Object.keys(ci).length ? ci : rec(picked?.ev_ci);
  const equity = rec(a?.equity);
  const bootEq = rec(equity.bootstrap);
  const endCap = rec(bootEq.ending_capital_cents);
  const ddBoot = rec(bootEq.max_drawdown_cents);
  const binary = rec(rec(a?.robustness).binary_entry_sensitivity);
  const binaryRows = Array.isArray(binary.rows) ? (binary.rows as Array<Record<string, unknown>>) : [];
  const at70 = binaryRows.find((r) => r.entry_cents === 70);
  const hurdle = rec(a?.economic_hurdle);
  const unc = rec(a?.uncertainty);
  const game = rec(unc.game_cluster_ci);
  const date = rec(unc.date_cluster_ci);
  return [
    "",
    "## Finite-sample analysis",
    `- Provenance: OBSERVED / DERIVED / HYPOTHETICAL / UNAVAILABLE`,
    `- EV contract: OBSERVED PATH EV = E[exit_close − entry_close]; BOOK-PRICE EV = P(WIN)×(WIN−entry)+P(LOSS)×(LOSS−entry); SETTLEMENT EV = P(YES)×(100−entry)+P(NO)×(0−entry); PATH WIN ≠ SETTLEMENT YES`,
    `- Observed path EV: ${obs.estimate_cents ?? picked?.mean_cents ?? "—"}¢ (n=${obs.n ?? picked?.n ?? "—"})`,
    `- EV inference: estimate ${sig.estimate ?? obs.estimate_cents ?? picked?.mean_cents ?? "—"} · SE ${evCi.standard_error ?? sig.standard_error ?? "—"} · t ${sig.t_statistic ?? evCi.t_statistic ?? "—"} · p ${sig.p_value ?? evCi.p_value ?? "—"} · H0 EV = 0`,
    `- 95% CI: ${evCi.lower ?? "—"} — ${evCi.upper ?? "—"} · ZERO INSIDE CI ${sig.zero_inside_ci === true || evCi.zero_inside_ci === true ? "YES" : sig.zero_inside_ci === false || evCi.zero_inside_ci === false ? "NO" : "—"}`,
    `- P(EV > 0): NOT COMPUTED`,
    `- Book-price EV: ${book.status === "HYPOTHETICAL" ? `${book.ev_cents}¢` : "UNAVAILABLE"}`,
    `- Book Wilson EV CI: ${rec(book.wilson_ev_ci).lower ?? "—"} — ${rec(book.wilson_ev_ci).upper ?? "—"} · ZERO INSIDE ${rec(book.wilson_ev_ci).zero_inside_ci === true ? "YES" : rec(book.wilson_ev_ci).zero_inside_ci === false ? "NO" : "—"}`,
    `- Exact-binomial EV CI: ${rec(book.exact_binomial_ev_ci).lower ?? "—"} — ${rec(book.exact_binomial_ev_ci).upper ?? "—"}`,
    `- Survivability: ${rec(rec(a?.diagnostics).survivability).prose ?? "—"}`,
    `- results_math: ${String(a?.results_math_code_version ?? a?.code_version ?? "derived")}`,
    `- Settlement EV: ${!settle.status || settle.status === "UNAVAILABLE" ? "UNAVAILABLE (terminal missing)" : `${settle.ev_cents ?? "—"}¢`}`,
    `- Reference / mean observed / sizing: ${prices.reference_cents ?? "—"}¢ / ${prices.mean_observed_entry_cents ?? "—"}¢ / ${prices.sizing_cents ?? "—"}¢`,
    `- Contracts @ sizing price: ${sizing.contracts ?? "—"} · deployed ${sizing.deployed_cents ?? "—"}¢ · residual ${sizing.residual_cents ?? "—"}¢`,
    `- Capitalized observed path EV: ${observed.expected_allocation_dollars ?? "—"} / allocation · SE ${observed.se_allocation_dollars ?? "—"} · 95% CI ${rec(observed.ev_ci_dollars).lower ?? "—"} — ${rec(observed.ev_ci_dollars).upper ?? "—"}`,
    `- Break-even total cost / contract: ${hurdle.break_even_total_cost_cents ?? obs.estimate_cents ?? picked?.mean_cents ?? "—"}¢ · not profit · fees/slippage/fill not measured`,
    `- Observation CI / game-cluster / date-cluster: ${rec(unc.observation_ci).status ?? (evCi.lower != null ? "DERIVED" : "—")} / ${game.status ?? derived.gameCluster.status} / ${date.status ?? derived.dateCluster.status}`,
    `- Capitalized distribution $: P5 ${dist.p5_dollars ?? "—"} · P50 ${dist.p50_dollars ?? dist.median_dollars ?? "—"} · P95 ${dist.p95_dollars ?? "—"} · worst ${dist.worst_dollars ?? "—"} · best ${dist.best_dollars ?? "—"}`,
    `- Binary 100/0 at 70¢: EV ${at70?.payoff_ev_cents ?? "—"}¢ · margin ${at70?.margin ?? "—"} · HYPOTHETICAL · P(WIN) ≠ EV`,
    `- Sequence max DD $: ${observed.max_dd_allocation_dollars ?? "—"} · ${observed.max_dd_pct_allocation ?? "—"} of allocation · ${observed.max_dd_pct_bankroll ?? "—"} of bankroll`,
    `- Bootstrap ending capital: observed ${endCap.observed ?? "—"} · median ${endCap.median ?? "—"} · P5 ${endCap.p5 ?? "—"} · P95 ${endCap.p95 ?? "—"}`,
    `- Bootstrap max DD: observed ${ddBoot.observed ?? "—"} · median ${ddBoot.median ?? "—"} · P95 ${ddBoot.p95 ?? "—"}`,
    `- Risk of ruin: NOT COMPUTED`,
  ].join("\n");
}

export function buildResultsJson(result: AnswerResult): string {
  return JSON.stringify(
    {
      execution_status: result.execution_status ?? null,
      research_object_id: result.research_object_id ?? null,
      population_n: result.summary?.population_n ?? result.population?.count ?? null,
      analysis: (result as { analysis?: unknown }).analysis ?? null,
      measurements: result.measurements ?? [],
      empirical_partition: result.empirical_partition ?? {
        status: "JOINT_PARTITION_NOT_CURRENTLY_MEASURED",
      },
      population: {
        count: result.population?.count ?? null,
        trades: result.population?.trades ?? result.population?.rows ?? [],
        rows_truncated: result.population?.rows_truncated ?? false,
      },
      caveats: result.caveats ?? [],
      provenance: result.provenance ?? {},
    },
    null,
    2,
  );
}

export function buildAggregateCsv(result: AnswerResult): string {
  const a = rec((result as { analysis?: unknown }).analysis);
  const obs = rec(a.observed_ev);
  const book = rec(a.book_price).status ? rec(a.book_price) : rec(a.hypothetical_payoff);
  const cap = rec(a.allocation).status ? rec(a.allocation) : rec(a.capitalization);
  const sizing = rec(cap.sizing);
  const observed = rec(cap.observed);
  const ci = rec(obs.ci95);
  const sig = rec(obs.significance);
  const boot = rec(rec(a.uncertainty).bootstrap);
  const bootMean = rec(boot.mean);
  const bootSharpe = rec(boot.sharpe);
  const wilson = rec(book.wilson);
  const wilsonEv = rec(book.wilson_ev_ci);
  const dist = rec(a.observed_returns);
  const settle = rec(a.settlement).status ? rec(a.settlement) : rec(a.settlement_payoff);
  const headers = [
    "N",
    "win",
    "loss",
    "mean_return",
    "median_return",
    "std_return",
    "variance",
    "wilson_low",
    "wilson_high",
    "book_ev",
    "book_ev_wilson_low",
    "book_ev_wilson_high",
    "observed_ev",
    "observed_ev_se",
    "observed_ev_t",
    "observed_ev_p",
    "observed_ev_ci_low",
    "observed_ev_ci_high",
    "bootstrap_ev_low",
    "bootstrap_ev_high",
    "sharpe",
    "sharpe_bootstrap_low",
    "sharpe_bootstrap_high",
    "allocation",
    "contracts",
    "deployed",
    "capitalized_ev",
    "capitalized_ci_low",
    "capitalized_ci_high",
    "max_drawdown",
    "terminal_coverage",
    "terminal_status",
    "book_status",
    "observed_status",
  ];
  const values = [
    obs.n ?? dist.n ?? result.summary?.population_n ?? "",
    book.win_n ?? "",
    book.loss_n ?? "",
    dist.mean_cents ?? obs.estimate_cents ?? "",
    dist.median_cents ?? "",
    dist.std_cents ?? "",
    dist.variance_cents ?? "",
    wilson.lower ?? "",
    wilson.upper ?? "",
    book.ev_cents ?? "",
    wilsonEv.lower ?? "",
    wilsonEv.upper ?? "",
    obs.estimate_cents ?? "",
    ci.standard_error ?? sig.standard_error ?? "",
    sig.t_statistic ?? ci.t_statistic ?? "",
    sig.p_value ?? ci.p_value ?? "",
    ci.lower ?? "",
    ci.upper ?? "",
    bootMean.lower ?? "",
    bootMean.upper ?? "",
    dist.observed_path_sharpe ?? dist.sharpe_trade ?? "",
    bootSharpe.lower ?? "",
    bootSharpe.upper ?? "",
    sizing.allocation_cents ?? "",
    sizing.contracts ?? "",
    sizing.deployed_cents ?? "",
    observed.expected_allocation_dollars ?? "",
    rec(observed.ev_ci_dollars).lower ?? "",
    rec(observed.ev_ci_dollars).upper ?? "",
    observed.max_dd_allocation_dollars ?? "",
    rec(a.data_quality).terminal_coverage ?? "",
    settle.status ?? "",
    book.status ?? "",
    obs.status ?? dist.status ?? "",
  ];
  return [headers.join(","), values.map(csvEscape).join(",")].join("\n");
}

function csvEscape(value: unknown): string {
  if (value == null) return "";
  const s = String(value);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function buildTradeLogCsv(result: AnswerResult): string {
  const trades = result.population?.trades ?? result.population?.rows ?? [];
  const headers = [
    "ticker",
    "internal_game_id",
    "entry_ordinal",
    "entry_price_e4",
    "entry_ts",
    "entry_close",
    "exit_ts",
    "exit_close",
    "hyp_pnl_cents",
    "mae_cents",
    "mfe_cents",
    "holding_seconds",
    "path_true",
    "terminal_yes",
    "alignment",
  ];
  const lines = [headers.join(",")];
  for (const raw of trades) {
    const row = raw as Record<string, unknown>;
    lines.push(headers.map((h) => csvEscape(row[h])).join(","));
  }
  return lines.join("\n");
}
