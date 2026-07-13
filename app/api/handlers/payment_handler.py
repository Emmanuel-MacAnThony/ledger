from dataclasses import dataclass
from typing import Callable, Protocol

from fastapi import FastAPI, Header, Request
from psycopg import Connection
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from app.payment.usecases.create_payment.dtos import CreatePaymentInput, PaymentResult
from app.payment.usecases.create_payment.errors import (
    CreatePaymentError, Internal, InvalidRequest, KeyReused,
    MissingIdempotencyKey, PaymentInProgress,
)
from app.shared.response import from_result
from app.shared.result import Result


class CreatePaymentUseCase(Protocol):
    def execute(self, inp: CreatePaymentInput) -> Result[PaymentResult, CreatePaymentError]: ...


@dataclass
class PaymentHandlerDeps:
    pool: ConnectionPool
    # factory: given a per-request connection, build the use case (closes over the
    # singletons — processor, clock, idgen, config — at bootstrap).
    make_create_payment: Callable[[Connection], CreatePaymentUseCase]


# The closed error union -> HTTP status. Exhaustive over CreatePaymentError.
_STATUS: dict[type, int] = {
    MissingIdempotencyKey: 400,
    InvalidRequest: 400,
    KeyReused: 409,
    PaymentInProgress: 409,
    Internal: 500,
}


class PaymentRequest(BaseModel):
    amount: int
    currency: str
    user_id: str


def _serialize(pr: PaymentResult) -> dict:
    return {
        "payment_id": pr.payment_id, "status": pr.status.value,
        "amount": pr.amount, "currency": pr.currency,
        "user_id": pr.user_id, "created_at": pr.created_at.isoformat(),
    }


class PaymentHandler:
    def __init__(self, deps: PaymentHandlerDeps):
        self._deps = deps

    def register_routes(self, app: FastAPI) -> None:
        app.add_api_route("/payments", self.create, methods=["POST"])

    def create(self, body: PaymentRequest, request: Request,
               idempotency_key: str = Header(default="")):
        # One pooled connection per request; the UnitOfWork owns transactions within it.
        with self._deps.pool.connection() as conn:
            usecase = self._deps.make_create_payment(conn)
            result = usecase.execute(CreatePaymentInput(
                idempotency_key=idempotency_key,
                amount=body.amount, currency=body.currency, user_id=body.user_id,
                source_ip=request.client.host if request.client else "",
            ))
        return from_result(
            result,
            serialize=_serialize,
            status_for_error=lambda e: _STATUS.get(type(e), 500),
            success_status=200,
        )
