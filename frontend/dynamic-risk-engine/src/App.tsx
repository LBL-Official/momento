import { useEffect, useState } from "react";
import type { DreBook } from "./api";
import Objective from "./Objective";
import PositionList from "./PositionList";
import PositionPage from "./PositionPage";
import RiskReport from "./RiskReport";

type Route =
  | { page: "list"; slice: string; q: string; book: DreBook }
  | { page: "position"; id: string; asOf: string | null; book: DreBook }
  | { page: "research"; book: DreBook }
  | { page: "objective"; book: DreBook };

function parseHash(): Route {
  let raw = window.location.hash.replace(/^#\/?/, "");
  let book: DreBook = "78";
  if (raw === "first80" || raw.startsWith("first80/") || raw.startsWith("first80?")) {
    book = "80";
    raw = raw.replace(/^first80\/?/, "");
  }
  const [path, queryString] = raw.split("?");
  const params = new URLSearchParams(queryString || "");
  if (path === "objective") return { page: "objective", book };
  if (path === "research") return { page: "research", book };
  if (path.startsWith("positions/")) {
    const id = decodeURIComponent(path.slice("positions/".length).split("/")[0] || "");
    if (id) return { page: "position", id, asOf: params.get("as_of"), book };
  }
  return { page: "list", slice: params.get("slice") || "", q: params.get("q") || "", book };
}

function listHash(slice: string, q: string, book: DreBook): string {
  const params = new URLSearchParams();
  if (slice) params.set("slice", slice);
  if (q) params.set("q", q);
  const suffix = params.toString();
  const base = book === "80" ? "#/first80" : "#/";
  if (!suffix) return base;
  return book === "80" ? `#/first80?${suffix}` : `#/?${suffix}`;
}

export default function App() {
  const [route, setRoute] = useState<Route>(parseHash);

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const page = route.page;
  const book = route.book;

  return (
    <main className="desk">
      <header className="mast">
        <div>
          <p className="kicker">DYNAMIC RISK ENGINE</p>
          <h1>DREVO</h1>
        </div>
        <div className="mast-meta">
          <nav className="page-nav">
            <a className={page === "list" || page === "position" ? "is-on" : undefined} href={book === "80" ? "#/first80" : "#/"}>
              Positions
            </a>
            <a className={page === "research" ? "is-on" : undefined} href={book === "80" ? "#/first80/research" : "#/research"}>
              Research
            </a>
            <a className={page === "objective" ? "is-on" : undefined} href={book === "80" ? "#/first80/objective" : "#/objective"}>
              Objective
            </a>
            <a href={book === "78" ? "#/first80" : "#/"}>{book === "78" ? "80/40" : "78/67"}</a>
            <a href="http://127.0.0.1:5182#/">Choosin Texas</a>
            <a href="http://127.0.0.1:5182#/austin">Austin</a>
            <a href="http://127.0.0.1:5194/">Positman</a>
            <a href="http://127.0.0.1:5193/">Systimo</a>
          </nav>
          <span className="pill">LIVE EXECUTION = FALSE</span>
          <span className="pill">no submit</span>
          <span className="pill">HISTORICAL / REPLAY</span>
        </div>
      </header>
      <p className="muted">
        {book === "78" ? "FIRST78→67 operating surface." : "FIRST80 80/40 operating surface."} Choosin Texas is the
        fixed trade prior. Austin is point-in-time historical conditional observation. Drevo does not classify risk
        and does not authorize intervention. Candle path ≠ fill. PORTFOLIO_OBJECTIVE_V1 calculus is NOT_IMPLEMENTED.
        Positman plan is a structural gate only.
      </p>
      {page === "objective" ? (
        <Objective book={book} />
      ) : page === "research" ? (
        book === "78" ? (
          <p className="muted">UNAVAILABLE. The 604 experiment index is not mounted on the 78/67 desk.</p>
        ) : (
          <RiskReport />
        )
      ) : page === "position" ? (
        <PositionPage positionId={route.id} asOf={route.asOf} book={book} />
      ) : (
        <PositionList
          slice={route.slice}
          query={route.q}
          book={book}
          onSlice={(slice) => {
            window.location.hash = listHash(slice, route.q, book);
          }}
          onQuery={(q) => {
            window.location.hash = listHash(route.slice, q, book);
          }}
        />
      )}
    </main>
  );
}
