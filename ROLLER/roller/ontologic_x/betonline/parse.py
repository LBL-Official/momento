"""Normalize a BetOnline offering payload. A zero American and zero decimal is not a price."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from roller.ontologic_x.betonline import BOOKMAKER, event_url
from roller.ontologic_x.math import InvalidPrice, american_implied, proportional_no_vig

OPEN_EVENT = {"ACTIVE", "OPEN", ""}
UNPUBLISHED_PERIODS = ("1h", "2h", "Q1", "Q2", "Q3", "Q4")
GROUP_NAMES = ("game_lines", "linked_periods", "team_totals", "alternates", "player_props")


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _zero(value: object) -> bool:
    number = _decimal(value)
    return number is not None and number == 0


def price_state(node: object) -> str:
    """Distinguish an absent price from the feed's zero sentinel."""
    if not isinstance(node, dict):
        return "NOT_YET_PRICED"
    if "Line" not in node and "DecimalLine" not in node:
        return "NOT_YET_PRICED"
    if _zero(node.get("Line")) and _zero(node.get("DecimalLine")):
        return "MARKET_NOT_OFFERED"
    if node.get("Line") is None and node.get("DecimalLine") is None:
        return "NOT_YET_PRICED"
    return "PRICED"


def _fractional(node: dict) -> str | None:
    numerator = node.get("FractionalNumeratorLine")
    denominator = node.get("FractionalDenominatorLine")
    if _zero(numerator) and _zero(denominator):
        return None
    if numerator in {None, ""} or denominator in {None, ""}:
        return None
    return f"{numerator}/{denominator}"


def _priced_fields(node: dict) -> dict:
    american = str(node.get("Line"))
    if american.endswith(".0"):
        american = american[:-2]
    source_decimal = None if node.get("DecimalLine") in {None, ""} else str(node.get("DecimalLine"))
    try:
        decimal_odds, implied = american_implied(american)
    except InvalidPrice:
        decimal_odds, implied = None, None
    decimal_text = None if decimal_odds is None else format(decimal_odds, "f")
    discrepancy = None
    source_number = _decimal(source_decimal)
    converted = _decimal(decimal_text)
    if source_number is not None and converted is not None and source_number != converted:
        discrepancy = format(source_number - converted, "f")
    return {
        "american": american,
        "source_decimal": source_decimal,
        "decimal_odds": decimal_text,
        "decimal_discrepancy": discrepancy,
        "implied": None if implied is None else format(implied, "f"),
        "fractional": _fractional(node),
    }


def wager_cutoff(game: dict) -> str | None:
    """WagerCutOff is a betting cutoff. With utc-offset 0 it is UTC. It is not a quote-update time."""
    text = str(game.get("WagerCutOff") or game.get("PeriodWagerCutOff") or "").strip()
    if not text or text.startswith("0001-"):
        return None
    if text.endswith("Z") or "+" in text[10:]:
        return text if text.endswith("Z") else text
    return f"{text}Z"


def start_utc(game: dict) -> str | None:
    """Backward-compatible name for the cutoff clock. Quote freshness does not use it."""
    return wager_cutoff(game)


def period_key(name: object, number: object) -> str:
    text = " ".join(str(name or "").casefold().split())
    if text in {"game", "full game", ""} and str(number) in {"0", "0.0", ""}:
        return "game"
    if text in {"game", "full game"}:
        return "game"
    aliases = {
        "1st half": "1h",
        "first half": "1h",
        "1h": "1h",
        "2nd half": "2h",
        "second half": "2h",
        "2h": "2h",
        "1st quarter": "Q1",
        "first quarter": "Q1",
        "q1": "Q1",
        "2nd quarter": "Q2",
        "second quarter": "Q2",
        "q2": "Q2",
        "3rd quarter": "Q3",
        "third quarter": "Q3",
        "q3": "Q3",
        "4th quarter": "Q4",
        "fourth quarter": "Q4",
        "q4": "Q4",
    }
    if text in aliases:
        return aliases[text]
    return text or f"period-{number}"


