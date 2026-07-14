from app.config import Config
from app.payment.usecases.drive_payment.dtos import DriveOutcome, DrivePaymentInput
from app.payment.usecases.recover_stale.dtos import RecoverStaleResult
from app.payment.usecases.recover_stale.interfaces import (
    Clock, PaymentDriver, StalePaymentsReader,
)


class RecoverStale:
    def __init__(self, reader: StalePaymentsReader, driver: PaymentDriver,
                 clock: Clock, config: Config):
        self._reader = reader
        self._driver = driver
        self._clock = clock
        self._config = config

    def execute(self) -> RecoverStaleResult:
        # In-flight payments stuck longer than the recovery window: their owner is
        # presumed dead and no client came back, so we re-drive them ourselves.
        cutoff = self._clock.now() - self._config.recovery_timeout
        stuck = self._reader.stale_in_flight(cutoff)

        settled = unresolved = 0
        for payment in stuck:
            # Re-drive with the payment's own key -> the processor dedups, so this is
            # safe even if a client is re-driving the same payment concurrently.
            result = self._driver.execute(
                DrivePaymentInput(key=payment.idempotency_key, payment=payment))
            if result.outcome is DriveOutcome.SETTLED:
                settled += 1
            else:  # UNRESOLVED or INTERNAL — still stuck, catch it next sweep
                unresolved += 1

        return RecoverStaleResult(
            processed=len(stuck), settled=settled, unresolved=unresolved)
