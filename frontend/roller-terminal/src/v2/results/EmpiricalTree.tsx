import type { ReactNode } from "react";
import type { EmpiricalPartition, PartitionCell } from "./partitionTypes";
import { cellByKey, jointIsMeasured, pathMarginOf } from "./partitionTypes";

type Props = {
  partition: EmpiricalPartition;
  onInspectCell: (cell: PartitionCell) => void;
  missingLabel?: string;
};

function Branch({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="v2-tree-branch">
      <div className="v2-tree-node">{title}</div>
      <div className="v2-tree-children">{children}</div>
    </div>
  );
}

function Leaf({
  label,
  n,
  onClick,
}: {
  label: string;
  n: number | string;
  onClick?: () => void;
}) {
  if (!onClick) {
    return (
      <div className="v2-tree-leaf is-static">
        <span>{label}</span>
        <span className="evidence">{n}</span>
      </div>
    );
  }
  return (
    <button type="button" className="v2-tree-leaf" onClick={onClick}>
      <span>{label}</span>
      <span className="evidence">{n}</span>
    </button>
  );
}

export default function EmpiricalTree({
  partition,
  onInspectCell,
  missingLabel = "missing terminal settlement",
}: Props) {
  const margin = pathMarginOf(partition);
  const joint = jointIsMeasured(partition);
  const tt = cellByKey(partition, "T_AND_W");
  const tf = cellByKey(partition, "T_AND_NOT_W");
  const ft = cellByKey(partition, "NOT_T_AND_W");
  const ff = cellByKey(partition, "NOT_T_AND_NOT_W");
  const pathTrue = margin?.true ?? (tt?.n ?? 0) + (tf?.n ?? 0);
  const pathFalse = margin?.false ?? (ft?.n ?? 0) + (ff?.n ?? 0);
  const termYes = (tt?.n ?? 0) + (ft?.n ?? 0);
  const termNo = (tf?.n ?? 0) + (ff?.n ?? 0);
  const missing = partition.n_missing ?? 0;
  const n = partition.n_population ?? margin?.available ?? pathTrue + pathFalse;

  const inspectPath = (pathTrueFlag: boolean, count: number) => {
    onInspectCell({
      key: pathTrueFlag ? "PATH_TRUE" : "PATH_FALSE",
      path_true: pathTrueFlag,
      n: count,
    });
  };

  return (
    <section className="v2-empirical-tree">
      <h2>Population decomposition</h2>
      <p className="muted small">
        {joint
          ? `Settled joint n = ${(tt?.n ?? 0) + (tf?.n ?? 0) + (ft?.n ?? 0) + (ff?.n ?? 0)} of N = ${n}. Not a partition of all observations. PATH FALSE ≠ LOSS.`
          : "Path margin from this run. PATH FALSE ≠ LOSS. Missing settlement is not inferred from path WIN."}
      </p>
      <div className="v2-tree-columns">
        <div>
          <h3>Path decomposition</h3>
          <Branch title={`Population · N = ${n}`}>
            <Branch title={`Path TRUE · ${pathTrue}`}>
              {joint && tt ? (
                <Leaf label="Terminal YES" n={tt.n} onClick={() => onInspectCell(tt)} />
              ) : null}
              {joint && tf ? (
                <Leaf label="Terminal NO" n={tf.n} onClick={() => onInspectCell(tf)} />
              ) : (
                <Leaf
                  label="Hold-to-YES path"
                  n={termYes}
                  onClick={() => inspectPath(true, pathTrue)}
                />
              )}
            </Branch>
            <Branch title={`Path FALSE · ${pathFalse} · not LOSS_EXIT`}>
              {joint && ft ? (
                <Leaf label="Terminal YES" n={ft.n} onClick={() => onInspectCell(ft)} />
              ) : null}
              {joint && ff ? (
                <Leaf label="Terminal NO" n={ff.n} onClick={() => onInspectCell(ff)} />
              ) : (
                <Leaf
                  label="Hold-to-YES path"
                  n={termNo}
                  onClick={() => inspectPath(false, pathFalse)}
                />
              )}
            </Branch>
          </Branch>
        </div>
        <div>
          <h3>Terminal decomposition</h3>
          {joint ? (
            <Branch title={`Population · N = ${n}`}>
              <Branch title={`Observed settlement · ${termYes + termNo}`}>
                <Branch title={`Terminal YES · ${termYes}`}>
                  {tt ? (
                    <Leaf label="Path TRUE" n={tt.n} onClick={() => onInspectCell(tt)} />
                  ) : null}
                  {ft ? (
                    <Leaf label="Path FALSE" n={ft.n} onClick={() => onInspectCell(ft)} />
                  ) : null}
                </Branch>
                <Branch title={`Terminal NO · ${termNo}`}>
                  {tf ? (
                    <Leaf label="Path TRUE" n={tf.n} onClick={() => onInspectCell(tf)} />
                  ) : null}
                  {ff ? (
                    <Leaf label="Path FALSE" n={ff.n} onClick={() => onInspectCell(ff)} />
                  ) : null}
                </Branch>
              </Branch>
              {missing ? <Leaf label={missingLabel} n={missing} /> : null}
            </Branch>
          ) : (
            <Branch title={`Population · N = ${n}`}>
              <Leaf label="Terminal YES" n={termYes} />
              <Leaf label="Terminal NO" n={termNo} />
              {missing ? <Leaf label={missingLabel} n={missing} /> : null}
            </Branch>
          )}
        </div>
      </div>
    </section>
  );
}