def event_quote_status(event_status: object, node: object = None) -> str:
    if isinstance(node, dict) and node.get("Suspended") is True:
        return "MARKET_SUSPENDED"
    text = str(event_status or "ACTIVE").strip().upper()
    if text in OPEN_EVENT:
        return "open"
    return "MARKET_SUSPENDED"


def iter_league_games(payload: dict) -> list[dict]:
    offering = payload.get("GameOffering") or {}
    games = []
    for row in offering.get("GamesDescription") or []:
        game = row.get("Game") or row
        if isinstance(game, dict) and game.get("GameId"):
            games.append(game)
    for league in offering.get("LeagueGroup") or []:
        for date_group in league.get("DateGrouping") or []:
            for schedule in date_group.get("ScheduleGroup") or []:
                for moment in schedule.get("TimeGrouping") or []:
                    for game in moment.get("Games") or []:
                        if isinstance(game, dict) and game.get("GameId"):
                            games.append(game)
    return games


def _line_text(point: object) -> str | None:
    number = _decimal(point)
    if number is None:
        return None
    return format(number, "f")


def _blank(game: dict, family: str, period: str, side: str, market_name: str, event_status: str) -> dict:
    game_id = game.get("GameId")
    return {
        "bookmaker": BOOKMAKER,
        "provider": "betonline",
        "provider_event_id": str(game_id),
        "home_team": game.get("HomeTeam"),
        "away_team": game.get("AwayTeam"),
        "home_rotation": game.get("HomeRotation"),
        "away_rotation": game.get("AwayRotation"),
        "wager_cutoff": wager_cutoff(game),
        "start_utc": None,
        "timezone": "UTC",
        "period": period,
        "market_family": family,
        "market_name": market_name,
        "participant": None,
        "market_id": None,
        "outcome_id": None,
        "side": side,
        "line": None,
        "status": "MARKET_NOT_OFFERED",
        "event_status": str(event_status or "ACTIVE"),
        "source_url": event_url(game_id),
        "source_updated_at": None,
        "american": None,
        "source_decimal": None,
        "decimal_odds": None,
        "decimal_discrepancy": None,
        "implied": None,
        "fractional": None,
        "main": period == "game" and family in {"spread", "moneyline", "total"},
        "settlement": None,
        "specialty": family in {"player_prop", "unmapped"},
    }


def _outcome(
    game: dict,
    family: str,
    period: str,
    side: str,
    node: object,
    point: object,
    event_status: str,
    *,
    market_name: str,
    participant: str | None = None,
    market_id: object = None,
    outcome_id: object = None,
) -> dict:
    record = _blank(game, family, period, side, market_name, event_status)
    record["participant"] = participant
    record["market_id"] = None if market_id is None else str(market_id)
    record["outcome_id"] = None if outcome_id is None else str(outcome_id)
    record["line"] = None if family == "moneyline" else _line_text(point)
    if node is not None and not isinstance(node, dict):
        record["status"] = "PARSE_FAILED"
        return record
    state = price_state(node)
    quote_status = event_quote_status(event_status, node if isinstance(node, dict) else None)
    if state == "PRICED" and isinstance(node, dict) and quote_status == "open":
        record["status"] = "open"
        record.update(_priced_fields(node))
        if family != "moneyline":
            record["line"] = _line_text(point if point is not None else node.get("Point"))
    elif state == "PRICED" and quote_status != "open":
        record["status"] = "MARKET_SUSPENDED"
    elif state == "NOT_YET_PRICED":
        record["status"] = "NOT_YET_PRICED"
    else:
        record["status"] = "MARKET_NOT_OFFERED"
    if record["status"] != "open" and (_zero(point) or point is None):
        record["line"] = None
    return record


