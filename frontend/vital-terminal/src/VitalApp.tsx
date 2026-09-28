import { useCallback, useEffect, useRef, useState } from "react";
import Bankroll from "./Bankroll";
import BotDetail from "./BotDetail";
import Bots from "./Bots";
import ItiBotDetail from "./ItiBotDetail";
import {
  getVitalDesk,
  moneyText,
  observeVitalHost,
  observeVitalKalshi,
  type VitalBankroll,
  type VitalBot,
  type VitalControls,
  type VitalDiagnose,
  type VitalExecution,
  type VitalHealth,
  type VitalIntegrationProof,
  type VitalKalshi,
  type VitalKalshiHealth,
  type VitalLogs,
  type VitalParameters,
  type VitalRuntime,
  type VitalStatus,
  type VitalStrategy,
} from "./api/vitalApi";
import { bookEnvironment, isMlb001, sortBots, sportLabel } from "./desk";
import { ageText, errorMessage, toneForLifecycle } from "./format";
import Home from "./Home";
import LiveObservatory from "./LiveObservatory";
import { openJump, openRoller, openSuperASI } from "./origins";
import VitalSpine from "./VitalSpine";
import type { VitalRoute } from "./navigation";

const MLB_001 = "mlb-001";
const READ_MS = 8000;
const OBSERVE_MS = 45000;

