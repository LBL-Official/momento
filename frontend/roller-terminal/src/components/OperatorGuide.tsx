import { useState } from "react";

/** Always-available operator directions — presentation only. */
export default function OperatorGuide() {
  const [open, setOpen] = useState(false);

  return (
    <details
      className="operator-guide"
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary>How to use ROLLER · start here</summary>
      <div className="operator-guide-body">
        <ol className="operator-steps">
          <li>
            Go to <strong>Research Object</strong>.
          </li>
          <li>
            <strong>Template → FIRST80_Q3</strong> (or NCAAB_FIRST80_P5).
          </li>
          <li>
            Click <strong>VALIDATE</strong>, wait for Research State → Validation{" "}
            <span className="mono">CURRENT</span> / <span className="mono">RUNNABLE</span>.
          </li>
          <li>
            Click <strong>RUN RESEARCH</strong> → read <strong>Results</strong>.
          </li>
        </ol>
        <p className="muted small">
          INTERPRET needs text · APPLY needs a proposed spec · RUN needs CURRENT+RUNNABLE.
          STALE means re-validate — it is not an error.
        </p>
        <p className="muted small">
          Full directions + tests: <span className="mono">frontend/roller-terminal/README.md</span>
        </p>
      </div>
    </details>
  );
}
