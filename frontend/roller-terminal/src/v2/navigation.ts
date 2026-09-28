export type PrimaryRoute = "start" | "entry" | "exit" | "confirm" | "results";
export type SecondaryRoute = "explorer" | "library" | "dictionary" | "docs" | "templates" | "auto_roller" | "settings";
export type LegacyRoute = "define" | "review" | "lab" | "data" | "phenomena";
export type AppRoute = PrimaryRoute | SecondaryRoute | LegacyRoute;

export type LabStep = "population" | "conditions" | "measurements" | "name" | "review";

export type NavItem = {
  id: AppRoute;
  label: string;
  hint: string;
};

export const PRIMARY_NAV: NavItem[] = [
  { id: "start", label: "Quick Start", hint: "What are you researching?" },
  { id: "entry", label: "Entry", hint: "What begins the research path?" },
  { id: "exit", label: "Exit", hint: "What do you observe after entry?" },
  { id: "confirm", label: "Confirm", hint: "Read the question, then run" },
  { id: "results", label: "Results", hint: "What happened?" },
];

export const SECONDARY_NAV: NavItem[] = [
  { id: "library", label: "Results Labs", hint: "Saved warehouse strategies and CSV artifacts" },
  { id: "explorer", label: "Explorer", hint: "Browse what exists" },
  { id: "dictionary", label: "Dictionary", hint: "Words Roller recognizes" },
  { id: "docs", label: "Docs", hint: "How to read a result" },
  { id: "settings", label: "Settings", hint: "Bankroll and risk per trade for new downstream work" },
  { id: "auto_roller", label: "Auto Roller", hint: "Ingest and verify the warehouse" },
];

export const DEFAULT_ROUTE: PrimaryRoute = "start";

export const NAV_ITEMS: NavItem[] = [...PRIMARY_NAV, ...SECONDARY_NAV];

export type ResearchMode = "overview" | "define" | "results" | "evidence";

export function normalizeRoute(route: AppRoute): AppRoute {
  if (route === "lab" || route === "define" || route === "data") return "start";
  if (route === "review") return "confirm";
  return route;
}

export function isPrimaryRoute(route: AppRoute): route is PrimaryRoute {
  return (
    route === "start" ||
    route === "entry" ||
    route === "exit" ||
    route === "confirm" ||
    route === "results"
  );
}
