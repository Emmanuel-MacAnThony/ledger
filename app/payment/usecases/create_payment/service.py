from app.config import Config
from app.payment.domain.entities.idempotency_key import IdempotencyKey
from app.payment.domain.entities.payment import Payment
from app.payment.domain.fingerprint import fingerprint
from app.payment.domain.states import ClaimOutcome, KeyState, PaymentStatus
from app.payment.usecases.create_payment.dtos import CreatePaymentInput, PaymentResult
from app.payment.usecases.drive_payment.dtos import DriveOutcome, DrivePaymentInput
from app.payment.usecases.create_payment.errors import (
    CreatePaymentError, Internal, KeyReused, MissingIdempotencyKey, PaymentInProgress,
)
from app.payment.usecases.create_payment.interfaces import (
    Clock, IdGen, PaymentDriver, UnitOfWork,
)
from app.shared.result import Result

# What this use case returns: a PaymentResult, or one of its declared errors.
CreatePaymentResult = Result[PaymentResult, CreatePaymentError]


class CreatePayment:
    def __init__(self, uow: UnitOfWork, driver: PaymentDriver,
                 clock: Clock, idgen: IdGen, config: Config):
        self._uow = uow
        self._driver = driver
        self._clock = clock
        self._idgen = idgen
        self._config = config

    def execute(self, inp: CreatePaymentInput) -> CreatePaymentResult:
        if not inp.idempotency_key:
            return Result.err(MissingIdempotencyKey())

        now = self._clock.now()
        request_hash = fingerprint(inp.amount, inp.currency, inp.user_id)
        existing = self._uow.keys.get(inp.idempotency_key)
        if existing is not None:
            return self._handle_existing(existing, inp, request_hash, now)
        return self._start(inp, request_hash, now, reclaim=False)

    def _handle_existing(self, existing: IdempotencyKey, inp: CreatePaymentInput,
                         request_hash: str, now) -> CreatePaymentResult:
        # Expiry reclaim is TERMINAL-only. An in-flight key that's aged past the
        # window must NOT be recycled — its original charge may still be outstanding,
        # so it falls through to the in-flight branch (resolve via re-drive) instead.
        if existing.is_terminal() and existing.is_expired(now, self._config.key_ttl):
            return self._start(inp, request_hash, now, reclaim=True)   # new generation
        # Live key: same key must mean the same operation. Different body -> 409.
        if request_hash != existing.request_hash:
            return Result.err(KeyReused())
        if existing.is_terminal():
            payment = self._uow.payments.get(existing.payment_id)
            return Result.ok(PaymentResult.from_payment(payment))   # replay from the payment row, no charge
        # in-flight: fresh -> owner alive, come back; stale -> owner dead, re-drive.
        if existing.is_stale(now, self._config.recovery_timeout):
            payment = self._uow.payments.get(existing.payment_id)
            return self._drive(existing.key, payment)   # same processor_key -> dedup
        return Result.err(PaymentInProgress())

    def _start(self, inp: CreatePaymentInput, request_hash: str, now, reclaim: bool) -> CreatePaymentResult:
        payment_id = self._idgen.new_payment_id()
        processor_key = self._idgen.new_processor_key()

        payment = Payment(
            id=payment_id,
            idempotency_key=inp.idempotency_key,
            processor_key=processor_key,
            amount=inp.amount,
            currency=inp.currency,
            user_id=inp.user_id,
            status=PaymentStatus.PENDING,
            created_at=now,
        )
        key = IdempotencyKey(
            key=inp.idempotency_key,
            state=KeyState.IN_FLIGHT,
            request_hash=request_hash,
            created_at=now,
            started_at=now,
            payment_id=payment_id,
        )

        # Beat 1 — claim: fresh key(IN_FLIGHT) + payment(PENDING), atomically.
        # reclaim overwrites an expired key row; new inserts a fresh one (unique-guarded).
        lost = False
        with self._uow as uow:
            if reclaim:
                uow.keys.reset(key)
            elif uow.keys.insert(key) is ClaimOutcome.LOST:
                lost = True                      # a concurrent request claimed it first
            if not lost:
                uow.payments.insert_pending(payment)
                uow.commit()

        if lost:
            # We lost the claim race: get() saw nothing, but insert hit the UNIQUE
            # constraint. Nothing was committed — re-read and handle the now-existing
            # key (replay / come-back) instead of creating a duplicate payment + charge.
            existing = self._uow.keys.get(inp.idempotency_key)
            return self._handle_existing(existing, inp, request_hash, now)

        # Beats 2 & 3 — charge + terminal.
        return self._drive(inp.idempotency_key, payment)

    def _drive(self, key_str: str, payment: Payment) -> CreatePaymentResult:
        # Shared drive: idempotent charge + atomic terminal. Map its neutral outcome
        # to this use case's client-facing Result.
        result = self._driver.execute(
            DrivePaymentInput(key=key_str, payment=payment))

        if result.outcome is DriveOutcome.UNRESOLVED:
            return Result.err(PaymentInProgress())    # charge undecided -> come back
        if result.outcome is DriveOutcome.INTERNAL:
            return Result.err(Internal())             # terminal write failed

        return Result.ok(PaymentResult(               # SETTLED
            payment_id=payment.id,
            status=result.status,
            amount=payment.amount,
            currency=payment.currency,
            user_id=payment.user_id,
            created_at=payment.created_at,
        ))
