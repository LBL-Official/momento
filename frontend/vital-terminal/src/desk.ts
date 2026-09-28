import type { VitalBot } from "./api/vitalApi";

export function isMlb001(botId: string | undefined | null): boolean {
  return botId === "mlb-001" || botId === "mlb-bot-one";
}

export function bookEnvironment(bot: VitalBot | null | undefined): "DEMO" | "PRODUCTION" {
  if (!bot || isMlb001(bot.bot_id)) return "PRODUCTION";
  return bot.environment === "PRODUCTION" ? "PRODUCTION" : "DEMO";
}

export function activationLabel(bot: VitalBot): string {
  if (isMlb001(bot.bot_id) || bot.kind === "grandfathered") {
    return bot.activation || bot.status || "OBSERVATION_UNAVAILABLE";
  }
  if (bot.activation === "RUNNING" || bot.status === "RUNNING") return "RUNNING";
  if (bot.activation === "RUNNING_DEMO" || bot.status === "RUNNING_DEMO") return "RUNNING_DEMO";
  return "DEPLOY_REQUIRED";
}

function rank(bot: VitalBot): number {
  if (isMlb001(bot.bot_id) || bot.kind === "grandfathered") return 0;
  const label = activationLabel(bot);
  if (label === "RUNNING") return 1;
  if (label === "RUNNING_DEMO") return 2;
  return 3;
}

export function sortBots(bots: VitalBot[]): VitalBot[] {
  return [...bots].sort((a, b) => {
    const ra = rank(a);
    const rb = rank(b);
    if (ra !== rb) return ra - rb;
    return String(a.bot_id).localeCompare(String(b.bot_id));
  });
}

export function sportLabel(bot: VitalBot | null | undefined): string {
  if (!bot) return "—";
  if (isMlb001(bot.bot_id) || bot.kind === "grandfathered") return "MLB";
  const value = String(bot.engine?.sport || bot.sport || "").trim();
  return value ? value.toUpperCase() : "—";
}

export function bookLabel(bot: VitalBot | null | undefined): string {
  if (!bot) return "—";
  if (isMlb001(bot.bot_id)) return "PRODUCTION";
  return bot.environment || "DEMO";
}

export function filterBots(
  bots: VitalBot[],
  sport: string,
  environment: string,
): VitalBot[] {
  return sortBots(bots).filter((bot) => {
    const rowSport =
      isMlb001(bot.bot_id) || bot.kind === "grandfathered"
        ? "mlb"
        : String(bot.engine?.sport || bot.sport || "").toLowerCase();
    if (sport && sport !== "all" && rowSport !== sport) return false;
    const env = bot.environment || (isMlb001(bot.bot_id) ? "PRODUCTION" : "DEMO");
    if (environment && environment !== "all" && env !== environment) return false;
    return true;
  });
}
