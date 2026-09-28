"""ISO-8601 duration clocks from NBA PBP. Not a PIT claim."""

from __future__ import annotations

import re

_CLOCK = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$")


def clock_to_seconds(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    m = _CLOCK.match(text)
    if m is None:
        return None
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    secs = float(m.group(3) or 0.0)
    return int(round(hours * 3600 + mins * 60 + secs))


def e4_to_cents(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    try:
        return int(int(text) / 100)
    except (TypeError, ValueError):
        return None
