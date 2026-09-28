import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../api/base";

type RunRec = {
  status?: string;
  started_at?: string;
  finished_at?: string;
  duration_s?: number;
  errors?: string[];
  warnings?: string[];
  sentinels?: { name: string; ok: boolean }[];
  gaps_found?: number;
};

type Status = {
  ingest?: RunRec | null;
  verify?: RunRec | null;
  declared_seasons?: { sport: string; season: string; root_exists: boolean }[];
  unavailable_sports?: string[];
};

function recLine(rec: RunRec | null | undefined, empty: string) {
  if (!rec) return empty;
  const warn = (rec.warnings || []).join(", ");
  return `${rec.status ?? "?"} ${rec.started_at ?? ""} ${rec.duration_s ?? "?"}s${warn ? ` ${warn}` : ""}`;
}

export default function AutoRollerView() {
  const [status, setStatus] = useState<Status | null>(null);
  const [coverage, setCoverage] = useState<string>("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const res = await apiFetch("/auto-roller/status");
    if (!res.ok) throw new Error(`status ${res.status}`);
    setStatus((await res.json()) as Status);
  }, []);

  useEffect(() => {
    refresh().catch((e: Error) => setError(e.message));
  }, [refresh]);

  async function run(path: string, label: string) {
    setBusy(label);
    setError(null);
    try {
      const res = await apiFetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fast: true }),
      });
      if (!res.ok) throw new Error(`run ${res.status}`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function loadGaps() {
    setBusy("gaps");
    setError(null);
    try {
      const res = await apiFetch("/auto-roller/coverage");
      if (!res.ok) throw new Error(`coverage ${res.status}`);
      setCoverage(JSON.stringify(await res.json(), null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="v2-docs">
      <article className="v2-docs-article research-object">
        <h1 className="v2-page-title">AUTO ROLLER</h1>
        <p className="v2-lede">
          Server-authoritative warehouse ingest and verify. Buttons call the API. They do not ingest in the browser.
          Semantics do not change. A failed sentinel does not rewrite goldens.
        </p>
        {error ? <p className="v2-lede">{error}</p> : null}
        <h2>AUTO ROLLER VERIFY — 00:00 local</h2>
        <p>Last verify: {recLine(status?.verify, "none")}</p>
        <h2>AUTO ROLLER INGEST — 02:00 local</h2>
        <p>Last ingest: {recLine(status?.ingest, "none")}</p>
        <p>Unavailable sports: {(status?.unavailable_sports || []).join(", ") || "—"}</p>
        <div className="v2-actions">
          <button type="button" disabled={!!busy} onClick={() => run("/auto-roller/verify", "verify")}>
            {busy === "verify" ? "RUNNING" : "RUN VERIFY NOW"}
          </button>
          <button type="button" disabled={!!busy} onClick={() => run("/auto-roller/ingest", "ingest")}>
            {busy === "ingest" ? "RUNNING" : "RUN INGEST NOW"}
          </button>
          <button type="button" disabled={!!busy} onClick={() => loadGaps()}>
            {busy === "gaps" ? "LOADING" : "VIEW DATA GAPS"}
          </button>
          <button type="button" disabled={!!busy} onClick={() => refresh()}>
            REFRESH STATUS
          </button>
        </div>
        {coverage ? (
          <pre className="v2-docs-article" style={{ whiteSpace: "pre-wrap" }}>
            {coverage}
          </pre>
        ) : null}
      </article>
    </div>
  );
}
