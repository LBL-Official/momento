import { useEffect, useState } from "react";
import { fetchConnection, fetchSystems } from "./api";
import Bdr from "./Bdr";
import TkUltra from "./TkUltra";
import TkUltra78 from "./TkUltra78";
import TkUltraInputs from "./TkUltraInputs";
import ExecutionDesk from "./ExecutionDesk";
import NbaExecutionDesk from "./NbaExecutionDesk";
import OntologicX from "./OntologicX";
import OntologicY from "./OntologicY";
import QuadrantCanvas from "./QuadrantCanvas";
import { Desk } from "./Desk";
import IngestDesk from "./IngestDesk";
import Inspector from "./Inspector";
import OrchestraDesk from "./OrchestraDesk";
import PositmanDesk from "./PositmanDesk";
import ReconciliationDesk from "./ReconciliationDesk";
import type { SystemRow } from "./types";

type Route =
  | { kind: "bracket" }
  | { kind: "backend"; id: string }
  | { kind: "bdr"; slug: string | null }
  | { kind: "tk-ultra" }
  | { kind: "tk-ultra-80" }
  | { kind: "tk-ultra-inputs" }
  | { kind: "ingest" }
  | { kind: "reconciliation" }
  | { kind: "orchestra" }
  | { kind: "execution"; sport: "MLB" | "WNBA" }
  | { kind: "nba-execution" }
  | { kind: "ontologic-x" }
  | { kind: "ontologic-y" }
  | { kind: "bball-7867"; sport: "NBA" | "NCAAB" | null };

function parseHash(): Route {
  const hash = window.location.hash.replace(/^#/, "");
  if (hash === "/tk-ultra/live-inputs" || hash === "/tk-ultra/inputs") return { kind: "tk-ultra-inputs" };
  if (hash === "/tk-ultra-80") return { kind: "tk-ultra-80" };
  if (hash === "/tk-ultra") return { kind: "tk-ultra" };
  if (hash === "/ingest") return { kind: "ingest" };
  if (hash === "/reconciliation") return { kind: "reconciliation" };
  if (hash === "/orchestra") return { kind: "orchestra" };
  if (hash === "/execution/mlb") return { kind: "execution", sport: "MLB" };
  if (hash === "/execution/wnba") return { kind: "execution", sport: "WNBA" };
  if (hash === "/execution/nba") return { kind: "nba-execution" };
  if (hash === "/ontologic-x") return { kind: "ontologic-x" };
  if (hash === "/ontologic-y") return { kind: "ontologic-y" };
  if (hash === "/bball-7867") return { kind: "bball-7867", sport: null };
  if (hash === "/bball-7867/nba") return { kind: "bball-7867", sport: "NBA" };
  if (hash === "/bball-7867/ncaab") return { kind: "bball-7867", sport: "NCAAB" };
  const bdr = hash.match(/^\/bdr(?:\/([a-z0-9-]+))?$/);
  if (bdr) return { kind: "bdr", slug: bdr[1] ?? null };
  const system = hash.match(/^\/systems\/([a-z0-9_]+)$/);
  if (system) return { kind: "backend", id: system[1] };
  return { kind: "bracket" };
}

function go(hash: string) {
  window.location.hash = hash;
}

export default function App() {
  const [systems, setSystems] = useState<SystemRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [route, setRoute] = useState<Route>(parseHash);

  useEffect(() => {
    let cancelled = false;
    let delay = 400;
    async function connect() {
      while (!cancelled) {
        try {
          const [rows] = await Promise.all([fetchSystems(), fetchConnection()]);
          if (cancelled) return;
          if (rows.length) {
            setSystems(rows);
            setError(null);
            return;
          }
        } catch (exc) {
          if (!cancelled) setError((exc as Error).message);
        }
        await new Promise((resolve) => window.setTimeout(resolve, delay));
        delay = Math.min(Math.floor(delay * 1.5), 4000);
      }
    }
    connect();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!systems.length) return;
    const timer = window.setInterval(() => {
      fetchSystems()
        .then((rows) => {
          if (rows.length) {
            setSystems(rows);
            setError(null);
          }
        })
        .catch((exc: Error) => setError(exc.message));
      fetchConnection().catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [systems.length]);

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function openBackend(id: string) {
    go(`/systems/${id}`);
  }

  function openFrontend(row: SystemRow) {
    const target = row.frontend_target;
    if (target.kind === "momento_page") {
      const hash = target.url.split("#")[1];
      if (!hash || hash === "/") {
        go("/");
        return;
      }
      go(hash.startsWith("/") ? hash : `/${hash}`);
      return;
    }
    window.open(target.url, "_blank", "noopener,noreferrer");
  }

  if (route.kind === "backend" && route.id === "position_management") {
    return <PositmanDesk onHome={() => go("/")} />;
  }
  if (route.kind === "backend") {
    return <Inspector systemId={route.id} mode="backend" onHome={() => go("/")} />;
  }
  if (route.kind === "bdr") {
    return (
      <Bdr
        slug={route.slug}
        onHome={() => go("/")}
        onCatalog={() => go("/bdr")}
        onOpen={(slug) => go(`/bdr/${slug}`)}
      />
    );
  }
  if (route.kind === "tk-ultra-inputs") {
    return <TkUltraInputs onHome={() => go("/")} onDesk={() => go("/tk-ultra")} />;
  }
  if (route.kind === "tk-ultra-80") {
    return <TkUltra onHome={() => go("/")} />;
  }
  if (route.kind === "tk-ultra") {
    return <TkUltra78 onHome={() => go("/")} />;
  }
  if (route.kind === "ingest") {
    return <IngestDesk onHome={() => go("/")} />;
  }
  if (route.kind === "reconciliation") {
    return <ReconciliationDesk onHome={() => go("/")} />;
  }
  if (route.kind === "orchestra") {
    return <OrchestraDesk onHome={() => go("/")} />;
  }
  if (route.kind === "nba-execution") {
    return <NbaExecutionDesk onHome={() => go("/")} />;
  }
  if (route.kind === "ontologic-x") {
    return <OntologicX onHome={() => go("/")} />;
  }
  if (route.kind === "ontologic-y") {
    return <OntologicY onHome={() => go("/")} />;
  }
  if (route.kind === "execution") {
    return <ExecutionDesk sport={route.sport} onHome={() => go("/")} />;
  }
  if (route.kind === "bball-7867" && systems.length) {
    return (
      <QuadrantCanvas
        systems={systems}
        focus="nba-ncaab"
        lockedQuadrant={route.sport === "NBA" ? "quad-1" : route.sport === "NCAAB" ? "quad-2" : null}
        onBackend={openBackend}
        onFrontend={openFrontend}
        onExecution={(quadrantId) =>
          go(quadrantId === "quad-4" ? "/execution/mlb" : quadrantId === "quad-1" ? "/execution/nba" : "/execution/wnba")
        }
      />
    );
  }
  if (!systems.length) {
    return (
      <Desk kicker="Momento systems" title="CONNECTING" active="bracket">
        <p className="muted">Waiting for the ROLLER controller. Retrying automatically.</p>
        {error ? <p className="muted">{error}</p> : null}
      </Desk>
    );
  }
  return (
    <QuadrantCanvas
      systems={systems}
      onBackend={openBackend}
      onFrontend={openFrontend}
      onExecution={(quadrantId) =>
        go(quadrantId === "quad-4" ? "/execution/mlb" : quadrantId === "quad-1" ? "/execution/nba" : "/execution/wnba")
      }
    />
  );
}
