from dataclasses import dataclass
from datetime import datetime, timedelta

from app.payment.domain.states import KeyState


@dataclass
class IdempotencyKey:
    key: str
    state: KeyState
    request_hash: str
    created_at: datetime            # drives expiry (the 24h window)
    started_at: datetime            # drives in-flight age (the recovery timeout)
    payment_id: str | None = None

    def is_terminal(self) -> bool:
        return self.state in (KeyState.SUCCEEDED, KeyState.FAILED)

    def age(self, now: datetime) -> timedelta:
        return now - self.started_at

    def is_expired(self, now: datetime, ttl: timedelta) -> bool:
        return now - self.created_at > ttl

    def is_stale(self, now: datetime, timeout: timedelta) -> bool:
        # Only an unfinished (IN_FLIGHT) key can be "stuck". A terminal key is done,
        # never stale — so guard on state before checking age.
        return self.state == KeyState.IN_FLIGHT and self.age(now) > timeout
