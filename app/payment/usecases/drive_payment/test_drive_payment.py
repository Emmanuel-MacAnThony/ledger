"""
drive_payment — observables:

  charge SUCCESS    -> SETTLED(SUCCEEDED); key+payment flipped terminal
  charge DECLINED   -> SETTLED(FAILED);    key+payment flipped terminal
  charge UNKNOWN    -> UNRESOLVED;         key stays IN_FLIGHT (no fabrication)
  terminal commit fails -> INTERNAL;       key stays IN_FLIGHT (atomic: nothing applied)
"""

from datetime import datetime

from app.payment.domain.entities.payment import Payment
from app.payment.domain.states import ChargeOutcome, KeyState, PaymentStatus
from app.payment.usecases.drive_payment.dtos import DriveOutcome, DrivePaymentInput
from app.payment.usecases.drive_payment.service import DrivePayment

T0 = datetime(2026, 1, 1, 12, 0, 0)


class Store:
    def __init__(self):
        self.key_state = KeyState.IN_FLIGHT
        self.payment_status = PaymentStatus.PENDING


class FakeKeys:
    def __init__(self, ops, store):
        self._ops, self._store = ops, store

    def set_terminal(self, key, state):
        self._ops.append(lambda: setattr(self._store, "key_state", state))


class FakePayments:
    def __init__(self, ops, store):
        self._ops, self._store = ops, store

    def set_status(self, payment_id, status):
        self._ops.append(lambda: setattr(self._store, "payment_status", status))


class FakeUoW:
    # buffers writes, applies on commit; fail_on_commit models a DB write that dies
    # at commit time (nothing lands -> atomic).
    def __init__(self, store, fail_on_commit=False):
        self.fail_on_commit = fail_on_commit
        self._ops = []
        self.keys = FakeKeys(self._ops, store)
        self.payments = FakePayments(self._ops, store)

    def __enter__(self):
        self._ops.clear()
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        if self.fail_on_commit:
            raise RuntimeError("commit failed")
        for op in self._ops:
            op()
        self._ops.clear()


class FakeProcessor:
    def __init__(self, outcome):
        self._outcome = outcome
        self.calls = 0

    def charge(self, processor_key, amount, currency, user_id):
        self.calls += 1
        return self._outcome


def a_payment():
    return Payment(
        id="pay_1", idempotency_key="abc", processor_key="pk_1",
        amount=1000, currency="USD", user_id="user_1",
        status=PaymentStatus.PENDING, created_at=T0,
    )


def drive(outcome, fail_on_commit=False):
    store = Store()
    uow = FakeUoW(store, fail_on_commit=fail_on_commit)
    result = DrivePayment(uow, FakeProcessor(outcome)).execute(
        DrivePaymentInput(key="abc", payment=a_payment()))
    return result, store


def test_success_settles_succeeded():
    result, store = drive(ChargeOutcome.SUCCESS)
    assert result.outcome is DriveOutcome.SETTLED
    assert result.status is PaymentStatus.SUCCEEDED
    assert store.key_state is KeyState.SUCCEEDED
    assert store.payment_status is PaymentStatus.SUCCEEDED


def test_declined_settles_failed():
    result, store = drive(ChargeOutcome.DECLINED)
    assert result.outcome is DriveOutcome.SETTLED
    assert result.status is PaymentStatus.FAILED
    assert store.key_state is KeyState.FAILED
    assert store.payment_status is PaymentStatus.FAILED


def test_unknown_is_unresolved_and_leaves_in_flight():
    result, store = drive(ChargeOutcome.UNKNOWN)
    assert result.outcome is DriveOutcome.UNRESOLVED
    assert store.key_state is KeyState.IN_FLIGHT       # never fabricated a terminal state
    assert store.payment_status is PaymentStatus.PENDING


def test_commit_failure_is_internal_and_leaves_in_flight():
    result, store = drive(ChargeOutcome.SUCCESS, fail_on_commit=True)
    assert result.outcome is DriveOutcome.INTERNAL
    assert store.key_state is KeyState.IN_FLIGHT       # atomic: nothing applied
    assert store.payment_status is PaymentStatus.PENDING
