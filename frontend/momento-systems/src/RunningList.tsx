import { useEffect, useRef, useState } from "react";
import { FRAME } from "./layout";

type Item = { id: string; text: string; date: string; archived?: boolean };

type Props = {
  enlarged?: boolean;
  docked?: boolean;
  onEnlarge?: () => void;
};

const STORAGE_KEY = "propino-running-list";
const INK = "#c8c4bc";
const NAVY = "#14161b";
const LINE = "#2a2e36";
const FIELD = "#1c2230";

function loadItems(): Item[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Item[]) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((row) => row && row.text && row.date)
      .map((row) => ({
        id: row.id,
        text: row.text,
        date: row.date,
        ...(row.archived === true ? { archived: true } : {}),
      }));
  } catch {
    return [];
  }
}

function groupByDate(rows: Item[]): { date: string; items: Item[] }[] {
  const groups = new Map<string, Item[]>();
  for (const row of rows) {
    const list = groups.get(row.date) ?? [];
    list.push(row);
    groups.set(row.date, list);
  }
  return [...groups.keys()]
    .sort((a, b) => a.localeCompare(b))
    .map((date) => ({ date, items: groups.get(date) ?? [] }));
}

const fieldStyle = {
  background: FIELD,
  color: INK,
  border: `1px solid ${LINE}`,
  borderRadius: 8,
  padding: "8px 10px",
  font: "inherit",
  fontSize: 13,
  outline: "none",
} as const;

const CAP = "Create a cursor agent prompt for the following:\n";
const IMP_FRAME = "Implement the following framework:\n";

function todayStamp(): string {
  const now = new Date();
  const month = now.getMonth() + 1;
  const day = String(now.getDate()).padStart(2, "0");
  return `${month}/${day}`;
}

const buttonStyle = {
  background: FIELD,
  color: INK,
  border: `1px solid ${LINE}`,
  borderRadius: 8,
  padding: "8px 12px",
  font: "inherit",
  fontSize: 12,
  letterSpacing: "0.06em",
  cursor: "pointer",
} as const;

