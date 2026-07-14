"""
inspect_key — admin read of a key's full state (for debugging / the dashboard):

  existing key      -> Ok(inspection: key state + timestamps + its payment snapshot)
  key w/o payment   -> Ok(inspection with payment=None)
  missing key       -> Err(KeyNotFound)
  blank key         -> Err(InvalidRequest)
"""

from datetime import datetime

from app.payment.domain.entities.idempotency_key import IdempotencyKey
from app.payment.domain.entities.payment import Payment
from app.payment.domain.states import KeyState, PaymentStatus
from app.payment.usecases.inspect_key.dtos import InspectKeyInput
from app.payment.usecases.inspect_key.errors import InvalidRequest, KeyNotFound
from app.payment.usecases.inspect_key.service import InspectKey

T0 = datetime(2026, 1, 1, 12, 0, 0)


class FakeKeysReader:
    def __init__(self, keys):
        self._keys = keys

    def get(self, key):
        return self._keys.get(key)


class FakePaymentsReader:
    def __init__(self, payments):
        self._payments = payments

    def get(self, payment_id):
        return self._payments.get(payment_id)


def a_key(key="abc", state=KeyState.SUCCEEDED, payment_id="pay_1"):
    return IdempotencyKey(
        key=key, state=state, request_hash="h",
        payment_id=payment_id, created_at=T0, started_at=T0,
    )


def a_payment(payment_id="pay_1"):
    return Payment(
        id=payment_id, idempotency_key="abc", processor_key="pk_1",
        amount=2500, currency="USD", user_id="u1",
        status=PaymentStatus.SUCCEEDED, created_at=T0,
    )


def test_returns_key_and_its_payment():
    keys = FakeKeysReader({"abc": a_key()})
    payments = FakePaymentsReader({"pay_1": a_payment()})

    result = InspectKey(keys, payments).execute(InspectKeyInput(key="abc"))

    assert result.is_ok
    assert result.value.key == "abc"
    assert result.value.state == "succeeded"
    assert result.value.payment.id == "pay_1"
    assert result.value.payment.status == "succeeded"
    assert result.value.payment.amount == 2500


def test_key_without_payment_has_none():
    keys = FakeKeysReader({"abc": a_key(payment_id=None)})

    result = InspectKey(keys, FakePaymentsReader({})).execute(InspectKeyInput(key="abc"))

    assert result.is_ok
    assert result.value.payment is None


def test_missing_key_returns_not_found():
    result = InspectKey(FakeKeysReader({}), FakePaymentsReader({})).execute(
        InspectKeyInput(key="nope"))
    assert not result.is_ok
    assert isinstance(result.error, KeyNotFound)


def test_blank_key_returns_invalid_request():
    result = InspectKey(FakeKeysReader({}), FakePaymentsReader({})).execute(
        InspectKeyInput(key=""))
    assert not result.is_ok
    assert isinstance(result.error, InvalidRequest)
