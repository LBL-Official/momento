import { metricText, moneyText, type VitalKalshiHealth } from "./api/vitalApi";

type Props = {
  health: VitalKalshiHealth | null;
};

export default function KalshiHealth({ health }: Props) {
  const unread = !health || health.status !== "CONFIRMED";
  return (
    <section className="vital-card" aria-label="Kalshi health">
      <p className="ws-kicker">Kalshi health</p>
      <p className="muted small">
        Query telemetry. Not a second OMS. A Demo submit is not a fill.
      </p>
      <dl className="ws-universe-dl">
        <div>
          <dt>Status</dt>
          <dd>{health?.status || "UNREAD"}</dd>
        </div>
        <div>
          <dt>Environment</dt>
          <dd>{health?.environment || "UNREAD"}</dd>
        </div>
        <div>
          <dt>Last series</dt>
          <dd>{health?.last_series || (health?.status === "CONFIRMED" ? "none" : "UNREAD")}</dd>
        </div>
        <div>
          <dt>Last HTTP</dt>
          <dd>{health?.last_http_class != null ? String(health.last_http_class) : health?.status === "CONFIRMED" ? "none" : "UNREAD"}</dd>
        </div>
        <div>
          <dt>Last reject</dt>
          <dd>{health?.last_reject_code || (health?.status === "CONFIRMED" ? "none" : "UNREAD")}</dd>
        </div>
        <div>
          <dt>Sports shard 3</dt>
          <dd>
            {health?.mlb_shard_cents != null
              ? moneyText({ status: "CONFIRMED", value: health.mlb_shard_cents })
              : health?.shard_status === "OBSERVATION_UNAVAILABLE"
                ? "UNREAD"
                : health?.shard_status || "UNREAD"}
          </dd>
        </div>
        <div>
          <dt>Last poll</dt>
          <dd>{health?.last_poll_ts || (health?.status === "CONFIRMED" ? "none" : "UNREAD")}</dd>
        </div>
        <div>
          <dt>Book</dt>
          <dd>{health?.book_status || metricText({ status: unread ? "OBSERVATION_UNAVAILABLE" : "CONFIRMED" })}</dd>
        </div>
      </dl>
      {health?.detail ? <p className="muted small">{health.detail}</p> : null}
    </section>
  );
}
