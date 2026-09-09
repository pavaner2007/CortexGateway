"""
Cortex Gateway — Retry & Exponential Backoff Policy (Phase 4).

Handles calculation of exponential backoff delays with jitter and async sleep.
"""

from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, Optional


class RetryPolicy:
    """
    Configurable exponential backoff retry policy.

    Delay formula:
      delay = min(max_delay, base_delay * (2 ** attempt)) + optional_jitter
    """

    def __init__(
        self,
        max_retries: int = 2,
        base_delay_seconds: float = 0.25,
        max_delay_seconds: float = 2.0,
        jitter: bool = True,
        sleep_func: Optional[Callable[[float], Awaitable[None]]] = None,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.jitter = jitter
        self._sleep_func = sleep_func or asyncio.sleep

    def compute_delay(self, retry_attempt: int) -> float:
        """
        Compute delay in seconds for a given retry attempt index (0-indexed).

        Attempt 0 (1st retry): base_delay * (2^0) = base_delay
        Attempt 1 (2nd retry): base_delay * (2^1) = base_delay * 2
        ...
        """
        raw_delay = self.base_delay_seconds * (2 ** retry_attempt)
        capped_delay = min(self.max_delay_seconds, raw_delay)

        if self.jitter:
            # Add randomized jitter up to 15% of capped delay
            jitter_amount = random.uniform(0.0, 0.15 * capped_delay)
            return round(min(self.max_delay_seconds, capped_delay + jitter_amount), 4)

        return round(capped_delay, 4)

    async def sleep(self, delay: float) -> None:
        """Asynchronously sleep for computed duration."""
        if delay > 0:
            await self._sleep_func(delay)
