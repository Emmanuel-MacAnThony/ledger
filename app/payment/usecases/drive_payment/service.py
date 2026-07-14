from app.payment.domain.states import ChargeOutcome, KeyState, PaymentStatus
from app.payment.usecases.drive_payment.dtos import (
    DriveOutcome, DrivePaymentInput, DriveResult,
)
from app.payment.usecases.drive_payment.interfaces import ProcessorClient, UnitOfWork


class DrivePayment:
    def __init__(self, uow: UnitOfWork, processor: ProcessorClient):
        self._uow = uow
        self._processor = processor

    def execute(self, inp: DrivePaymentInput) -> DriveResult:
        payment = inp.payment

        # Charge with the payment's OWN processor_key — stable across re-drives, so
        # the processor dedups and a stuck payment finishes with exactly one charge.
        outcome = self._processor.charge(
            payment.processor_key, payment.amount, payment.currency, payment.user_id)

        if outcome is ChargeOutcome.UNKNOWN:
            return DriveResult(DriveOutcome.UNRESOLVED)   # don't fabricate a terminal state

        if outcome is ChargeOutcome.SUCCESS:
            key_state, status = KeyState.SUCCEEDED, PaymentStatus.SUCCEEDED
        else:  # DECLINED — a definite "no"
            key_state, status = KeyState.FAILED, PaymentStatus.FAILED

        # One transaction: key state + payment status land together or not at all.
        try:
            with self._uow as uow:
                uow.keys.set_terminal(inp.key, key_state)
                uow.payments.set_status(payment.id, status)
                uow.commit()
        except Exception:
            return DriveResult(DriveOutcome.INTERNAL)     # nothing applied — recoverable

        return DriveResult(DriveOutcome.SETTLED, status=status)
