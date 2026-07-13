from enum import Enum, auto


class ClaimOutcome(Enum):
    # Outcome of trying to claim a key. Shared by the use case (which decides) and
    # the repo (which reports it) — lives in domain so neither depends on the other.
    WON = auto()      # this call inserted the key — it owns the payment
    LOST = auto()     # key already existed (UNIQUE violation) — someone else owns it


class KeyState(str, Enum):
    # Stored states of an idempotency key. EXPIRED is derived from created_at at
    # read time (not stored), so it's deliberately absent. CREATED is merged into
    # IN_FLIGHT — the claim inserts IN_FLIGHT directly.
    IN_FLIGHT = "in_flight"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ChargeOutcome(Enum):
    # What the processor port returns. Transient (not persisted): SUCCESS/DECLINED
    # are definite; UNKNOWN means retries were exhausted without a definite answer.
    SUCCESS = "success"
    DECLINED = "declined"
    UNKNOWN = "unknown"
