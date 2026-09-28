import type { WarehouseCompile } from "../../api/warehouseResearch";
import type { ResearchQuestionJson, SyntacticError } from "./researchQuestionFromDraft";

type Props = {
  question: ResearchQuestionJson | null;
  errors: SyntacticError[];
  compile: WarehouseCompile | null;
  busy: boolean;
};

function statusLabel(status: string): string {
  if (status === "READY") return "● READY";
  if (status === "ZERO_RESULTS") return "● ZERO RESULTS";
  if (status === "DATA_REQUIRED") return "○ DATA REQUIRED";
  if (status === "OPERATION_REQUIRED") return "○ OPERATION REQUIRED";
  if (status === "INVALID") return "○ INVALID";
  return status;
}

function statusNote(status: string): string {
  if (status === "READY") return "Backend can execute this ResearchQuestion against canonical parquet.";
  if (status === "ZERO_RESULTS")
    return "Valid strategy, required data available, engine executed, population = 0. Not missing data.";
  if (status === "DATA_REQUIRED")
    return "Required data is unavailable. No candle approximation. Not ZERO RESULTS.";
  if (status === "OPERATION_REQUIRED")
    return "Required operation is unimplemented. No synthetic PBP↔candle PIT join.";
  if (status === "INVALID") return "Syntactic validation failed before capability resolution.";
  return "Warehouse compiler is the authority.";
}

export default function WarehouseConfirmPanel({ question, errors, compile, busy }: Props) {
  const status = compile?.status || (errors.length ? "INVALID" : "");
  const cap = compile?.capability;
  const entry = question?.entry_conditions?.[0];
  const win = question?.path_conditions.find((p) => p.outcome === "win");
  const loss = question?.path_conditions.find((p) => p.outcome === "loss");
  const periodLabel = (() => {
    const windows = entry?.period_windows || [];
    if (windows.length) {
      return windows.map((w) => w.period).filter(Boolean).join(" or ");
    }
    return entry?.period || "";
  })();
  const teRequested = (compile as { te_filters?: Record<string, unknown> } | null)?.te_filters;
  const teLabel = (() => {
    if (!teRequested) return "none";
    const custom = (teRequested.customRange || teRequested.custom_range) as { min?: number; max?: number } | undefined;
    if (custom && (custom.min != null || custom.max != null)) {
      return `custom ${custom.min ?? "…"}–${custom.max ?? "…"}`;
    }
    return "scoped";
  })();
  return (
    <section className="ws-warehouse-desk" aria-label="Warehouse research desk">
      <p className="v2-kicker">Warehouse ResearchQuestion</p>
      <p className={status === "READY" || status === "ZERO_RESULTS" ? "ws-review-ready" : "ws-review-attention"}>
        {busy ? "Server compile…" : status ? statusLabel(status) : "—"}
      </p>
      <p className="muted small">{statusNote(status)}</p>
      {errors.length ? (
        <ul>
          {errors.map((e) => (
            <li key={e}>{e.replace(/_/g, " ")}</li>
          ))}
        </ul>
      ) : null}
      {cap?.missing_data?.length ? <p className="muted small">Missing data: {cap.missing_data.join(", ")}</p> : null}
      {cap?.missing_operations?.length ? (
        <p className="muted small">Missing operations: {cap.missing_operations.join(", ")}</p>
      ) : null}
      <dl className="ws-warehouse-meta">
        <div>
          <dt>Observation</dt>
          <dd>
            {compile?.observation_basis || "TRADABLE_YES_BID"} · {compile?.resolution || "1_MINUTE_CANDLE"} · PIT{" "}
            {compile?.pit_field || "available_at"}
          </dd>
        </div>
        <div>
          <dt>Entry</dt>
          <dd>
            {entry?.operation || entry?.ordinal || "—"}
            {entry?.price_e4 != null ? ` ${(entry.price_e4 / 100).toFixed(0)}¢` : ""}
            {entry?.max_entry_e4 != null ? ` accept through ${(entry.max_entry_e4 / 100).toFixed(0)}¢` : ""}
            {periodLabel ? ` ${periodLabel}` : ""}
          </dd>
        </div>
        <div>
          <dt>Base TE</dt>
          <dd>
            {teLabel}
          </dd>
        </div>
        <div>
          <dt>WIN / LOSS</dt>
          <dd>
            {win ? `${win.op} ${(win.price_e4 / 100).toFixed(0)}¢` : "HOLD"}
            {" / "}
            {loss ? `${loss.op} ${(loss.price_e4 / 100).toFixed(0)}¢` : "HOLD"}
          </dd>
        </div>
        <div>
          <dt>Terminal</dt>
          <dd>{question?.requested_dimensions?.join(", ") || question?.terminal || "—"}</dd>
        </div>
        <div>
          <dt>Plan</dt>
          <dd className="ws-mono">{compile?.plan_hash ? compile.plan_hash.slice(0, 16) : "—"}</dd>
        </div>
      </dl>
      <p className="muted small">
        Frontend constructs ResearchQuestion. Backend compiles and executes. CANDLE PATH ≠ FILL.
      </p>
    </section>
  );
}
