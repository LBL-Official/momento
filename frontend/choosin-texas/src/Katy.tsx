import { useEffect, useState, type MouseEvent } from "react";
import { UniverseError, fetchKaty, fetchKatyExperiment } from "./api";
import { text } from "./text";

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

function money(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "UNAVAILABLE";
  return value.toFixed(2);
}

function buckets(value: unknown): string {
  if (!value || typeof value !== "object") return "UNAVAILABLE";
  return Object.entries(value as Record<string, unknown>)
    .map(([key, count]) => `${key}:${text(count)}`)
    .join(" ");
}

type Book = {
  book?: string;
  n_trades?: number;
  n_run_mark_reached?: number;
  n_in_price_band?: number;
  n_hedge_scenario?: number;
  n_hedge_losers?: number;
  n_hedge_winners?: number;
  n_hold_in_band?: number;
  n_ev_unavailable_in_band?: number;
  n_not_underwater?: number;
  n_through_band?: number;
  n_stop_55?: number;
  n_stop_45?: number;
  n_stop_40?: number;
  n_hold?: number;
  cut_survivors_who_won?: number;
  used_remaining?: { min?: unknown; median?: unknown; max?: unknown };
  katy_path?: { mean_cents?: unknown; n?: unknown };
  katy_vs_8040?: { mean_cents?: unknown };
  always_hold?: { mean_cents?: unknown };
  always_8040?: { mean_cents?: unknown };
  overlay_theo?: { mean_cents?: unknown };
  overlay_obs?: { mean_cents?: unknown };
  delta_theo_mean?: unknown;
  delta_obs_mean?: unknown;
  hedge_subset_lock?: { mean_cents?: unknown; n?: unknown };
  hedge_subset_had_held?: { mean_cents?: unknown };
  hedge_subset_had_8040?: { mean_cents?: unknown };
  losers_hold?: { mean_cents?: unknown; n?: unknown };
  losers_katy?: { mean_cents?: unknown };
  losers_katy_8040?: { mean_cents?: unknown };
};

type ExamSide = {
  n?: number;
  n_open_ge_41?: number;
  n_already_lt_41?: number;
  n_t40_already_at_mark?: number;
  n_t40_terminal?: number;
  n_ev_unavailable?: number;
  price?: { mean?: unknown; median?: unknown };
  ev?: { n?: unknown; mean?: unknown };
  score_differential?: { n?: unknown; mean?: unknown; median?: unknown };
  price_buckets?: Record<string, number>;
};

type Card = {
  number?: number;
  experiment_id?: string;
  slug?: string;
  href?: string;
  title?: string;
  question?: string;
  marks?: { nba?: string; ncaab?: string };
  rule?: string;
  status?: string;
  one_line?: string;
};

const BOOK_META: Record<string, { title: string; caveat: string }> = {
  ncaab_h1_2_discovery: { title: "NCAAB H1_2 Discovery", caveat: "Transfer Discovery only. Confirmation sealed." },
  ncaab_h2_1_discovery: { title: "NCAAB H2_1 Discovery", caveat: "2H first-10 FIRST80, observed later at 2H last 10. Not H2_2." },
  nba_604_in_sample: { title: "NBA 604 in-sample 4Q", caveat: "Same 604 trades Dallas uses, later 4Q path. In-sample. Not 2026-27." },
  nba_2q: { title: "NBA 2Q", caveat: "Locked FIRST80 2Q. N=314. 2025-26. Not 2026-27." },
  nba_3q: { title: "NBA 3Q", caveat: "Locked FIRST80 3Q. N=290. 2025-26. Not 2026-27." },
  ncaab_h1_2: { title: "NCAAB 1H second 10", caveat: "Locked FIRST80 H1_2. N=193. Not H2_2." },
  ncaab_h2_1: { title: "NCAAB 2H first 10", caveat: "Locked FIRST80 H2_1. N=139. Observed at 2H last 10. Not H2_2." },
};

