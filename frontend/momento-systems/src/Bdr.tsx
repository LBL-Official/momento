import { useEffect, useState, type MouseEvent } from "react";
import { fetchBdrCatalog, fetchBdrDocument } from "./api";
import { Desk } from "./Desk";
import { Markdown } from "./markdown";
import type { BdrCard, BdrCatalog, BdrDocument } from "./types";

type Props = {
  slug: string | null;
  onHome: () => void;
  onCatalog: () => void;
  onOpen: (slug: string) => void;
};

function DocCard({ card, onOpen }: { card: BdrCard; onOpen: (slug: string) => void }) {
  return (
    <a
      href={card.hash}
      className="experiment-card"
      onClick={(event) => {
        event.preventDefault();
        onOpen(card.slug);
      }}
    >
      <h3>
        {card.number}. {card.title}
      </h3>
      <p className="muted">{card.kind}</p>
      <p>{card.blurb}</p>
    </a>
  );
}

export default function Bdr({ slug, onHome, onCatalog, onOpen }: Props) {
  const [catalog, setCatalog] = useState<BdrCatalog | null>(null);
  const [doc, setDoc] = useState<BdrDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchBdrCatalog()
      .then((body) => {
        if (!cancelled) setCatalog(body);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!slug) {
      setDoc(null);
      return;
    }
    setError(null);
    fetchBdrDocument(slug)
      .then((body) => {
        if (!cancelled) setDoc(body);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  function goHome(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onHome();
  }

  function goCatalog(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onCatalog();
  }

  if (error) {
    return (
      <Desk kicker="Hedging analysis · BDR" title="BDR # MOMENTO SYSTEMS" active="bdr">
        <p className="banner is-bad">{error}</p>
      </Desk>
    );
  }

  if (!catalog) {
    return (
      <Desk kicker="Hedging analysis · BDR" title="BDR # MOMENTO SYSTEMS" active="bdr">
        <p className="muted">UNREAD</p>
      </Desk>
    );
  }

  if (slug && doc) {
    return (
      <Desk kicker="BDR # MOMENTO SYSTEMS" title={doc.title} active="bdr">
        <div className="page-meta">
          <a className="pill" href="#/" onClick={goHome}>
            bracket
          </a>
          <a className="pill" href="#/bdr" onClick={goCatalog}>
            BDR
          </a>
          <span className="pill">research only</span>
        </div>
        <article className="wide" style={{ marginTop: 14 }}>
          <h2>ALL DOCUMENTS</h2>
          <nav className="doc-hop">
            {catalog.documents.map((card) => (
              <a
                key={card.slug}
                className={card.slug === doc.slug ? "is-on" : ""}
                href={card.hash}
                onClick={(event) => {
                  event.preventDefault();
                  onOpen(card.slug);
                }}
              >
                {card.number}. {card.title}
              </a>
            ))}
          </nav>
        </article>
        <article className="wide" style={{ marginTop: 14 }}>
          <Markdown source={doc.markdown} />
        </article>
      </Desk>
    );
  }

  if (slug && !doc) {
    return (
      <Desk kicker="Hedging analysis · BDR" title="BDR # MOMENTO SYSTEMS" active="bdr">
        <p className="muted">UNREAD</p>
      </Desk>
    );
  }

  return (
    <Desk kicker="Hedging analysis · BDR" title="BDR # MOMENTO SYSTEMS" active="bdr">
      <p className="muted" style={{ marginTop: 14 }}>
        {catalog.subtitle}
      </p>
      <div className="banner">
        <h2>LIMITATIONS</h2>
        <p>LIVE EXECUTION = FALSE</p>
        <p>CANDLE PATH ≠ FILL · 40¢ is a trigger, not a fill.</p>
        <p>Not an 18th system. Does not change FIRST01 / 80/81/83/89.</p>
        <p className="muted">{catalog.note}</p>
      </div>
      <h2 style={{ marginTop: 22 }}>ALL DOCUMENTS</h2>
      <section className="grid">
        {catalog.documents.map((card) => (
          <DocCard key={card.slug} card={card} onOpen={onOpen} />
        ))}
      </section>
    </Desk>
  );
}
