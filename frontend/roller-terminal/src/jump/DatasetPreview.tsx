import { useEffect, useState } from "react";
import { previewArtifact } from "./api/jumpApi";

type Props = {
  artifactId: string;
};

export default function DatasetPreview({ artifactId }: Props) {
  const [status, setStatus] = useState<string>("LOADING");
  const [note, setNote] = useState<string>("");
  const [path, setPath] = useState<string | null>(null);
  const [body, setBody] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    previewArtifact(artifactId)
      .then((payload) => {
        if (cancelled) return;
        setStatus(payload.status);
        setNote(payload.note || "");
        setPath(payload.source_path);
        if (payload.preview == null) {
          setBody("Unavailable");
          return;
        }
        if (typeof payload.preview === "string") {
          setBody(payload.preview);
          return;
        }
        setBody(JSON.stringify(payload.preview, null, 2));
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setStatus("ERROR");
        setBody(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [artifactId]);

  return (
    <section className="ju-drive-preview">
      <h1>Preview</h1>
      <p className="ju-drive-meta">
        {status}
        {path ? ` · ${path}` : ""}
      </p>
      {note ? <p className="ju-drive-meta">{note}</p> : null}
      <pre className="ju-drive-pre">{body}</pre>
    </section>
  );
}
