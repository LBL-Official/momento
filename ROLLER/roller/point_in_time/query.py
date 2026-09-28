"""Public research API. No dataset read bypasses the as_of filter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from roller.admin import load_dataset, load_identity, load_table
from roller.canonical.align import latest_candle, latest_pbp
from roller.config import RollerConfig
from roller.features.engine import summarize_priors, team_appearances
from roller.point_in_time.filters import (
    AsOfRequiredError,
    FutureInformationError,
    dataset_contains_future_information,
    dataset_is_fundamental,
    dataset_is_v4b,
    dataset_is_v4c,
    public_filter,
)
from roller.timeutil import UTC, parse_utc, resolve_cutoff


class ResearchNotImplementedError(NotImplementedError):
    """Train/OOS stub. V4A exposes db.fundamental(); V4B exposes db.greeks(); research() cannot merge labels into I(t)."""


@dataclass
class InformationSet:
    """I(t) = {x | available_at(x) < t}."""

    cutoff: datetime
    roller: "Roller"

    def dataset(self, sport: str, season: str, dataset: str) -> pd.DataFrame:
        return self.roller.dataset(sport, season, dataset, as_of=self.cutoff)

    def get_team_state(self, team: str, sport: str | None = None, season: str | None = None) -> dict[str, Any]:
        return self.roller.get_team_state(team=team, as_of=self.cutoff, sport=sport, season=season)

    def game_state(self, internal_game_id: str) -> dict[str, Any]:
        return self.roller.game_state(internal_game_id=internal_game_id, as_of=self.cutoff)

    def observation(self, internal_game_id: str) -> dict[str, Any]:
        return self.roller.observation(internal_game_id, as_of=self.cutoff)

    def labels(self, observation_id: str | None = None, internal_game_id: str | None = None) -> dict[str, Any]:
        return self.roller.labels(
            observation_id=observation_id,
            internal_game_id=internal_game_id,
            as_of=None if observation_id else self.cutoff,
        )

    def clock_snap(self, internal_game_id: str, timestamp) -> dict[str, Any]:
        return self.roller.clock_snap(internal_game_id, timestamp, as_of=self.cutoff)

    def first80(self, internal_game_id: str | None = None, sport: str | None = None, season: str | None = None) -> dict[str, Any]:
        return self.roller.first80(
            internal_game_id=internal_game_id,
            sport=sport,
            season=season,
            as_of=self.cutoff,
        )

    def research(self, *args: Any, **kwargs: Any) -> None:
        return self.roller.research(*args, **kwargs)

    def response(self, observation_id: str, measurement: str, horizon: str) -> dict[str, Any]:
        return self.roller.response(observation_id=observation_id, measurement=measurement, horizon=horizon)

    def baseline(self, observation_id: str, measurement: str, horizon: str, corpus=None) -> dict[str, Any]:
        return self.roller.baseline(
            observation_id=observation_id, measurement=measurement, horizon=horizon, corpus=corpus
        )

    def residual(self, observation_id: str, measurement: str, horizon: str, corpus=None) -> dict[str, Any]:
        return self.roller.residual(
            observation_id=observation_id, measurement=measurement, horizon=horizon, corpus=corpus
        )

    def greeks(
        self,
        observation_id: str,
        names=None,
        corpus=None,
        schema_version: str | None = None,
    ) -> dict[str, Any]:
        return self.roller.greeks(
            observation_id=observation_id,
            names=names,
            corpus=corpus,
            schema_version=schema_version,
        )

    def fundamental(
        self,
        observation_id: str,
        name: str = "fundamental_win_probability_empirical_v1",
        conditioning_schema_version: str | None = None,
        corpus=None,
    ) -> dict[str, Any]:
        return self.roller.fundamental(
            observation_id=observation_id,
            name=name,
            conditioning_schema_version=conditioning_schema_version,
            corpus=corpus,
        )


class Roller:
    def __init__(self, root=None) -> None:
        self.cfg = RollerConfig(root)

    def as_of(self, as_of, end_of_day: bool = False) -> InformationSet:
        return InformationSet(cutoff=resolve_cutoff(as_of, end_of_day=end_of_day), roller=self)

    def dataset(
        self,
        sport: str,
        season: str,
        dataset: str,
        as_of=None,
        end_of_day: bool = False,
        full_history: bool = False,
    ) -> pd.DataFrame:
        if dataset_contains_future_information(dataset, self.cfg.schemas):
            if dataset_is_v4b(dataset) or dataset_is_v4c(dataset):
                hint = "use db.greeks()"
            elif dataset_is_fundamental(dataset):
                hint = "use db.fundamental()"
            else:
                hint = "use db.labels()"
            raise FutureInformationError(
                f"dataset {dataset!r} contains future information; {hint}"
            )
        raw = load_dataset(self.cfg, sport, season, dataset)
        mask = dataset in {"games", "kalshi_markets"}
        return public_filter(
            raw, as_of=as_of, end_of_day=end_of_day, full_history=full_history, mask_results=mask
        )

    def get_team_state(
        self,
        team: str,
        as_of=None,
        end_of_day: bool = False,
        full_history: bool = False,
        sport: str | None = None,
        season: str | None = None,
    ) -> dict[str, Any]:
        if as_of is None and not full_history:
            raise AsOfRequiredError("get_team_state requires as_of or full_history=True")
        cutoff = resolve_cutoff(as_of or "9999-12-31", end_of_day=end_of_day) if as_of or full_history else None
        sport = sport or "NBA"
        season = season or self.cfg.season_labels(sport)[0]
        games = load_dataset(self.cfg, sport, season, "games")
        windows = list(self.cfg.features.get("team_features", {}).get("rolling_windows") or [5, 10])
        priors = []
        for g in games.to_dict("records"):
            for app in team_appearances(g):
                if app["team_id"] != team or not app["has_result"]:
                    continue
                ts = parse_utc(app["result_available_at"])
                if full_history or (ts is not None and cutoff is not None and ts < cutoff):
                    priors.append(app)
        priors.sort(key=lambda p: parse_utc(p["result_available_at"]) or datetime.min.replace(tzinfo=UTC))
        stats, _ = summarize_priors(priors, team, windows)
        return {
            "team": team,
            "sport": sport,
            "season": season,
            "as_of": cutoff.isoformat().replace("+00:00", "Z") if cutoff else None,
            "games": stats["games_played_pre"],
            "wins": stats["wins_pre"],
            "losses": stats["losses_pre"],
            "win_pct_pre": stats["win_pct_pre"],
            **stats,
        }

    def game_state(
        self,
        internal_game_id: str,
        as_of=None,
        end_of_day: bool = False,
        full_history: bool = False,
    ) -> dict[str, Any]:
        if as_of is None and not full_history:
            raise AsOfRequiredError("game_state requires as_of or full_history=True")
        ident = load_identity(self.cfg)
        hit = ident[ident["internal_game_id"] == internal_game_id]
        if hit.empty:
            raise KeyError(internal_game_id)
        rec = hit.iloc[0].to_dict()
        sport, season = rec["sport"], rec["season"]
        games = self.dataset(sport, season, "games", as_of=as_of, end_of_day=end_of_day, full_history=full_history)
        game_row = games[games["internal_game_id"] == internal_game_id]
        pbp = load_dataset(self.cfg, sport, season, "pbp")
        pbp = pbp[pbp["internal_game_id"] == internal_game_id] if not pbp.empty else pbp
        candles = load_dataset(self.cfg, sport, season, "kalshi_candles")
        candles = candles[candles["internal_game_id"] == internal_game_id] if not candles.empty else candles
        feats = load_dataset(self.cfg, sport, season, "team_features")
        feats = feats[feats["internal_game_id"] == internal_game_id] if not feats.empty else feats
        if not full_history:
            pbp_f = public_filter(pbp, as_of=as_of, end_of_day=end_of_day) if not pbp.empty else pbp
            c_f = public_filter(candles, as_of=as_of, end_of_day=end_of_day) if not candles.empty else candles
            f_f = public_filter(feats, as_of=as_of, end_of_day=end_of_day) if not feats.empty else feats
        else:
            pbp_f, c_f, f_f = pbp, candles, feats
        latest = latest_pbp(pbp, as_of, end_of_day) if as_of is not None and not pbp.empty else None
        candle = latest_candle(candles, as_of, end_of_day) if as_of is not None and not candles.empty else None
        return {
            "internal_game_id": internal_game_id,
            "game": game_row.iloc[0].to_dict() if not game_row.empty else None,
            "pre_game_features": f_f.to_dict("records") if not f_f.empty else [],
            "score": {
                "home": None if latest is None else latest.get("home_score"),
                "away": None if latest is None else latest.get("away_score"),
                "score_differential_home": None if latest is None else latest.get("score_differential_home"),
            },
            "period": None if latest is None else latest.get("period"),
            "clock": None if latest is None else latest.get("clock"),
            "pbp": None if latest is None else latest.to_dict(),
            "market": None if candle is None else candle.to_dict(),
            "n_pbp_available": int(len(pbp_f)),
            "n_candles_available": int(len(c_f)),
        }

    def observation(
        self,
        internal_game_id: str,
        as_of=None,
        end_of_day: bool = False,
        full_history: bool = False,
    ) -> dict[str, Any]:
        from roller.state.observation import assemble_observation

        return assemble_observation(
            self.cfg,
            internal_game_id,
            as_of=as_of,
            end_of_day=end_of_day,
            full_history=full_history,
        )

    def clock_snap(
        self,
        internal_game_id: str,
        timestamp,
        as_of=None,
        end_of_day: bool = False,
        full_history: bool = False,
    ) -> dict[str, Any]:
        from roller.state.clock_snap import clock_snap

        return clock_snap(
            self.cfg,
            internal_game_id,
            timestamp,
            as_of=as_of,
            end_of_day=end_of_day,
            full_history=full_history,
        )

    def first80(
        self,
        internal_game_id: str | None = None,
        sport: str | None = None,
        season: str | None = None,
        as_of=None,
        end_of_day: bool = False,
        full_history: bool = False,
    ) -> dict[str, Any]:
        from roller.research.first80 import load_first80

        return load_first80(
            self.cfg,
            internal_game_id=internal_game_id,
            sport=sport,
            season=season,
            as_of=as_of,
            end_of_day=end_of_day,
            full_history=full_history,
        )

    def labels(
        self,
        observation_id: str | None = None,
        internal_game_id: str | None = None,
        as_of=None,
        end_of_day: bool = False,
    ) -> dict[str, Any]:
        from roller.labels.engine import build_labels

        return build_labels(
            self.cfg,
            observation_id=observation_id,
            internal_game_id=internal_game_id,
            as_of=as_of,
            end_of_day=end_of_day,
        )

    def research(self, *args: Any, **kwargs: Any) -> None:
        raise ResearchNotImplementedError(
            "db.research remains unimplemented; V4A exposes db.fundamental(); "
            "V4B exposes db.greeks(). It cannot combine labels into I(t) or implement train/OOS"
        )

    def greeks(
        self,
        observation_id: str,
        names: list[str] | None = None,
        corpus: list[dict[str, Any]] | None = None,
        schema_version: str | None = None,
    ) -> dict[str, Any]:
        payload = self._canonical_v4b_greeks(observation_id, names=names, corpus=corpus)
        version = schema_version or "4.0.0-B"
        if version == "4.0.0-B":
            return payload
        if version == "4.0.0-C":
            from roller.v4c.mapping import overlay_architecture

            return overlay_architecture(self.cfg, payload)
        raise ValueError(f"unknown greek schema_version {schema_version!r}")

    def _canonical_v4b_greeks(
        self,
        observation_id: str,
        names: list[str] | None = None,
        corpus: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from roller.measurement.response import load_game_tables
        from roller.state.observation import assemble_observation
        from roller.state.observation_id import parse_observation_id
        from roller.v4b.baseline import load_v4b_corpus
        from roller.v4b.measurements import assemble_shared_xt, build_greeks_payload, compute_observed

        gid, obs_time, _ver = parse_observation_id(observation_id)
        obs = assemble_observation(self.cfg, gid, as_of=obs_time)
        _sport, _season, candles, _pbp = load_game_tables(self.cfg, gid)

        def fundamental_fn(oid: str) -> dict[str, Any]:
            return self.fundamental(oid)

        def load_obs(game_id: str, cutoff):
            return assemble_observation(self.cfg, game_id, as_of=cutoff)

        xt = assemble_shared_xt(
            self.cfg,
            observation=obs,
            candles=candles,
            fundamental_fn=fundamental_fn,
            load_observation=load_obs,
        )
        observed = compute_observed(xt)
        if names:
            allow = set(names)
            observed = {k: v for k, v in observed.items() if k in allow}
        rows = corpus if corpus is not None else load_v4b_corpus(self.cfg, xt.sport, xt.season)
        return build_greeks_payload(self.cfg, xt, observed, rows)

    def fundamental(
        self,
        observation_id: str,
        name: str = "fundamental_win_probability_empirical_v1",
        conditioning_schema_version: str | None = None,
        corpus: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from roller.fundamental.corpus import load_fundamental_corpus
        from roller.fundamental.estimator import estimate_fundamental
        from roller.state.observation import assemble_observation
        from roller.state.observation_id import parse_observation_id

        gid, obs_time, _ver = parse_observation_id(observation_id)
        obs = assemble_observation(self.cfg, gid, as_of=obs_time)
        rows = corpus if corpus is not None else load_fundamental_corpus(self.cfg, obs["sport"], obs["season"])
        return estimate_fundamental(
            self.cfg,
            observation=obs,
            name=name,
            conditioning_schema_version=conditioning_schema_version,
            corpus=rows,
        )

    def response(self, observation_id: str, measurement: str, horizon: str) -> dict[str, Any]:
        from roller.measurement.conditioning import condition_observation
        from roller.measurement.response import build_response, load_game_tables
        from roller.state.observation import assemble_observation
        from roller.state.observation_id import parse_observation_id

        gid, obs_time, _ver = parse_observation_id(observation_id)
        sport, season, candles, pbp = load_game_tables(self.cfg, gid)
        row = build_response(
            self.cfg,
            observation_id=observation_id,
            measurement=measurement,
            horizon=horizon,
            candles=candles,
            pbp=pbp,
        )
        obs = assemble_observation(self.cfg, gid, as_of=obs_time)
        cond = condition_observation(self.cfg, obs)
        row["condition_id"] = cond["condition_id"]
        row["internal_game_id"] = gid
        row["sport"] = sport
        row["season"] = season
        return row

    def baseline(
        self,
        observation_id: str,
        measurement: str,
        horizon: str,
        corpus: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from roller.measurement.baseline import compute_baseline
        from roller.measurement.corpus import load_response_corpus
        from roller.state.observation import assemble_observation
        from roller.state.observation_id import parse_observation_id

        gid, obs_time, _ver = parse_observation_id(observation_id)
        obs = assemble_observation(self.cfg, gid, as_of=obs_time)
        rows = corpus if corpus is not None else load_response_corpus(self.cfg, obs["sport"], obs["season"])
        return compute_baseline(
            self.cfg,
            observation=obs,
            measurement=measurement,
            horizon=horizon,
            corpus=rows,
            cutoff=obs_time,
        )

    def residual(
        self,
        observation_id: str,
        measurement: str,
        horizon: str,
        corpus: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from roller.greeks.residual import compute_residual

        y = self.response(observation_id=observation_id, measurement=measurement, horizon=horizon)
        base = self.baseline(
            observation_id=observation_id, measurement=measurement, horizon=horizon, corpus=corpus
        )
        return compute_residual(y, base)