def _spread_total_moneyline(game: dict, period: str, event_status: str) -> list[dict]:
    away = game.get("AwayLine") if isinstance(game.get("AwayLine"), dict) else {}
    home = game.get("HomeLine") if isinstance(game.get("HomeLine"), dict) else {}
    total_holder = game.get("TotalLine") if isinstance(game.get("TotalLine"), dict) else {}
    total = total_holder.get("TotalLine") if isinstance(total_holder.get("TotalLine"), dict) else {}
    rows = [
        _outcome(game, "spread", period, "away", away.get("SpreadLine"), (away.get("SpreadLine") or {}).get("Point") if isinstance(away.get("SpreadLine"), dict) else None, event_status, market_name="Spread"),
        _outcome(game, "spread", period, "home", home.get("SpreadLine"), (home.get("SpreadLine") or {}).get("Point") if isinstance(home.get("SpreadLine"), dict) else None, event_status, market_name="Spread"),
        _outcome(game, "moneyline", period, "away", away.get("MoneyLine"), None, event_status, market_name="Moneyline"),
        _outcome(game, "moneyline", period, "home", home.get("MoneyLine"), None, event_status, market_name="Moneyline"),
        _outcome(game, "total", period, "over", total.get("Over"), total.get("Point"), event_status, market_name="Total"),
        _outcome(game, "total", period, "under", total.get("Under"), total.get("Point"), event_status, market_name="Total"),
    ]
    away_name = str(game.get("AwayTeam") or "away")
    home_name = str(game.get("HomeTeam") or "home")
    rows.extend(_team_total(game, period, event_status, away_name, away.get("TeamTotalLine")))
    rows.extend(_team_total(game, period, event_status, home_name, home.get("TeamTotalLine")))
    return rows


def _team_total(game: dict, period: str, event_status: str, participant: str, node: object) -> list[dict]:
    if node is None:
        over = _blank(game, "team_total", period, "over", "Team Total", event_status)
        under = _blank(game, "team_total", period, "under", "Team Total", event_status)
        over["participant"] = participant
        under["participant"] = participant
        return [over, under]
    if not isinstance(node, dict):
        failed = _blank(game, "team_total", period, "board", "Team Total", event_status)
        failed["participant"] = participant
        failed["status"] = "PARSE_FAILED"
        return [failed]
    return [
        _outcome(game, "team_total", period, "over", node.get("Over"), node.get("Point"), event_status, market_name="Team Total", participant=participant),
        _outcome(game, "team_total", period, "under", node.get("Under"), node.get("Point"), event_status, market_name="Team Total", participant=participant),
    ]


def _buy_points(game: dict, period: str, event_status: str, rule: object) -> list[dict]:
    if rule is None:
        row = _blank(game, "alternate", period, "board", "Alternate", event_status)
        return [row]
    items = rule if isinstance(rule, list) else [rule]
    rows: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            failed = _blank(game, "alternate", period, "board", "Alternate", event_status)
            failed["status"] = "PARSE_FAILED"
            rows.append(failed)
            continue
        away = item.get("Away") if isinstance(item.get("Away"), dict) else None
        home = item.get("Home") if isinstance(item.get("Home"), dict) else None
        over = item.get("Over") if isinstance(item.get("Over"), dict) else None
        under = item.get("Under") if isinstance(item.get("Under"), dict) else None
        if away or home:
            away_point = None if away is None else away.get("Point", item.get("Point"))
            home_point = None if home is None else home.get("Point")
            rows.append(_outcome(game, "alternate_spread", period, "away", away, away_point, event_status, market_name="Alternate Spread"))
            rows.append(_outcome(game, "alternate_spread", period, "home", home, home_point, event_status, market_name="Alternate Spread"))
            continue
        if over or under:
            rows.append(_outcome(game, "alternate_total", period, "over", over, item.get("Point"), event_status, market_name="Alternate Total"))
            rows.append(_outcome(game, "alternate_total", period, "under", under, item.get("Point"), event_status, market_name="Alternate Total"))
            continue
        unmapped = _blank(game, "unmapped", period, "board", str(item.get("MarketName") or item.get("Name") or "BuyPointLineRule"), event_status)
        unmapped["status"] = "UNMAPPED_MARKET"
        unmapped["specialty"] = True
        unmapped["raw_market"] = {key: item.get(key) for key in list(item)[:12]}
        rows.append(unmapped)
    return rows


