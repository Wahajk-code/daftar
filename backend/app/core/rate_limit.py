"""Named rate-limit policies, held in memory. A sliding window per key; one lock; one API worker.

Limits throttle, they never lock an account. An attempt is counted before the expensive work and refunded on success.
Every number is a setting (RATE_LIMIT_OVERRIDES). See docs/architecture.md section 9a."""

import hashlib
import math
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from app.core.clock import Clock
from app.core.errors import RateLimitedError

MAX_KEY_LENGTH: Final = 256
DEFAULT_EVICTION_BATCH: Final = 256  # keys dropped at once when the table is full, fewest hits first


@dataclass(frozen=True)
class Policy:
    name: str
    limit: int
    window_seconds: int


DEFAULT_POLICIES: Final[dict[str, tuple[int, int]]] = {
    "login_strict": (5, 15 * 60),  # email and IP together
    "login_loose": (30, 60 * 60),  # email alone
    "login_ip": (20, 15 * 60),  # IP alone
    "forgot_email": (3, 60 * 60),
    "forgot_ip": (10, 60 * 60),
    "token_confirm_ip": (10, 15 * 60),  # reset confirm and invite accept
    "admin_target": (3, 60 * 60),  # Admin-triggered reset or invite resend, per target
    "reauth_user": (5, 15 * 60),  # password re-entry for a sensitive change
    "upload_user": (30, 60 * 60),
    "export_user": (10, 60 * 60),
    "user_all": (300, 60),  # safety net on every authenticated route
}


def build_policies(overrides: dict[str, str]) -> dict[str, Policy]:
    """Defaults, then any override written as "limit/window_seconds"."""
    unknown = set(overrides) - set(DEFAULT_POLICIES)
    if unknown:
        raise ValueError(f"unknown rate-limit policies: {sorted(unknown)}")
    policies: dict[str, Policy] = {}
    for name, (default_limit, default_window) in DEFAULT_POLICIES.items():
        limit, window = default_limit, default_window
        if name in overrides:
            raw_limit, _, raw_window = overrides[name].partition("/")
            limit, window = int(raw_limit), int(raw_window)
        if limit < 1 or window < 1:
            raise ValueError(f"rate-limit policy {name} needs a positive limit and window")
        policies[name] = Policy(name, limit, window)
    return policies


@dataclass(frozen=True)
class Ticket:
    """What a successful hit leaves behind, so the hit can be refunded."""

    entries: tuple[tuple[str, str, datetime], ...]  # policy name, key, timestamp


class RateLimiter:
    def __init__(
        self,
        clock: Clock,
        policies: dict[str, Policy],
        *,
        max_keys: int = 50_000,
        evict_batch: int = DEFAULT_EVICTION_BATCH,
    ) -> None:
        if not 0 < evict_batch < max_keys:
            raise ValueError("evict_batch must be positive and smaller than max_keys")
        self._clock = clock
        self._policies = policies
        self._max_keys = max_keys
        self._evict_batch = evict_batch
        self._lock = threading.Lock()
        self._hits: dict[tuple[str, str], deque[datetime]] = {}

    @staticmethod
    def _bounded(key: str) -> str:
        return key if len(key) <= MAX_KEY_LENGTH else "h:" + hashlib.sha256(key.encode()).hexdigest()

    def hit(self, *checks: tuple[str, str]) -> Ticket:
        """Count one attempt against each (policy, key) pair, or raise RateLimitedError and count none of them.

        The check and the count are one locked step, so a burst of parallel requests cannot all pass the check before
        the first is recorded.
        """
        now = self._clock.now()
        resolved = [(self._policies[name], self._bounded(key)) for name, key in checks]
        with self._lock:
            retry_after = 0
            for policy, key in resolved:
                window = self._window(policy, key, now)
                if window is not None and len(window) >= policy.limit:
                    wait = window[0] + timedelta(seconds=policy.window_seconds) - now
                    retry_after = max(retry_after, math.ceil(wait.total_seconds()))
            if retry_after:
                raise RateLimitedError(
                    "Too many attempts. Wait a little and try again.", retry_after_seconds=retry_after
                )
            for policy, key in resolved:
                if (policy.name, key) not in self._hits:
                    self._make_room(now)
                    self._hits[(policy.name, key)] = deque()
                self._hits[(policy.name, key)].append(now)
            return Ticket(tuple((policy.name, key, now) for policy, key in resolved))

    def refund(self, ticket: Ticket) -> None:
        with self._lock:
            for name, key, stamp in ticket.entries:
                window = self._hits.get((name, key))
                if window is None:
                    continue
                try:
                    window.remove(stamp)
                except ValueError:
                    continue
                if not window:
                    del self._hits[(name, key)]

    def _window(self, policy: Policy, key: str, now: datetime) -> deque[datetime] | None:
        window = self._hits.get((policy.name, key))
        if window is None:
            return None
        cutoff = now - timedelta(seconds=policy.window_seconds)
        while window and window[0] <= cutoff:
            window.popleft()
        if not window:
            del self._hits[(policy.name, key)]
            return None
        return window

    def _make_room(self, now: datetime) -> None:
        """Keep memory bounded. Expired entries go first; if still full, the keys with the fewest hits go, so a counter
        near its limit is never the one lost and junk keys cannot flush a victim's counter."""
        if len(self._hits) < self._max_keys:
            return
        for name, key in list(self._hits):
            self._window(self._policies[name], key, now)
        if len(self._hits) < self._max_keys:
            return
        by_hits = sorted(self._hits, key=lambda k: (len(self._hits[k]), self._hits[k][-1]))
        for victim in by_hits[: self._evict_batch]:
            del self._hits[victim]

    def size(self) -> int:
        with self._lock:
            return len(self._hits)
