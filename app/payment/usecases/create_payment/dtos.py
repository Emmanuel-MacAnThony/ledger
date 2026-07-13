from dataclasses import dataclass
from datetime import datetime

from app.payment.domain.entities.payment import Payment
from app.payment.domain.states import PaymentStatus


@dataclass
class CreatePaymentInput:
    idempotency_key: str
    amount: int
    currency: str
    user_id: str
    source_ip: str


@dataclass
class PaymentResult:
    payment_id: str
    status: PaymentStatus
    amount: int
    currency: str
    user_id: str
    created_at: datetime

    @classmethod
    def from_payment(cls, payment: Payment) -> "PaymentResult":
        # The reply is reconstructed from the (immutable) payment row on replay —
        # no separate cached copy to keep in sync.
        return cls(
            payment_id=payment.id,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            user_id=payment.user_id,
            created_at=payment.created_at,
        )
