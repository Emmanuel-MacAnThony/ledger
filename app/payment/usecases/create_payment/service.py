from app.config import Config
from app.payment.domain.entities.idempotency_key import IdempotencyKey
from app.payment.domain.entities.payment import Payment
from app.payment.domain.fingerprint import fingerprint
from app.payment.domain.states import ChargeOutcome, KeyState, PaymentStatus
from app.payment.usecases.create_payment.dtos import CreatePaymentInput, PaymentResult
from app.payment.usecases.create_payment.errors import (
    CreatePaymentError, Internal, KeyReused, MissingIdempotencyKey, PaymentInProgress,
)
from app.payment.usecases.create_payment.interfaces import (
    Clock, IdGen, ProcessorClient, UnitOfWork,
)
from app.shared.result import Result

# What this use case returns: a PaymentResult, or one of its declared errors.
CreatePaymentResult = Result[PaymentResult, CreatePaymentError]


class CreatePayment:
    def __init__(self, uow: UnitOfWork, processor: ProcessorClient,
                 clock: Clock, idgen: IdGen, config: Config):
        self._uow = uow
        self._processor = processor
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
        # Expiry FIRST: an expired key reclaims as a new payment regardless of body,
        # so the fingerprint check must not run on it (get() returns expired rows too).
        if existing.is_expired(now, self._config.key_ttl):
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
        with self._uow as uow:
            if reclaim:
                uow.keys.reset(key)
            else:
                uow.keys.insert(key)
            uow.payments.insert_pending(payment)
            uow.commit()

        # Beats 2 & 3 — charge + terminal.
        return self._drive(inp.idempotency_key, payment)

    def _drive(self, key_str: str, payment: Payment) -> CreatePaymentResult:
        # Charge with the payment's OWN processor_key — stable across re-drives, so
        # the processor dedups and a stuck payment finishes with exactly one charge.
        # Shared by the first attempt and by re-drive of a stale in-flight payment.
        outcome = self._processor.charge(
            payment.processor_key, payment.amount, payment.currency, payment.user_id)

        # UNKNOWN: retries exhausted, outcome undecided. Do NOT fabricate a terminal
        # state — leave the key IN_FLIGHT and let recovery/reconciliation resolve it.
        if outcome is ChargeOutcome.UNKNOWN:
            return Result.err(PaymentInProgress())

        if outcome is ChargeOutcome.SUCCESS:
            key_state, status = KeyState.SUCCEEDED, PaymentStatus.SUCCEEDED
        else:  # DECLINED — a definite "no"
            key_state, status = KeyState.FAILED, PaymentStatus.FAILED

        # The terminal write is one transaction — key state + payment status land
        # together or not at all. If the commit fails, nothing applies (the key
        # stays IN_FLIGHT, recoverable) and we surface an observable Internal error
        # rather than letting the infra exception escape.
        try:
            with self._uow as uow:
                uow.keys.set_terminal(key_str, key_state)
                uow.payments.set_status(payment.id, status)
                uow.commit()
        except Exception:
            return Result.err(Internal())

        return Result.ok(PaymentResult(
            payment_id=payment.id,
            status=status,
            amount=payment.amount,
            currency=payment.currency,
            user_id=payment.user_id,
            created_at=payment.created_at,
        ))
