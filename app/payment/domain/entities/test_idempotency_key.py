from datetime import datetime, timedelta

from app.payment.domain.entities.idempotency_key import IdempotencyKey
from app.payment.domain.states import KeyState

T0 = datetime(2026, 1, 1, 12, 0, 0)


def make_key(state=KeyState.IN_FLIGHT, created_at=T0, started_at=T0):
    return IdempotencyKey(
        key="abc", state=state, request_hash="h",
        created_at=created_at, started_at=started_at,
    )


# is_terminal — "does this key already have a final answer?"

def test_succeeded_and_failed_are_terminal():
    assert make_key(state=KeyState.SUCCEEDED).is_terminal()
    assert make_key(state=KeyState.FAILED).is_terminal()


def test_in_flight_is_not_terminal():
    assert not make_key(state=KeyState.IN_FLIGHT).is_terminal()


# is_expired — "is this key past its 24h window?" (measured from created_at)

def test_key_older_than_ttl_is_expired():
    key = make_key(created_at=T0)
    assert key.is_expired(now=T0 + timedelta(hours=25), ttl=timedelta(hours=24))


def test_key_within_ttl_is_not_expired():
    key = make_key(created_at=T0)
    assert not key.is_expired(now=T0 + timedelta(hours=23), ttl=timedelta(hours=24))


# is_stale — "is an in-flight key stuck? (owner presumed dead)" (measured from started_at)

def test_in_flight_older_than_timeout_is_stale():
    key = make_key(state=KeyState.IN_FLIGHT, started_at=T0)
    assert key.is_stale(now=T0 + timedelta(minutes=5), timeout=timedelta(minutes=1))


def test_fresh_in_flight_is_not_stale():
    key = make_key(state=KeyState.IN_FLIGHT, started_at=T0)
    assert not key.is_stale(now=T0 + timedelta(seconds=10), timeout=timedelta(minutes=1))


def test_terminal_key_is_never_stale():
    # a finished key can't be "stuck" — stale only means an IN_FLIGHT that never finished
    key = make_key(state=KeyState.SUCCEEDED, started_at=T0)
    assert not key.is_stale(now=T0 + timedelta(hours=1), timeout=timedelta(minutes=1))
