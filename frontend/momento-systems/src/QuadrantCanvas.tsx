import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { BOXES, EDGES, FRAME, LOCK_BOXES, center } from "./layout";
import RunningList from "./RunningList";
import PnlBoard from "./PnlBoard";
import SeasonBanner from "./SeasonBanner";
import SideDiamonds, { DiamondEditor, loadDiamonds, saveDiamonds, type DiamondSide, type DiamondStore } from "./SideDiamonds";
import type { BoxGeom } from "./layout";
import type { SystemRow } from "./types";

type Instance = {
  instance_id: string;
  quadrant_id: string;
  system_type: string;
  label: string;
  interactive: string;
};

type NodeRow = {
  node_id: string;
  instance_id: string;
  geometry_key: string;
  label_override: string;
};

type Quadrant = {
  quadrant_id: string;
  sport: string;
  heading: string;
  position: string;
};

type Topology = {
  status: string;
  quadrants: Quadrant[];
  instances: Instance[];
  nodes: NodeRow[];
};

type Props = {
  systems: SystemRow[];
  onBackend: (id: string) => void;
  onFrontend: (row: SystemRow) => void;
  onExecution: (quadrantId: string) => void;
  focus?: "all" | "nba-ncaab";
  lockedQuadrant?: string | null;
};

const ORDER = ["quad-1", "quad-2", "quad-4", "quad-3"];
const FIT_LABEL: Record<string, string> = {
  "quad-1": "Fit NBA",
  "quad-2": "Fit NCAAB",
  "quad-3": "Fit WNBA",
  "quad-4": "Fit MLB",
};
const QUAD_TITLE: Record<string, string> = {
  "quad-1": "NBA Momento Systems",
  "quad-2": "NCAAB Momento Systems",
  "quad-3": "WNBA Momento Systems",
  "quad-4": "MLB Momento Systems",
};
const INFRA = new Set([
  "system_maintenance",
  "data_ingestion",
  "trade_reconciliation",
  "system_orchestration",
]);
const COMING_SOON = new Set(["game_modeling"]);
const FONT_FAMILY = 'Menlo, Monaco, Consolas, "Courier New", monospace';

