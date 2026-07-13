from dataclasses import dataclass
from datetime import datetime

from app.payment.domain.entities.payment import Payment
from app.payment.domain.states import PaymentStatus


@dataclass
class GetPaymentInput:
    payment_id: str


@dataclass
class PaymentView:
    # get_payment owns its own output shape (same fields as create_payment's reply
    # today, but a separate type — the two use cases evolve independently).
    payment_id: str
    status: PaymentStatus
    amount: int
    currency: str
    user_id: str
    created_at: datetime

    @classmethod
    def from_payment(cls, payment: Payment) -> "PaymentView":
        return cls(
            payment_id=payment.id,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            user_id=payment.user_id,
            created_at=payment.created_at,
        )
