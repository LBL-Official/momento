/**
 * Hypothetical payoff presets.
 * CANDLE PATH ≠ FILL. Never treat these as empirical P&L.
 *
 * Fee model from FIRST80_REALISTIC_EXIT_FEE_AUDIT_V1 (ESTIMATED):
 * fee = ceil_6dp(M × coef × C × P × (1 − P)), M = 1, SETTLEMENT_FEE = 0
 */

export type FeeLeg = { role: "maker" | "taker" | "none"; coef: number };

export type ScenarioPreset = {
  id: string;
  name: string;
  kind: "empirical" | "hypothetical";
  stopVsHold: "stop" | "hold";
  entryCents: number;
  barrierCents: number | null;
  entryFee: FeeLeg;
  exitFee: FeeLeg;
  builtIn: boolean;
};

export const SCENARIO_STORAGE_KEY = "roller.v2.scenario_presets.v1";

export const BUILTIN_SCENARIOS: ScenarioPreset[] = [
  {
    id: "observed_path",
    name: "Observed path analysis",
    kind: "empirical",
    stopVsHold: "stop",
    entryCents: 80,
    barrierCents: 40,
    entryFee: { role: "none", coef: 0 },
    exitFee: { role: "none", coef: 0 },
    builtIn: true,
  },
  {
    id: "no_fee",
    name: "No-fee scenario",
    kind: "hypothetical",
    stopVsHold: "stop",
    entryCents: 80,
    barrierCents: 40,
    entryFee: { role: "none", coef: 0 },
    exitFee: { role: "none", coef: 0 },
    builtIn: true,
  },
  {
    id: "current_fees",
    name: "Current fees",
    kind: "hypothetical",
    stopVsHold: "stop",
    entryCents: 80,
    barrierCents: 40,
    entryFee: { role: "maker", coef: 0 },
    exitFee: { role: "taker", coef: 0.07 },
    builtIn: true,
  },
  {
    id: "moderate_fees",
    name: "Moderate fees",
    kind: "hypothetical",
    stopVsHold: "stop",
    entryCents: 80,
    barrierCents: 40,
    entryFee: { role: "maker", coef: 0.0175 },
    exitFee: { role: "taker", coef: 0.07 },
    builtIn: true,
  },
  {
    id: "conservative_fees",
    name: "Conservative fees",
    kind: "hypothetical",
    stopVsHold: "stop",
    entryCents: 80,
    barrierCents: 40,
    entryFee: { role: "taker", coef: 0.07 },
    exitFee: { role: "taker", coef: 0.07 },
    builtIn: true,
  },
  {
    id: "hold_settlement",
    name: "Hold to settlement",
    kind: "hypothetical",
    stopVsHold: "hold",
    entryCents: 80,
    barrierCents: null,
    entryFee: { role: "none", coef: 0 },
    exitFee: { role: "none", coef: 0 },
    builtIn: true,
  },
];

export function ceil6dp(n: number): number {
  return Math.ceil(n * 1e6) / 1e6;
}

/** Estimated Kalshi quadratic fee in dollars. */
export function estimatedFee(price: number, coef: number, contracts = 1): number {
  if (coef <= 0) return 0;
  return ceil6dp(1 * coef * contracts * price * (1 - price));
}

export type HypotheticalEv = {
  evPerContract: number | null;
  winPnL: number | null;
  losePnL: number | null;
  stopPnL: number | null;
  assumptions: string[];
  usedJoint: boolean;
};

