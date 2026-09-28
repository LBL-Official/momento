#!/usr/bin/env python3
"""Asked-six FIRST83 ledger for Choosin Texas.

Same τ definition as first75_slice_not40_given_w.py, threshold 83.
Same clock slices as the FIRST80 / FIRST75 / FIRST77 asked-six exports.
One row per FIRST83 event.

TABLES.md has no FIRST83. This CSV is the measured book. Do not invent
Lebronner FIRST83 rows. Do not reuse first80 / first75 / first77 CSVs.

Research only. Candle path ≠ fill. Does not change live FIRST01.
Does not invent L2.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first_tau_asked_six_export as T  # noqa: E402

TAU = 83


def main() -> None:
    T.export_tau(TAU)


if __name__ == "__main__":
    main()
