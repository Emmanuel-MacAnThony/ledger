"""Expected inspect_key failures. Returned via Result; the API maps each to a status."""


class InspectError(Exception):
    message = "inspect error"

    def __init__(self, message: str | None = None):
        self.message = message or type(self).message
        super().__init__(self.message)


class InvalidRequest(InspectError):
    # -> 400
    message = "a key is required"


class KeyNotFound(InspectError):
    # -> 404
    message = "no idempotency key with that value"


# The closed set of errors inspect_key can return — the E in Result[T, E].
InspectKeyError = InvalidRequest | KeyNotFound
