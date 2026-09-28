import type { ReactNode } from "react";

type Active = "bracket" | "bdr" | "tk-ultra";

type Props = {
  kicker: string;
  title: string;
  active: Active;
  scroll?: boolean;
  children: ReactNode;
};

export function Desk({ kicker, title, active, scroll = false, children }: Props) {
  return (
    <main className={active === "bracket" && !scroll ? "desk desk-fit" : "desk"}>
      <header className="mast">
        <div>
          <p className="kicker">{kicker}</p>
          <h1>{title}</h1>
        </div>
        <div className="mast-meta">
          <nav className="page-nav">
            <a className={active === "bracket" ? "is-on" : ""} href="#/">
              Bracket
            </a>
            <a className={active === "bdr" ? "is-on" : ""} href="#/bdr">
              BDR
            </a>
            <a className={active === "tk-ultra" ? "is-on" : ""} href="#/tk-ultra">
              TK Ultra
            </a>
          </nav>
          <span className="pill">LIVE EXECUTION = FALSE</span>
          <span className="pill">CANDLE PATH ≠ FILL</span>
        </div>
      </header>
      {children}
    </main>
  );
}
