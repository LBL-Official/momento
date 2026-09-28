"""Read-only frozen XIB/MCD artifact loader.

Answers: what frozen intelligence observations are available for this universe?
Does not answer: what does the model think about this market?
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from terminal_efficiency.consumption.errors import (
    ConsumptionForbidden,
    FrozenUnavailable,
    ProvenanceRequired,
)
from terminal_efficiency.consumption.models import (
    REQUIRED_VIEW_FIELDS,
    FrozenIdentity,
    FrozenObservation,
    unavailable_observation,
)
from terminal_efficiency.consumption.store import data_root, derived_root, sha256_file
from terminal_efficiency.consumption.validation import (
    KNOWN_FORBIDDEN_METHODS,
    assert_no_training_api,
    match_identity,
    reject_kalshi_join,
    reject_probabilities_only,
    require_view_columns,
)
from terminal_efficiency.frozen_artifacts.registry import resolve_published

_FORBIDDEN_ATTR = frozenset(
    {
        *KNOWN_FORBIDDEN_METHODS,
        "evaluate",
        "score",
        "predict",
        "refit",
        "write",
        "write_artifact",
        "save",
        "dump",
        "persist",
        "update_model",
        "calibrate_model",
        "select_model",
        "evaluate_oos",
        "join_kalshi",
        "residuals",
        "to_probability_map",
        "probabilities_only",
    }
)

_BANNED_KW = frozenset(
    {
        "evaluate",
        "evaluate_oos",
        "kalshi",
        "residual",
        "join_candles",
        "refit",
        "fit",
        "train",
        "calibrate",
        "select_model",
    }
)

_QUALITY_KEEP = (
    "availability_status",
    "coverage_status",
    "data_quality_flags",
    "feature_availability_status",
    "model_version",
    "prediction_timestamp",
    "feature_as_of_timestamp",
    "prediction_available",
)


class AuditedReadOnlyView:
    """Provenance-preserving view. No game_id → probability projection."""

    def __init__(self, frame: pd.DataFrame, identity: FrozenIdentity, coverage: dict[str, Any]):
        require_view_columns(list(frame.columns))
        self._frame = frame
        self.identity = identity
        self.coverage = coverage

    def to_frame(self) -> pd.DataFrame:
        return self._frame.copy()

    def records(self) -> list[FrozenObservation]:
        out = []
        for row in self._frame.to_dict("records"):
            out.append(FrozenObservation(**{k: row[k] for k in REQUIRED_VIEW_FIELDS}))
        return out

    def probabilities_only(self) -> None:
        raise ProvenanceRequired(
            "probabilities-only projection is forbidden; it strips coverage and provenance"
        )

    def to_probability_map(self) -> None:
        raise ProvenanceRequired("naked game_id → probability maps are forbidden")


class FrozenObjectLoader:
    """Locate, inspect, and read frozen artifacts. Incapable of refitting."""

    def __init__(
        self,
        data_root_path: Path | None = None,
        *,
        registry_records: list[dict[str, Any]] | None = None,
    ):
        self._root = data_root(data_root_path)
        self._registry_override = registry_records
        assert_no_training_api(self)

    def _published(self, identity: FrozenIdentity) -> tuple[FrozenIdentity, dict[str, Any]]:
        if self._registry_override is None:
            return resolve_published(identity=identity)
        matches = [
            row
            for row in self._registry_override
            if FrozenIdentity(
                league=str(row["league"]),
                season=str(row["season"]),
                dataset_version=str(row["dataset_version"]),
                feature_set_version=str(row["feature_set_version"]),
                model_version=str(row["model_version"]),
                code_version=str(row["code_version"]),
                artifact_manifest_hash=str(row["artifact_manifest_hash"]),
            ).key()
            == identity.key()
            and (
                not identity.artifact_manifest_hash
                or identity.artifact_manifest_hash == row["artifact_manifest_hash"]
            )
        ]
        if not matches:
            raise FrozenUnavailable("UNAVAILABLE: requested freeze identity is not published")
        row = matches[0]
        published = FrozenIdentity(
            league=str(row["league"]),
            season=str(row["season"]),
            dataset_version=str(row["dataset_version"]),
            feature_set_version=str(row["feature_set_version"]),
            model_version=str(row["model_version"]),
            code_version=str(row["code_version"]),
            artifact_manifest_hash=str(row["artifact_manifest_hash"]),
        )
        match_identity(identity, published)
        return published, row

    def __getattr__(self, name: str) -> None:
        if name in _FORBIDDEN_ATTR or name.startswith(("fit", "train", "calibrate", "evaluate", "write")):
            raise ConsumptionForbidden(
                f"{name} is not available on the read-only loader (no refit / no OOS / no market join)"
            )
        raise AttributeError(name)

    def _reject_kwargs(self, kwargs: dict[str, Any]) -> None:
        reject_kalshi_join(kwargs)
        banned = {k for k in kwargs if k.lower() in _BANNED_KW}
        if banned:
            raise ConsumptionForbidden(f"forbidden loader argument: {sorted(banned)}")

    def resolve(self, identity: FrozenIdentity, **kwargs: Any) -> tuple[FrozenIdentity, dict]:
        self._reject_kwargs(kwargs)
        published, record = self._published(identity)
        match_identity(identity, published)
        dest = derived_root(self._root, published.league, published.season)
        pred = dest / record["prediction_file"]
        model = dest / record["frozen_model_file"]
        if not pred.is_file():
            raise FrozenUnavailable(f"UNAVAILABLE: prediction file missing ({pred})")
        if not model.is_file():
            raise FrozenUnavailable(f"UNAVAILABLE: frozen model file missing ({model})")
        pred_hash = sha256_file(pred)
        model_hash = sha256_file(model)
        if pred_hash != record["prediction_sha256"]:
            raise FrozenUnavailable("UNAVAILABLE: prediction artifact hash mismatch (mutated or substituted)")
        if model_hash != record["frozen_model_sha256"]:
            raise FrozenUnavailable("UNAVAILABLE: model artifact hash mismatch (mutated or substituted)")
        warehouse_manifest = dest / "frozen_artifacts" / "manifests" / _manifest_name(record)
        if warehouse_manifest.is_file():
            disk = json.loads(warehouse_manifest.read_text())
            if disk.get("artifact_manifest_hash") != record["artifact_manifest_hash"]:
                raise FrozenUnavailable("UNAVAILABLE: warehouse manifest does not match published freeze")
        return published, {**record, "derived_root": str(dest), "prediction_path": str(pred)}

    def inspect(self, identity: FrozenIdentity, **kwargs: Any) -> dict[str, Any]:
        self._reject_kwargs(kwargs)
        published, record = self.resolve(identity)
        dest = Path(record["derived_root"])
        games_path = dest / "games.parquet"
        universe = {
            "games_table_present": games_path.is_file(),
            "ncaab_in_game_rule": "P5-vs-P5 verified PBP only"
            if published.league.upper() == "NCAAB"
            else "NBA Dataset B (supported coverage)",
        }
        return {
            "read_only": True,
            "refit_forbidden": True,
            "answers": "what frozen intelligence observations are available for this requested universe",
            "does_not_answer": "what the model thinks about this market",
            "phase7": "NOT AUTHORIZED",
            "market_evaluation": "NOT AUTHORIZED",
            "roller_consumption": "NOT AUTHORIZED",
            "live_trading": "NOT AUTHORIZED",
            "identity": published.as_dict(),
            "coverage": record["coverage"],
            "raw_probability_status": record["raw_probability_status"],
            "calibrated_probability_status": record["calibrated_probability_status"],
            "prediction_file": record["prediction_file"],
            "prediction_sha256": record["prediction_sha256"],
            "frozen_model_file": record["frozen_model_file"],
            "frozen_model_sha256": record["frozen_model_sha256"],
            "frozen_model_loaded": False,
            "joblib_unpickled": False,
            "universe": universe,
            "dataset_c_opened": False,
            "dataset_a_opened": False,
        }

    def lookup_game(self, identity: FrozenIdentity, game_id: str, **kwargs: Any) -> AuditedReadOnlyView:
        self._reject_kwargs(kwargs)
        return self.load_observations(identity, game_ids=[str(game_id)])

    def load_observations(
        self,
        identity: FrozenIdentity,
        *,
        game_ids: list[str] | None = None,
        columns: list[str] | None = None,
        **kwargs: Any,
    ) -> AuditedReadOnlyView:
        self._reject_kwargs(kwargs)
        reject_probabilities_only(columns)
        published, record = self.resolve(identity)
        dest = Path(record["derived_root"])
        pred_path = dest / record["prediction_file"]
        games_path = dest / "games.parquet"

        requested = [str(g) for g in (game_ids or [])]
        pred = pd.read_parquet(pred_path)
        pred["game_id"] = pred["game_id"].astype(str)

        p5_false: set[str] = set()
        known_games: set[str] = set()
        if games_path.is_file() and published.league.upper() == "NCAAB":
            games = pd.read_parquet(games_path, columns=["game_id", "p5_vs_p5"])
            games["game_id"] = games["game_id"].astype(str)
            known_games = set(games["game_id"])
            p5_false = set(games.loc[~games["p5_vs_p5"].astype(bool), "game_id"])

        rows: list[dict[str, Any]] = []
        if requested:
            for gid in requested:
                if published.league.upper() == "NCAAB" and gid in p5_false:
                    rows.append(
                        unavailable_observation(
                            game_id=gid,
                            identity=published,
                            reason="NCAAB_INGAME_XIB_REQUIRES_P5_VS_P5_VERIFIED_PBP",
                        ).as_dict()
                    )
                    continue
                hit = pred[pred["game_id"] == gid]
                if hit.empty:
                    reason = (
                        "NCAAB_INGAME_XIB_REQUIRES_P5_VS_P5_VERIFIED_PBP"
                        if published.league.upper() == "NCAAB"
                        else "OUTSIDE_FROZEN_SUPPORTED_COVERAGE"
                    )
                    if published.league.upper() == "NCAAB" and gid in known_games and gid not in p5_false:
                        reason = "NCAAB_INGAME_XIB_PBP_UNAVAILABLE"
                    rows.append(unavailable_observation(game_id=gid, identity=published, reason=reason).as_dict())
                    continue
                rows.extend(_project_rows(hit, published, record))
        else:
            rows.extend(_project_rows(pred, published, record))

        frame = pd.DataFrame(rows)
        if columns:
            keep = list(dict.fromkeys([*columns, *_QUALITY_KEEP, *REQUIRED_VIEW_FIELDS]))
            missing = [c for c in columns if c not in frame.columns and c not in REQUIRED_VIEW_FIELDS]
            if missing:
                raise FrozenUnavailable(f"requested columns unavailable: {missing}")
            frame = frame[[c for c in keep if c in frame.columns]]
            require_view_columns(list(frame.columns))
        return AuditedReadOnlyView(frame, published, record["coverage"])


def _manifest_name(record: dict) -> str:
    return f"{record['league']}_{record['season']}_{record['model_version']}.json"


def _project_rows(hit: pd.DataFrame, identity: FrozenIdentity, record: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    league = identity.league.upper()
    coverage = (
        "P5_VS_P5_VERIFIED_PBP" if league == "NCAAB" else "FROZEN_SUPPORTED_COVERAGE"
    )
    for rec in hit.to_dict("records"):
        raw_p = rec.get("xib_raw_probability")
        cal_p = rec.get("xib_home_win_probability")
        if cal_p is None or (isinstance(cal_p, float) and pd.isna(cal_p)):
            available = False
            status = "CORRUPT"
            cal_out: float | None = None
        else:
            available = True
            status = "AVAILABLE"
            cal_out = float(cal_p)
        raw_out = None
        raw_status = record.get("raw_probability_status", "UNAVAILABLE")
        if raw_p is not None and not (isinstance(raw_p, float) and pd.isna(raw_p)):
            raw_out = float(raw_p)
            raw_status = "AVAILABLE"
        flags = str(rec.get("data_quality_flags") or "")
        extra = f"raw_probability={raw_status};calibrated_probability={record.get('calibrated_probability_status', 'AVAILABLE')}"
        flags = f"{flags};{extra}" if flags else extra
        feat_status = str(rec.get("timestamp_quality") or rec.get("data_quality_flags") or "UNAVAILABLE")
        out.append(
            {
                "observation_id": str(rec.get("observation_id") or ""),
                "game_id": str(rec.get("game_id") or ""),
                "league": identity.league,
                "season": identity.season,
                "prediction_timestamp": str(rec.get("prediction_timestamp") or ""),
                "feature_as_of_timestamp": str(rec.get("feature_as_of_timestamp") or ""),
                "raw_probability": raw_out,
                "calibrated_probability": cal_out,
                "model_version": identity.model_version,
                "dataset_version": identity.dataset_version,
                "feature_set_version": identity.feature_set_version,
                "code_version": identity.code_version,
                "artifact_manifest_hash": identity.artifact_manifest_hash or record["artifact_manifest_hash"],
                "prediction_available": available,
                "availability_status": status,
                "coverage_status": coverage,
                "feature_availability_status": feat_status,
                "data_quality_flags": flags,
            }
        )
    return out
