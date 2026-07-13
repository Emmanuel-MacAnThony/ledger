# Rule: two requests are the SAME operation iff (amount, currency, user_id) match.
#   same operation    -> same fingerprint      (a retry replays, never re-charges)
#   any field differs -> different fingerprint  (reused key + different body -> 409)

from app.payment.domain.fingerprint import fingerprint


def test_same_operation_yields_same_fingerprint():
    assert fingerprint(1000, "USD", "user_1") == fingerprint(1000, "USD", "user_1")


def test_different_amount_is_a_different_operation():
    assert fingerprint(1000, "USD", "user_1") != fingerprint(2000, "USD", "user_1")


def test_different_currency_is_a_different_operation():
    assert fingerprint(1000, "USD", "user_1") != fingerprint(1000, "EUR", "user_1")


def test_different_user_is_a_different_operation():
    assert fingerprint(1000, "USD", "user_1") != fingerprint(1000, "USD", "user_2")
