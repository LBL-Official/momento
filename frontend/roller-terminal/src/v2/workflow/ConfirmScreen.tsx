import { useEffect, useState } from "react";
import type { ResearchCapabilityPreview } from "../../researchCapabilityPreview";
import type { ValidationSnapshot } from "../../researchFreshness";
import type { Spec } from "../../researchTypes";
import {
  entrySummary,
  exitSummary,
  composeQuestionFromDraft,
  universeSummaryLines,
} from "./questionFromDraft";
import type { ResearchPlan } from "./resolveResearchPlan";
import type { ApiAvailability } from "../../api/base";
import type { WorkflowDraft } from "./types";
import type { WarehouseCompile } from "../../api/warehouseResearch";
import WarehouseConfirmPanel from "../warehouse/WarehouseConfirmPanel";
import type { ResearchQuestionJson, SyntacticError } from "../warehouse/researchQuestionFromDraft";

type ServerCompile = {
  status?: string;
  execution_path?: string;
  reference_match?: string | null;
  reasons?: string[];
  omitted_dimensions?: string[];
  available?: string[];
  unavailable?: string[];
  observation_basis?: string | null;
  question?: {
    universe?: {
      leagues?: string[];
      markets?: string[];
      market_data?: string[];
      date_from?: string | null;
      date_to?: string | null;
    };
    entry_conditions?: Array<{ ordinal?: string; price_e4?: number; period?: string | null }>;
  };
};

type Props = {
  draft: WorkflowDraft;
  resolution: ResearchPlan;
  spec: Spec;
  validationSnapshot: ValidationSnapshot | null;
  capabilityPreview: ResearchCapabilityPreview | null;
  runBusy: boolean;
  templateReady: boolean;
  acceptLimitations: boolean;
  onAcceptLimitations: (next: boolean) => void;
  compile: ServerCompile | null;
  compileBusy: boolean;
  warehouseQuestion?: ResearchQuestionJson | null;
  warehouseErrors?: SyntacticError[];
  warehouseCompile?: WarehouseCompile | null;
  warehouseBusy?: boolean;
  apiAvailability?: ApiAvailability | null;
  onRun: () => void;
  onEdit: (step: "start" | "entry" | "exit") => void;
  onSaveQuestion: () => void;
};

function statusLabel(status: string): string {
  if (status === "READY") return "● READY";
  if (status === "READY_WITH_LIMITATIONS") return "◐ READY WITH LIMITATIONS";
  if (status === "DATA_REQUIRED") return "○ DATA REQUIRED";
  if (status === "OPERATION_REQUIRED") return "○ OPERATION REQUIRED";
  return status;
}

