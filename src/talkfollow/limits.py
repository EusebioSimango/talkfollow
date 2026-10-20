"""In-memory cache and rate limits that keep the public demo inside its SerpApi budget."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from datetime import date

CACHE_SECONDS = 6 * 60 * 60
CACHE_MAX_ENTRIES = 200
HOUR_SECONDS = 60 * 60


class LimitReached(Exception):
    """A demo limit was hit; the message is written for the visitor."""


class BriefingCache:
    """Rendered briefings by query, kept for a few hours so repeat visits cost no searches."""

    def __init__(
        self,
        *,
        ttl_seconds: float = CACHE_SECONDS,
        max_entries: int = CACHE_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if self._clock() >= expires_at:
                del self._entries[key]
                return None
            return value

    def put(self, key: str, value: str) -> None:
        with self._lock:
            self._entries[key] = (self._clock() + self._ttl, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)


class DemoLimits:
    """A daily cap for the whole demo and an hourly cap per visitor.

    Visitors are tracked by a salted hash of their IP, held only in memory, so no IP is stored.
    """

    def __init__(
        self,
        *,
        daily_briefings: int,
        briefings_per_visitor_per_hour: int,
        clock: Callable[[], float] = time.monotonic,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._daily_limit = daily_briefings
        self._hourly_limit = briefings_per_visitor_per_hour
        self._clock = clock
        self._today = today
        self._salt = secrets.token_bytes(16)
        self._lock = threading.Lock()
        self._day = today()
        self._used_today = 0
        self._visits: dict[str, deque[float]] = {}

    def reserve(self, ip: str) -> None:
        """Count one new briefing for this visitor, or raise ``LimitReached``."""
        with self._lock:
            self._start_new_day_if_needed()
            if self._used_today >= self._daily_limit:
                raise LimitReached(
                    f"The demo has used today's {self._daily_limit} live briefings. "
                    "Please try again tomorrow, or run TalkFollow with your own free SerpApi key."
                )
            now = self._clock()
            self._forget_visits_before(now - HOUR_SECONDS)
            visits = self._visits.setdefault(self._visitor_id(ip), deque())
            if len(visits) >= self._hourly_limit:
                raise LimitReached(
                    f"You have made {self._hourly_limit} live briefings in the last hour. "
                    "Please try again later, or run TalkFollow with your own free SerpApi key."
                )
            visits.append(now)
            self._used_today += 1

    def _start_new_day_if_needed(self) -> None:
        today = self._today()
        if today != self._day:
            self._day = today
            self._used_today = 0

    def _forget_visits_before(self, cutoff: float) -> None:
        for visitor, visits in list(self._visits.items()):
            while visits and visits[0] <= cutoff:
                visits.popleft()
            if not visits:
                del self._visits[visitor]

    def _visitor_id(self, ip: str) -> str:
        return hashlib.sha256(self._salt + ip.encode()).hexdigest()
