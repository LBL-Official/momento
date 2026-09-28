import type { DetailPayload } from "../../v2/components/DetailDrawer";
import { fmtCents, fmtFrac } from "../format";
import { FILL_ALGORITHMS, type FillAlgorithm, type MixSummary } from "../types/superasi";

type Props = {
  active: FillAlgorithm;
  mixes?: Record<string, MixSummary>;
  onChange: (id: FillAlgorithm) => void;
  onOpenDetail: (detail: DetailPayload) => void;
};

export default function FillAlgorithmPanel({ active, mixes, onChange, onOpenDetail }: Props) {
  return (
    <section className="ws-level" aria-label="Research exit mixes">
      <p className="v2-kicker">DECOMPOSITION LAYER 2 · Exit loss</p>
      <h2>Research exit mixes</h2>
      <p className="muted small">
        NOT A FILL · RESEARCH EXIT MIX. Changing the mix changes headline EV and must not
        change N, four-cell, p, α, s_W, s_L, or S.
      </p>
      <ol className="stax-ledger sa-scenario-ledger">
        {FILL_ALGORITHMS.map((algo) => {
          const mix = mixes?.[algo.id];
          const on = algo.id === active;
          return (
            <li key={algo.id}>
              <button
                type="button"
                className={`stax-ledger-row sa-ledger-btn${on ? " on" : ""}`}
                onClick={() => {
                  onChange(algo.id);
                  onOpenDetail({
                    title: algo.label,
                    subtitle: "NOT A FILL · RESEARCH EXIT MIX",
                    value: mix?.EV ? `EV ${fmtCents(mix.EV)}` : "Not yet decomposed",
                    sections: [
                      {
                        heading: "Definition",
                        body: <p>{mix?.definition || "Research mix. Candle path is not a fill."}</p>,
                      },
                      {
                        heading: "n / mean L / EV",
                        body: (
                          <p className="evidence">
                            path losses {mix?.n_path_loss ?? "—"} · available {mix?.n_available ?? "—"} ·
                            mean L {mix?.mean_L ? `${fmtFrac(mix.mean_L)} (${fmtCents(mix.mean_L)})` : "—"} ·
                            EV {mix?.EV ? `${fmtFrac(mix.EV)} (${fmtCents(mix.EV)})` : "—"}
                          </p>
                        ),
                      },
                      {
                        heading: "Status",
                        body: <p>{mix?.research_status || "RESEARCH EXIT MIX"} · NOT A FILL</p>,
                      },
                    ],
                  });
                }}
              >
                <span className="stax-ledger-index">{on ? "ACTIVE" : "MIX"}</span>
                <span className="stax-ledger-name">{algo.label}</span>
                <span className="evidence">{mix?.EV ? fmtCents(mix.EV) : "—"}</span>
                <span className="muted small">{mix?.mean_L ? `mean L ${fmtCents(mix.mean_L)}` : "NOT A FILL"}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
