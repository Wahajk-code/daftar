"""The limiter on its own: windows, refunds, atomicity, bounded memory. API-level policy tests are in tests/api."""

import threading
from datetime import UTC, datetime

import pytest

from app.core.errors import RateLimitedError
from app.core.rate_limit import DEFAULT_POLICIES, MAX_KEY_LENGTH, Policy, RateLimiter, build_policies
from tests.support.clock import FakeClock


def limiter_for(clock: FakeClock, limit: int = 3, window: int = 60, **kwargs: int) -> RateLimiter:
    return RateLimiter(clock, {"p": Policy("p", limit, window), "q": Policy("q", 2, window)}, **kwargs)


@pytest.fixture
def clk() -> FakeClock:
    return FakeClock(datetime(2026, 10, 12, 9, 0, tzinfo=UTC))


# Policies as data ----------------------------------------------------------------------------------------------------


def test_defaults_match_the_architecture_table() -> None:
    policies = build_policies({})
    assert (policies["login_strict"].limit, policies["login_strict"].window_seconds) == (5, 900)
    assert (policies["login_loose"].limit, policies["login_loose"].window_seconds) == (30, 3600)
    assert (policies["login_ip"].limit, policies["login_ip"].window_seconds) == (20, 900)
    assert (policies["forgot_email"].limit, policies["forgot_email"].window_seconds) == (3, 3600)
    assert (policies["forgot_ip"].limit, policies["forgot_ip"].window_seconds) == (10, 3600)
    assert (policies["token_confirm_ip"].limit, policies["token_confirm_ip"].window_seconds) == (10, 900)
    assert (policies["admin_target"].limit, policies["admin_target"].window_seconds) == (3, 3600)
    assert (policies["upload_user"].limit, policies["upload_user"].window_seconds) == (30, 3600)
    assert (policies["export_user"].limit, policies["export_user"].window_seconds) == (10, 3600)
    assert (policies["user_all"].limit, policies["user_all"].window_seconds) == (300, 60)
    assert set(policies) == set(DEFAULT_POLICIES)


def test_every_number_can_be_overridden_by_setting() -> None:
    policies = build_policies({"login_strict": "2/30"})
    assert (policies["login_strict"].limit, policies["login_strict"].window_seconds) == (2, 30)
    assert policies["login_loose"].limit == 30


@pytest.mark.parametrize("overrides", [{"nonsense": "1/1"}, {"login_strict": "0/10"}, {"login_strict": "5/0"}])
def test_bad_overrides_are_refused_at_start_up(overrides: dict[str, str]) -> None:
    with pytest.raises(ValueError, match=r"rate-limit|unknown"):
        build_policies(overrides)


# Windows -------------------------------------------------------------------------------------------------------------


def test_the_limit_is_reached_then_refused_with_a_wait(clk: FakeClock) -> None:
    limiter = limiter_for(clk)
    for _ in range(3):
        limiter.hit(("p", "k"))
    with pytest.raises(RateLimitedError) as caught:
        limiter.hit(("p", "k"))
    assert caught.value.headers == {"Retry-After": "60"}
    assert caught.value.status_code == 429


def test_the_window_slides_rather_than_resetting(clk: FakeClock) -> None:
    limiter = limiter_for(clk)
    limiter.hit(("p", "k"))  # t = 0
    clk.advance(seconds=30)
    limiter.hit(("p", "k"))  # t = 30
    limiter.hit(("p", "k"))  # t = 30
    with pytest.raises(RateLimitedError) as caught:
        limiter.hit(("p", "k"))
    assert caught.value.retry_after_seconds == 30  # until the first hit leaves the window
    clk.advance(seconds=30)  # t = 60: the t = 0 hit has expired, the two at t = 30 have not
    limiter.hit(("p", "k"))
    with pytest.raises(RateLimitedError) as again:
        limiter.hit(("p", "k"))
    assert again.value.retry_after_seconds == 30
    clk.advance(seconds=30)
    limiter.hit(("p", "k"))