export function hypotheticalEv(input: {
  preset: ScenarioPreset;
  yesRate: number | null;
  t40Rate: number | null;
  cells?: { tAndW: number; tAndNotW: number; notTAndW: number; notTAndNotW: number; n: number } | null;
  /** When settlement is absent, apply documented 80→40 Model A: (1−q)(+20) + q(−40). */
  modelAPathOnly?: boolean;
}): HypotheticalEv {
  const { preset, yesRate, t40Rate, cells, modelAPathOnly } = input;
  const entry = preset.entryCents / 100;
  const barrier = preset.barrierCents != null ? preset.barrierCents / 100 : null;
  const entryFee = estimatedFee(entry, preset.entryFee.coef);
  const exitFee = barrier != null ? estimatedFee(barrier, preset.exitFee.coef) : 0;
  const assumptions = [
    "HYPOTHETICAL · CANDLE PATH ≠ FILL",
    `Entry ${preset.entryCents}¢ · ${preset.entryFee.role} coef ${preset.entryFee.coef}`,
    preset.stopVsHold === "hold"
      ? "Hold to settlement — no 40¢ stop"
      : `Observe ${preset.barrierCents}¢ as a hypothetical stop, not an executed fill`,
    "Fee model ESTIMATED: ceil_6dp(M × coef × C × P × (1−P)), M=1, SETTLEMENT_FEE=0",
    "EV ≠ EDGE. This is not live performance.",
  ];

  if (preset.kind === "empirical") {
    return {
      evPerContract: null,
      winPnL: null,
      losePnL: null,
      stopPnL: null,
      assumptions: ["EMPIRICAL observed path only. No payoff is implied."],
      usedJoint: false,
    };
  }

  const winPnL = 1 - entry - entryFee;
  const loseHold = -entry - entryFee;
  const stopPnL = barrier != null ? barrier - entry - entryFee - exitFee : null;

  if (preset.stopVsHold === "hold") {
    if (yesRate == null) {
      return { evPerContract: null, winPnL, losePnL: loseHold, stopPnL, assumptions, usedJoint: false };
    }
    return {
      evPerContract: yesRate * winPnL + (1 - yesRate) * loseHold,
      winPnL,
      losePnL: loseHold,
      stopPnL,
      assumptions,
      usedJoint: false,
    };
  }

  if (cells && cells.n > 0 && stopPnL != null) {
    const ev =
      (cells.tAndW * stopPnL +
        cells.tAndNotW * stopPnL +
        cells.notTAndW * winPnL +
        cells.notTAndNotW * loseHold) /
      cells.n;
    return {
      evPerContract: ev,
      winPnL,
      losePnL: loseHold,
      stopPnL,
      assumptions: [
        ...assumptions,
        "Applied to the authoritative joint partition of this run. Stop cells receive the hypothetical 40¢ exit payoff.",
      ],
      usedJoint: true,
    };
  }

  if (modelAPathOnly && t40Rate != null && stopPnL != null) {
    return {
      evPerContract: (1 - t40Rate) * winPnL + t40Rate * stopPnL,
      winPnL,
      losePnL: loseHold,
      stopPnL,
      assumptions: [
        ...assumptions,
        "SETTLEMENT ABSENT. Model A path-only: survive +20¢, stop −40¢. q = observed path rate. CANDLE PATH ≠ FILL.",
      ],
      usedJoint: false,
    };
  }

  if (yesRate == null || t40Rate == null || stopPnL == null) {
    return { evPerContract: null, winPnL, losePnL: loseHold, stopPnL, assumptions, usedJoint: false };
  }
  // Marginal fallback — not a joint. Labeled as such.
  const ev = t40Rate * stopPnL + (1 - t40Rate) * (yesRate * winPnL + (1 - yesRate) * loseHold);
  return {
    evPerContract: ev,
    winPnL,
    losePnL: loseHold,
    stopPnL,
    assumptions: [
      ...assumptions,
      "JOINT PARTITION NOT USED. Marginal fallback mixes path rate and terminal rate and is not a joint.",
    ],
    usedJoint: false,
  };
}

export function loadUserPresets(): ScenarioPreset[] {
  try {
    const raw = localStorage.getItem(SCENARIO_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ScenarioPreset[];
    return Array.isArray(parsed) ? parsed.filter((p) => p && p.id && !p.builtIn) : [];
  } catch {
    return [];
  }
}

export function saveUserPreset(preset: ScenarioPreset): void {
  const next = [...loadUserPresets().filter((p) => p.id !== preset.id), { ...preset, builtIn: false }];
  localStorage.setItem(SCENARIO_STORAGE_KEY, JSON.stringify(next));
}

export function allScenarios(): ScenarioPreset[] {
  return [...BUILTIN_SCENARIOS, ...loadUserPresets()];
}
