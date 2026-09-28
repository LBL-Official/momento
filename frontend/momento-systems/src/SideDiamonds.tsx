import { useState, type CSSProperties, type ReactNode } from "react";
import { FRAME } from "./layout";

export type DiamondSlot = { name: string; fill: string; overlay: string };
export type DiamondSide = "left" | "right";
export type DiamondStore = { left: DiamondSlot[]; right: DiamondSlot[] };

const MAX_ADDED = 4;

const STORAGE_KEY = "momento-side-diamonds";
const SIZE = 132;
const GAP = 12;
const INK = "#c8c4bc";
const NAVY = "#14161b";
const LINE = "#2a2e36";
const FIELD = "#1c2230";
const CLIP = "polygon(50% 0, 100% 50%, 50% 100%, 0 50%)";

export const DIAMOND_COLORS = [
  { name: "Purple", value: "#3c3648" },
  { name: "Blue grey", value: "#343c44" },
  { name: "Navy", value: "#14161b" },
  { name: "Stone", value: "#6d675e" },
  { name: "Wool", value: "#8a8680" },
  { name: "Olive", value: "#4a5244" },
  { name: "Slate", value: "#3a4450" },
  { name: "Dust", value: "#4a3c40" },
  { name: "Charcoal", value: "#2c2a28" },
  { name: "Gold", value: "#8a7344" },
] as const;

const GRID = `min(100%, (100dvh - 300px) * ${FRAME.w} / ${FRAME.h} + 32px)`;
const PAIR_INSET = `max(16px, calc((100% - ${GRID}) / 4 - 138px))`;

function loadSide(value: unknown): DiamondSlot[] {
  const rows = Array.isArray(value) ? value : value ? [value] : [];
  return rows
    .map((row) => validSlot(row as DiamondSlot))
    .filter((row): row is DiamondSlot => row !== null)
    .slice(0, MAX_ADDED);
}

export function loadDiamonds(): DiamondStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as { left?: unknown; right?: unknown }) : null;
    return { left: loadSide(parsed?.left), right: loadSide(parsed?.right) };
  } catch {
    return { left: [], right: [] };
  }
}

export function saveDiamonds(store: DiamondStore) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

function validSlot(slot: DiamondSlot | null | undefined): DiamondSlot | null {
  if (!slot || !slot.name) return null;
  const known = new Set<string>(DIAMOND_COLORS.map((color) => color.value));
  if (!known.has(slot.fill) || !known.has(slot.overlay)) return null;
  return { name: slot.name, fill: slot.fill, overlay: slot.overlay };
}

function DiamondFace({
  fill,
  overlay,
  label,
  children,
  fluid,
}: {
  fill: string;
  overlay: string;
  label?: string;
  children?: ReactNode;
  fluid?: boolean;
}) {
  return (
    <div
      aria-label={label || "diamond placeholder"}
      style={
        fluid
          ? { position: "relative", width: "100%", height: "auto", aspectRatio: "1", minWidth: 0 }
          : { position: "relative", width: SIZE, height: SIZE, flex: "0 0 auto" }
      }
    >
      <span aria-hidden="true" style={{ position: "absolute", inset: 0, background: overlay, clipPath: CLIP }} />
      <span
        style={{
          position: "absolute",
          inset: 3,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 4,
          background: fill,
          color: INK,
          clipPath: CLIP,
          fontSize: 13,
          fontWeight: 500,
          letterSpacing: "0.03em",
          lineHeight: 1.1,
          textAlign: "center",
          padding: 18,
        }}
      >
        {children}
        {label ? <span>{label}</span> : null}
      </span>
    </div>
  );
}

function AddButton({ side, disabled, onEdit }: { side: DiamondSide; disabled: boolean; onEdit: (side: DiamondSide) => void }) {
  const edge = side === "left" ? { left: PAIR_INSET } : { right: PAIR_INSET };
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onEdit(side)}
      style={{
        position: "absolute",
        ...edge,
        width: SIZE * 2 + GAP,
        top: "calc(50% - 66px)",
        transform: "translateY(calc(-100% - 10px))",
        zIndex: 1,
        background: NAVY,
        color: INK,
        border: `1px solid ${LINE}`,
        borderRadius: 8,
        padding: "8px 12px",
        font: "inherit",
        fontSize: 12,
        letterSpacing: "0.06em",
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.45 : 1,
      }}
    >
      Add diamond
    </button>
  );
}