function lockedFromHash(): string | null {
  const match = window.location.hash.match(/^#\/quad\/(quad-[1-4])$/);
  return match ? match[1] : null;
}

function estimateFrame(locked: boolean): { w: number; h: number } {
  if (typeof window === "undefined") return { w: FRAME.w, h: FRAME.h };
  const vh = window.innerHeight;
  const vw = window.innerWidth;
  const grid = locked
    ? Math.min(vw - 32, ((vh - 140) * FRAME.w) / FRAME.h)
    : Math.min(vw - 32, ((vh - 300) * FRAME.w) / FRAME.h + 32);
  const w = locked ? grid - 32 : (grid - 32 - 16) / 2;
  return { w: Math.max(1, w), h: Math.max(1, (w * FRAME.h) / FRAME.w) };
}

let measureCtx: CanvasRenderingContext2D | null = null;

function textWidth(text: string, fontPx: number): number {
  if (typeof document === "undefined") return text.length * fontPx * 0.62;
  if (!measureCtx) measureCtx = document.createElement("canvas").getContext("2d");
  if (!measureCtx) return text.length * fontPx * 0.62;
  measureCtx.font = `${fontPx}px ${FONT_FAMILY}`;
  return measureCtx.measureText(text).width;
}

function boxTitle(quadrantId: string, inst: Instance, node: NodeRow, system: SystemRow | undefined): string {
  if (quadrantId === "quad-1" && inst.system_type === "momento_systems") return "NBA North";
  return node.label_override || (quadrantId === "quad-1" ? system?.short_name || system?.display_name || inst.label : inst.label);
}

const PAIR_WIDTH = 276;

function railOverlaps(side: number): boolean {
  const inset = Math.max(16, side / 2 - 138);
  const frameLeft = side + 16;
  const pairRight = inset + PAIR_WIDTH;
  const widgetRight = 18 + Math.max(160, side - 36);
  return pairRight > frameLeft - 12 || widgetRight > frameLeft - 12;
}

function labelFontPx(boxW: number, boxH: number, title: string, extra?: string, cap = 22): number {
  const innerW = Math.max(8, boxW - 8);
  const innerH = Math.max(8, boxH - 4);
  const lineCount = extra ? 2.12 : 1.08;
  let lo = 4;
  let hi = Math.min(innerH / (extra ? 1.9 : 1.02), cap);
  for (let i = 0; i < 14; i += 1) {
    const mid = (lo + hi) / 2;
    const titleFits = textWidth(title, mid) <= innerW;
    const extraFits = extra ? textWidth(extra, mid * 0.78) <= innerW : true;
    const heightFits = mid * lineCount <= innerH;
    if (titleFits && extraFits && heightFits) lo = mid;
    else hi = mid;
  }
  return Math.floor(lo * 10) / 10;
}

export default function QuadrantCanvas({ systems, onBackend, onFrontend, onExecution, focus = "all", lockedQuadrant }: Props) {
  const [topology, setTopology] = useState<Topology | null>(null);
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState("");
  const [picked, setPicked] = useState<SystemRow | null>(null);
  const [running, setRunning] = useState(false);
  const [runLine, setRunLine] = useState("");
  const [hashLocked, setHashLocked] = useState<string | null>(lockedFromHash);
  const locked = lockedQuadrant === undefined ? hashLocked : lockedQuadrant;
  const [enlarged, setEnlarged] = useState<"list" | "pnl" | null>(null);
  const [editorSide, setEditorSide] = useState<DiamondSide | null>(null);
  const [diamonds, setDiamonds] = useState<DiamondStore>(loadDiamonds);
  const [framePx, setFramePx] = useState(() => estimateFrame(lockedFromHash() !== null));
  const [docked, setDocked] = useState(() => {
    if (typeof document === "undefined") return false;
    const width = document.documentElement.clientWidth;
    const height = document.documentElement.clientHeight;
    const grid = Math.min(width, ((height - 300) * FRAME.w) / FRAME.h + 32);
    return railOverlaps((width - grid) / 2);
  });
  const frameRef = useRef<HTMLDivElement | null>(null);
  const boardRef = useRef<HTMLDivElement | null>(null);
  const gridRef = useRef<HTMLDivElement | null>(null);
  const byId = useMemo(() => new Map(systems.map((row) => [row.id, row])), [systems]);

  useEffect(() => {
    const apply = () => {
      const id = lockedQuadrant === undefined ? lockedFromHash() : lockedQuadrant;
      if (lockedQuadrant === undefined) setHashLocked(id);
      if (id) {
        setEnlarged(null);
        setEditorSide(null);
      }
      document.title = id ? `${QUAD_TITLE[id] ?? "Momento Systems"}${focus === "nba-ncaab" ? " · 78/67" : ""}` : focus === "nba-ncaab" ? "78/67 bball" : "Momento Systems";
    };
    apply();
    window.addEventListener("hashchange", apply);
    return () => window.removeEventListener("hashchange", apply);
  }, [focus, lockedQuadrant]);

  useLayoutEffect(() => {
    const apply = () => {
      const el = frameRef.current;
      const next = el && el.offsetWidth > 1 ? { w: el.offsetWidth, h: el.offsetHeight } : estimateFrame(locked !== null);
      setFramePx((prev) => (Math.abs(prev.w - next.w) < 0.5 && Math.abs(prev.h - next.h) < 0.5 ? prev : next));
    };
    apply();
    const observer = new ResizeObserver(apply);
    if (frameRef.current) observer.observe(frameRef.current);
    window.addEventListener("resize", apply);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", apply);
    };
  }, [locked, zoom, topology]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/systimo/topology")
      .then(async (response) => {
        if (!response.ok) throw new Error(`topology ${response.status}`);
        return (await response.json()) as Topology;
      })
      .then((body) => {
        if (!cancelled) setTopology(body);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function systimoRun() {
    setRunning(true);
    setError("");
    setRunLine("");
    try {
      const response = await fetch("/api/systimo/run", { method: "POST" });
      const body = (await response.json()) as {
        detail?: { message?: string };
        results?: Array<{ service_id: string; port: number; state: string }>;
      };
      if (!response.ok) {
        throw new Error(body.detail?.message || `run ${response.status}`);
      }
      const results = body.results ?? [];
      setRunLine(results.map((row) => `${row.service_id} :${row.port} ${row.state}`).join(" · "));
      const failed = results.filter((row) => row.state === "failed" || row.state === "occupied");
      if (failed.length) {
        setError(failed.map((row) => `${row.service_id} :${row.port} ${row.state}`).join(" · "));
      }
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setRunning(false);
    }
  }

  const quadrants = topology?.quadrants ?? [];
  const instances = topology?.instances ?? [];
  const nodes = topology?.nodes ?? [];

  const zoomButton = { whiteSpace: "nowrap" as const, flexShrink: 0, color: "#c8c4bc" };
  const labelFonts = useMemo(() => {
    const ordinary: number[] = [];
    const infra: number[] = [];
    const north: number[] = [];
    const geoms = locked ? LOCK_BOXES : BOXES;
    for (const quadrantId of locked ? [locked] : ORDER) {
      for (const node of nodes) {
        const inst = instances.find((row) => row.instance_id === node.instance_id);
        const geom = geoms[node.geometry_key];
        if (!inst || inst.quadrant_id !== quadrantId || !geom) continue;
        const title = boxTitle(quadrantId, inst, node, byId.get(inst.system_type));
        if (!title) continue;
        const soon = quadrantId === "quad-1" && COMING_SOON.has(inst.system_type) ? "coming soon" : undefined;
        const width = (geom.w / FRAME.w) * framePx.w;
        const height = (geom.h / FRAME.h) * framePx.h;
        if (locked && node.geometry_key === "momento_systems") north.push(labelFontPx(width, height, title, soon, 36));
        else if (locked && INFRA.has(node.geometry_key)) infra.push(labelFontPx(width, height, title, soon, 36));
        else ordinary.push(labelFontPx(width, height, title, soon, 22));
      }
    }
    const shared = (sizes: number[]) => (sizes.length ? Math.min(...sizes) : 9);
    return { ordinary: shared(ordinary), infra: shared(infra), north: shared(north) };
  }, [locked, nodes, instances, byId, framePx]);
  const shown = locked ? [locked] : focus === "nba-ncaab" ? ["quad-1", "quad-2"] : ORDER;
  const boardHidden = (enlarged || editorSide !== null) && !locked;
  const railDocked = docked && !locked;

  useLayoutEffect(() => {
    if (locked || boardHidden) return;
    const measure = () => {
      const board = boardRef.current;
      const grid = gridRef.current;
      if (!board || !grid || grid.offsetWidth === 0) return;
      setDocked(railOverlaps((board.clientWidth - grid.offsetWidth) / 2));
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (boardRef.current) observer.observe(boardRef.current);
    if (gridRef.current) observer.observe(gridRef.current);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [locked, boardHidden]);
  const boxes: Record<string, BoxGeom> = locked ? LOCK_BOXES : BOXES;
  const measureId = locked ?? "quad-1";

  return (
    <div style={{ background: "#111", color: "#e8e8e8", height: "100dvh", overflowX: "hidden", overflowY: railDocked && !boardHidden ? "auto" : "hidden", display: "flex", flexDirection: "column", fontFamily: "Menlo, monospace" }}>
      <header style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "flex-end", flexShrink: 0, minHeight: 72, padding: "12px 16px" }}>
        <div style={{ position: "absolute", left: 16, display: "flex", gap: 8, zIndex: 1 }}>
          <button type="button" style={zoomButton} onClick={() => { if (editorSide) setEditorSide(null); else if (enlarged) setEnlarged(null); else window.history.back(); }}>Back</button>
          <button type="button" style={zoomButton} onClick={() => { setEditorSide(null); setEnlarged(null); window.location.hash = "/"; }}>Home</button>
        </div>
        {boardHidden ? null : <button
          type="button"
          disabled={running}
          onClick={() => void systimoRun()}
          style={{
            position: "absolute",
            left: "50%",
            transform: "translateX(-50%)",
            background: "#6d675e",
            color: "#d5d0c8",
            border: "none",
            borderRadius: 14,
            padding: "16px 36px",
            fontSize: 18,
            fontWeight: 700,
            letterSpacing: "0.14em",
            whiteSpace: "nowrap",
            cursor: running ? "wait" : "pointer",
            boxShadow: "none",
          }}
        >
          {running ? "STARTING" : "SYSTIMO RUN"}
        </button>}
        {boardHidden ? null : <div style={{ display: "flex", flexWrap: "nowrap", flexShrink: 0, gap: 8, whiteSpace: "nowrap" }}>
          <button type="button" style={zoomButton} onClick={() => setZoom((value) => Math.max(0.4, value - 0.1))}>−</button>
          <button type="button" style={zoomButton} onClick={() => setZoom((value) => Math.min(2, value + 0.1))}>+</button>
          <button type="button" style={zoomButton} onClick={() => { setZoom(1); window.location.hash = focus === "nba-ncaab" ? "/bball-7867" : "/"; }}>Fit All</button>
          {(focus === "nba-ncaab" ? ["quad-1", "quad-2"] : ["quad-1", "quad-2", "quad-3", "quad-4"]).map((quadrantId) => (
            <button
              key={quadrantId}
              type="button"
              style={zoomButton}
              onClick={() => {
                window.location.hash = focus === "nba-ncaab"
                  ? `/bball-7867/${quadrantId === "quad-1" ? "nba" : "ncaab"}`
                  : `/quad/${quadrantId}`;
              }}
            >
              {FIT_LABEL[quadrantId]}
            </button>
          ))}
        </div>}
      </header>
      {enlarged === "list" && !locked && !editorSide ? <RunningList enlarged /> : null}
      {enlarged === "pnl" && !locked && !editorSide ? <PnlBoard enlarged /> : null}
      {editorSide && !locked ? (
        <DiamondEditor
          side={editorSide}
          onSave={(slot) => {
            const list = diamonds[editorSide];
            if (list.length >= 4) {
              setEditorSide(null);
              return;
            }
            const next = { ...diamonds, [editorSide]: [...list, slot] };
            setDiamonds(next);
            saveDiamonds(next);
            setEditorSide(null);
          }}
        />
      ) : null}
      {boardHidden ? null : <br />}
      {boardHidden ? null : runLine ? <p style={{ textAlign: "center", margin: "0 16px 8px" }}>{runLine}</p> : null}
      {boardHidden ? null : error ? <p style={{ padding: "0 16px", textAlign: "center" }}>{error}</p> : null}
      {boardHidden ? null : topology?.status === "PRE_V1" ? <p style={{ padding: "0 16px" }}>PRE_V1</p> : null}
      {boardHidden || focus !== "nba-ncaab" ? null : <SeasonBanner />}
      <div ref={boardRef} style={{ position: "relative", flex: "0 0 auto", display: boardHidden ? "none" : undefined }}>
      <div ref={gridRef} style={{ display: "grid", gridTemplateColumns: locked ? "1fr" : "1fr 1fr", gap: locked ? 16 : 28, padding: "0 16px", boxSizing: "border-box", width: locked ? `min(100%, calc((100dvh - 140px) * ${FRAME.w} / ${FRAME.h}))` : `min(100%, calc((100dvh - 300px) * ${FRAME.w} / ${FRAME.h} + 32px))`, margin: "0 auto", flex: "0 0 auto", transform: `scale(${zoom})`, transformOrigin: "top left" }}>
        {shown.map((quadrantId) => {
          const quad = quadrants.find((row) => row.quadrant_id === quadrantId);
          return (
            <section key={quadrantId} aria-label={quad?.heading ?? quadrantId}>
              <h2 style={{ fontSize: 14, textAlign: "center", margin: "0 0 22px" }}>
                {focus === "nba-ncaab" ? `${quad?.sport ?? quadrantId} · 78/67` : quad?.heading ?? quadrantId}
              </h2>
              <div
                ref={quadrantId === measureId ? frameRef : undefined}
                style={{ position: "relative", width: "100%", aspectRatio: `${FRAME.w} / ${FRAME.h}`, background: "#1b1b1b" }}
              >
                <svg className="wires" viewBox={`0 0 ${FRAME.w} ${FRAME.h}`} style={{ pointerEvents: "none" }} aria-hidden="true">
                  {EDGES.map(([source, target]) => {
                    const a = center(boxes[source]);
                    const b = center(boxes[target]);
                    const mirrored = quadrantId === "quad-2" || quadrantId === "quad-3";
                    const x1 = mirrored ? FRAME.w - a.x : a.x;
                    const x2 = mirrored ? FRAME.w - b.x : b.x;
                    return <line key={`${source}-${target}`} x1={x1} y1={a.y} x2={x2} y2={b.y} stroke="currentColor" strokeWidth={1} />;
                  })}
                </svg>
                {nodes
                  .filter((node) => instances.find((row) => row.instance_id === node.instance_id)?.quadrant_id === quadrantId)
                  .map((node) => {
                    const inst = instances.find((row) => row.instance_id === node.instance_id);
                    const geom = boxes[node.geometry_key];
                    if (!inst || !geom) return null;
                    const mirrored = (quadrantId === "quad-2" || quadrantId === "quad-3") && !(locked && INFRA.has(node.geometry_key));
                    const x = mirrored ? FRAME.w - geom.x - geom.w : geom.x;
                    const system = byId.get(inst.system_type);
                    const title = boxTitle(quadrantId, inst, node, system);
                    const closed = inst.interactive !== "true";
                    const soon = quadrantId === "quad-1" && COMING_SOON.has(inst.system_type);
                    const fontPx = !title
                      ? 9
                      : locked && node.geometry_key === "momento_systems"
                        ? labelFonts.north
                        : locked && INFRA.has(node.geometry_key)
                          ? labelFonts.infra
                          : labelFonts.ordinary;
                    return (
                      <button
                        key={node.node_id}
                        type="button"
                        className={`${soon ? "box box-soon box-has-sub" : "box"}${title ? "" : ""}`}
                        disabled={closed}
                        aria-label={title || inst.system_type}
                        style={{
                          left: `${(x / FRAME.w) * 100}%`,
                          top: `${(geom.y / FRAME.h) * 100}%`,
                          width: `${(geom.w / FRAME.w) * 100}%`,
                          height: `${(geom.h / FRAME.h) * 100}%`,
                          fontSize: fontPx,
                          color: "#c8c4bc",
                          cursor: closed ? "default" : "pointer",
                        }}
                        onClick={() => {
                          if (closed) return;
                          if (inst.system_type === "algorithmic_execution") {
                            onExecution(quadrantId);
                            return;
                          }
                          if (quadrantId === "quad-1" && system) setPicked(system);
                        }}
                      >
                        {title ? (
                          <span className="box-label">
                            {title}
                            {soon ? <small>coming soon</small> : null}
                          </span>
                        ) : null}
                      </button>
                    );
                  })}
              </div>
            </section>
          );
        })}
      </div>
      {locked ? null : (
        <div
          style={
            railDocked
              ? {
                  width: `min(100%, calc((100dvh - 300px) * ${FRAME.w} / ${FRAME.h} + 32px))`,
                  margin: "18px auto 0",
                  padding: "0 16px 8px",
                  boxSizing: "border-box",
                  display: "flex",
                  flexDirection: "column",
                  gap: 16,
                }
              : undefined
          }
        >
          {enlarged === "list" ? null : <RunningList docked={railDocked} onEnlarge={() => setEnlarged("list")} />}
          <PnlBoard docked={railDocked} onEnlarge={() => setEnlarged("pnl")} />
          <SideDiamonds docked={railDocked} slots={diamonds} onEdit={setEditorSide} />
        </div>
      )}
      </div>
      {locked || boardHidden ? null : <section style={{ display: "flex", flexShrink: 0, gap: 12, justifyContent: "center", padding: 16 }}>
        {instances
          .filter((row) => row.quadrant_id === "global")
          .map((row) => (
            <button
              key={row.instance_id}
              type="button"
              style={{ color: "#c8c4bc" }}
              onClick={() => {
                if (row.system_type === "data_ingestion") window.location.hash = "/ingest";
                else if (row.system_type === "trade_reconciliation") window.location.hash = "/reconciliation";
                else if (row.system_type === "system_orchestration") window.location.hash = "/orchestra";
                else {
                  void fetch("/api/systimo/scope/sessions", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ source_node_id: `node:${row.instance_id}` }),
                  })
                    .then((response) => response.json())
                    .then((session: { session_id?: string }) => {
                      if (!session.session_id) return;
                      sessionStorage.setItem("momento_scope", session.session_id);
                      return fetch(`/api/systimo/runtime/endpoints?session_id=${session.session_id}`);
                    })
                    .then((response) => (response ? response.json() : null))
                    .then((body: { endpoints?: Array<{ service_id: string; port?: number; bound?: boolean }> } | null) => {
                      const desk = body?.endpoints?.find((item) => item.service_id === "systimo-ui" && item.bound && item.port);
                      if (!desk?.port) {
                        setError("systimo-ui UNAVAILABLE");
                        return;
                      }
                      window.open(`http://127.0.0.1:${desk.port}/`, "_blank", "noopener,noreferrer");
                    })
                    .catch((exc: Error) => setError(exc.message));
                }
              }}
            >
              {row.label}
            </button>
          ))}
      </section>}
      <div style={{ flex: boardHidden ? "0 0 0" : "1 1 auto" }} />
      {picked ? (
        <div className="modal-back" onClick={() => setPicked(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h2>{picked.display_name}</h2>
            {COMING_SOON.has(picked.id) ? (
              <p>Coming soon. LIVE EXECUTION = FALSE.</p>
            ) : (
              <>
                <button type="button" onClick={() => onBackend(picked.id)}>Backend</button>
                <button type="button" onClick={() => onFrontend(picked)}>
                  {picked.frontend_target?.product && picked.frontend_target.product !== "Momento"
                    ? picked.frontend_target.product
                    : "Frontend"}
                </button>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
