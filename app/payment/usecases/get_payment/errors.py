"""Expected get_payment failures. Returned via Result; the API maps each to a
status and surfaces its message."""


class PaymentReadError(Exception):
    """Base for the expected get_payment failures."""
    message = "get payment error"

    def __init__(self, message: str | None = None):
        self.message = message or type(self).message
        super().__init__(self.message)


class InvalidRequest(PaymentReadError):
    # -> 400
    message = "a payment id is required"


class PaymentNotFound(PaymentReadError):
    # -> 404
    message = "no payment with that id"


# The closed set of errors get_payment can return — the E in Result[T, E].
GetPaymentError = InvalidRequest | PaymentNotFound
