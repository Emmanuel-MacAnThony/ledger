"""Interfaces create_payment depends on — exactly the ports THIS use case needs,
nothing more (other use cases declare their own). Structural (Protocol), so one
concrete adapter satisfies every use case's interface without importing any of them."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.payment.domain.entities.idempotency_key import IdempotencyKey
from app.payment.domain.entities.payment import Payment
from app.payment.domain.states import ChargeOutcome, ClaimOutcome, KeyState, PaymentStatus


class KeysRepo(Protocol):
    def get(self, key: str) -> IdempotencyKey | None: ...
    def insert(self, key: IdempotencyKey) -> ClaimOutcome: ...   # WON | LOST (the lock)
    def reset(self, key: IdempotencyKey) -> None: ...            # reclaim: overwrite existing row
    def set_terminal(self, key: str, state: KeyState) -> None: ...


class PaymentsRepo(Protocol):
    def get(self, payment_id: str) -> Payment: ...
    def insert_pending(self, payment: Payment) -> None: ...
    def set_status(self, payment_id: str, status: PaymentStatus) -> None: ...


class UnitOfWork(Protocol):
    keys: KeysRepo
    payments: PaymentsRepo

    def __enter__(self) -> UnitOfWork: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...   # rollback on exception, else no-op
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class ProcessorClient(Protocol):
    def charge(self, processor_key: str, amount: int, currency: str,
               user_id: str) -> ChargeOutcome: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGen(Protocol):
    def new_payment_id(self) -> str: ...
    def new_processor_key(self) -> str: ...
