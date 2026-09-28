import { asObj, type Spec } from "../../researchTypes";
import type { RecognizedIntent } from "./recognizedIntent";

export type ChipHonesty = "required" | "optional" | "implied" | "recognized";

export type DefineChip = {
  id: string;
  label: string;
  honesty: ChipHonesty;
  /** Backend template to load. Never hand-build FIRST80. */
  templateId?: string;
  recognized?: boolean;
};

export type QuestionBlock = {
  n: number;
  id: string;
  title: string;
  honesty: ChipHonesty;
  hint: string;
  chips: DefineChip[];
};

export function lockedTemplateKind(spec: Spec): "FIRST80_Q3" | "NCAAB_FIRST80_P5" | null {
  const defs = asObj(spec.definition_versions);
  if (typeof defs.NCAAB_FIRST80_P5 === "string") return "NCAAB_FIRST80_P5";
  if (typeof defs.FIRST80 === "string") return "FIRST80_Q3";
  return null;
}

export function defineBlocks(spec: Spec, intent: RecognizedIntent): QuestionBlock[] {
  const lock = lockedTemplateKind(spec);
  const nba = lock === "FIRST80_Q3";
  const ncaab = lock === "NCAAB_FIRST80_P5";
  const customized = intent.customizeUnlocked;

  return [
    {
      n: 1,
      id: "sport",
      title: "Sport",
      honesty: "required",
      hint: "Which sport is this question about?",
      chips: [
        { id: "nba", label: "NBA", honesty: nba ? "implied" : "required" },
        { id: "ncaab", label: "NCAAB", honesty: ncaab ? "implied" : "required" },
        { id: "wnba", label: "WNBA", honesty: "recognized", recognized: true },
      ],
    },
    {
      n: 2,
      id: "population",
      title: "Population",
      honesty: "required",
      hint: "Which membership lock are we measuring?",
      chips: [
        {
          id: "FIRST80_Q3",
          label: "FIRST80 · Q3",
          honesty: nba ? "implied" : "required",
          templateId: "FIRST80_Q3",
        },
        {
          id: "NCAAB_FIRST80_P5",
          label: "NCAAB FIRST80 · P5",
          honesty: ncaab ? "implied" : "required",
          templateId: "NCAAB_FIRST80_P5",
        },
        { id: "FIRST80", label: "FIRST80", honesty: "optional" },
        { id: "SECOND80", label: "SECOND80", honesty: "recognized", recognized: true },
        { id: "NTH80", label: "NTH80", honesty: "recognized", recognized: true },
        { id: "SECOND75", label: "SECOND75", honesty: "recognized", recognized: true },
      ],
    },
    {
      n: 3,
      id: "season",
      title: "Season",
      honesty: lock ? "implied" : "optional",
      hint: lock
        ? "Frozen ledger — all membership rows. A custom season is STRUCTURAL and is not applied."
        : "Calendar scope is STRUCTURAL. It is not an implemented filter on a lock.",
      chips: [
        {
          id: "frozen",
          label: "Frozen ledger — all membership rows",
          honesty: lock ? "implied" : "optional",
        },
        { id: "2023-24", label: "2023–24", honesty: "recognized", recognized: true },
        { id: "2024-25", label: "2024–25", honesty: "recognized", recognized: true },
      ],
    },
    {
      n: 4,
      id: "event",
      title: "Event",
      honesty: lock && !customized ? "implied" : "optional",
      hint: lock && !customized
        ? "Implied by the lock. Customize reveals ordinal × touch × 5¢ as overlay unless it is the lock."
        : "Non-lock grid cells are recognized, not constructible.",
      chips: lock
        ? [
            {
              id: "lock-event",
              label: nba ? "FIRST touch of 80¢" : "FIRST80 · P5 lock",
              honesty: "implied",
            },
            { id: "SECOND80", label: "SECOND80", honesty: "recognized", recognized: true },
            { id: "FIRST75", label: "FIRST75", honesty: "recognized", recognized: true },
            { id: "FIRST83", label: "FIRST83", honesty: "recognized", recognized: true },
          ]
        : [
            { id: "FIRST80", label: "FIRST80", honesty: "optional" },
            { id: "SECOND80", label: "SECOND80", honesty: "recognized", recognized: true },
          ],
    },
    {
      n: 5,
      id: "when",
      title: "When",
      honesty: nba ? "implied" : "optional",
      hint: nba
        ? "Q3 is implied on FIRST80 Q3. Other quarters, NCAAB 1H / 1st 10, and multi-window OR live on Entry → Game period — not on this lock sheet."
        : "P5 is implied on the NCAAB lock. 1H / 1st 10 / 2nd 10 and multi-window OR are constructible on Entry → Game period.",
      chips: [
        { id: "Q3", label: "Q3", honesty: nba ? "implied" : "optional" },
        { id: "P5", label: "P5", honesty: ncaab ? "implied" : "optional" },
        { id: "Q1", label: "Q1", honesty: "recognized", recognized: true },
        { id: "Q4", label: "Q4", honesty: "recognized", recognized: true },
        { id: "OT", label: "OT", honesty: "recognized", recognized: true },
      ],
    },
    {
      n: 6,
      id: "prior",
      title: "Prior path",
      honesty: "optional",
      hint: "Default NONE. Reversion / drop-then-recover is recognized, not constructible.",
      chips: [
        { id: "NONE", label: "NONE", honesty: "optional" },
        { id: "reversion", label: "Reversion", honesty: "recognized", recognized: true },
        { id: "drop10", label: "10¢ down", honesty: "recognized", recognized: true },
      ],
    },
    {
      n: 7,
      id: "after",
      title: "Afterward",
      honesty: lock ? "implied" : "optional",
      hint: "Default T40 from the template. Bounce / recover is overlay.",
      chips: [
        { id: "T40", label: "T40", honesty: lock ? "implied" : "optional" },
        { id: "bounce", label: "Bounce", honesty: "recognized", recognized: true },
        { id: "recover", label: "Recover", honesty: "recognized", recognized: true },
        { id: "rebound15", label: "15¢ rebound", honesty: "recognized", recognized: true },
      ],
    },
    {
      n: 8,
      id: "terminal",
      title: "Terminal",
      honesty: lock ? "implied" : "optional",
      hint: "Only existing terminal_conditions / kalshi_yes_rate.",
      chips: [
        { id: "YES", label: "Kalshi YES", honesty: lock ? "implied" : "optional" },
        { id: "NO", label: "Kalshi NO", honesty: lock ? "implied" : "optional" },
      ],
    },
  ];
}

export const QUICK_START = [
  {
    id: "FIRST80_Q3",
    label: "FIRST80 · Q3",
    sub: "NBA · n = 290 lock",
    templateId: "FIRST80_Q3",
  },
  {
    id: "NCAAB_FIRST80_P5",
    label: "NCAAB FIRST80 · P5",
    sub: "NCAAB · n = 721 lock",
    templateId: "NCAAB_FIRST80_P5",
  },
] as const;
