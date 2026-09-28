import type { Spec } from "../../researchTypes";
import type { ValidationSnapshot } from "../../researchFreshness";
import type { ResearchCapabilityPreview } from "../../researchCapabilityPreview";
import { asArr, asObj } from "../../researchTypes";
import { composeQuestion } from "../define/questionComposer";
import { lockedTemplateKind } from "../define/defineCatalog";
import { overlayBlocksReadyToRun, readyToRun } from "../define/honesty";
import type { RecognizedIntent } from "../define/recognizedIntent";

type Props = {
  spec: Spec;
  intent: RecognizedIntent;
  validationSnapshot: ValidationSnapshot | null;
  capabilityPreview: ResearchCapabilityPreview | null;
  canRunFromValidation: boolean;
  runBusy: boolean;
  onRun: () => void;
  onEdit: () => void;
};

export default function ReviewRunView({
  spec,
  intent,
  validationSnapshot,
  capabilityPreview,
  canRunFromValidation,
  runBusy,
  onRun,
  onEdit,
}: Props) {
  const question = composeQuestion(spec, intent);
  const lock = lockedTemplateKind(spec);
  const overlayBlocks = overlayBlocksReadyToRun(intent);
  const runnable = readyToRun(canRunFromValidation, intent);
  const status = validationSnapshot?.payload.status;
  const unresolved = validationSnapshot?.payload.unresolved ?? [];
  const errors = validationSnapshot?.payload.errors ?? [];

  const attentionReasons: string[] = [];
  if (overlayBlocks) {
    attentionReasons.push(
      ...intent.clauses.map((c) => `${c.label} is recognized but not constructible`),
    );
    if (intent.selectedSeason) {
      attentionReasons.push(
        `Season ${intent.selectedSeason} is STRUCTURAL and is not applied to a locked population`,
      );
    }
  }
  if (status === "UNRESOLVED" || status === "INVALID") {
    attentionReasons.push(`Validation is ${status}`);
  }
  if (!validationSnapshot) {
    attentionReasons.push("This study has not been validated yet.");
  }

  const pop = asObj(spec.population_binding);
  const measurements = asArr(spec.measurement_requests)
    .map((m) => (typeof m === "string" ? m : String(asObj(m).name || asObj(m).kind || "")))
    .filter(Boolean);

  return (
    <div className="ws-review">
      <header className="ws-review-head">
        <p className="v2-kicker">Step 2 · Review & Run</p>
        <h1 className="v2-page-title">{question}</h1>
        <p className={runnable ? "ws-review-ready" : "ws-review-attention"}>
          {runnable ? "Ready to run" : "Requires attention"}
        </p>
      </header>

      {!runnable ? (
        <section className="ws-review-block warn">
          <h2>Why this cannot run</h2>
          <ul>
            {attentionReasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="muted small">
            Roller will not simplify this question to a nearby lock such as FIRST80 · Q3.
          </p>
        </section>
      ) : null}

      <dl className="ws-review-dl">
        <div>
          <dt>Population</dt>
          <dd>
            {lock || String(asObj(spec.identity).name || "Unspecified")}
            {Array.isArray(pop.leagues) ? ` · ${(pop.leagues as string[]).join(", ")}` : ""}
          </dd>
        </div>
        <div>
          <dt>Conditions</dt>
          <dd>
            {intent.clauses.length
              ? intent.clauses.map((c) => c.label).join(" · ")
              : lock
                ? "Implied by the lock (no extra path overlay)"
                : "None specified"}
          </dd>
        </div>
        <div>
          <dt>Measurements</dt>
          <dd>{measurements.length ? measurements.join(", ") : "t40_rate, kalshi_yes_rate (from lock)"}</dd>
        </div>
        <div>
          <dt>Constructibility</dt>
          <dd>
            {overlayBlocks
              ? "Recognized — not constructible"
              : capabilityPreview?.population.status === "IMPLEMENTED"
                ? "Implemented lock"
                : capabilityPreview?.population.status || "Unknown"}
          </dd>
        </div>
        <div>
          <dt>Research status</dt>
          <dd>{status || "Not validated"}</dd>
        </div>
      </dl>

      <details className="ws-review-tech">
        <summary>Technical details</summary>
        <pre className="spec-json">
          {JSON.stringify(
            {
              validation: validationSnapshot?.payload ?? null,
              capability: capabilityPreview,
              unresolved,
              errors,
            },
            null,
            2,
          )}
        </pre>
      </details>

      <footer className="ws-review-footer">
        <button type="button" className="btn-secondary" onClick={onEdit}>
          Edit research
        </button>
        <button
          type="button"
          className="btn-primary ws-step-primary"
          disabled={!runnable || runBusy}
          onClick={onRun}
        >
          {runBusy ? "Running…" : "Run research"}
        </button>
      </footer>
    </div>
  );
}
