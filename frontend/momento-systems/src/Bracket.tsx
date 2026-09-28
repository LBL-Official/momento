import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { Desk } from "./Desk";
import { BOXES, EDGES, FRAME, center } from "./layout";
import type { ConnectionPayload, SystemRow } from "./types";

type Props = {
  systems: SystemRow[];
  connection: ConnectionPayload | null;
  onBackend: (id: string) => void;
  onFrontend: (row: SystemRow) => void;
};

const FONT_FAMILY = 'Menlo, Monaco, Consolas, "Courier New", monospace';

const COMING_SOON = new Set([
  "game_modeling",
  "algorithmic_execution",
]);

let measureCtx: CanvasRenderingContext2D | null = null;

function textWidth(text: string, fontPx: number): number {
  if (typeof document === "undefined") return text.length * fontPx * 0.62;
  if (!measureCtx) {
    const canvas = document.createElement("canvas");
    measureCtx = canvas.getContext("2d");
  }
  if (!measureCtx) return text.length * fontPx * 0.62;
  measureCtx.font = `${fontPx}px ${FONT_FAMILY}`;
  return measureCtx.measureText(text).width;
}

function subtitle(row: SystemRow): string | undefined {
  return row.visual_subtitle || row.extra?.visual_subtitle || undefined;
}

function labelFontPx(boxW: number, boxH: number, title: string, extra?: string): number {
  const innerW = Math.max(8, boxW - 12);
  const innerH = Math.max(8, boxH - 6);
  const lineCount = extra ? 2.12 : 1.08;
  let lo = 4;
  let hi = Math.min(innerH / (extra ? 1.9 : 1.02), 22);
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

export default function Bracket({ systems, connection, onBackend, onFrontend }: Props) {
  const byId = useMemo(() => Object.fromEntries(systems.map((row) => [row.id, row])), [systems]);
  const [openId, setOpenId] = useState<string | null>(null);
  const open = openId ? byId[openId] : null;
  const stageRef = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState({ w: FRAME.w, h: FRAME.h });

  useLayoutEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const apply = () => {
      const w = el.clientWidth;
      const h = Math.min(
        el.clientHeight,
        Math.max(0, window.innerHeight - el.getBoundingClientRect().top - 8),
      );
      if (w < 1 || h < 1) return;
      const scale = Math.min(w / FRAME.w, h / FRAME.h);
      const next = { w: FRAME.w * scale, h: FRAME.h * scale };
      setFit((prev) =>
        Math.abs(prev.w - next.w) < 0.5 && Math.abs(prev.h - next.h) < 0.5 ? prev : next,
      );
    };
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    window.addEventListener("resize", apply);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", apply);
    };
  }, []);

  const scale = fit.w / FRAME.w;
  const fontPx = useMemo(() => {
    let shared = 22;
    for (const row of systems) {
      const box = BOXES[row.id];
      if (!box) continue;
      shared = Math.min(
        shared,
        labelFontPx(box.w * scale, box.h * scale, row.short_name, subtitle(row)),
      );
    }
    return Math.max(4, shared - 0.3);
  }, [systems, scale]);

  const nba = connection?.markets.nba.query;
  const ncaab = connection?.markets.ncaab.query;
  const roller = connection?.roller.status || "CONNECTED";

  return (
    <Desk kicker="Momento systems · 19-system bracket" title="Momento Systems" active="bracket">
    <div className="conn-strip">
      <span className={`pill ${roller === "CONNECTED" ? "is-ok" : "is-idle"}`}>ROLLER {roller}</span>
      <span className={`pill ${nba === "OK" ? "is-ok" : "is-idle"}`}>NBA query {nba || "UNAVAILABLE"}</span>
      <span className={`pill ${ncaab === "OK" ? "is-ok" : "is-idle"}`}>NCAAB query {ncaab || "UNAVAILABLE"}</span>
    </div>
    <div className="stage" ref={stageRef}>
      <div className="frame" style={{ width: fit.w, height: fit.h }}>
        <svg className="wires" viewBox={`0 0 ${FRAME.w} ${FRAME.h}`} aria-hidden="true">
          {EDGES.map(([src, dst]) => {
            const a = BOXES[src];
            const b = BOXES[dst];
            if (!a || !b) return null;
            const p = center(a);
            const q = center(b);
            return (
              <line
                key={`${src}-${dst}`}
                x1={p.x}
                y1={p.y}
                x2={q.x}
                y2={q.y}
                stroke="currentColor"
                strokeWidth="1"
              />
            );
          })}
        </svg>
        {systems.map((row) => {
          const box = BOXES[row.id];
          if (!box) return null;
          const extra = COMING_SOON.has(row.id) ? "coming soon" : subtitle(row);
          return (
            <button
              key={row.id}
              type="button"
              className={`${extra ? "box box-has-sub" : "box"}${COMING_SOON.has(row.id) ? " box-soon" : ""}`}
              style={{
                left: `${(box.x / FRAME.w) * 100}%`,
                top: `${(box.y / FRAME.h) * 100}%`,
                width: `${(box.w / FRAME.w) * 100}%`,
                height: `${(box.h / FRAME.h) * 100}%`,
                fontSize: `${fontPx}px`,
              }}
              onClick={() => setOpenId(row.id)}
            >
              <span className="box-label">
                {row.short_name}
                {extra ? <small>{extra}</small> : null}
              </span>
            </button>
          );
        })}
      </div>
      {open ? (
        <div className="modal-back" onClick={() => setOpenId(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h2>{open.display_name}</h2>
            {COMING_SOON.has(open.id) ? (
              <p>Coming soon. This bracket stays a placeholder. LIVE EXECUTION = FALSE.</p>
            ) : (
              <>
                <button type="button" onClick={() => onBackend(open.id)}>
                  Backend
                </button>
                <button type="button" onClick={() => onFrontend(open)}>
                  {open.frontend_target?.product && open.frontend_target.product !== "Momento"
                    ? open.frontend_target.product
                    : "Frontend"}
                </button>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
    </Desk>
  );
}
