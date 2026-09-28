import type { AnswerResult } from "./ResultsAnswer";

export type RateParts = {
  name: string;
  rate: number | null;
  trueN: number | null;
  avail: number | null;
  status?: string;
};

export function findMeasurement(result: AnswerResult | null | undefined, names: string[]) {
  if (!result?.measurements) return undefined;
  for (const name of names) {
    const m = result.measurements.find((x) => x.name === name);
    if (m) return m;
  }
  return undefined;
}

export function ratePartsFromNames(result: AnswerResult | null | undefined, names: string[]): RateParts {
  const m = findMeasurement(result, names);
  const name = m?.name || names[0] || "";
  if (!m || m.status === "ABSENT") {
    return { name, rate: null, trueN: null, avail: null, status: m?.status };
  }
  const d = m.detail || {};
  const trueN = typeof d.count_true === "number" ? d.count_true : null;
  const avail = typeof d.count_available === "number" ? d.count_available : null;
  if (avail != null && avail <= 0) {
    return { name, rate: null, trueN: null, avail: null, status: m.status };
  }
  const rate =
    typeof m.value === "number" && Number.isFinite(m.value)
      ? m.value
      : trueN != null && avail != null && avail > 0
        ? trueN / avail
        : null;
  return { name, rate, trueN, avail, status: m.status };
}

export function pathRate(result: AnswerResult | null | undefined): RateParts {
  return ratePartsFromNames(result, ["path_rate", "t40_rate"]);
}

export function terminalRate(result: AnswerResult | null | undefined): RateParts {
  return ratePartsFromNames(result, ["kalshi_yes_rate", "terminal_yes_rate"]);
}

export function measurementNumber(result: AnswerResult | null | undefined, name: string): number | null {
  const m = result?.measurements?.find((x) => x.name === name && x.status !== "ABSENT");
  return typeof m?.value === "number" && Number.isFinite(m.value) ? m.value : null;
}