function BookCard({ title, book, caveat, showAustin = true, trail = false }: { title: string; book?: Book; caveat: string; showAustin?: boolean; trail?: boolean }) {
  return (
    <article>
      <h3>{title}</h3>
      <p className="muted">{caveat}</p>
      <dl>
        <Row label="N" value={book?.n_trades} />
        <Row label="run mark reached" value={book?.n_run_mark_reached} />
        {trail ? (
          <>
            <Row label="STOP 55 / 45 / 40" value={`${text(book?.n_stop_55)} / ${text(book?.n_stop_45)} / ${text(book?.n_stop_40)}`} />
            <Row label="HOLD" value={book?.n_hold} />
            <Row label="cut winning survivors" value={book?.cut_survivors_who_won} />
            <Row label="trail theo mean ¢" value={money(book?.overlay_theo?.mean_cents)} />
            <Row label="trail observed mean ¢" value={money(book?.overlay_obs?.mean_cents)} />
            <Row label="always 80/40 mean ¢" value={money(book?.always_8040?.mean_cents)} />
            <Row label="Δ theo vs 80/40 ¢" value={typeof book?.delta_theo_mean === "number" ? money(book.delta_theo_mean) : book?.delta_theo_mean} />
            <Row label="Δ obs vs 80/40 ¢" value={typeof book?.delta_obs_mean === "number" ? money(book.delta_obs_mean) : book?.delta_obs_mean} />
          </>
        ) : (
          <>
            <Row label="in selected band" value={book?.n_in_price_band} />
            <Row label="HEDGE_SCENARIO" value={book?.n_hedge_scenario} />
            <Row label="hedge losers / winners" value={`${text(book?.n_hedge_losers)} / ${text(book?.n_hedge_winners)}`} />
            <Row label="HOLD in band" value={book?.n_hold_in_band} />
            {showAustin ? <Row label="EV unavailable in band" value={book?.n_ev_unavailable_in_band} /> : null}
            <Row label="not underwater" value={book?.n_not_underwater} />
            <Row label="through band" value={book?.n_through_band} />
            <Row label="used remaining median s" value={book?.used_remaining?.median} />
            <Row label="mixed vs hold mean ¢" value={money(book?.katy_path?.mean_cents)} />
            <Row label="mixed vs 80/40 mean ¢" value={money(book?.katy_vs_8040?.mean_cents)} />
            <Row label="always hold mean ¢" value={money(book?.always_hold?.mean_cents)} />
            <Row label="always 80/40 mean ¢" value={money(book?.always_8040?.mean_cents)} />
            <Row label="hedge-subset lock mean ¢" value={money(book?.hedge_subset_lock?.mean_cents)} />
            <Row label="hedge-subset if 80/40 mean ¢" value={money(book?.hedge_subset_had_8040?.mean_cents)} />
          </>
        )}
        <Row label="losers hold mean ¢" value={money(book?.losers_hold?.mean_cents)} />
        <Row label="losers mixed-80/40 mean ¢" value={money(book?.losers_katy_8040?.mean_cents)} />
      </dl>
    </article>
  );
}

