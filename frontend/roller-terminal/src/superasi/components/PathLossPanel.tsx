import type { DetailPayload } from "../../v2/components/DetailDrawer";
import { fmtFrac } from "../format";
import type { Decomp } from "../types/superasi";

type Props = {
  windows?: Decomp["path_windows"];
  onOpenDetail: (detail: DetailPayload) => void;
};

const KEYS = ["-5", "-1", "0", "5"] as const;

export default function PathLossPanel({ windows, onOpenDetail }: Props) {
  const offsets = windows?.offsets ?? {};
  return (
    <section className="ws-level" aria-label="Path-loss windows">
      <p className="v2-kicker">DECOMPOSITION LAYER 5 · Path geometry</p>
      <h2>Path-loss windows ±5</h2>
      <p className="muted small">
        Offset 0 is FIRST THROUGH-CLOSE / PATH EVENT, not FILLED AT 40. Missing minutes are
        UNAVAILABLE. Window default is ±5.
      </p>
      <ol className="stax-ledger sa-scenario-ledger sa-path-ledger">
        {KEYS.map((key) => {
          const row = offsets[key];
          const label =
            key === "0" ? "FIRST THROUGH-CLOSE / PATH EVENT" : `offset ${key}`;
          return (
            <li key={key}>
              <button
                type="button"
                className="stax-ledger-row sa-ledger-btn"
                onClick={() =>
                  onOpenDetail({
                    title: label,
                    subtitle: "CANDLE PATH ≠ FILL",
                    value: row?.mean ? fmtFrac(row.mean) : "UNAVAILABLE",
                    sections: [
                      {
                        heading: "Observed close cents",
                        body: (
                          <p className="evidence">
                            n = {row?.n ?? "—"} · sum = {row?.sum ?? "—"} · median = {row?.median ?? "—"}
                          </p>
                        ),
                      },
                      {
                        heading: "Pre-event note",
                        body: (
                          <p>
                            {windows?.pre_t40_38_40_trades != null
                              ? `${windows.pre_t40_38_40_trades} path-loss observation(s) had a 38–40 close in t−5…t−1 (measurement only).`
                              : "—"}
                          </p>
                        ),
                      },
                    ],
                  })
                }
              >
                <span className="stax-ledger-name">{label}</span>
                <span className="evidence">{row?.mean ? fmtFrac(row.mean) : "UNAVAILABLE"}</span>
                <span className="muted small">n = {row?.n ?? "—"} · median {row?.median ?? "—"}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
