"""HTTP handlers for Choosin Texas. Mounted on the ROLLER research API."""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.locks import (
    ENTRY_CAP_CENTS,
    GAIN_CENTS,
    K_DENOM,
    K_NUMER,
    MID_STOPS,
    PATH_STOPS,
    RULE,
    STOP_55_CENTS,
    STOP_CENTS,
)
from roller.choosin_texas.book import build_book
from roller.choosin_texas.dallas import build_dallas
from roller.choosin_texas.nba_path import build_nba_path
from roller.choosin_texas.verify import verify_locks


def handle_health() -> dict[str, Any]:
    return {
        "ok": True,
        "product": "Choosin Texas",
        "live_execution": False,
        "submits": False,
        "capability": "choosin_texas_universe",
        "capabilities": [
            "choosin_texas_universe",
            "choosin_texas_universe_60",
            "choosin_texas_paired_replay",
            "choosin_texas_execution_validation",
            "choosin_texas_universe_75",
            "choosin_texas_universe_77",
            "choosin_texas_nba_path_75",
            "choosin_texas_nba_path_77",
            "choosin_texas_nba_path",
            "choosin_texas_dallas",
            "choosin_texas_book",
            "choosin_texas_sugarland",
            "choosin_texas_katy",
            "choosin_texas_katy_catalog",
            "choosin_texas_asked_six",
            "choosin_texas_universe_81",
            "choosin_texas_universe_83",
            "choosin_texas_first78",
        ],
        "rule": RULE,
        "path_stops": list(PATH_STOPS),
        "mid_stops": list(MID_STOPS),
        "note": "Research desk. Candle path ≠ fill. N is FIRST80 trigger events. 80/60 is stop 60 on the same derived four. Texas (75) and Texas (77) are separate FIRST75 / FIRST77 books. Asked-six is a separate page. FIRST81 / FIRST83 are research books, not live 80/81/83.",
    }


def handle_universe() -> dict[str, Any]:
    verified = verify_locks()
    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "live_execution": False,
        "submits": False,
        "rule": RULE,
        "K": {"numer": K_NUMER, "denom": K_DENOM},
        "stop_cents": STOP_CENTS,
        "stop_55_cents": STOP_55_CENTS,
        "entry_cap_cents": ENTRY_CAP_CENTS,
        "gain_cents": GAIN_CENTS,
        "path_stops": list(PATH_STOPS),
        "mid_stops": list(MID_STOPS),
        "unit": "FIRST80 trigger events (one per settled event). Not Kalshi trade prints.",
        "partitions": verified["partitions"],
        "pool": verified["pool"],
        "complement": verified["complement"],
        "verification": {
            "status": verified["status"],
            "sources": verified["sources"],
        },
        "variables": {
            "rule": RULE,
            "K": K_NUMER,
            "stop_cents": STOP_CENTS,
            "stop_55_cents": STOP_55_CENTS,
            "entry_cap_cents": ENTRY_CAP_CENTS,
            "gain_cents": GAIN_CENTS,
            "path_stops": list(PATH_STOPS),
            "mid_stops": list(MID_STOPS),
            "slices": [row["partition_id"] for row in verified["partitions"]],
            "locked": True,
            "recompute": "FAIL_CLOSED",
            "note": "Changing a knob without a defined recompute stays fail-closed.",
        },
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ ACTUAL FILL",
            "N = FIRST80 trigger events, not Kalshi prints",
            "asked-six (1182) ≠ NBA+NCAAB four (936)",
            "terminal W/N ≠ 80/40 trade S",
            "80/25–80/50 use N=936; 80/55 S uses entry yes_bid < 86 only",
            "80/33–80/47 use N=936; separate tile from 25–55",
            "ledger EV is candle-path theoretical, not a fill or live EV",
        ],
    }


def handle_universe_60() -> dict[str, Any]:
    from roller.choosin_texas.texas60 import build_universe_60

    return build_universe_60()


def handle_paired_replay() -> dict[str, Any]:
    from roller.choosin_texas.paired_replay import build_paired_replay

    return build_paired_replay()


def handle_execution_validation() -> dict[str, Any]:
    from roller.choosin_texas.execution_validation.build import load_summary

    return load_summary()