function ExamCard({
  title,
  exam,
  showAustin = true,
}: {
  title: string;
  exam?: { losers?: ExamSide; winners?: ExamSide; n_reached?: number };
  showAustin?: boolean;
}) {
  const losers = exam?.losers || {};
  const winners = exam?.winners || {};
  return (
    <article>
      <h3>{title}</h3>
      <p className="muted">Settlement identity. Mark = first snapshot at or after the clock.</p>
      <dl>
        <Row label="reached" value={exam?.n_reached} />
        <Row label="losers / winners" value={`${text(losers.n)} / ${text(winners.n)}`} />
        <Row label="losers still open ≥41" value={losers.n_open_ge_41} />
        <Row label="losers already <41" value={losers.n_already_lt_41} />
        <Row label="losers already stopped at mark" value={losers.n_t40_already_at_mark} />
        <Row label="losers terminal t40" value={losers.n_t40_terminal} />
        <Row label="loser price mean / median" value={`${money(losers.price?.mean)} / ${money(losers.price?.median)}`} />
        <Row label="winner price mean / median" value={`${money(winners.price?.mean)} / ${money(winners.price?.median)}`} />
        {showAustin ? (
          <>
            <Row label="loser Austin EV n / mean" value={`${text(losers.ev?.n)} / ${text(losers.ev?.mean)}`} />
            <Row label="winner Austin EV n / mean" value={`${text(winners.ev?.n)} / ${text(winners.ev?.mean)}`} />
            <Row label="loser EV unavailable" value={losers.n_ev_unavailable} />
          </>
        ) : (
          <>
            <Row label="loser score-diff mean / median" value={`${money(losers.score_differential?.mean)} / ${money(losers.score_differential?.median)}`} />
            <Row label="winner score-diff mean / median" value={`${money(winners.score_differential?.mean)} / ${money(winners.score_differential?.median)}`} />
          </>
        )}
        <Row label="loser price buckets" value={buckets(losers.price_buckets)} />
        <Row label="winner price buckets" value={buckets(winners.price_buckets)} />
      </dl>
    </article>
  );
}

function SelectedCard({ title, cell, showAustin = true }: { title: string; cell?: Record<string, unknown>; showAustin?: boolean }) {
  const none = cell?.status !== "SELECTED";
  const shown = none ? ((cell?.best_nonpositive as Record<string, unknown> | undefined) || {}) : cell || {};
  return (
    <article>
      <h3>{title}</h3>
      <dl>
        <Row label="status" value={cell?.status} />
        <Row label="reason" value={cell?.reason} />
        <Row label="yes_bid band" value={none ? "NONE" : `${text(shown.price_lo)}–${text(shown.price_hi)}`} />
        {none && shown.price_hi != null ? <Row label="best nonpositive band" value={`${text(shown.price_lo)}–${text(shown.price_hi)}`} /> : null}
        {showAustin ? <Row label="Austin EV <" value={cell?.austin_ev_lt} /> : null}
        <Row label="hedges" value={shown.n_hedge} />
        <Row label="hedge L / W" value={`${text(shown.n_hedge_losers)} / ${text(shown.n_hedge_winners)}`} />
        <Row label="Δ mean ¢ vs 80/40" value={typeof shown.delta_mean_cents === "number" ? money(shown.delta_mean_cents) : shown.delta_mean_cents} />
        <Row label="Δ sum ¢ vs 80/40" value={shown.delta_sum_cents} />
      </dl>
    </article>
  );
}

