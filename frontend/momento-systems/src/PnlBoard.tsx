import { FRAME } from "./layout";

const INK = "#c8c4bc";
const NAVY = "#14161b";
const LINE = "#2a2e36";
const MUTED = "#8b8f98";
const ROWS = ["NBA", "NCAAB", "WNBA", "MLB", "propino", "120 Desk"];
const COLS = ["Day", "Week", "Sharpe day", "Sharpe week"];
const PLACEHOLDER = 0;

const STOP_0: [number, number, number] = [196, 164, 164];
const STOP_50: [number, number, number] = [138, 122, 122];
const STOP_1: [number, number, number] = [154, 184, 166];

function mix(a: [number, number, number], b: [number, number, number], t: number): string {
  const c = a.map((channel, i) => Math.round(channel + (b[i] - channel) * t));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

function tileFill(value: number): string {
  const t = Math.min(1, Math.max(0, value));
  if (t <= 0.5) return mix(STOP_0, STOP_50, t / 0.5);
  return mix(STOP_50, STOP_1, (t - 0.5) / 0.5);
}

function formatScore(value: number): string {
  const t = Math.min(1, Math.max(0, value));
  return t.toFixed(2);
}

type Props = {
  enlarged?: boolean;
  docked?: boolean;
  onEnlarge?: () => void;
};

function Tile({ large }: { large: boolean }) {
  return (
    <span
      style={
        large
          ? {
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              maxHeight: "100%",
              aspectRatio: "1",
              maxWidth: "100%",
              boxSizing: "border-box",
              borderRadius: 8,
              background: tileFill(PLACEHOLDER),
              color: NAVY,
              fontSize: "clamp(14px, 2.4vh, 32px)",
              fontWeight: 500,
            }
          : {
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 26,
              height: 26,
              boxSizing: "border-box",
              borderRadius: 3,
              background: tileFill(PLACEHOLDER),
              color: NAVY,
              fontSize: 8,
              fontWeight: 500,
            }
      }
    >
      {formatScore(PLACEHOLDER)}
    </span>
  );
}

export default function PnlBoard({ enlarged = false, docked = false, onEnlarge }: Props) {
  const gutter = `max(160px, calc((100% - min(100%, (100dvh - 300px) * ${FRAME.w} / ${FRAME.h} + 32px)) / 2 - 36px))`;

  return (
    <section
      aria-label="P&L"
      style={
        enlarged
          ? {
              flex: "1 1 auto",
              minHeight: 0,
              margin: "0 24px 24px",
              zIndex: 1,
              boxSizing: "border-box",
              background: NAVY,
              color: INK,
              border: `1px solid ${LINE}`,
              display: "flex",
              flexDirection: "column",
              padding: "28px 32px 20px",
              overflow: "hidden",
            }
          : docked
            ? {
                position: "relative",
                width: "100%",
                boxSizing: "border-box",
                background: NAVY,
                color: INK,
                border: `1px solid ${LINE}`,
                display: "flex",
                flexDirection: "column",
                padding: "14px 14px 12px",
                overflow: "hidden",
              }
            : {
                position: "absolute",
                right: 18,
                top: 0,
                bottom: "calc(50% + 158px)",
                width: gutter,
                zIndex: 1,
                boxSizing: "border-box",
                background: NAVY,
                color: INK,
                border: `1px solid ${LINE}`,
                display: "flex",
                flexDirection: "column",
                padding: "14px 14px 12px",
                minHeight: 0,
                overflow: "hidden",
              }
      }
    >
      {enlarged ? null : (
        <button
          type="button"
          onClick={onEnlarge}
          style={{
            alignSelf: "flex-start",
            flex: "0 0 auto",
            marginBottom: 8,
            background: "#1c2230",
            color: INK,
            border: `1px solid ${LINE}`,
            borderRadius: 8,
            padding: "4px 8px",
            font: "inherit",
            fontSize: 11,
            letterSpacing: "0.06em",
            cursor: "pointer",
          }}
        >
          Enlarge
        </button>
      )}
      {enlarged ? (
        <div
          style={{
            flex: "1 1 auto",
            minHeight: 0,
            display: "grid",
            gridTemplateColumns: "minmax(88px, 160px) repeat(4, minmax(0, 1fr))",
            gridTemplateRows: "auto repeat(6, minmax(0, 1fr))",
            gap: 10,
          }}
        >
          <span />
          {COLS.map((col) => (
            <span key={col} style={{ textAlign: "center", color: MUTED, fontSize: 13, letterSpacing: "0.04em" }}>
              {col}
            </span>
          ))}
          {ROWS.map((row) => (
            <div key={row} style={{ display: "contents" }}>
              <span style={{ alignSelf: "center", fontSize: 16 }}>{row}</span>
              {COLS.map((col) => (
                <div key={col} style={{ minWidth: 0, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Tile large />
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed", fontSize: 8, lineHeight: 1.1 }}>
          <thead>
            <tr>
              <th style={{ width: "22%", textAlign: "left", fontWeight: 500, letterSpacing: "0.02em", padding: "0 4px 4px 0", color: MUTED }} />
              {COLS.map((col) => (
                <th key={col} style={{ textAlign: "center", fontWeight: 500, letterSpacing: "0.02em", padding: "0 1px 4px", color: MUTED }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row}>
                <th scope="row" style={{ textAlign: "left", fontWeight: 500, padding: "1px 4px 1px 0", fontSize: 10 }}>
                  {row}
                </th>
                {COLS.map((col) => (
                  <td key={col} style={{ textAlign: "center", padding: "1px" }}>
                    <Tile large={false} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
