/**
 * Runtime unit for sport-family switch. No location.reload in the helper.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const __dirname = dirname(fileURLToPath(import.meta.url));
const BASKETBALL_PERIOD = /^(Q|H|OT|P5)/;
const BASEBALL_PERIOD = /^(T|B|I)\d|^T[BX]$|^B[BX]$/;
const TENNIS_PERIOD = /^S[1-5]$|^G\d|^G10\+$/;

function familyOf(id) {
  if (["basketball", "NBA", "WNBA", "NCAAB"].includes(id)) return "basketball";
  if (["baseball", "MLB"].includes(id)) return "baseball";
  if (["tennis", "ATP", "WTA"].includes(id)) return "tennis";
  return "unknown";
}

function mixedClockFamilies(universe) {
  const fams = new Set(
    [...universe.sports, ...universe.leagues].map(familyOf).filter((f) => f !== "unknown"),
  );
  return fams.size > 1;
}

function selectSportFamily(universe, id) {
  const fam = familyOf(id);
  if (fam === "baseball") {
    return { ...universe, sports: ["baseball"], leagues: ["MLB"], marketData: ["last_trade"] };
  }
  if (fam === "tennis") {
    const sports = ["tennis"];
    let leagues = universe.leagues.filter((l) => familyOf(l) === "tennis");
    if (id === "ATP" || id === "WTA") {
      leagues =
        leagues.includes(id) && universe.sports.includes("tennis")
          ? leagues.filter((l) => l !== id)
          : [...leagues.filter((l) => l !== id), id];
    }
    if (id === "tennis" && !leagues.length) {
      leagues = ["ATP", "WTA"];
    }
    return {
      ...universe,
      sports,
      leagues: leagues.length ? leagues : ["ATP", "WTA"],
      marketData: ["candles"],
    };
  }
  if (fam === "basketball") {
    const sports = ["basketball"];
    let leagues = universe.leagues.filter((l) => familyOf(l) === "basketball");
    if (id === "NBA" || id === "NCAAB" || id === "WNBA") {
      leagues =
        leagues.includes(id) && universe.sports.includes("basketball")
          ? leagues.filter((l) => l !== id)
          : [...leagues.filter((l) => l !== id), id];
    }
    const md = universe.marketData || [];
    const marketData =
      !md.length || (md.length === 1 && md[0] === "last_trade") ? ["candles"] : md;
    return { ...universe, sports, leagues, marketData };
  }
  return universe;
}

function clearIncompatiblePeriods(entry, nextFamily) {
  const drop = (period) => {
    if (!period) return false;
    if (nextFamily === "basketball") {
      return BASEBALL_PERIOD.test(period) || TENNIS_PERIOD.test(period);
    }
    if (nextFamily === "baseball") {
      return BASKETBALL_PERIOD.test(period) || TENNIS_PERIOD.test(period);
    }
    if (nextFamily === "tennis") {
      return BASKETBALL_PERIOD.test(period) || BASEBALL_PERIOD.test(period);
    }
    return false;
  };
  const windows = (entry.periodWindows ?? []).filter((w) => !drop(w.period));
  const tennisGameRange =
    nextFamily === "tennis" ? entry : { gameFrom: undefined, gameTo: undefined };
  const clockStripped = drop(entry.period) || nextFamily === "tennis";
  return {
    ...entry,
    ...tennisGameRange,
    period: drop(entry.period) ? undefined : entry.period,
    clockFrom: drop(entry.period) || clockStripped ? undefined : entry.clockFrom,
    clockTo: drop(entry.period) || clockStripped ? undefined : entry.clockTo,
    periodWindows: windows.length ? windows : undefined,
  };
}

test("baseball click clears basketball and does not reload", () => {
  const next = selectSportFamily(
    {
      sports: ["basketball"],
      leagues: ["NBA", "NCAAB"],
      seasons: ["2025-26"],
      markets: ["kalshi"],
      marketData: ["candles"],
      dataSources: [],
    },
    "baseball",
  );
  assert.deepEqual(next.sports, ["baseball"]);
  assert.deepEqual(next.leagues, ["MLB"]);
  assert.deepEqual(next.marketData, ["last_trade"]);
  assert.equal(typeof location, "undefined");
});

test("NBA candles draft switching to Baseball forces last_trade without reload", () => {
  const nbaDraft = {
    sports: ["basketball"],
    leagues: ["NBA"],
    seasons: ["2025-26"],
    markets: ["kalshi"],
    marketData: ["candles"],
    dataSources: [],
  };
  const next = selectSportFamily(nbaDraft, "baseball");
  assert.deepEqual(next.marketData, ["last_trade"]);
  assert.ok(!next.marketData.includes("candles"));
  assert.equal(typeof location, "undefined");
});

test("MLB click same family switch", () => {
  const next = selectSportFamily(
    { sports: ["basketball"], leagues: ["NBA"], seasons: [], markets: [], marketData: [], dataSources: [] },
    "MLB",
  );
  assert.deepEqual(next.sports, ["baseball"]);
  assert.deepEqual(next.leagues, ["MLB"]);
});

test("NBA click clears baseball", () => {
  const next = selectSportFamily(
    {
      sports: ["baseball"],
      leagues: ["MLB"],
      seasons: ["2025-26"],
      markets: ["kalshi"],
      marketData: ["last_trade"],
      dataSources: [],
    },
    "NBA",
  );
  assert.deepEqual(next.sports, ["basketball"]);
  assert.deepEqual(next.leagues, ["NBA"]);
  assert.deepEqual(next.marketData, ["candles"]);
});

test("family switch drops Q chips and keeps price", () => {
  const cleared = clearIncompatiblePeriods(
    { family: "first_touch", priceCents: 80, period: "Q3", clockFrom: "08:00" },
    "baseball",
  );
  assert.equal(cleared.priceCents, 80);
  assert.equal(cleared.period, undefined);
});

test("NBA -> Tennis clears basketball periods and sets sports/leagues correctly", () => {
  const next = selectSportFamily(
    {
      sports: ["basketball"],
      leagues: ["NBA"],
      seasons: ["2025-26"],
      markets: ["kalshi"],
      marketData: ["candles"],
      dataSources: [],
    },
    "tennis",
  );
  assert.deepEqual(next.sports, ["tennis"]);
  assert.deepEqual(next.leagues, ["ATP", "WTA"]);
  assert.deepEqual(next.marketData, ["candles"]);
  const cleared = clearIncompatiblePeriods(
    { family: "first_touch", priceCents: 80, period: "Q3", clockFrom: "08:00" },
    "tennis",
  );
  assert.equal(cleared.period, undefined);
  assert.equal(cleared.clockFrom, undefined);
  assert.equal(cleared.priceCents, 80);
});

test("Tennis -> MLB clears tennis state", () => {
  const next = selectSportFamily(
    {
      sports: ["tennis"],
      leagues: ["ATP", "WTA"],
      seasons: ["2025-26"],
      markets: ["kalshi"],
      marketData: ["candles"],
      dataSources: [],
    },
    "MLB",
  );
  assert.deepEqual(next.sports, ["baseball"]);
  assert.deepEqual(next.leagues, ["MLB"]);
  assert.deepEqual(next.marketData, ["last_trade"]);
  const cleared = clearIncompatiblePeriods(
    { family: "first_touch", priceCents: 70, period: "S2", gameFrom: 4, gameTo: 6 },
    "baseball",
  );
  assert.equal(cleared.period, undefined);
  assert.equal(cleared.gameFrom, undefined);
  assert.equal(cleared.gameTo, undefined);
  assert.equal(cleared.priceCents, 70);
});

test("Tennis -> NBA clears tennis state", () => {
  const next = selectSportFamily(
    {
      sports: ["tennis"],
      leagues: ["ATP"],
      seasons: ["2025-26"],
      markets: ["kalshi"],
      marketData: ["candles"],
      dataSources: [],
    },
    "NBA",
  );
  assert.deepEqual(next.sports, ["basketball"]);
  assert.deepEqual(next.leagues, ["NBA"]);
  const cleared = clearIncompatiblePeriods(
    { family: "first_touch", period: "G4-6", periodWindows: [{ period: "S1" }] },
    "basketball",
  );
  assert.equal(cleared.period, undefined);
  assert.equal(cleared.periodWindows, undefined);
});

test("MLB -> Tennis clears innings", () => {
  const next = selectSportFamily(
    {
      sports: ["baseball"],
      leagues: ["MLB"],
      seasons: ["2025-26"],
      markets: ["kalshi"],
      marketData: ["last_trade"],
      dataSources: [],
    },
    "tennis",
  );
  assert.deepEqual(next.sports, ["tennis"]);
  assert.deepEqual(next.marketData, ["candles"]);
  assert.ok(!next.marketData.includes("last_trade"));
  const cleared = clearIncompatiblePeriods(
    { family: "first_touch", period: "T7", clockFrom: undefined },
    "tennis",
  );
  assert.equal(cleared.period, undefined);
});

test("tennis marketData is candles not last_trade", () => {
  const next = selectSportFamily(
    {
      sports: ["baseball"],
      leagues: ["MLB"],
      seasons: [],
      markets: ["kalshi"],
      marketData: ["last_trade"],
      dataSources: [],
    },
    "ATP",
  );
  assert.deepEqual(next.marketData, ["candles"]);
  assert.ok(!next.marketData.includes("last_trade"));
});

test("tennis is an allowed implemented sport", () => {
  const catalog = readFileSync(
    join(__dirname, "..", "src", "v2", "catalog", "availabilityCatalog.ts"),
    "utf8",
  );
  const plan = readFileSync(
    join(__dirname, "..", "src", "v2", "workflow", "resolveResearchPlan.ts"),
    "utf8",
  );
  assert.ok(/id: "tennis"[\s\S]*?availability: "IMPLEMENTED"/.test(catalog));
  assert.ok(/id: "ATP"[\s\S]*?availability: "IMPLEMENTED"/.test(catalog));
  assert.ok(/id: "WTA"[\s\S]*?availability: "IMPLEMENTED"/.test(catalog));
  assert.ok(!/new Set\(\["tennis"\]\)/.test(plan));
  assert.ok(!plan.includes("tennis_sequence_pbp"));
});

test("mixed tennis+NBA is flagged as mixed families", () => {
  assert.ok(
    mixedClockFamilies({ sports: ["tennis", "basketball"], leagues: ["ATP", "NBA"] }),
  );
  assert.ok(mixedClockFamilies({ sports: ["tennis"], leagues: ["ATP", "MLB"] }));
  assert.ok(!mixedClockFamilies({ sports: ["tennis"], leagues: ["ATP", "WTA"] }));
});

function hasReloadCall(source) {
  const stripped = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  return /\blocation\.reload\s*\(/.test(stripped);
}

test("baseball YES batting is stripped when leaving baseball", () => {
  const src = readFileSync(join(__dirname, "..", "src", "v2", "workflow", "sportFamily.ts"), "utf8");
  assert.ok(src.includes("nextFamily !== FAMILY_BASEBALL"));
  assert.ok(src.includes("delete base.yesBatting"));
  const question = readFileSync(
    join(__dirname, "..", "src", "v2", "workflow", "questionFromDraft.ts"),
    "utf8",
  );
  assert.ok(question.includes("isBaseballFamily"));
  assert.ok(question.includes("YES ${filters.yesBatting}"));
});

test("stax is coming soon, hold hides path cents, SuperASI is A then B", () => {
  const sidebar = readFileSync(
    join(__dirname, "..", "src", "v2", "shell", "ResearchSidebar.tsx"),
    "utf8",
  );
  assert.ok(sidebar.includes("Coming soon · not in use"));
  assert.ok(sidebar.includes("COMING SOON"));
  const exit = readFileSync(
    join(__dirname, "..", "src", "v2", "workflow", "ExitConditionsScreen.tsx"),
    "utf8",
  );
  assert.ok(exit.includes("{!hold ? ("));
  const nav = readFileSync(join(__dirname, "..", "src", "superasi", "navigation.ts"), "utf8");
  assert.ok(nav.indexOf('"sources"') < nav.indexOf('"run"'));
  assert.ok(nav.indexOf('"run"') < nav.indexOf('"labs_phase_a"'));
  assert.ok(nav.indexOf('"labs_phase_a"') < nav.indexOf('"run_debase"'));
  assert.ok(nav.indexOf('"run_debase"') < nav.indexOf('"labs_phase_b"'));
  const baseRun = readFileSync(join(__dirname, "..", "src", "superasi", "BaseRun.tsx"), "utf8");
  assert.ok(baseRun.includes("selected?: SuperasiLabSource"));
  assert.ok(baseRun.includes("inspect.source_lab_id === selected.lab_id"));
  const app = readFileSync(join(__dirname, "..", "src", "superasi", "SuperASIApp.tsx"), "utf8");
  assert.ok(app.includes("selected={selected}"));
  assert.ok(app.includes("matchPhaseBResult"));
  assert.ok(app.includes("getDebaseResult"));
  const labsA = readFileSync(join(__dirname, "..", "src", "superasi", "LabsPhaseA.tsx"), "utf8");
  assert.ok(labsA.includes("SuperasiAResults"));
  assert.ok(!labsA.includes("ws-labs-list"));
  assert.ok(labsA.includes("not a library of every Roller CSV"));
  const labsB = readFileSync(join(__dirname, "..", "src", "superasi", "LabsPhaseB.tsx"), "utf8");
  assert.ok(labsB.includes("SuperasiBResults"));
  assert.ok(labsB.includes("FolderTile"));
  assert.ok(labsB.includes("Go to Jump"));
  assert.ok(labsB.indexOf("Go to Jump") < labsB.indexOf("Inspect other Final Results"));
  assert.ok(labsB.includes("Inspect other Final Results"));
  assert.ok(!labsB.includes("ws-labs-list"));
  assert.ok(labsB.includes("not a library of every Phase B folder"));
  const aResults = readFileSync(join(__dirname, "..", "src", "superasi", "SuperasiAResults.tsx"), "utf8");
  const deskReport = readFileSync(join(__dirname, "..", "src", "superasi", "SuperasiDeskReport.tsx"), "utf8");
  const bResults = readFileSync(join(__dirname, "..", "src", "superasi", "SuperasiBResults.tsx"), "utf8");
  assert.ok(deskReport.includes("This Roller's entry/exit + observed win rate"));
  assert.ok(aResults.includes("SuperasiDeskReport"));
  assert.ok(aResults.includes("UNAVAILABLE") || deskReport.includes("UNAVAILABLE"));
  assert.ok(deskReport.includes("instrument"));
  assert.ok(bResults.includes("SuperasiDeskReport"));
  assert.ok(bResults.includes("This Roller") || deskReport.includes("This Roller"));
  assert.ok(labsB.includes("SuperasiAResults"));
  const saCss = readFileSync(join(__dirname, "..", "src", "styles.css"), "utf8");
  const rootTheme = saCss.slice(saCss.indexOf(":root {"), saCss.indexOf("--signal-live"));
  assert.ok(rootTheme.includes("--momento-bg: #0c1824"));
  assert.ok(rootTheme.includes("--momento-accent: #5eb8e8"));
  assert.ok(!rootTheme.includes("#7ea3ce"));
  const saTheme = saCss.slice(saCss.lastIndexOf("/* SuperASI mint / charcoal"));
  assert.ok(saTheme.includes("--momento-bg: #cfeee0"));
  assert.ok(saTheme.includes("--momento-text: #1a1a1a"));
  assert.ok(saTheme.includes("--momento-accent: #0f4d32"));
  assert.ok(!saTheme.includes("#7ea3ce"));
  assert.ok(saCss.includes(".ju-drive"));
  assert.ok(saCss.includes(".ju-drive-table"));
  const jumpApp = readFileSync(join(__dirname, "..", "src", "jump", "JumpApp.tsx"), "utf8");
  assert.ok(jumpApp.includes("ju-drive"));
  assert.ok(jumpApp.includes("getDriveTree"));
  assert.ok(jumpApp.includes("Open ROLLER"));
  assert.ok(jumpApp.includes("Open SuperASI"));
  assert.ok(!jumpApp.includes("Create Bot"));
  assert.ok(!jumpApp.includes("My Bots"));
  assert.ok(!jumpApp.includes("openVitalDashboard"));
  assert.ok(!jumpApp.includes("/vital/"));
  assert.ok(!jumpApp.includes("5180"));
  const jumpApi = readFileSync(join(__dirname, "..", "src", "jump", "api", "jumpApi.ts"), "utf8");
  assert.ok(jumpApi.includes("/jump/tree"));
  assert.ok(!jumpApi.includes("/vital/"));
  assert.ok(!jumpApi.includes("/jump/bots"));
  const iti = readFileSync(join(__dirname, "..", "src", "superasi", "ITI.tsx"), "utf8");
  assert.ok(iti.includes("SuperasiAResults"));
  assert.ok(iti.includes("SuperasiBResults"));
  assert.ok(iti.includes("Full expansion is coming soon"));
  assert.ok(iti.includes("ATTACHABLE"));
});

test("no location.reload in src", () => {
  const srcRoot = join(__dirname, "..", "src");
  const app = readFileSync(join(srcRoot, "App.tsx"), "utf8");
  const sportFamily = readFileSync(join(srcRoot, "v2", "workflow", "sportFamily.ts"), "utf8");
  assert.ok(!hasReloadCall(app));
  assert.ok(!hasReloadCall(sportFamily));
});
