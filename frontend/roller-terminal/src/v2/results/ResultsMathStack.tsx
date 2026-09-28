import { useMemo } from "react";
import { useDeskSettings } from "../settings/useDeskSettings";
import type { DetailPayload } from "../components/DetailDrawer";
import type { AnswerResult } from "./ResultsAnswer";
import type { WorkflowDraft } from "../workflow/types";
import { formatPct, wilsonCi } from "./wilson";
import { computeFiniteMath } from "./finiteMath";
import {
  deriveObservedStats,
  pickBootstrap,
  pickCluster,
  pickDependence,
  pickObserved,
  pickObservedEv,
} from "./deriveObserved";
import type { ClusterBlock } from "./deriveObserved";
import { fmtAbsDollars, fmtCents, fmtDollars, fmtPValue, fmtSharpe } from "./formatMoney";
import { bookEvInterval } from "./bookInference";
import { terminalMissingPhrase } from "../mlbContractHonesty";
import { coveragePct, fmtRate, lastTradePrintDisplacement } from "./lastTradeResults";
import { LAST_TRADE_UNAVAILABLE } from "./lastTradeBasis";
import { economicsOpen, readResultsContract } from "./resultsContract";
import {
  binaryBreakeven,
  entryCentsFromResult,
  fmtPct as fmtTradePct,
  fmtPp,
  fmtSignedCents,
  sameNRates,
} from "./tradeHeadline";

type Props = {
  result: AnswerResult;
  draft?: WorkflowDraft | null;
  onOpenDetail: (detail: DetailPayload) => void;
};

