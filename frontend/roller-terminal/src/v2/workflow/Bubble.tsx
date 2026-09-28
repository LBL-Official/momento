import {
  availabilityLabel,
  type Availability,
  type CatalogItem,
} from "../catalog/availabilityCatalog";

type Props = {
  item: CatalogItem;
  selected: boolean;
  onToggle: () => void;
  disabled?: boolean;
};

/** A selectable research dimension, rendered as a bordered instrument cell.
 *  Availability semantics are unchanged — only their presentation. */
export default function Bubble({ item, selected, onToggle, disabled }: Props) {
  const mark =
    item.availability === "IMPLEMENTED"
      ? "●"
      : item.availability === "REGISTERED"
        ? "○"
        : item.availability === "OPERATION_REQUIRED"
          ? "✕"
          : "◇";
  const className = [
    "ws-bubble",
    selected ? "on" : "",
    item.availability === "IMPLEMENTED" ? "" : "recognized",
    `avail-${item.availability.toLowerCase()}`,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button
      type="button"
      className={className}
      aria-pressed={selected}
      disabled={disabled}
      title={item.note}
      onClick={onToggle}
    >
      <span className="ws-bubble-label">
        <span className="ws-honesty">{mark}</span> {item.label}
      </span>
      {item.availability !== "IMPLEMENTED" ? (
        <span className="ws-bubble-avail">{availabilityLabel(item.availability)}</span>
      ) : null}
    </button>
  );
}

export function AvailabilityNote({ availability, note }: { availability: Availability; note?: string }) {
  if (availability === "IMPLEMENTED") return null;
  return (
    <p className="ws-coming-soon">
      <strong>{availabilityLabel(availability)}</strong>
      {note ? <span>{note}</span> : null}
    </p>
  );
}
