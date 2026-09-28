#!/usr/bin/env python3
"""Read-only research API for NBA Research Engine V2 Test 2.

Serves derived parquet/JSON. Does not trade. Default bind 127.0.0.1:8788.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from common import OUT, read_parquet_rows

HOST = "127.0.0.1"
PORT = 8788
_CACHE: dict = {}


def _load(name: str):
    if name not in _CACHE:
        path = OUT / name
        if name.endswith(".json"):
            _CACHE[name] = json.loads(path.read_text()) if path.exists() else {}
        else:
            _CACHE[name] = read_parquet_rows(path) if path.exists() else []
    return _CACHE[name]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[api]", fmt % args)

    def _send(self, code, obj, ctype="application/json"):
        body = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        path = unquote(u.path)
        qs = parse_qs(u.query)
        try:
            if path in ("/api/health", "/health"):
                return self._send(200, {"ok": True, "engine": "NBA_RESEARCH_ENGINE_V2_TEST2"})
            if path == "/api/summary":
                return self._send(200, _load("summary.json"))
            if path == "/api/trades":
                feats = _load("features.parquet")
                split = (qs.get("split") or [None])[0]
                q = (qs.get("q") or [""])[0].upper()
                primary = (qs.get("primary") or ["1"])[0] != "0"
                rows = []
                for r in feats:
                    if primary and not r.get("primary_set"):
                        continue
                    if split and r.get("dataset_split") != split:
                        continue
                    if q and q not in str(r.get("ticker") or "").upper() and q not in str(r.get("event_id") or "").upper():
                        continue
                    rows.append(
                        {
                            "observation_id": r["observation_id"],
                            "ticker": r.get("ticker"),
                            "game_date": r.get("game_date"),
                            "dataset_split": r.get("dataset_split"),
                            "Y_40_CLOSE": r.get("Y_40_CLOSE"),
                            "alignment_confidence": r.get("alignment_confidence"),
                            "possession_id": r.get("possession_id"),
                            "score_differential": r.get("score_differential"),
                            "mkt_yes_bid_cents": r.get("mkt_yes_bid_cents"),
                        }
                    )
                return self._send(200, {"n": len(rows), "rows": rows[:500]})
            if path.startswith("/api/trade/"):
                oid = path[len("/api/trade/") :]
                return self._send(200, trade_bundle(oid))
            if path == "/api/models":
                return self._send(200, _load("models.json"))
            if path == "/api/clusters":
                return self._send(200, _load("clusters.json"))
            if path == "/api/registry":
                return self._send(200, _load("experiment_registry.json"))
            return self._send(404, {"error": "not found"})
        except FileNotFoundError:
            return self._send(404, {"error": "artifact missing — run the pipeline"})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": str(exc)})


def trade_bundle(oid: str) -> dict:
    feats = {r["observation_id"]: r for r in _load("features.parquet")}
    obs = {r["observation_id"]: r for r in _load("observations.parquet")}
    snaps = {r["observation_id"]: r for r in _load("entry_snaps.parquet")}
    f = feats.get(oid)
    o = obs.get(oid)
    s = snaps.get(oid) or {}
    if not f and not o:
        return {"error": "unknown observation", "observation_id": oid}
    nba = s.get("nba_game_id")
    entry = int((o or f or {}).get("entry_decision_time") or 0)
    poss = [p for p in _load("possessions.parquet") if p.get("nba_game_id") == nba]
    poss.sort(key=lambda p: p.get("possession_sequence") or 0)
    at_entry = []
    after_entry = []
    for p in poss:
        row = {
            "possession_id": p.get("possession_id"),
            "possession_sequence": p.get("possession_sequence"),
            "period": p.get("period"),
            "possession_team": p.get("possession_team"),
            "possession_result": p.get("possession_result"),
            "points_scored": p.get("points_scored"),
            "home_score_end": p.get("home_score_end"),
            "away_score_end": p.get("away_score_end"),
            "wall_start_ts": p.get("wall_start_ts"),
            "wall_end_ts": p.get("wall_end_ts"),
            "wall_source": "DERIVED_PROXY",
        }
        if p.get("wall_start_ts") is not None and p["wall_start_ts"] <= entry:
            row["asof"] = "AT_ENTRY"
            at_entry.append(row)
        else:
            row["asof"] = "AFTER_ENTRY_NOT_A_FEATURE"
            after_entry.append(row)
    ov = None
    for r in _load("possession_market_overlay.parquet"):
        if r.get("observation_id") == oid:
            ov = r
            break
    return {
        "observation": o,
        "features": f,
        "snap": s,
        "overlay": ov,
        "at_entry_possessions": at_entry,
        "after_entry_possessions": after_entry,
        "entry_decision_time": entry,
        "visual_split": "Information at ENTRY_DECISION_TIME vs after entry. After-entry path is not a live feature.",
    }


def main() -> int:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"NBA Research Engine V2 API http://{HOST}:{PORT}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
