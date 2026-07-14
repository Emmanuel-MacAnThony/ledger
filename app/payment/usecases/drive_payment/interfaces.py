"""Interfaces drive_payment depends on — the charge, and a unit of work exposing
exactly the terminal-write surface it needs."""

from __future__ import annotations

from typing import Protocol

from app.payment.domain.states import ChargeOutcome, KeyState, PaymentStatus


class ProcessorClient(Protocol):
    def charge(self, processor_key: str, amount: int, currency: str,
               user_id: str) -> ChargeOutcome: ...


class _Keys(Protocol):
    def set_terminal(self, key: str, state: KeyState) -> None: ...


class _Payments(Protocol):
    def set_status(self, payment_id: str, status: PaymentStatus) -> None: ...


class UnitOfWork(Protocol):
    keys: _Keys
    payments: _Payments

    def __enter__(self) -> UnitOfWork: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...
