"""
get_payment — observables (real reader fake, no other deps):

  existing payment id   -> Ok(view) matching the stored row
  missing payment id    -> Err(PaymentNotFound)
  empty / blank id      -> Err(InvalidRequest)     # trust no one
"""

from datetime import datetime

from app.payment.domain.entities.payment import Payment
from app.payment.domain.states import PaymentStatus
from app.payment.usecases.get_payment.dtos import GetPaymentInput
from app.payment.usecases.get_payment.errors import InvalidRequest, PaymentNotFound
from app.payment.usecases.get_payment.service import GetPayment

T0 = datetime(2026, 1, 1, 12, 0, 0)


class FakeReader:
    def __init__(self):
        self.payments = {}

    def get(self, payment_id):
        return self.payments.get(payment_id)


def a_payment(payment_id="pay_1", amount=1000):
    return Payment(
        id=payment_id, idempotency_key="abc", processor_key="pk_1",
        amount=amount, currency="USD", user_id="user_1",
        status=PaymentStatus.SUCCEEDED, created_at=T0,
    )


def test_returns_payment_when_found():
    reader = FakeReader()
    reader.payments["pay_1"] = a_payment("pay_1", amount=2500)

    result = GetPayment(reader).execute(GetPaymentInput(payment_id="pay_1"))

    assert result.is_ok
    assert result.value.payment_id == "pay_1"
    assert result.value.amount == 2500
    assert result.value.status == PaymentStatus.SUCCEEDED


def test_missing_payment_returns_not_found():
    result = GetPayment(FakeReader()).execute(GetPaymentInput(payment_id="nope"))

    assert not result.is_ok
    assert isinstance(result.error, PaymentNotFound)


def test_blank_id_returns_invalid_request():
    result = GetPayment(FakeReader()).execute(GetPaymentInput(payment_id=""))

    assert not result.is_ok
    assert isinstance(result.error, InvalidRequest)
