"""
recover_stale — observables (fake reader + fake driver):

  N stale payments -> driver re-drives each with its OWN key; tally by outcome
  cutoff passed to the reader == now - recovery_timeout
  no stale payments -> processed 0, nothing driven

We fake the driver (scripted DriveOutcomes) — its internals are tested in
drive_payment. Here we test the orchestration: sweep -> drive-each -> tally.
"""

from datetime import datetime

from app.config import Config
from app.payment.domain.entities.payment import Payment
from app.payment.domain.states import PaymentStatus
from app.payment.usecases.drive_payment.dtos import DriveOutcome, DriveResult
from app.payment.usecases.recover_stale.service import RecoverStale

T0 = datetime(2026, 1, 1, 12, 0, 0)


class FakeReader:
    def __init__(self, payments):
        self._payments = payments
        self.cutoff = None

    def stale_in_flight(self, cutoff):
        self.cutoff = cutoff
        return self._payments


class FakeDriver:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = []

    def execute(self, inp):
        self.calls.append(inp)
        return DriveResult(self._outcomes.pop(0))


class FakeClock:
    def __init__(self, now):
        self._now = now

    def now(self):
        return self._now


def a_payment(payment_id, key):
    return Payment(
        id=payment_id, idempotency_key=key, processor_key="pk_" + payment_id,
        amount=1000, currency="USD", user_id="u1",
        status=PaymentStatus.PENDING, created_at=T0,
    )


def test_re_drives_each_stale_payment_and_tallies():
    payments = [a_payment("pay_1", "k1"), a_payment("pay_2", "k2"), a_payment("pay_3", "k3")]
    reader = FakeReader(payments)
    driver = FakeDriver([DriveOutcome.SETTLED, DriveOutcome.SETTLED, DriveOutcome.UNRESOLVED])

    result = RecoverStale(reader, driver, FakeClock(T0), Config()).execute()

    assert result.processed == 3
    assert result.settled == 2
    assert result.unresolved == 1
    # each stuck payment re-driven with its OWN idempotency key
    assert [c.key for c in driver.calls] == ["k1", "k2", "k3"]
    assert [c.payment.id for c in driver.calls] == ["pay_1", "pay_2", "pay_3"]


def test_cutoff_is_now_minus_recovery_timeout():
    reader = FakeReader([])
    RecoverStale(reader, FakeDriver([]), FakeClock(T0), Config()).execute()
    assert reader.cutoff == T0 - Config().recovery_timeout


def test_no_stale_payments_drives_nothing():
    driver = FakeDriver([])
    result = RecoverStale(FakeReader([]), driver, FakeClock(T0), Config()).execute()
    assert result.processed == 0
    assert driver.calls == []
