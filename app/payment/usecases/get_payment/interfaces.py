"""Interfaces get_payment depends on — just a read that can report 'not found'."""

from typing import Protocol

from app.payment.domain.entities.payment import Payment


class PaymentReader(Protocol):
    def get(self, payment_id: str) -> Payment | None: ...
