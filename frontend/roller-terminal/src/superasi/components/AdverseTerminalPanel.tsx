import type { DetailPayload } from "../../v2/components/DetailDrawer";
import { fmtCents, fmtFrac, fmtPct } from "../format";
import { ADVERSE_OPTIONS, type AdverseP, type Decomp } from "../types/superasi";

type Props = {
  active: AdverseP;
  adverse?: Decomp["adverse_terminal"];
  onChange: (id: AdverseP) => void;
  onOpenDetail: (detail: DetailPayload) => void;
};

export default function AdverseTerminalPanel({ active, adverse, onChange, onOpenDetail }: Props) {
  return (
    <section className="ws-level" aria-label="Adverse terminal">
      <p className="v2-kicker">DECOMPOSITION LAYER 4 · Adverse p</p>
      <h2>Adverse terminal</h2>
      <p className="muted small">
        STRESS TEST · NOT A FORECAST. Holds observed s_W and s_L. SuperASI headline WR stays S
        on the source four-cell. Path-only packages (no settlement) stay DATA_REQUIRED.
      </p>
      {adverse?.status === "DATA_REQUIRED" ? (
        <p className="muted small">DATA_REQUIRED — {adverse.note || "terminal s_W / s_L unavailable."}</p>
      ) : null}
      <ol className="stax-ledger sa-scenario-ledger">
        {ADVERSE_OPTIONS.map((opt) => {
          const on = opt.id === active;
          return (
            <li key={opt.id}>
              <button
                type="button"
                className={`stax-ledger-row sa-ledger-btn${on ? " on" : ""}`}
                onClick={() => {
                  onChange(opt.id);
                  onOpenDetail({
                    title: `Adverse p · ${opt.label}`,
                    subtitle: "STRESS TEST · NOT A FORECAST",
                    value: adverse?.S_stressed ? `S* ${fmtPct(adverse.S_stressed)}` : "—",
                    sections: [
                      {
                        heading: "Held path terms",
                        body: (
                          <p className="evidence">
                            s_W {fmtFrac(adverse?.s_W)} · s_L {fmtFrac(adverse?.s_L)} · held{" "}
                            {adverse?.held_s_W && adverse?.held_s_L ? "yes" : "—"}
                          </p>
                        ),
                      },
                      {
                        heading: "Stressed identities",
                        body: (
                          <p>
                            p {fmtFrac(adverse?.p)} · S* {fmtFrac(adverse?.S_stressed)} · EV{" "}
                            {fmtCents(adverse?.EV_adverse)}
                          </p>
                        ),
                      },
                    ],
                  });
                }}
              >
                <span className="stax-ledger-index">{on ? "ACTIVE" : "STRESS"}</span>
                <span className="stax-ledger-name">{opt.label}</span>
                <span className="muted small">NOT A FORECAST</span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