def _unmapped_market(game: dict, period: str, event_status: str, market: dict) -> list[dict]:
    name = str(market.get("MarketName") or market.get("Name") or market.get("ContestType") or "Unmapped")
    outcomes = market.get("Outcomes") or market.get("Contestants") or market.get("Participants")
    if not isinstance(outcomes, list) or not outcomes:
        row = _blank(game, "unmapped", period, "board", name, event_status)
        row["status"] = "UNMAPPED_MARKET"
        row["specialty"] = True
        row["market_id"] = None if market.get("MarketId") is None else str(market.get("MarketId"))
        row["raw_market"] = {key: market.get(key) for key in list(market)[:8] if key not in {"Outcomes", "Contestants"}}
        return [row]
    rows = []
    for index, outcome in enumerate(outcomes):
        if not isinstance(outcome, dict):
            failed = _blank(game, "unmapped", period, "board", name, event_status)
            failed["status"] = "PARSE_FAILED"
            rows.append(failed)
            continue
        side = str(outcome.get("Side") or outcome.get("Name") or index)
        row = _outcome(
            game,
            "unmapped",
            period,
            side,
            outcome,
            outcome.get("Point"),
            event_status,
            market_name=name,
            participant=None if outcome.get("Participant") is None else str(outcome.get("Participant")),
            market_id=market.get("MarketId") or market.get("ContestId"),
            outcome_id=outcome.get("OutcomeId") or outcome.get("Id"),
        )
        if row["status"] == "open":
            row["status"] = "UNMAPPED_MARKET"
            row["specialty"] = True
        elif row["status"] == "MARKET_NOT_OFFERED":
            row["status"] = "UNMAPPED_MARKET"
            row["specialty"] = True
        rows.append(row)
    return rows


def _linked_period_events(linked_payload: object) -> list[dict]:
    if linked_payload is None:
        return []
    rows: list[dict] = []
    items = linked_payload if isinstance(linked_payload, list) else [linked_payload]
    for item in items:
        if not isinstance(item, dict):
            continue
        periods = item.get("PeriodEvents")
        if isinstance(periods, list):
            rows.extend(period for period in periods if isinstance(period, dict))
        elif item.get("Name") is not None and item.get("Event") is not None:
            rows.append(item)
    return rows


def _published_games(game: dict, event_payload: dict | None, linked_payload: object) -> list[tuple[str, dict]]:
    published: list[tuple[str, dict]] = [("game", game)]
    seen = {"game"}
    if isinstance(event_payload, dict):
        offering = event_payload.get("EventOffering") or {}
        for period_row in offering.get("PeriodEvents") or []:
            if not isinstance(period_row, dict):
                continue
            key = period_key(period_row.get("Name"), period_row.get("Number"))
            nested = period_row.get("Event") if isinstance(period_row.get("Event"), dict) else game
            if key not in seen:
                published.append((key, nested))
                seen.add(key)
    for period_row in _linked_period_events(linked_payload):
        key = period_key(period_row.get("Name"), period_row.get("Number"))
        nested = period_row.get("Event") if isinstance(period_row.get("Event"), dict) else None
        if nested is None or key in seen:
            continue
        published.append((key, nested))
        seen.add(key)
    return published


