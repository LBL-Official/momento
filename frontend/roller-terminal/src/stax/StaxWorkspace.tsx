import { useCallback, useEffect, useMemo, useState } from "react";
import ResultsAnswer, { type AnswerResult } from "../v2/results/ResultsAnswer";
import type { DetailPayload } from "../v2/components/DetailDrawer";
import { blankSpec } from "../researchTypes";
import type { LibraryEntry } from "../v2/researchLibrary";
import type { ResultSnapshot } from "../researchFreshness";
import {
  compareStax,
  createStax,
  exportStax,
  getStax,
  getStaxVersion,
  listCandidates,
  listStax,
  runStax,
  setAutomation,
  validateStax,
} from "./api";
import { fmtN, leagueLabel, pct, seasonLabel, timeframeLabel } from "./format";
import StaxCreateStrategy from "./StaxCreateStrategy";
import StaxNativeBuilder from "./StaxNativeBuilder";
import StaxPicker from "./StaxPicker";
import StaxSaveModal from "./StaxSaveModal";
import { ledgerLabel, ledgerStatus } from "./nativeDraft";
import type {
  CanonicalUniverse,
  LibraryRow,
  StaxCompare,
  StaxHead,
  StaxMember,
  StaxMemberResult,
  StaxRoute,
  StaxVersion,
} from "./types";

type LocalCandidate = {
  id: string;
  name: string;
  source: "session" | "library" | "save";
  payload: Record<string, unknown>;
  universe?: CanonicalUniverse | null;
  n?: number | null;
  status?: string | null;
};

type Props = {
  route: StaxRoute;
  currentResult: ResultSnapshot | null;
  libraryEntries: LibraryEntry[];
  onOpenDetail: (detail: DetailPayload) => void;
  onNavigate?: (route: StaxRoute) => void;
  onMeta?: (name: string, strategyCount: number) => void;
};

function compareRows(compare: StaxCompare): Array<{ member_id: string; label: string; kind: string; detail: string }> {
  const rows: Array<{ member_id: string; label: string; kind: string; detail: string }> = [];
  for (const row of compare.added || []) {
    rows.push({
      member_id: row.member_id || "—",
      label: row.label || row.member_id || "—",
      kind: "ADDED",
      detail: "Member present in the newer version only",
    });
  }
  for (const row of compare.removed || []) {
    rows.push({
      member_id: row.member_id || "—",
      label: row.label || row.member_id || "—",
      kind: "REMOVED",
      detail: "Member present in the older version only",
    });
  }
  for (const row of compare.changed || []) {
    const parts = [
      row.definition_changed ? "definition changed" : null,
      row.dataset_changed ? "dataset changed" : null,
    ].filter(Boolean);
    rows.push({
      member_id: row.member_id,
      label: row.member_id,
      kind: "CHANGED",
      detail: parts.join(" · ") || "changed",
    });
  }
  for (const row of compare.reordered || []) {
    rows.push({
      member_id: row.member_id,
      label: row.member_id,
      kind: "REORDERED",
      detail: `position ${row.from ?? "—"} → ${row.to ?? "—"}`,
    });
  }
  for (const memberId of compare.unchanged || []) {
    rows.push({
      member_id: memberId,
      label: memberId,
      kind: "UNCHANGED",
      detail: "Same member_id, definition, and dataset fingerprint",
    });
  }
  return rows;
}

function memberLabel(member: StaxMember): string {
  return ledgerLabel(member);
}

