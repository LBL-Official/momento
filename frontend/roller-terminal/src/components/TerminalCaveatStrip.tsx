export default function TerminalCaveatStrip({ extra }: { extra?: string[] }) {
  return (
    <div className="caveats terminal-caveat-strip" aria-label="Epistemic constraints">
      <span>MEASUREMENT ≠ EDGE</span>
      <span className="caveat-sep">·</span>
      <span>SURVIVE ≠ TERMINAL YES</span>
      <span className="caveat-sep">·</span>
      <span>CANDLE PATH ≠ FILL</span>
      <span className="caveat-sep">·</span>
      <span>WORDS ≠ RESEARCH SPEC</span>
      {extra && extra.length > 0 ? (
        <>
          <span className="caveat-sep">·</span>
          <span className="caveat-extra">{extra.join(" · ")}</span>
        </>
      ) : null}
    </div>
  );
}
