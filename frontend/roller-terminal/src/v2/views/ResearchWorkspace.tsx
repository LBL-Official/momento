import type { ReactNode } from "react";
import ObjectHero from "../components/ObjectHero";
import MetricValue from "../components/MetricValue";
import type { DetailPayload } from "../components/DetailDrawer";
import type { ResearchMode } from "../navigation";
import { summarizeResearchSpec } from "../../researchSummary";
import type { Spec } from "../../researchTypes";
import type { Freshness, ResultSnapshot, ValidationSnapshot } from "../../researchFreshness";
import type { ResearchResult } from "../../ResultsView";

type Measurement = NonNullable<ResearchResult["measurements"]>[number];

type Props = {
  mode: ResearchMode;
  onMode: (mode: ResearchMode) => void;
  spec: Spec;
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  validationSnapshot: ValidationSnapshot | null;
  resultSnapshot: ResultSnapshot | null;
  canRun: boolean;
  onSaveToLibrary: () => void;
  onOpenDetail: (detail: DetailPayload) => void;
  defineSlot: ReactNode;
  resultsSlot: ReactNode;
  evidenceSlot: ReactNode;
};

function fmtPct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

function findMeasurement(result: ResearchResult | null | undefined, name: string): Measurement | undefined {
  return result?.measurements?.find((m) => m.name === name);
}

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

