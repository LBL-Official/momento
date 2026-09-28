/**
 * Research intelligence catalog.
 *
 * VOCABULARY ≠ SELECTABLE DIMENSION ≠ REGISTERED CONCEPT
 *   ≠ EMPIRICAL PRODUCER ≠ RUNNABLE RESEARCH
 *
 * Second Touch / 60¢ / Reach / Recover and the nine Entry operations
 * (Cross through Minimum Touch) execute on the generic candle engine.
 * Exit-path bounce / revert / maximum_move / minimum_move / never_reach
 * execute on post-entry tradable close (OPERATIONS.md 1.1.0).
 * Polymarket last-trade 1-minute history is not tradable top-of-book.
 * Kalshi is never substituted.
 */

export type Availability =
  | "IMPLEMENTED"
  | "REGISTERED"
  | "COMING_SOON"
  | "NOT_AVAILABLE"
  | "DATA_REQUIRED"
  | "OPERATION_REQUIRED";

export type CatalogKind =
  | "sport"
  | "league"
  | "season"
  | "market"
  | "market_data"
  | "pbp"
  | "entry"
  | "exit_path"
  | "exit_terminal"
  | "exit_horizon";

export type CatalogItem = {
  id: string;
  label: string;
  kind: CatalogKind;
  availability: Availability;
  /** Sport ids this league/season belongs to. */
  sports?: string[];
  note?: string;
};

export const COMING_SOON_COPY =
  "This research dimension is recognized by ROLLER but does not currently have an authoritative producer.";

export const OPERATION_REQUIRED_COPY =
  "OPERATION REQUIRED — no approved candle-close definition. The system will not invent one or return a fake n=0.";

export const DATA_REQUIRED_COPY =
  "DATA REQUIRED — no authoritative warehouse is connected. Kalshi is not substituted.";

