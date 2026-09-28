import { useState } from "react";
import EmpiricalStateSpace from "./EmpiricalStateSpace";
import EmpiricalTree from "./EmpiricalTree";
import type { EmpiricalPartition, PartitionCell } from "./partitionTypes";
import { cellTitle, fmtPct } from "./partitionTypes";
import type { DetailPayload } from "../components/DetailDrawer";
import type { Spec } from "../../researchTypes";
import { asObj } from "../../researchTypes";
import { findMeasurement, pathRate, terminalRate } from "./measurementLookup";
import TerminalEfficiencyPanel, { type TeSummary } from "./TerminalEfficiencyPanel";
import {
  GOLDEN_MLB,
  goldenDiffsFromResult,
  hashesMatchGolden,
  isMlbLastTradeResult,
  terminalMissingPhrase,
} from "../mlbContractHonesty";
import { coveragePct } from "./lastTradeResults";

import { readResultsContract } from "./resultsContract";
import {
  binaryBreakeven,
  entryCentsFromResult,
  fmtPct as fmtTradePct,
  fmtPp,
  fmtSignedCents,
  sameNRates,
} from "./tradeHeadline";

type Measurement = {
  name?: string;
  status?: string;
  value?: number | null;
  detail?: Record<string, unknown>;
  caveat?: string | null;
  definition_version?: string | null;
  source?: { artifact?: string; field?: string } | null;
};

export type AnswerResult = {
  research_object_id?: string | null;
  execution_status?: string;
  summary?: {
    population_n?: number | null;
    population_description?: string | null;
  };
  population?: {
    count?: number;
    status?: string;
    rows?: Record<string, unknown>[];
    trades?: Record<string, unknown>[];
    rows_truncated?: boolean;
    funnel?: Array<{
      id?: string;
      condition_id?: string;
      label?: string;
      n?: number;
      qualifying?: number;
    }>;
  };
  hashes?: Record<string, string>;
  dataset_version?: string | null;
  compile?: {
    question?: {
      universe?: {
        date_from?: string | null;
        date_to?: string | null;
        leagues?: string[];
        sports?: string[];
        market_data?: string[];
      };
      entry_conditions?: Array<{ price_e4?: number; ordinal?: string; period?: string | null }>;
      path_conditions?: Array<{ op?: string; price_e4?: number }>;
    };
  };
  measurements?: Measurement[];
  empirical_partition?: EmpiricalPartition | null;
  provenance?: Record<string, unknown>;
  caveats?: string[];
  observation_basis?: string | null;
  mlb?: {
    observation_basis?: string;
    funnel?: Record<string, number>;
    exclusions?: Record<string, number>;
    notes?: string[];
  } | null;
  base_terminal_efficiency?: TeSummary | null;
  analysis?: Record<string, unknown> | null;
  identity?: {
    entry_eligible?: number;
    n_entry_events?: number;
    reported_n?: number;
    exclusions?: Record<string, number>;
    te_scope?: {
      requested?: { score_side?: string; abs_diff?: string; exact_diffs?: number[] } | null;
      n_entry?: number;
      n_scoped?: number;
      n_dropped?: number;
    };
    league_counts?: Record<string, number>;
    terminal_yes?: number;
    terminal_no?: number;
    terminal_missing?: number;
    path_true?: number;
    path_false?: number;
  } | null;
};

type Props = {
  result: AnswerResult | null;
  spec: Spec;
  isStale: boolean;
  viewingSaved?: boolean;
  savedAt?: string | null;
  onOpenDetail: (detail: DetailPayload) => void;
  onOpenEvidence: () => void;
  onReturnToDefine: () => void;
  onSaveResults: () => void;
  onDownload: () => void;
  onPrint?: () => void;
  onNewResearch: () => void;
  onMoveToSuperASI?: () => void;
  moveToSuperASIBusy?: boolean;
  onMeasureCurrent?: () => void;
};

