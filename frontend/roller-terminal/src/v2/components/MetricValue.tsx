type Props = {
  label: string;
  value: string;
  sub?: string;
  onClick?: () => void;
};

export default function MetricValue({ label, value, sub, onClick }: Props) {
  const inner = (
    <>
      <div className="v2-metric-label">{label}</div>
      <div className="v2-metric-value evidence">{value}</div>
      {sub ? <div className="v2-metric-sub muted">{sub}</div> : null}
    </>
  );
  if (onClick) {
    return (
      <button type="button" className="v2-metric clickable" onClick={onClick}>
        {inner}
      </button>
    );
  }
  return <div className="v2-metric">{inner}</div>;
}