export const CATALOG: CatalogItem[] = [
  { id: "basketball", label: "Basketball", kind: "sport", availability: "IMPLEMENTED" },
  {
    id: "baseball",
    label: "Baseball",
    kind: "sport",
    availability: "IMPLEMENTED",
    note: "MLB warehouse desk. Default observation is TRADABLE_YES_BID. LAST TRADE ≠ YES BID.",
  },
  {
    id: "tennis",
    label: "Tennis",
    kind: "sport",
    availability: "IMPLEMENTED",
    note: "Isolated ATP or WTA warehouse desk. Mixed ATP+WTA and tennis without a tour fail closed. Default observation is TRADABLE_YES_BID. LAST TRADE ≠ YES BID.",
  },

  { id: "NBA", label: "NBA", kind: "league", availability: "IMPLEMENTED", sports: ["basketball"] },
  {
    id: "NCAAB",
    label: "NCAAB",
    kind: "league",
    availability: "IMPLEMENTED",
    sports: ["basketball"],
    note: "NCAAB warehouse desk. Default observation is TRADABLE_YES_BID. NCAAB_FIRST80_P5 is not this desk.",
  },
  {
    id: "WNBA",
    label: "WNBA",
    kind: "league",
    availability: "NOT_AVAILABLE",
    sports: ["basketball"],
    note: "NOT AVAILABLE. Production ROLLER executes NBA, MLB, NCAAB, ATP, and WTA warehouse desks only.",
  },
  {
    id: "MLB",
    label: "MLB",
    kind: "league",
    availability: "IMPLEMENTED",
    sports: ["baseball"],
    note: "MLB warehouse desk. Default observation is TRADABLE_YES_BID. LAST TRADE ≠ YES BID.",
  },
  {
    id: "ATP",
    label: "ATP",
    kind: "league",
    availability: "IMPLEMENTED",
    sports: ["tennis"],
    note: "ATP warehouse desk. Default observation is TRADABLE_YES_BID. LAST TRADE ≠ YES BID. Mixed ATP+WTA fails closed.",
  },
  {
    id: "WTA",
    label: "WTA",
    kind: "league",
    availability: "IMPLEMENTED",
    sports: ["tennis"],
    note: "WTA warehouse desk. Default observation is TRADABLE_YES_BID. LAST TRADE ≠ YES BID. Mixed ATP+WTA fails closed.",
  },

  {
    id: "2023-24",
    label: "2023–24",
    kind: "season",
    availability: "REGISTERED",
    note: "Mapped to the warehouse season id when a dataset exists. Not written onto a frozen lock.",
  },
  {
    id: "2024-25",
    label: "2024–25",
    kind: "season",
    availability: "REGISTERED",
    note: "Mapped to the warehouse season id when a dataset exists. Not written onto a frozen lock.",
  },
  {
    id: "2025-26",
    label: "2025–26",
    kind: "season",
    availability: "IMPLEMENTED",
    note: "Display-aligned with the warehouse ledger. UI seasons are never written onto a lock spec.",
  },
  {
    id: "2026-27",
    label: "2026–27",
    kind: "season",
    availability: "REGISTERED",
    note: "Mapped to the warehouse season id when a dataset exists. Not written onto a frozen lock.",
  },

  { id: "kalshi", label: "Kalshi", kind: "market", availability: "IMPLEMENTED" },
  {
    id: "polymarket",
    label: "Polymarket",
    kind: "market",
    availability: "OPERATION_REQUIRED",
    note: "Last-trade 1-minute history is not tradable top-of-book. Kalshi cannot be substituted automatically.",
  },

  { id: "candles", label: "Candles", kind: "market_data", availability: "IMPLEMENTED" },
  {
    id: "last_trade",
    label: "Last trade",
    kind: "market_data",
    availability: "IMPLEMENTED",
    note: "Selectable second basis. LAST TRADE ≠ YES BID. EV / fees stay DATA_REQUIRED on this basis.",
  },
  {
    id: "tick",
    label: "Tick Data",
    kind: "market_data",
    availability: "DATA_REQUIRED",
    note: "Optional dimension. Running requires acknowledging that tick data is omitted.",
  },
  {
    id: "l2",
    label: "Order Book / L2",
    kind: "market_data",
    availability: "DATA_REQUIRED",
    note: "Optional dimension. Running requires acknowledging that L2 is omitted. L2 is not invented.",
  },

  {
    id: "espn",
    label: "ESPN",
    kind: "pbp",
    availability: "REGISTERED",
    note: "Used for PBP snap alignment when ingested. Not a separate population producer.",
  },
  {
    id: "nba_api",
    label: "NBA API",
    kind: "pbp",
    availability: "REGISTERED",
    note: "Used for PBP snap alignment when ingested. Not a separate population producer.",
  },
  {
    id: "mlb_statsapi",
    label: "MLB StatsAPI",
    kind: "pbp",
    availability: "IMPLEMENTED",
    note: "Used for MLB PIT snap alignment. Not a prediction. Scores come from the event row, not the box.",
  },
  {
    id: "mcp",
    label: "Match Charting Project",
    kind: "pbp",
    availability: "REGISTERED",
    note: "Sequence-only tennis PBP. No point timestamps. pit_joinable = false. CC BY-NC-SA 4.0 NonCommercial.",
  },
  { id: "kenpom", label: "KenPom", kind: "pbp", availability: "DATA_REQUIRED", note: DATA_REQUIRED_COPY },
  { id: "ncaa", label: "NCAA", kind: "pbp", availability: "DATA_REQUIRED", note: DATA_REQUIRED_COPY },
  { id: "wnba_pbp", label: "WNBA", kind: "pbp", availability: "DATA_REQUIRED", note: DATA_REQUIRED_COPY },

  { id: "first_touch", label: "First Touch", kind: "entry", availability: "IMPLEMENTED" },
  { id: "second_touch", label: "Second Touch", kind: "entry", availability: "IMPLEMENTED" },
  { id: "third_touch", label: "Third Touch", kind: "entry", availability: "IMPLEMENTED" },
  { id: "fourth_touch", label: "Fourth Touch", kind: "entry", availability: "IMPLEMENTED" },
  { id: "nth_touch", label: "Nth Touch", kind: "entry", availability: "IMPLEMENTED" },
  { id: "cross", label: "Cross", kind: "entry", availability: "IMPLEMENTED", note: "First tradable close-cross of P. Up: prior < P ≤ current. Down: prior > P ≥ current. 80→80 is not a cross." },
  { id: "break", label: "Break", kind: "entry", availability: "IMPLEMENTED", note: "Cross that finishes strictly beyond P. 79→80 is Cross, not Break." },
  { id: "reversion", label: "Reversion", kind: "entry", availability: "IMPLEMENTED", note: "Cross P, then later cross back to the original side. Ordered. 79→81→80 is not complete." },
  { id: "bounce", label: "Bounce", kind: "entry", availability: "IMPLEMENTED", note: "Touch then reverse on the next tradable candle. Timestamp = confirmation candle. 79→80→79 and 81→80→81 count." },
  { id: "recovery", label: "Recovery", kind: "entry", availability: "IMPLEMENTED", note: "Adverse excursion away from P, then return cross. Standalone Recovery requires direction. Equality at P does not invent a side." },
  { id: "above", label: "Above", kind: "entry", availability: "IMPLEMENTED", note: "First tradable close strictly above P. Equality is not Above." },
  { id: "below", label: "Below", kind: "entry", availability: "IMPLEMENTED", note: "First tradable close strictly below P. Equality is not Below." },
  { id: "maximum_touch", label: "Maximum Touch", kind: "entry", availability: "IMPLEMENTED", note: "First bar where running max of tradable close ≥ P over the full game/ticker series. Then period/clock filter." },
  { id: "minimum_touch", label: "Minimum Touch", kind: "entry", availability: "IMPLEMENTED", note: "First bar where running min of tradable close ≤ P over the full game/ticker series. Then period/clock filter." },

  { id: "reach", label: "Reach Price", kind: "exit_path", availability: "IMPLEMENTED" },
  { id: "drop_to", label: "Drop To", kind: "exit_path", availability: "IMPLEMENTED" },
  { id: "rise_to", label: "Rise To", kind: "exit_path", availability: "IMPLEMENTED" },
  {
    id: "bounce",
    label: "Bounce",
    kind: "exit_path",
    availability: "IMPLEMENTED",
    note: "Post-entry Bounce on tradable close. Up: prior < P ≤ current and next < P. Missing next does not fire. Timestamp = confirmation bar.",
  },
  { id: "recover", label: "Recover", kind: "exit_path", availability: "IMPLEMENTED" },
  {
    id: "revert",
    label: "Revert",
    kind: "exit_path",
    availability: "IMPLEMENTED",
    note: "Post-entry Reversion: cross P, then later cross back. 79→81→80 is not complete. Timestamp = event-2 bar.",
  },
  {
    id: "maximum_move",
    label: "Maximum Move",
    kind: "exit_path",
    availability: "IMPLEMENTED",
    note: "First post-entry bar where running max(close) ≥ P. Close-only; coincides with Reach on a single barrier.",
  },
  {
    id: "minimum_move",
    label: "Minimum Move",
    kind: "exit_path",
    availability: "IMPLEMENTED",
    note: "First post-entry bar where running min(close) ≤ P. Close-only; coincides with Drop-to on a single barrier.",
  },
  {
    id: "never_reach",
    label: "Never Reach",
    kind: "exit_path",
    availability: "IMPLEMENTED",
    note: "Complement of Reach. Does not fire mid-path. Resolves at hold-to-settlement if present, else last post-entry tradable bar.",
  },

  { id: "yes", label: "YES", kind: "exit_terminal", availability: "IMPLEMENTED" },
  { id: "no", label: "NO", kind: "exit_terminal", availability: "IMPLEMENTED" },
  { id: "both", label: "BOTH", kind: "exit_terminal", availability: "IMPLEMENTED" },
  {
    id: "hold_expiration_win",
    label: "Hold to expiration · WIN",
    kind: "exit_terminal",
    availability: "IMPLEMENTED",
    note: "Kalshi settlement YES. Missing settlement is counted, not inferred.",
  },
  {
    id: "hold_expiration_loss",
    label: "Hold to expiration · LOSS",
    kind: "exit_terminal",
    availability: "IMPLEMENTED",
    note: "Kalshi settlement NO. Missing settlement is counted, not inferred.",
  },

  {
    id: "horizon_game_win",
    label: "Game clock · WIN",
    kind: "exit_horizon",
    availability: "IMPLEMENTED",
    note: "Requires +N game minutes. First later tradable bar at that horizon. WIN if yes_bid_close ≥ 50¢. Candle observation, not settlement. Incomplete clock is not Reach-only.",
  },
  {
    id: "horizon_game_loss",
    label: "Game clock · LOSS",
    kind: "exit_horizon",
    availability: "IMPLEMENTED",
    note: "First later tradable bar at +N game minutes. LOSS if yes_bid_close < 50¢. Candle observation, not settlement.",
  },
  {
    id: "horizon_market_win",
    label: "Market clock · WIN",
    kind: "exit_horizon",
    availability: "IMPLEMENTED",
    note: "First later tradable bar at +N wall-clock minutes. WIN if yes_bid_close ≥ 50¢. Candle observation, not settlement.",
  },
  {
    id: "horizon_market_loss",
    label: "Market clock · LOSS",
    kind: "exit_horizon",
    availability: "IMPLEMENTED",
    note: "First later tradable bar at +N wall-clock minutes. LOSS if yes_bid_close < 50¢. Candle observation, not settlement.",
  },
];

export function catalogByKind(kind: CatalogKind): CatalogItem[] {
  return CATALOG.filter((c) => c.kind === kind);
}

export function catalogItem(id: string, kind?: CatalogKind): CatalogItem | undefined {
  return CATALOG.find((c) => c.id === id && (kind == null || c.kind === kind));
}

export function availabilityLabel(a: Availability): string {
  if (a === "IMPLEMENTED") return "SUPPORTED";
  if (a === "REGISTERED") return "RECOGNIZED";
  if (a === "COMING_SOON") return "DATA REQUIRED";
  if (a === "DATA_REQUIRED") return "DATA REQUIRED";
  if (a === "OPERATION_REQUIRED") return "OPERATION REQUIRED";
  return "UNAVAILABLE";
}
