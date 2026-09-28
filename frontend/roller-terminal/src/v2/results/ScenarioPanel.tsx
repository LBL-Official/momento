import { useMemo, useState } from "react";
import type { DetailPayload } from "../components/DetailDrawer";
import type { AnswerResult } from "./ResultsAnswer";
import type { WorkflowDraft } from "../workflow/types";
import {
  allScenarios,
  hypotheticalEv,
  saveUserPreset,
  type ScenarioPreset,
} from "./scenarioPresets";
import { cellByKey, jointIsMeasured } from "./partitionTypes";
import { formatPct } from "./wilson";
import { computeFiniteMath, isModelA8040 } from "./finiteMath";
import { pathRate, terminalRate } from "./measurementLookup";
import { readResultsContract } from "./resultsContract";

type Props = {
  result: AnswerResult;
  draft?: WorkflowDraft | null;
  onOpenDetail: (detail: DetailPayload) => void;
};

function jointCells(result: AnswerResult) {
  const p = result.empirical_partition;
  if (!jointIsMeasured(p)) return null;
  const tAndW = cellByKey(p, "T_AND_W")?.n ?? 0;
  const tAndNotW = cellByKey(p, "T_AND_NOT_W")?.n ?? 0;
  const notTAndW = cellByKey(p, "NOT_T_AND_W")?.n ?? 0;
  const notTAndNotW = cellByKey(p, "NOT_T_AND_NOT_W")?.n ?? 0;
  const n = p?.n_joint_available ?? tAndW + tAndNotW + notTAndW + notTAndNotW;
  if (!n) return null;
  return { tAndW, tAndNotW, notTAndW, notTAndNotW, n };
}

