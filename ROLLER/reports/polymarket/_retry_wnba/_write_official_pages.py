"""Persist official Gamma fields from inlined WebFetch pages. No invented events."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SPORT = {
    "id": 6,
    "sport": "wnba",
    "name": "WNBA",
    "image": "https://polymarket-upload.s3.us-east-2.amazonaws.com/league-icons/wnba.png",
    "resolution": "https://www.wnba.com/",
    "ordering": "away",
    "tags": "1,100639,100254",
    "primaryTagId": 100254,
    "series": "10105",
    "createdAt": "2025-11-05T19:27:45.399303Z",
}

TEAMS = {
    "atl": {
        "id": 114248,
        "name": "Atlanta Dream",
        "league": "wnba",
        "record": "32-17",
        "logo": "https://polymarket-upload.s3.us-east-2.amazonaws.com/WNBA Team Logos/ATL.png",
        "abbreviation": "atl",
        "alias": "Dream",
        "createdAt": "2025-05-14T13:26:25.600459Z",
        "updatedAt": "2026-07-31T15:24:52.408047Z",
        "providerId": 1,
        "color": "#e83e52",
    },
    "conn": {
        "id": 114250,
        "name": "Connecticut Sun",
        "league": "wnba",
        "record": "12-34",
        "logo": "https://polymarket-upload.s3.us-east-2.amazonaws.com/WNBA Team Logos/CONN.png",
        "abbreviation": "conn",
        "alias": "Sun",
        "createdAt": "2025-05-14T13:26:25.600459Z",
        "updatedAt": "2026-07-31T04:43:06.192895Z",
        "providerId": 3,
        "color": "#c4651c",
    },
    "phx": {
        "id": 114258,
        "name": "Phoenix Mercury",
        "league": "wnba",
        "record": "29-20",
        "logo": "https://polymarket-upload.s3.us-east-2.amazonaws.com/WNBA Team Logos/PHX.png",
        "abbreviation": "phx",
        "alias": "Mercury",
        "createdAt": "2025-05-14T13:26:25.600459Z",
        "updatedAt": "2026-07-31T15:24:53.442088Z",
        "providerId": 11,
        "color": "#e56020",
    },
    "dal": {
        "id": 114251,
        "name": "Dallas Wings",
        "league": "wnba",
        "record": "11-34",
        "logo": "https://polymarket-upload.s3.us-east-2.amazonaws.com/WNBA Team Logos/DAL.png",
        "abbreviation": "dal",
        "alias": "Wings",
        "createdAt": "2025-05-14T13:26:25.600459Z",
        "updatedAt": "2026-07-31T15:24:51.911586Z",
        "providerId": 7,
        "color": "#c4d600",
    },
    "ind": {
        "id": 114253,
        "name": "Indiana Fever",
        "league": "wnba",
        "record": "30-21",
        "logo": "https://polymarket-upload.s3.us-east-2.amazonaws.com/WNBA Team Logos/IND.png",
        "abbreviation": "ind",
        "alias": "Fever",
        "createdAt": "2025-05-14T13:26:25.600459Z",
        "updatedAt": "2026-07-31T15:24:52.057728Z",
        "providerId": 4,
        "color": "#e6be18",
    },
    "min": {
        "id": 114256,
        "name": "Minnesota Lynx",
        "league": "wnba",
        "record": "36-12",
        "logo": "https://polymarket-upload.s3.us-east-2.amazonaws.com/WNBA Team Logos/MIN.png",
        "abbreviation": "min",
        "alias": "Lynx",
        "createdAt": "2025-05-14T13:26:25.600459Z",
        "updatedAt": "2026-07-31T15:24:52.918033Z",
        "providerId": 10,
        "color": "#266092",
    },
    "sea": {
        "id": 114259,
        "name": "Seattle Storm",
        "league": "wnba",
        "record": "25-23",
        "logo": "https://polymarket-upload.s3.us-east-2.amazonaws.com/WNBA Team Logos/SEA.png",
        "abbreviation": "sea",
        "alias": "Storm",
        "createdAt": "2025-05-14T13:26:25.600459Z",
        "updatedAt": "2026-07-31T15:24:54.064473Z",
        "providerId": 12,
        "color": "#2d5536",
    },
}


def team(code: str, ordering: str) -> dict:
    out = deepcopy(TEAMS[code])
    out["ordering"] = ordering
    return out


def ev(
    eid: str,
    slug: str,
    title: str,
    event_date: str,
    start_time: str,
    game_id: int,
    away: str,
    home: str,
    market_id: str,
    outcomes: str,
    tokens: str,
    question: str,
    game_start: str,
) -> dict:
    return {
        "id": eid,
        "slug": slug,
        "title": title,
        "eventDate": event_date,
        "startTime": start_time,
        "gameId": game_id,
        "teams": [team(away, "away"), team(home, "home")],
        "sport": deepcopy(SPORT),
        "seriesSlug": "wnba",
        "markets": [
            {
                "id": market_id,
                "sportsMarketType": "moneyline",
                "outcomes": outcomes,
                "clobTokenIds": tokens,
                "question": question,
                "slug": slug,
                "gameStartTime": game_start,
                "closed": True,
            }
        ],
    }


PAGES: dict[str, list] = {
    "page_02.json": [
        ev(
            "42695",
            "wnba-atl-conn-2025-09-10",
            "Dream vs. Sun",
            "2025-09-10",
            "2025-09-10T23:00:00Z",
            13002181,
            "atl",
            "conn",
            "591451",
            '["Dream", "Sun"]',
            '["53845089503668430042486319518889510690661745381763320537778286192366398715604", "26946163248994505391709352285269799740226293747955451354952581883505855709375"]',
            "Dream vs. Sun",
            "2025-09-10 23:00:00+00",
        )
    ],
    "page_04.json": [
        ev(
            "42994",
            "wnba-phx-dal-2025-09-11",
            "Mercury vs. Wings",
            "2025-09-11",
            "2025-09-12T00:00:00Z",
            13002183,
            "phx",
            "dal",
            "592451",
            '["Mercury", "Wings"]',
            '["33379823538909842603556995048536655422350350426973180434239513202006675018185", "93881466653774210433442680278890879421094390311243930308749633050193411378063"]',
            "Mercury vs. Wings",
            "2025-09-12 00:00:00+00",
        )
    ],
    "page_05.json": [
        ev(
            "44058",
            "wnba-ind-atl-2025-09-14",
            "Fever vs. Dream",
            "2025-09-14",
            "2025-09-14T19:00:00Z",
            13002200,
            "ind",
            "atl",
            "596311",
            '["Fever", "Dream"]',
            '["102113269077409731745016526645461509151041046396684923210782600930407511636481", "83307629684960395955999697719659301681268518811456239232179164549652744874451"]',
            "Fever vs. Dream",
            "2025-09-14 19:00:00+00",
        )
    ],
    "page_07.json": [
        ev(
            "44868",
            "wnba-atl-ind-2025-09-16",
            "Dream vs. Fever",
            "2025-09-16",
            "2025-09-16T23:30:00Z",
            13002203,
            "atl",
            "ind",
            "598654",
            '["Dream", "Fever"]',
            '["86203955355882190636944683678839701334851320149262240655933362333271031852506", "28767271190372114243042978326834880704104965264635702266253134321494720012148"]',
            "Dream vs. Fever",
            "2025-09-16 23:30:00+00",
        )
    ],
    "page_09.json": [
        ev(
            "45781",
            "wnba-ind-atl-2025-09-18",
            "Fever vs. Dream",
            "2025-09-18",
            "2025-09-18T23:30:00Z",
            13002205,
            "ind",
            "atl",
            "601335",
            '["Fever", "Dream"]',
            '["21787803994318978381360125651678150152132165575395027425094504513676824242695", "97824038013393416011037216391880446128976400095961043280286048531659595899800"]',
            "Fever vs. Dream",
            "2025-09-18 23:30:00+00",
        )
    ],
    "page_11.json": [
        ev(
            "47152",
            "wnba-phx-min-2025-09-21",
            "Mercury vs. Lynx",
            "2025-09-21",
            "2025-09-21T21:00:00Z",
            13002216,
            "phx",
            "min",
            "605225",
            '["Mercury", "Lynx"]',
            '["34268872657544209153932361591684753143602294083335681244659853969389987760576", "108086748336512789986556482924193529079733371396595194755794200106479491505071"]',
            "Mercury vs. Lynx",
            "2025-09-21 21:00:00+00",
        )
    ],
    "page_12.json": [
        ev(
            "48006",
            "wnba-phx-min-2025-09-23",
            "Mercury vs. Lynx",
            "2025-09-23",
            "2025-09-23T23:30:00Z",
            13002217,
            "phx",
            "min",
            "607442",
            '["Mercury", "Lynx"]',
            '["95894713587922685439726960987252691064820786481154954938686727826412643791250", "37522514234235478947672414200084139006854010963023400645247660604546696294387"]',
            "Mercury vs. Lynx",
            "2025-09-23 23:30:00+00",
        )
    ],
    "page_13.json": [
        ev(
            "49653",
            "wnba-min-phx-2025-09-26",
            "Lynx vs. Mercury",
            "2025-09-26",
            "2025-09-27T01:30:00Z",
            13002218,
            "min",
            "phx",
            "612059",
            '["Lynx", "Mercury"]',
            '["3592371190954928455660574857418882481120399077501908254557734386116415192257", "12368376759778547926188460331270364470977413737724624205338406024626907655591"]',
            "Lynx vs. Mercury",
            "2025-09-27 01:30:00+00",
        )
    ],
    "page_14.json": [
        ev(
            "50610",
            "wnba-min-phx-2025-09-28",
            "Lynx vs. Mercury",
            "2025-09-28",
            "2025-09-29T00:00:00Z",
            13002219,
            "min",
            "phx",
            "615529",
            '["Lynx", "Mercury"]',
            '["83613063446396954838907372123391457669629400120565291910051401709731470193909", "11259043941130036399629301314836335510730946613476598005297780420554093024242"]',
            "Lynx vs. Mercury",
            "2025-09-29 00:00:00+00",
        )
    ],
    "page_19.json": [
        ev(
            "433046",
            "wnba-dal-ind-2026-04-30",
            "Dallas Wings vs. Indiana Fever",
            "2026-04-30",
            "2026-04-30T23:00:00Z",
            13002565,
            "dal",
            "ind",
            "2121842",
            '["Dallas Wings", "Indiana Fever"]',
            '["44002319184537728919138734918360955864380221904419020382986626062591754264984", "28661855626561638212802197559106575486600604033032401228708661394340276595619"]',
            "Dallas Wings vs. Indiana Fever",
            "2026-04-30 23:00:00+00",
        ),
        ev(
            "436137",
            "wnba-dal-ind-2026-05-09",
            "Dallas Wings vs. Indiana Fever",
            "2026-05-09",
            "2026-05-09T17:00:00Z",
            13002230,
            "dal",
            "ind",
            "2128834",
            '["Dallas Wings", "Indiana Fever"]',
            '["24275449520323670290506147040042339003071172527695555982842078326206786260810", "102894435103610763995846660598849120848276917768189159528077930026063865171366"]',
            "Dallas Wings vs. Indiana Fever",
            "2026-05-09 17:00:00+00",
        ),
    ],
    "page_23.json": [
        ev(
            "436139",
            "wnba-sea-conn-2026-05-10",
            "Seattle Storm vs. Connecticut Sun",
            "2026-05-10",
            "2026-05-10T17:00:00Z",
            13002232,
            "sea",
            "conn",
            "2128836",
            '["Seattle Storm", "Connecticut Sun"]',
            '["44954261069205557078168589926963119814738005303169707584718413382439590136144", "90690081309426146373313168569368450637669359079744792181334651665871703094965"]',
            "Seattle Storm vs. Connecticut Sun",
            "2026-05-10 17:00:00+00",
        )
    ],
}


def main() -> None:
    for name, events in PAGES.items():
        path = ROOT / name
        path.write_text(json.dumps(events, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {name} events={len(events)}")
    for name in (
        "page_15.json",
        "page_16.json",
        "page_17.json",
        "page_18.json",
        "page_20.json",
        "page_21.json",
        "page_22.json",
    ):
        path = ROOT / name
        path.write_text("[]\n", encoding="utf-8")
        print(f"wrote {name} events=0")


if __name__ == "__main__":
    main()
