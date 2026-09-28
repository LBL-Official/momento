/** Types for authoritative empirical_partition from the executor. */

export type PartitionCell = {
  key: string;
  path_true?: boolean;
  terminal_true?: boolean;
  n: number;
};

export type PathMargin = {
  true: number;
  false: number;
  available: number;
};

export type EmpiricalPartition = {
  status?: "COMPLETE" | "UNAVAILABLE" | string;
  reason?: string | null;
  axes?: { id: string; field: string; true_label: string; false_label: string }[];
  cells?: PartitionCell[];
  n_population?: number;
  n_joint_available?: number;
  n_missing?: number;
  path_margin?: PathMargin;
  joint_measured?: boolean;
};

export function jointIsMeasured(part: EmpiricalPartition | null | undefined): boolean {
  if (!part || part.status !== "COMPLETE") return false;
  if (part.joint_measured === true) return true;
  if (part.joint_measured === false) return false;
  return (part.n_joint_available ?? 0) > 0;
}

export function pathMarginOf(part: EmpiricalPartition | null | undefined): PathMargin | null {
  const m = part?.path_margin;
  if (m && typeof m.available === "number" && m.available > 0) return m;
  return null;
}

export type DisplayMode = "count" | "population_pct" | "conditional_pct";

export type ConditioningDirection = "path_to_terminal" | "terminal_to_path";

export function cellByKey(
  part: EmpiricalPartition | null | undefined,
  key: string,
): PartitionCell | undefined {
  return part?.cells?.find((c) => c.key === key);
}

export function fmtPct(n: number, d: number): string {
  if (d <= 0) return "—";
  return `${((n / d) * 100).toFixed(1)}%`;
}

export function cellDisplay(
  cell: PartitionCell,
  mode: DisplayMode,
  part: EmpiricalPartition,
  direction: ConditioningDirection,
): { value: string; denominatorLabel: string } {
  const N = part.n_population ?? 0;
  if (mode === "count") {
    return { value: String(cell.n), denominatorLabel: "observations in cell" };
  }
  if (mode === "population_pct") {
    return {
      value: fmtPct(cell.n, N),
      denominatorLabel: `of population N = ${N}`,
    };
  }
  // Conditional — denominator by conditioning axis
  const cells = part.cells ?? [];
  if (direction === "path_to_terminal") {
    // P(W | T40) or P(¬W | T40) etc. — denom = all cells with same path_true
    const denom = cells
      .filter((c) => c.path_true === cell.path_true)
      .reduce((s, c) => s + c.n, 0);
    return {
      value: fmtPct(cell.n, denom),
      denominatorLabel: cell.path_true
        ? `of PATH TRUE (n = ${denom}) · P(terminal | path)`
        : `of PATH FALSE (n = ${denom}) · P(terminal | path)`,
    };
  }
  const denom = cells
    .filter((c) => c.terminal_true === cell.terminal_true)
    .reduce((s, c) => s + c.n, 0);
  return {
    value: fmtPct(cell.n, denom),
    denominatorLabel: cell.terminal_true
      ? `of TERMINAL YES (n = ${denom}) · P(path | terminal)`
      : `of TERMINAL NO (n = ${denom}) · P(path | terminal)`,
  };
}

export function cellTitle(cell: PartitionCell): string {
  if (cell.key === "PATH_TRUE") return "PATH TRUE";
  if (cell.key === "PATH_FALSE") return "PATH FALSE";
  const path = cell.path_true ? "PATH TRUE" : "PATH FALSE";
  const term = cell.terminal_true ? "TERMINAL YES" : "TERMINAL NO";
  return `${path} ∩ ${term}`;
}
