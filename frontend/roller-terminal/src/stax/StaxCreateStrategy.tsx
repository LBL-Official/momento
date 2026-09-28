import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api/base";
import { emptyDraft } from "../v2/workflow/draft";
import EntryConditionsScreen from "../v2/workflow/EntryConditionsScreen";
import ExitConditionsScreen from "../v2/workflow/ExitConditionsScreen";
import { composeQuestionFromDraft, entrySummary, exitSummary } from "../v2/workflow/questionFromDraft";
import type { WorkflowDraft } from "../v2/workflow/types";
import { StaxApiError, createStaxStrategy, type StaxCreateStrategyResponse } from "./api";
import { leagueLabel, seasonLabel, timeframeLabel } from "./format";
import { universeFromLock } from "./nativeDraft";
import StaxUniverseFields from "./StaxUniverseFields";
import type { CanonicalUniverse, StaxHead } from "./types";

type Tab = "universe" | "entry" | "exit";

type Props = {
  staxId: string | null;
  staxName?: string | null;
  lockedUniverse: CanonicalUniverse | null;
  ensureStax: (name: string) => Promise<StaxHead>;
  onCancel: () => void;
  onAdded: (result: StaxCreateStrategyResponse, next: "list" | "another") => void;
};

function freshDraft(locked: CanonicalUniverse | null): WorkflowDraft {
  const draft = emptyDraft();
  if (!locked) return draft;
  return { ...draft, universe: universeFromLock(locked) };
}