def _attach_no_vig(rows: list[dict]) -> list[dict]:
    """Proportional no-vig only inside one complete market, period, and line."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        if row.get("status") not in {"open", "UNMAPPED_MARKET"} or row.get("american") is None or row.get("implied") is None:
            continue
        family = row.get("market_family")
        if family in {"spread", "alternate_spread"}:
            line_key = None if _decimal(row.get("line")) is None else format(abs(_decimal(row.get("line"))), "f")
        else:
            line_key = row.get("line")
        groups.setdefault(
            (
                row.get("provider_event_id"),
                row.get("period"),
                family,
                row.get("market_name"),
                row.get("participant"),
                row.get("market_id"),
                line_key,
            ),
            [],
        ).append(row)
    for grouped in groups.values():
        family = grouped[0].get("market_family")
        if family in {"total", "alternate_total", "team_total"}:
            left = next((item for item in grouped if item.get("side") == "over"), None)
            right = next((item for item in grouped if item.get("side") == "under"), None)
            matched = left is not None and right is not None and left.get("line") == right.get("line") and len(grouped) == 2
        elif family in {"spread", "alternate_spread"}:
            left = next((item for item in grouped if item.get("side") == "away"), None)
            right = next((item for item in grouped if item.get("side") == "home"), None)
            away_line = _decimal(None if left is None else left.get("line"))
            home_line = _decimal(None if right is None else right.get("line"))
            matched = (
                away_line is not None
                and home_line is not None
                and home_line == -away_line
                and len(grouped) == 2
            )
            if left is not None and right is not None and not matched:
                left["no_vig_status"] = "ORIENTATION_INVALID"
                right["no_vig_status"] = "ORIENTATION_INVALID"
        elif family == "moneyline":
            left = next((item for item in grouped if item.get("side") == "away"), None)
            right = next((item for item in grouped if item.get("side") == "home"), None)
            matched = left is not None and right is not None and all(item.get("implied") for item in grouped)
        elif family == "unmapped":
            left = right = None
            matched = len(grouped) >= 2 and all(item.get("implied") for item in grouped)
        else:
            continue
        if family == "unmapped" and matched:
            try:
                raw = [Decimal(str(item["implied"])) for item in grouped]
            except (InvalidOperation, KeyError, TypeError):
                for item in grouped:
                    item["no_vig_status"] = "INCOMPLETE"
                continue
            result = proportional_no_vig(raw)
            for item, normalized in zip(grouped, result.get("normalized") or []):
                item["no_vig_status"] = result["status"]
                if result["status"] == "OK":
                    item["no_vig_probability"] = format(normalized["probability"], "f")
                    item["no_vig_method"] = result["method"]
            continue
        if not matched or left is None or right is None:
            for item in grouped:
                item.setdefault("no_vig_status", "INCOMPLETE")
            continue
        try:
            raw = [Decimal(str(left["implied"])), Decimal(str(right["implied"]))]
        except (InvalidOperation, KeyError, TypeError):
            left["no_vig_status"] = "INCOMPLETE"
            right["no_vig_status"] = "INCOMPLETE"
            continue
        result = proportional_no_vig(raw)
        left["no_vig_status"] = result["status"]
        right["no_vig_status"] = result["status"]
        if result["status"] == "OK":
            left["no_vig_probability"] = format(result["normalized"][0]["probability"], "f")
            right["no_vig_probability"] = format(result["normalized"][1]["probability"], "f")
            left["no_vig_method"] = result["method"]
            right["no_vig_method"] = result["method"]
    return rows


def parse_bundle(
    game: dict,
    event_payload: dict | None = None,
    linked_payload: object = None,
    *,
    event_ok: bool = True,
    linked_ok: bool = False,
) -> tuple[list[dict], dict]:
    """Parse one event. Missing markets are absent only after their group was fetched."""
    event_status = "ACTIVE"
    if isinstance(event_payload, dict) and event_payload.get("EventStatus"):
        event_status = str(event_payload.get("EventStatus"))
    game_id = str(game.get("GameId"))
    failures: list[str] = []
    if not event_ok:
        failures.append("FETCH_FAILED:get-event")
    if not linked_ok:
        failures.append("FETCH_FAILED:get-linked-events")
    rows: list[dict] = []
    published_keys: set[str] = set()
    if event_ok:
        for key, source in _published_games(game, event_payload if event_ok else None, linked_payload if linked_ok else None):
            published_keys.add(key)
            try:
                rows.extend(_spread_total_moneyline(source, key, event_status))
            except (TypeError, ValueError, KeyError):
                failed = _blank(game, "game", key, "board", "Game", event_status)
                failed["status"] = "PARSE_FAILED"
                rows.append(failed)
        away_rule = ((game.get("AwayLine") or {}) if isinstance(game.get("AwayLine"), dict) else {}).get("BuyPointLineRule")
        if away_rule is None and isinstance(game.get("TotalLine"), dict):
            away_rule = game["TotalLine"].get("BuyPointLineRule")
        rows.extend(_buy_points(game, "game", event_status, away_rule))
        offering = (event_payload or {}).get("EventOffering") if isinstance(event_payload, dict) else {}
        markets = (offering or {}).get("Markets") if isinstance(offering, dict) else None
        if isinstance(markets, list):
            for market in markets:
                if isinstance(market, dict):
                    rows.extend(_unmapped_market(game, "game", event_status, market))
                else:
                    failed = _blank(game, "unmapped", "game", "board", "Markets", event_status)
                    failed["status"] = "PARSE_FAILED"
                    rows.append(failed)
    if linked_ok:
        for period_row in _linked_period_events(linked_payload):
            key = period_key(period_row.get("Name"), period_row.get("Number"))
            if key in published_keys:
                continue
            nested = period_row.get("Event")
            if not isinstance(nested, dict):
                continue
            published_keys.add(key)
            rows.extend(_spread_total_moneyline(nested, key, event_status))
    inspected_periods = linked_ok and event_ok
    if inspected_periods:
        for period in UNPUBLISHED_PERIODS:
            if period not in published_keys:
                rows.append(_blank(game, "period", period, "board", period, event_status))
        if not any(row.get("market_family") == "player_prop" or (row.get("specialty") and row.get("market_family") == "unmapped") for row in rows):
            if not game.get("UrlWidgetPlayerProps"):
                rows.append(_blank(game, "player_prop", "game", "board", "Player Props", event_status))
            else:
                pending = _blank(game, "player_prop", "game", "board", "Player Props", event_status)
                pending["status"] = "COVERAGE_INCOMPLETE"
                rows.append(pending)
                failures.append("COVERAGE_INCOMPLETE:player_props_widget")
    elif not event_ok or not linked_ok:
        incomplete = _blank(game, "period", "game", "board", "Coverage", event_status)
        incomplete["status"] = "FETCH_FAILED" if not event_ok else "COVERAGE_INCOMPLETE"
        rows.append(incomplete)
    priced = [row for row in rows if row.get("american") is not None]
    unmapped = [row for row in rows if row.get("status") == "UNMAPPED_MARKET" or row.get("market_family") == "unmapped"]
    fetched = []
    if event_ok:
        fetched.extend(["game_lines", "team_totals", "alternates"])
    if linked_ok:
        fetched.append("linked_periods")
    if event_ok and linked_ok and not game.get("UrlWidgetPlayerProps"):
        fetched.append("player_props")
    status = "INSPECTED"
    if not event_ok:
        status = "FETCH_FAILED"
    elif failures:
        status = "COVERAGE_INCOMPLETE"
    coverage = {
        "provider_event_id": game_id,
        "source_url": event_url(game_id),
        "groups_discovered": list(GROUP_NAMES),
        "groups_fetched": fetched,
        "markets_parsed": len(priced),
        "unmapped_count": len(unmapped),
        "failures": failures,
        "status": status,
    }
    return _attach_no_vig(rows), coverage


def parse_event(game: dict, event_payload: dict | None = None, linked_payload: object = None, *, event_ok: bool = True, linked_ok: bool | None = None) -> list[dict]:
    """One game. Pass an empty linked payload when that call succeeded and returned nothing."""
    if linked_ok is None:
        linked_ok = linked_payload is not None
    records, _coverage = parse_bundle(
        game,
        event_payload,
        linked_payload,
        event_ok=event_ok,
        linked_ok=linked_ok,
    )
    return records
