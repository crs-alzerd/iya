from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: float = 0.0
    # Чтобы не спамить отказами: предупреждение шлём только на первом превышении окна.
    first_rejection: bool = False


class SlidingWindowRateLimiter:
    """Скользящее окно в памяти: не больше max_events за window_seconds на пользователя.

    Состояние живёт в процессе — при рестарте сбрасывается, для одного polling-процесса
    этого достаточно. Часы инжектируются ради тестов.
    """

    def __init__(
        self,
        max_events: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_events = max(1, max_events)
        self._window_seconds = max(1.0, window_seconds)
        self._clock = clock
        self._events: dict[int, deque[float]] = {}
        self._rejected_in_window: set[int] = set()

    def check(self, user_id: int) -> RateLimitDecision:
        now = self._clock()
        events = self._events.setdefault(user_id, deque())
        cutoff = now - self._window_seconds
        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) < self._max_events:
            events.append(now)
            self._rejected_in_window.discard(user_id)
            return RateLimitDecision(allowed=True)

        retry_after = max(0.0, events[0] + self._window_seconds - now)
        first = user_id not in self._rejected_in_window
        self._rejected_in_window.add(user_id)
        return RateLimitDecision(allowed=False, retry_after_seconds=retry_after, first_rejection=first)

    def prune(self) -> None:
        """Убрать пользователей без событий в окне, чтобы словарь не рос бесконечно."""
        cutoff = self._clock() - self._window_seconds
        stale = [user_id for user_id, events in self._events.items() if not events or events[-1] <= cutoff]
        for user_id in stale:
            del self._events[user_id]
            self._rejected_in_window.discard(user_id)