export default function StaxCreateStrategy({
  staxId,
  staxName,
  lockedUniverse,
  ensureStax,
  onCancel,
  onAdded,
}: Props) {
  const locked = Boolean(lockedUniverse);
  const [draft, setDraft] = useState<WorkflowDraft>(() => freshDraft(lockedUniverse));
  const [tab, setTab] = useState<Tab>(locked ? "entry" : "universe");
  const [name, setName] = useState("");
  const [preview, setPreview] = useState<StaxCreateStrategyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!lockedUniverse) return;
    setDraft((current) => ({ ...current, universe: universeFromLock(lockedUniverse) }));
  }, [lockedUniverse]);

  const defaultName = useMemo(() => {
    const entry = entrySummary(draft);
    const exit = exitSummary(draft);
    if (entry.startsWith("No entry") && exit.startsWith("No observation")) {
      return composeQuestionFromDraft(draft);
    }
    return `${entry} → ${exit}`;
  }, [draft]);

  useEffect(() => {
    let cancelled = false;
    const handle = window.setTimeout(async () => {
      try {
        if (!staxId) {
          const res = await apiFetch("/research-query/compile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ draft }),
          });
          const compiled = (await res.json()) as { status?: string; reasons?: string[]; hashes?: { question_hash?: string } };
          if (cancelled) return;
          const ok = compiled.status != null && compiled.status !== "OPERATION_REQUIRED";
          setPreview({
            valid: ok,
            persisted: false,
            compile: compiled,
            hashes: compiled.hashes,
            reasons: compiled.reasons,
            message: ok ? undefined : "strategy does not compile",
          });
          setDuplicate(false);
          setError(ok ? null : compiled.reasons?.join(" · ") || "strategy does not compile");
          return;
        }
        const out = await createStaxStrategy(staxId, {
          name: name.trim() || defaultName,
          draft,
          persist: false,
        });
        if (cancelled) return;
        setPreview(out);
        setDuplicate(Boolean(out.duplicate));
        setError(out.valid === false ? out.message || out.reasons?.join(" · ") || "strategy does not compile" : null);
      } catch (e) {
        if (cancelled) return;
        setPreview(null);
        setDuplicate(e instanceof StaxApiError && e.code === "STAX_DUPLICATE_DEFINITION");
        setError(e instanceof Error ? e.message : String(e));
      }
    }, 280);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [draft, defaultName, name, staxId]);

  const persist = async (next: "list" | "another", allowDuplicate = false) => {
    setSaving(true);
    setError(null);
    try {
      const head = staxId
        ? { stax_id: staxId }
        : await ensureStax(name.trim() || defaultName || "Untitled STAX");
      const out = await createStaxStrategy(head.stax_id, {
        name: name.trim() || defaultName,
        draft,
        persist: true,
        allow_duplicate: allowDuplicate,
      });
      if (next === "another") {
        setDraft(freshDraft(out.stax?.universe || lockedUniverse));
        setName("");
        setPreview(null);
        setDuplicate(false);
        setTab("entry");
      }
      onAdded(out, next);
    } catch (e) {
      if (e instanceof StaxApiError && e.code === "STAX_DUPLICATE_DEFINITION") {
        setDuplicate(true);
      }
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const valid = Boolean(preview?.valid) && !error?.startsWith("STAX CONSTRAINT");
  const state = saving ? "SAVING" : error ? "INVALID" : preview?.valid ? "VALID" : "DRAFT";

  return (
    <section className="stax-create">
      <header className="stax-create-head">
        <div>
          <p className="ws-kicker">CREATE ROLLER STRATEGY</p>
          <h2 className="ws-title">FOR {staxId || staxName || "NEW STAX"}</h2>
          <p className="muted">
            This creates an independent ROLLER research object and adds it to the current STAX.
          </p>
        </div>
        <button type="button" className="v2-text-link" onClick={onCancel}>
          Cancel
        </button>
      </header>

      <div className={`stax-lock-banner${locked ? " is-locked" : ""}`}>
        <div>
          <div className="muted small">STAX UNIVERSE</div>
          <div className="evidence">
            {(lockedUniverse?.sport_family || draft.universe.sports.join(" / ") || "—").toUpperCase()}
            {" · "}
            {leagueLabel(lockedUniverse) !== "—" ? leagueLabel(lockedUniverse) : draft.universe.leagues.join(" + ") || "—"}
            {" · "}
            {seasonLabel(lockedUniverse) !== "—" ? seasonLabel(lockedUniverse) : draft.universe.seasons.join(" · ") || "—"}
          </div>
          <div className="muted">
            {lockedUniverse ? timeframeLabel(lockedUniverse) : `${draft.universe.dateFrom || "—"} → ${draft.universe.dateTo || "—"}`}
          </div>
        </div>
        <div className="stax-caveat">{locked ? "LOCKED BY STAX" : "FIRST STRATEGY SETS THE UNIVERSE"}</div>
      </div>

      <label className="stax-field">
        <span>Label</span>
        <input value={name} placeholder={defaultName} onChange={(e) => setName(e.target.value)} />
      </label>

      <div className="stax-create-tabs">
        {(["universe", "entry", "exit"] as const).map((id) => (
          <button
            key={id}
            type="button"
            className={`stax-create-tab${tab === id ? " on" : ""}`}
            onClick={() => setTab(id)}
          >
            {id}
          </button>
        ))}
        <span className="stax-create-state">{state}</span>
      </div>

      {tab === "universe" ? <StaxUniverseFields draft={draft} locked={locked} onChange={setDraft} /> : null}
      {tab === "entry" ? (
        <EntryConditionsScreen
          draft={draft}
          onChange={setDraft}
          onBack={() => setTab(locked ? "exit" : "universe")}
          onEnter={() => setTab("exit")}
        />
      ) : null}
      {tab === "exit" ? (
        <ExitConditionsScreen
          draft={draft}
          onChange={setDraft}
          onBack={() => setTab("entry")}
          onEnter={() => setTab("entry")}
        />
      ) : null}

      <div className="stax-create-review">
        <div>
          <div className="muted small">ROLLER DEFINITION</div>
          <div>{entrySummary(draft)}</div>
          <div className="muted">{exitSummary(draft)}</div>
        </div>
        {preview?.hashes?.question_hash ? (
          <div className="muted small">question_hash {preview.hashes.question_hash.slice(0, 16)}</div>
        ) : null}
      </div>

      {duplicate ? <p className="stax-warn">DUPLICATE RESEARCH DEFINITION. This definition already exists in this STAX.</p> : null}
      {error ? <p className="stax-error">{error}</p> : null}

      <div className="stax-toolbar">
        <button type="button" className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={saving || !valid || duplicate}
          onClick={() => void persist("another")}
        >
          Save & add another
        </button>
        {duplicate ? (
          <button type="button" className="btn-secondary" disabled={saving} onClick={() => void persist("list", true)}>
            Add anyway
          </button>
        ) : null}
        <button
          type="button"
          className="btn-primary"
          disabled={saving || !valid || duplicate}
          onClick={() => void persist("list")}
        >
          {saving ? "Saving…" : "Save & add to STAX"}
        </button>
      </div>
    </section>
  );
}
