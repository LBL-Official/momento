import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  getDocument,
  getDriveFolder,
  getDriveRecent,
  getDriveRoot,
  getDriveTree,
  getResearchObject,
  refreshIndex,
  searchDrive,
  type DriveArtifact,
  type JumpDocument,
  type JumpObject,
  type SearchHit,
  type SportInfo,
} from "./api/jumpApi";
import DataExplorer from "./data/DataExplorer";
import DatasetPreview from "./DatasetPreview";
import DetailsPanel from "./DetailsPanel";
import DocumentView from "./DocumentView";
import ErrorState from "./ErrorState";
import FolderView from "./FolderView";
import JumpSidebar from "./JumpSidebar";
import JumpTopBar from "./JumpTopBar";
import SearchResults from "./SearchResults";
import WarehouseShell from "./warehouse/WarehouseShell";
import {
  DEFAULT_SPORT,
  docId,
  jumpHash,
  parseJumpHash,
  rememberSport,
  sportLabel,
  warehouseSport,
  type JumpLocation,
} from "./routing";

type Props = {
  onBackToSuperASI: () => void;
  onBackToRoller: () => void;
};

export default function JumpShell({ onBackToSuperASI, onBackToRoller }: Props) {
  const [location, setLocation] = useState(() => parseJumpHash(window.location.hash));
  const [sports, setSports] = useState<SportInfo[]>([]);
  const [tree, setTree] = useState<DriveArtifact[]>([]);
  const [children, setChildren] = useState<DriveArtifact[]>([]);
  const [crumbs, setCrumbs] = useState<{ artifact_id: string; name: string }[]>([]);
  const [selected, setSelected] = useState<DriveArtifact | null>(null);
  const [object, setObject] = useState<JumpObject | null>(null);
  const [document, setDocument] = useState<JumpDocument | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [recent, setRecent] = useState<SearchHit[]>([]);
  const [emptyMessage, setEmptyMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const go = useCallback((next: JumpLocation) => {
    rememberSport(next.sport || DEFAULT_SPORT);
    const hash = jumpHash(next);
    if (window.location.hash !== hash) {
      window.location.hash = hash;
    }
    setLocation(next);
  }, []);

  useEffect(() => {
    function onHash() {
      setLocation(parseJumpHash(window.location.hash));
      setHits(null);
    }
    window.addEventListener("hashchange", onHash);
    if (!window.location.hash || window.location.hash === "#" || window.location.hash === "#/") {
      window.location.hash = `#/${DEFAULT_SPORT}`;
    }
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    getDriveTree()
      .then((body) => setTree(body.tree))
      .catch((err: Error) => setError(err.message));
    getDriveRecent()
      .then((body) => setRecent(body.results))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const sport = location.sport || DEFAULT_SPORT;
    setError(null);
    setPreviewId(null);
    getDriveRoot(sport.toUpperCase())
      .then((body) => {
        if (cancelled) return;
        setSports(body.sports);
        if (location.databases) {
          setChildren([]);
          setEmptyMessage(null);
          setCrumbs([
            { artifact_id: "root", name: "Jump" },
            { artifact_id: "databases", name: "Warehouses" },
          ]);
          setSelected(null);
          setObject(null);
          setDocument(null);
          return;
        }
        if (location.dataPlane) {
          setChildren([]);
          setEmptyMessage(null);
          setCrumbs([
            { artifact_id: "root", name: "Jump" },
            { artifact_id: `sport.${sport}`, name: sportLabel(sport) },
            { artifact_id: "research-data", name: "DATA / RESEARCH" },
          ]);
          setSelected(null);
          setObject(null);
          setDocument(null);
          return;
        }
        if (location.warehouseId) {
          setChildren([]);
          setEmptyMessage(null);
          setCrumbs([
            { artifact_id: "root", name: "Jump" },
            { artifact_id: `sport.${sport}`, name: sportLabel(sport) },
            { artifact_id: `wh.${location.warehouseId}`, name: `${location.warehouseId} warehouse` },
          ]);
          setSelected(null);
          setObject(null);
          setDocument(null);
          return;
        }
        if (!location.canonicalKey) {
          setChildren(body.children);
          setEmptyMessage(body.empty_message || null);
          setCrumbs([
            { artifact_id: "root", name: "Jump" },
            { artifact_id: `sport.${sport}`, name: sportLabel(sport) },
          ]);
          setSelected(null);
          setObject(null);
          setDocument(null);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });

    if (location.databases || location.dataPlane || location.warehouseId || !location.canonicalKey) {
      return () => {
        cancelled = true;
      };
    }

    getResearchObject(location.canonicalKey)
      .then((body) => {
        if (!cancelled) setObject(body.object);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });

    if (location.docSlug) {
      const id = docId(location.canonicalKey, location.docSlug);
      getDocument(id)
        .then((body) => {
          if (cancelled) return;
          setDocument({
            doc_id: body.document.doc_id,
            canonical_key: body.document.canonical_key,
            slug: body.document.slug,
            title: body.document.title,
            body_markdown: body.document.body_markdown || body.document.body || "",
            provenance: body.document.provenance || [],
            status: body.document.status,
          });
          setCrumbs(body.breadcrumbs);
          setSelected({
            artifact_id: body.document.doc_id,
            name: body.document.title,
            artifact_type: "DOCUMENT",
            system_owner: "data_modeling",
            canonical_key: body.document.canonical_key,
            provenance: body.document.provenance,
          });
          setChildren([]);
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message);
        });
      return () => {
        cancelled = true;
      };
    }

    getDriveFolder(`research.${location.canonicalKey}`)
      .then((body) => {
        if (cancelled) return;
        setChildren(body.children);
        setCrumbs(body.breadcrumbs);
        setSelected(body.folder);
        setDocument(null);
        setPreviewId(null);
        setEmptyMessage(body.empty_message || null);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [location.sport, location.canonicalKey, location.docSlug, location.warehouseId, location.databases]);

  function openNestedFolder(id: string) {
    getDriveFolder(id)
      .then((body) => {
        setChildren(body.children);
        setCrumbs(body.breadcrumbs);
        setSelected(body.folder);
        setDocument(null);
        setPreviewId(null);
        setEmptyMessage(body.empty_message || null);
      })
      .catch((err: Error) => setError(err.message));
  }

  function openFolderId(id: string) {
    if (id === "root") {
      go({ sport: location.sport || DEFAULT_SPORT });
      return;
    }
    if (id === "databases") {
      go({ sport: DEFAULT_SPORT, databases: true });
      return;
    }
    if (id.startsWith("wh.")) {
      const warehouseId = id.slice("wh.".length);
      go({ sport: warehouseSport(warehouseId), warehouseId });
      return;
    }
    if (id.startsWith("sport.") && !id.includes(".research.")) {
      go({ sport: id.slice("sport.".length) });
      return;
    }
    const nested = id.match(/^sport\.[a-z]+\.research\.(.+)$/);
    if (nested) {
      go({ sport: location.sport, canonicalKey: nested[1] });
      return;
    }
    if (
      id.startsWith("research.") &&
      (id.endsWith(".data") || id.endsWith(".models") || id.endsWith(".source-artifacts"))
    ) {
      openNestedFolder(id);
      return;
    }
    const research = id.match(/^research\.(.+)$/);
    if (research) {
      go({ sport: location.sport, canonicalKey: research[1] });
    }
  }

  function openRow(row: DriveArtifact) {
    if (row.artifact_type === "FOLDER") {
      const id = row.artifact_id;
      if (id === "databases") {
        go({ sport: DEFAULT_SPORT, databases: true });
        return;
      }
      if (id === "research-data") {
        go({ sport: location.sport || DEFAULT_SPORT, dataPlane: true });
        return;
      }
      if (id.endsWith(".data") || id.endsWith(".models") || id.endsWith(".source-artifacts")) {
        openNestedFolder(id);
        return;
      }
      if (row.canonical_key) {
        go({ sport: (row.sport || location.sport).toLowerCase(), canonicalKey: row.canonical_key });
        return;
      }
      openFolderId(id);
      return;
    }
    if (row.artifact_type === "WAREHOUSE" || row.kind === "warehouse") {
      const warehouseId = row.warehouse_id || String(row.name || "").split(" ")[0];
      if (warehouseId) {
        go({ sport: warehouseSport(warehouseId), warehouseId });
      }
      return;
    }
    if (row.artifact_type === "TABLE" || row.kind === "table") {
      const warehouseId = row.warehouse_id || String(row.name || "").split(".")[0];
      const tableName = row.table_name || String(row.name || "").split(".")[1];
      if (warehouseId && tableName) {
        go({
          sport: warehouseSport(warehouseId),
          warehouseId,
          tableName,
          tableTab: "data",
          warehousePage: "tables",
        });
      }
      return;
    }
    if (row.artifact_type === "DOCUMENT" && row.canonical_key && (row.slug || row.doc_id)) {
      const slug = row.slug || String(row.doc_id || "").split(".").pop() || "";
      go({ sport: location.sport, canonicalKey: row.canonical_key, docSlug: slug });
      return;
    }
    if (row.artifact_type === "ARTIFACT") {
      setPreviewId(row.artifact_id);
      setSelected(row);
      setDocument(null);
    }
  }

  function openHit(hit: SearchHit) {
    if (hit.kind === "sport" && hit.sport) {
      go({ sport: hit.sport.toLowerCase() });
      setHits(null);
      return;
    }
    if (hit.kind === "document" && hit.canonical_key && hit.slug) {
      go({
        sport: (hit.sport || location.sport).toLowerCase(),
        canonicalKey: hit.canonical_key,
        docSlug: hit.slug,
      });
      setHits(null);
      return;
    }
    if (hit.canonical_key) {
      go({ sport: (hit.sport || location.sport).toLowerCase(), canonicalKey: hit.canonical_key });
      setHits(null);
    }
  }

  function runSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!q) {
      setHits(null);
      return;
    }
    searchDrive(q)
      .then((body) => setHits(body.results))
      .catch((err: Error) => setError(err.message));
  }

  function onRefresh() {
    refreshIndex()
      .then(() => {
        setLocation({ ...parseJumpHash(window.location.hash) });
        getDriveTree().then((body) => setTree(body.tree));
      })
      .catch((err: Error) => setError(err.message));
  }

  const recentForSport = recent.filter(
    (row) => !row.sport || row.sport.toLowerCase() === (location.sport || DEFAULT_SPORT).toLowerCase()
  );

  const title = useMemo(() => {
    if (document) return document.title;
    if (object) return object.display_name;
    return sportLabel(location.sport || DEFAULT_SPORT);
  }, [document, object, location.sport]);

  return (
    <div className="ju-drive">
      <JumpTopBar
        crumbs={crumbs}
        query={query}
        onQuery={setQuery}
        onSearch={runSearch}
        onOpenCrumb={openFolderId}
        onRefresh={onRefresh}
      />
      <div className="ju-drive-body">
        <JumpSidebar
          sports={sports}
          sport={location.sport}
          tree={tree}
          onSport={(sport) => go({ sport })}
          onOpen={openRow}
        />
        <main className="ju-drive-main">
          {error ? <ErrorState message={error} /> : null}
          {hits ? (
            <SearchResults hits={hits} onOpen={openHit} />
          ) : location.dataPlane ? (
            <DataExplorer
              tradeId={location.tradeId}
              onTrade={(tradeId) => go({ sport: location.sport || DEFAULT_SPORT, dataPlane: true, tradeId })}
            />
          ) : location.databases || location.warehouseId ? (
            <WarehouseShell location={location} onGo={go} />
          ) : previewId ? (
            <DatasetPreview artifactId={previewId} />
          ) : document ? (
            <DocumentView document={document} />
          ) : (
            <>
              <FolderView title={title} rows={children} emptyMessage={emptyMessage} onOpen={openRow} />
              {!location.canonicalKey && recentForSport.length ? (
                <section>
                  <h2>Recent</h2>
                  <SearchResults hits={recentForSport} onOpen={openHit} />
                </section>
              ) : null}
            </>
          )}
        </main>
        <DetailsPanel
          selected={selected}
          object={object}
          onOpenRoller={onBackToRoller}
          onOpenSuperASI={onBackToSuperASI}
        />
      </div>
    </div>
  );
}
