import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api/base";
import { catalogByKind, catalogItem } from "../v2/catalog/availabilityCatalog";
import { GRID_CENTS } from "../v2/vocabulary/normalize";
import Bubble from "../v2/workflow/Bubble";
import { StaxApiError, createStaxStrategy, type StaxCreateStrategyResponse } from "./api";
import { leagueLabel, seasonLabel, timeframeLabel } from "./format";
import {
  DEFAULT_NATIVE_SEASON,
  NATIVE_ENTRY_FAMILIES,
  NATIVE_LEAGUES,
  NATIVE_TERMINALS,
  defaultNativeForm,
  draftFromNativeForm,
  nativeFormIssues,
  nativeStrategyLabel,
  type NativeEntryFamily,
  type NativeLeague,
  type NativeStrategyForm,
  type NativeTerminal,
} from "./nativeDraft";
import type { CanonicalUniverse, StaxHead } from "./types";

type Props = {
  staxId: string | null;
  staxName?: string | null;
  lockedUniverse: CanonicalUniverse | null;
  ensureStax: (name: string) => Promise<StaxHead>;
  onCancel: () => void;
  onAdvanced: () => void;
  onAdded: (result: StaxCreateStrategyResponse, next: "list" | "another") => void;
};

function PriceChip({
  cents,
  selected,
  disabled,
  onToggle,
}: {
  cents: number;
  selected: boolean;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      className={`ws-bubble${selected ? " on" : ""}`}
      disabled={disabled}
      aria-pressed={selected}
      onClick={onToggle}
    >
      {cents}¢
    </button>
  );
}

