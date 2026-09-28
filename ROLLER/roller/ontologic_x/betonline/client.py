"""Public BetOnline offering client. Reads the site header from the NBA page. Does not log in."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from roller.ontologic_x.betonline import SOURCE_URL

API_ORIGIN = "https://api-offering.betonline.ag"
LEAGUE_PATH = "/api/offering/Sports/offering-by-league"
EVENT_PATH = "/api/offering/sports/get-event"
LINKED_PATH = "/api/offering/sports/get-linked-events"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
_GSETTING = re.compile(r"""data-gsetting\s*=\s*["']([^"']+)["']""", re.I)
BLOCKED_STATUS = {401, 403, 429}


class CollectionBlocked(Exception):
    """The public page or offering host refused the request. Do not retry aggressively."""

    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "COLLECTION_BLOCKED"
        super().__init__(f"COLLECTION_BLOCKED {status}")


class CollectionFailed(Exception):
    """The request failed after the bounded retry budget."""

    def __init__(self, detail: str) -> None:
        self.reason = "COLLECTION_FAILED"
        self.detail = detail
        super().__init__(detail)


class Client:
    def __init__(self, timeout: float = 20, retries: int = 2, sleep=time.sleep) -> None:
        self.timeout = timeout
        self.retries = retries
        self._sleep = sleep
        self._gsetting: str | None = None
        self._page_read = False

    def league(self, period: int = 0) -> dict:
        return self._post(
            LEAGUE_PATH,
            {"Sport": "Basketball", "League": "NBA", "ScheduleText": None, "Period": period, "filterTime": 0},
        )

    def event(self, game_id: int) -> dict:
        return self._post(
            EVENT_PATH,
            {"Sport": "Basketball", "League": "NBA", "GameId": game_id, "Period": 0},
        )

    def linked_events(self, game_id: int) -> list | dict:
        """Same event identity the public event page posts. An empty list means no linked periods."""
        return self._post(
            LINKED_PATH,
            {"sport": "basketball", "league": "nba", "gameID": int(game_id), "scheduleText": None},
        )

    def _post(self, path: str, body: dict) -> dict | list:
        gsetting = self._site_header()
        status, payload = self._send(
            "POST",
            f"{API_ORIGIN}{path}",
            body,
            {
                "content-type": "application/json",
                "accept": "application/json",
                "utc-offset": "0",
                "gsetting": gsetting,
            },
        )
        if status in BLOCKED_STATUS:
            raise CollectionBlocked(status)
        if status != 200 or not isinstance(payload, (dict, list)):
            raise CollectionFailed(f"HTTP_{status}")
        if isinstance(payload, dict) and payload.get("IsError") and not payload.get("GameOffering") and not payload.get("EventOffering"):
            raise CollectionFailed(str(payload.get("ModelErrorMessage") or payload.get("ErrorKind") or "OFFERING_ERROR"))
        return payload

    def _site_header(self) -> str:
        if self._gsetting and self._page_read:
            return self._gsetting
        status, payload = self._send("GET", SOURCE_URL, None, {"accept": "text/html"})
        self._page_read = True
        if status in BLOCKED_STATUS:
            raise CollectionBlocked(status)
        if status != 200 or not isinstance(payload, str):
            raise CollectionFailed(f"PAGE_HTTP_{status}")
        found = _GSETTING.search(payload)
        if found is None:
            raise CollectionFailed("GSETTING_ABSENT")
        self._gsetting = found.group(1)
        return self._gsetting

    def _send(self, method: str, url: str, body: dict | None, headers: dict) -> tuple[int, object]:
        attempt = 0
        while True:
            try:
                status, raw = self._once(method, url, body, headers)
            except (TimeoutError, urllib.error.URLError, ConnectionError) as exc:
                if attempt >= self.retries:
                    raise CollectionFailed(type(exc).__name__) from exc
                attempt += 1
                self._sleep(min(8, 2**attempt))
                continue
            if status in BLOCKED_STATUS:
                return status, raw
            if status >= 500 and attempt < self.retries:
                attempt += 1
                self._sleep(min(8, 2**attempt))
                continue
            return status, raw

    def _once(self, method: str, url: str, body: dict | None, headers: dict) -> tuple[int, object]:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            url,
            data=data,
            headers={"user-agent": USER_AGENT, **headers},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = int(exc.code)
        if method == "GET":
            return status, raw.decode("utf-8", errors="replace")
        try:
            return status, json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise CollectionFailed("OFFERING_SHAPE") from exc
