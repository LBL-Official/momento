import { metricText, moneyText, type VitalBankrollAccount, type VitalDemoAccount, type VitalKalshi } from "./api/vitalApi";

type Props = {
  title: string;
  environment: "DEMO" | "PRODUCTION";
  account?: VitalBankrollAccount | VitalDemoAccount | null;
  kalshi?: VitalKalshi | null;
};

export default function BookPane({ title, environment, account, kalshi }: Props) {
  const balance =
    account && "top_level_cents" in account ? moneyText(account.top_level_cents) : "OBSERVATION_UNAVAILABLE";
  const unread = balance === "UNAVAILABLE" || balance === "OBSERVATION_UNAVAILABLE" || !account;
  const shard =
    account && "mlb_shard_cents" in account ? moneyText(account.mlb_shard_cents) : "OBSERVATION_UNAVAILABLE";
  const catchAll =
    account && "catch_all_shard_cents" in account
      ? moneyText(account.catch_all_shard_cents)
      : null;
  return (
    <section className={`vital-card vital-book-card is-${environment.toLowerCase()}`} aria-label={`${environment} book`}>
      <div className="vital-row-head">
        <p className="ws-kicker">{title}</p>
        <span className="vital-chip">{environment}</span>
      </div>
      <p className="vital-book-hero">
        {unread ? account?.top_level_cents?.status || kalshi?.status || "OBSERVATION_UNAVAILABLE" : balance}
      </p>
      <dl className="vital-mini-dl">
        <div>
          <dt>Sports shard 3</dt>
          <dd>{shard}</dd>
        </div>
        {catchAll ? (
          <div>
            <dt>Catch-all 0</dt>
            <dd>{catchAll}</dd>
          </div>
        ) : null}
        <div>
          <dt>Pos / fills</dt>
          <dd>
            {kalshi?.status === "CONFIRMED" && kalshi.position_n != null
              ? String(kalshi.position_n)
              : "UNREAD"}
            {" / "}
            {kalshi?.status === "CONFIRMED" && kalshi.fill_n != null ? String(kalshi.fill_n) : "UNREAD"}
          </dd>
        </div>
      </dl>
      <p className="muted small">
        Kalshi {kalshi?.status || "OBSERVATION_UNAVAILABLE"}
        {kalshi?.observed_at ? ` · ${kalshi.observed_at}` : ""}
      </p>
      <p className="muted small">
        {environment === "PRODUCTION" ? "Demo cents are not mixed in." : "Production cents are not mixed in."}{" "}
        Top-level is not sports collateral. Missing is never $0.
      </p>
      {account && "source" in account ? (
        <p className="vital-bot-meta">Source {metricText(account.source)}</p>
      ) : null}
    </section>
  );
}
