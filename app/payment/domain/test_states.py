# The string values are the persisted/wire contract — they land in the DB
# state/status columns and get emitted by the API. Pin them so a rename can't
# silently orphan stored rows. (EXPIRED is computed, not stored, so it's not here.)

from app.payment.domain.states import KeyState, PaymentStatus, ChargeOutcome


def test_key_states_are_the_stored_values():
    assert KeyState.IN_FLIGHT.value == "in_flight"
    assert KeyState.SUCCEEDED.value == "succeeded"
    assert KeyState.FAILED.value == "failed"
    assert {s.value for s in KeyState} == {"in_flight", "succeeded", "failed"}


def test_payment_statuses_are_the_stored_values():
    assert PaymentStatus.PENDING.value == "pending"
    assert PaymentStatus.SUCCEEDED.value == "succeeded"
    assert PaymentStatus.FAILED.value == "failed"


def test_charge_outcomes_are_a_closed_set():
    assert {o.name for o in ChargeOutcome} == {"SUCCESS", "DECLINED", "UNKNOWN"}
