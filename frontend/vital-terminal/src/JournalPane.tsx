type Props = {
  logs: string[];
  status?: string | null;
  unit?: string | null;
  detail?: string | null;
};

export default function JournalPane({ logs, status, unit, detail }: Props) {
  return (
    <section className="vital-card" aria-label="Journal">
      <p className="ws-kicker">Journal</p>
      <p className="muted small">
        {unit || "unit unread"} · {status || "OBSERVATION_UNAVAILABLE"}
        {detail ? ` · ${detail}` : ""}
      </p>
      {logs.length === 0 ? (
        <p className="muted small">OBSERVATION_UNAVAILABLE</p>
      ) : (
        <ul className="vital-journal">
          {logs.slice(-40).map((line, index) => (
            <li key={`${index}-${line.slice(0, 24)}`} className="muted small">
              {line}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
