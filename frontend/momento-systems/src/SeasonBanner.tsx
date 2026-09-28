import { useEffect, useState } from "react";

type SeasonView = {
  official_strategy_id?: string;
  live_execution?: boolean;
  labels?: { official?: string; live_execution?: string; validation?: string };
  validation_limitations?: string[];
  historical_research_book?: { role?: string; entry_cents?: number; stop_cents?: number };
};

const FALLBACK: SeasonView = {
  official_strategy_id: "FIRST78_67",
  live_execution: false,
  labels: {
    official: "Official upcoming-season strategy: FIRST78→67",
    live_execution: "Live execution: disabled",
    validation: "Validation: NOT_YET_IDENTIFIABLE",
  },
  validation_limitations: [
    "Launch assessment remains NOT_YET_IDENTIFIABLE. This designation does not approve a launch.",
    "The repaired headline book is LEGACY_FIRST80_CONDITIONED_936. It is not a prospective FIRST78 universe.",
    "October 2025 is previously examined retrospective validation. The repaired close-proxy mean stayed positive. That is not a 5% rejection.",
    "April 2025 is a partial raw ticker subset. The available six-contract mean is at or below zero, and the p-value is not estimable.",
    "Candle path is not a fill. Order type, latency, and partial-fill handling stay unresolved. Fee applicability is unverified.",
  ],
  historical_research_book: { role: "HISTORICAL_REGISTERED_RESEARCH_BASELINE", entry_cents: 80, stop_cents: 40 },
};

export default function SeasonBanner() {
  const [view, setView] = useState<SeasonView>(FALLBACK);
  const [source, setSource] = useState("selector file");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/momento/season-strategy")
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        return (await response.json()) as SeasonView;
      })
      .then((body) => {
        if (cancelled) return;
        if (body.official_strategy_id === "FIRST78_67" && body.live_execution === false && body.labels?.official) {
          setView(body);
          setSource("season selector");
        }
      })
      .catch(() => {
        if (!cancelled) setSource("selector file; running API has not loaded the route");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const labels = view.labels;
  return (
    <section aria-label="Official upcoming-season strategy" style={{ textAlign: "center", margin: "0 24px 12px" }}>
      <p style={{ margin: "0 0 4px" }}>{labels?.official}</p>
      <p style={{ margin: "0 0 4px" }}>{labels?.live_execution}</p>
      <p style={{ margin: "0 0 8px" }}>{labels?.validation}</p>
      <ul style={{ display: "inline-block", textAlign: "left", margin: 0, paddingLeft: 18 }}>
        {(view.validation_limitations || []).map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <p style={{ margin: "8px 0 0" }}>
        Historical registered research baseline remains 80/40. Entry {view.historical_research_book?.entry_cents} / stop{" "}
        {view.historical_research_book?.stop_cents}. {source}.
      </p>
    </section>
  );
}
