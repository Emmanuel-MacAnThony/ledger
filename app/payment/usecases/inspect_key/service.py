from app.payment.usecases.inspect_key.dtos import InspectKeyInput, KeyInspection
from app.payment.usecases.inspect_key.errors import (
    InspectKeyError, InvalidRequest, KeyNotFound,
)
from app.payment.usecases.inspect_key.interfaces import KeysReader, PaymentsReader
from app.shared.result import Result

InspectKeyResult = Result[KeyInspection, InspectKeyError]


class InspectKey:
    def __init__(self, keys: KeysReader, payments: PaymentsReader):
        self._keys = keys
        self._payments = payments

    def execute(self, inp: InspectKeyInput) -> InspectKeyResult:
        if not inp.key:
            return Result.err(InvalidRequest())        # trust no one

        key = self._keys.get(inp.key)
        if key is None:
            return Result.err(KeyNotFound())

        payment = self._payments.get(key.payment_id) if key.payment_id else None
        return Result.ok(KeyInspection.build(key, payment))