function asRec(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : null;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function fmtPctPts(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(1)} pp`;
}

function Chip({ children }: { children: string }) {
  return <span className="ws-prov-chip">{children}</span>;
}

function Card(props: {
  kicker: string;
  value: string;
  sub?: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={props.onClick ? "mm-metric is-actionable" : "mm-metric"}
      onClick={props.onClick}
      disabled={!props.onClick}
    >
      <span className="mm-metric-label">{props.kicker}</span>
      <span className="mm-metric-value">{props.value}</span>
      {props.sub ? <span className="mm-metric-note">{props.sub}</span> : null}
    </button>
  );
}

function explain(title: string, body: string, onOpenDetail: (d: DetailPayload) => void, value?: string) {
  onOpenDetail({
    title,
    value: value ?? "",
    subtitle: "Definition",
    sections: [
      { heading: "What this is", body: <p>{body}</p> },
      {
        heading: "Caveats",
        body: (
          <p>
            CANDLE PATH ≠ FILL. MEASUREMENT ≠ EDGE. Not a live P&amp;L. Not a trading recommendation.
          </p>
        ),
      },
    ],
  });
}

export default function ResultsMathStack({ result, draft, onOpenDetail }: Props) {
  const contract = readResultsContract(result);
  const lastPrint = contract.lastTrade;
  const lt = contract.rates;
  const sameN = sameNRates(lt);
  const tradeBe = binaryBreakeven(entryCentsFromResult(result), sameN?.pWin ?? null);
  const printDisp = lastPrint ? contract.printDisplacement ?? lastTradePrintDisplacement(result) : null;
  const evOpen = economicsOpen(contract.economics.observedPathEv);
  const analysis = asRec(result.analysis);
  const derived = useMemo(() => deriveObservedStats(result), [result]);
  const fallback = computeFiniteMath(result, draft);
  const empirical = asRec(analysis?.empirical);
  const observed = pickObserved(analysis, derived);
  const observedEv = pickObservedEv(analysis, derived);
  const book = asRec(analysis?.book_price) ?? asRec(analysis?.hypothetical_payoff);
  const settle = asRec(analysis?.settlement) ?? asRec(analysis?.settlement_payoff);
  const capital = asRec(analysis?.allocation) ?? asRec(analysis?.capitalization);
  const diagnostics = asRec(analysis?.diagnostics);
  const survive = asRec(diagnostics?.survivability);
  const bookWilsonEv = bookEvInterval(book, "wilson_ev_ci", "wilson");
  const bookExactEv = bookEvInterval(book, "exact_binomial_ev_ci", "clopper_pearson");
  const continuum = asRec(asRec(analysis?.robustness)?.binary_entry_continuum);
  const sizing = asRec(capital?.sizing);
  const unc = asRec(analysis?.uncertainty);
  const dep = pickDependence(analysis, derived);
  const seq = asRec(analysis?.sequence) ?? derived.sequence;
  const equity = asRec(analysis?.equity);
  const robust = asRec(analysis?.robustness);
  const hold = asRec(analysis?.holding_time);
  const exc = asRec(analysis?.excursion);
  const tte = asRec(analysis?.time_to_event);
  const ledger = asRec(analysis?.exclusion_ledger);
  const quality = asRec(analysis?.data_quality);
  const prov = asRec(analysis?.provenance);
  const ror = asRec(analysis?.risk_of_ruin);
  const hurdle = asRec(analysis?.economic_hurdle);
  const evContract = asRec(analysis?.ev_contract);

  const prices = asRec(capital?.prices);
  const entryRef =
    num(sizing?.entry_cents) ??
    num(prices?.sizing_cents) ??
    num(prices?.reference_cents) ??
    entryFromExecuted(result);
  const {
    bankrollDollars,
    setBankrollDollars,
    allocationPct: allocPct,
    setAllocationPct: setAllocPct,
    saving: deskSaving,
    error: deskError,
    save: saveDesk,
  } = useDeskSettings();

  const scaled = useMemo(() => {
    const entry = entryRef;
    const bankrollCents = Math.round(bankrollDollars * 100);
    const allocCents = Math.round((bankrollCents * allocPct) / 100);
    const contracts = entry != null && entry > 0 ? Math.floor(allocCents / entry) : 0;
    const deployed = entry != null ? contracts * entry : null;
    const residual = deployed != null ? allocCents - deployed : null;
    const mean = num(observed?.mean_cents) ?? fallback.observedEvCents;
    const sum = num(observed?.sum_cents);
    const n = num(observed?.n) ?? fallback.observedN;
    const sized = entry != null && contracts > 0;
    const evAlloc = !sized
      ? null
      : sum != null && n > 0
        ? (sum * contracts) / n
        : mean != null
          ? mean * contracts
          : null;
    const bookEv = num(book?.ev_cents);
    const bookCi = bookWilsonEv;
    const std = num(observed?.std_cents);
    const se = num(asRec(observedEv?.ci95)?.standard_error) ?? num(asRec(observed?.ev_ci)?.standard_error);
    const ci = asRec(observedEv?.ci95) ?? asRec(observed?.ev_ci);
    const dd = num(asRec(seq?.drawdown)?.max_drawdown_cents) ?? fallback.maxDrawdownCents;
    const q = asRec(observed?.quantiles);
    const dollar = (cents: number | null) =>
      cents == null || !sized ? null : (cents * contracts) / 100;
    return {
      bankrollCents,
      allocCents,
      contracts,
      deployed,
      residual,
      evAlloc,
      bookAlloc: sized && bookEv != null ? bookEv * contracts : null,
      bookCiAllocLo: sized ? dollar(num(bookCi?.lower)) : null,
      bookCiAllocHi: sized ? dollar(num(bookCi?.upper)) : null,
      stdAlloc: sized && std != null ? std * contracts : null,
      seAlloc: sized && se != null ? se * contracts : null,
      ciAllocLo: sized ? dollar(num(ci?.lower)) : null,
      ciAllocHi: sized ? dollar(num(ci?.upper)) : null,
      ddAlloc: sized && dd != null ? dd * contracts : null,
      medianAlloc: dollar(num(observed?.median_cents)),
      p5Alloc: dollar(num(q?.p5)),
      p25Alloc: dollar(num(q?.p25)),
      p50Alloc: dollar(num(q?.p50)),
      p75Alloc: dollar(num(q?.p75)),
      p95Alloc: dollar(num(q?.p95)),
      worstAlloc: dollar(num(observed?.min_cents)),
      bestAlloc: dollar(num(observed?.max_cents)),
      entry,
    };
  }, [
    allocPct,
    bankrollDollars,
    book?.ev_cents,
    bookWilsonEv,
    entryRef,
    fallback.maxDrawdownCents,
    fallback.observedEvCents,
    fallback.observedN,
    observed?.mean_cents,
    observed?.median_cents,
    observed?.min_cents,
    observed?.max_cents,
    observed?.n,
    observed?.quantiles,
    observed?.std_cents,
    observed?.sum_cents,
    observed?.ev_ci,
    observedEv?.ci95,
    seq?.drawdown,
  ]);

  const winN = num(empirical?.successes) ?? fallback.pathTrue;
  const den = num(empirical?.denominator) ?? fallback.pathAvail;
  const pHat = den && winN != null ? winN / den : fallback.pathRate;
  const wilson = den && winN != null && den > 0 ? wilsonCi(winN, den) : null;
  const evCi = asRec(observedEv?.ci95) ?? asRec(observed?.ev_ci);
  const boot = pickBootstrap(analysis, derived);
  const bootMean = asRec(boot?.mean);
  const bootSharpe = asRec(boot?.sharpe);
  const significance = asRec(observedEv?.significance);
  const q = asRec(observed?.quantiles);
  const meanEntry =
    num(prices?.mean_observed_entry_cents) ??
    num(analysis?.mean_actual_entry_cents) ??
    derived.meanEntryCents;
  const dollarDist = asRec(asRec(capital?.observed)?.distribution);
  const classified =
    (num(empirical?.win_exit) ?? 0) + (num(empirical?.loss_exit) ?? 0) > 0 ||
    book?.status === "HYPOTHETICAL";
  const binarySens =
    asRec(robust?.binary_entry_sensitivity) ?? binaryEntrySensitivity(pHat);
  const bookSens = asRec(robust?.book_entry_sensitivity);
  const bootEq = asRec(equity?.bootstrap);
  const endCap =
    asRec(bootEq?.ending_capital_cents) ??
    scaleBootstrapCapital(asRec(boot?.ending_pnl_cents), scaled.contracts, scaled.bankrollCents, num(equity?.ending_bankroll_cents));
  const ddBoot =
    asRec(bootEq?.max_drawdown_cents) ??
    scaleBootstrapDd(asRec(boot?.max_drawdown_cents), scaled.contracts, scaled.ddAlloc);
  const gameCluster = pickCluster(
    (asRec(unc?.game_cluster_ci) as ClusterBlock | null) ?? (asRec(dep?.game_cluster) as ClusterBlock | null),
    derived.gameCluster,
  );
  const dateCluster = pickCluster(
    (asRec(unc?.date_cluster_ci) as ClusterBlock | null) ?? (asRec(dep?.date_cluster) as ClusterBlock | null),
    derived.dateCluster,
  );
  const pathDd = lastPrint
    ? null
    : num(asRec(seq?.drawdown)?.max_drawdown_cents) ?? fallback.maxDrawdownCents;
  const pathFormula = String(
    asRec(asRec(evContract?.objects)?.observed_path_ev)?.formula ||
      observedEv?.formula ||
      "E[exit_close − entry_close]",
  );
  const bookFormula =
    String(book?.formula || "P(WIN)×(WIN_price − entry) + P(LOSS)×(LOSS_price − entry)");
  const settleFormula =
    String(settle?.formula || "P(YES)×(100¢ − entry) + P(NO)×(0¢ − entry)");
  const grossEv = lastPrint
    ? null
    : num(hurdle?.observed_gross_ev_cents) ?? num(observed?.mean_cents) ?? fallback.observedEvCents;
  const desk = lastPrint
    ? [
        sameN
          ? `P(win) ${fmtTradePct(sameN.pWin)} · ${sameN.wins} / ${sameN.n}. Loss ${sameN.losses} / ${sameN.n}. Other ${sameN.other} / ${sameN.n}.`
          : lt
            ? `PATH RATE ${fmtRate(lt.pathTrue, lt.n)}.`
            : null,
        tradeBe
          ? `Breakeven before fees ${fmtTradePct(tradeBe.breakeven)} (${tradeBe.entryCents}¢). Margin ${fmtPp(tradeBe.margin)} · ${fmtSignedCents(tradeBe.evCents)} / contract.`
          : null,
        `Observed executable-path EV unavailable. ${LAST_TRADE_UNAVAILABLE}.`,
        book?.status === "HYPOTHETICAL" && num(book.ev_cents) != null
          ? `Book-price EV ${fmtCents(num(book.ev_cents))} · chips × rates on N.`
          : "Book-price EV needs tagged WIN and LOSS path prices.",
        lt?.settled != null && lt.n != null
          ? `Settlement coverage ${lt.settled} / ${lt.n}. Missing remains missing.`
          : null,
        "PATH WIN ≠ TERMINAL YES. LAST TRADE ≠ FILL. MEASUREMENT ≠ EDGE.",
      ]
        .filter(Boolean)
        .join(" ")
    : deskRead({
        pHat,
        rateNoun: classified ? "WIN" : "path",
        wilson,
        ev: num(observed?.mean_cents) ?? fallback.observedEvCents,
        evCi,
        book,
        settle,
        ddDollars: scaled.ddAlloc != null ? scaled.ddAlloc / 100 : null,
        allocDollars: scaled.allocCents / 100,
        capitalizedEv: scaled.evAlloc != null ? scaled.evAlloc / 100 : null,
        beWin: num(book?.breakeven_probability),
      });

  const pathEv = evOpen
    ? contract.economics.observedPathEv.estimate_cents ?? num(observed?.mean_cents) ?? fallback.observedEvCents
    : null;
  const pathSe = evOpen ? num(significance?.standard_error) ?? num(evCi?.standard_error) : null;
  const pathN = evOpen ? num(observed?.n) ?? fallback.observedN : null;
  const zeroInside = lastPrint
    ? "—"
    : significance?.zero_inside_ci === true || evCi?.zero_inside_ci === true
      ? "YES"
      : significance?.zero_inside_ci === false || evCi?.zero_inside_ci === false
        ? "NO"
        : "—";
  const pathCi = lastPrint
    ? LAST_TRADE_UNAVAILABLE
    : evCi && num(evCi.lower) != null && num(evCi.upper) != null
      ? `${fmtCents(num(evCi.lower))} — ${fmtCents(num(evCi.upper))}`
      : "—";
  const bookEv = book?.status === "HYPOTHETICAL" ? num(book.ev_cents) : null;
  const bookCiTxt =
    bookWilsonEv && num(bookWilsonEv.lower) != null
      ? `${fmtCents(num(bookWilsonEv.lower))} — ${fmtCents(num(bookWilsonEv.upper))}`
      : "—";
  const bootCiTxt = lastPrint
    ? "UNAVAILABLE"
    : bootMean && num(bootMean.lower) != null
      ? `${fmtCents(num(bootMean.lower))} — ${fmtCents(num(bootMean.upper))}`
      : "—";
  const capEv = lastPrint ? null : scaled.evAlloc != null ? scaled.evAlloc / 100 : null;
  const capCiTxt = lastPrint
    ? "UNAVAILABLE"
    : scaled.ciAllocLo != null && scaled.ciAllocHi != null
      ? `${fmtDollars(scaled.ciAllocLo)} — ${fmtDollars(scaled.ciAllocHi)}`
      : "—";
  const settleStatus = String(settle?.status || "");
  const settleDisplay =
    settleStatus === "DERIVED" || settleStatus === "HYPOTHETICAL"
      ? fmtCents(num(settle?.ev_cents))
      : settleStatus === "INCOMPLETE" || lastPrint
        ? "INCOMPLETE"
        : "UNAVAILABLE";

  return (
    <>
      <section className="ws-expect-tile" aria-label="Expected return per contract">
        <p className="v2-kicker">Per contract · not profit · not a fill</p>
        <div className="ws-expect-main">
          <div>
            <div className="ws-expect-label">
              {lastPrint ? "Backtest P(win) vs breakeven before fees" : "Expected observed-path return"}
            </div>
            <div className="ws-expect-value evidence">
              {lastPrint
                ? tradeBe
                  ? `${fmtTradePct(sameN?.pWin)} vs ${fmtTradePct(tradeBe.breakeven)} BE`
                  : fmtTradePct(sameN?.pWin)
                : fmtCents(pathEv)}
            </div>
            <div className="ws-expect-ci evidence">
              {lastPrint
                ? tradeBe
                  ? `${fmtPp(tradeBe.margin)} · ${fmtSignedCents(tradeBe.evCents)} / contract`
                  : "Need an entry chip for breakeven"
                : pathCi}
            </div>
            <p className="muted small">
              {lastPrint
                ? sameN
                  ? `Wins ${sameN.wins} / ${sameN.n} · Losses ${sameN.losses} / ${sameN.n} · Other ${sameN.other} / ${sameN.n}. Binary 100/0 before fees. LAST TRADE ≠ FILL.`
                  : "LAST TRADE ≠ EXECUTABLE PRICE. Do not reconstruct population EV from LOSS-exit prints."
                : `95% observation-level interval · SE ${fmtCents(pathSe)} · n = ${pathN || "—"} · ZERO INSIDE CI · ${zeroInside}`}
            </p>
            <p className="muted small">
              {lastPrint
                ? "Observed executable-path EV remains unavailable. LAST TRADE ≠ YES BID. Historical last-trade prints do not prove executable fills."
                : "Candle exit − entry. Not executed P&L. Point estimate is not proof of edge."}
            </p>
          </div>
          <dl className="ws-expect-side">
            <div>
              <dt>Book-price EV</dt>
              <dd>
                {bookEv != null ? fmtCents(bookEv) : lastPrint ? "needs WIN+LOSS chips" : "—"}
                {bookEv != null ? <span className="muted"> · Wilson 95% {bookCiTxt}</span> : null}
              </dd>
            </div>
            <div>
              <dt>Bootstrap EV 95%</dt>
              <dd>{bootCiTxt}</dd>
            </div>
            <div>
              <dt>{lastPrint ? "Capitalized observed path" : "$1,000 capitalized path EV"}</dt>
              <dd>
                {lastPrint ? "UNAVAILABLE" : fmtDollars(capEv)}
                {lastPrint ? (
                  <span className="muted"> · {LAST_TRADE_UNAVAILABLE}</span>
                ) : (
                  <span className="muted"> · 95% {capCiTxt}</span>
                )}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <div className="ws-chip-row">
        <Chip>OBSERVED</Chip>
        <Chip>DERIVED</Chip>
        <Chip>HYPOTHETICAL</Chip>
        <Chip>MODEL-ASSUMED</Chip>
      </div>

      <section className="ws-ev-identity" aria-label="Three distinct EV objects">
        <p className="v2-kicker">Three distinct objects</p>
        <p className="ws-desk-read">{desk}</p>
        <div className="ws-breakdown">
          <Card
            kicker="Observed path EV"
            value={lastPrint ? "UNAVAILABLE" : fmtCents(pathEv)}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : pathFormula}
            onClick={() =>
              explain(
                "Observed path EV",
                lastPrint
                  ? `${LAST_TRADE_UNAVAILABLE}. LOSS-only print displacement is not population EV.`
                  : `${pathFormula}. Candle path, not a fill, not book-price EV, not settlement, not profit.`,
                onOpenDetail,
              )
            }
          />
          <Card
            kicker="Book-price EV"
            value={book?.status === "HYPOTHETICAL" ? fmtCents(num(book.ev_cents)) : lastPrint ? "needs WIN+LOSS chips" : "—"}
            sub={
              book?.status === "HYPOTHETICAL"
                ? bookFormula
                : lastPrint
                  ? "Tagged WIN and LOSS path prices required. Binary BE is separate."
                  : bookFormula
            }
          />
          <Card
            kicker="Settlement EV"
            value={settleDisplay}
            sub={
              lastPrint && lt?.settled != null && lt.n != null
                ? `INCOMPLETE · ${lt.settled} / ${lt.n} settled · PATH WIN ≠ SETTLEMENT YES`
                : `${settleFormula} · PATH WIN ≠ SETTLEMENT YES`
            }
          />
        </div>
      </section>

      {lastPrint && printDisp ? (
        <section className="ws-print-diag" aria-label="Loss-exit print displacement">
          <p className="v2-kicker">Optional print diagnostic</p>
          <h2>LOSS-exit print displacement</h2>
          <p className="muted small">
            OBSERVED LAST-TRADE PRINT SUBSET. NOT POPULATION EV. NOT FILL P&amp;L. NOT SETTLEMENT
            EV. {LAST_TRADE_UNAVAILABLE}.
          </p>
          <div className="ws-breakdown">
            <Card
              kicker="LOSS-EXIT PRINT DISPLACEMENT"
              value={printDisp.meanCents != null ? fmtCents(printDisp.meanCents) : "—"}
              sub={`mean(exit_close − entry_close) · n = ${printDisp.n} · last-trade print only`}
            />
            <Card
              kicker="WIN hold rows"
              value={String(printDisp.winHold)}
              sub="HOLD_TO_EXPIRATION · exit_close is None by definition"
            />
          </div>
        </section>
      ) : null}

      <section className="ws-level ws-finite-math is-sample">
        <p className="v2-kicker">Sample strength</p>
        <h2>Rate and clustering</h2>
        <p className="muted small">
          Wilson is a CI for the binary proportion, not for edge. N observations ≠ N independent games.
        </p>
        <div className="ws-breakdown">
          <Card
            kicker={lastPrint ? "Path rate" : classified ? "WIN rate" : "Path rate"}
            value={
              lastPrint && lt?.pathTrue != null && lt.n != null
                ? fmtRate(lt.pathTrue, lt.n)
                : den != null && winN != null
                  ? `${formatPct(pHat)} · ${winN}/${den}`
                  : "—"
            }
            sub={
              lastPrint && lt
                ? `PATH FALSE ${lt.pathFalse ?? "—"} / ${lt.n ?? "—"} · not LOSS_EXIT`
                : `LOSS ${num(empirical?.failures) ?? "—"} · denom ${den ?? "—"}`
            }
            onClick={() =>
              explain("Observed rate", "Successes over this statistic’s own denominator.", onOpenDetail, formatPct(pHat))
            }
          />
          <Card
            kicker="Wilson 95%"
            value={wilson ? `${formatPct(wilson.lower)} — ${formatPct(wilson.upper)}` : "—"}
            sub="binomial proportion · not edge"
          />
          <Card
            kicker="N / games / dates"
            value={`${String((num(dep?.n_observations) || den) ?? "—")} · ${String(num(dep?.n_games) ?? "—")} · ${String(num(dep?.n_dates) ?? "—")}`}
            sub={`${String(dep?.n_tickers ?? "—")} tickers · not independent experiments`}
          />
        </div>
      </section>

      <section className="ws-level is-path">
        <p className="v2-kicker">Economics · observed</p>
        <h2>Observed path return</h2>
        <p className="muted small">
          {lastPrint
            ? `${LAST_TRADE_UNAVAILABLE}. LOSS-only print travel is not a population return sample.`
            : "Mean exit−entry on candles. Not a fill. Not the book-price EV. Not settlement."}
        </p>
        <div className="ws-breakdown">
          <Card
            kicker="Observed path EV"
            value={lastPrint ? "UNAVAILABLE" : fmtCents(pathEv)}
            sub={
              lastPrint
                ? LAST_TRADE_UNAVAILABLE
                : (num(observed?.n) ?? 0) > 0
                  ? `${pathFormula} · n = ${observed?.n}`
                  : "No valid exit · missing exit is not 0"
            }
            onClick={() =>
              explain(
                "Observed path EV",
                lastPrint
                  ? `${LAST_TRADE_UNAVAILABLE}. Do not treat missing WIN exit prices as zero.`
                  : "Mean observed exit-minus-entry movement per contract. Candle-path measurement; not a fill.",
                onOpenDetail,
              )
            }
          />
          <Card kicker="Median" value={lastPrint ? "UNAVAILABLE" : fmtCents(num(observed?.median_cents))} />
          <Card
            kicker="Stdev / variance"
            value={
              lastPrint
                ? "UNAVAILABLE"
                : `${fmtCents(num(observed?.std_cents))} · ${num(observed?.variance_cents)?.toFixed(2) ?? "—"}`
            }
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "sample N−1 · dash if N < 2"}
          />
          <Card
            kicker="P5 / P95"
            value={lastPrint ? "UNAVAILABLE" : `${fmtCents(num(q?.p5))} · ${fmtCents(num(q?.p95))}`}
          />
          <Card
            kicker="Observed path Sharpe"
            value={lastPrint ? "UNAVAILABLE" : fmtSharpe(num(observed?.observed_path_sharpe) ?? num(observed?.sharpe_trade))}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "UNANNUALIZED · not a trade Sharpe unless fills exist"}
          />
          <Card
            kicker="Sortino"
            value={lastPrint ? "UNAVAILABLE" : fmtSharpe(num(observed?.sortino))}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "mean / downside deviation vs 0 · UNAVAILABLE if no downside"}
          />
          <Card
            kicker="Expected shortfall P5"
            value={lastPrint ? "UNAVAILABLE" : fmtCents(num(asRec(observed?.expected_shortfall_p5)?.mean_cents))}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "EMPIRICAL · mean of returns ≤ P5"}
          />
          <Card
            kicker="Empirical P(π < 0)"
            value={lastPrint ? "UNAVAILABLE" : formatPct(num(asRec(observed?.sign_fractions)?.p_return_lt_0))}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "sample fraction · not a future probability"}
          />
          <Card
            kicker="MAE / MFE"
            value={
              exc?.status === "OBSERVED"
                ? `${fmtCents(num(asRec(exc.mae)?.mean_cents))} · ${fmtCents(num(asRec(exc.mfe)?.mean_cents))}`
                : "—"
            }
            sub={exc?.status === "OBSERVED" ? "mean later-bar excursion" : String(exc?.reason ?? "UNAVAILABLE")}
          />
          <Card
            kicker="Holding time"
            value={
              asRec(hold?.overall)?.status === "OBSERVED"
                ? `${Math.round(num(asRec(hold?.overall)?.median_seconds) ?? 0)}s median`
                : "—"
            }
            sub={
              asRec(hold?.overall)?.status === "OBSERVED"
                ? `n = ${String(asRec(hold?.overall)?.n)}`
                : "UNAVAILABLE without exit timestamps"
            }
          />
        </div>
      </section>

      <section className="ws-level is-book">
        <p className="v2-kicker">Economics · payoff</p>
        <h2>Book-price EV and economic threshold</h2>
        <p className="muted small">
          {bookFormula}. Settlement: {settleFormula}. PATH WIN ≠ SETTLEMENT YES. PATH LOSS ≠
          SETTLEMENT NO. P(WIN) ≠ EV.
        </p>
        <div className="ws-breakdown">
          <Card
            kicker="Book-price EV"
            value={book?.status === "HYPOTHETICAL" ? fmtCents(num(book.ev_cents)) : "—"}
            sub={
              book?.status === "HYPOTHETICAL"
                ? `WIN ${fmtCents(num(book.win_payoff_cents), 1)} · LOSS ${fmtCents(num(book.loss_payoff_cents), 1)}`
                : String(book?.reason ?? "Tagged WIN/LOSS chips required")
            }
          />
          <Card
            kicker="WIN contribution"
            value={fmtCents(num(book?.win_contribution_cents))}
            sub={book ? `${formatPct(num(book.win_probability))} × ${fmtCents(num(book.win_payoff_cents), 1)}` : "—"}
          />
          <Card
            kicker="LOSS contribution"
            value={fmtCents(num(book?.loss_contribution_cents))}
            sub={book ? `${formatPct(num(book.loss_probability))} × ${fmtCents(num(book.loss_payoff_cents), 1)}` : "—"}
          />
          <Card
            kicker="Breakeven before fees"
            value={formatPct(num(book?.breakeven_probability) ?? tradeBe?.breakeven)}
            sub={
              tradeBe || num(book?.rate_margin_vs_breakeven) != null
                ? `margin ${fmtPctPts(num(book?.rate_margin_vs_breakeven) ?? tradeBe?.margin)} · binary 100/0 · not a fill`
                : "Need an entry chip"
            }
          />
          <Card
            kicker="Settlement EV"
            value={settleDisplay}
            sub={
              lastPrint && lt?.settled != null && lt.n != null
                ? `INCOMPLETE · coverage ${coveragePct(lt.settled, lt.n)} · missing is not NO`
                : settle?.status === "DERIVED" || settle?.status === "HYPOTHETICAL"
                  ? `measured YES/NO only · missing ${String(settle?.terminal_missing ?? "—")}`
                  : `TERMINAL DATA UNAVAILABLE · ${terminalMissingPhrase(result.provenance)} · not 0 · not path WIN`
            }
          />
        </div>
        <div className="ws-hurdle">
          <p className="v2-kicker">Minimum economically viable edge</p>
          <div className="ws-breakdown">
            <Card
              kicker="Observed gross EV"
              value={lastPrint ? "UNAVAILABLE" : fmtCents(grossEv)}
              sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "not profit · candle-path mean"}
            />
            <Card
              kicker="Break-even total cost"
              value={lastPrint ? "UNAVAILABLE" : fmtCents(num(hurdle?.break_even_total_cost_cents) ?? grossEv)}
              sub={
                lastPrint
                  ? "no valid executable return basis"
                  : "max cost before EV = 0 · / contract"
              }
            />
            <Card
              kicker="Platform fees"
              value="not measured"
              sub="UNAVAILABLE on rows"
            />
            <Card
              kicker="Slippage"
              value="not measured"
              sub="UNAVAILABLE"
            />
            <Card
              kicker="Fill impact"
              value="not measured"
              sub={lastPrint ? "UNAVAILABLE · LAST TRADE ≠ FILL" : "UNAVAILABLE · CANDLE PATH ≠ FILL"}
            />
          </div>
        </div>
        <SensitivityTable
          block={binarySens}
          observedWin={pHat}
          title={lastPrint ? "Hypothetical path-rate sensitivity" : "Hypothetical binary 100/0"}
          observedCol={lastPrint ? "PATH RATE · not terminal probability" : classified ? "OBSERVED WIN" : "OBSERVED RATE"}
          referenceCents={num(prices?.sizing_cents) ?? scaled.entry}
        />
        <SensitivityTable
          block={bookSens}
          observedWin={pHat}
          title="Hypothetical book-price · chips fixed"
          observedCol={classified ? "OBSERVED WIN" : "OBSERVED RATE"}
          referenceCents={num(prices?.sizing_cents) ?? scaled.entry}
        />
      </section>

      <section className="ws-level is-capital">
        <p className="v2-kicker">Model-assumed</p>
        <h2>Hypothetical capitalization</h2>
        <p className="muted small">
          {lastPrint
            ? `${LAST_TRADE_UNAVAILABLE}. LOSS-only print displacement cannot be capitalized into strategy economics.`
            : "MODEL-ASSUMED overlay. Capitalizes the observed candle-path return distribution at a reference price — not the expected P&L of an executed binary trade at that price. Fixed allocation. Not compounding. Not the Risk Decision Engine."}
        </p>
        <div className="ws-capital-inputs">
          <label>
            Bankroll $
            <input
              type="number"
              min={1}
              value={bankrollDollars}
              onChange={(e) => setBankrollDollars(Number(e.target.value) || 0)}
            />
          </label>
          <label>
            Allocation %
            <input
              type="number"
              min={0.1}
              step={0.1}
              value={allocPct}
              onChange={(e) => setAllocPct(Number(e.target.value) || 0)}
            />
          </label>
          <button type="button" className="btn-secondary" disabled={deskSaving} onClick={() => void saveDesk()}>
            {deskSaving ? "Saving…" : "Save settings"}
          </button>
        </div>
        {deskError ? <p className="muted small">{deskError}</p> : null}
        <div className="ws-breakdown">
          <Card
            kicker="Allocation"
            value={fmtAbsDollars(scaled.allocCents / 100)}
            sub={`${allocPct}% of $${bankrollDollars.toLocaleString()}`}
          />
          <Card
            kicker="Reference price"
            value={
              (num(prices?.reference_cents) ?? scaled.entry) != null
                ? `${(num(prices?.reference_cents) ?? scaled.entry)!.toFixed(1)}¢`
                : "—"
            }
            sub="query band floor / chip · not a fill"
          />
          <Card
            kicker="Mean observed entry"
            value={meanEntry != null ? `${meanEntry.toFixed(1)}¢` : "—"}
            sub={
              lastPrint
                ? "empirical mean last_close at the touch · LAST TRADE ≠ YES BID"
                : "empirical mean yes_bid_close at the touch"
            }
          />
          <Card
            kicker="Sizing price"
            value={
              (num(prices?.sizing_cents) ?? scaled.entry) != null
                ? `${(num(prices?.sizing_cents) ?? scaled.entry)!.toFixed(1)}¢`
                : "—"
            }
            sub="contracts use this price, not the mean touch"
          />
          <Card
            kicker="Contracts"
            value={scaled.entry != null ? scaled.contracts.toLocaleString("en-US") : "—"}
            sub={
              scaled.entry != null
                ? "floor(allocation / sizing price) · not sized at mean touch"
                : "UNAVAILABLE without an executed entry reference"
            }
          />
          <Card
            kicker="Deployed"
            value={scaled.deployed != null ? fmtAbsDollars(scaled.deployed / 100) : "—"}
            sub={
              scaled.residual != null
                ? `residual ${fmtAbsDollars(scaled.residual / 100)} unspent`
                : "UNAVAILABLE without an executed entry reference"
            }
          />
          <Card
            kicker="Capitalized observed path EV"
            value={lastPrint ? "UNAVAILABLE" : fmtDollars(scaled.evAlloc != null ? scaled.evAlloc / 100 : null)}
            sub={
              lastPrint
                ? LAST_TRADE_UNAVAILABLE
                : `${fmtCents(pathEv)} × ${scaled.contracts} · from Σπᵢ · not binary-trade P&L`
            }
            onClick={() =>
              explain(
                "Capitalized observed path EV",
                lastPrint
                  ? `${LAST_TRADE_UNAVAILABLE}. Print displacement is not strategy P&L.`
                  : "Hypothetical capitalization of the observed candle-path return mean at the reference contract count. Not a deterministic expected P&L. Not profit.",
                onOpenDetail,
              )
            }
          />
          <Card
            kicker="Capitalized SE"
            value={lastPrint ? "UNAVAILABLE" : fmtAbsDollars(scaled.seAlloc != null ? scaled.seAlloc / 100 : num(asRec(capital?.observed)?.se_allocation_dollars))}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "SE(π̄) × contracts · not a loss limit"}
          />
          <Card
            kicker="Capitalized 95% CI"
            value={
              lastPrint
                ? "UNAVAILABLE"
                : scaled.ciAllocLo != null && scaled.ciAllocHi != null
                  ? `${fmtDollars(scaled.ciAllocLo)} — ${fmtDollars(scaled.ciAllocHi)}`
                  : "—"
            }
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "t-interval on the capitalized mean · not a forecast"}
          />
          <Card
            kicker="Expected $ / median $"
            value={
              lastPrint
                ? "UNAVAILABLE"
                : `${fmtDollars(scaled.evAlloc != null ? scaled.evAlloc / 100 : num(dollarDist?.expected_dollars))} · ${fmtDollars(scaled.medianAlloc ?? num(dollarDist?.median_dollars))}`
            }
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "mean vs median of the capitalized πᵢ distribution"}
          />
          <Card
            kicker="Stdev $"
            value={fmtAbsDollars(scaled.stdAlloc != null ? scaled.stdAlloc / 100 : num(dollarDist?.std_dollars))}
            sub="dispersion of capitalized πᵢ · not a loss limit"
          />
          <Card
            kicker="P5 / P25"
            value={`${fmtDollars(scaled.p5Alloc ?? num(dollarDist?.p5_dollars))} · ${fmtDollars(scaled.p25Alloc ?? num(dollarDist?.p25_dollars))}`}
          />
          <Card
            kicker="P50 / P75"
            value={`${fmtDollars(scaled.p50Alloc ?? num(dollarDist?.p50_dollars))} · ${fmtDollars(scaled.p75Alloc ?? num(dollarDist?.p75_dollars))}`}
          />
          <Card
            kicker="P95"
            value={fmtDollars(scaled.p95Alloc ?? num(dollarDist?.p95_dollars))}
          />
          <Card
            kicker="Worst / best observed"
            value={`${fmtDollars(scaled.worstAlloc ?? num(dollarDist?.worst_dollars))} · ${fmtDollars(scaled.bestAlloc ?? num(dollarDist?.best_dollars))}`}
            sub="single-observation capitalized extremes"
          />
          <Card
            kicker="Book-price $ / allocation"
            value={fmtDollars(scaled.bookAlloc != null ? scaled.bookAlloc / 100 : null)}
            sub="HYPOTHETICAL chips · not observed path EV"
          />
          <Card
            kicker="Book-price 95% CI $"
            value={
              scaled.bookCiAllocLo != null && scaled.bookCiAllocHi != null
                ? `${fmtDollars(scaled.bookCiAllocLo)} — ${fmtDollars(scaled.bookCiAllocHi)}`
                : "—"
            }
            sub="Wilson-transformed payoff interval · capitalized · not a forecast"
          />
        </div>
      </section>

      <section className="ws-level is-sequence">
        <p className="v2-kicker">Model-assumed</p>
        <h2>Sequence risk</h2>
        <p className="muted small">
          {lastPrint
            ? `${LAST_TRADE_UNAVAILABLE}. Sequence drawdown and bankroll path are not computed from LOSS-only prints.`
            : "Three different drawdowns: per-contract path, fixed-allocation sequence, and bankroll share. One historical ordering is not the likely outcome."}
        </p>
        <div className="ws-breakdown">
          <Card
            kicker="Max price-path DD"
            value={lastPrint ? "UNAVAILABLE" : pathDd != null ? `${pathDd}¢ / contract` : "—"}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "chronological entry_ts · observed path"}
          />
          <Card
            kicker="Max sequence DD"
            value={lastPrint ? "UNAVAILABLE" : fmtAbsDollars(scaled.ddAlloc != null ? scaled.ddAlloc / 100 : null)}
            sub={
              lastPrint
                ? LAST_TRADE_UNAVAILABLE
                : scaled.ddAlloc != null && scaled.allocCents
                  ? `${((scaled.ddAlloc / scaled.allocCents) * 100).toFixed(1)}% of one ${fmtAbsDollars(scaled.allocCents / 100)} allocation · ${((scaled.ddAlloc / scaled.bankrollCents) * 100).toFixed(1)}% of ${fmtAbsDollars(scaled.bankrollCents / 100)} starting bankroll`
                  : "observed sequence required"
            }
          />
          <Card
            kicker="Capitalized observed path"
            value={lastPrint ? "UNAVAILABLE" : fmtAbsDollars(num(equity?.ending_bankroll_cents) != null ? num(equity?.ending_bankroll_cents)! / 100 : null)}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "FIXED ALLOCATION · one historical order · not account equity"}
          />
          <Card
            kicker="Bootstrap capitalization"
            value={endCap ? `${fmtAbsDollars(centsToDollars(endCap.median))} median` : "—"}
            sub={
              endCap
                ? `observed ${fmtAbsDollars(centsToDollars(endCap.observed))} · P5 ${fmtAbsDollars(centsToDollars(endCap.p5))} · P95 ${fmtAbsDollars(centsToDollars(endCap.p95))} · not a forecast`
                : boot
                  ? "return vector present · sequence overlay needs contracts"
                  : "UNAVAILABLE · need N ≥ 2 observed returns"
            }
          />
          <Card
            kicker="Bootstrap max DD"
            value={ddBoot ? fmtAbsDollars(centsToDollars(ddBoot.median)) : "—"}
            sub={
              ddBoot
                ? `observed ${fmtAbsDollars(centsToDollars(ddBoot.observed))} · P95 ${fmtAbsDollars(centsToDollars(ddBoot.p95))}`
                : "—"
            }
          />
          <Card
            kicker="Longest streaks"
            value={`W ${String(asRec(seq?.streaks)?.longest_winning_streak ?? "—")} · L ${String(asRec(seq?.streaks)?.longest_losing_streak ?? "—")}`}
          />
          <Card
            kicker="Recovery"
            value={
              seq?.recovery_trades == null
                ? String(seq?.recovery_status ?? "—")
                : `${String(seq.recovery_trades)} trades`
            }
          />
        </div>
      </section>

      <section className="ws-level is-uncertainty">
        <p className="v2-kicker">Finite-sample</p>
        <h2>Uncertainty</h2>
        <p className="muted small">
          Observation-level t-interval, then game-cluster, then date-cluster. P(EV &gt; 0) is not
          computed — that would be a posterior. Independence is not assumed. N observations is not N
          independent experiments.
        </p>
        <div className="ws-breakdown">
          <Card
            kicker="Estimate / SE"
            value={
              lastPrint
                ? "UNAVAILABLE"
                : `${fmtCents(num(significance?.estimate) ?? num(observed?.mean_cents))} · ${fmtCents(num(significance?.standard_error) ?? num(evCi?.standard_error))}`
            }
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "mean and standard error of πᵢ"}
          />
          <Card
            kicker="t-statistic"
            value={
              lastPrint
                ? "UNAVAILABLE"
                : num(significance?.t_statistic) != null
                  ? num(significance?.t_statistic)!.toFixed(3)
                  : num(evCi?.t_statistic) != null
                    ? num(evCi?.t_statistic)!.toFixed(3)
                    : "—"
            }
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : `H0: EV = 0 · df ${String(significance?.df ?? evCi?.df ?? "—")}`}
          />
          <Card
            kicker="p-value"
            value={lastPrint ? "UNAVAILABLE" : fmtPValue(num(significance?.p_value) ?? num(evCi?.p_value))}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "two-sided Student-t · H0: EV = 0"}
          />
          <Card
            kicker="Observation-level CI"
            value={lastPrint ? "UNAVAILABLE" : evCi ? `${fmtCents(num(evCi.lower))} — ${fmtCents(num(evCi.upper))}` : "—"}
            sub={`IID-like t-interval · ZERO INSIDE CI · ${
              significance?.zero_inside_ci === true || evCi?.zero_inside_ci === true
                ? "YES"
                : significance?.zero_inside_ci === false || evCi?.zero_inside_ci === false
                  ? "NO"
                  : "—"
            }`}
          />
          <Card
            kicker="Game-cluster CI"
            value={clusterCiValue(gameCluster, evCi)}
            sub={gameCluster.reason}
          />
          <Card
            kicker="Date-cluster CI"
            value={clusterCiValue(dateCluster, evCi)}
            sub={dateCluster.reason}
          />
          <Card
            kicker="Interpretation"
            value={String(significance?.verdict ?? "—")}
            sub="not a buy/sell label"
          />
          <Card
            kicker="P(EV > 0)"
            value="NOT COMPUTED"
            sub="not a posterior · bootstrap share of means > 0 is separate"
          />
          <Card
            kicker="Bootstrap share means > 0"
            value={
              num(boot?.share_means_positive) != null
                ? formatPct(num(boot?.share_means_positive))
                : "—"
            }
            sub="DERIVED resample fraction · not P(EV > 0)"
          />
          <Card
            kicker="Bootstrap EV 95%"
            value={bootMean ? `${fmtCents(num(bootMean.lower))} — ${fmtCents(num(bootMean.upper))}` : "—"}
            sub="observation-level percentile · 10,000 · not a forecast"
          />
          <Card
            kicker="Book-price EV"
            value={book?.status === "HYPOTHETICAL" ? fmtCents(num(book.ev_cents)) : "—"}
            sub="l + p(w − l) · not observed path EV"
          />
          <Card
            kicker="Wilson-transformed EV CI"
            value={
              bookWilsonEv
                ? `${fmtCents(num(bookWilsonEv.lower))} — ${fmtCents(num(bookWilsonEv.upper))}`
                : "—"
            }
            sub={`ZERO INSIDE CI · ${bookWilsonEv?.zero_inside_ci === true ? "YES" : bookWilsonEv?.zero_inside_ci === false ? "NO" : "—"}`}
          />
          <Card
            kicker="Exact-binomial EV CI"
            value={
              bookExactEv
                ? `${fmtCents(num(bookExactEv.lower))} — ${fmtCents(num(bookExactEv.upper))}`
                : "—"
            }
            sub="Clopper–Pearson transformed · not Bayesian"
          />
          <Card
            kicker="Observed path Sharpe"
            value={lastPrint ? "UNAVAILABLE" : fmtSharpe(num(observed?.observed_path_sharpe) ?? num(observed?.sharpe_trade))}
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "UNANNUALIZED"}
          />
          <Card
            kicker="Sharpe bootstrap"
            value={
              lastPrint
                ? "UNAVAILABLE"
                : bootSharpe
                  ? `${num(bootSharpe.lower)?.toFixed(3) ?? "—"} — ${num(bootSharpe.upper)?.toFixed(3) ?? "—"}`
                  : "—"
            }
            sub={lastPrint ? LAST_TRADE_UNAVAILABLE : "not Wilson"}
          />
          <Card
            kicker="Risk of ruin"
            value="NOT COMPUTED"
            sub={String(ror?.reason ?? "No explicit stochastic bankroll model.")}
          />
        </div>
      </section>

      <details className="ws-level ws-advanced-math">
        <summary>Level 8 · Does it survive?</summary>
        {survive?.prose ? <p className="ws-desk-read">{String(survive.prose)}</p> : null}
        <p className="muted small">
          {lastPrint
            ? `${LAST_TRADE_UNAVAILABLE}. Break-even cost and 100/0 continuum are not executable last-trade economics.`
            : `Facts only. Not TRADE QUALITY. Not ALPHA. Break-even entry ${
                num(continuum?.breakeven_entry_cents) != null
                  ? `${num(continuum?.breakeven_entry_cents)!.toFixed(1)}¢`
                  : "—"
              } on the hypothetical 100/0 continuum.`}
        </p>
        {lastPrint ? (
          <p className="muted small">BREAK-EVEN TOTAL COST UNAVAILABLE.</p>
        ) : (
          <CostGrid cost={asRec(robust?.cost_sensitivity)} />
        )}
        <BucketTable title="Adjacent entry buckets" block={asRec(robust?.adjacent_entry_buckets)} />
        <SeasonTable block={asRec(robust?.season_partitions)} />
        <p className="muted small">
          Train / validation / OOS:{" "}
          {asRec(robust?.temporal_partitions)?.status === "OBSERVED"
            ? "pre-specified partitions present"
            : String(
                asRec(robust?.temporal_partitions)?.reason ??
                  "UNAVAILABLE — no sample_partition on this snapshot",
              )}
        </p>
      </details>

      <details className="ws-level ws-advanced-math">
        <summary>Level 9 · What is actually missing?</summary>
        <ExclusionLedger ledger={ledger} quality={quality} />
        <p className="muted small">
          Fees, fills, L2, and platform costs are UNAVAILABLE. PATH WIN ≠ TERMINAL YES.
          {lastPrint ? " LAST TRADE ≠ FILL." : " CANDLE PATH ≠ FILL."}
        </p>
        {tte?.status === "OBSERVED" && Array.isArray(tte.horizons) ? (
          <p className="muted small">
            Empirical time-to-exit:{" "}
            {(tte.horizons as Array<Record<string, unknown>>)
              .map((h) => `${String(h.horizon_seconds)}s ${(Number(h.incidence) * 100).toFixed(0)}%`)
              .join(" · ")}
            . Not a predictive probability.
          </p>
        ) : null}
        <pre className="ws-prov-json">{JSON.stringify(prov ?? {}, null, 2)}</pre>
      </details>
    </>
  );
}

function centsToDollars(v: unknown): number | null {
  const n = num(v);
  return n == null ? null : n / 100;
}

function scaleBootstrapCapital(
  end: Record<string, unknown> | null,
  contracts: number,
  bankrollCents: number,
  observedEnd: number | null,
): Record<string, unknown> | null {
  if (!end || contracts <= 0) return null;
  const cap = (v: unknown) => {
    const n = num(v);
    return n == null ? null : bankrollCents + n * contracts;
  };
  return {
    observed: observedEnd,
    median: cap(end.median),
    p5: cap(end.lower),
    p95: cap(end.upper),
  };
}

function scaleBootstrapDd(
  dd: Record<string, unknown> | null,
  contracts: number,
  observedDd: number | null,
): Record<string, unknown> | null {
  if (!dd || contracts <= 0) return null;
  const sc = (v: unknown) => {
    const n = num(v);
    return n == null ? null : n * contracts;
  };
  return {
    observed: observedDd,
    median: sc(dd.median),
    p5: sc(dd.lower),
    p95: sc(dd.p95 ?? dd.upper),
  };
}

function clusterCiValue(block: ClusterBlock, evCi: Record<string, unknown> | null): string {
  if (block.status === "DERIVED") {
    const m = asRec((block as unknown as Record<string, unknown>).mean);
    if (m && num(m.lower) != null) return `${fmtCents(num(m.lower))} — ${fmtCents(num(m.upper))}`;
  }
  if (block.status === "COINCIDENT") {
    return evCi ? `${fmtCents(num(evCi.lower))} — ${fmtCents(num(evCi.upper))}` : "COINCIDENT";
  }
  return "UNAVAILABLE";
}

function e4ToCents(v: unknown): number | null {
  const n = num(v);
  if (n == null) return null;
  return n >= 100 ? Math.round(n / 100) : n;
}

function entryFromExecuted(result: AnswerResult): number | null {
  const compile = asRec(result.compile);
  const question = asRec(compile?.question) ?? compile;
  const entries = Array.isArray(question?.entry_conditions)
    ? (question?.entry_conditions as unknown[])
    : [];
  const first = asRec(entries[0]);
  const fromCompile = first ? e4ToCents(first.price_e4) ?? num(first.price_cents) : null;
  if (fromCompile != null) return fromCompile;
  for (const step of result.population?.funnel ?? []) {
    const m = String(step.label ?? "").match(/(\d{3,5})\b/);
    if (!m) continue;
    const raw = Number(m[1]);
    if (raw >= 500 && raw <= 9500 && raw % 100 === 0) return Math.round(raw / 100);
  }
  return null;
}

function binaryEntrySensitivity(pWin: number | null): Record<string, unknown> | null {
  if (pWin == null || !Number.isFinite(pWin)) return null;
  const entries = [50, 55, 60, 65, 70, 75, 80, 85];
  return {
    status: "HYPOTHETICAL",
    label: "HYPOTHETICAL BINARY 100/0 · observed rate held fixed · not settlement",
    observed_win: pWin,
    rows: entries.map((k) => ({
      entry_cents: k,
      breakeven: k / 100,
      observed_win: pWin,
      margin: pWin - k / 100,
      payoff_ev_cents: 100 * pWin - k,
    })),
  };
}

function deskRead(input: {
  pHat: number | null;
  rateNoun: string;
  wilson: { lower: number; upper: number } | null;
  ev: number | null;
  evCi: Record<string, unknown> | null;
  book: Record<string, unknown> | null;
  settle: Record<string, unknown> | null;
  ddDollars: number | null;
  allocDollars: number;
  capitalizedEv: number | null;
  beWin: number | null;
}): string {
  const parts: string[] = [];
  if (input.pHat != null) {
    let s = `${formatPct(input.pHat)} observed ${input.rateNoun} rate`;
    if (input.wilson) {
      s += `. Wilson 95% CI ${formatPct(input.wilson.lower)}–${formatPct(input.wilson.upper)}`;
    }
    parts.push(`${s}.`);
  }
  if (input.ev != null) {
    let s = `Observed path EV ${fmtCents(input.ev)}`;
    if (input.evCi && num(input.evCi.lower) != null) {
      s += ` with 95% CI ${fmtCents(num(input.evCi.lower))} to ${fmtCents(num(input.evCi.upper))}`;
    }
    parts.push(`${s}.`);
  }
  if (input.book?.status === "HYPOTHETICAL") {
    const w = num(input.book.win_price_cents);
    const l = num(input.book.loss_price_cents);
    const chips =
      w != null && l != null ? ` under the specified ${w}/${l} payoff` : "";
    parts.push(`Book-price EV ${fmtCents(num(input.book.ev_cents))}${chips}.`);
    if (input.beWin != null && input.pHat != null) {
      parts.push(
        `Break-even WIN rate ${formatPct(input.beWin)}, observed ${formatPct(input.pHat)}.`,
      );
    }
  }
  if (!input.settle || input.settle.status === "UNAVAILABLE") {
    parts.push("Settlement EV unavailable because terminal settlement is missing.");
  } else {
    parts.push(`Settlement EV ${fmtCents(num(input.settle.ev_cents))} on measured YES/NO only.`);
  }
  if (input.capitalizedEv != null || input.ddDollars != null) {
    const bits = [`At a hypothetical ${fmtAbsDollars(input.allocDollars)} fixed allocation`];
    if (input.capitalizedEv != null) bits.push(`the observed path distribution has mean ${fmtDollars(input.capitalizedEv)}`);
    if (input.ddDollars != null) bits.push(`historical maximum sequence drawdown of ${fmtAbsDollars(input.ddDollars)}`);
    parts.push(`${bits.join(", ")}.`);
  }
  parts.push("Results are observational and hypothetical, not executed P&L.");
  return parts.join(" ");
}

function SensitivityTable({
  block,
  observedWin,
  title,
  observedCol,
  referenceCents,
}: {
  block: Record<string, unknown> | null;
  observedWin: number | null;
  title: string;
  observedCol: string;
  referenceCents: number | null;
}) {
  if (!block || block.status === "UNAVAILABLE") {
    return <p className="muted small">{title}: UNAVAILABLE.</p>;
  }
  const rows = Array.isArray(block.rows) ? (block.rows as Array<Record<string, unknown>>) : [];
  if (!rows.length) return null;
  return (
    <div className="ws-sens-wrap">
      <h3>{title}</h3>
      <p className="muted small">
        {String(block.label ?? "HYPOTHETICAL")} · P(WIN) ≠ EV. Same historical rate can be
        attractive at one entry and negative at another.
      </p>
      <div className="ws-sens-scroll">
        <table className="ws-sens-table">
          <thead>
            <tr>
              <th>ENTRY</th>
              <th>BREAKEVEN</th>
              <th>{observedCol}</th>
              <th>MARGIN</th>
              <th>PAYOFF EV</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const entry = num(r.entry_cents);
              return (
                <tr
                  key={String(r.entry_cents)}
                  className={entry === referenceCents ? "is-ref" : undefined}
                >
                  <td>{entry != null ? `${entry}¢` : "—"}</td>
                  <td>{formatPct(num(r.breakeven))}</td>
                  <td>{formatPct(num(r.observed_win) ?? observedWin)}</td>
                  <td>{fmtPctPts(num(r.margin))}</td>
                  <td>{fmtCents(num(r.payoff_ev_cents), 1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CostGrid({ cost }: { cost: Record<string, unknown> | null }) {
  if (!cost || cost.status === "UNAVAILABLE") {
    return <p className="muted small">Cost sensitivity unavailable — no gross EV.</p>;
  }
  const grid = Array.isArray(cost.grid) ? (cost.grid as Array<Record<string, unknown>>) : [];
  return (
    <div>
      <p className="muted small">
        Gross EV {fmtCents(num(cost.gross_ev_cents))} · break-even cost {fmtCents(num(cost.break_even_cost_cents))} ·
        not platform fees
      </p>
      <div className="ws-breakdown">
        {grid.map((row) => (
          <Card
            key={String(row.cost_cents)}
            kicker={`${row.cost_cents}¢ cost`}
            value={fmtCents(num(row.net_ev_cents))}
            sub="net = gross − cost"
          />
        ))}
      </div>
    </div>
  );
}

function BucketTable({
  title,
  block,
}: {
  title: string;
  block: Record<string, unknown> | null;
}) {
  if (!block || block.status === "UNAVAILABLE") {
    return <p className="muted small">{title}: UNAVAILABLE.</p>;
  }
  const buckets = Array.isArray(block.buckets) ? (block.buckets as Array<Record<string, unknown>>) : [];
  return (
    <div className="ws-bucket-list">
      <h3>{title}</h3>
      <p className="muted small">Not ranked as a discovered edge. Multiple-testing disclosure only.</p>
      <ul>
        {buckets.map((b) => {
          const win = asRec(b.win);
          return (
            <li key={String(b.bucket)}>
              {String(b.bucket)} · N={String(b.n)} · {formatPct(num(win?.p_hat))}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function SeasonTable({ block }: { block: Record<string, unknown> | null }) {
  if (!block || block.status === "UNAVAILABLE") {
    return <p className="muted small">Season replication: {String(block?.reason ?? "UNAVAILABLE")}</p>;
  }
  const seasons = Array.isArray(block.seasons) ? (block.seasons as Array<Record<string, unknown>>) : [];
  return (
    <ul className="ws-bucket-list">
      {seasons.map((s) => (
        <li key={String(s.season)}>
          {String(s.season)} · N={String(s.n)} · {formatPct(num(asRec(s.win)?.p_hat))}
        </li>
      ))}
    </ul>
  );
}

function ExclusionLedger({
  ledger,
  quality,
}: {
  ledger: Record<string, unknown> | null;
  quality: Record<string, unknown> | null;
}) {
  const ex = asRec(ledger?.exclusions) ?? {};
  return (
    <div>
      <p>
        Universe {String(ledger?.universe ?? "—")} · qualifying entry {String(ledger?.qualifying_entry ?? "—")} ·
        missing exit {String(ledger?.missing_exit ?? "—")} · terminal missing {String(ledger?.terminal_missing ?? "—")}
      </p>
      <ul>
        {Object.entries(ex).map(([k, v]) => (
          <li key={k}>
            {k}: {String(v)}
          </li>
        ))}
      </ul>
      {quality ? (
        <p className="muted small">
          Data quality · valid returns {String(quality.valid_returns)} · terminal coverage{" "}
          {String(quality.terminal_coverage)} · holding-time n {String(quality.holding_time_n)} · MAE n{" "}
          {String(quality.mae_n)}
        </p>
      ) : null}
    </div>
  );
}
