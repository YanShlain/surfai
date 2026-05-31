import random

from app.infrastructure.retry_policy import compute_backoff_sleep


def test_backoff_within_bounds():
    rng = random.Random(0)
    for attempt in range(1, 6):
        sleep = compute_backoff_sleep(
            attempt,
            base_seconds=0.5,
            max_seconds=30,
            rng=rng,
        )
        max_delay = min(0.5 * (2 ** (attempt - 1)), 30)
        assert 0 <= sleep <= max_delay


def test_backoff_respects_max():
    rng = random.Random(1)
    sleep = compute_backoff_sleep(10, base_seconds=0.5, max_seconds=2, rng=rng)
    assert 0 <= sleep <= 2
