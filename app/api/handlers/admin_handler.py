from dataclasses import dataclass
from typing import Callable, Protocol

from fastapi import FastAPI
from psycopg import Connection
from psycopg_pool import ConnectionPool

from app.payment.usecases.inspect_key.dtos import InspectKeyInput, KeyInspection
from app.payment.usecases.inspect_key.errors import (
    InspectKeyError, InvalidRequest, KeyNotFound,
)
from app.shared.response import from_result
from app.shared.result import Result


class InspectKeyUseCase(Protocol):
    def execute(self, inp: InspectKeyInput) -> Result[KeyInspection, InspectKeyError]: ...


@dataclass
class AdminHandlerDeps:
    pool: ConnectionPool
    make_inspect_key: Callable[[Connection], InspectKeyUseCase]


_STATUS: dict[type, int] = {
    InvalidRequest: 400,
    KeyNotFound: 404,
}


def _serialize(insp: KeyInspection) -> dict:
    return {
        "key": insp.key,
        "state": insp.state,
        "request_hash": insp.request_hash,
        "payment_id": insp.payment_id,
        "created_at": insp.created_at.isoformat(),
        "started_at": insp.started_at.isoformat(),
        "payment": None if insp.payment is None else {
            "id": insp.payment.id,
            "status": insp.payment.status,
            "amount": insp.payment.amount,
            "currency": insp.payment.currency,
            "user_id": insp.payment.user_id,
            "processor_key": insp.payment.processor_key,
            "created_at": insp.payment.created_at.isoformat(),
        },
    }


class AdminHandler:
    def __init__(self, deps: AdminHandlerDeps):
        self._deps = deps

    def register_routes(self, app: FastAPI) -> None:
        app.add_api_route("/admin/keys/{key}", self.inspect, methods=["GET"])

    def inspect(self, key: str):
        with self._deps.pool.connection() as conn:
            result = self._deps.make_inspect_key(conn).execute(InspectKeyInput(key=key))
        return from_result(
            result, serialize=_serialize,
            status_for_error=lambda e: _STATUS.get(type(e), 500),
            success_status=200,
        )
