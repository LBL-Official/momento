export const SPORTS = ["nba", "ncaab", "mlb", "wnba", "tennis"] as const;
export const DEFAULT_SPORT = "nba";
const LAST_SPORT_KEY = "jump.lastSport";

export type WarehousePage = "tables" | "relationships" | "queries" | "dictionary" | "files" | "info";
export type TableTab = "data" | "structure" | "properties" | "stats";

export type JumpLocation = {
  sport: string;
  canonicalKey?: string;
  docSlug?: string;
  databases?: boolean;
  dataPlane?: boolean;
  tradeId?: string;
  warehouseId?: string;
  tableName?: string;
  tableTab?: TableTab;
  warehousePage?: WarehousePage;
  queryId?: string;
};

export function sportLabel(sport: string): string {
  return sport.toUpperCase();
}

function isSport(value: string): boolean {
  return (SPORTS as readonly string[]).includes(value);
}

const TABLE_TABS: TableTab[] = ["data", "structure", "properties", "stats"];
const PAGES: WarehousePage[] = ["tables", "relationships", "queries", "dictionary", "files", "info"];

export function parseJumpHash(hash: string): JumpLocation {
  const raw = String(hash || "").replace(/^#/, "").replace(/^\//, "");
  const parts = raw.split("/").filter(Boolean);
  if (parts.length === 0) {
    return { sport: DEFAULT_SPORT };
  }
  if (parts[0].toLowerCase() === "databases") {
    return { sport: DEFAULT_SPORT, databases: true };
  }
  const sport = parts[0].toLowerCase();
  const known = isSport(sport) ? sport : DEFAULT_SPORT;
  if (parts[1] === "data") {
    return {
      sport: known,
      dataPlane: true,
      tradeId: parts[2] ? decodeURIComponent(parts[2]) : undefined,
    };
  }
  if (parts[1] === "warehouses" && parts[2]) {
    const loc: JumpLocation = {
      sport: known,
      warehouseId: decodeURIComponent(parts[2]),
      warehousePage: "tables",
    };
    const rest = parts.slice(3);
    if (rest[0] === "tables" && rest[1]) {
      loc.tableName = decodeURIComponent(rest[1]);
      const tab = rest[2]?.toLowerCase();
      loc.tableTab = TABLE_TABS.includes(tab as TableTab) ? (tab as TableTab) : "data";
      return loc;
    }
    if (rest[0] === "queries") {
      loc.warehousePage = "queries";
      if (rest[1]) loc.queryId = decodeURIComponent(rest[1]);
      return loc;
    }
    if (PAGES.includes(rest[0] as WarehousePage)) {
      loc.warehousePage = rest[0] as WarehousePage;
    }
    return loc;
  }
  return {
    sport: known,
    canonicalKey: parts[1] ? decodeURIComponent(parts[1]) : undefined,
    docSlug: parts[2] ? decodeURIComponent(parts[2]) : undefined,
  };
}

export function jumpHash(loc: JumpLocation): string {
  if (loc.databases) return "#/databases";
  const sport = (loc.sport || DEFAULT_SPORT).toLowerCase();
  if (loc.dataPlane) {
    return loc.tradeId
      ? `#/${sport}/data/${encodeURIComponent(loc.tradeId)}`
      : `#/${sport}/data`;
  }
  if (loc.warehouseId) {
    let hash = `#/${sport}/warehouses/${encodeURIComponent(loc.warehouseId)}`;
    if (loc.tableName) {
      hash += `/tables/${encodeURIComponent(loc.tableName)}`;
      if (loc.tableTab && loc.tableTab !== "data") hash += `/${encodeURIComponent(loc.tableTab)}`;
      return hash;
    }
    const page = loc.warehousePage && loc.warehousePage !== "tables" ? loc.warehousePage : null;
    if (page === "queries") {
      hash += "/queries";
      if (loc.queryId) hash += `/${encodeURIComponent(loc.queryId)}`;
      return hash;
    }
    if (page) hash += `/${page}`;
    return hash;
  }
  let hash = `#/${sport}`;
  if (loc.canonicalKey) hash += `/${encodeURIComponent(loc.canonicalKey)}`;
  if (loc.docSlug) hash += `/${encodeURIComponent(loc.docSlug)}`;
  return hash;
}

export function rememberSport(sport: string): void {
  try {
    sessionStorage.setItem(LAST_SPORT_KEY, sport.toLowerCase());
  } catch {
    /* ignore */
  }
}

export function lastSport(): string {
  try {
    const value = sessionStorage.getItem(LAST_SPORT_KEY);
    if (value && isSport(value)) return value;
  } catch {
    /* ignore */
  }
  return DEFAULT_SPORT;
}

export function docId(canonicalKey: string, slug: string): string {
  return `doc.${canonicalKey}.${slug}`;
}

export function warehouseSport(warehouseId: string): string {
  if (warehouseId === "atp" || warehouseId === "wta") return "tennis";
  return warehouseId;
}
