import { useEffect, useMemo, useState } from "react";
import {
  listWarehouseLabs,
  saveWarehouseLab,
  type WarehouseCompile,
  type WarehouseResultsContract,
} from "../../api/warehouseResearch";
import RiskPanel from "./RiskPanel";

const SAVED_NAME_KEY = "roller.v2.saved_strategy_by_hash.v1";

type SavedName = { name: string; lab_id: string; folder: string };

function loadSavedMap(): Record<string, SavedName> {
  try {
    const raw = sessionStorage.getItem(SAVED_NAME_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, SavedName>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function persistSaved(hash: string, rec: SavedName): void {
  const map = loadSavedMap();
  map[hash] = rec;
  try {
    sessionStorage.setItem(SAVED_NAME_KEY, JSON.stringify(map));
  } catch {
    /* private mode */
  }
}

export type WarehouseSuperasiHandoff = {
  labId: string;
  folder: string;
  name: string;
};

type Props = {
  payload: WarehouseCompile;
  onReturn: () => void;
  onSaved?: () => void;
  onMoveToSuperASI?: (handoff: WarehouseSuperasiHandoff) => void;
};

function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function rr(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(2)} : 1`;
}

function evCents(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value / 100).toFixed(2)}¢`;
}

const SETTLEMENT_YES_E4 = 10000;
const SETTLEMENT_NO_E4 = 0;

function firstPriceE4(items?: Array<Record<string, unknown>>): number | null {
  const raw = items?.[0]?.price_e4;
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function firstOp(items?: Array<Record<string, unknown>>): string {
  return String(items?.[0]?.op || "").toUpperCase();
}

function isWinHold(contract: WarehouseResultsContract): boolean {
  return Boolean(contract.win_hold) || firstOp(contract.win_exit) === "HOLD";
}

function isLossHold(contract: WarehouseResultsContract): boolean {
  return Boolean(contract.loss_hold) || firstOp(contract.loss_exit) === "HOLD";
}

function tradeOutcome(row: Record<string, unknown>, winHold: boolean): "WIN" | "LOSS" | null {
  const klass = String(row.classification || "").toUpperCase();
  const settle = String(row.settlement_status || "").toUpperCase();
  if (klass === "WIN") return "WIN";
  if (klass === "LOSS") return "LOSS";
  if (winHold && klass === "HELD_TO_SETTLEMENT") {
    if (settle === "YES") return "WIN";
    if (settle === "NO") return "LOSS";
  }
  return null;
}

function headlineBooks(contract: WarehouseResultsContract): { w: number; l: number } {
  const stats = contract.statistics || {};
  if (stats.W != null && stats.L != null) {
    return { w: Number(stats.W), l: Number(stats.L) };
  }
  const winHold = isWinHold(contract);
  let w = 0;
  let l = 0;
  for (const row of contract.audit_rows || []) {
    const outcome = tradeOutcome(row as Record<string, unknown>, winHold);
    if (outcome === "WIN") w += 1;
    if (outcome === "LOSS") l += 1;
  }
  return { w, l };
}

function centsFromE4(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value / 100}¢`;
}

/** Display the trade geometry. Server statistics win when present. */
function tradeDisplay(contract: WarehouseResultsContract, lastTrade: boolean): {
  reward: number | null;
  risk: number | null;
  rr: number | null;
  ev: number | null;
} {
  const stats = contract.statistics || {};
  const entry = firstPriceE4(contract.entry);
  const winExit = firstPriceE4(contract.win_exit) ?? (isWinHold(contract) ? SETTLEMENT_YES_E4 : null);
  const lossExit = firstPriceE4(contract.loss_exit) ?? (isLossHold(contract) ? SETTLEMENT_NO_E4 : null);
  const reward = stats.reward_e4 ?? (entry != null && winExit != null ? winExit - entry : null);
  const risk = stats.risk_e4 ?? (entry != null && lossExit != null ? entry - lossExit : null);
  const rr = stats.rr ?? (reward != null && risk != null && risk !== 0 ? reward / risk : null);
  if (lastTrade || stats.ev_status === "DATA_REQUIRED") {
    return { reward, risk, rr, ev: null };
  }
  if (stats.ev_e4 != null && !Number.isNaN(Number(stats.ev_e4))) {
    return { reward, risk, rr, ev: Number(stats.ev_e4) };
  }
  const n = Number(stats.population ?? contract.population ?? 0);
  if (!n || entry == null) return { reward, risk, rr, ev: null };
  const pathWinN = Number(stats.path_win_n ?? 0);
  const termWinN = Number(stats.terminal_win_n ?? 0);
  const pathLossN = Number(stats.path_loss_n ?? 0);
  const termLossN = Number(stats.terminal_loss_n ?? 0);
  let total = 0;
  let counted = false;
  if (pathWinN) {
    if (winExit == null) return { reward, risk, rr, ev: null };
    total += pathWinN * (winExit - entry);
    counted = true;
  }
  if (termWinN) {
    total += termWinN * (SETTLEMENT_YES_E4 - entry);
    counted = true;
  }
  if (pathLossN) {
    if (lossExit == null) return { reward, risk, rr, ev: null };
    total -= pathLossN * (entry - lossExit);
    counted = true;
  }
  if (termLossN) {
    total -= termLossN * (entry - SETTLEMENT_NO_E4);
    counted = true;
  }
  return { reward, risk, rr, ev: counted ? total / n : null };
}

function auditValue(row: Record<string, unknown>, key: string): string {
  const v = row[key];
  if (v == null || v === "") return "—";
  if (typeof v === "number" && /value/.test(key)) return `${(v / 100).toFixed(0)}¢`;
  return String(v);
}

function defaultStrategyName(payload: WarehouseCompile, folder: string): string {
  const entry = payload.question?.entry_conditions?.[0];
  const cents = entry?.price_e4 != null ? Math.round(Number(entry.price_e4) / 100) : 65;
  const from = payload.question?.universe.date_from || "";
  const to = payload.question?.universe.date_to || "";
  const window = from && to ? ` ${from.slice(0, 7)}` : "";
  return `${folder} CROSS ${cents} REACH 85 40${window}`;
}

export default function WarehouseResults({ payload, onReturn, onSaved, onMoveToSuperASI }: Props) {
  const contract = (payload.results_contract || {}) as WarehouseResultsContract;
  const stats = contract.statistics || {};
  const classif = contract.classification || {};
  const coverage = contract.coverage || {};
  const exclusions = contract.exclusions || coverage.exclusions || {};
  const rows = contract.audit_rows || [];
  const status = payload.status || "";
  const resultHash = String(contract.reproducibility?.result_hash || payload.result?.result_hash || "");
  const deskFolder = useMemo(() => {
    const sports = payload.question?.universe.sports || [];
    const leagues = payload.question?.universe.leagues || [];
    if (sports.includes("MLB") || leagues.includes("MLB")) return "MLB";
    if (sports.includes("NCAAB") || leagues.includes("NCAAB")) return "NCAAB";
    if ((sports.includes("ATP") || leagues.includes("ATP")) && !(sports.includes("WTA") || leagues.includes("WTA"))) {
      return "ATP";
    }
    if ((sports.includes("WTA") || leagues.includes("WTA")) && !(sports.includes("ATP") || leagues.includes("ATP"))) {
      return "WTA";
    }
    return "NBA";
  }, [payload.question]);
  const lastTrade = String(contract.observation_basis || "").toUpperCase() === "LAST_TRADE_PRINT";
  const trade = useMemo(() => tradeDisplay(contract, lastTrade), [contract, lastTrade]);
  const books = useMemo(() => headlineBooks(contract), [contract]);
  const decided = books.w + books.l;
  const winRate = stats.win_rate ?? (decided ? books.w / decided : null);
  const lossRate = stats.loss_rate ?? (decided ? books.l / decided : null);
  const [name, setName] = useState("");
  const [folder, setFolder] = useState(deskFolder);
  const [labId, setLabId] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [superasiBusy, setSuperasiBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    if (!resultHash) {
      setName("");
      setLabId(null);
      setFolder(deskFolder);
      setSaved(false);
      return;
    }
    const local = loadSavedMap()[resultHash];
    if (local) {
      setName(local.name);
      setLabId(local.lab_id);
      setFolder(local.folder || deskFolder);
      setSaved(true);
      return;
    }
    let cancelled = false;
    void listWarehouseLabs()
      .then(({ labs }) => {
        if (cancelled) return;
        const match = labs.find((lab) => lab.result_hash === resultHash);
        if (match) {
          setName(match.strategy_name);
          setLabId(match.lab_id);
          setFolder(match.folder || deskFolder);
          setSaved(true);
          persistSaved(resultHash, {
            name: match.strategy_name,
            lab_id: match.lab_id,
            folder: match.folder || deskFolder,
          });
          return;
        }
        setName("");
        setLabId(null);
        setFolder(deskFolder);
        setSaved(false);
      })
      .catch(() => {
        if (!cancelled) {
          setName("");
          setLabId(null);
          setFolder(deskFolder);
          setSaved(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [resultHash, deskFolder]);
  const save = async () => {
    const strategyName = name.trim();
    if (!strategyName) {
      setMessage("Name the strategy before saving.");
      return;
    }
    setBusy(true);
    try {
      const rec = await saveWarehouseLab({
        name: strategyName,
        folder,
        labId: saved ? labId : null,
        question: payload.question,
        payload,
      });
      setName(rec.strategy_name);
      setLabId(rec.lab_id);
      setFolder(rec.folder || folder);
      setSaved(true);
      if (resultHash) {
        persistSaved(resultHash, {
          name: rec.strategy_name,
          lab_id: rec.lab_id,
          folder: rec.folder || folder,
        });
      }
      setMessage(saved ? `Renamed ${rec.filename}` : `Saved ${rec.filename}`);
      onSaved?.();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };
  const moveToSuperASI = async () => {
    if (!onMoveToSuperASI) {
      setMessage("SuperASI handoff is not wired.");
      return;
    }
    setSuperasiBusy(true);
    try {
      if (saved && labId) {
        onMoveToSuperASI({ labId, folder, name: name.trim() || defaultStrategyName(payload, folder) });
        return;
      }
      const strategyName = name.trim() || defaultStrategyName(payload, folder);
      const rec = await saveWarehouseLab({
        name: strategyName,
        folder,
        labId: saved ? labId : null,
        question: payload.question,
        payload,
      });
      setName(rec.strategy_name);
      setLabId(rec.lab_id);
      setFolder(rec.folder || folder);
      setSaved(true);
      if (resultHash) {
        persistSaved(resultHash, {
          name: rec.strategy_name,
          lab_id: rec.lab_id,
          folder: rec.folder || folder,
        });
      }
      onSaved?.();
      onMoveToSuperASI({
        labId: rec.lab_id,
        folder: rec.folder || folder,
        name: rec.strategy_name,
      });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setSuperasiBusy(false);
    }
  };
  return (
    <div className="ws-flow ws-warehouse-results">
      <header className="ws-flow-head ws-results-head">
        <div>
          <p className="v2-kicker">Warehouse results</p>
          <h1 className="v2-page-title">
            {status === "ZERO_RESULTS" ? "Zero results" : lastTrade ? "Observed last-trade path" : "Observed candle path"}
          </h1>
          <p className="muted small">
            {contract.label || "observed candle-path research result"}. W/L is the trade. Not live
            trading. Not a fill. Official settlement is an overlay on the same rows — it does not
            un-do a path LOSS. ZERO RESULTS means the engine ran and population = 0.
          </p>
        </div>
        <form
          className="ws-save-strategy"
          aria-label="Save Strategy"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <p className="v2-kicker">{saved ? "Saved strategy" : "Save Strategy"}</p>
          <input
            type="text"
            placeholder="Strategy name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            type="text"
            placeholder="Folder"
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
            disabled={saved}
          />
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? (saved ? "Renaming…" : "Saving…") : saved ? "Rename" : "Save"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => void moveToSuperASI()} disabled={superasiBusy}>
            {superasiBusy ? "Handing off…" : "Move to SuperASI"}
          </button>
          {saved ? <p className="muted small">Saved · further edits rename this lab only.</p> : null}
          {message ? <p className="muted small">{message}</p> : null}
        </form>
      </header>

      <section className="ws-warehouse-stats" aria-label="Trade statistics">
        <dl>
          <div>
            <dt>Population</dt>
            <dd>{stats.population ?? contract.population ?? 0}</dd>
          </div>
          <div>
            <dt>W / L</dt>
            <dd>
              {books.w} / {books.l}
            </dd>
          </div>
          <div>
            <dt>Win rate</dt>
            <dd>{pct(winRate)}</dd>
          </div>
          <div>
            <dt>Loss rate</dt>
            <dd>{pct(lossRate)}</dd>
          </div>
          <div>
            <dt>R:R</dt>
            <dd>{rr(trade.rr)}</dd>
          </div>
          {stats.rr_trade_mean != null &&
          trade.rr != null &&
          Math.abs(Number(stats.rr_trade_mean) - Number(trade.rr)) > 1e-6 ? (
            <div>
              <dt>R:R trade mean</dt>
              <dd>{rr(stats.rr_trade_mean)}</dd>
            </div>
          ) : null}
          <div>
            <dt>EV</dt>
            <dd>{lastTrade || stats.ev_status === "DATA_REQUIRED" ? "DATA_REQUIRED" : evCents(trade.ev)}</dd>
          </div>
        </dl>
        <p className="muted small">
          {trade.reward != null && trade.risk != null
            ? `Trade payoff +${centsFromE4(trade.reward)} / −${centsFromE4(trade.risk)}. `
            : null}
          {stats.assumption}
        </p>
      </section>

      <section className="ws-warehouse-stats ws-warehouse-books" aria-label="Resolution books">
        <p className="v2-kicker">Resolution books</p>
        <p className="muted small">
          Breakdown only. Official W is settle YES on the same rows; it is not the trade and does not
          un-do a path LOSS.
        </p>
        <dl>
          <div>
            <dt>Path W / L</dt>
            <dd>
              {stats.path_win_n ?? 0} / {stats.path_loss_n ?? 0}
            </dd>
          </div>
          <div>
            <dt>Terminal W / L</dt>
            <dd>
              {stats.terminal_win_n ?? 0} / {stats.terminal_loss_n ?? 0}
            </dd>
          </div>
          <div>
            <dt>Unresolved</dt>
            <dd>{stats.unresolved_n ?? 0}</dd>
          </div>
          <div>
            <dt>Official W / L</dt>
            <dd>
              {stats.official_w_n ?? 0} / {stats.official_l_n ?? 0}
            </dd>
          </div>
          <div>
            <dt>Official W rate</dt>
            <dd>{pct(stats.official_w_rate)}</dd>
          </div>
        </dl>
      </section>

      <section aria-label="Research identity">
        <p className="v2-kicker">Strategy</p>
        <dl className="ws-warehouse-meta">
          <div>
            <dt>Sport / league / season</dt>
            <dd>
              {(payload.question?.universe.sports || []).join(", ") || "NBA"}
              {" · "}
              {(payload.question?.universe.leagues || []).join(", ") || "NBA"}
              {" · "}
              {(payload.question?.universe.seasons || []).join(", ") || "—"}
            </dd>
          </div>
          <div>
            <dt>Date range</dt>
            <dd>
              {payload.question?.universe.date_from || "—"} → {payload.question?.universe.date_to || "—"}
            </dd>
          </div>
          <div>
            <dt>plan_hash / result_hash</dt>
            <dd className="ws-mono">
              {contract.plan_hash || payload.plan_hash || "—"}
              {" · "}
              {String(contract.reproducibility?.result_hash || payload.result?.result_hash || "—")}
            </dd>
          </div>
          <div>
            <dt>compiler / warehouse / identity / catalog</dt>
            <dd>
              {contract.compiler_version} / {contract.warehouse_version} / {contract.identity_version} /{" "}
              {contract.catalog_version}
            </dd>
          </div>
          <div>
            <dt>Observation</dt>
            <dd>
              {contract.observation_basis} · {contract.resolution} · {contract.pit_field}
            </dd>
          </div>
          <div>
            <dt>Strategy</dt>
            <dd>
              {(contract.entry || [])
                .map((e) => {
                  const windows = (e.period_windows as Array<{ period?: string }> | undefined) || [];
                  const period =
                    windows.length > 0
                      ? windows.map((w) => w.period).filter(Boolean).join(" or ")
                      : e.period
                        ? String(e.period)
                        : "";
                  const ceiling =
                    e.max_entry_e4 != null && !Number.isNaN(Number(e.max_entry_e4))
                      ? ` accept through ${Number(e.max_entry_e4) / 100}¢`
                      : "";
                  return `${e.op} ${Number(e.price_e4) / 100}¢${ceiling}${period ? ` ${period}` : ""}`;
                })
                .join(" · ") || "—"}
              {" · WIN "}
              {isWinHold(contract)
                ? "HOLD (settlement YES)"
                : (contract.win_exit || [])
                    .map((e) =>
                      e.price_e4 == null || Number.isNaN(Number(e.price_e4))
                        ? String(e.op || "HOLD")
                        : `${e.op} ${Number(e.price_e4) / 100}¢`,
                    )
                    .join(" · ") || "HOLD"}
              {" · LOSS "}
              {(contract.loss_exit || [])
                .map((e) =>
                  e.price_e4 == null || Number.isNaN(Number(e.price_e4))
                    ? String(e.op || "HOLD")
                    : `${e.op} ${Number(e.price_e4) / 100}¢`,
                )
                .join(" · ") || "HOLD"}
              {" · "}
              {contract.terminal}
            </dd>
          </div>
        </dl>
      </section>

      <section aria-label="Classification">
        <p className="v2-kicker">Classification</p>
        <ul>
          {Object.entries(classif).map(([k, v]) => (
            <li key={k}>
              {k}: {v}
            </li>
          ))}
          {contract.settlement_crosstab ? (
            <>
              <li>HELD + YES: {contract.settlement_crosstab.held_yes ?? 0}</li>
              <li>HELD + NO: {contract.settlement_crosstab.held_no ?? 0}</li>
              <li>HELD + MISSING: {contract.settlement_crosstab.held_missing ?? 0}</li>
            </>
          ) : null}
          {!Object.keys(classif).length ? <li>none</li> : null}
        </ul>
      </section>

      <section aria-label="Base Terminal Efficiency">
        <p className="v2-kicker">Base TE</p>
        <p className="muted small">
          {contract.te_scope?.requested
            ? `scoped ${JSON.stringify(contract.te_scope.requested)} · entry ${contract.te_scope.n_entry ?? "—"} · kept ${contract.te_scope.n_scoped ?? "—"} · dropped ${contract.te_scope.n_dropped ?? 0}`
            : "no TE population scope"}
        </p>
      </section>

      <section aria-label="Exposure">
        <p className="v2-kicker">Exposure</p>
        <p className="muted small">
          {contract.exposure
            ? [
                contract.exposure.status || "UNVERIFIED",
                `EXPOSURE_UNIT=${contract.exposure.declared_unit || contract.exposure.exposure_unit || "GAME"}`,
                `unique games ${contract.exposure.n_unique_games ?? "—"}`,
                contract.exposure.execution_enforced
                  ? "first chronological · one trade per game enforced"
                  : "N unchanged · verify only",
              ].join(" · ")
            : "UNVERIFIED"}
        </p>
        {contract.exposure?.reason ? <p className="muted small">{contract.exposure.reason}</p> : null}
      </section>

      <section aria-label="Coverage">
        <p className="v2-kicker">Coverage</p>
        <p className="muted small">
          Nominal games {coverage.nominal_universe?.games ?? "—"} · markets {coverage.nominal_universe?.markets ?? "—"} ·
          executed {coverage.executed_population ?? 0}
        </p>
        <ul>
          {Object.entries(exclusions).map(([k, v]) => (
            <li key={k}>
              excluded {k}: {v}
            </li>
          ))}
          {(coverage.missing_data || []).map((k) => (
            <li key={`m-${k}`}>missing data: {k}</li>
          ))}
          {(coverage.unsupported_operations || []).map((k) => (
            <li key={`o-${k}`}>unsupported: {k}</li>
          ))}
        </ul>
      </section>

      <section aria-label="Row-level audit">
        <p className="v2-kicker">Row-level audit</p>
        <div className="ws-audit-scroll">
          <table className="ws-audit-table">
            <thead>
              <tr>
                {[
                  "internal_game_id",
                  "market_id",
                  "entry_timestamp",
                  "entry_value",
                  "entry_operation",
                  "entry_period",
                  "entry_clock",
                  "win_exit_timestamp",
                  "win_exit_value",
                  "win_exit_operation",
                  "loss_exit_timestamp",
                  "loss_exit_value",
                  "loss_exit_operation",
                  "classification",
                  "settlement_status",
                  "settlement_value",
                  "observation_basis",
                  "observation_resolution",
                  "pit_field",
                ].map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={`${row.internal_game_id}-${row.market_id}-${row.entry_timestamp}-${i}`}>
                  {[
                    "internal_game_id",
                    "market_id",
                    "entry_timestamp",
                    "entry_value",
                    "entry_operation",
                    "entry_period",
                    "entry_clock",
                    "win_exit_timestamp",
                    "win_exit_value",
                    "win_exit_operation",
                    "loss_exit_timestamp",
                    "loss_exit_value",
                    "loss_exit_operation",
                    "classification",
                    "settlement_status",
                    "settlement_value",
                    "observation_basis",
                    "observation_resolution",
                    "pit_field",
                  ].map((col) => (
                    <td key={col}>{auditValue(row, col)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <RiskPanel
        researchHash={String(contract.reproducibility?.result_hash || payload.result?.result_hash || "")}
        classifications={rows.map((r) => String(r.classification || ""))}
      />

      <section aria-label="Reproducibility">
        <p className="v2-kicker">Reproducibility</p>
        <pre className="spec-json">{JSON.stringify(contract.reproducibility || {}, null, 2)}</pre>
      </section>

      <footer className="ws-define-footer">
        <button type="button" className="btn-secondary" onClick={onReturn}>
          ← Edit research
        </button>
      </footer>
    </div>
  );
}

export function isWarehouseResult(payload: unknown): payload is WarehouseCompile {
  if (!payload || typeof payload !== "object") return false;
  const rec = payload as Record<string, unknown>;
  return rec.source === "warehouse_research" || Boolean(rec.results_contract);
}
