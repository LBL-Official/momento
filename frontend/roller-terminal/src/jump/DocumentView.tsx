import type { ReactElement } from "react";
import type { JumpDocument, SourceRef } from "./api/jumpApi";

type Props = {
  document: JumpDocument;
};

function renderInline(text: string, keyPrefix: string) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={`${keyPrefix}-${idx}`} className="ju-drive-mono">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${keyPrefix}-${idx}`}>{part.slice(2, -2)}</strong>;
    }
    return <span key={`${keyPrefix}-${idx}`}>{part}</span>;
  });
}

function MarkdownBody({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactElement[] = [];
  let fence: string[] | null = null;
  lines.forEach((line, idx) => {
    if (line.startsWith("```")) {
      if (fence) {
        blocks.push(
          <pre key={`pre-${idx}`} className="ju-drive-pre">
            {fence.join("\n")}
          </pre>
        );
        fence = null;
      } else {
        fence = [];
      }
      return;
    }
    if (fence) {
      fence.push(line);
      return;
    }
    if (line.startsWith("# ")) {
      blocks.push(<h1 key={idx}>{line.slice(2)}</h1>);
      return;
    }
    if (line.startsWith("## ")) {
      blocks.push(<h2 key={idx}>{line.slice(3)}</h2>);
      return;
    }
    if (line.startsWith("- ")) {
      blocks.push(
        <p key={idx} className="ju-drive-li">
          {renderInline(line.slice(2), `li-${idx}`)}
        </p>
      );
      return;
    }
    if (!line.trim()) {
      blocks.push(<div key={idx} className="ju-drive-gap" />);
      return;
    }
    blocks.push(<p key={idx}>{renderInline(line, `p-${idx}`)}</p>);
  });
  return <div className="ju-drive-md">{blocks}</div>;
}

export default function DocumentView({ document }: Props) {
  return (
    <article className="ju-drive-doc">
      <h1>{document.title}</h1>
      <MarkdownBody text={document.body_markdown || ""} />
      {document.provenance?.length ? <ProvenanceList rows={document.provenance} /> : null}
    </article>
  );
}

function ProvenanceList({ rows }: { rows: SourceRef[] }) {
  return (
    <section className="ju-drive-prov">
      <h2>Lineage</h2>
      <ul>
        {rows.map((row) => (
          <li key={`${row.owner}-${row.path}`}>
            <span className="ju-drive-mono">{row.owner}</span> {row.role}{" "}
            <span className="ju-drive-mono">{row.path}</span> ({row.status})
          </li>
        ))}
      </ul>
    </section>
  );
}
