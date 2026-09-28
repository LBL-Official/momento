"""Synthetic E2E games. Tagged SYNTHETIC. Never presented as warehouse L2."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig


def _season_of(era: str) -> int:
    for year in (2021, 2022, 2023, 2024):
        if str(year) in era:
            return year
    return 2024


ERAS = (
    ("2021-11-10", "early_2021"),
    ("2022-02-01", "late_2021"),
    ("2022-11-10", "early_2022"),
    ("2023-02-01", "late_2022"),
    ("2023-11-01", "early_2023"),
    ("2024-02-01", "late_2023"),
    ("2024-11-15", "early_2024"),
    ("2025-02-10", "late_2024"),
)


def generate_games(cfg: PathFeConfig = DEFAULT) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (ticks, games). ticks are one row per minute × side.

    Latent fragility is a function of impulse + thin book + disagreement so
    A+B+C can have residual information. Books are synthetic, not Kalshi L2.
    """
    rng = np.random.default_rng(cfg.seed)
    tick_rows: list[dict] = []
    game_rows: list[dict] = []
    per_era = max(8, cfg.n_games // len(ERAS))
    gid = 0
    for era_i, (start, era) in enumerate(ERAS):
        base = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
        n_here = per_era if era_i < len(ERAS) - 1 else cfg.n_games - per_era * (len(ERAS) - 1)
        n_here = max(n_here, 8)
        for j in range(n_here):
            gid += 1
            game_id = f"SYN-G{gid:04d}"
            tip = base + timedelta(days=j, hours=int(rng.integers(17, 23)))
            n = int(cfg.ticks_per_game)
            q_len = n // 4
            winner = int(rng.integers(0, 2))  # 0 home, 1 away
            rest_home = int(rng.choice([1, 1, 2, 2, 3, 4]))
            rest_away = int(rng.choice([1, 1, 2, 2, 3, 4]))
            home_final = 100 + int(rng.integers(-15, 16))
            away_final = home_final + (8 if winner == 1 else -8) + int(rng.integers(-6, 7))
            game_rows.append(
                {
                    "game_id": game_id,
                    "era": era,
                    "season": _season_of(era),
                    "tip_utc": tip.isoformat(),
                    "home_team": f"H{gid:03d}",
                    "away_team": f"A{gid:03d}",
                    "winner_side": "home" if winner == 0 else "away",
                    "home_final": int(home_final),
                    "away_final": int(away_final),
                    "rest_home": rest_home,
                    "rest_away": rest_away,
                    "source": cfg.source_tag,
                }
            )
            for side in ("home", "away"):
                mid = f"{game_id}-MKT-{side}"
                start_p = float(rng.integers(42, 62))
                impulse = bool(rng.random() < 0.22)
                thin = bool(rng.random() < 0.18)
                is_winner = (side == "home" and winner == 0) or (side == "away" and winner == 1)
                dest = (88.0 if is_winner else 28.0) + float(rng.normal(0, 5))
                prices = np.zeros(n, dtype=float)
                prices[0] = start_p
                shock_t = int(rng.integers(20, n - 15))
                for t in range(1, n):
                    drift = (dest - prices[t - 1]) / max(8.0, n - t)
                    noise = float(rng.normal(0, 1.6))
                    jump = 0.0
                    if impulse and t == shock_t:
                        jump = float(rng.uniform(10, 22))
                    prices[t] = float(np.clip(prices[t - 1] + drift + noise + jump, 1.0, 99.0))
                if prices.max() < 80:
                    # Favorite-heavy 80-touch, like the asked-six desk. Not a live filter.
                    if is_winner or rng.random() < 0.28:
                        t80 = int(rng.integers(q_len, min(3 * q_len + 10, n - 8)))
                        prices[t80] = 80.0 + float(rng.uniform(0, 4))
                        if impulse and t80 >= 2:
                            prices[t80 - 1] = min(prices[t80] - 8, 79.0)
                t80_idx = int(np.argmax(prices >= 80)) if np.any(prices >= 80) else None
                if t80_idx is not None:
                    if impulse and thin:
                        crash = bool(rng.random() < 0.72)
                    elif impulse or thin:
                        crash = bool(rng.random() < 0.38)
                    else:
                        crash = bool(rng.random() < 0.07)
                    post_dest = 32.0 if crash else dest
                    for t in range(t80_idx + 1, n):
                        drift = (post_dest - prices[t - 1]) / max(6.0, n - t)
                        prices[t] = float(np.clip(prices[t - 1] + drift + float(rng.normal(0, 1.8)), 1.0, 99.0))
                spreads = np.full(n, 4.0 if thin else 2.0) + rng.normal(0, 0.4, size=n)
                spreads = np.clip(spreads, 1.0, 12.0)
                size = np.full(n, 8.0 if thin else 40.0) * rng.uniform(0.6, 1.4, size=n)
                for t in range(n):
                    period = min(4, 1 + t // q_len)
                    sec_left_period = int((q_len - (t % q_len) - 1) * 15)  # 12-min Q ≈ 720s / 48
                    sec_left_game = int((n - t - 1) * 15)
                    # linear score path
                    frac = (t + 1) / n
                    hs = int(round(home_final * frac + rng.normal(0, 1.2)))
                    aws = int(round(away_final * frac + rng.normal(0, 1.2)))
                    ts = tip + timedelta(minutes=t)
                    tick_rows.append(
                        {
                            "game_id": game_id,
                            "era": era,
                            "season": _season_of(era),
                            "market_id": mid,
                            "side": side,
                            "t": t,
                            "timestamp_utc": ts.isoformat(),
                            "period": int(period),
                            "sec_left_period": max(0, sec_left_period),
                            "sec_left_game": max(0, sec_left_game),
                            "yes_bid": int(round(prices[t])),
                            "yes_ask": int(round(np.clip(prices[t] + spreads[t], 1, 99))),
                            "spread": float(spreads[t]),
                            "size_bid": float(max(1.0, size[t])),
                            "home_score": max(0, hs),
                            "away_score": max(0, aws),
                            "possession": int(rng.integers(0, 2)) if rng.random() > 0.12 else None,
                            "impulse_style": int(impulse),
                            "thin_style": int(thin),
                            "source": cfg.source_tag,
                            "book_source": "SYNTHETIC_BOOK",
                        }
                    )
    ticks = pd.DataFrame(tick_rows)
    games = pd.DataFrame(game_rows)
    return ticks, games