function rateParts(m: Measurement | undefined) {
  if (!m) return { rate: null as number | null, trueN: null as number | null, avail: null as number | null };
  const d = m.detail || {};
  const trueN = typeof d.count_true === "number" ? d.count_true : null;
  const avail = typeof d.count_available === "number" ? d.count_available : null;
  const rate =
    typeof m.value === "number" && Number.isFinite(m.value)
      ? m.value
      : trueN != null && avail != null && avail > 0
        ? trueN / avail
        : null;
  return { rate, trueN, avail };
}

function phenomenonTitle(spec: Spec): string {
  const identity = asObj(spec.identity);
  const name = typeof identity.name === "string" ? identity.name.trim() : "";
  if (name) return name.replace(/_/g, " ");
  const pop = asObj(spec.population_binding);
  const leagues = Array.isArray(pop.leagues) ? pop.leagues.join(" · ") : "";
  const slices = Array.isArray(pop.default_structural_slices)
    ? pop.default_structural_slices.join(" · ")
    : "";
  const anchor = asObj(spec.anchor);
  const parts = [leagues, slices].filter(Boolean);
  if (anchor.event === "FIRST_PRICE_TOUCH" && typeof anchor.price_e4 === "number") {
    parts.push(`first touch at ${Math.round(anchor.price_e4 / 100)}¢`);
  }
  return parts.join(" · ") || "Research result";
}

