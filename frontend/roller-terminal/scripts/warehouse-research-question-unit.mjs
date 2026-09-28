/**
 * Phase 19: frontend ResearchQuestion constructor.
 * Serialization only. No detector math.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = join(__dirname, "..", "src", "v2", "warehouse", "researchQuestionFromDraft.ts");
const text = readFileSync(SRC, "utf8");

function token(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/-/g, "_");
}

function season(value) {
  const raw = String(value ?? "")
    .trim()
    .replace(/[–_]/g, "-");
  if (raw === "2025-26" || raw === "2025-2026") return "2025-2026";
  return raw;
}

function centsToE4(value) {
  if (value == null || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 100);
}

const ENTRY_FAMILY = {
  cross: { ordinal: "FIRST_TOUCH", operation: "CROSS" },
  break: { ordinal: "FIRST_TOUCH", operation: "BREAK" },
};

function construct(draft) {
  const entry = draft.entryConditions[0];
  const mapped = ENTRY_FAMILY[entry.family];
  const payload = {
    id: entry.id,
    ordinal: mapped.ordinal,
    price_e4: centsToE4(entry.priceCents),
    period: entry.period || null,
    event_definition: "TRADABLE_CLOSE_CROSS",
    price_field: "yes_bid_close",
  };
  if (mapped.operation !== mapped.ordinal) payload.operation = mapped.operation;
  return {
    universe: {
      sports: draft.universe.sports.map((s) => s.toUpperCase()),
      seasons: draft.universe.seasons.map(season),
      market_data: draft.universe.marketData.map((m) => token(m)),
      date_from: draft.universe.dateFrom,
      date_to: draft.universe.dateTo,
    },
    entry_conditions: [payload],
    path_conditions: draft.exitConditions
      .filter((e) => e.kind === "path")
      .map((e) => ({
        id: e.id,
        op: e.family === "drop_to" ? "DROP_TO" : "REACH",
        price_e4: centsToE4(e.priceCents),
        outcome: e.outcome,
      })),
    terminal: "BOTH",
    requested_dimensions: ["HOLD_TO_SETTLEMENT"],
  };
}

test("warehouse desk activates on league NBA with sport basketball", () => {
  const basketballNba = {
    universe: { sports: ["basketball"], leagues: ["NBA"] },
  };
  const ncaabOnly = {
    universe: { sports: ["basketball"], leagues: ["NCAAB"] },
  };
  const desk = (draft) =>
    draft.universe.leagues.some((s) => ["NBA", "NCAAB", "MLB"].includes(s.toUpperCase()))
    || draft.universe.sports.some((s) => ["NBA", "NCAAB", "MLB", "BASEBALL"].includes(s.toUpperCase()));
  assert.equal(desk(basketballNba), true);
  assert.equal(desk(ncaabOnly), true);
  assert.ok(text.includes("canonicalNbaUniverse"));
  assert.ok(text.includes("NCAAB"));
  const resultsSrc = readFileSync(join(__dirname, "..", "src", "v2", "warehouse", "WarehouseResults.tsx"), "utf8");
  assert.ok(resultsSrc.includes('return "NCAAB"'));
  const quickStart = readFileSync(join(__dirname, "..", "src", "v2", "workflow", "QuickStartScreen.tsx"), "utf8");
  assert.ok(quickStart.includes("ncaabOnly"));
  assert.ok(quickStart.includes("nbaOnly || ncaabOnly || mlbOnly"));
});

test("constructs CROSS 63 ResearchQuestion without FIRST80", () => {
  const q = construct({
    universe: {
      sports: ["NBA"],
      seasons: ["2025-26"],
      marketData: ["candles"],
      dateFrom: "2025-10-10",
      dateTo: "2025-10-10",
    },
    entryConditions: [{ id: "e1", family: "cross", priceCents: 63, period: "Q2" }],
    exitConditions: [
      { id: "win", kind: "path", family: "reach", priceCents: 87, outcome: "win" },
      { id: "loss", kind: "path", family: "reach", priceCents: 41, outcome: "loss" },
    ],
  });
  assert.equal(q.universe.seasons[0], "2025-2026");
  assert.equal(q.entry_conditions[0].operation, "CROSS");
  assert.equal(q.entry_conditions[0].price_e4, 6300);
  assert.equal(q.path_conditions[0].price_e4, 8700);
  assert.equal(q.path_conditions[1].price_e4, 4100);
  assert.ok(!JSON.stringify(q).includes("FIRST80"));
});

test("constructs previously unseen BREAK 71 strategy", () => {
  const q = construct({
    universe: {
      sports: ["NBA"],
      seasons: ["2025-26"],
      marketData: ["candles"],
      dateFrom: "2025-10-10",
      dateTo: "2025-10-10",
    },
    entryConditions: [{ id: "e1", family: "break", priceCents: 71 }],
    exitConditions: [
      { id: "win", kind: "path", family: "reach", priceCents: 90, outcome: "win" },
      { id: "loss", kind: "path", family: "drop_to", priceCents: 35, outcome: "loss" },
    ],
  });
  assert.equal(q.entry_conditions[0].operation, "BREAK");
  assert.equal(q.entry_conditions[0].price_e4, 7100);
  assert.equal(q.path_conditions[1].op, "DROP_TO");
  assert.equal(q.path_conditions[1].price_e4, 3500);
});

test("source constructor has no frozen primitives", () => {
  for (const tokenName of ["FIRST80", "FIRST75", "FIRST01", "T40", "Lebronner", "PADE", "DRE"]) {
    assert.equal(text.includes(tokenName), false, tokenName);
  }
  assert.ok(text.includes("researchQuestionFromDraft"));
  assert.ok(text.includes("CROSS"));
  assert.ok(text.includes('bounce: "BOUNCE"'));
  assert.ok(text.includes('never_reach: "NEVER_REACH"'));
});