export default function RunningList({ enlarged = false, docked = false, onEnlarge }: Props) {
  const [items, setItems] = useState<Item[]>(loadItems);
  const [text, setText] = useState("");
  const [date, setDate] = useState("");
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [openDays, setOpenDays] = useState<string[]>([]);
  const noteRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  function addItem() {
    const next = text.trim();
    const when = date.trim();
    if (!next || !when) return;
    setItems((prev) => [...prev, { id: `${Date.now()}`, text: next, date: when }]);
    setText("");
    setDate("");
  }

  function openTemplate(body: string) {
    setText(body);
    setDate(todayStamp());
    requestAnimationFrame(() => {
      const field = noteRef.current;
      if (!field) return;
      field.focus();
      const end = field.value.length;
      field.setSelectionRange(end, end);
    });
  }

  function archiveItem(id: string) {
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, archived: true } : item)));
  }

  const active = items.filter((item) => item.archived !== true);
  const archived = groupByDate(items.filter((item) => item.archived === true));
  const needle = query.trim().toLowerCase();
  const visibleArchive = archived
    .map((group) => {
      if (!needle) return group;
      if (group.date.toLowerCase().includes(needle)) return group;
      const matched = group.items.filter((item) => item.text.toLowerCase().includes(needle));
      return matched.length ? { date: group.date, items: matched } : null;
    })
    .filter((group): group is { date: string; items: Item[] } => group !== null);
  const archivedCount = archived.reduce((sum, group) => sum + group.items.length, 0);
  const gutter = `max(160px, calc((100% - min(100%, (100dvh - 300px) * ${FRAME.w} / ${FRAME.h} + 32px)) / 2 - 36px))`;

  return (
    <section
      aria-label="Running list"
      className="running-list"
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
                maxHeight: 320,
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
            : {
                position: "absolute",
                left: 18,
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
      <style>{`.running-list input::placeholder, .running-list textarea::placeholder { color: #8b8f98; }`}</style>
      {enlarged ? (
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flex: "0 0 auto" }}>
          <button type="button" onClick={() => openTemplate(CAP)} style={buttonStyle}>
            cap
          </button>
          <button type="button" onClick={() => openTemplate(IMP_FRAME)} style={buttonStyle}>
            ImpFrame
          </button>
        </div>
      ) : null}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          addItem();
        }}
        style={{ display: "flex", gap: 6, alignItems: "flex-start", flex: "0 0 auto", minWidth: 0, marginBottom: 8 }}
      >
        <textarea
          ref={noteRef}
          aria-label="List item"
          value={text}
          rows={enlarged ? 6 : 2}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.stopPropagation();
          }}
          placeholder="Add a line"
          style={{
            ...fieldStyle,
            flex: "1 1 auto",
            minWidth: 0,
            resize: "none",
            lineHeight: 1.35,
            height: enlarged ? 160 : 52,
            boxSizing: "border-box",
          }}
        />
        <input
          aria-label="Completion date"
          type="text"
          value={date}
          onChange={(event) => setDate(event.target.value)}
          placeholder="Date"
            style={{ ...fieldStyle, width: enlarged ? 140 : 72, flex: "0 1 auto", minWidth: 0 }}
        />
        <button type="submit" style={{ ...buttonStyle, flex: "0 0 auto", padding: enlarged ? "8px 12px" : "6px 8px" }}>
          Add
        </button>
      </form>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, overflow: "auto", flex: "1 1 auto", minHeight: 0 }}>
        {active.map((item) => (
          <li key={item.id} style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: enlarged ? "12px 0" : "8px 0" }}>
            <button
              type="button"
              aria-label={`Archive ${item.text}`}
              onClick={() => archiveItem(item.id)}
              style={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                border: `2px solid ${INK}`,
                background: "transparent",
                padding: 0,
                flex: "0 0 auto",
                cursor: "pointer",
                marginTop: 2,
              }}
            />
            <span style={{ flex: "1 1 auto", minWidth: 0, fontSize: enlarged ? 16 : 13, lineHeight: 1.35, whiteSpace: "pre-wrap" }}>{item.text}</span>
            <time style={{ flex: "0 0 auto", fontSize: enlarged ? 13 : 11, letterSpacing: "0.14em", textTransform: "uppercase", color: INK }}>
              {item.date}
            </time>
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8, flex: "0 0 auto", minWidth: 0 }}>
        {enlarged ? null : (
          <button type="button" onClick={onEnlarge} style={{ ...buttonStyle, flex: "0 0 auto", padding: "6px 8px" }}>
            Enlarge
          </button>
        )}
        <button
          type="button"
          aria-expanded={archiveOpen}
          onClick={() => setArchiveOpen((open) => !open)}
          style={{ ...buttonStyle, marginLeft: "auto", flex: "0 1 auto", minWidth: 0, padding: enlarged ? "8px 12px" : "6px 8px" }}
        >
          Archive {archivedCount}
        </button>
      </div>
      {archiveOpen ? (
        <aside aria-label="Archive" style={{ flex: "1 1 auto", minHeight: 0, overflow: "auto", marginTop: 8 }}>
          <input
            aria-label="Search archive"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search"
            style={{ ...fieldStyle, width: "100%", boxSizing: "border-box", marginBottom: 8 }}
          />
          {visibleArchive.map((group) => {
            const open = openDays.includes(group.date);
            return (
              <div key={group.date} style={{ marginBottom: 6 }}>
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => setOpenDays((days) => (days.includes(group.date) ? days.filter((day) => day !== group.date) : [...days, group.date]))}
                  style={{ ...buttonStyle, width: "100%", textAlign: "left", padding: enlarged ? "8px 12px" : "6px 8px" }}
                >
                  {group.date} {group.items.length}
                </button>
                {open ? (
                  <ul style={{ listStyle: "none", margin: 0, padding: "4px 0 0 8px" }}>
                    {group.items.map((item) => (
                      <li key={item.id} style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "3px 0" }}>
                        <span aria-hidden="true" style={{ width: 12, height: 12, borderRadius: "50%", border: `2px solid ${INK}`, flex: "0 0 auto", marginTop: 2 }} />
                        <span style={{ flex: "1 1 auto", minWidth: 0, fontSize: enlarged ? 14 : 11, lineHeight: 1.3, whiteSpace: "pre-wrap" }}>{item.text}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            );
          })}
        </aside>
      ) : null}
    </section>
  );
}
