"""Deterministic tennis state derived from a canonical PBP row.

Pure functions. No I/O. Observation only.

MISSING IS NOT FALSE
--------------------
Every predicate returns ``bool | None``. ``None`` means "the inputs required
to decide this were not present", and it must never collapse to ``False``.
A row with no score cannot be asserted to be "not a break point".

THREE SEPARATE LEAD DIMENSIONS
------------------------------
``set_lead``, ``game_lead`` and ``point_lead`` are returned independently and
are never summed, weighted or collapsed into one differential. A player up a
set and down a break is not "even".

FORMAT PARAMETERS, NOT TOURNAMENT SPECIAL CASES
-----------------------------------------------
Best-of-3 and best-of-5 are handled by the same arithmetic
(``sets_to_win = best_of // 2 + 1``). Set length, set margin and tiebreak
target are explicit parameters with standard defaults, so non-standard
formats are expressed by passing different numbers, never by branching on a
tournament name.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PLAYER_1 = 1
PLAYER_2 = 2
VALID_PLAYERS = frozenset({PLAYER_1, PLAYER_2})

POINT_AD = "AD"
# Ordinal rank of a classic game score. Used for point_lead only; the raw
# token is what is stored on the row. "AD" is a rank, never a number.
POINT_RANK: dict[str, int] = {"0": 0, "15": 1, "30": 2, "40": 3, POINT_AD: 4}

DEFAULT_GAMES_TO_WIN_SET = 6
DEFAULT_SET_MARGIN = 2
DEFAULT_TIEBREAK_TARGET = 7


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _token(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _player(value: Any) -> int | None:
    parsed = _int(value)
    return parsed if parsed in VALID_PLAYERS else None


def _tiebreak_points(token: str | None) -> int | None:
    if token is None or not token.isdigit():
        return None
    return int(token)


def sets_to_win(best_of: Any) -> int | None:
    """2 for best-of-3, 3 for best-of-5. No per-tournament branching."""
    parsed = _int(best_of)
    if parsed is None or parsed < 1 or parsed % 2 == 0:
        return None
    return parsed // 2 + 1


def set_lead(sets_p1: Any, sets_p2: Any) -> int | None:
    a, b = _int(sets_p1), _int(sets_p2)
    if a is None or b is None:
        return None
    return a - b


def game_lead(games_p1: Any, games_p2: Any) -> int | None:
    a, b = _int(games_p1), _int(games_p2)
    if a is None or b is None:
        return None
    return a - b


def point_lead(points_p1_raw: Any, points_p2_raw: Any, is_tiebreak: Any) -> int | None:
    """Signed point lead for p1.

    In a tiebreak this is the numeric point difference. In a normal game it is
    the difference of ordinal ranks (0/15/30/40/AD -> 0/1/2/3/4), because
    "15" is a label, not a quantity. Returns None when the tiebreak status is
    unknown, since the two scales are not interchangeable.
    """
    left, right = _token(points_p1_raw), _token(points_p2_raw)
    if left is None or right is None or is_tiebreak is None:
        return None
    if is_tiebreak:
        a, b = _tiebreak_points(left), _tiebreak_points(right)
        if a is None or b is None:
            return None
        return a - b
    if left not in POINT_RANK or right not in POINT_RANK:
        return None
    return POINT_RANK[left] - POINT_RANK[right]


def game_point(
    points_p1_raw: Any,
    points_p2_raw: Any,
    is_tiebreak: Any,
    *,
    tiebreak_target: int = DEFAULT_TIEBREAK_TARGET,
) -> tuple[bool | None, bool | None]:
    """(p1_has_game_point, p2_has_game_point) for the current game.

    In a tiebreak "game point" means one point from winning the tiebreak,
    which decides the set. ``tiebreak_target`` is a parameter because a
    10-point match tiebreak is not inferable from a charted point row; the
    caller must state the format rather than have it guessed here.
    """
    left, right = _token(points_p1_raw), _token(points_p2_raw)
    if left is None or right is None or is_tiebreak is None:
        return None, None
    if is_tiebreak:
        a, b = _tiebreak_points(left), _tiebreak_points(right)
        if a is None or b is None:
            return None, None
        target = _int(tiebreak_target)
        if target is None or target < 1:
            return None, None
        p1 = (a + 1) >= target and (a + 1 - b) >= DEFAULT_SET_MARGIN
        p2 = (b + 1) >= target and (b + 1 - a) >= DEFAULT_SET_MARGIN
        return p1, p2
    if left not in POINT_RANK or right not in POINT_RANK:
        return None, None
    if left == POINT_AD and right == POINT_AD:
        # Not a real score. Fail closed rather than assert a game point.
        return None, None
    p1 = left == POINT_AD or (left == "40" and right != "40" and right != POINT_AD)
    p2 = right == POINT_AD or (right == "40" and left != "40" and left != POINT_AD)
    return p1, p2


def break_point(
    points_p1_raw: Any,
    points_p2_raw: Any,
    server: Any,
    is_tiebreak: Any,
    *,
    tiebreak_target: int = DEFAULT_TIEBREAK_TARGET,
) -> bool | None:
    """True when the receiver is one point from winning the server's game.

    A tiebreak has no service game to break, so a tiebreak point returns
    ``False``. That is a determinate fact about the format, not missing data,
    which is why it is False and not None.
    """
    srv = _player(server)
    if srv is None or is_tiebreak is None:
        return None
    if is_tiebreak:
        return False
    p1, p2 = game_point(points_p1_raw, points_p2_raw, is_tiebreak, tiebreak_target=tiebreak_target)
    if p1 is None or p2 is None:
        return None
    return p2 if srv == PLAYER_1 else p1


def _set_won_by(
    games_for: int,
    games_against: int,
    *,
    games_to_win_set: int,
    set_margin: int,
) -> bool:
    """Would ``games_for`` games (after winning the current game) take the set?"""
    if games_for < games_to_win_set:
        return False
    if games_for - games_against >= set_margin:
        return True
    # 7-6 style: one past the target with a one-game margin, i.e. the tiebreak.
    return games_for == games_to_win_set + 1 and games_for - games_against == 1


def set_point(
    points_p1_raw: Any,
    points_p2_raw: Any,
    games_p1: Any,
    games_p2: Any,
    is_tiebreak: Any,
    *,
    games_to_win_set: int = DEFAULT_GAMES_TO_WIN_SET,
    set_margin: int = DEFAULT_SET_MARGIN,
    tiebreak_target: int = DEFAULT_TIEBREAK_TARGET,
) -> tuple[bool | None, bool | None]:
    """(p1_has_set_point, p2_has_set_point).

    A player has a set point when winning the current point wins the current
    game AND winning that game wins the set.
    """
    gp1, gp2 = game_point(points_p1_raw, points_p2_raw, is_tiebreak, tiebreak_target=tiebreak_target)
    if gp1 is None or gp2 is None:
        return None, None
    g1, g2 = _int(games_p1), _int(games_p2)
    if g1 is None or g2 is None:
        return None, None
    if is_tiebreak:
        # Winning a tiebreak wins the set by definition of the format.
        return gp1, gp2
    p1 = gp1 and _set_won_by(g1 + 1, g2, games_to_win_set=games_to_win_set, set_margin=set_margin)
    p2 = gp2 and _set_won_by(g2 + 1, g1, games_to_win_set=games_to_win_set, set_margin=set_margin)
    return p1, p2


def match_point(
    points_p1_raw: Any,
    points_p2_raw: Any,
    games_p1: Any,
    games_p2: Any,
    sets_p1: Any,
    sets_p2: Any,
    best_of: Any,
    is_tiebreak: Any,
    *,
    games_to_win_set: int = DEFAULT_GAMES_TO_WIN_SET,
    set_margin: int = DEFAULT_SET_MARGIN,
    tiebreak_target: int = DEFAULT_TIEBREAK_TARGET,
) -> tuple[bool | None, bool | None]:
    """(p1_has_match_point, p2_has_match_point).

    A match point is a set point that also completes the required set count.
    Works for best-of-3 and best-of-5 through the same arithmetic.
    """
    needed = sets_to_win(best_of)
    if needed is None:
        return None, None
    s1, s2 = _int(sets_p1), _int(sets_p2)
    if s1 is None or s2 is None:
        return None, None
    sp1, sp2 = set_point(
        points_p1_raw,
        points_p2_raw,
        games_p1,
        games_p2,
        is_tiebreak,
        games_to_win_set=games_to_win_set,
        set_margin=set_margin,
        tiebreak_target=tiebreak_target,
    )
    if sp1 is None or sp2 is None:
        return None, None
    return bool(sp1 and s1 + 1 >= needed), bool(sp2 and s2 + 1 >= needed)


STATE_FIELDS: tuple[str, ...] = (
    "set_lead",
    "game_lead",
    "point_lead",
    "game_point_p1",
    "game_point_p2",
    "break_point",
    "set_point_p1",
    "set_point_p2",
    "match_point_p1",
    "match_point_p2",
    "sets_to_win",
)


def derive_state(
    row: Mapping[str, Any] | None,
    *,
    games_to_win_set: int = DEFAULT_GAMES_TO_WIN_SET,
    set_margin: int = DEFAULT_SET_MARGIN,
    tiebreak_target: int = DEFAULT_TIEBREAK_TARGET,
) -> dict[str, Any]:
    """Derive every state field from one canonical PBP row.

    A missing or empty row yields all-None, never all-False.
    """
    if not row:
        return dict.fromkeys(STATE_FIELDS)
    p1_pts = row.get("points_p1_raw")
    p2_pts = row.get("points_p2_raw")
    tb = row.get("is_tiebreak")
    kwargs = {
        "games_to_win_set": games_to_win_set,
        "set_margin": set_margin,
        "tiebreak_target": tiebreak_target,
    }
    gp1, gp2 = game_point(p1_pts, p2_pts, tb, tiebreak_target=tiebreak_target)
    sp1, sp2 = set_point(p1_pts, p2_pts, row.get("games_p1"), row.get("games_p2"), tb, **kwargs)
    mp1, mp2 = match_point(
        p1_pts,
        p2_pts,
        row.get("games_p1"),
        row.get("games_p2"),
        row.get("sets_p1"),
        row.get("sets_p2"),
        row.get("best_of"),
        tb,
        **kwargs,
    )
    return {
        "set_lead": set_lead(row.get("sets_p1"), row.get("sets_p2")),
        "game_lead": game_lead(row.get("games_p1"), row.get("games_p2")),
        "point_lead": point_lead(p1_pts, p2_pts, tb),
        "game_point_p1": gp1,
        "game_point_p2": gp2,
        "break_point": break_point(p1_pts, p2_pts, row.get("server"), tb, tiebreak_target=tiebreak_target),
        "set_point_p1": sp1,
        "set_point_p2": sp2,
        "match_point_p1": mp1,
        "match_point_p2": mp2,
        "sets_to_win": sets_to_win(row.get("best_of")),
    }


# --------------------------------------------------------------------------
# Contract-relative view. `yes_player` is which MCP player slot (1 or 2) the
# Kalshi YES side refers to. Nothing here prices or trades anything.
# --------------------------------------------------------------------------


def yes_serving(server: Any, yes_player: Any) -> bool | None:
    srv, yes = _player(server), _player(yes_player)
    if srv is None or yes is None:
        return None
    return srv == yes


def yes_returning(server: Any, yes_player: Any) -> bool | None:
    serving = yes_serving(server, yes_player)
    return None if serving is None else not serving


def _orient(value: int | None, yes_player: int | None) -> int | None:
    if value is None or yes_player is None:
        return None
    return value if yes_player == PLAYER_1 else -value


def yes_set_lead(sets_p1: Any, sets_p2: Any, yes_player: Any) -> int | None:
    return _orient(set_lead(sets_p1, sets_p2), _player(yes_player))


def yes_game_lead(games_p1: Any, games_p2: Any, yes_player: Any) -> int | None:
    return _orient(game_lead(games_p1, games_p2), _player(yes_player))


def yes_point_lead(points_p1_raw: Any, points_p2_raw: Any, is_tiebreak: Any, yes_player: Any) -> int | None:
    return _orient(point_lead(points_p1_raw, points_p2_raw, is_tiebreak), _player(yes_player))


YES_STATE_FIELDS: tuple[str, ...] = (
    "yes_serving",
    "yes_returning",
    "yes_set_lead",
    "yes_game_lead",
    "yes_point_lead",
    "yes_game_point",
    "yes_set_point",
    "yes_match_point",
    "yes_faces_match_point",
    "break_point",
)


def yes_view(
    row: Mapping[str, Any] | None,
    yes_player: Any,
    *,
    games_to_win_set: int = DEFAULT_GAMES_TO_WIN_SET,
    set_margin: int = DEFAULT_SET_MARGIN,
    tiebreak_target: int = DEFAULT_TIEBREAK_TARGET,
) -> dict[str, Any]:
    """Contract-relative state for the player the YES contract refers to."""
    yes = _player(yes_player)
    if not row or yes is None:
        return dict.fromkeys(YES_STATE_FIELDS)
    state = derive_state(
        row,
        games_to_win_set=games_to_win_set,
        set_margin=set_margin,
        tiebreak_target=tiebreak_target,
    )

    def pick(field_p1: str, field_p2: str) -> bool | None:
        return state[field_p1] if yes == PLAYER_1 else state[field_p2]

    def pick_other(field_p1: str, field_p2: str) -> bool | None:
        return state[field_p2] if yes == PLAYER_1 else state[field_p1]

    return {
        "yes_serving": yes_serving(row.get("server"), yes),
        "yes_returning": yes_returning(row.get("server"), yes),
        "yes_set_lead": _orient(state["set_lead"], yes),
        "yes_game_lead": _orient(state["game_lead"], yes),
        "yes_point_lead": _orient(state["point_lead"], yes),
        "yes_game_point": pick("game_point_p1", "game_point_p2"),
        "yes_set_point": pick("set_point_p1", "set_point_p2"),
        "yes_match_point": pick("match_point_p1", "match_point_p2"),
        "yes_faces_match_point": pick_other("match_point_p1", "match_point_p2"),
        "break_point": state["break_point"],
    }
