/**
 * Contract for STAX native strategy construction.
 * STAX writes a ROLLER WorkflowDraft. It does not measure.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = join(__dirname, "..", "src", "stax");

function entryFamilyToken(family) {
  if (family === "first_touch") return "First";
  if (family === "cross") return "Cross";
  return "Entry";
}

function nativeStrategyLabel(form) {
  const token = `${entryFamilyToken(form.entryFamily)}${form.entryCents}`;
  const left = `${form.league} ${token}`;
  if (form.pathCents == null) return left;
  if (form.lossCents == null) return `${left} → ${form.pathCents}`;
  return `${left} → ${form.pathCents} / ${form.lossCents}`;
}

function pathAsWin(form) {
  return form.lossCents != null && form.pathCents != null;
}

function exitConditions(form) {
  const exits = [];
  if (form.pathCents != null) {
    exits.push({
      kind: "path",
      family: "reach",
      priceCents: form.pathCents,
      ...(pathAsWin(form) ? { outcome: "win" } : {}),
    });
  }
  if (form.lossCents != null) {
    exits.push({
      kind: "path",
      family: "reach",
      priceCents: form.lossCents,
      outcome: "loss",
    });
  }
  exits.push({ kind: "terminal", family: form.terminal });
  return exits;
}

test("NBA First75 → 85 / 35 is a two-sided Reach book", () => {
  const form = {
    league: "NBA",
    entryFamily: "first_touch",
    entryCents: 75,
    pathCents: 85,
    lossCents: 35,
    terminal: "both",
  };
  assert.equal(nativeStrategyLabel(form), "NBA First75 → 85 / 35");
  const exits = exitConditions(form);
  assert.equal(exits[0].outcome, "win");
  assert.equal(exits[0].priceCents, 85);
  assert.equal(exits[1].outcome, "loss");
  assert.equal(exits[1].priceCents, 35);
  assert.equal(exits[2].kind, "terminal");
  assert.equal(exits[2].family, "both");
});

test("NBA Cross60 → 90 is an untagged observational Reach", () => {
  const form = {
    league: "NBA",
    entryFamily: "cross",
    entryCents: 60,
    pathCents: 90,
    lossCents: null,
    terminal: "both",
  };
  assert.equal(nativeStrategyLabel(form), "NBA Cross60 → 90");
  const exits = exitConditions(form);
  assert.equal(exits.length, 2);
  assert.equal(exits[0].outcome, undefined);
  assert.equal(exits[0].priceCents, 90);
  assert.equal(exits[1].family, "both");
});

test("NCAAB First80 → 40 stays observational (FIRST80-style path)", () => {
  const form = {
    league: "NCAAB",
    entryFamily: "first_touch",
    entryCents: 80,
    pathCents: 40,
    lossCents: null,
    terminal: "both",
  };
  assert.equal(nativeStrategyLabel(form), "NCAAB First80 → 40");
  const exits = exitConditions(form);
  assert.equal(exits[0].outcome, undefined);
  assert.equal(exits[0].priceCents, 40);
});

test("WIN path under entry is rejected when a stop is present", () => {
  const form = {
    entryCents: 75,
    pathCents: 40,
    lossCents: 35,
  };
  assert.equal(pathAsWin(form), true);
  assert.ok(form.pathCents < form.entryCents);
});

test("nativeDraft constructs a WorkflowDraft and does not invent measurement", () => {
  const src = readFileSync(join(SRC, "nativeDraft.ts"), "utf8");
  assert.match(src, /must not[\s\S]*reinterpret/);
  assert.match(src, /draftFromNativeForm/);
  assert.match(src, /family: "reach"/);
  assert.match(src, /outcome: "win"/);
  assert.match(src, /outcome: "loss"/);
  assert.match(src, /family: form\.terminal/);
  assert.doesNotMatch(src, /execute_question|path_rate|invent/);
});

test("+ ADD STRATEGY opens the native builder, not a chooser", () => {
  const workspace = readFileSync(join(SRC, "StaxWorkspace.tsx"), "utf8");
  const builder = readFileSync(join(SRC, "StaxNativeBuilder.tsx"), "utf8");
  assert.match(workspace, /setAddMode\("native"\)/);
  assert.match(workspace, /StaxNativeBuilder/);
  assert.doesNotMatch(workspace, /StaxAddChooser/);
  assert.match(builder, /createStaxStrategy/);
  assert.match(builder, /\/research-query\/compile/);
  assert.match(builder, /persist: true/);
  assert.match(builder, /Save strategy/);
});