def handle_universe_75() -> dict[str, Any]:
    from roller.choosin_texas.locks75 import (
        ENTRY_CAP_CENTS_75,
        ENTRY_CENTS_75,
        GAIN_CENTS_75,
        K_DENOM_75,
        K_NUMER_75,
        MID_STOPS_75,
        PATH_STOPS_75,
        RULE_75,
        STOP_55_CENTS_75,
        STOP_CENTS_75,
    )
    from roller.choosin_texas.texas75 import verify_locks_75

    verified = verify_locks_75()
    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "page": "texas_75",
        "live_execution": False,
        "submits": False,
        "rule": RULE_75,
        "K": {"numer": K_NUMER_75, "denom": K_DENOM_75},
        "entry_cents": ENTRY_CENTS_75,
        "stop_cents": STOP_CENTS_75,
        "stop_55_cents": STOP_55_CENTS_75,
        "entry_cap_cents": ENTRY_CAP_CENTS_75,
        "gain_cents": GAIN_CENTS_75,
        "path_stops": list(PATH_STOPS_75),
        "mid_stops": list(MID_STOPS_75),
        "unit": "FIRST75 trigger events (one per settled event). Not Kalshi trade prints.",
        "partitions": verified["partitions"],
        "pool": verified["pool"],
        "complement": verified["complement"],
        "verification": {
            "status": verified["status"],
            "sources": verified["sources"],
        },
        "variables": {
            "rule": RULE_75,
            "K": K_NUMER_75,
            "entry_cents": ENTRY_CENTS_75,
            "stop_cents": STOP_CENTS_75,
            "stop_55_cents": STOP_55_CENTS_75,
            "entry_cap_cents": ENTRY_CAP_CENTS_75,
            "gain_cents": GAIN_CENTS_75,
            "path_stops": list(PATH_STOPS_75),
            "mid_stops": list(MID_STOPS_75),
            "slices": [row["partition_id"] for row in verified["partitions"]],
            "locked": True,
            "recompute": "FAIL_CLOSED",
            "note": (
                "Same four clock slices as Texas FIRST80. Different τ. "
                "75/25–75/50 use N=913. 75/55 is the entry<81 book. "
                "75/33–75/47 use N=913 on a separate tile. "
                "Changing a knob without a defined recompute stays fail-closed."
            ),
        },
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ ACTUAL FILL",
            "N = FIRST75 trigger events, not Kalshi prints",
            "asked-six FIRST75 (1126) ≠ NBA+NCAAB four FIRST75 (913)",
            "FIRST75 913 ≠ FIRST80 936",
            "terminal W/N ≠ 75/40 trade S",
            "S = P(¬T40); s_L is not 0 (NBA 2Q has L∩¬T40 = 1)",
            "75/40 EV = 25S − 35(1−S). Not the Lebronner assumed-fill-80 +20 object",
            "75/25–75/50 use N=913; 75/55 S uses entry yes_bid < 81 only",
            "75/33–75/47 use N=913; separate tile from 25–55",
            "ledger EV is candle-path theoretical, not a fill or live EV",
        ],
    }


def handle_universe_77() -> dict[str, Any]:
    from roller.choosin_texas.locks77 import (
        ENTRY_CAP_CENTS_77,
        ENTRY_CENTS_77,
        GAIN_CENTS_77,
        K_DENOM_77,
        K_NUMER_77,
        MID_STOPS_77,
        PATH_STOPS_77,
        RULE_77,
        STOP_55_CENTS_77,
        STOP_CENTS_77,
    )
    from roller.choosin_texas.texas77 import verify_locks_77

    verified = verify_locks_77()
    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "page": "texas_77",
        "live_execution": False,
        "submits": False,
        "rule": RULE_77,
        "K": {"numer": K_NUMER_77, "denom": K_DENOM_77},
        "entry_cents": ENTRY_CENTS_77,
        "stop_cents": STOP_CENTS_77,
        "stop_55_cents": STOP_55_CENTS_77,
        "entry_cap_cents": ENTRY_CAP_CENTS_77,
        "gain_cents": GAIN_CENTS_77,
        "path_stops": list(PATH_STOPS_77),
        "mid_stops": list(MID_STOPS_77),
        "unit": "FIRST77 trigger events (one per settled event). Not Kalshi trade prints.",
        "partitions": verified["partitions"],
        "pool": verified["pool"],
        "complement": verified["complement"],
        "verification": {
            "status": verified["status"],
            "sources": verified["sources"],
        },
        "variables": {
            "rule": RULE_77,
            "K": K_NUMER_77,
            "entry_cents": ENTRY_CENTS_77,
            "stop_cents": STOP_CENTS_77,
            "stop_55_cents": STOP_55_CENTS_77,
            "entry_cap_cents": ENTRY_CAP_CENTS_77,
            "gain_cents": GAIN_CENTS_77,
            "path_stops": list(PATH_STOPS_77),
            "mid_stops": list(MID_STOPS_77),
            "slices": [row["partition_id"] for row in verified["partitions"]],
            "locked": True,
            "recompute": "FAIL_CLOSED",
            "note": (
                "Same four clock slices as Texas FIRST80. Different τ. "
                "77/25–77/50 use N=933. 77/55 is the entry<83 book. "
                "77/33–77/47 use N=933 on a separate tile. "
                "TABLES.md has no FIRST77. Changing a knob without a defined "
                "recompute stays fail-closed."
            ),
        },
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ ACTUAL FILL",
            "N = FIRST77 trigger events, not Kalshi prints",
            "asked-six FIRST77 (1158) ≠ NBA+NCAAB four FIRST77 (933)",
            "FIRST77 933 ≠ FIRST75 913 ≠ FIRST80 936",
            "terminal W/N ≠ 77/40 trade S",
            "S = P(¬T40); s_L is not 0 (NBA 2Q has L∩¬T40 = 1)",
            "77/40 EV = 23S − 37(1−S). Not the Lebronner assumed-fill-80 +20 object",
            "77/25–77/50 use N=933; 77/55 S uses entry yes_bid < 83 only",
            "77/33–77/47 use N=933; separate tile from 25–55",
            "ledger EV is candle-path theoretical, not a fill or live EV",
        ],
    }


