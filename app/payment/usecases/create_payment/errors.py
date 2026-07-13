"""Expected create_payment failures. Returned via Result (not raised); the API
layer maps each type to an HTTP status and surfaces its message. Unexpected
failures still raise."""


class PaymentError(Exception):
    """Base for the expected create_payment failures. Each subclass sets a default
    message; pass a custom one to override."""
    message = "payment error"

    def __init__(self, message: str | None = None):
        self.message = message or type(self).message
        super().__init__(self.message)


class MissingIdempotencyKey(PaymentError):
    # -> 400
    message = "an Idempotency-Key header is required"


class InvalidRequest(PaymentError):
    # -> 400
    message = "the request is invalid (check amount and currency)"


class KeyReused(PaymentError):
    # -> 409. Developer-facing; must NOT echo the original request (no data leak).
    message = "this idempotency key was already used for a request with different parameters"


class PaymentInProgress(PaymentError):
    # -> 409. "come back": a fresh in-flight charge, or a charge that returned UNKNOWN.
    message = "this payment is still in progress; retry shortly"


class Internal(PaymentError):
    # -> 500. An infrastructure failure (e.g. a DB write that didn't commit). The
    # state is left recoverable (nothing partially applied); the client may retry.
    message = "internal error"


# The closed set of errors create_payment can return — the E in Result[T, E].
CreatePaymentError = (
    MissingIdempotencyKey
    | InvalidRequest
    | KeyReused
    | PaymentInProgress
    | Internal
)
