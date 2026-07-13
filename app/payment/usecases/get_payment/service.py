from app.payment.usecases.get_payment.dtos import GetPaymentInput, PaymentView
from app.payment.usecases.get_payment.errors import (
    GetPaymentError, InvalidRequest, PaymentNotFound,
)
from app.payment.usecases.get_payment.interfaces import PaymentReader
from app.shared.result import Result

GetPaymentResult = Result[PaymentView, GetPaymentError]


class GetPayment:
    def __init__(self, reader: PaymentReader):
        self._reader = reader

    def execute(self, inp: GetPaymentInput) -> GetPaymentResult:
        if not inp.payment_id:
            return Result.err(InvalidRequest())        # trust no one

        payment = self._reader.get(inp.payment_id)
        if payment is None:
            return Result.err(PaymentNotFound())
        return Result.ok(PaymentView.from_payment(payment))