export default function StaxNativeBuilder({
  staxId,
  staxName,
  lockedUniverse,
  ensureStax,
  onCancel,
  onAdvanced,
  onAdded,
}: Props) {
  const locked = Boolean(lockedUniverse);
  const [form, setForm] = useState<NativeStrategyForm>(() => defaultNativeForm(lockedUniverse));
  const [preview, setPreview] = useState<StaxCreateStrategyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm((current) => {
      const next = defaultNativeForm(lockedUniverse);
      return {
        ...current,
        league: next.league,
        season: next.season,
      };
    });
  }, [lockedUniverse]);

  const draft = useMemo(() => draftFromNativeForm(form, lockedUniverse), [form, lockedUniverse]);
  const defaultName = nativeStrategyLabel(form, lockedUniverse);
  const localIssues = nativeFormIssues(form);
  const seasons = catalogByKind("season");
  const twoSided = form.lossCents != null;

  useEffect(() => {
    let cancelled = false;
    const handle = window.setTimeout(async () => {
      if (localIssues.length) {
        setPreview(null);
        setDuplicate(false);
        setError(localIssues.join(" · "));
        return;
      }
      try {
        if (!staxId) {
          const res = await apiFetch("/research-query/compile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ draft }),
          });
          const compiled = (await res.json()) as {
            status?: string;
            reasons?: string[];
            hashes?: { question_hash?: string };
          };
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
          name: form.name.trim() || defaultName,
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
  }, [draft, defaultName, form.name, localIssues, staxId]);

  const persist = async (next: "list" | "another", allowDuplicate = false) => {
    setSaving(true);
    setError(null);
    try {
      const head = staxId
        ? { stax_id: staxId }
        : await ensureStax(staxName && staxName !== "Multi-strategy stack" ? staxName : `${form.league} ${form.season}`);
      const out = await createStaxStrategy(head.stax_id, {
        name: form.name.trim() || defaultName,
        draft,
        persist: true,
        allow_duplicate: allowDuplicate,
      });
      if (next === "another") {
        setForm(defaultNativeForm(out.stax?.universe || lockedUniverse));
        setPreview(null);
        setDuplicate(false);
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

  const patch = (partial: Partial<NativeStrategyForm>) => {
    setForm((current) => {
      const next = { ...current, ...partial };
      if (partial.entryCents != null && next.lossCents != null && next.pathCents != null) {
        if (next.pathCents < next.entryCents) next.pathCents = null;
        if (next.lossCents > next.entryCents) next.lossCents = null;
      }
      return next;
    });
  };

  const valid = Boolean(preview?.valid) && !localIssues.length && !error?.startsWith("STAX CONSTRAINT");
  const state = saving ? "SAVING" : error ? "INVALID" : preview?.valid ? "VALID" : "DRAFT";

  return (
    <section className="stax-native" aria-label="Add strategy">
      <header className="stax-create-head">
        <div>
          <p className="ws-kicker">+ ADD STRATEGY</p>
          <h2 className="ws-title">Create a ROLLER research object</h2>
          <p className="muted">
            STAX writes a ROLLER-compatible specification. ROLLER decides whether it is measurable
            and how it is measured.
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
            {(lockedUniverse?.sport_family || "basketball").toUpperCase()}
            {" · "}
            {leagueLabel(lockedUniverse) !== "—" ? leagueLabel(lockedUniverse) : form.league}
            {" · "}
            {seasonLabel(lockedUniverse) !== "—" ? seasonLabel(lockedUniverse) : form.season}
          </div>
          <div className="muted">
            {lockedUniverse
              ? timeframeLabel(lockedUniverse)
              : `${draft.universe.dateFrom || "—"} → ${draft.universe.dateTo || "—"}`}
          </div>
        </div>
        <div className="stax-caveat">{locked ? "LOCKED BY STAX" : "FIRST STRATEGY SETS THE UNIVERSE"}</div>
      </div>

      <label className="stax-field">
        <span>Strategy name</span>
        <input
          value={form.name}
          placeholder={defaultName}
          onChange={(e) => patch({ name: e.target.value })}
        />
      </label>

      <div className="stax-native-grid">
        <div className="stax-field-row">
          <span>Universe</span>
          <div className="ws-chip-row">
            {(locked && lockedUniverse?.league_set?.length ? lockedUniverse.league_set : [...NATIVE_LEAGUES]).map((id) => (
              <Bubble
                key={id}
                item={catalogItem(id, "league") ?? { id, label: id, kind: "league", availability: "IMPLEMENTED" }}
                selected={locked ? true : form.league === id}
                disabled={locked}
                onToggle={() => {
                  if (!locked && (id === "NBA" || id === "NCAAB")) patch({ league: id as NativeLeague });
                }}
              />
            ))}
          </div>
        </div>

        <div className="stax-field-row">
          <span>Season</span>
          <div className="ws-chip-row">
            {(locked && lockedUniverse?.seasons?.length
              ? lockedUniverse.seasons.map(
                  (id) => catalogItem(id, "season") ?? { id, label: id, kind: "season" as const, availability: "IMPLEMENTED" as const },
                )
              : seasons
            ).map((item) => (
              <Bubble
                key={item.id}
                item={item}
                selected={locked ? true : form.season === item.id}
                disabled={locked}
                onToggle={() => {
                  if (!locked) patch({ season: item.id || DEFAULT_NATIVE_SEASON });
                }}
              />
            ))}
          </div>
        </div>

        <div className="stax-field-row">
          <span>Entry</span>
          <div className="stax-native-split">
            <div className="ws-chip-row">
              {NATIVE_ENTRY_FAMILIES.map((id) => (
                <Bubble
                  key={id}
                  item={
                    catalogItem(id, "entry") ?? {
                      id,
                      label: id === "cross" ? "Cross" : "First Touch",
                      kind: "entry",
                      availability: "IMPLEMENTED",
                    }
                  }
                  selected={form.entryFamily === id}
                  onToggle={() => patch({ entryFamily: id as NativeEntryFamily })}
                />
              ))}
            </div>
            <div className="ws-chip-row ws-price-grid">
              {GRID_CENTS.map((c) => (
                <PriceChip
                  key={`entry-${c}`}
                  cents={c}
                  selected={form.entryCents === c}
                  onToggle={() => patch({ entryCents: c })}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="stax-field-row">
          <span>Path</span>
          <div className="stax-native-split">
            <div className="ws-chip-row">
              <Bubble
                item={catalogItem("reach", "exit_path") ?? { id: "reach", label: "Reach", kind: "exit_path", availability: "IMPLEMENTED" }}
                selected
                onToggle={() => undefined}
              />
            </div>
            <div className="ws-chip-row ws-price-grid">
              {GRID_CENTS.map((c) => {
                const blocked = twoSided && c < form.entryCents;
                return (
                  <PriceChip
                    key={`path-${c}`}
                    cents={c}
                    selected={form.pathCents === c}
                    disabled={blocked}
                    onToggle={() => {
                      if (blocked) return;
                      patch({ pathCents: form.pathCents === c ? null : c });
                    }}
                  />
                );
              })}
            </div>
          </div>
        </div>

        <div className="stax-field-row">
          <span>Loss / Stop</span>
          <div className="stax-native-split">
            <div className="ws-chip-row">
              <Bubble
                item={{ id: "loss_reach", label: "Reach", kind: "exit_path", availability: "IMPLEMENTED" }}
                selected={form.lossCents != null}
                onToggle={() => patch({ lossCents: form.lossCents == null ? 35 : null })}
              />
            </div>
            <div className="ws-chip-row ws-price-grid">
              {GRID_CENTS.map((c) => {
                const blocked = c > form.entryCents;
                return (
                  <PriceChip
                    key={`loss-${c}`}
                    cents={c}
                    selected={form.lossCents === c}
                    disabled={blocked}
                    onToggle={() => {
                      if (blocked) return;
                      patch({ lossCents: form.lossCents === c ? null : c });
                    }}
                  />
                );
              })}
            </div>
          </div>
        </div>

        <div className="stax-field-row">
          <span>Terminal</span>
          <div className="ws-chip-row">
            {NATIVE_TERMINALS.map((id) => (
              <Bubble
                key={id}
                item={{
                  id,
                  label: id === "yes" ? "YES" : id === "no" ? "NO" : "BOTH",
                  kind: "exit_terminal",
                  availability: "IMPLEMENTED",
                }}
                selected={form.terminal === id}
                onToggle={() => patch({ terminal: id as NativeTerminal })}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="stax-create-review">
        <div>
          <div className="muted small">ROLLER DEFINITION</div>
          <div className="evidence">{defaultName}</div>
          <div className="muted">
            {staxId || staxName || "NEW STAX"} · question_hash{" "}
            {preview?.hashes?.question_hash?.slice(0, 16) || "—"}
          </div>
        </div>
        <span className="stax-create-state">{state}</span>
      </div>

      {duplicate ? (
        <p className="stax-warn">DUPLICATE RESEARCH DEFINITION. This definition already exists in this STAX.</p>
      ) : null}
      {error ? <p className="stax-error">{error}</p> : null}

      <div className="stax-toolbar">
        <button
          type="button"
          className="btn-primary"
          disabled={saving || !valid || duplicate}
          onClick={() => void persist("list")}
        >
          {saving ? "Saving…" : "Save strategy"}
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
        <button type="button" className="v2-text-link" onClick={onAdvanced}>
          Full ROLLER definition
        </button>
      </div>
    </section>
  );
}