function lineStyle(side: DiamondSide, line: number): CSSProperties {
  const edge = side === "left" ? { left: PAIR_INSET } : { right: PAIR_INSET };
  const below = line === 0 ? undefined : `calc(50% + ${66 + GAP + (line - 1) * (SIZE + GAP)}px)`;
  return {
    position: "absolute",
    ...edge,
    top: line === 0 ? "50%" : below,
    transform: line === 0 ? "translateY(-50%)" : undefined,
    display: "flex",
    justifyContent: side === "left" ? "flex-start" : "flex-end",
    gap: GAP,
    width: SIZE * 2 + GAP,
    zIndex: 1,
  };
}

function faceButton(fluid?: boolean): CSSProperties {
  return {
    padding: 0,
    border: "none",
    background: "transparent",
    cursor: "default",
    ...(fluid ? { width: "100%", display: "block" } : {}),
  };
}

function Hypno() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="2.1" fill="none" stroke="currentColor" strokeWidth="1.35" />
      <circle cx="12" cy="12" r="4.8" fill="none" stroke="currentColor" strokeWidth="1.35" />
      <circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" strokeWidth="1.35" />
      <circle cx="12" cy="12" r="10.2" fill="none" stroke="currentColor" strokeWidth="1.35" />
    </svg>
  );
}

function DeskMark() {
  return (
    <svg width="22" height="16" viewBox="0 0 36 28" aria-hidden="true">
      <rect x="2" y="8" width="32" height="4" fill="currentColor" />
      <rect x="6" y="12" width="3" height="12" fill="currentColor" />
      <rect x="27" y="12" width="3" height="12" fill="currentColor" />
    </svg>
  );
}

function LeftPair({ fluid }: { fluid?: boolean }) {
  return (
    <>
      <button
        type="button"
        aria-label="78/67 bball"
        onClick={() => {
          window.location.hash = "/bball-7867";
        }}
        style={{ ...faceButton(fluid), cursor: "pointer" }}
      >
        <DiamondFace fluid={fluid} fill="#3c3648" overlay="#8a7344" label={"78/67 bball"} />
      </button>
      <button type="button" aria-label="propino" style={faceButton(fluid)}>
        <DiamondFace fluid={fluid} fill="#3c3648" overlay="#8a7344" label="propino">
          <Hypno />
        </DiamondFace>
      </button>
    </>
  );
}

function RightPair({ fluid }: { fluid?: boolean }) {
  return (
    <>
      <button type="button" aria-label="120 Desk" style={faceButton(fluid)}>
        <DiamondFace fluid={fluid} fill="#343c44" overlay="#8a7344" label="120 Desk">
          <DeskMark />
        </DiamondFace>
      </button>
      <DiamondFace fluid={fluid} fill="#343c44" overlay="#8a7344" />
    </>
  );
}

function SavedFace({ slot, fluid }: { slot: DiamondSlot; fluid?: boolean }) {
  return <DiamondFace fluid={fluid} fill={slot.fill} overlay={slot.overlay} label={slot.name} />;
}

function dockRow(side: DiamondSide): CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: GAP,
    width: "min(276px, 100%)",
    marginLeft: side === "right" ? "auto" : undefined,
  };
}

function DockedSide({
  side,
  lines,
  fixed,
  onEdit,
}: {
  side: DiamondSide;
  lines: DiamondSlot[][];
  fixed: ReactNode;
  onEdit: (side: DiamondSide) => void;
}) {
  const disabled = lines.reduce((sum, line) => sum + line.length, 0) >= MAX_ADDED;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, width: "100%" }}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onEdit(side)}
        style={{
          width: "min(276px, 100%)",
          marginLeft: side === "right" ? "auto" : undefined,
          background: NAVY,
          color: INK,
          border: `1px solid ${LINE}`,
          borderRadius: 8,
          padding: "8px 12px",
          font: "inherit",
          fontSize: 12,
          letterSpacing: "0.06em",
          cursor: disabled ? "default" : "pointer",
          opacity: disabled ? 0.45 : 1,
        }}
      >
        Add diamond
      </button>
      <div style={dockRow(side)}>{fixed}</div>
      {lines.map((line, index) => (
        <div key={`${side}-${index}`} style={dockRow(side)}>
          {side === "right" && line.length === 1 ? <span /> : null}
          {line.map((slot, slotIndex) => (
            <SavedFace key={`${slot.name}-${slotIndex}`} slot={slot} fluid />
          ))}
        </div>
      ))}
    </div>
  );
}

