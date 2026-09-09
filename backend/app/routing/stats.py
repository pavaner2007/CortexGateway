"""
Cortex Gateway — Provider Runtime Statistics Tracker (Phase 3).

Tracks in-memory rolling statistics per (provider, model) pair:
- Request counts (total, success, failure)
- Rolling success rate (last N requests)
- Exponential Moving Average (EMA) and last observed latency
- Health state transitions

Thread-safe and async-safe.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple


@dataclass
class ModelStats:
    """Statistics for a specific (provider, model) target."""

    provider: str
    model: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_latency_ms: Optional[float] = None
    average_latency_ms: Optional[float] = None
    # Rolling window of last N request outcomes (True=success, False=fail)
    _recent_outcomes: Deque[bool] = field(default_factory=lambda: deque(maxlen=50))
    # Rolling window of last N latency measurements in ms
    _recent_latencies: Deque[float] = field(default_factory=lambda: deque(maxlen=50))

    @property
    def success_rate(self) -> float:
        """Rolling success rate in [0.0, 1.0]. Defaults to 1.0 if no requests."""
        if not self._recent_outcomes:
            return 1.0
        return sum(1 for o in self._recent_outcomes if o) / len(self._recent_outcomes)

    @property
    def latency_ms(self) -> Optional[float]:
        """Average latency over recent window, or last observed."""
        if self._recent_latencies:
            return sum(self._recent_latencies) / len(self._recent_latencies)
        return self.last_latency_ms

    def record_success(self, latency_ms: float) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.last_latency_ms = latency_ms
        self._recent_outcomes.append(True)
        self._recent_latencies.append(latency_ms)
        if self.average_latency_ms is None:
            self.average_latency_ms = latency_ms
        else:
            # EMA with alpha=0.2
            self.average_latency_ms = (0.2 * latency_ms) + (0.8 * self.average_latency_ms)

    def record_failure(self) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        self._recent_outcomes.append(False)


class ProviderStatsTracker:
    """In-memory thread-safe statistics tracker."""

    def __init__(self) -> None:
        self._stats: Dict[Tuple[str, str], ModelStats] = {}
        self._lock = threading.Lock()

    def _key(self, provider: str, model: str) -> Tuple[str, str]:
        return (provider.lower().strip(), model.strip())

    def get_or_create(self, provider: str, model: str) -> ModelStats:
        key = self._key(provider, model)
        with self._lock:
            if key not in self._stats:
                self._stats[key] = ModelStats(provider=key[0], model=key[1])
            return self._stats[key]

    def record_success(self, provider: str, model: str, latency_ms: float) -> None:
        stats = self.get_or_create(provider, model)
        with self._lock:
            stats.record_success(latency_ms)

    def record_failure(self, provider: str, model: str) -> None:
        stats = self.get_or_create(provider, model)
        with self._lock:
            stats.record_failure()

    def get_stats(self, provider: str, model: str) -> Optional[ModelStats]:
        key = self._key(provider, model)
        with self._lock:
            return self._stats.get(key)

    def reset(self) -> None:
        """Reset all tracked runtime statistics (useful for tests)."""
        with self._lock:
            self._stats.clear()
