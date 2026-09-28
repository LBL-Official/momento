export default function StatusBadge({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "ok" | "warn" | "bad" | "active";
}) {
  return <span className={`status-badge tone-${tone}`}>{label}</span>;
}

export function toneForStatus(status: string | null | undefined): "neutral" | "ok" | "warn" | "bad" | "active" {
  if (!status) return "neutral";
  const s = status.toUpperCase();
  if (["RUNNABLE", "COMPLETE", "RESOLVED", "CONTEXT", "IMPLEMENTED", "VALID", "CURRENT"].includes(s)) {
    return "ok";
  }
  // STALE is warn (not error) — prior authority, not a system failure
  if (
    [
      "PARTIAL",
      "UNRESOLVED",
      "PROPOSED",
      "EXECUTING",
      "QUERIED",
      "ACTIVE",
      "WARN",
      "STALE",
      "MODIFIED",
    ].includes(s) ||
    s.includes("STALE")
  ) {
    return "warn";
  }
  if (
    [
      "INVALID",
      "ABSENT",
      "UNSUPPORTED",
      "NOT_CONSTRUCTIBLE",
      "NO_MATCH",
      "UNVALIDATED",
      "NONE",
    ].includes(s)
  ) {
    return "bad";
  }
  return "neutral";
}
