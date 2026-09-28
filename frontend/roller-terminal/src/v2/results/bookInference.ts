/** Render helper for older envelopes that lack backend-transformed book EV CIs. */

function asRec(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : null;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function bookEvInterval(
  book: Record<string, unknown> | null,
  key: "wilson_ev_ci" | "exact_binomial_ev_ci",
  rateKey: "wilson" | "clopper_pearson",
): Record<string, unknown> | null {
  const existing = asRec(book?.[key]);
  if (existing && num(existing.lower) != null && num(existing.upper) != null) return existing;
  const rate = asRec(book?.[rateKey]);
  const w = num(book?.win_payoff_cents);
  const loss = num(book?.loss_payoff_cents);
  const loP = num(rate?.lower);
  const hiP = num(rate?.upper);
  if (w == null || loss == null || loP == null || hiP == null || w <= loss) return null;
  const span = w - loss;
  let lo = loss + loP * span;
  let hi = loss + hiP * span;
  if (span < 0) {
    const tmp = lo;
    lo = hi;
    hi = tmp;
  }
  return {
    lower: lo,
    upper: hi,
    zero_inside_ci: lo <= 0 && 0 <= hi,
    method: `${rateKey}_transformed_ev`,
  };
}
