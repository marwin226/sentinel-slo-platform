"""Deterministic-friendly fault injection used to simulate a bad release.

FAULT_ERROR_RATE=0.2  -> ~20% of user requests return 503
FAULT_LATENCY_MS=400  -> every user request gets +400ms (with +/-20% jitter)

Never enabled in the stable overlay; the `bad-release` demo turns it on for a canary.
"""

from __future__ import annotations

import random


class FaultInjector:
    def __init__(self, error_rate: float = 0.0, latency_ms: float = 0.0, seed: int | None = None):
        if not 0.0 <= error_rate <= 1.0:
            raise ValueError("FAULT_ERROR_RATE must be within [0, 1]")
        if latency_ms < 0:
            raise ValueError("FAULT_LATENCY_MS must be >= 0")
        self.error_rate = error_rate
        self.latency_ms = latency_ms
        self._rng = random.Random(seed)  # noqa: S311 - simulation, not crypto

    @property
    def enabled(self) -> bool:
        return self.error_rate > 0 or self.latency_ms > 0

    def should_fail(self) -> bool:
        return self.error_rate > 0 and self._rng.random() < self.error_rate

    def latency_seconds(self) -> float:
        if self.latency_ms <= 0:
            return 0.0
        jitter = self._rng.uniform(0.8, 1.2)
        return (self.latency_ms * jitter) / 1000.0