def handle_asked_six() -> dict[str, Any]:
    from roller.choosin_texas.asked_six import handle_asked_six as _handle

    return _handle()


def handle_universe_81() -> dict[str, Any]:
    from roller.choosin_texas.tau_companion import handle_universe_tau

    return handle_universe_tau(81)


def handle_universe_83() -> dict[str, Any]:
    from roller.choosin_texas.tau_companion import handle_universe_tau

    return handle_universe_tau(83)


def handle_nba_path() -> dict[str, Any]:
    verify_locks()
    return build_nba_path()


def handle_nba_path_75() -> dict[str, Any]:
    from roller.choosin_texas.nba_path75 import build_nba_path_75
    from roller.choosin_texas.texas75 import verify_locks_75

    verify_locks_75()
    return build_nba_path_75()


def handle_nba_path_77() -> dict[str, Any]:
    from roller.choosin_texas.nba_path77 import build_nba_path_77
    from roller.choosin_texas.texas77 import verify_locks_77

    verify_locks_77()
    return build_nba_path_77()


def handle_lubbock() -> dict[str, Any]:
    from roller.choosin_texas.lubbock.serve import handle_lubbock as _handle

    verify_locks()
    return _handle()


def handle_lubbock_export(sport: str, season: str, phase: str, grain: str) -> tuple[str, str]:
    from roller.choosin_texas.lubbock.serve import handle_export_csv

    verify_locks()
    return handle_export_csv(sport, season, phase, grain)


def handle_dallas() -> dict[str, Any]:
    verify_locks()
    return build_dallas()


def handle_book() -> dict[str, Any]:
    verify_locks()
    return build_book()


def handle_sugarland() -> dict[str, Any]:
    """Serve the precomputed Sugarland artifact. Does not verify FIRST80 locks."""
    import json
    from pathlib import Path

    from roller.choosin_texas.models import ChoosinTexasError

    path = Path(__file__).resolve().parents[3] / "research" / "sugarland" / "v1" / "page.json"
    if not path.is_file():
        raise ChoosinTexasError(
            "ARTIFACT_UNAVAILABLE",
            "Sugarland page.json is absent. Run roller.choosin_texas.sugarland.build.",
        )
    payload = json.loads(path.read_text())
    payload["live_execution"] = False
    payload["submits"] = False
    payload["research_only"] = True
    payload["execution_disabled"] = True
    return payload


def handle_katy() -> dict[str, Any]:
    from roller.austin.errors import AustinError
    from roller.choosin_texas.katy import handle_katy as _handle
    from roller.choosin_texas.models import ChoosinTexasError

    verify_locks()
    try:
        return _handle()
    except AustinError as exc:
        raise ChoosinTexasError(exc.code, exc.message) from exc


def handle_katy_experiment(experiment_id: str) -> dict[str, Any]:
    from roller.austin.errors import AustinError
    from roller.choosin_texas.katy import handle_katy_experiment as _handle
    from roller.choosin_texas.models import ChoosinTexasError

    verify_locks()
    try:
        return _handle(experiment_id)
    except AustinError as exc:
        raise ChoosinTexasError(exc.code, exc.message) from exc
