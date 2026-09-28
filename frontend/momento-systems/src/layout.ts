/** Normalized coordinates on the 664×476 reference frame. IDs only — no URLs. */

export const FRAME = { w: 664, h: 476 };

export type BoxGeom = { x: number; y: number; w: number; h: number };

export const BOXES: Record<string, BoxGeom> = {
  database: { x: 16, y: 14, w: 124, h: 22 },
  data_analysis: { x: 16, y: 42, w: 124, h: 22 },
  data_modeling: { x: 168, y: 28, w: 112, h: 22 },
  fair_odds_modeling: { x: 16, y: 82, w: 124, h: 22 },
  in_house_odds_modeling: { x: 16, y: 110, w: 124, h: 22 },
  game_modeling: { x: 168, y: 96, w: 112, h: 22 },
  signal_generation: { x: 308, y: 62, w: 118, h: 22 },
  momento_systems: { x: 454, y: 118, w: 124, h: 22 },
  algorithmic_execution: { x: 308, y: 148, w: 118, h: 34 },
  dynamic_risk_engine: { x: 168, y: 204, w: 112, h: 22 },
  trade_breakdown: { x: 16, y: 190, w: 124, h: 22 },
  position_stratification: { x: 16, y: 218, w: 124, h: 22 },
  position_management: { x: 168, y: 272, w: 112, h: 22 },
  hedging_analysis: { x: 16, y: 258, w: 124, h: 22 },
  relative_value_hedging: { x: 16, y: 286, w: 124, h: 22 },
  system_maintenance: { x: 16, y: 404, w: 124, h: 22 },
  data_ingestion: { x: 168, y: 404, w: 124, h: 22 },
  trade_reconciliation: { x: 16, y: 436, w: 124, h: 22 },
  system_orchestration: { x: 168, y: 436, w: 124, h: 22 },
};

export const EDGES: [string, string][] = [
  ["database", "data_modeling"],
  ["data_analysis", "data_modeling"],
  ["fair_odds_modeling", "game_modeling"],
  ["in_house_odds_modeling", "game_modeling"],
  ["data_modeling", "signal_generation"],
  ["game_modeling", "signal_generation"],
  ["trade_breakdown", "dynamic_risk_engine"],
  ["position_stratification", "dynamic_risk_engine"],
  ["hedging_analysis", "position_management"],
  ["relative_value_hedging", "position_management"],
  ["dynamic_risk_engine", "algorithmic_execution"],
  ["position_management", "algorithmic_execution"],
  ["signal_generation", "momento_systems"],
  ["algorithmic_execution", "momento_systems"],
];

/** Locked-quadrant placement. North stays enlarged and sits in the bracket slot beside signal generation and algorithmic execution. The four infrastructure boxes stay centered below. */
export const LOCK_BOXES: Record<string, BoxGeom> = {
  ...BOXES,
  signal_generation: { x: 246, y: 62, w: 118, h: 22 },
  algorithmic_execution: { x: 246, y: 148, w: 118, h: 34 },
  momento_systems: { x: 376, y: 95, w: 280, h: 48 },
  system_maintenance: { x: 72, y: 376, w: 248, h: 42 },
  data_ingestion: { x: 344, y: 376, w: 248, h: 42 },
  trade_reconciliation: { x: 72, y: 426, w: 248, h: 42 },
  system_orchestration: { x: 344, y: 426, w: 248, h: 42 },
};

export function center(box: BoxGeom): { x: number; y: number } {
  return { x: box.x + box.w / 2, y: box.y + box.h / 2 };
}
