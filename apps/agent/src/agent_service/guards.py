"""Live-demo protection: per-IP rate limit and a daily token budget."""

import os
import sqlite3
import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window per-IP limit for the chat endpoint (in-memory, single process)."""

    def __init__(self, max_per_hour: int | None = None):
        self.max_per_hour = max_per_hour or int(os.environ.get("CHAT_RATE_LIMIT_PER_HOUR", "30"))
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        window = self._hits[ip]
        while window and now - window[0] > 3600:
            window.popleft()
        if len(window) >= self.max_per_hour:
            return False
        window.append(now)
        return True


def daily_tokens_used(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS used
           FROM runs WHERE started_at >= datetime('now', 'start of day')"""
    ).fetchone()
    return int(row["used"])


def daily_budget() -> int:
    return int(os.environ.get("DAILY_TOKEN_BUDGET", "2000000"))


def budget_exceeded(conn: sqlite3.Connection) -> bool:
    return daily_tokens_used(conn) >= daily_budget()
