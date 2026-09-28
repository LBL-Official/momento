import type { DetailPayload } from "../../v2/components/DetailDrawer";
import { FEE_SCENARIOS, type FeeScenario } from "../types/superasi";

type Props = {
  active: FeeScenario;
  fees?: Record<string, unknown> | null;
  net?: Record<string, unknown> | null;
  onChange: (id: FeeScenario) => void;
  onOpenDetail: (detail: DetailPayload) => void;
};

export default function FeeScenarioPanel({ active, fees, net, onChange, onOpenDetail }: Props) {
  const status = typeof fees?.status === "string" ? fees.status : "ESTIMATED";
  return (
    <section className="ws-level" aria-label="Estimated fee schedule">
      <p className="v2-kicker">DECOMPOSITION LAYER 3 · Fees</p>
      <h2>Estimated fee schedule</h2>
      <p className="muted small">
        ESTIMATED FEE SCHEDULE · PublishedScheduleEstimate only. Does not mutate S or the
        ROLLER source.
      </p>
      <ol className="stax-ledger sa-scenario-ledger">
        {FEE_SCENARIOS.map((sc) => {
          const on = sc.id === active;
          return (
            <li key={sc.id}>
              <button
                type="button"
                className={`stax-ledger-row sa-ledger-btn${on ? " on" : ""}`}
                onClick={() => {
                  onChange(sc.id);
                  onOpenDetail({
                    title: sc.label,
                    subtitle: "ESTIMATED FEE SCHEDULE",
                    value: status,
                    sections: [
                      {
                        heading: "Counts",
                        body: (
                          <p className="evidence">
                            maker {String(fees?.maker_count ?? "—")} · taker {String(fees?.taker_count ?? "—")} ·
                            unavailable {String(fees?.unavailable_count ?? "—")}
                          </p>
                        ),
                      },
                      {
                        heading: "Net estimate",
                        body: (
                          <p>
                            {net && typeof net === "object" && "note" in net
                              ? String(net.note)
                              : "NET ESTIMATE is research EV minus ESTIMATED fee. Not executed P&L."}
                          </p>
                        ),
                      },
                    ],
                  });
                }}
              >
                <span className="stax-ledger-index">{on ? "ACTIVE" : "FEE"}</span>
                <span className="stax-ledger-name">{sc.label}</span>
                <span className="muted small">{status}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