export default function ScenarioPanel({ result, draft, onOpenDetail }: Props) {
  const [tick, setTick] = useState(0);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("My scenario");
  const scenarios = useMemo(() => {
    void tick;
    return allScenarios();
  }, [tick]);

  const path = pathRate(result);
  const yes = terminalRate(result);
  const t40Rate = path.rate;
  const yesRate = yes.rate;
  const cells = jointCells(result);
  const contract = readResultsContract(result);
  const modelA = !contract.lastTrade && isModelA8040(draft, result);
  const math = computeFiniteMath(result, draft);

  return (
    <section className="ws-level">
      <p className="v2-kicker">Level 4 · What hypothetical payoff structures would this imply?</p>
      <h2>Hypothetical payoff analysis</h2>
      <p className="muted small">
        {contract.lastTrade
          ? "LAST TRADE ≠ FILL. Hypothetical payoff chips are not last-trade economics."
          : "HYPOTHETICAL · CANDLE PATH ≠ FILL. These numbers apply assumptions to this run’s empirical probabilities. They are not this run’s live P&L."}
      </p>
      <div className="ws-scenario-grid">
        {scenarios.map((preset) => {
          const ev = hypotheticalEv({
            preset,
            yesRate,
            t40Rate: modelA ? t40Rate : preset.kind === "empirical" ? t40Rate : null,
            cells: modelA ? cells : null,
            modelAPathOnly: modelA && !cells && preset.stopVsHold === "stop",
          });
          const observedLabel = contract.lastTrade
            ? "UNAVAILABLE"
            : math.observedEvCents != null
              ? `Obs EV ${math.observedEvCents.toFixed(2)}¢`
              : math.modelAEvCents != null
                ? `Model A ${math.modelAEvCents.toFixed(2)}¢`
                : t40Rate != null
                  ? `Path ${formatPct(t40Rate)}`
                  : "Observed path";
          return (
            <button
              key={preset.id}
              type="button"
              className="ws-scenario-card"
              onClick={() =>
                onOpenDetail({
                  title: preset.name,
                  subtitle: preset.kind === "empirical" ? "EMPIRICAL" : "HYPOTHETICAL PAYOFF STRUCTURE",
                  value:
                    preset.kind === "empirical"
                      ? observedLabel
                      : ev.evPerContract != null
                        ? `EV ${ev.evPerContract.toFixed(4)}`
                        : math.observedEvCents != null
                          ? `Obs EV ${math.observedEvCents.toFixed(2)}¢`
                          : "Assumption required",
                  sections: [
                    {
                      heading: "Inputs",
                      body: (
                        <p>
                          Entry {preset.entryCents}¢ · barrier {preset.barrierCents ?? "none"} ·{" "}
                          {preset.stopVsHold}
                          {!modelA && preset.stopVsHold === "stop"
                            ? " · 80→40 Model A does not apply to this query"
                            : ""}
                        </p>
                      ),
                    },
                    {
                      heading: "Empirical probabilities",
                      body: (
                        <p>
                          P(PATH) = {formatPct(t40Rate, 2)} · P(W) = {formatPct(yesRate, 2)}
                          {cells ? ` · joint N = ${cells.n}` : " · joint not measured"}
                        </p>
                      ),
                    },
                    {
                      heading: "Finite payoff / EV",
                      body: (
                        <p className="evidence">
                          {preset.kind === "empirical"
                            ? math.observedEvCents != null
                              ? `Mean candle-path P&L = ${math.observedEvCents.toFixed(2)}¢ on ${math.observedN} exits`
                              : math.modelAEvCents != null
                                ? `Model A EV = ${math.modelAEvCents.toFixed(2)}¢ (20 − 60q)`
                                : "No payoff. Observed path only."
                            : ev.evPerContract != null
                              ? `EV / contract = ${ev.evPerContract.toFixed(4)} · win ${ev.winPnL?.toFixed(4)} · lose/hold ${ev.losePnL?.toFixed(4)} · stop ${ev.stopPnL?.toFixed(4) ?? "—"}`
                              : math.observedEvCents != null
                                ? `Query-specific mean hyp P&L = ${math.observedEvCents.toFixed(2)}¢. 80/40 fee cards do not apply.`
                                : "Insufficient empirical inputs. Settlement and 80→40 payoffs are not invented."}
                        </p>
                      ),
                    },
                    {
                      heading: "Assumptions",
                      body: (
                        <ul>
                          {ev.assumptions.map((a) => (
                            <li key={a}>{a}</li>
                          ))}
                        </ul>
                      ),
                    },
                    {
                      heading: "Drawdown / ruin",
                      body: (
                        <p>
                          {math.maxDrawdownCents != null
                            ? `Max drawdown ${math.maxDrawdownCents}¢ (${math.maxDrawdownSource})`
                            : "Drawdown not measured — no P&L sequence"}
                          {" · "}
                          {math.riskOfRuin != null
                            ? `Risk of ruin ${(math.riskOfRuin * 100).toFixed(2)}% on $50 snapshot`
                            : "Risk of ruin not measured"}
                          . HYPOTHETICAL.
                        </p>
                      ),
                    },
                  ],
                })
              }
            >
              <div className="v2-kicker">
                {preset.kind === "empirical" ? "EMPIRICAL" : "HYPOTHETICAL"}
              </div>
              <strong>{preset.name}</strong>
              {preset.kind === "empirical" ? (
                <p className="evidence">
                  Path {formatPct(t40Rate)}
                  {yesRate != null ? ` · YES ${formatPct(yesRate)}` : " · YES absent"}
                </p>
              ) : (
                <p className="evidence">
                  {ev.evPerContract != null
                    ? `EV ${ev.evPerContract.toFixed(4)}`
                    : math.observedEvCents != null
                      ? `Obs ${math.observedEvCents.toFixed(2)}¢`
                      : "—"}
                </p>
              )}
              <p className="muted small">
                {math.maxDrawdownCents != null
                  ? `Max DD ${math.maxDrawdownCents}¢`
                  : "Drawdown not measured"}
                {math.riskOfRuin != null ? ` · RoR ${(math.riskOfRuin * 100).toFixed(1)}%` : ""}
              </p>
            </button>
          );
        })}
      </div>
      {creating ? (
        <div className="ws-create-scenario">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              const preset: ScenarioPreset = {
                id: `user_${Date.now().toString(36)}`,
                name: name.trim() || "Untitled scenario",
                kind: "hypothetical",
                stopVsHold: "stop",
                entryCents: 80,
                barrierCents: 40,
                entryFee: { role: "taker", coef: 0.07 },
                exitFee: { role: "taker", coef: 0.07 },
                builtIn: false,
              };
              saveUserPreset(preset);
              setCreating(false);
              setTick((n) => n + 1);
            }}
          >
            Save scenario
          </button>
        </div>
      ) : (
        <button type="button" className="btn-secondary" onClick={() => setCreating(true)}>
          Create scenario
        </button>
      )}
    </section>
  );
}