export default function ResearchWorkspace({
  mode,
  onMode,
  spec,
  validationFreshness,
  executionFreshness,
  validationSnapshot,
  resultSnapshot,
  canRun,
  onSaveToLibrary,
  onOpenDetail,
  defineSlot,
  resultsSlot,
  evidenceSlot,
}: Props) {
  const summary = summarizeResearchSpec(spec);
  const identity = (spec.identity as { name?: string; description?: string } | undefined) ?? {};
  const title = identity.name?.trim() || "Untitled research object";
  const result = resultSnapshot?.payload as ResearchResult | undefined;
  const n =
    result?.summary?.population_n ??
    result?.population?.count ??
    null;
  const t40 = findMeasurement(result, "t40_rate");
  const yes = findMeasurement(result, "kalshi_yes_rate");
  const t40p = rateParts(t40);
  const yesp = rateParts(yes);

  const phenomenonLine = (() => {
    if (identity.description?.trim()) return identity.description.trim();
    if (summary.anchor?.includes("FIRST_PRICE_TOUCH") && summary.slices.includes("Q3")) {
      return "First price touch at 80¢ during Q3.";
    }
    if (summary.anchor) return summary.anchor;
    return "No phenomenon description yet — define the research object.";
  })();

  const modes: { id: ResearchMode; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "define", label: "Define" },
    { id: "results", label: "Results" },
    { id: "evidence", label: "Evidence" },
  ];

  return (
    <div className="v2-research">
      <ObjectHero
        title={title.replace(/_/g, " ")}
        subtitle={[summary.leagues.join(" · ") || "—", summary.universe || "BBALL1"]
          .filter(Boolean)
          .join(" · ")}
        meta={[
          n != null ? `${n} observations` : "No population result",
          summary.slices.length ? summary.slices.join(" · ") : "No structural slices",
        ]}
        badges={[
          {
            label: validationFreshness === "CURRENT" ? "Validated" : validationFreshness,
            tone: validationFreshness === "CURRENT" ? "ok" : "warn",
          },
          {
            label: canRun
              ? "Runnable"
              : validationSnapshot?.payload.status || "Not runnable",
            tone: canRun ? "ok" : "neutral",
          },
          {
            label:
              executionFreshness === "CURRENT"
                ? "Result current"
                : executionFreshness === "STALE"
                  ? "Result stale"
                  : "No result",
            tone: executionFreshness === "CURRENT" ? "ok" : "neutral",
          },
        ]}
        actions={
          <button type="button" className="btn-secondary" onClick={onSaveToLibrary}>
            Save to library
          </button>
        }
      />

      <nav className="v2-mode-nav" aria-label="Research modes">
        {modes.map((m) => (
          <button
            key={m.id}
            type="button"
            className={mode === m.id ? "v2-mode on" : "v2-mode"}
            onClick={() => onMode(m.id)}
          >
            {m.label}
          </button>
        ))}
      </nav>

      {mode === "overview" ? (
        <div className="v2-overview">
          <section className="v2-overview-block">
            <h2>The phenomenon</h2>
            <p className="v2-overview-prose">{phenomenonLine}</p>
          </section>

          <section className="v2-overview-block">
            <button
              type="button"
              className="v2-overview-hit"
              onClick={() =>
                onOpenDetail({
                  title: "Population",
                  subtitle: summary.universe || "BBALL1",
                  value: n != null ? `n = ${n}` : "Not measured",
                  sections: [
                    {
                      heading: "Binding",
                      body: (
                        <pre className="spec-json">
                          {JSON.stringify(spec.population_binding ?? {}, null, 2)}
                        </pre>
                      ),
                    },
                    {
                      heading: "Definition versions",
                      body: (
                        <pre className="spec-json">
                          {JSON.stringify(spec.definition_versions ?? {}, null, 2)}
                        </pre>
                      ),
                    },
                    {
                      heading: "Note",
                      body: (
                        <p>
                          Population membership is authoritative. UI filters do not invent rows.
                        </p>
                      ),
                    },
                  ],
                })
              }
            >
              <h2>Population</h2>
              <p className="evidence">
                {(spec.definition_versions as Record<string, string> | undefined)?.FIRST80 ||
                  "Population binding"}
              </p>
              <p>
                {summary.leagues.join(" · ") || "—"}
                {summary.slices.length ? ` · ${summary.slices.join(" · ")}` : ""}
              </p>
              <p className="v2-overview-n evidence">{n != null ? `n = ${n}` : "n = —"}</p>
            </button>
          </section>

          <section className="v2-overview-block">
            <h2>Measurements</h2>
            <div className="v2-metric-row">
              <MetricValue
                label="T40 rate"
                value={fmtPct(t40p.rate)}
                sub={
                  t40p.trueN != null && t40p.avail != null
                    ? `${t40p.trueN} / ${t40p.avail}`
                    : "Click for detail"
                }
                onClick={() =>
                  onOpenDetail({
                    title: "T40 rate",
                    value: fmtPct(t40p.rate),
                    subtitle:
                      t40p.trueN != null && t40p.avail != null
                        ? `${t40p.trueN} / ${t40p.avail}`
                        : undefined,
                    sections: [
                      {
                        heading: "What does this measure?",
                        body: (
                          <p>
                            The proportion of the authoritative population for which the artifact
                            field T40 is true. MEASUREMENT ≠ EDGE. Survive ≠ terminal yes.
                          </p>
                        ),
                      },
                      {
                        heading: "Formula",
                        body: (
                          <pre className="evidence">{`count(T40 = true)\n──────────────────\npopulation n`}</pre>
                        ),
                      },
                      {
                        heading: "Binding",
                        body: (
                          <p className="evidence">
                            {t40?.definition_version || "—"} · field{" "}
                            {t40?.source?.field || "T40"}
                          </p>
                        ),
                      },
                      {
                        heading: "Evidence",
                        body: (
                          <p className="evidence">{t40?.source?.artifact || "No source yet"}</p>
                        ),
                      },
                    ],
                  })
                }
              />
              <MetricValue
                label="Terminal YES rate"
                value={fmtPct(yesp.rate)}
                sub={
                  yesp.trueN != null && yesp.avail != null
                    ? `${yesp.trueN} / ${yesp.avail}`
                    : "Click for detail"
                }
                onClick={() =>
                  onOpenDetail({
                    title: "Terminal YES rate",
                    value: fmtPct(yesp.rate),
                    subtitle:
                      yesp.trueN != null && yesp.avail != null
                        ? `${yesp.trueN} / ${yesp.avail}`
                        : undefined,
                    sections: [
                      {
                        heading: "What does this measure?",
                        body: (
                          <p>
                            Terminal YES proportion (Kalshi settlement). Not box-score win.
                            MEASUREMENT ≠ EDGE.
                          </p>
                        ),
                      },
                      {
                        heading: "Formula",
                        body: (
                          <pre className="evidence">{`count(W = true)\n──────────────────\npopulation n`}</pre>
                        ),
                      },
                      {
                        heading: "Binding",
                        body: (
                          <p className="evidence">
                            {yes?.definition_version || "—"} · field {yes?.source?.field || "W"}
                          </p>
                        ),
                      },
                      {
                        heading: "Evidence",
                        body: (
                          <p className="evidence">{yes?.source?.artifact || "No source yet"}</p>
                        ),
                      },
                    ],
                  })
                }
              />
            </div>
            {!result ? (
              <p className="muted">
                No authoritative result yet. Open Define → Validate → Run Research.
              </p>
            ) : null}
          </section>
        </div>
      ) : null}

      {mode === "define" ? <div className="v2-mode-pane">{defineSlot}</div> : null}
      {mode === "results" ? <div className="v2-mode-pane">{resultsSlot}</div> : null}
      {mode === "evidence" ? <div className="v2-mode-pane">{evidenceSlot}</div> : null}
    </div>
  );
}
