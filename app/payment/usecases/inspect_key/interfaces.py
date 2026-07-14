"""Interfaces inspect_key depends on — read the key, and its payment (if any)."""

from typing import Protocol

from app.payment.domain.entities.idempotency_key import IdempotencyKey
from app.payment.domain.entities.payment import Payment


class KeysReader(Protocol):
    def get(self, key: str) -> IdempotencyKey | None: ...


class PaymentsReader(Protocol):
    def get(self, payment_id: str) -> Payment | None: ...
