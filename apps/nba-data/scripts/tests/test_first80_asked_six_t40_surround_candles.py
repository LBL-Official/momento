#!/usr/bin/env python3
"""T40 surround window. Does not change live FIRST01."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def _load():
    path = SCRIPTS / "first80_asked_six_t40_surround_candles.py"
    spec = importlib.util.spec_from_file_location(
        "first80_asked_six_t40_surround_candles", path
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _load()


class TestSurround(unittest.TestCase):
    def test_offsets_include_t40_and_neighbors(self):
        quotes = [{"ts": 1000 + 60 * i, "bid_c": 8000 - 100 * i} for i in range(11)]
        # T40 at index 5
        win = M.surround(quotes, 5, window=5)
        self.assertEqual([q["offset_min"] for q in win], list(range(-5, 6)))
        self.assertTrue(win[5]["is_t40_bar"])
        self.assertEqual(win[5]["ts"], 1000 + 60 * 5)

    def test_clips_at_tape_edge(self):
        quotes = [{"ts": i} for i in range(3)]
        win = M.surround(quotes, 0, window=5)
        self.assertEqual([q["offset_min"] for q in win], [0, 1, 2])

    def test_identity(self):
        self.assertEqual(M.EXPECTED_STOP, 299)
        self.assertEqual(M.WINDOW, 5)


if __name__ == "__main__":
    unittest.main()
