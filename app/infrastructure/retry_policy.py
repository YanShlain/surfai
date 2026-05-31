import random


def compute_backoff_sleep(
    attempt: int,
    *,
    base_seconds: float,
    max_seconds: float,
    rng: random.Random | None = None,
) -> float:
    """Return jittered backoff sleep for the given 1-based attempt after a timeout."""
    rng = rng or random
    delay = min(base_seconds * (2 ** (attempt - 1)), max_seconds)
    return rng.uniform(0, delay)
