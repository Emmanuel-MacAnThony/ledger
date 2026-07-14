from dataclasses import dataclass
from datetime import datetime

from app.payment.domain.entities.idempotency_key import IdempotencyKey
from app.payment.domain.entities.payment import Payment


@dataclass
class InspectKeyInput:
    key: str


@dataclass
class PaymentSnapshot:
    id: str
    status: str
    amount: int
    currency: str
    user_id: str
    processor_key: str
    created_at: datetime

    @classmethod
    def from_payment(cls, p: Payment) -> "PaymentSnapshot":
        return cls(
            id=p.id, status=p.status.value, amount=p.amount, currency=p.currency,
            user_id=p.user_id, processor_key=p.processor_key, created_at=p.created_at,
        )


@dataclass
class KeyInspection:
    key: str
    state: str
    request_hash: str
    payment_id: str | None
    created_at: datetime
    started_at: datetime
    payment: PaymentSnapshot | None

    @classmethod
    def build(cls, key: IdempotencyKey, payment: Payment | None) -> "KeyInspection":
        return cls(
            key=key.key, state=key.state.value, request_hash=key.request_hash,
            payment_id=key.payment_id, created_at=key.created_at, started_at=key.started_at,
            payment=PaymentSnapshot.from_payment(payment) if payment else None,
        )
