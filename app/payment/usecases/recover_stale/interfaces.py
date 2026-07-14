"""Interfaces recover_stale depends on — read the stale batch, drive each."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.payment.domain.entities.payment import Payment
from app.payment.usecases.drive_payment.dtos import DrivePaymentInput, DriveResult


class StalePaymentsReader(Protocol):
    def stale_in_flight(self, cutoff: datetime) -> list[Payment]: ...


class PaymentDriver(Protocol):
    def execute(self, inp: DrivePaymentInput) -> DriveResult: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
