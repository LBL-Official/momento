/**
 * Last-trade observation basis. Do not infer YES BID from TradableBar.bid.
 */

export const LAST_TRADE_UNAVAILABLE = "LAST TRADE ≠ EXECUTABLE PRICE";

export type LastTradeBasisResult = {
  observation_basis?: string | null;
  provenance?: Record<string, unknown> | null;
  analysis?: Record<string, unknown> | null;
  mlb?: { observation_basis?: string } | null;
};

export function isLastTradePrint(result: LastTradeBasisResult | null | undefined): boolean {
  if (!result) return false;
  const basis = String(result.observation_basis || result.mlb?.observation_basis || "");
  const prov = result.provenance || {};
  if (basis.includes("LAST_TRADE")) return true;
  if (String(prov.price_basis || "").includes("LAST_TRADE")) return true;
  if (String(prov.market_data_type || "").includes("LAST_TRADE")) return true;
  if (String(prov.market_data || "").includes("last_trade")) return true;
  const observed = result.analysis?.observed_returns as { reason?: string } | undefined;
  return String(observed?.reason || "").includes("LAST TRADE");
}