def test_keys_are_independent(clk: FakeClock) -> None:
    limiter = limiter_for(clk, limit=1)
    limiter.hit(("p", "a"))
    limiter.hit(("p", "b"))
    with pytest.raises(RateLimitedError):
        limiter.hit(("p", "a"))


def test_a_refund_gives_the_attempt_back(clk: FakeClock) -> None:
    limiter = limiter_for(clk, limit=1)
    ticket = limiter.hit(("p", "k"))
    limiter.refund(ticket)
    limiter.hit(("p", "k"))
    limiter.refund(ticket)  # refunding twice, or after expiry, is harmless
    clk.advance(seconds=120)
    limiter.refund(ticket)


def test_several_checks_are_one_atomic_step(clk: FakeClock) -> None:
    limiter = limiter_for(clk, limit=5)  # "q" allows only 2
    limiter.hit(("p", "k"), ("q", "k"))
    limiter.hit(("p", "k"), ("q", "k"))
    with pytest.raises(RateLimitedError):
        limiter.hit(("p", "k"), ("q", "k"))
    # The refused attempt counted against "p" for nobody: three more "p" hits still fit.
    for _ in range(3):
        limiter.hit(("p", "k"))


# Memory --------------------------------------------------------------------------------------------------------------


def test_a_very_long_key_is_hashed_not_stored(clk: FakeClock) -> None:
    limiter = limiter_for(clk, limit=1)
    long_a = "a" * (MAX_KEY_LENGTH + 500)
    long_b = "a" * (MAX_KEY_LENGTH + 499) + "b"
    limiter.hit(("p", long_a))
    limiter.hit(("p", long_b))  # a different long key is a different counter
    with pytest.raises(RateLimitedError):
        limiter.hit(("p", long_a))


def test_junk_keys_cannot_flush_a_counter_near_its_limit(clk: FakeClock) -> None:
    limiter = RateLimiter(clk, {"p": Policy("p", 5, 3600)}, max_keys=100, evict_batch=20)
    for _ in range(4):
        limiter.hit(("p", "victim"))
    for number in range(5_000):
        limiter.hit(("p", f"junk-{number}"))
    assert limiter.size() <= 100
    limiter.hit(("p", "victim"))  # the fifth hit is still allowed
    with pytest.raises(RateLimitedError):
        limiter.hit(("p", "victim"))  # and the counter survived the flood, so the sixth is refused


def test_expired_entries_are_dropped_before_live_ones(clk: FakeClock) -> None:
    limiter = RateLimiter(clk, {"p": Policy("p", 5, 60)}, max_keys=50, evict_batch=10)
    for number in range(49):
        limiter.hit(("p", f"old-{number}"))
    limiter.hit(("p", "live"))
    clk.advance(seconds=61)
    limiter.hit(("p", "live"))
    for number in range(40):
        limiter.hit(("p", f"new-{number}"))
    assert limiter.size() <= 50


def test_the_eviction_batch_must_leave_room() -> None:
    with pytest.raises(ValueError, match="evict_batch"):
        RateLimiter(FakeClock(datetime(2026, 1, 1, tzinfo=UTC)), {}, max_keys=10, evict_batch=10)


# Parallel ------------------------------------------------------------------------------------------------------------


def test_a_burst_of_parallel_hits_cannot_exceed_the_limit(clk: FakeClock) -> None:
    limiter = limiter_for(clk, limit=5)
    outcomes: list[bool] = []
    barrier = threading.Barrier(50)

    def attempt() -> None:
        barrier.wait()
        try:
            limiter.hit(("p", "k"))
            outcomes.append(True)
        except RateLimitedError:
            outcomes.append(False)

    threads = [threading.Thread(target=attempt) for _ in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes.count(True) == 5
    assert outcomes.count(False) == 45
