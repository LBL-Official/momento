"""Persist the Lubbock v1 artifacts. The API serves these files and does not rescan."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from roller.choosin_texas.lubbock.analyze import build_series, explicit_matches_cells
from roller.choosin_texas.lubbock.observations import HOLM_SEASON, load_observations
from roller.choosin_texas.lubbock.schedule import rank_all, repo_root
from roller.choosin_texas.lubbock.stats import INTERPRETATION, classify_holm, holm
from roller.choosin_texas.models import ChoosinTexasError
from roller.nba_8040_reverse_features.instances import load_instances

ARTIFACTS = "research/choosin_texas/lubbock/v1"
BOOK = "research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json"
SPEC = "research/choosin_texas/lubbock/LUBBOCK_SPEC_V1.md"
SPORT_ORDER = ("NBA", "NCAAB", "WNBA", "MLB")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_sha256() -> str:
    digest = hashlib.sha256()
    package = Path(__file__).resolve().parent
    for path in sorted(package.glob("*.py")):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _git_head(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "UNAVAILABLE"


def _partition_ok(games) -> None:
    grouped: dict[tuple[str, str, str], list] = defaultdict(list)
    for game in games:
        grouped[(game.sport, game.season_id, game.phase)].append(game)
    for key, rows in grouped.items():
        ranks = sorted(game.game_rank for game in rows)
        total = rows[0].g
        if ranks != list(range(1, total + 1)) or len(rows) != total:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{key} ranks are not 1..G")
        for attr, buckets in (("decile", 10), ("quintile", 5)):
            counts = [sum(1 for game in rows if getattr(game, attr) == index) for index in range(buckets)]
            populated = [count for count in counts if count]
            if populated and max(populated) - min(populated) > 1:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{key} {attr} sizes differ by more than one")
            if sum(counts) != total:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{key} {attr} does not cover G")


def _identity(observations) -> dict[str, object]:
    instances = load_instances()
    instance_ids = {row["event_id"] for row in instances}
    nba_ids = {row.event_ticker for row in observations if row.sport == "NBA"}
    if nba_ids != instance_ids or len(nba_ids) != 604:
        raise ChoosinTexasError("LOCK_MISMATCH", "NBA 604 does not match the Austin/Dallas instance set")
    ncaab = [row for row in observations if row.sport == "NCAAB"]
    h1 = sum(1 for row in ncaab if row.slice_id == "H1_2")
    h2 = sum(1 for row in ncaab if row.slice_id == "H2_1")
    if h1 != 193 or h2 != 139 or len(ncaab) != 332:
        raise ChoosinTexasError("LOCK_MISMATCH", f"NCAAB slices {h1}/{h2} are not 193/139")
    regular_instances = {row["event_id"] for row in instances if row["season_phase"] == "REGULAR_SEASON"}
    regular_nba = {row.event_ticker for row in observations if row.sport == "NBA" and row.csv_phase == "REGULAR_SEASON"}
    if regular_instances != regular_nba:
        raise ChoosinTexasError("LOCK_MISMATCH", "NBA regular-season identity drifted")
    return {
        "asked_six": 1182,
        "derived_four": 936,
        "nba_604": 604,
        "ncaab_332": 332,
        "ncaab_h1_2": h1,
        "ncaab_h2_1": h2,
        "wnba_246": sum(1 for row in observations if row.sport == "WNBA"),
        "nba_matches_derived_four_nba": True,
        "nba_matches_asked_six_nba": True,
        "ncaab_matches_asked_six": True,
        "note": "NBA 604 and the NBA rows inside derived-four 936 are the same membership. One Holm test.",
    }


def _apply_holm(series: list[dict], holm_rows: list[dict[str, str]]) -> None:
    parsed: dict[str, tuple[int, int, str]] = {}
    for row in holm_rows:
        numer, denom = row["holm_p"].split("/")
        parsed[row["label"]] = (int(numer), int(denom), row["holm_p"])
    for series_row in series:
        contrast = series_row["contrasts"]["primary_ev"]
        if not series_row.get("holm_primary"):
            continue
        if "estimate_micro" not in contrast or "lo_micro" not in contrast:
            contrast["classification"] = "INSUFFICIENT_DATA"
            continue
        numer, denom, text = parsed[series_row["sport"]]
        contrast["holm_p"] = text
        contrast["classification"] = classify_holm(
            estimate=int(contrast["estimate_micro"]),
            lo=int(contrast["lo_micro"]),
            hi=int(contrast["hi_micro"]),
            holm_numer=numer,
            holm_denom=denom,
        )


def _conclusions(series: list[dict], holm_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    holm_by_sport = {row["label"]: row["holm_p"] for row in holm_rows}
    out = []
    for sport in SPORT_ORDER:
        for row in series:
            if row["sport"] != sport or row["phase"] != "REGULAR_SEASON":
                continue
            contrast = row["contrasts"]["primary_ev"]
            holm_p = holm_by_sport.get(sport, "not in the Holm family")
            if not row["holm_primary"]:
                holm_p = "not in the Holm family"
                legacy = "exploratory"
            else:
                legacy = str(contrast.get("classification") or "UNAVAILABLE")
            text = (
                f"{sport} {row['season_id']} regular season, universe {row['universe_id']}: "
                f"official-season final 10% and final 20% contrasts are UNAVAILABLE. "
                f"Warehouse-covered progress does not establish the league final decile. "
                f"Warehouse-relative last 10% minus preceding 90%, legacy path flags: "
                f"estimate {contrast.get('estimate')} cents per contract, "
                f"interval {contrast.get('lo')} to {contrast.get('hi')}. "
                f"Distinct active dates late {contrast.get('n_dates_late', 'UNAVAILABLE')}, "
                f"earlier {contrast.get('n_dates_early', 'UNAVAILABLE')}. "
                f"Holm-adjusted p: {holm_p}. "
                f"Warehouse-relative legacy classification: {legacy.replace('_', ' ')}. "
                f"Path status is PATH_COMPLETENESS_UNVERIFIED. "
                f"Net EV is UNAVAILABLE. Candle path is not a fill. This is not an execution filter."
            )
            out.append(
                {
                    "sport": sport,
                    "season_id": str(row["season_id"]),
                    "universe_id": str(row["universe_id"]),
                    "holm_primary": str(bool(row["holm_primary"])),
                    "classification": "UNAVAILABLE",
                    "warehouse_relative_legacy_classification": legacy,
                    "estimate": str(contrast.get("estimate")),
                    "lo": str(contrast.get("lo")),
                    "hi": str(contrast.get("hi")),
                    "holm_p": holm_p,
                    "distinct_active_dates_late": str(contrast.get("n_dates_late", "UNAVAILABLE")),
                    "distinct_active_dates_early": str(contrast.get("n_dates_early", "UNAVAILABLE")),
                    "statement": text,
                }
            )
    return out


def run() -> dict:
    root = repo_root()
    book = root / BOOK
    book_hash = _sha256(book)
    games, schedule_notes = rank_all()
    _partition_ok(games)
    observations, audit = load_observations(games)
    if not explicit_matches_cells(observations):
        raise ChoosinTexasError("LOCK_MISMATCH", "explicit EV disagrees with row payoffs")
    series = build_series(games, observations)
    primaries = [row for row in series if row["holm_primary"] and row["phase"] == "REGULAR_SEASON"]
    if [row["sport"] for row in sorted(primaries, key=lambda item: SPORT_ORDER.index(item["sport"]))] != list(SPORT_ORDER):
        raise ChoosinTexasError("LOCK_MISMATCH", "Holm family is not the four primary seasons")
    p_values = []
    for sport in SPORT_ORDER:
        row = next(item for item in primaries if item["sport"] == sport)
        contrast = row["contrasts"]["primary_ev"]
        if "p_numer" not in contrast:
            raise ChoosinTexasError("DATA_REQUIRED", f"{sport} primary contrast has no p-value")
        p_values.append((sport, int(contrast["p_numer"]), int(contrast["p_denom"])))
        if row["season_id"] != HOLM_SEASON[sport]:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{sport} Holm season drifted")
    holm_rows = holm(p_values)
    _apply_holm(series, holm_rows)
    identity = _identity(observations)
    conclusions = _conclusions(series, holm_rows)
    if _sha256(book) != book_hash:
        raise ChoosinTexasError("LOCK_MISMATCH", "book.json changed during the run")
    summary = {
        "spec_id": "LUBBOCK_SPEC_V1",
        "live_execution": False,
        "submits": False,
        "net_ev": "UNAVAILABLE",
        "schedule_completeness": "WAREHOUSE_COVERED_PROGRESS",
        "independent_schedule": "NONE",
        "candle_basis": "CANDLE_PATH_NOT_A_FILL",
        "path_status": "PATH_COMPLETENESS_UNVERIFIED",
        "interpretation": INTERPRETATION,
        "holm_season": HOLM_SEASON,
        "holm": holm_rows,
        "identity": identity,
        "conclusions": conclusions,
        "schedule_notes": schedule_notes,
        "audit": audit,
        "series": series,
    }
    out = root / ARTIFACTS
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary))
    _write_games(out / "assignments.csv", games)
    _write_observations(out / "observations.csv", observations)
    (out / "exclusions.json").write_text(
        json.dumps(
            {
                "schedule_unjoined": audit["schedule_unjoined"],
                "missing_settlement": audit["missing_settlement"],
                "t40_post_min_mismatch": audit["t40_post_min_mismatch"],
                "mlb_gross_pnl_mismatch": audit["mlb_gross_pnl_mismatch"],
                "schedule_notes": schedule_notes,
                "coverage_limits_not_in_denominator": {"NBA": 1230, "NCAAB_P5": 721, "WNBA": 589},
            }
        )
    )
    manifest = {
        "spec": SPEC,
        "spec_sha256": _sha256(root / SPEC),
        "book_json_sha256": book_hash,
        "confirmation_cohorts_opened": False,
        "command": "python -m roller.choosin_texas.lubbock.run",
        "code_version": _git_head(root),
        "code_sha256": _code_sha256(),
        "source_sha256": {
            "asked_six_csv": _sha256(root / "research/first80_asked_six_chatgpt_export/first80_asked_six.csv"),
            "mlb_ledger": _sha256(root / "research/mlb_first80_80_40_v1/ledger_baseline.json"),
            "conferences": _sha256(root / "ROLLER/config/conferences.json"),
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    if _sha256(book) != book_hash:
        raise ChoosinTexasError("LOCK_MISMATCH", "book.json changed while artifacts were written")
    return summary


def _write_games(path: Path, games) -> None:
    fields = [
        "sport",
        "season_id",
        "source_season",
        "phase",
        "raw_phase",
        "event_ticker",
        "internal_game_id",
        "game_date",
        "league_local_date",
        "start_basis",
        "event_status",
        "game_rank",
        "g",
        "season_progress",
        "decile",
        "quintile",
        "p5_vs_p5",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for game in games:
            writer.writerow({field: getattr(game, field) for field in fields})


def _write_observations(path: Path, observations) -> None:
    fields = [
        "sport",
        "universe_id",
        "event_ticker",
        "slice_id",
        "season_id",
        "phase",
        "join_status",
        "evaluation_status",
        "league_local_date",
        "game_rank",
        "decile",
        "quintile",
        "t40",
        "yes",
        "payoff",
        "hold",
        "entry_cents",
        "entry_band",
        "period",
        "nominal_entry",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in observations:
            payload = {field: getattr(row, field) for field in fields}
            writer.writerow(payload)


def main() -> None:
    summary = run()
    print(f"series {len(summary['series'])} holm {summary['holm']}")


if __name__ == "__main__":
    main()
