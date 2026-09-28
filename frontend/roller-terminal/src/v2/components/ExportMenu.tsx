import type { Spec } from "../../researchTypes";
import type { ResearchResult } from "../../ResultsView";

type Props = {
  spec: Spec;
  result: ResearchResult | null | undefined;
};

function download(filename: string, text: string, mime = "application/json") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ExportMenu({ spec, result }: Props) {
  const identity = (spec.identity as { name?: string } | undefined)?.name || "research_object";

  return (
    <div className="v2-export">
      <h3>Export</h3>
      <p className="muted">Only exports data that exists. Distinguishes research object, measurements, provenance, caveats.</p>
      <div className="v2-home-links">
        <button
          type="button"
          className="btn-secondary"
          onClick={() =>
            download(`${identity}_spec.json`, JSON.stringify(spec, null, 2))
          }
        >
          Research Spec JSON
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={!result}
          onClick={() =>
            result &&
            download(`${identity}_results.json`, JSON.stringify(result, null, 2))
          }
        >
          Results JSON
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={!result?.measurements?.length}
          onClick={() => {
            if (!result?.measurements?.length) return;
            const lines = ["name,status,value,definition_version,caveat"];
            for (const m of result.measurements) {
              lines.push(
                [
                  m.name ?? "",
                  m.status ?? "",
                  m.value ?? "",
                  m.definition_version ?? "",
                  (m.caveat ?? "").replace(/,/g, ";"),
                ].join(","),
              );
            }
            download(`${identity}_measurements.csv`, lines.join("\n"), "text/csv");
          }}
        >
          Measurements CSV
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={!result}
          onClick={() => {
            if (!result) return;
            const n = result.summary?.population_n ?? result.population?.count ?? "";
            const lines = [
              "field,value",
              `population_n,${n}`,
              `population_description,${(result.summary?.population_description ?? "").replace(/,/g, ";")}`,
              `execution_status,${result.execution_status ?? ""}`,
              `research_object_id,${result.research_object_id ?? ""}`,
            ];
            download(`${identity}_population_summary.csv`, lines.join("\n"), "text/csv");
          }}
        >
          Population Summary CSV
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={!result}
          onClick={() => {
            if (!result) return;
            const report = {
              RESEARCH_OBJECT: spec,
              POPULATION: result.population,
              MEASUREMENTS: result.measurements,
              PROVENANCE: result.provenance,
              CAVEATS: result.caveats,
              USER_SUPPLIED_SCENARIOS: null,
              note: "USER_SUPPLIED_SCENARIOS not included unless exported separately from Analytics.",
            };
            download(`${identity}_full_report.json`, JSON.stringify(report, null, 2));
          }}
        >
          Full Research Report
        </button>
      </div>
      <p className="muted small">Chart PNG export: use OS screenshot for now (canvas capture deferred).</p>
    </div>
  );
}
