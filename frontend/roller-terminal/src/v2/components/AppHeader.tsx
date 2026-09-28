import type { HumanStatus } from "../researchStatus";

type Props = {
  status: HumanStatus;
  onOpenDocs: () => void;
  onOpenSuperASI?: () => void;
  onOpenVital?: () => void;
  /** The ROLLER mark always returns to the start of the research process. */
  onOpenHome?: () => void;
};

/** Maps the existing research status kind onto an instrument signal tint.
 *  Presentation only — the semantic status text is unchanged. */
const SIGNAL: Record<HumanStatus["kind"], string> = {
  ready: "live",
  review: "hold",
  attention: "blocked",
  idle: "idle",
};

export default function AppHeader({ status, onOpenDocs, onOpenSuperASI, onOpenVital, onOpenHome }: Props) {
  return (
    <header className="ws-header">
      <button
        type="button"
        className="mm-masthead-brand"
        onClick={onOpenHome}
        aria-label="ROLLER Research Terminal — go to Quick Start"
      >
        <img
          className="mm-mark"
          src="/brand/momento-m-mark.png"
          alt=""
          width={26}
          height={26}
          decoding="async"
        />
        <span className="mm-wordmark">
          <span className="mm-wordmark-product">Roller</span>
          <span className="mm-wordmark-rule" aria-hidden />
          <span className="mm-wordmark-sub">Research Terminal</span>
        </span>
      </button>

      <div className="mm-masthead-org">Momento Systems</div>

      <div className="mm-status-strip">
        <div className="mm-status-item">
          <span className="mm-status-key">Universe</span>
          <span className="mm-status-value is-strong">BBALL1</span>
        </div>
        <div className="mm-status-item">
          <span className="mm-status-key">Information</span>
          <span className="mm-status-value">POINT-IN-TIME</span>
        </div>
        {onOpenSuperASI ? (
          <div className="mm-status-item">
            <span className="mm-status-key">Downstream</span>
            <button type="button" className="mm-status-value" onClick={onOpenSuperASI}>
              SUPERASI
            </button>
          </div>
        ) : null}
        {onOpenVital ? (
          <div className="mm-status-item">
            <span className="mm-status-key">Execution</span>
            <button type="button" className="mm-status-value" onClick={onOpenVital}>
              VITAL
            </button>
          </div>
        ) : null}
        <div className="mm-status-item">
          <span className="mm-status-key">System</span>
          <span className="mm-status-value is-strong" title={status.detail}>
            <span className={`mm-signal ${SIGNAL[status.kind]}`} aria-hidden />
            {status.title}
          </span>
        </div>
        <button type="button" className="mm-help" onClick={onOpenDocs} aria-label="Open docs">
          ?
        </button>
      </div>
    </header>
  );
}
