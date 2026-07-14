from dataclasses import dataclass
from enum import Enum, auto

from app.payment.domain.entities.payment import Payment
from app.payment.domain.states import PaymentStatus


@dataclass
class DrivePaymentInput:
    key: str            # the idempotency key whose terminal state we flip
    payment: Payment    # the payment to charge + finalize (carries the processor_key)


class DriveOutcome(Enum):
    SETTLED = auto()      # charged + terminal committed — see .status
    UNRESOLVED = auto()   # charge returned UNKNOWN — left IN_FLIGHT
    INTERNAL = auto()     # terminal DB write failed — left IN_FLIGHT (recoverable)


@dataclass
class DriveResult:
    # A NEUTRAL outcome — not a success/error. Each caller (create_payment,
    # recover_stale) maps SETTLED / UNRESOLVED / INTERNAL to its own response.
    outcome: DriveOutcome
    status: PaymentStatus | None = None   # set only when SETTLED
