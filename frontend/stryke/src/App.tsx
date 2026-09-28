import { useEffect, useState } from "react";

type Folder = {
  folder_id?: string;
  display_name?: string;
  population_n?: number;
  population_note?: string;
};

type SheetRow = { label?: string; value?: string };

type Signal = {
  status?: string;
  label?: string;
  rows?: SheetRow[];
  pointers?: {
    choosin?: { universe?: string; n?: number };
    austin?: { universe?: string; n?: number };
  };
  detail?: string;
};

function folderId(): string {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return hash.split("?")[0];
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${path}`);
  return (await res.json()) as T;
}

export default function App() {
  const [open, setOpen] = useState(folderId());
  const [folders, setFolders] = useState<Folder[]>([]);
  const [signal, setSignal] = useState<Signal | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onHash = () => setOpen(folderId());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    getJson<{ folders?: Folder[] }>("/api/stryke/folders")
      .then((body) => setFolders(body.folders || []))
      .catch((exc: Error) => setError(exc.message));
  }, []);

  useEffect(() => {
    if (!open) {
      setSignal(null);
      return;
    }
    setError(null);
    getJson<Signal>(`/api/stryke/signal/${encodeURIComponent(open)}`)
      .then(setSignal)
      .catch((exc: Error) => setError(exc.message));
  }, [open]);

  const choosin = signal?.pointers?.choosin;
  const austin = signal?.pointers?.austin;

  return (
    <main className="desk">
      <p className="kicker">SIGNAL GENERATION</p>
      <h1>Stryke</h1>
      <p className="lede">
        FIRST78 78/67 sheet from the Jump folder. Algorithmic execution reads this table and does not submit.
        Candle path is not a fill.
      </p>
      <div className="mast-meta">
        <span className="pill">LIVE EXECUTION = FALSE</span>
        <span className="pill">NOT_DEPLOYED</span>
      </div>
      {error ? <p className="banner">{error}</p> : null}
      {open ? (
        <>
          <p><a className="back" href="#/">Folders</a></p>
          <h2>{signal?.label || open}</h2>
          <div className="sheet-wrap">
            <table className="sheet">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Signal</th>
                </tr>
              </thead>
              <tbody>
                {(signal?.rows || []).map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td>{row.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="caption">
            Choosin {choosin?.universe || "UNAVAILABLE"} {choosin?.n ?? "UNAVAILABLE"} · Austin {austin?.universe || "UNAVAILABLE"} {austin?.n ?? "UNAVAILABLE"} · Touch (N) stays on the sheet
          </p>
        </>
      ) : (
        <section>
          <h2>Jump folders</h2>
          {folders.map((folder) => (
            <button
              key={folder.folder_id}
              type="button"
              className="folder"
              onClick={() => {
                window.location.hash = `#/${folder.folder_id}`;
              }}
            >
              {folder.display_name || folder.folder_id}
              <small>
                {folder.folder_id} · membership pointer N={folder.population_n ?? "UNAVAILABLE"}. {folder.population_note}
              </small>
            </button>
          ))}
          {folders.length === 0 ? <p className="caption">UNAVAILABLE</p> : null}
        </section>
      )}
    </main>
  );
}