export default function StaxWorkspace({
  route,
  currentResult,
  libraryEntries,
  onOpenDetail,
  onNavigate,
  onMeta,
}: Props) {
  const [head, setHead] = useState<StaxHead | null>(null);
  const [members, setMembers] = useState<StaxMember[]>([]);
  const [latest, setLatest] = useState<StaxVersion | null>(null);
  const [versions, setVersions] = useState<Array<{ version: string; kind?: string; created_at?: string; status?: string; strategy_count?: number }>>([]);
  const [libraryRows, setLibraryRows] = useState<LibraryRow[]>([]);
  const [addMode, setAddMode] = useState<"native" | "advanced" | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveDescription, setSaveDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mutating, setMutating] = useState(false);
  const [running, setRunning] = useState(false);
  const [detailMember, setDetailMember] = useState<string | null>(null);
  const [historyVersion, setHistoryVersion] = useState<StaxVersion | null>(null);
  const [compare, setCompare] = useState<StaxCompare | null>(null);
  const [candidates, setCandidates] = useState<LocalCandidate[]>([]);
  const [tz, setTz] = useState("America/Los_Angeles");

  const universe = head?.universe || members[0]?.universe || null;

  useEffect(() => {
    onMeta?.(head?.name || "Multi-strategy stack", members.length);
  }, [head?.name, members.length, onMeta]);

  const reload = useCallback(async (staxId: string) => {
    const got = await getStax(staxId);
    setHead(got.stax);
    setMembers(got.members || []);
    setLatest(got.latest);
    setVersions(got.versions || []);
  }, []);

  const refreshLibrary = useCallback(async () => {
    const listed = await listStax();
    setLibraryRows(listed.stax || []);
  }, []);

  useEffect(() => {
    void refreshLibrary().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [refreshLibrary]);

  const openPicker = async () => {
    setError(null);
    const items: LocalCandidate[] = [];
    if (currentResult?.payload) {
      const payload = currentResult.payload as Record<string, unknown>;
      items.push({
        id: "session",
        name: "Current session result",
        source: "session",
        payload,
        n: Number((payload as { summary?: { population_n?: number } }).summary?.population_n ?? null),
        status: String((payload as { execution_status?: string }).execution_status || ""),
      });
    }
    for (const entry of libraryEntries) {
      items.push({
        id: entry.id,
        name: entry.name,
        source: "library",
        payload: {
          name: entry.name,
          id: entry.server_save_id || entry.id,
          save_id: entry.server_save_id || entry.id,
          draft: entry.workflow_draft,
          workflow_draft: entry.workflow_draft,
          result:
            entry.saved_snapshot?.result_snapshot?.payload || entry.last_result_snapshot?.payload,
          research_spec: entry.research_spec,
        },
        n: entry.last_result?.population_n,
        status: entry.last_result?.execution_status,
      });
    }
    try {
      const remote = await listCandidates();
      for (const c of remote.candidates || []) {
        items.push({
          id: c.save_id,
          name: c.name,
          source: "save",
          payload: { ...c, id: c.save_id, save_id: c.save_id },
          universe: c.universe,
          n: c.population_n,
          status: c.execution_status,
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    setCandidates(items);
    setPickerOpen(true);
  };

  const ensureStax = useCallback(
    async (name: string) => {
      if (head) return head;
      const created = await createStax({
        name: name || saveName || "Untitled STAX",
        description: saveDescription,
        timezone: tz,
        members: [],
      });
      setHead(created.stax);
      setMembers(created.members);
      await refreshLibrary();
      return created.stax;
    },
    [head, refreshLibrary, saveDescription, saveName, tz],
  );

  const persistMembers = async (nextSources: Record<string, unknown>[], name?: string) => {
    setMutating(true);
    setError(null);
    try {
      if (!head) {
        const created = await createStax({
          name: name || saveName || "Untitled STAX",
          description: saveDescription,
          timezone: tz,
          members: nextSources,
        });
        setHead(created.stax);
        setMembers(created.members);
        await refreshLibrary();
        return created;
      }
      const got = await validateStax(head.stax_id, { replace: true, members: nextSources });
      setMembers(got.members);
      await reload(head.stax_id);
      return got;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setMutating(false);
    }
  };

  const onPick = async (item: LocalCandidate) => {
    const existing = members.map((m) => ({
      ...m,
      name: m.label,
    }));
    const result = await persistMembers([...existing, item.payload], item.name);
    if (result) setPickerOpen(false);
  };

  const remove = async (memberId: string) => {
    if (!head) return;
    setMutating(true);
    try {
      const got = await validateStax(head.stax_id, { remove: memberId });
      setMembers(got.members);
      await reload(head.stax_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMutating(false);
    }
  };

  const run = async () => {
    if (!head) {
      setSaveOpen(true);
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const out = await runStax(head.stax_id);
      setLatest(out);
      await reload(head.stax_id);
      await refreshLibrary();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  const save = async () => {
    if (!saveName.trim()) {
      setError("STAX NAME is required");
      return;
    }
    const sources = members.length
      ? members.map((m) => ({ ...m, name: m.label }))
      : [];
    const created = await persistMembers(sources, saveName.trim());
    if (created) {
      setSaveOpen(false);
      if ("stax" in created && created.stax) {
        setHead(created.stax);
      }
    }
  };

  const automate = async (enabled: boolean) => {
    if (!head) return;
    setMutating(true);
    try {
      await setAutomation(head.stax_id, { enabled, timezone: tz, schedule: "00:00" });
      await reload(head.stax_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMutating(false);
    }
  };

  const openVersion = async (version: string) => {
    if (!head) return;
    const rec = await getStaxVersion(head.stax_id, version);
    setHistoryVersion(rec);
    if (versions.length >= 2) {
      const idx = versions.findIndex((v) => v.version === version);
      const parent = rec.parent_version || versions[idx + 1]?.version;
      if (parent) {
        try {
          setCompare(await compareStax(head.stax_id, parent, version));
        } catch {
          setCompare(null);
        }
      }
    }
  };

  const resultsByMember = useMemo(() => {
    const map = new Map<string, StaxMemberResult>();
    for (const row of latest?.results || []) map.set(row.member_id, row);
    return map;
  }, [latest]);

  const detail = detailMember
    ? resultsByMember.get(detailMember) || (historyVersion?.results || []).find((r) => r.member_id === detailMember)
    : null;

  const view = route === "library" ? "library" : route;

  return (
    <div className="stax-workspace">
      {error ? <p className="stax-error">{error}</p> : null}

      {view === "overview" || view === "strategies" ? (
        <section className="ws-hero">
          <p className="ws-kicker">STAX</p>
          <h1 className="ws-title">Multi-strategy research stack</h1>
          <p className="ws-lede">
            Build a stack from independent ROLLER research objects. One common universe. Independent
            measurements.
          </p>
          <div className="stax-product-lang">
            <div>
              <div className="muted small">ROLLER</div>
              <div>ONE RESEARCH OBJECT · ONE QUESTION · ONE MEASUREMENT</div>
            </div>
            <div>
              <div className="muted small">STAX</div>
              <div>MULTIPLE RESEARCH OBJECTS · ONE COMMON UNIVERSE · INDEPENDENT MEASUREMENTS</div>
            </div>
            <div>
              <div className="muted small">SUPERASI</div>
              <div>DOWNSTREAM ANALYSIS</div>
            </div>
          </div>
        </section>
      ) : null}

      {view === "overview" || view === "strategies" ? (
        <section className="stax-universe">
          <p className="ws-kicker">STAX universe</p>
          <div className="stax-metric-row">
            <div>
              <div className="muted small">SPORT</div>
              <div className="evidence">{universe?.sport_family || "—"}</div>
            </div>
            <div>
              <div className="muted small">LEAGUE</div>
              <div className="evidence">{leagueLabel(universe)}</div>
            </div>
            <div>
              <div className="muted small">TIMEFRAME</div>
              <div className="evidence">{timeframeLabel(universe)}</div>
            </div>
            <div>
              <div className="muted small">STRATEGIES</div>
              <div className="evidence">{members.length}</div>
            </div>
          </div>
          <p className="muted small">
            Locked from the first accepted strategy. Sport / league / timeframe must match. Dates are
            not expanded.
          </p>
        </section>
      ) : null}

      {view === "overview" || view === "strategies" ? (
        <section className="stax-strategies">
          <header className="stax-count-head">
            <p className="ws-kicker">{head?.name || "STAX"}</p>
            <h2 className="stax-count">{String(members.length).padStart(2, "0")} STRATEGIES</h2>
            <p className="muted small">
              Independent ROLLER research objects. Each N, path, terminal, and EV stays separate.
              Independence of definitions is not statistical independence.
            </p>
          </header>

          {members.length ? (
            <ol className="stax-ledger">
              {members.map((m, i) => {
                const row = resultsByMember.get(m.member_id);
                return (
                  <li key={m.member_id} className="stax-ledger-row">
                    <span className="stax-ledger-index">{String(i + 1).padStart(2, "0")}</span>
                    <span className="stax-ledger-name">{memberLabel(m)}</span>
                    <span className="stax-ledger-status">{ledgerStatus(m, row?.status)}</span>
                    <span className="stax-row-actions">
                      <button type="button" className="v2-text-link" onClick={() => setDetailMember(m.member_id)}>
                        Open
                      </button>
                      <button type="button" className="v2-text-link" onClick={() => void remove(m.member_id)}>
                        Remove
                      </button>
                    </span>
                  </li>
                );
              })}
            </ol>
          ) : addMode == null ? (
            <p className="stax-empty muted">No strategies yet.</p>
          ) : null}

          {addMode === "native" ? (
            <StaxNativeBuilder
              staxId={head?.stax_id || null}
              staxName={head?.name}
              lockedUniverse={universe}
              ensureStax={ensureStax}
              onCancel={() => setAddMode(null)}
              onAdvanced={() => {
                setError(null);
                setAddMode("advanced");
              }}
              onAdded={(result, next) => {
                if (result.stax) setHead(result.stax);
                if (result.members) setMembers(result.members);
                if (result.stax?.stax_id) void reload(result.stax.stax_id);
                void refreshLibrary();
                if (next === "list") setAddMode(null);
              }}
            />
          ) : null}

          {addMode === "advanced" ? (
            <StaxCreateStrategy
              staxId={head?.stax_id || null}
              staxName={head?.name}
              lockedUniverse={universe}
              ensureStax={ensureStax}
              onCancel={() => setAddMode(null)}
              onAdded={(result, next) => {
                if (result.stax) setHead(result.stax);
                if (result.members) setMembers(result.members);
                if (result.stax?.stax_id) void reload(result.stax.stax_id);
                void refreshLibrary();
                if (next === "list") setAddMode(null);
              }}
            />
          ) : null}

          {addMode == null ? (
            <div className="stax-toolbar stax-toolbar-stack">
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  setError(null);
                  setAddMode("native");
                }}
              >
                + Add strategy
              </button>
              <button type="button" className="btn-secondary" onClick={() => setSaveOpen(true)}>
                Save STAX
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => void run()}
                disabled={running || mutating || !members.length}
              >
                {running ? "Running…" : "Run stack"}
              </button>
              <button
                type="button"
                className="v2-text-link"
                onClick={() => {
                  setAddMode(null);
                  void openPicker();
                }}
              >
                Add existing
              </button>
              <button type="button" className="v2-text-link" onClick={() => onNavigate?.("library")}>
                Stack library
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      {view === "results" ? (
        <section>
          <header className="stax-results-header">
            <div>
              <p className="ws-kicker">{head?.stax_id || "STAX"}</p>
              <h1 className="ws-title">{head?.name || "Unsaved stack"}</h1>
              <p className="muted">
                {members.length} STRATEGIES · {leagueLabel(universe)} · {seasonLabel(universe)}
              </p>
              <p className="evidence">{timeframeLabel(universe)}</p>
            </div>
            <div className="stax-actions">
              <button type="button" className="btn-secondary" onClick={() => setSaveOpen(true)}>
                Save STAX
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => void automate(!(head?.automation_enabled))}
                disabled={!head}
              >
                {head?.automation_enabled ? "Automation on" : "Automate"}
              </button>
            </div>
          </header>

          <div className="stax-infra">
            <div>
              <div className="muted small">AUTOMATION</div>
              <div className="evidence">{head?.automation_enabled ? "● ACTIVE" : "OFF"}</div>
              <div className="muted">
                DAILY · 00:00 · {(head?.timezone || tz).toUpperCase()}
              </div>
              <div className="muted small">LAST RUN {head?.last_run_at || "—"}</div>
              <div className="muted small">NEXT RUN {head?.next_run_at || "—"}</div>
              <div className="stax-caveat">RESEARCH AUTOMATION · NOT EXECUTION</div>
            </div>
            <div>
              <div className="muted small">LATEST VERSION</div>
              <div className="evidence">v{latest?.version || "—"} {latest?.kind || ""}</div>
              <div>
                {latest ? `${latest.completed_count ?? 0} / ${latest.strategy_count ?? 0} COMPLETE` : "Not executed"}
              </div>
              <div className="muted small">DATASET {latest?.dataset_fingerprint?.slice(0, 12) || "—"}</div>
              <div className="muted small">PARENT {latest?.parent_version ? `v${latest.parent_version}` : "—"}</div>
              <div className="stax-caveat">LIVE EXECUTION = FALSE</div>
            </div>
          </div>

          {latest?.overlap?.note ? <p className="muted small">{latest.overlap.note}</p> : null}
          {latest?.overlap?.shared_game_count != null ? (
            <p className="muted">
              OBSERVATION OVERLAP · shared games {latest.overlap.shared_game_count} · method{" "}
              {latest.overlap.overlap_method}
            </p>
          ) : (
            <p className="muted small">OBSERVATION OVERLAP · {latest?.overlap?.overlap_method || "UNAVAILABLE"}</p>
          )}
          {latest?.sum_of_strategy_n != null ? (
            <p className="muted small">
              SUM OF PER-STRATEGY N = {fmtN(latest.sum_of_strategy_n)} — not an independent population
            </p>
          ) : null}

          <div className="stax-table-wrap">
          <table className="stax-table">
            <thead>
              <tr>
                <th>Strategy</th>
                <th>N</th>
                <th>Path rate</th>
                <th>Terminal</th>
                <th>EV</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => {
                const row = resultsByMember.get(m.member_id);
                return (
                  <tr key={m.member_id} className="stax-click" onClick={() => setDetailMember(m.member_id)}>
                    <td>
                      <div className="evidence">{m.display_id}</div>
                      <div>{memberLabel(m)}</div>
                    </td>
                    <td className="evidence">{fmtN(row?.summary?.n)}</td>
                    <td className="evidence">{pct(row?.summary?.path_rate)}</td>
                    <td className="evidence">{pct(row?.summary?.terminal)}</td>
                    <td className="evidence">{row?.summary?.ev ?? "—"}</td>
                    <td>{row?.status || "PENDING"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
          {detail?.envelope ? (
            <div className="stax-detail">
              <div className="stax-toolbar">
                <p className="ws-kicker">ROLLER results · {detail.member_id}</p>
                <button type="button" className="v2-text-link" onClick={() => setDetailMember(null)}>
                  Close
                </button>
              </div>
              <ResultsAnswer
                result={detail.envelope as AnswerResult}
                spec={blankSpec()}
                isStale={false}
                viewingSaved
                onOpenDetail={onOpenDetail}
                onOpenEvidence={() => undefined}
                onReturnToDefine={() => setDetailMember(null)}
                onSaveResults={() => undefined}
                onDownload={() => undefined}
                onNewResearch={() => setDetailMember(null)}
              />
            </div>
          ) : null}
          {head?.latest_version ? (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => void exportStax(head.stax_id)}
            >
              SuperASI export ready
            </button>
          ) : (
            <p className="muted small">MOVE TO SUPERASI is available after the STAX is persisted and executed.</p>
          )}
        </section>
      ) : null}

      {view === "history" ? (
        <section>
          <p className="ws-kicker">Version history</p>
          <h1 className="ws-title">Immutable snapshots</h1>
          <p className="muted small">
            Compare keys on member_id. Position is order only. Historical rows are stored snapshots —
            they are not re-executed.
          </p>
          <div className="stax-table-wrap">
          <table className="stax-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Kind</th>
                <th>Strategies</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.version} className="stax-click" onClick={() => void openVersion(v.version)}>
                  <td className="evidence">v{v.version}</td>
                  <td>{v.kind || "—"}</td>
                  <td>{v.strategy_count ?? "—"}</td>
                  <td>{v.status || "—"}</td>
                  <td className="muted">{v.created_at || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          {historyVersion ? (
            <div className="stax-detail">
              <p className="evidence">v{historyVersion.version} · {historyVersion.kind} · parent {historyVersion.parent_version || "—"}</p>
              <p className="muted small">definition {historyVersion.definition_hash?.slice(0, 16)}</p>
              <p className="muted small">dataset {historyVersion.dataset_fingerprint?.slice(0, 16)}</p>
              <div className="stax-table-wrap">
              <table className="stax-table">
                <thead>
                  <tr>
                    <th>member_id</th>
                    <th>Position</th>
                    <th>Display</th>
                    <th>N</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(historyVersion.members || []).map((m) => {
                    const row = (historyVersion.results || []).find((r) => r.member_id === m.member_id);
                    return (
                      <tr key={m.member_id}>
                        <td className="evidence">{m.member_id}</td>
                        <td>{m.position}</td>
                        <td>{m.display_id || "—"}</td>
                        <td className="evidence">{fmtN(row?.summary?.n)}</td>
                        <td>{row?.status || m.status || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              </div>
            </div>
          ) : null}
          {compare ? (
            <div className="stax-detail">
              <p className="ws-kicker">Compare by member_id</p>
              <p className="muted small">
                v{compare.from || "—"} → v{compare.to || "—"}
                {compare.definition_hash_changed ? " · DEFINITION CHANGED" : ""}
                {compare.dataset_fingerprint_changed ? " · DATASET CHANGED" : ""}
              </p>
              <div className="stax-table-wrap">
              <table className="stax-table">
                <thead>
                  <tr>
                    <th>member_id</th>
                    <th>Change</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {compareRows(compare).map((row) => (
                    <tr key={`${row.kind}-${row.member_id}`}>
                      <td className="evidence">{row.member_id}</td>
                      <td>{row.kind}</td>
                      <td className="muted">{row.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {view === "automation" ? (
        <section>
          <p className="ws-kicker">Automation</p>
          <h1 className="ws-title">Daily re-execution</h1>
          <p className="ws-lede">
            Recompute the saved research specification against the current warehouse. The timeframe
            does not expand.
          </p>
          <div className="stax-infra">
            <div>
              <div className="muted small">STATUS</div>
              <div className="evidence">{head?.automation_enabled ? "● ACTIVE" : "OFF"}</div>
              <div>DAILY · 00:00</div>
              <label className="stax-field">
                <span>TIMEZONE</span>
                <input value={tz} onChange={(e) => setTz(e.target.value)} />
              </label>
              <button
                type="button"
                className="btn-primary"
                disabled={!head}
                onClick={() => void automate(!head?.automation_enabled)}
              >
                {head?.automation_enabled ? "Disable" : "Enable"}
              </button>
            </div>
            <div>
              <div className="stax-caveat">RESEARCH AUTOMATION</div>
              <div className="stax-caveat">NOT EXECUTION</div>
              <div className="stax-caveat">LIVE EXECUTION = FALSE</div>
              <p className="muted small">LAST RUN {head?.last_run_at || "—"}</p>
              <p className="muted small">NEXT RUN {head?.next_run_at || "—"}</p>
            </div>
          </div>
        </section>
      ) : null}

      {view === "library" ? (
        <section>
          <p className="ws-kicker">STAX library</p>
          <h1 className="ws-title">Stack library</h1>
          <div className="stax-table-wrap">
          <table className="stax-table">
            <thead>
              <tr>
                <th>STAX</th>
                <th>Sport</th>
                <th>League</th>
                <th>Strategies</th>
                <th>Version</th>
                <th>Automation</th>
                <th>Last run</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {libraryRows.map((row) => (
                <tr
                  key={row.stax_id}
                  className="stax-click"
                  onClick={() => {
                    void reload(row.stax_id).then(() => onNavigate?.("overview"));
                  }}
                >
                  <td>
                    <div className="evidence">{row.name}</div>
                    <div className="muted small">{row.stax_id}</div>
                  </td>
                  <td>{row.sport || "—"}</td>
                  <td>{(row.league_set || []).join(" + ") || "—"}</td>
                  <td>{row.strategies ?? "—"}</td>
                  <td>{row.latest_version ? `v${row.latest_version}` : "—"}</td>
                  <td>{row.automation}</td>
                  <td className="muted">{row.last_run || "—"}</td>
                  <td>{row.status || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </section>
      ) : null}

      <StaxPicker
        open={pickerOpen}
        items={candidates}
        error={error}
        onClose={() => setPickerOpen(false)}
        onPick={(item) => void onPick(item)}
      />
      <StaxSaveModal
        open={saveOpen}
        name={saveName}
        description={saveDescription}
        busy={mutating}
        error={error}
        onChangeName={setSaveName}
        onChangeDescription={setSaveDescription}
        onCancel={() => setSaveOpen(false)}
        onSave={() => void save()}
      />
    </div>
  );
}
