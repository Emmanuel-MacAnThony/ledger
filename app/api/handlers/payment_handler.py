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
from app.payment.usecases.get_payment.dtos import GetPaymentInput, PaymentView
from app.payment.usecases.get_payment.errors import GetPaymentError, PaymentNotFound
from app.payment.usecases.get_payment.errors import InvalidRequest as GetInvalidRequest
from app.shared.response import from_result
from app.shared.result import Result


class CreatePaymentUseCase(Protocol):
    def execute(self, inp: CreatePaymentInput) -> Result[PaymentResult, CreatePaymentError]: ...


class GetPaymentUseCase(Protocol):
    def execute(self, inp: GetPaymentInput) -> Result[PaymentView, GetPaymentError]: ...


@dataclass
class PaymentHandlerDeps:
    pool: ConnectionPool
    # factories: bind a per-request connection to the singletons at call time.
    make_create_payment: Callable[[Connection], CreatePaymentUseCase]
    make_get_payment: Callable[[Connection], GetPaymentUseCase]


_CREATE_STATUS: dict[type, int] = {
    MissingIdempotencyKey: 400,
    InvalidRequest: 400,
    KeyReused: 409,
    PaymentInProgress: 409,
    Internal: 500,
}

_GET_STATUS: dict[type, int] = {
    GetInvalidRequest: 400,
    PaymentNotFound: 404,
}


class PaymentRequest(BaseModel):
    amount: int
    currency: str
    user_id: str


def _serialize_result(pr: PaymentResult) -> dict:
    return {
        "payment_id": pr.payment_id, "status": pr.status.value,
        "amount": pr.amount, "currency": pr.currency,
        "user_id": pr.user_id, "created_at": pr.created_at.isoformat(),
    }


def _serialize_view(pv: PaymentView) -> dict:
    return {
        "payment_id": pv.payment_id, "status": pv.status.value,
        "amount": pv.amount, "currency": pv.currency,
        "user_id": pv.user_id, "created_at": pv.created_at.isoformat(),
    }


class PaymentHandler:
    def __init__(self, deps: PaymentHandlerDeps):
        self._deps = deps

    def register_routes(self, app: FastAPI) -> None:
        app.add_api_route("/payments", self.create, methods=["POST"])
        app.add_api_route("/payments/{payment_id}", self.get, methods=["GET"])

    def create(self, body: PaymentRequest, request: Request,
               idempotency_key: str = Header(default="")):
        with self._deps.pool.connection() as conn:
            result = self._deps.make_create_payment(conn).execute(CreatePaymentInput(
                idempotency_key=idempotency_key,
                amount=body.amount, currency=body.currency, user_id=body.user_id,
                source_ip=request.client.host if request.client else "",
            ))
        return from_result(
            result, serialize=_serialize_result,
            status_for_error=lambda e: _CREATE_STATUS.get(type(e), 500),
            success_status=200,
        )

    def get(self, payment_id: str):
        with self._deps.pool.connection() as conn:
            result = self._deps.make_get_payment(conn).execute(
                GetPaymentInput(payment_id=payment_id))
        return from_result(
            result, serialize=_serialize_view,
            status_for_error=lambda e: _GET_STATUS.get(type(e), 500),
            success_status=200,
        )
