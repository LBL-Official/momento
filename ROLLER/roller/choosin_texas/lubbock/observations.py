"""Attach season rank to existing FIRST80 rows. Does not rescan the warehouse."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass

from roller.choosin_texas.lubbock.schedule import RankedGame, repo_root
from roller.choosin_texas.lubbock.stats import entry_band, explicit_payoff, hold_payoff
from roller.choosin_texas.models import ChoosinTexasError

ASKED_SIX = "research/first80_asked_six_chatgpt_export/first80_asked_six.csv"
MLB_LEDGER = "research/mlb_first80_80_40_v1/ledger_baseline.json"

PRIMARY = {
    "NBA": "nba_austin_604",
    "NCAAB": "ncaab_derived_332",
    "WNBA": "wnba_asked_six",
    "MLB": "mlb_ledger_v1",
}
HOLM_SEASON = {"NBA": "2025-2026", "NCAAB": "2025-2026", "WNBA": "2025", "MLB": "2025"}


@dataclass
class Observation:
    sport: str
    universe_id: str
    event_ticker: str
    slice_id: str
    game_date: str
    csv_phase: str
    season_id: str
    phase: str
    league_local_date: str
    game_rank: int | None
    g: int | None
    decile: int | None
    quintile: int | None
    join_status: str
    evaluation_status: str
    t40: bool | None
    yes: bool | None
    payoff: int | None
    hold: int | None
    entry_cents: int | None
    entry_band: str
    period: str
    nominal_entry: bool
    gross_pnl_cents: int | None


def _blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def _bool(value: str | None) -> bool | None:
    if _blank(value):
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes"}:
        return True
    if text in {"0", "false", "f", "no"}:
        return False
    return None


def _int(value: str | None) -> int | None:
    if _blank(value):
        return None
    return int(float(str(value).strip()))


def _index(games: list[RankedGame]) -> dict[tuple[str, str], RankedGame]:
    found: dict[tuple[str, str], RankedGame] = {}
    for game in games:
        found[(game.sport, game.event_ticker)] = game
    return found


def _attach(sport: str, ticker: str, index: dict[tuple[str, str], RankedGame]) -> dict:
    game = index.get((sport, ticker))
    if game is None:
        return {
            "season_id": "",
            "phase": "",
            "league_local_date": "",
            "game_rank": None,
            "g": None,
            "decile": None,
            "quintile": None,
            "join_status": "SCHEDULE_UNJOINED",
        }
    return {
        "season_id": game.season_id,
        "phase": game.phase,
        "league_local_date": game.league_local_date,
        "game_rank": game.game_rank,
        "g": game.g,
        "decile": game.decile,
        "quintile": game.quintile,
        "join_status": "JOINED",
    }


def load_observations(games: list[RankedGame]) -> tuple[list[Observation], dict]:
    index = _index(games)
    root = repo_root()
    rows: list[Observation] = []
    audit = {
        "asked_six_rows": 0,
        "t40_post_min_mismatch": 0,
        "mlb_gross_pnl_mismatch": 0,
        "missing_settlement": 0,
        "schedule_unjoined": 0,
        "by_sport": {},
    }
    sport_counts: dict[str, int] = {}
    with (root / ASKED_SIX).open(newline="") as handle:
        for raw in csv.DictReader(handle):
            sport = raw["sport"].strip()
            sport_counts[sport] = sport_counts.get(sport, 0) + 1
            t40 = _bool(raw.get("T40"))
            post_min = _int(raw.get("post_entry_min_yes_bid_cents"))
            if t40 is not None and post_min is not None and ((post_min <= 40) != t40):
                audit["t40_post_min_mismatch"] += 1
            yes = _bool(raw.get("terminal_yes"))
            if yes is None:
                yes = _bool(raw.get("W"))
            if yes is None and not t40:
                audit["missing_settlement"] += 1
            entry = _int(raw.get("market_yes_bid"))
            attached = _attach(sport, raw["event_id"].strip(), index)
            if attached["join_status"] != "JOINED":
                audit["schedule_unjoined"] += 1
            rows.append(
                Observation(
                    sport=sport,
                    universe_id=PRIMARY[sport],
                    event_ticker=raw["event_id"].strip(),
                    slice_id=(raw.get("slice") or "").strip(),
                    game_date=(raw.get("game_date") or "").strip(),
                    csv_phase=(raw.get("season_phase") or "").strip(),
                    evaluation_status="PATH_COMPLETENESS_UNVERIFIED",
                    t40=t40,
                    yes=yes,
                    payoff=explicit_payoff(t40=bool(t40), yes=yes) if t40 is not None else None,
                    hold=hold_payoff(yes),
                    entry_cents=entry,
                    entry_band=entry_band(entry, nominal=False),
                    period=(raw.get("period") or "").strip() or "UNSPECIFIED",
                    nominal_entry=False,
                    gross_pnl_cents=None,
                    **attached,
                )
            )
    audit["asked_six_rows"] = sum(sport_counts.values())
    audit["by_sport"] = sport_counts
    if audit["asked_six_rows"] != 1182:
        raise ChoosinTexasError("LOCK_MISMATCH", f"asked-six rows {audit['asked_six_rows']} != 1182")
    if sport_counts.get("NBA") != 604 or sport_counts.get("NCAAB") != 332 or sport_counts.get("WNBA") != 246:
        raise ChoosinTexasError("LOCK_MISMATCH", f"sport split {sport_counts} is not 604/332/246")
    ledger = json.loads((root / MLB_LEDGER).read_text())
    mlb_counts = {"rows": 0, "REGULAR_SEASON": 0}
    for raw in ledger:
        phase = str(raw.get("season_phase") or "")
        mlb_counts["rows"] += 1
        if phase == "REGULAR_SEASON":
            mlb_counts["REGULAR_SEASON"] += 1
        t40 = _bool(str(raw.get("stop_triggered")))
        yes = _bool(str(raw.get("expiration_result")))
        if yes is None and not t40:
            audit["missing_settlement"] += 1
        payoff = explicit_payoff(t40=bool(t40), yes=yes) if t40 is not None else None
        stored = raw.get("gross_pnl_cents")
        if payoff is not None and stored is not None and int(stored) != payoff:
            audit["mlb_gross_pnl_mismatch"] += 1
        attached = _attach("MLB", str(raw.get("event_ticker") or "").strip(), index)
        if attached["join_status"] != "JOINED":
            audit["schedule_unjoined"] += 1
        rows.append(
            Observation(
                sport="MLB",
                universe_id=PRIMARY["MLB"],
                event_ticker=str(raw.get("event_ticker") or "").strip(),
                slice_id="",
                game_date=str(raw.get("game_date") or ""),
                csv_phase=phase,
                evaluation_status="PATH_COMPLETENESS_UNVERIFIED",
                t40=t40,
                yes=yes,
                payoff=payoff,
                hold=hold_payoff(yes),
                entry_cents=80,
                entry_band=entry_band(80, nominal=True),
                period="UNSPECIFIED",
                nominal_entry=True,
                gross_pnl_cents=int(stored) if stored is not None else None,
                **attached,
            )
        )
    audit["mlb"] = mlb_counts
    return rows, audit
