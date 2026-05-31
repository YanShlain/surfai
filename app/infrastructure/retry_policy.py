import random


def compute_backoff_sleep(
    attempt: int,
    *,
    base_seconds: float,
    max_seconds: float,
    rng: random.Random | None = None,
) -> float:
    """Return jittered exponential backoff sleep for a timeout retry attempt.

    Args:
        attempt: 1-based attempt number that just failed.
        base_seconds: Initial backoff base before exponential growth.
        max_seconds: Upper cap on the backoff delay before jitter.
        rng: Optional random source for tests; defaults to ``random`` module.

    Returns:
        float: Seconds to sleep before the next retry, uniformly jittered in [0, delay].
    """
    rng = rng or random
    delay = min(base_seconds * (2 ** (attempt - 1)), max_seconds)
    return rng.uniform(0, delay)
