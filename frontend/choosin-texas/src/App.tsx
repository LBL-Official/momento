import { useEffect, useState, type MouseEvent } from "react";
import Austin from "./Austin";
import Austin78 from "./Austin78";
import Lubbock from "./Lubbock";
import DreMoved from "./DreMoved";
import Book from "./Book";
import Dallas from "./Dallas";
import FortWorth from "./FortWorth";
import Katy from "./Katy";
import Sugarland from "./Sugarland";
import AskedSix from "./AskedSix";
import Paired from "./Paired";
import First78 from "./First78";
import Texas from "./Texas";
import Texas60 from "./Texas60";
import Texas75 from "./Texas75";
import Texas77 from "./Texas77";

type Page = "first78" | "texas" | "texas-60" | "paired" | "texas-75" | "texas-77" | "asked-six" | "dallas" | "lubbock" | "book" | "austin" | "austin-80" | "austin-risk" | "fortworth" | "katy" | "sugarland";

function hashParts(): { page: Page; katySlug?: string } {
  const raw = window.location.hash.replace(/^#/, "").replace(/^\//, "");
  if (raw === "texas-60" || raw === "texas60" || raw === "80-60") return { page: "texas-60" };
  if (raw === "paired" || raw === "paired-replay") return { page: "paired" };
  if (raw === "texas-77" || raw === "texas77") return { page: "texas-77" };
  if (raw === "texas-75" || raw === "texas75") return { page: "texas-75" };
  if (raw === "asked-six" || raw === "six") return { page: "asked-six" };
  if (raw === "dallas") return { page: "dallas" };
  if (raw === "lubbock") return { page: "lubbock" };
  if (raw === "book") return { page: "book" };
  if (raw === "austin/risk" || raw === "austin-risk") return { page: "austin-risk" };
  if (raw === "austin-80" || raw === "austin80") return { page: "austin-80" };
  if (raw === "austin") return { page: "austin" };
  if (raw === "fort-worth" || raw === "fortworth") return { page: "fortworth" };
  if (raw === "sugarland") return { page: "sugarland" };
  if (raw === "first80" || raw === "texas-80") return { page: "texas" };
  if (raw === "katy" || raw.startsWith("katy/")) {
    const slug = raw.startsWith("katy/") ? raw.slice("katy/".length) : undefined;
    return { page: "katy", katySlug: slug || undefined };
  }
  if (raw === "" || raw === "first78") return { page: "first78" };
  return { page: "first78" };
}

export default function App() {
  const [page, setPage] = useState<Page>(() => hashParts().page);
  const [katySlug, setKatySlug] = useState<string | undefined>(() => hashParts().katySlug);

  useEffect(() => {
    const onHash = () => {
      const next = hashParts();
      setPage(next.page);
      setKatySlug(next.katySlug);
    };
    window.addEventListener("hashchange", onHash);
    window.addEventListener("popstate", onHash);
    onHash();
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("popstate", onHash);
    };
  }, []);

  function go(next: Page, href: string) {
    return (event: MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault();
      if (window.location.hash !== href) {
        window.location.hash = href;
      }
      setPage(next);
      setKatySlug(next === "katy" && href.startsWith("#/katy/") ? href.slice("#/katy/".length) : undefined);
    };
  }

  return (
    <main className="desk">
      <header className="mast">
        <div>
          <p className="kicker">
            {page === "first78"
              ? "TEXAS · FIRST78 PATH LADDER"
              : page === "asked-six"
              ? "PAGE · ASKED-SIX · FIRST80 / FIRST75 / FIRST77 / FIRST81 / FIRST83"
              : page === "paired"
              ? "PAGE · PAIRED REPLAY · 80/40 VS 80/65 · SAME 936"
              : page === "texas-60"
              ? "PAGE 1A · 80/60 · FIRST80 STOP 60 · SAME DERIVED FOUR"
              : page === "texas-77"
              ? "PAGE 1C · TEXAS (77) · FIRST77 PATH LADDER"
              : page === "texas-75"
              ? "PAGE 1B · TEXAS (75) · FIRST75 PATH LADDER"
              : page === "dallas"
              ? "PAGE 2 · DALLAS · NBA 2Q/3Q"
              : page === "lubbock"
                ? "PAGE · LUBBOCK · SEASON PROGRESSION"
              : page === "book"
                ? "PAGE 3 · HISTORICAL REGISTERED RESEARCH BASELINE · 80/40"
                : page === "austin-risk"
                  ? "PAGE 4 · DRE · DYNAMIC RISK ENGINE"
                : page === "austin"
                  ? "PAGE 4 · AUSTIN · FIRST78 78/67"
                  : page === "austin-80"
                    ? "PAGE 4 · AUSTIN · FIRST80 604"
                  : page === "fortworth"
                    ? "PAGE 5 · FORT WORTH · POLICY CONTRACT"
                    : page === "katy"
                      ? katySlug
                        ? "PAGE 6 · KATY · EXPERIMENT"
                        : "PAGE 6 · KATY · EXPERIMENTS"
                    : page === "sugarland"
                      ? "PAGE 7 · SUGARLAND · PREGAME QUOTES"
                    : page === "texas"
                      ? "PAGE 1 · TEXAS · FIRST80 PATH LADDER"
                      : "TEXAS · FIRST78 PATH LADDER"}
          </p>
          <h1>
            {page === "first78"
              ? "Texas · FIRST78 Path Ladder"
              : page === "asked-six"
              ? "Asked-six"
              : page === "paired"
              ? "Paired replay"
              : page === "texas-60"
              ? "80/60"
              : page === "texas-77"
              ? "Texas (77)"
              : page === "texas-75"
              ? "Texas (75)"
              : page === "dallas"
              ? "Dallas"
              : page === "lubbock"
                ? "Lubbock"
              : page === "book"
                ? "80/40 baseline"
                : page === "austin-risk"
                  ? "DRE moved"
                : page === "austin"
                  ? "Austin · 78/67"
                  : page === "austin-80"
                    ? "Austin · 604"
                  : page === "fortworth"
                    ? "Fort Worth"
                    : page === "katy"
                      ? "Katy"
                    : page === "sugarland"
                      ? "Sugarland"
                    : page === "texas"
                      ? "Choosin Texas"
                      : "Texas"}
          </h1>
        </div>
        <div className="mast-meta">
          <nav className="page-nav">
            <a className={page === "first78" ? "is-on" : ""} href="#/" onClick={go("first78", "#/")}>
              Texas
            </a>
            <a className={page === "texas" ? "is-on" : ""} href="#/first80" onClick={go("texas", "#/first80")}>
              FIRST80
            </a>
            <a className={page === "texas-60" ? "is-on" : ""} href="#/texas-60" onClick={go("texas-60", "#/texas-60")}>
              80/60
            </a>
            <a className={page === "paired" ? "is-on" : ""} href="#/paired" onClick={go("paired", "#/paired")}>
              Paired
            </a>
            <a className={page === "texas-75" ? "is-on" : ""} href="#/texas-75" onClick={go("texas-75", "#/texas-75")}>
              Texas (75)
            </a>
            <a className={page === "texas-77" ? "is-on" : ""} href="#/texas-77" onClick={go("texas-77", "#/texas-77")}>
              Texas (77)
            </a>
            <a className={page === "asked-six" ? "is-on" : ""} href="#/asked-six" onClick={go("asked-six", "#/asked-six")}>
              Asked-six
            </a>
            <a className={page === "dallas" ? "is-on" : ""} href="#/dallas" onClick={go("dallas", "#/dallas")}>
              Dallas
            </a>
            <a className={page === "lubbock" ? "is-on" : ""} href="#/lubbock" onClick={go("lubbock", "#/lubbock")}>
              Lubbock
            </a>
            <a className={page === "book" ? "is-on" : ""} href="#/book" onClick={go("book", "#/book")}>
              80/40 baseline
            </a>
            <a className={page === "austin" ? "is-on" : ""} href="#/austin" onClick={go("austin", "#/austin")}>
              Austin
            </a>
            <a className={page === "austin-80" ? "is-on" : ""} href="#/austin-80" onClick={go("austin-80", "#/austin-80")}>
              Austin 80
            </a>
            <a href="http://127.0.0.1:5191/">DRE</a>
            <a className={page === "fortworth" ? "is-on" : ""} href="#/fort-worth" onClick={go("fortworth", "#/fort-worth")}>
              Fort Worth
            </a>
            <a className={page === "katy" ? "is-on" : ""} href="#/katy" onClick={go("katy", "#/katy")}>
              Katy
            </a>
            <a className={page === "sugarland" ? "is-on" : ""} href="#/sugarland" onClick={go("sugarland", "#/sugarland")}>
              Sugarland
            </a>
          </nav>
          <span className="pill">LIVE EXECUTION = FALSE</span>
          <span className="pill">no submit</span>
        </div>
      </header>
      {page === "first78" ? (
        <First78 />
      ) : page === "asked-six" ? (
        <AskedSix />
      ) : page === "dallas" ? (
        <Dallas />
      ) : page === "lubbock" ? (
        <Lubbock />
      ) : page === "paired" ? (
        <Paired />
      ) : page === "texas-60" ? (
        <Texas60 />
      ) : page === "texas-75" ? (
        <Texas75 />
      ) : page === "texas-77" ? (
        <Texas77 />
      ) : page === "book" ? (
        <Book />
      ) : page === "austin-risk" ? (
        <DreMoved />
      ) : page === "austin" ? (
        <Austin78 />
      ) : page === "austin-80" ? (
        <Austin />
      ) : page === "fortworth" ? (
        <FortWorth />
      ) : page === "katy" ? (
        <Katy slug={katySlug} />
      ) : page === "sugarland" ? (
        <Sugarland />
      ) : page === "texas" ? (
        <Texas />
      ) : (
        <First78 />
      )}
    </main>
  );
}