function chunk(slots: DiamondSlot[]): DiamondSlot[][] {
  const lines: DiamondSlot[][] = [];
  for (let i = 0; i < slots.length; i += 2) lines.push(slots.slice(i, i + 2));
  return lines;
}

export default function SideDiamonds({
  slots,
  onEdit,
  docked = false,
}: {
  slots: DiamondStore;
  onEdit: (side: DiamondSide) => void;
  docked?: boolean;
}) {
  const leftLines = chunk(slots.left);
  const rightLines = chunk(slots.right);
  if (docked) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 20, width: "100%" }}>
        <DockedSide side="left" lines={leftLines} fixed={<LeftPair fluid />} onEdit={onEdit} />
        <DockedSide side="right" lines={rightLines} fixed={<RightPair fluid />} onEdit={onEdit} />
      </div>
    );
  }
  return (
    <>
      <AddButton side="left" disabled={slots.left.length >= MAX_ADDED} onEdit={onEdit} />
      <div style={lineStyle("left", 0)}>
        <LeftPair />
      </div>
      {leftLines.map((line, index) => (
        <div key={`left-${index}`} style={lineStyle("left", index + 1)}>
          {line.map((slot, slotIndex) => (
            <SavedFace key={`${slot.name}-${slotIndex}`} slot={slot} />
          ))}
        </div>
      ))}
      <AddButton side="right" disabled={slots.right.length >= MAX_ADDED} onEdit={onEdit} />
      <div style={lineStyle("right", 0)}>
        <RightPair />
      </div>
      {rightLines.map((line, index) => (
        <div key={`right-${index}`} style={lineStyle("right", index + 1)}>
          {line.map((slot, slotIndex) => (
            <SavedFace key={`${slot.name}-${slotIndex}`} slot={slot} />
          ))}
        </div>
      ))}
    </>
  );
}

export function DiamondEditor({
  side,
  onSave,
}: {
  side: DiamondSide;
  onSave: (slot: DiamondSlot) => void;
}) {
  const [name, setName] = useState("");
  const [fill, setFill] = useState(side === "left" ? "#3c3648" : "#343c44");
  const [overlay, setOverlay] = useState("#8a7344");

  return (
    <section
      aria-label="Add diamond"
      style={{
        flex: "1 1 auto",
        minHeight: 0,
        margin: "0 24px 24px",
        background: NAVY,
        color: INK,
        border: `1px solid ${LINE}`,
        display: "flex",
        flexDirection: "column",
        padding: "28px 32px 20px",
        gap: 18,
        overflow: "auto",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        <DiamondFace fill={fill} overlay={overlay} label={name || "name"} />
        <input
          aria-label="Diamond name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Name"
          style={{ flex: "1 1 auto", background: FIELD, color: INK, border: `1px solid ${LINE}`, borderRadius: 8, padding: "10px 12px", font: "inherit", fontSize: 16 }}
        />
      </div>
      <Swatches label="Fill" value={fill} onPick={setFill} />
      <Swatches label="Overlay" value={overlay} onPick={setOverlay} />
      <button
        type="button"
        disabled={!name.trim()}
        onClick={() => onSave({ name: name.trim(), fill, overlay })}
        style={{
          alignSelf: "flex-start",
          background: FIELD,
          color: INK,
          border: `1px solid ${LINE}`,
          borderRadius: 8,
          padding: "10px 16px",
          font: "inherit",
          letterSpacing: "0.06em",
          cursor: name.trim() ? "pointer" : "default",
        }}
      >
        Save
      </button>
    </section>
  );
}

function Swatches({ label, value, onPick }: { label: string; value: string; onPick: (value: string) => void }) {
  return (
    <div>
      <div style={{ fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {DIAMOND_COLORS.map((color) => (
          <button
            key={color.value}
            type="button"
            aria-label={color.name}
            aria-pressed={value === color.value}
            onClick={() => onPick(color.value)}
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: color.value,
              border: value === color.value ? `2px solid ${INK}` : `1px solid ${LINE}`,
              cursor: "pointer",
            }}
          />
        ))}
      </div>
    </div>
  );
}
