import pytest

from app.faults import FaultInjector


def test_disabled_by_default():
    f = FaultInjector()
    assert not f.enabled
    assert not any(f.should_fail() for _ in range(1000))
    assert f.latency_seconds() == 0.0


def test_error_rate_is_respected():
    f = FaultInjector(error_rate=0.2, seed=42)
    failures = sum(f.should_fail() for _ in range(10_000))
    assert 1800 < failures < 2200


def test_latency_has_bounded_jitter():
    f = FaultInjector(latency_ms=400, seed=1)
    samples = [f.latency_seconds() for _ in range(500)]
    assert min(samples) >= 0.32 and max(samples) <= 0.48


@pytest.mark.parametrize("rate", [-0.1, 1.5])
def test_rejects_invalid_rate(rate):
    with pytest.raises(ValueError):
        FaultInjector(error_rate=rate)
