from dataclasses import dataclass
from datetime import datetime

from app.payment.domain.states import PaymentStatus


@dataclass
class Payment:
    id: str
    idempotency_key: str            # which client key produced it (audit link)
    processor_key: str              # unique per payment; what we send the processor
    amount: int                     # minor units (cents)
    currency: str
    user_id: str
    status: PaymentStatus
    created_at: datetime