export default function ConfirmScreen({
  draft,
  resolution,
  spec,
  validationSnapshot,
  capabilityPreview,
  runBusy,
  templateReady: _templateReady,
  acceptLimitations,
  onAcceptLimitations,
  compile,
  compileBusy,
  warehouseQuestion = null,
  warehouseErrors = [],
  warehouseCompile = null,
  warehouseBusy = false,
  apiAvailability,
  onRun,
  onEdit,
  onSaveQuestion,
}: Props) {
  const question = composeQuestionFromDraft(draft, resolution);
  const authoritative = Boolean(compile) && !compileBusy;
  const status = authoritative && compile?.status ? compile.status : resolution.status;
  const path = authoritative && compile?.execution_path ? compile.execution_path : resolution.executionPath;
  const reasons =
    authoritative && compile?.reasons?.length ? compile.reasons : resolution.reasons;
  const omitted =
    authoritative && compile?.omitted_dimensions
      ? compile.omitted_dimensions
      : resolution.omittedDimensions;
  const frozen = path === "frozen_reference";
  const generic = path === "generic_query";
  const compiledBasis = String(compile?.observation_basis || "");
  const compiledAvailable = compile?.available ?? [];
  const lastPrint = compiledBasis
    ? compiledBasis.includes("LAST_TRADE")
    : compiledAvailable.includes("last_trade_close_cross")
      ? true
      : compiledAvailable.includes("tradable_yes_bid_close_cross")
        ? false
        : draft.universe.marketData.includes("last_trade") &&
          !draft.universe.marketData.includes("candles");
  const apiDown =
    !runBusy &&
    (apiAvailability === "API_UNREACHABLE" || apiAvailability === "API_REQUEST_FAILED");
  const warehouseDesk = Boolean(warehouseQuestion);
  const warehouseReady = warehouseCompile?.status === "READY" && warehouseErrors.length === 0;
  const canRun = warehouseDesk && !apiDown && warehouseReady && !warehouseBusy;
  const [ack, setAck] = useState(acceptLimitations);

  useEffect(() => {
    setAck(acceptLimitations);
  }, [acceptLimitations]);

  return (
    <div className="ws-flow ws-confirm">
      <header className="ws-flow-head">
        <p className="v2-kicker">Confirm</p>
        <h1 className="v2-page-title">Your research</h1>
      </header>

      <section className="ws-confirm-question">
        <p className="v2-kicker">Research question</p>
        <p className="ws-question-hero">{question}</p>
      </section>

      {warehouseQuestion ? (
        <WarehouseConfirmPanel
          question={warehouseQuestion}
          errors={warehouseErrors}
          compile={warehouseCompile}
          busy={Boolean(warehouseBusy)}
        />
      ) : null}

      {!warehouseQuestion ? (
        <section className="ws-review-block" aria-label="Sport availability">
          <p className="v2-kicker">NOT AVAILABLE</p>
          <p>Production ROLLER executes NBA, MLB, NCAAB, ATP, and WTA warehouse research. Mixed ATP+WTA and tennis without a tour cannot run. WNBA cannot run.</p>
        </section>
      ) : null}

      <section className="ws-confirm-grid">
        <button type="button" className="ws-confirm-card" onClick={() => onEdit("start")}>
          <h2>Universe</h2>
          <dl>
            {universeSummaryLines(draft).map((row) => (
              <div key={row.k}>
                <dt>{row.k}</dt>
                <dd>{row.v}</dd>
              </div>
            ))}
          </dl>
        </button>
        <button type="button" className="ws-confirm-card" onClick={() => onEdit("entry")}>
          <h2>Entry</h2>
          <p>{entrySummary(draft)}</p>
          <p className="muted small">
            {lastPrint
              ? "Last-trade print crossing. LAST TRADE ≠ YES BID. Minutes without a print are absent, not forward-filled. PIT snap is PBP_ts ≤ entry_ts. CANDLE/PRINT PATH ≠ FILL."
              : "Tradable yes_bid_close crossing. Game-level ordinal, then PBP snap filter. Base TE records PIT score and market path at that bar."}
          </p>
        </button>
        <button type="button" className="ws-confirm-card" onClick={() => onEdit("exit")}>
          <h2>Observations</h2>
          <p>{exitSummary(draft)}</p>
          <p className="muted small">
            {lastPrint
              ? "CANDLE/PRINT PATH ≠ FILL · LAST TRADE ≠ YES BID · TE WIN/LOSS is exact-timestamp · settlement is Kalshi result, not the box score"
              : "CANDLE PATH ≠ EXECUTABLE EXIT · CANDLE ≠ FILL · TE WIN/LOSS is exact-timestamp"}
          </p>
        </button>
        <div className="ws-confirm-card">
          <h2>Availability</h2>
          <p className={canRun || runBusy ? "ws-review-ready" : "ws-review-attention"}>
            {runBusy ? "● MEASURING" : apiDown ? apiAvailability : statusLabel(status)}
          </p>
          {runBusy ? (
            <p className="muted small">
              Execute is a background job. /health stays reachable. This is not N = 0.
            </p>
          ) : null}
          {apiDown ? (
            <p className="muted small">
              Infrastructure failure — not N = 0, DATA REQUIRED, OPERATION REQUIRED, or an empty
              population.
            </p>
          ) : null}
          {compileBusy ? <p className="muted small">Server compile…</p> : null}
          {reasons.length ? (
            <ul>
              {reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          ) : (
            <p className="muted small">Requested operations are defined and measurable.</p>
          )}
          {omitted.length ? (
            <label className="ws-ack">
              <input
                type="checkbox"
                checked={ack}
                onChange={(e) => {
                  setAck(e.target.checked);
                  onAcceptLimitations(e.target.checked);
                }}
              />
              Acknowledge omitted dimensions: {omitted.join(", ")}
            </label>
          ) : null}
        </div>
      </section>

      <section className="ws-confirm-meta">
        <dl>
          <div>
            <dt>Execution path</dt>
            <dd>{warehouseQuestion ? "warehouse ResearchQuestion → ConditionalBacktest" : "none"}</dd>
          </div>
          <div>
            <dt>Observability</dt>
            <dd>
              {frozen
                ? "warehouse lock"
                : generic
                  ? lastPrint
                    ? "LAST-TRADE PRINT OBSERVED · LAST TRADE ≠ YES BID · CANDLE/PRINT PATH ≠ FILL"
                    : "CANDLE-LEVEL OBSERVED · CANDLE PATH ≠ FILL"
                  : "—"}
            </dd>
          </div>
          <div>
            <dt>Price rule</dt>
            <dd>
              {generic
                ? lastPrint
                  ? "last_trade_close_cross · not yes_bid · minutes without a print are absent"
                  : "tradable_yes_bid_close_cross"
                : frozen
                  ? "lock binding"
                  : "—"}
            </dd>
          </div>
          <div>
            <dt>PBP alignment</dt>
            <dd>snap at entry timestamp · unaligned fails a requested period/clock filter</dd>
          </div>
          <div>
            <dt>Terminal source</dt>
            <dd>Kalshi settlement on the warehouse path. Missing settlement is missing, not inferred. Candle path ≠ fill.</dd>
          </div>
          <div>
            <dt>Accept through</dt>
            <dd>
              {draft.entryConditions[0]?.maxEntryCents != null
                ? `${draft.entryConditions[0].maxEntryCents}¢ observed close ceiling · not an assumed fill at the trigger`
                : "none — entry is the observed close, not the trigger"}
            </dd>
          </div>
          <div>
            <dt>Exposure</dt>
            <dd>
              {draft.exposureEnforcementMode === "strategy_enforced" &&
              draft.exposureUnit === "GAME" &&
              draft.maxEntriesPerGame === 1
                ? "one trade per game · first chronological First Touch · later 80-crosses on the same game are not taken"
                : "per market First Touch · later gamesides are separate rows"}
            </dd>
          </div>
          <div>
            <dt>Base TE</dt>
            <dd>
              PIT entry state + exact-timestamp WIN/LOSS book on results
              {draft.teFilters?.scoreSide && draft.teFilters.scoreSide !== "any"
                ? ` · ${draft.teFilters.scoreSide}`
                : ""}
              {(draft.teFilters?.exactDiffs ?? []).length
                ? ` · exact lead ${draft.teFilters?.exactDiffs?.join(",")}`
                : ""}
              {draft.teFilters?.customRange?.min != null || draft.teFilters?.customRange?.max != null
                ? ` · range ${draft.teFilters?.customRange?.min ?? "…"}–${draft.teFilters?.customRange?.max ?? "…"} (OR-union with exact)`
                : ""}
              {draft.teFilters?.absDiff && draft.teFilters.absDiff !== "any"
                ? ` · |Δ| ${draft.teFilters.absDiff.replace("_", "–").replace("plus", "+")}`
                : ""}
            </dd>
          </div>
        </dl>
      </section>

      <details className="ws-review-tech">
        <summary>View technical details</summary>
        <p className="muted small">Server compile is authoritative. Client preview cannot force the path.</p>
        <pre className="spec-json">
          {JSON.stringify(
            {
              preview: resolution,
              compile,
              validation: validationSnapshot?.payload ?? null,
              identity: spec.identity ?? null,
              capability_summary: capabilityPreview?.summary ?? null,
            },
            null,
            2,
          )}
        </pre>
      </details>

      <footer className="ws-define-footer">
        <button type="button" className="btn-secondary" onClick={() => onEdit("start")}>
          ← Edit research
        </button>
        <div className="ws-flow-actions">
          <button type="button" className="btn-secondary" onClick={onSaveQuestion}>
            Save as research question
          </button>
          <button
            type="button"
            className="btn-primary ws-step-primary"
            disabled={!canRun || runBusy || compileBusy || warehouseBusy}
            onClick={onRun}
          >
            {runBusy ? "Measuring…" : "Run research"}
          </button>
        </div>
      </footer>
    </div>
  );
}
