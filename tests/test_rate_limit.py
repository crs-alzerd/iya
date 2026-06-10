from iya_bot.application.rate_limit import SlidingWindowRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_limit_then_rejects() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_events=3, window_seconds=60, clock=clock)

    assert limiter.check(1).allowed
    assert limiter.check(1).allowed
    assert limiter.check(1).allowed
    decision = limiter.check(1)
    assert not decision.allowed
    assert decision.retry_after_seconds > 0


def test_warning_only_on_first_rejection() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_events=1, window_seconds=60, clock=clock)

    assert limiter.check(1).allowed
    first = limiter.check(1)
    second = limiter.check(1)
    assert first.first_rejection
    assert not second.first_rejection


def test_window_slides_and_resets() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_events=2, window_seconds=60, clock=clock)

    assert limiter.check(1).allowed
    assert limiter.check(1).allowed
    assert not limiter.check(1).allowed

    clock.now += 61
    decision = limiter.check(1)
    assert decision.allowed
    # После успешного хода флаг «уже предупреждали» сброшен.
    assert limiter.check(1).allowed
    assert limiter.check(1).first_rejection


def test_users_are_independent() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_events=1, window_seconds=60, clock=clock)

    assert limiter.check(1).allowed
    assert not limiter.check(1).allowed
    assert limiter.check(2).allowed


def test_prune_drops_stale_users() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_events=5, window_seconds=60, clock=clock)
    limiter.check(1)
    limiter.check(2)
    clock.now += 120
    limiter.prune()
    assert limiter._events == {}