function selectedBotFromHash(): string {
  const hash = window.location.hash.replace(/^#/, "");
  const match = hash.match(/^\/bots\/([a-z0-9-]+)$/);
  return match?.[1] || "";
}

function routeFromHash(): VitalRoute {
  const hash = window.location.hash.replace(/^#/, "");
  if (hash.startsWith("/bankroll")) return "bankroll";
  if (hash.startsWith("/live")) return "live";
  if (hash.startsWith("/bots/") || hash === "/detail") return "detail";
  if (hash.startsWith("/bots")) return "bots";
  return "home";
}

function runtimeObservedAt(runtime: VitalRuntime | null | undefined): string {
  const observed = runtime?.observed;
  if (!observed || typeof observed !== "object") return "";
  return String((observed as { observed_at?: unknown }).observed_at || "");
}

function shouldApplyRuntime(next: VitalRuntime | null | undefined, newest: string): boolean {
  const stamp = runtimeObservedAt(next);
  if (!stamp) return !newest;
  return !newest || stamp >= newest;
}

function hashFor(route: VitalRoute, botId = MLB_001): string {
  if (route === "detail") return `#/bots/${botId}`;
  if (route === "live") return "#/live";
  if (route === "bots") return "#/bots";
  if (route === "bankroll") return "#/bankroll";
  return "#/";
}

async function pullBook(botId: string, environment: "DEMO" | "PRODUCTION"): Promise<void> {
  try {
    await observeVitalKalshi(botId, environment);
  } catch {
    // Unread stays OBSERVATION_UNAVAILABLE. Never invent $0.
  }
}

export default function VitalApp() {
  const [route, setRoute] = useState<VitalRoute>(() => routeFromHash());
  const [selectedId, setSelectedId] = useState<string>(() => selectedBotFromHash() || MLB_001);
  const [health, setHealth] = useState<VitalHealth | null>(null);
  const [bots, setBots] = useState<VitalBot[]>([]);
  const [bot, setBot] = useState<VitalBot | null>(null);
  const [status, setStatus] = useState<VitalStatus | null>(null);
  const [runtime, setRuntime] = useState<VitalRuntime | null>(null);
  const [logs, setLogs] = useState<VitalLogs | null>(null);
  const [parameters, setParameters] = useState<VitalParameters | null>(null);
  const [kalshiHealth, setKalshiHealth] = useState<VitalKalshiHealth | null>(null);
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const [orders, setOrders] = useState<Record<string, unknown> | null>(null);
  const [positions, setPositions] = useState<Record<string, unknown> | null>(null);
  const [execution, setExecution] = useState<VitalExecution | null>(null);
  const [bankroll, setBankroll] = useState<VitalBankroll | null>(null);
  const [kalshi, setKalshi] = useState<VitalKalshi | null>(null);
  const [strategy, setStrategy] = useState<VitalStrategy | null>(null);
  const [diagnose, setDiagnose] = useState<VitalDiagnose | null>(null);
  const [controls, setControls] = useState<VitalControls | null>(null);
  const [integration, setIntegration] = useState<VitalIntegrationProof | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [observing, setObserving] = useState(false);
  const [hostBusy, setHostBusy] = useState(false);
  const [builtAt, setBuiltAt] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const observingRef = useRef(false);
  const refreshLock = useRef(false);
  const newestObservedAt = useRef("");
  const firstObserve = useRef(true);
  const botsRef = useRef<VitalBot[]>([]);
  botsRef.current = bots;

  const go = useCallback((next: VitalRoute, botId?: string) => {
    const id = botId || (next === "detail" ? selectedId || MLB_001 : MLB_001);
    if (botId) {
      setSelectedId(botId);
      const listed = botsRef.current.find((row) => row.bot_id === botId);
      if (listed) setBot(listed);
    }
    if (next === "detail" && !botId) setSelectedId(id);
    setRoute(next);
    window.history.replaceState({}, "", hashFor(next, next === "detail" ? id : MLB_001));
  }, [selectedId]);

  const applyRuntime = useCallback((runtime: VitalRuntime | null | undefined) => {
    if (!runtime || !shouldApplyRuntime(runtime, newestObservedAt.current)) return false;
    const stamp = runtimeObservedAt(runtime);
    if (stamp) newestObservedAt.current = stamp;
    setRuntime(runtime);
    return true;
  }, []);

  const applyDesk = useCallback((desk: Awaited<ReturnType<typeof getVitalDesk>>, surface: "list" | "full") => {
    setHealth(desk.health || null);
    setBots(desk.bots || []);
    setBankroll(desk.bankroll || null);
    setBuiltAt(desk.built_at || null);
    const focus = desk.focus;
    if (focus?.bot) setBot(focus.bot);
    if (focus?.status) setStatus(focus.status);
    applyRuntime(focus?.runtime);
    if (focus?.kalshi) setKalshi(focus.kalshi);
    if (focus?.strategy) setStrategy(focus.strategy);
    if (focus?.controls) setControls(focus.controls);
    if (focus?.integration) setIntegration(focus.integration);
    const surfaces = desk.surfaces || {};
    if (surface === "full") {
      setLogs(surfaces.logs || null);
      setParameters(surfaces.parameters || null);
      setKalshiHealth(surfaces.kalshi_health || null);
      setExecution(surfaces.execution || null);
      setEvents(surfaces.events || []);
      setOrders(surfaces.orders || null);
      setPositions(surfaces.positions || null);
      setDiagnose(surfaces.diagnose || null);
    }
    setError(null);
  }, [applyRuntime]);

  const refresh = useCallback(async (observe = false) => {
    const hashId = selectedBotFromHash();
    const target = hashId || selectedId || MLB_001;
    const listedBot = botsRef.current.find((row) => row.bot_id === target) || null;
    const focusId = route === "detail" ? target : MLB_001;
    const surface = route === "detail" || route === "live" ? "full" : "list";
    if (!refreshLock.current) {
      refreshLock.current = true;
      try {
        const desk = await getVitalDesk(focusId, surface);
        applyDesk(desk, surface);
      } finally {
        refreshLock.current = false;
      }
    }
    if (!observe || observingRef.current) return;
    observingRef.current = true;
    setObserving(true);
    try {
      if (route === "bankroll") {
        await pullBook(MLB_001, "PRODUCTION");
        const demo = botsRef.current.find((row) => row.environment === "DEMO");
        if (demo) await pullBook(demo.bot_id, "DEMO");
      } else if (route === "detail" && !isMlb001(target)) {
        await pullBook(target, bookEnvironment(listedBot));
      } else {
        await pullBook(MLB_001, "PRODUCTION");
        const demo = botsRef.current.find((row) => row.environment === "DEMO");
        if (demo && route === "home") await pullBook(demo.bot_id, "DEMO");
      }
      if (refreshLock.current) return;
      refreshLock.current = true;
      try {
        const after = await getVitalDesk(focusId, surface);
        applyDesk(after, surface);
      } finally {
        refreshLock.current = false;
      }
    } finally {
      observingRef.current = false;
      setObserving(false);
    }
  }, [applyDesk, selectedId, route]);

  useEffect(() => {
    const observe = firstObserve.current;
    firstObserve.current = false;
    void refresh(observe).catch((err) => setError(errorMessage(err)));
  }, [refresh]);

  useEffect(() => {
    const reader = window.setInterval(() => {
      void refresh(false).catch((err) => setError(errorMessage(err)));
    }, READ_MS);
    const observer = window.setInterval(() => {
      void refresh(true).catch((err) => setError(errorMessage(err)));
    }, OBSERVE_MS);
    const clock = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => {
      window.clearInterval(reader);
      window.clearInterval(observer);
      window.clearInterval(clock);
    };
  }, [refresh]);

  useEffect(() => {
    const onHash = () => {
      setRoute(routeFromHash());
      const id = selectedBotFromHash();
      if (id) setSelectedId(id);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement
      ) {
        return;
      }
      if (event.key === "1") go("home");
      if (event.key === "2") go("live");
      if (event.key === "3") go("bots");
      if (event.key === "4") go("detail", selectedId || MLB_001);
      if (event.key === "5") go("bankroll");
      if (event.key === "r" || event.key === "R") void refresh(false).catch((err) => setError(errorMessage(err)));
      if (event.key === "o" || event.key === "O") void refresh(true).catch((err) => setError(errorMessage(err)));
      if (event.key === "[" || event.key === "]") {
        const ranked = sortBots(botsRef.current);
        if (!ranked.length) return;
        const index = Math.max(0, ranked.findIndex((row) => row.bot_id === selectedId));
        const next =
          event.key === "]"
            ? ranked[(index + 1) % ranked.length]
            : ranked[(index - 1 + ranked.length) % ranked.length];
        go("detail", next.bot_id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, refresh, selectedId]);

  const refreshHost = useCallback(async () => {
    const target = selectedBotFromHash() || selectedId || MLB_001;
    setHostBusy(true);
    try {
      const observed = await observeVitalHost(isMlb001(target) ? MLB_001 : target);
      applyRuntime(observed.runtime);
      await refresh(false);
    } finally {
      setHostBusy(false);
    }
  }, [applyRuntime, refresh, selectedId]);

  const detailIsMlb = isMlb001(selectedId);
  const listedSelected = bots.find((row) => row.bot_id === selectedId) || null;
  const detailBot = detailIsMlb ? bot : listedSelected || bot;
  const focusLifecycle = status?.lifecycle || listedSelected?.activation || "OBSERVATION_UNAVAILABLE";
  const prodSports = moneyText(bankroll?.account?.mlb_shard_cents);
  const demoSports = moneyText(bankroll?.demo_account?.mlb_shard_cents);
  const observeAge = ageText(
    (bankroll?.account?.observed_at?.status === "CONFIRMED"
      ? String(bankroll.account.observed_at.value || "")
      : kalshi?.observed_at) || builtAt,
    nowMs,
  );

  return (
    <div className="app-root ws-app sa-app ju-app vital-shell">
      <header className="ws-header">
        <button
          type="button"
          className="mm-masthead-brand"
          onClick={() => go("home")}
          aria-label="Vital — desk"
        >
          <img className="mm-mark" src="/brand/momento-m-mark.png" alt="" width={26} height={26} decoding="async" />
          <span className="mm-wordmark">
            <span className="mm-wordmark-product">Vital</span>
            <span className="mm-wordmark-rule" aria-hidden />
            <span className="mm-wordmark-sub">Execution</span>
          </span>
        </button>
        <div className="mm-status-strip">
          <div className="mm-status-item">
            <span className="mm-status-key">Unit</span>
            <span className={`mm-status-value ${toneForLifecycle(focusLifecycle)}`}>{focusLifecycle}</span>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Service</span>
            <span className="mm-status-value">
              {runtime?.service?.status === "CONFIRMED" && runtime.service.value && typeof runtime.service.value === "object"
                ? String((runtime.service.value as { active?: string }).active || "UNREAD")
                : "UNREAD"}
            </span>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Prod 3</span>
            <span className="mm-status-value is-strong">{prodSports}</span>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Demo 3</span>
            <span className="mm-status-value is-strong">{demoSports}</span>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Kalshi</span>
            <span className="mm-status-value">{observing ? "OBSERVING" : kalshi?.status || "UNREAD"}</span>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Age</span>
            <span className="mm-status-value">{observeAge}</span>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Browser</span>
            <span className="mm-status-value">NO SUBMIT</span>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Research</span>
            <button type="button" className="mm-status-value" onClick={openSuperASI}>
              SUPERASI
            </button>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Client</span>
            <button type="button" className="mm-status-value" onClick={openJump}>
              JUMP
            </button>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Measure</span>
            <button type="button" className="mm-status-value" onClick={openRoller}>
              ROLLER
            </button>
          </div>
        </div>
      </header>

      <div className="ws-body">
        <VitalSpine
          route={route}
          botId={route === "detail" ? selectedId : MLB_001}
          sport={sportLabel(route === "detail" ? detailBot : bots.find((row) => row.bot_id === MLB_001) || bot)}
          lifecycle={focusLifecycle}
          health={status?.health || "UNKNOWN"}
          onNavigate={(next) => go(next, next === "detail" ? selectedId || MLB_001 : undefined)}
        />
        <div className="ws-main-col">
          <div className="ws-main-scroll sa-body">
            {route === "live" ? (
              <LiveObservatory
                status={status}
                runtime={runtime}
                logs={logs}
                execution={execution}
                diagnose={diagnose}
                integration={integration}
                error={error}
                hostBusy={hostBusy}
                nowMs={nowMs}
                onRefreshHost={() => void refreshHost().catch((err) => setError(errorMessage(err)))}
              />
            ) : null}
            {route === "home" ? (
              <Home
                health={health}
                status={status}
                runtime={runtime}
                bots={bots}
                bankroll={bankroll}
                kalshi={kalshi}
                strategy={strategy}
                error={error}
                observing={observing}
                hostBusy={hostBusy}
                builtAt={builtAt}
                controls={controls}
                integration={integration}
                onOpenBots={() => go("bots")}
                onOpenDetail={(botId) => go("detail", botId || MLB_001)}
                onRefreshHost={() => void refreshHost().catch((err) => setError(errorMessage(err)))}
              />
            ) : null}
            {route === "bots" ? (
              <Bots
                bots={bots}
                error={error}
                selectedId={selectedId}
                onOpenDetail={(botId) => go("detail", botId)}
              />
            ) : null}
            {route === "bankroll" ? (
              <Bankroll
                bankroll={bankroll}
                error={error}
                onError={setError}
                onRefresh={() => void refresh(false).catch((err) => setError(errorMessage(err)))}
              />
            ) : null}
            {route === "detail" && detailIsMlb ? (
              <BotDetail
                bot={bot}
                status={status}
                runtime={runtime}
                logs={logs}
                parameters={parameters}
                kalshiHealth={kalshiHealth}
                events={events}
                orders={orders}
                positions={positions}
                execution={execution}
                bankroll={bankroll}
                kalshi={kalshi}
                strategy={strategy}
                diagnose={diagnose}
                controls={controls}
                integration={integration}
                error={error}
                onError={setError}
                onRefresh={() => void refresh(true).catch((err) => setError(errorMessage(err)))}
              />
            ) : null}
            {route === "detail" && !detailIsMlb ? (
              <ItiBotDetail
                bot={detailBot}
                status={status}
                runtime={runtime}
                logs={logs}
                parameters={parameters}
                kalshiHealth={kalshiHealth}
                execution={execution}
                bankroll={bankroll}
                kalshi={kalshi}
                strategy={strategy}
                integration={integration}
                error={error}
                onError={setError}
                onRefresh={() => void refresh(true).catch((err) => setError(errorMessage(err)))}
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