export default function ResultsAnswer({
  result,
  spec,
  isStale,
  viewingSaved,
  savedAt,
  onOpenDetail,
  onOpenEvidence,
  onReturnToDefine,
  onSaveResults,
  onDownload,
  onPrint,
  onNewResearch,
  onMoveToSuperASI,
  moveToSuperASIBusy,
  onMeasureCurrent,
}: Props) {
  const [structureOpen, setStructureOpen] = useState(true);

  if (isStale && !viewingSaved) {
    return (
      <div className="ws-answer empty">
        <h1 className="v2-page-title">Not this Quick Start</h1>
        <p className="v2-lede">
          The numbers on file are from a previous question. Confirm & Run measures the league,
          market, dates, and conditions you entered — not a leftover result.
        </p>
        <button
          type="button"
          className="btn-primary"
          onClick={onMeasureCurrent ?? onReturnToDefine}
        >
          Confirm & Run this question
        </button>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="ws-answer empty">
        <h1 className="v2-page-title">No measurement yet</h1>
        <p className="v2-lede">
          This Quick Start has not been measured. Confirm & Run executes the chips on screen —
          not a leftover trade and not a blank N.
        </p>
        <button
          type="button"
          className="btn-primary"
          onClick={onMeasureCurrent ?? onReturnToDefine}
        >
          Confirm & Run this question
        </button>
      </div>
    );
  }

  const pathP = pathRate(result);
  const termP = terminalRate(result);
  const winM = findMeasurement(result, ["win_exit_rate"]);
  const lossM = findMeasurement(result, ["loss_exit_rate"]);
  const taggedExits = Boolean(winM || lossM);
  const t40 = result.measurements?.find((m) => m.name === pathP.name);
  const yes = result.measurements?.find((m) => m.name === termP.name);
  const t40p = pathP;
  const yesp = termP;
  const n = result.summary?.population_n ?? result.population?.count ?? null;
  const termYes = result.identity?.terminal_yes;
  const termNo = result.identity?.terminal_no;
  const termMissing = result.identity?.terminal_missing;
  const contract = readResultsContract(result);
  const lastPrint = contract.lastTrade;
  const lt = contract.rates;
  const missingPhrase = terminalMissingPhrase(result.provenance);
  const mlbLastTrade = isMlbLastTradeResult(result);
  const mlbGoldenDiffs = mlbLastTrade ? goldenDiffsFromResult(result) : [];
  const teScope = result.identity?.te_scope;
  const entryN = teScope?.n_entry ?? result.identity?.n_entry_events ?? result.identity?.entry_eligible ?? n;
  const leagueBits = Object.entries(result.identity?.league_counts ?? {})
    .map(([k, v]) => `${k} ${v}`)
    .join(" · ");
  const exposure = contract.exposure;
  const nLabel =
    teScope?.requested && entryN != null && n != null && entryN !== n
      ? `N = ${n} TE-scoped · ${entryN} entry events`
      : n != null
        ? `N = ${n}`
        : "N = —";
  const exposureLabel =
    exposure.status === "CARDINALITY_VIOLATION"
      ? `CARDINALITY_VIOLATION · EXPOSURE_UNIT=${exposure.declaredUnit} failed · N unchanged · strategy statistics withheld`
      : exposure.status === "UNVERIFIED"
        ? `exposure UNVERIFIED · EXPOSURE_UNIT=${exposure.declaredUnit} · do not assume N is unique games`
        : exposure.status === "OBSERVED" && exposure.declaredUnit === "GAME" && exposure.maxEntriesPerUnit === 1
          ? "EXPOSURE_UNIT=GAME · MAX_ENTRIES_PER_GAME=1 · N = unique internal_game_id"
          : `EXPOSURE_UNIT=${exposure.declaredUnit}`;
  const rawPartition = result.empirical_partition ?? null;
  const partition = enrichPartition(rawPartition, pathP.trueN, pathP.avail);
  const path = String(result.provenance?.path ?? result.provenance?.execution_path ?? "");
  const generic = path === "generic_query";
  const title = lastPrint
    ? String(result.summary?.population_description || "Last-trade print query")
    : generic
      ? String(result.summary?.population_description || "Generic candle query")
      : phenomenonTitle(spec);
  const popDesc =
    result.summary?.population_description ||
    (Array.isArray(asObj(spec.population_binding).leagues)
      ? String((asObj(spec.population_binding).leagues as string[]).join(" · "))
      : "Population");
  const funnel = result.population?.funnel ?? [];
  const status = String(result.execution_status || "");
  const unmeasured = status && status !== "COMPLETE" && status !== "PARTIAL";
  const exclusionLedger = Object.entries({
    ...(result.identity?.exclusions ?? {}),
    ...(result.mlb?.exclusions ?? {}),
  }).filter(([, v]) => typeof v === "number" && v > 0);
  const sameN = sameNRates(lt);
  const entryCents = entryCentsFromResult(result);
  const tradeBe = binaryBreakeven(entryCents, sameN?.pWin ?? null);
  const onePerGame =
    exposure.status === "OBSERVED" &&
    exposure.declaredUnit === "GAME" &&
    exposure.maxEntriesPerUnit === 1;

  const parentLabel = title;
  const containmentFor = (currentLabel: string, currentN: number | null) => ({
    parentLabel,
    parentN: n,
    currentLabel,
    currentN,
  });

  const inspectMeasurement = (m: Measurement | undefined, label: string, meaning: string) => {
    if (!m) return;
    const p = rateParts(m);
    onOpenDetail({
      title: label,
      value: p.rate != null ? `${(p.rate * 100).toFixed(2)}%` : "—",
      subtitle:
        p.trueN != null && p.avail != null ? `${p.trueN} / ${p.avail}` : undefined,
      containment: containmentFor(label, p.avail),
      sections: [
        { heading: "Definition", body: <p>{meaning}</p> },
        { heading: "Calculation", body: <p>Rate = count_true / count_available on the lock.</p> },
        {
          heading: "Conditional denominator",
          body: (
            <p className="evidence">
              {p.trueN ?? "—"} true / {p.avail ?? "—"} available of parent N = {n ?? "—"}
            </p>
          ),
        },
        {
          heading: "Evidence",
          body: <p className="evidence">{m.source?.artifact || "—"}</p>,
        },
        {
          heading: "IDs",
          body: (
            <p className="evidence">
              {m.definition_version || "—"} · field {m.source?.field || "—"}
            </p>
          ),
        },
        {
          heading: "Provenance",
          body: <p className="evidence">{m.source?.artifact || "local measurement"}</p>,
        },
      ],
    });
  };

  const inspectCell = (cell: PartitionCell) => {
    const N = partition?.n_population ?? n ?? 0;
    onOpenDetail({
      title: cellTitle(cell),
      value: String(cell.n),
      subtitle: N ? `${fmtPct(cell.n, N)} of population N = ${N}` : undefined,
      containment: containmentFor(cellTitle(cell), cell.n),
      sections: [
        {
          heading: "What this means",
          body: (
            <p>
              Observations in this finite partition cell. Counts come from the
              authoritative full-population joint — not from truncated row previews.
              PARTITION MEMBERSHIP ≠ CAUSAL TRANSITION.
            </p>
          ),
        },
        {
          heading: "Population proportion",
          body: (
            <p className="evidence">
              P(cell) = {cell.n} / {N} = {N ? fmtPct(cell.n, N) : "—"}
            </p>
          ),
        },
      ],
    });
  };

  const hasMarginals = t40 != null || yes != null || taggedExits;
  const caseA = partition?.status === "COMPLETE";
  const caseC = !caseA && !hasMarginals && (result.measurements?.length ?? 0) > 0;

  return (
    <div className="ws-answer">
      <div className="ws-answer-toolbar">
        <div className="ws-answer-toolbar-meta">
          {viewingSaved ? (
            <span className="v2-badge">Saved result snapshot · local{savedAt ? ` · ${savedAt}` : ""}</span>
          ) : isStale ? (
            <span className="v2-badge warn">Prior result · study changed</span>
          ) : (
            <span className="v2-badge ok">{result.execution_status || "COMPLETE"}</span>
          )}
        </div>
        <div className="ws-answer-toolbar-actions">
          <button type="button" className="v2-text-link" onClick={onDownload}>
            Download
          </button>
          {onPrint ? (
            <button type="button" className="v2-text-link" onClick={onPrint}>
              Print
            </button>
          ) : null}
          <button type="button" className="v2-text-link" onClick={onNewResearch}>
            New research
          </button>
          {!viewingSaved ? (
            <button type="button" className="btn-primary ws-step-primary" onClick={onSaveResults}>
              Save results
            </button>
          ) : null}
          {onMoveToSuperASI && canMoveToSuperASI(result) ? (
            <button
              type="button"
              className="btn-secondary"
              onClick={onMoveToSuperASI}
              disabled={moveToSuperASIBusy}
            >
              {moveToSuperASIBusy ? "Importing…" : "Move to SuperASI"}
            </button>
          ) : null}
        </div>
      </div>

      <header className="ws-answer-hero">
        <p className="v2-kicker">Level 1 · What happened?</p>
        <h1 className="v2-page-title">{title}</h1>
        {unmeasured ? (
          <p className="ws-review-attention">
            {status.replace(/_/g, " ")} — not a silent empty FIRST_TOUCH population.
            {result.caveats?.length ? ` ${result.caveats[result.caveats.length - 1]}` : ""}
          </p>
        ) : null}
        <p className="muted small ws-trade-pop">
          {popDesc}
          {leagueBits ? ` · ${leagueBits}` : ""}
          {onePerGame ? " · one earliest trade per game" : ""}
        </p>
        {exposure.status === "CARDINALITY_VIOLATION" ? (
          <p className="ws-review-attention">
            N still includes more than one entry in some games. Confirm &amp; Run again — this
            terminal now keeps the earliest trade per game. Strategy statistics stay withheld
            until that run.
          </p>
        ) : null}

        <div className="ws-trade-board" aria-label="Backtest trade">
          <button
            type="button"
            className="mm-metric is-actionable"
            onClick={() =>
              onOpenDetail({
                title: "N",
                value: sameN ? String(sameN.n) : nLabel,
                subtitle: onePerGame
                  ? "One earliest trade per game after Confirm & Run"
                  : "Measured population after requested PIT chips",
                containment: containmentFor(popDesc, n),
                sections: [
                  {
                    heading: "What N is",
                    body: (
                      <p>
                        N is the measured population. Wins and losses below use this same
                        denominator. Changing reach/hold/exit classifies the same entries — it
                        does not rewrite N.
                      </p>
                    ),
                  },
                ],
              })
            }
          >
            <span className="mm-metric-label">N</span>
            <span className="mm-metric-value">{sameN ? sameN.n : n ?? "—"}</span>
            <span className="mm-metric-note">
              {onePerGame ? "one trade / game" : exposureLabel}
            </span>
          </button>
          <button
            type="button"
            className="mm-metric is-actionable"
            onClick={() =>
              inspectMeasurement(
                findMeasurement(result, ["win_on_n"]) ?? t40,
                "Backtest P(win)",
                "WIN_EXIT / N when tagged exits exist, otherwise path_true / N. Same N as losses. Not WIN/(WIN+LOSS). Not Kalshi settlement.",
              )
            }
          >
            <span className="mm-metric-label">Backtest P(win)</span>
            <span className="mm-metric-value">{fmtTradePct(sameN?.pWin)}</span>
            <span className="mm-metric-note">
              {sameN ? `${sameN.wins} / ${sameN.n}` : "—"}
            </span>
          </button>
          <button
            type="button"
            className="mm-metric is-actionable"
            onClick={() =>
              onOpenDetail({
                title: "Breakeven before fees",
                value: tradeBe ? fmtTradePct(tradeBe.breakeven) : "—",
                subtitle:
                  tradeBe != null
                    ? `${tradeBe.entryCents}¢ entry · binary 100/0`
                    : "Need an entry chip",
                sections: [
                  {
                    heading: "Definition",
                    body: (
                      <p>
                        For a 100/0 contract, breakeven before fees is the entry price:
                        {entryCents != null ? ` ${entryCents}¢ → ${entryCents}%.` : " —"}{" "}
                        Hypothetical ¢/contract = 100 × P(win) − entry. Non-win is treated as 0
                        settlement, not as Kalshi NO. LAST TRADE ≠ FILL. Fees are not subtracted.
                      </p>
                    ),
                  },
                ],
              })
            }
          >
            <span className="mm-metric-label">Breakeven before fees</span>
            <span className="mm-metric-value">{tradeBe ? fmtTradePct(tradeBe.breakeven) : "—"}</span>
            <span className="mm-metric-note">
              {tradeBe ? `${tradeBe.entryCents}¢ entry · binary 100/0` : "no entry chip"}
            </span>
          </button>
          <button
            type="button"
            className="mm-metric is-actionable"
            onClick={() =>
              onOpenDetail({
                title: "Vs breakeven",
                value: tradeBe ? `${fmtPp(tradeBe.margin)} · ${fmtSignedCents(tradeBe.evCents)}` : "—",
                subtitle: "Hypothetical before fees · not a fill",
                sections: [
                  {
                    heading: "Definition",
                    body: (
                      <p>
                        Margin = P(win) − entry/100. ¢/contract = 100 × P(win) − entry. This is
                        not observed path EV and not executable P&amp;L.
                      </p>
                    ),
                  },
                ],
              })
            }
          >
            <span className="mm-metric-label">Vs breakeven</span>
            <span className="mm-metric-value">{tradeBe ? fmtPp(tradeBe.margin) : "—"}</span>
            <span className="mm-metric-note">
              {tradeBe
                ? `${fmtSignedCents(tradeBe.evCents)} / contract before fees`
                : "need P(win) and entry"}
            </span>
          </button>
        </div>
        {sameN ? (
          <p className="ws-trade-split">
            Wins {sameN.wins} / {sameN.n} · Losses {sameN.losses} / {sameN.n} · Other {sameN.other} /{" "}
            {sameN.n}
            {sameN.other > 0 ? " (ties / unclassified — not LOSS)" : ""}
          </p>
        ) : null}
        <p className="muted small">
          {lastPrint
            ? "Last-trade print observed. LAST TRADE ≠ YES BID. LAST TRADE ≠ FILL. Measurement ≠ edge."
            : "Candle path ≠ fill. Measurement ≠ edge."}
          {lt.settled != null && lt.n != null && (lt.terminalMissing ?? 0) > 0
            ? ` Settlement coverage ${lt.settled} / ${lt.n} · missing ${lt.terminalMissing} remains missing.`
            : ""}
        </p>
        {mlbLastTrade && mlbGoldenDiffs.length ? (
          <p className="muted small">
            Not the golden MLB last-trade object (N = {GOLDEN_MLB.n}, FT{GOLDEN_MLB.entryCents},{" "}
            {GOLDEN_MLB.dateFrom} → {GOLDEN_MLB.dateTo}). This run measured the chips on screen.
          </p>
        ) : mlbLastTrade && hashesMatchGolden(result) ? (
          <p className="muted small">
            Golden MLB last-trade chips · N = {n ?? GOLDEN_MLB.n}.
          </p>
        ) : null}
      </header>

      {funnel.length || exclusionLedger.length ? (
        <details className="ws-answer-more">
          <summary>Population funnel and exclusions</summary>
          {funnel.length ? (
            <section className="ws-funnel" aria-label="Population funnel">
              <p className="v2-kicker">Population funnel</p>
              <ol>
                {funnel.map((step, i) => (
                  <li key={`${step.condition_id ?? step.id ?? step.label ?? i}`}>
                    {step.label ?? step.condition_id ?? "layer"} · n = {step.qualifying ?? step.n ?? "—"}
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
          {exclusionLedger.length ? (
            <section className="ws-funnel" aria-label="Exclusion ledger">
              <p className="v2-kicker">Exclusion ledger</p>
              <ol>
                {exclusionLedger.map(([reason, count]) => (
                  <li key={reason}>
                    {reason} · n = {count}
                  </li>
                ))}
              </ol>
              <p className="muted small">
                Missing or unusable observation is counted here. It is not a silent N = 0.
              </p>
            </section>
          ) : null}
        </details>
      ) : null}

      {hasMarginals ? (
        <section className="ws-breakdown" aria-label="Empirical breakdown">
          {sameN ? (
            <>
              <button
                type="button"
                className="ws-breakdown-card"
                onClick={() =>
                  inspectMeasurement(
                    findMeasurement(result, ["win_on_n"]) ?? t40,
                    "WIN / N",
                    "WIN_EXIT / N. Same denominator as LOSS / N. Not WIN/(WIN+LOSS).",
                  )
                }
              >
                <div className="v2-kicker">WIN / N</div>
                <div className="ws-breakdown-value evidence">{fmtTradePct(sameN.pWin)}</div>
                <div className="muted">same N</div>
                <div className="evidence small">
                  {sameN.wins} / {sameN.n}
                </div>
              </button>
              <button
                type="button"
                className="ws-breakdown-card"
                onClick={() =>
                  inspectMeasurement(
                    findMeasurement(result, ["loss_on_n"]) ?? lossM,
                    "LOSS / N",
                    "LOSS_EXIT / N. Same denominator as WIN / N. PATH FALSE is not LOSS.",
                  )
                }
              >
                <div className="v2-kicker">LOSS / N</div>
                <div className="ws-breakdown-value evidence">{fmtTradePct(sameN.pLoss)}</div>
                <div className="muted">same N</div>
                <div className="evidence small">
                  {sameN.losses} / {sameN.n}
                </div>
              </button>
              {sameN.other > 0 ? (
                <button
                  type="button"
                  className="ws-breakdown-card"
                  onClick={() =>
                    inspectMeasurement(
                      t40,
                      "OTHER / N",
                      "N − WIN − LOSS. Ties and unclassified rows. Not LOSS_EXIT. PATH FALSE is not LOSS.",
                    )
                  }
                >
                  <div className="v2-kicker">OTHER / N</div>
                  <div className="ws-breakdown-value evidence">{fmtTradePct(sameN.pOther)}</div>
                  <div className="muted">not LOSS</div>
                  <div className="evidence small">
                    {sameN.other} / {sameN.n}
                  </div>
                </button>
              ) : null}
            </>
          ) : lt.pathTrue != null && lt.n != null ? (
            <button
              type="button"
              className="ws-breakdown-card"
              onClick={() =>
                inspectMeasurement(
                  t40,
                  generic ? "Path proportion" : "Path proportion · T40",
                  generic
                    ? "Proportion of the authoritative population whose observed path condition is true. Candle path ≠ fill. MEASUREMENT ≠ EDGE."
                    : "Proportion of the authoritative population whose observed path reaches 40¢ under the measurement definition. Candle path ≠ fill. MEASUREMENT ≠ EDGE.",
                )
              }
            >
              <div className="v2-kicker">Path</div>
              <div className="ws-breakdown-value evidence">
                {t40p.rate != null ? `${(t40p.rate * 100).toFixed(1)}%` : "—"}
              </div>
              <div className="muted">{generic ? "Path condition true" : "Reached 40¢"}</div>
              {t40p.trueN != null && t40p.avail != null ? (
                <div className="evidence small">
                  {t40p.trueN} / {t40p.avail}
                </div>
              ) : null}
            </button>
          ) : null}
          <button
            type="button"
            className="ws-breakdown-card"
            onClick={() =>
              inspectMeasurement(
                yes,
                "TERMINAL YES",
                "YES / settled only. Conditional on observed Kalshi settlement. Missing is not NO. Not terminal efficiency. Not YES / N.",
              )
            }
          >
            <div className="v2-kicker">TERMINAL YES</div>
            <div className="ws-breakdown-value evidence">
              {lt.terminalYes != null && lt.settled
                ? `${((lt.terminalYes / lt.settled) * 100).toFixed(1)}%`
                : yesp.rate != null
                  ? `${(yesp.rate * 100).toFixed(1)}%`
                  : "—"}
            </div>
            <div className="muted">of observed Kalshi settlements</div>
            {lt.terminalYes != null && lt.settled != null && lt.n != null ? (
              <div className="evidence small">
                {lt.terminalYes} / {lt.settled} · coverage {coveragePct(lt.settled, lt.n)}
              </div>
            ) : termYes != null && termNo != null && termMissing != null && n != null ? (
              <div className="evidence small">
                YES {termYes} · NO {termNo} · miss {termMissing} / {n}
              </div>
            ) : yesp.trueN != null && yesp.avail != null ? (
              <div className="evidence small">
                {yesp.trueN} / {yesp.avail}
              </div>
            ) : (
              <div className="muted small">terminal path stays on this page</div>
            )}
          </button>
        </section>
      ) : null}

      {!caseA && !pathP.avail ? (
        <p className="ws-partition-note">JOINT PARTITION NOT CURRENTLY MEASURED</p>
      ) : null}

      {caseC ? (
        <section className="ws-generic-measures">
          <h2>Measurements</h2>
          {(result.measurements || []).map((m) => (
            <button
              key={m.name}
              type="button"
              className="ws-breakdown-card"
              onClick={() =>
                inspectMeasurement(m, m.name || "Measurement", m.caveat || "Authoritative measurement.")
              }
            >
              <div className="v2-kicker">{m.name}</div>
              <div className="ws-breakdown-value evidence">
                {typeof m.value === "number" ? m.value.toFixed(4) : m.status || "—"}
              </div>
            </button>
          ))}
        </section>
      ) : null}

      {partition && (caseA || pathP.avail) ? (
        <>
          <EmpiricalStateSpace
            partition={partition}
            onInspectCell={inspectCell}
            missingLabel={missingPhrase}
          />
          <details open={structureOpen} onToggle={(e) => setStructureOpen((e.target as HTMLDetailsElement).open)}>
            <summary className="ws-structure-summary">Path / terminal decomposition</summary>
            <EmpiricalTree
              partition={partition}
              onInspectCell={inspectCell}
              missingLabel={missingPhrase}
            />
          </details>
        </>
      ) : null}

      <PitEntryState
        trades={(result.population?.trades ?? result.population?.rows ?? []) as Array<Record<string, unknown> & { te?: Record<string, unknown> }>}
        basis={result.observation_basis}
        mlb={result.mlb}
      />

      <TerminalEfficiencyPanel
        summary={result.base_terminal_efficiency}
        trades={(result.population?.trades ?? result.population?.rows ?? []) as Array<Record<string, unknown> & { te?: Record<string, unknown> }>}
        onOpenDetail={onOpenDetail}
        rates={lt}
      />

      <div className="ws-answer-footer">
        <button type="button" className="v2-text-link" onClick={onOpenEvidence}>
          Evidence & provenance →
        </button>
        <span className="muted small">
          Click any measurement or partition cell to inspect.
        </span>
      </div>
    </div>
  );
}

function PitEntryState({
  trades,
  basis,
  mlb,
}: {
  trades: Array<Record<string, unknown> & { te?: Record<string, unknown> }>;
  basis?: string | null;
  mlb?: AnswerResult["mlb"];
}) {
  const peek = trades.filter((t) => t.te).slice(0, 6);
  if (!peek.length && !mlb) return null;
  const lastTrade = String(basis || mlb?.observation_basis || "").includes("LAST_TRADE");
  return (
    <section className="ws-te-results" aria-label="PIT entry state">
      <p className="v2-kicker">PIT ENTRY STATE</p>
      <h2>Game state at the entry bar</h2>
      <p className="muted small">
        Separate from MARKET PATH and TERMINAL SETTLEMENT.{" "}
        {lastTrade ? "LAST TRADE ≠ YES BID. " : ""}
        CANDLE/PRINT PATH ≠ FILL. PBP_ts ≤ entry_ts or excluded.
      </p>
      {mlb?.funnel ? (
        <p className="muted small">
          Funnel: {Object.entries(mlb.funnel).map(([k, v]) => `${k} ${v}`).join(" · ")}
        </p>
      ) : null}
      <div className="ws-te-stat-grid">
        {peek.map((row, i) => {
          const te = row.te ?? {};
          return (
            <div key={String(row.ticker ?? i)} className="ws-breakdown-card">
              <div className="v2-kicker">{String(row.ticker ?? "")}</div>
              <p className="muted small">
                {te.inning != null ? `I${String(te.inning)}` : String(te.period ?? "—")} {String(te.half ?? "")} ·{" "}
                {te.yes_batting === true ? "YES batting" : te.yes_batting === false ? "YES pitching" : "—"} ·{" "}
                score {String(te.team_points ?? "—")}–{String(te.opponent_points ?? "—")} · Δ{" "}
                {String(te.point_differential ?? te.run_differential ?? "—")}
                {te.point_differential_unit === "runs" ? " runs" : ""} · {String(te.outs ?? "—")} outs ·{" "}
                {String(te.count_display ?? "—")} · {String(te.runners ?? "—")}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function canMoveToSuperASI(result: AnswerResult): boolean {
  const status = result.execution_status;
  const count = result.population?.count ?? result.summary?.population_n ?? 0;
  return (status === "COMPLETE" || status === "PARTIAL") && count > 0;
}

function enrichPartition(
  part: EmpiricalPartition | null,
  pathTrue: number | null,
  pathAvail: number | null,
): EmpiricalPartition | null {
  if (!part && pathTrue != null && pathAvail != null && pathAvail > 0) {
    return {
      status: "COMPLETE",
      n_population: pathAvail,
      n_joint_available: 0,
      n_missing: pathAvail,
      joint_measured: false,
      path_margin: { true: pathTrue, false: pathAvail - pathTrue, available: pathAvail },
      cells: [],
    };
  }
  if (!part) return null;
  if (part.path_margin?.available) return part;
  if (pathTrue == null || pathAvail == null || pathAvail <= 0) return part;
  return {
    ...part,
    path_margin: {
      true: pathTrue,
      false: pathAvail - pathTrue,
      available: pathAvail,
    },
    joint_measured: part.joint_measured ?? (part.n_joint_available ?? 0) > 0,
  };
}