function Home() {
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchKaty()
      .then(setPayload)
      .catch((err: unknown) => setError(err instanceof UniverseError ? err.message : String(err)));
  }, []);

  const experiments = ((payload?.experiments || []) as Card[]) || [];
  const houston = ((payload?.components as Record<string, unknown> | undefined)?.houston || {}) as Record<string, unknown>;

  function go(href: string) {
    return (event: MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault();
      window.location.hash = href;
    };
  }

  return (
    <div>
      {error ? <div className="banner is-bad">{error}</div> : null}
      <div className="page-meta">
        <span className="pill">SHADOW RESEARCH</span>
        <span className="pill">ONE OF MANY EXPERIMENTS</span>
        <span className="pill">SCENARIO ≠ FILL</span>
        <span className="pill">CONFIRMATION UNSPENT</span>
        <span className="pill">EXECUTION DISABLED</span>
      </div>
      <p className="muted">{text(payload?.note)}</p>
      <section style={{ marginTop: 18 }}>
        <h2>Shared pieces — members vary by experiment</h2>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>Path / Dallas</h3>
            <p className="muted">Clock and yes_bid at the experiment mark. Experiments 3–4 read warehouse bars + PBP on the four locked books. Dallas page stays 2Q/3Q.</p>
          </article>
          <article>
            <h3>Houston</h3>
            <p className="muted">{text(houston.note)}</p>
            <Row label="identity" value={houston.identity} />
            <Row label="formula" value={houston.formula} />
            <Row label="fill" value={houston.fill_status} />
          </article>
          <article>
            <h3>Austin</h3>
            <p className="muted">Used only when the experiment says so. Experiments 1, 2, and 5 query frozen Austin EV. Experiments 3 and 4 do not.</p>
          </article>
        </div>
      </section>
      <section style={{ marginTop: 22 }}>
        <h2>Experiments</h2>
        <p className="muted">Each card opens its own page. Books are never combined into one headline.</p>
        <div className="grid" style={{ marginTop: 14 }}>
          {experiments.map((exp) => (
            <a key={exp.slug || exp.experiment_id} className="experiment-card" href={exp.href || "#/katy"} onClick={go(exp.href || "#/katy")}>
              <h3>
                Experiment {text(exp.number)} · {text(exp.title)}
              </h3>
              <p className="muted">{text(exp.question)}</p>
              <dl>
                <Row label="id" value={exp.experiment_id} />
                <Row label="NBA mark" value={exp.marks?.nba} />
                <Row label="NCAAB mark" value={exp.marks?.ncaab} />
                <Row label="rule" value={exp.rule} />
                <Row label="status" value={exp.status} />
                <Row label="result" value={exp.one_line} />
              </dl>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}

function Experiment({ slug }: { slug: string }) {
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchKatyExperiment(slug)
      .then(setPayload)
      .catch((err: unknown) => setError(err instanceof UniverseError ? err.message : String(err)));
  }, [slug]);

  const books = (payload?.books || {}) as Record<string, Book>;
  const rule = (payload?.rule || {}) as Record<string, unknown>;
  const selected = (payload?.selected || {}) as Record<string, Record<string, unknown>>;
  const exam = (payload?.loser_exam || {}) as Record<string, { losers?: ExamSide; winners?: ExamSide; n_reached?: number }>;
  const top = (payload?.top_cells || {}) as Record<string, Record<string, unknown>[]>;
  const houston = ((payload?.components as Record<string, unknown> | undefined)?.houston || {}) as Record<string, unknown>;
  const conversion = ((payload?.conversion as Record<string, unknown> | undefined)?.rows || []) as Record<string, unknown>[];
  const bookOrder =
    (payload?.book_order as string[] | undefined) ||
    (Object.keys(books).length ? Object.keys(books) : ["ncaab_h1_2_discovery", "ncaab_h2_1_discovery", "nba_604_in_sample"]);
  const showAustin = payload?.austin_used !== false;
  const isTrail = payload?.surface === "trail";
  const isSearch = Boolean(payload?.selected) && !isTrail;
  const marks = (payload?.marks || {}) as Record<string, unknown>;
  const grid = (payload?.grid_declared || {}) as Record<string, unknown>;

  return (
    <div>
      {error ? <div className="banner is-bad">{error}</div> : null}
      <p className="muted">
        <a href="#/katy">← Katy experiments</a>
      </p>
      <div className="page-meta">
        <span className="pill">EXPERIMENT {text(payload?.number)}</span>
        {showAustin ? null : <span className="pill">INDEPENDENT · NO AUSTIN</span>}
        {isTrail ? <span className="pill">CLOCK TRAIL</span> : null}
        <span className="pill">SCENARIO ≠ FILL</span>
        <span className="pill">NO POLICY FROZEN</span>
        <span className="pill">CONFIRMATION UNSPENT</span>
        <span className="pill">EXECUTION DISABLED</span>
      </div>
      <p className="muted">{text(payload?.note)}</p>
      <section style={{ marginTop: 18 }}>
        <h2>{text(payload?.title)}</h2>
        <article className="wide">
          <p className="muted">{text(payload?.question || payload?.note)}</p>
          <dl>
            <Row label="id" value={payload?.experiment_id} />
            <Row label="Austin" value={showAustin ? (payload?.austin_refit === false ? "queried, not refit" : payload?.austin_refit) : "not used"} />
            <Row label="Houston" value={houston.identity} />
            <Row label="Houston fill" value={houston.fill_status} />
            <Row label="NBA mark" value={typeof marks.nba === "string" ? marks.nba : rule.nba_run_mark || "2H last 10 = Q4 12:00 remaining"} />
            <Row label="NCAAB mark" value={typeof marks.ncaab === "string" ? marks.ncaab : rule.ncaab_run_mark || "2H last 10 = 2H 10:00 remaining"} />
            {isSearch ? <Row label="grid" value={grid.objective || grid.signal} /> : isTrail ? <Row label="trail" value="≤55 early last-10, ≤45 mid last-10, else 80/40" /> : <Row label="price band" value="41–70¢ (underwater ≥10, not through 40)" />}
            {isSearch ? <Row label="search ≠ freeze" value={payload?.search_is_not_a_freeze} /> : isTrail ? <Row label="Austin EV" value="not a member" /> : <Row label="Austin EV threshold" value={rule.austin_ev_lt} />}
          </dl>
        </article>
      </section>
      {conversion.length ? (
        <section style={{ marginTop: 22 }}>
          <h2>2H last 10 conversion</h2>
          <div className="grid" style={{ marginTop: 14 }}>
            {conversion.map((row) => (
              <article key={text(row.label)}>
                <h3>{text(row.label)}</h3>
                <dl>
                  <Row label="NBA" value={row.nba} />
                  <Row label="NCAAB" value={row.ncaab} />
                </dl>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      {Object.keys(exam).length ? (
        <section style={{ marginTop: 22 }}>
          <h2>What losers look like at this mark</h2>
          <div className="grid" style={{ marginTop: 14 }}>
            {bookOrder.map((key) => (
              <ExamCard key={key} title={`${BOOK_META[key]?.title || key} losers vs winners`} exam={exam[key]} showAustin={showAustin} />
            ))}
          </div>
        </section>
      ) : null}
      {isSearch ? (
        <section style={{ marginTop: 22 }}>
          <h2>{showAustin ? "Selected range × Austin EV vs always 80/40" : "Selected yes_bid range vs always 80/40"}</h2>
          <p className="muted">Per book. Tighten on ties. NONE if no cell beats always-80/40. Not a freeze.</p>
          <div className="grid" style={{ marginTop: 14 }}>
            {bookOrder.map((key) => (
              <SelectedCard key={key} title={`${BOOK_META[key]?.title || key} selected`} cell={selected[key]} showAustin={showAustin} />
            ))}
          </div>
        </section>
      ) : null}
      {isSearch ? (
        <section style={{ marginTop: 22 }}>
          <h2>{showAustin ? "Top grid cells" : "Top price cells"}</h2>
          <div className="grid" style={{ marginTop: 14 }}>
            {bookOrder.map((key) => (
              <article key={key}>
                <h3>{key}</h3>
                {(top[key] || []).map((cell, idx) => (
                  <p key={`${key}-${idx}`} className="muted">
                    {idx + 1}. {text(cell.price_lo)}–{text(cell.price_hi)}
                    {showAustin ? ` / EV<${text(cell.austin_ev_lt)}` : ""} hedge={text(cell.n_hedge)} Δmean={money(cell.delta_mean_cents)}
                  </p>
                ))}
              </article>
            ))}
          </div>
        </section>
      ) : null}
      <section style={{ marginTop: 22 }}>
        <h2>{bookOrder.length > 3 ? "Four books, never one headline" : "Three books, never one headline"}</h2>
        <div className="grid" style={{ marginTop: 14 }}>
          {bookOrder.map((key) => {
            const meta = BOOK_META[key] || { title: key, caveat: "Research book. Candle path ≠ fill." };
            return <BookCard key={key} title={meta.title} book={books[key]} caveat={meta.caveat} showAustin={showAustin} trail={isTrail} />;
          })}
        </div>
      </section>
    </div>
  );
}

export default function Katy({ slug }: { slug?: string }) {
  if (slug) {
    return <Experiment slug={slug} />;
  }
  return <Home />;
}
