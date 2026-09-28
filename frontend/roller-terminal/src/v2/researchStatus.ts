import type { ApiAvailability } from "../api/base";
import type { Freshness, ValidationSnapshot } from "../researchFreshness";

export type HumanStatusKind = "ready" | "review" | "attention" | "idle";

export type HumanStatus = {
  kind: HumanStatusKind;
  title: string;
  detail: string;
};

export function humanResearchStatus(input: {
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  canRun: boolean;
  validationSnapshot: ValidationSnapshot | null;
  blockedByOverlay?: boolean;
  apiAvailability?: ApiAvailability | null;
}): HumanStatus {
  const {
    validationFreshness,
    executionFreshness,
    canRun,
    validationSnapshot,
    blockedByOverlay,
    apiAvailability,
  } = input;
  const status = validationSnapshot?.payload.status;

  if (apiAvailability === "API_UNREACHABLE") {
    return {
      kind: "attention",
      title: "API_UNREACHABLE",
      detail: "Terminal API at the configured base is not reachable. Not an empty population.",
    };
  }
  if (apiAvailability === "API_REQUEST_FAILED") {
    return {
      kind: "attention",
      title: "API_REQUEST_FAILED",
      detail: "Terminal API responded with an error. Not a research result.",
    };
  }

  if (blockedByOverlay) {
    return {
      kind: "attention",
      title: "Recognized — not constructible",
      detail: "The question is understood. Roller cannot execute the requested conditions.",
    };
  }

  if (validationFreshness === "STALE") {
    return {
      kind: "review",
      title: "Review required",
      detail: "The study changed after validation. Revalidate before running.",
    };
  }
  if (canRun) {
    return {
      kind: "ready",
      title: executionFreshness === "CURRENT" ? "Ready · result current" : "Ready to run",
      detail: "Population binding valid. Measurements supported.",
    };
  }
  if (status === "INVALID" || status === "UNRESOLVED") {
    return {
      kind: "attention",
      title: "Requires attention",
      detail: "Some required fields are unresolved.",
    };
  }
  if (executionFreshness === "STALE") {
    return {
      kind: "review",
      title: "Prior result",
      detail: "The study changed after the last measurement. This result is prior, not current.",
    };
  }
  return {
    kind: "idle",
    title: "Define a study",
    detail: "Choose a population to begin.",
  };
}
