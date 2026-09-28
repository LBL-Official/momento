import type { VitalIntegrationProof } from "./api/vitalApi";
import { toneForProof } from "./format";

type Props = {
  proof: VitalIntegrationProof | null;
  variant?: "desk" | "detail";
};

const LEVELS = [
  ["L1_PROCESS", "L1 Process"],
  ["L2_RUNTIME", "L2 Runtime"],
  ["L3_CONTROL", "L3 Control"],
  ["L4_CONFIGURATION", "L4 Config"],
  ["L5_LOAD", "L5 Load"],
  ["L6_EVALUATION", "L6 Eval"],
  ["L7_EXECUTION", "L7 Exec"],
  ["L8_EXCHANGE", "L8 Exchange"],
] as const;

const SUITES = [
  ["A_PRODUCTION_READ", "A Read"],
  ["B_DEMO_CONTROL", "B Demo control"],
  ["C_DEMO_STRATEGY", "C Demo strategy"],
  ["D_PRODUCTION_STRATEGY_LOAD", "D Prod load"],
] as const;

const CHAIN = [
  "DESIRED",
  "WRITTEN",
  "OBSERVED",
  "LOADED",
  "EVALUATING",
  "SIGNALING",
  "RISK_APPROVED",
  "SUBMITTING",
  "ACKNOWLEDGED",
  "FILLED",
] as const;

function statusOf(row: unknown): string {
  if (row && typeof row === "object" && "status" in row) {
    return String((row as { status?: string }).status || "OBSERVATION_UNAVAILABLE");
  }
  return String(row || "OBSERVATION_UNAVAILABLE");
}

export default function IntegrationProofPane({ proof, variant = "desk" }: Props) {
  const accepted = proof?.accepted === true;
  const claim = proof?.lifecycle_claim || "OBSERVATION_UNAVAILABLE";
  return (
    <section className="vital-card vital-integration-proof" aria-label="Live-service integration proof">
      <div className="vital-row-head">
        <div>
          <p className="ws-kicker">Integration proof</p>
          <h2>Vital ↔ live service</h2>
        </div>
        <p className={`vital-tone ${accepted ? "is-live" : "is-unread"}`}>
          {accepted ? "ACCEPTED" : "NOT ACCEPTED"}
        </p>
      </div>
      <p className="muted small">
        RUNNING ≠ HEALTHY ≠ EXECUTING · claim {claim}
        {proof?.strategy_status ? ` · strategy ${proof.strategy_status}` : ""}
        {proof?.factory ? " · no production test order" : ""}
      </p>
      <dl className="vital-mini-dl">
        {SUITES.map(([key, label]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd className={`vital-tone ${toneForProof(statusOf(proof?.suites?.[key]))}`}>
              {statusOf(proof?.suites?.[key])}
            </dd>
          </div>
        ))}
      </dl>
      {variant === "detail" ? (
        <>
          <dl className="vital-mini-dl">
            {LEVELS.map(([key, label]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd className={`vital-tone ${toneForProof(statusOf(proof?.levels?.[key]))}`}>
                  {statusOf(proof?.levels?.[key])}
                </dd>
              </div>
            ))}
          </dl>
          <dl className="vital-mini-dl">
            {CHAIN.map((key) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd className={`vital-tone ${toneForProof(statusOf(proof?.chain?.[key]))}`}>
                  {statusOf(proof?.chain?.[key])}
                </dd>
              </div>
            ))}
          </dl>
        </>
      ) : null}
      {proof?.blocking?.length ? (
        <p className="muted small">Blocking · {proof.blocking.join(" · ")}</p>
      ) : null}
    </section>
  );
}
