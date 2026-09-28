import { useState } from "react";
import {
  cellByKey,
  cellDisplay,
  cellTitle,
  jointIsMeasured,
  pathMarginOf,
  type ConditioningDirection,
  type DisplayMode,
  type EmpiricalPartition,
  type PartitionCell,
} from "./partitionTypes";

type Props = {
  partition: EmpiricalPartition;
  onInspectCell: (cell: PartitionCell) => void;
  missingLabel?: string;
};

const ORDER = ["T_AND_W", "T_AND_NOT_W", "NOT_T_AND_W", "NOT_T_AND_NOT_W"] as const;

export default function EmpiricalStateSpace({
  partition,
  onInspectCell,
  missingLabel = "missing terminal settlement",
}: Props) {
  const [mode, setMode] = useState<DisplayMode>("count");
  const [direction, setDirection] = useState<ConditioningDirection>("path_to_terminal");
  const margin = pathMarginOf(partition);
  const joint = jointIsMeasured(partition);
  const N = partition.n_population ?? margin?.available ?? 0;

  if (partition.status !== "COMPLETE" && !margin) {
    return (
      <section className="v2-state-space unavailable">
        <h2>Empirical state space</h2>
        <p className="v2-lede">
          {partition.reason ||
            "JOINT PARTITION NOT CURRENTLY MEASURED. Marginal measurements may still be available."}
        </p>
      </section>
    );
  }

  const renderJointCell = (key: string) => {
    const cell = cellByKey(partition, key);
    if (!cell) return null;
    const shown = cellDisplay(cell, mode, partition, direction);
    return (
      <button
        type="button"
        key={key}
        className="v2-state-cell"
        onClick={() => onInspectCell(cell)}
      >
        <div className="v2-state-cell-value evidence">{shown.value}</div>
        <div className="v2-state-cell-title">{cellTitle(cell)}</div>
        <div className="muted small">{shown.denominatorLabel}</div>
        <div className="v2-kicker">Click to inspect</div>
      </button>
    );
  };

  const renderPathCell = (key: "PATH_TRUE" | "PATH_FALSE", n: number) => {
    const cell: PartitionCell = {
      key,
      path_true: key === "PATH_TRUE",
      n,
    };
    const denom = margin?.available ?? N;
    const value =
      mode === "count" ? String(n) : denom > 0 ? `${((n / denom) * 100).toFixed(1)}%` : "—";
    return (
      <button
        type="button"
        className="v2-state-cell"
        onClick={() => onInspectCell(cell)}
      >
        <div className="v2-state-cell-value evidence">{value}</div>
        <div className="v2-state-cell-title">{key === "PATH_TRUE" ? "PATH TRUE" : "PATH FALSE"}</div>
        <div className="muted small">
          {mode === "count" ? "observations in path margin" : `of path-available N = ${denom}`}
        </div>
        <div className="v2-kicker">Click to inspect</div>
      </button>
    );
  };

  return (
    <section className="v2-state-space">
      <div className="v2-state-space-head">
        <div>
          <h2>Empirical state space</h2>
          <p className="muted">
            {joint
              ? `Settled joint n = ${partition.n_joint_available ?? 0} of N = ${N}`
              : `Path margin · N = ${margin?.available ?? N}`}
            {partition.n_missing ? ` · ${partition.n_missing} ${missingLabel}` : ""}
          </p>
          <p className="muted small">
            {joint
              ? "PARTITION OF OBSERVED SETTLEMENTS · not a partition of all N · PATH FALSE ≠ LOSS · PATH WIN ≠ TERMINAL YES"
              : "Path margin is measured. PATH FALSE ≠ LOSS. Missing settlement is not inferred from path WIN."}
          </p>
        </div>
        <div className="v2-display-modes">
          <div className="v2-kicker">Display</div>
          <div className="v2-mode-nav">
            {(
              [
                ["count", "Count"],
                ["population_pct", "Population %"],
                ...(joint ? ([["conditional_pct", "Conditional %"]] as const) : []),
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={mode === id ? "v2-mode on" : "v2-mode"}
                onClick={() => setMode(id)}
              >
                {label}
              </button>
            ))}
          </div>
          {joint && mode === "conditional_pct" ? (
            <div className="v2-mode-nav">
              <button
                type="button"
                className={direction === "path_to_terminal" ? "v2-mode on" : "v2-mode"}
                onClick={() => setDirection("path_to_terminal")}
              >
                Path → Terminal
              </button>
              <button
                type="button"
                className={direction === "terminal_to_path" ? "v2-mode on" : "v2-mode"}
                onClick={() => setDirection("terminal_to_path")}
              >
                Terminal → Path
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {joint ? (
        <div className="v2-state-grid-labels">
          <div />
          <div className="v2-kicker">Terminal YES</div>
          <div className="v2-kicker">Terminal NO</div>
          <div className="v2-kicker">Path TRUE</div>
          {renderJointCell(ORDER[0])}
          {renderJointCell(ORDER[1])}
          <div className="v2-kicker">Path FALSE</div>
          {renderJointCell(ORDER[2])}
          {renderJointCell(ORDER[3])}
        </div>
      ) : (
        <div className="v2-state-grid v2-state-grid-path">
          {renderPathCell("PATH_TRUE", margin?.true ?? 0)}
          {renderPathCell("PATH_FALSE", margin?.false ?? 0)}
        </div>
      )}
    </section>
  );
}
