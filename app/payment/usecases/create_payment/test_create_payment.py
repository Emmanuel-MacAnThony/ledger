"""
create_payment — observables (given injected fakes -> asserted off Result / fake state):

  fresh key, processor=SUCCESS         -> Ok(SUCCEEDED); charges==1; 1 payment; key.response set
  same key again (terminal)            -> Ok; charges STILL ==1; response byte-equal (replay)
  same key, DIFFERENT body             -> Err(KeyReused); charges==0
  no idempotency key                   -> Err(MissingIdempotencyKey)
  IN_FLIGHT, age < RECOVERY_TIMEOUT    -> Err(PaymentInProgress); charges==0
  IN_FLIGHT, age > RECOVERY_TIMEOUT    -> re-drive same pk; charges STILL ==1 (dedup); SUCCEEDED
  processor=UNKNOWN                    -> Err(PaymentInProgress); key STAYS IN_FLIGHT
  processor=DECLINED                   -> Ok(FAILED); exactly 1 charge attempt
  key age > KEY_TTL                    -> reclaim: +1 payment row; old payment unchanged
  UoW fails during terminal            -> key stays IN_FLIGHT; response unset

invariants (never observed): SUCCEEDED w/ no response; 2 payments per key in-window;
2 real charges per processor_key; partial terminal write.
"""

from datetime import datetime, timedelta

from app.payment.domain.entities.idempotency_key import IdempotencyKey
from app.payment.domain.entities.payment import Payment
from app.payment.domain.fingerprint import fingerprint
from app.payment.domain.states import ChargeOutcome, ClaimOutcome, KeyState, PaymentStatus
from app.payment.usecases.create_payment.service import CreatePayment
from app.payment.usecases.create_payment.dtos import CreatePaymentInput
from app.payment.usecases.create_payment.errors import (
    Internal, KeyReused, MissingIdempotencyKey, PaymentInProgress,
)
from app.config import Config

T0 = datetime(2026, 1, 1, 12, 0, 0)


# --- fakes (in-memory, mimic the interface contracts) -----------------------

class Store:
    """Shared committed state the fake repos read/write."""
    def __init__(self):
        self.keys = {}          # key -> IdempotencyKey
        self.payments = {}      # payment_id -> Payment
        self.attempts = []      # list[Attempt]


class FakeKeysRepo:
    def __init__(self, store, ops):
        self._store, self._ops = store, ops

    def get(self, key):
        return self._store.keys.get(key)

    def insert(self, key):
        if key.key in self._store.keys:
            return ClaimOutcome.LOST                 # mimics the UNIQUE constraint
        self._ops.append(lambda: self._store.keys.__setitem__(key.key, key))
        return ClaimOutcome.WON

    def reset(self, key):
        self._ops.append(lambda: self._store.keys.__setitem__(key.key, key))

    def set_terminal(self, key, state):
        def op():
            self._store.keys[key].state = state
        self._ops.append(op)


class FakePaymentsRepo:
    def __init__(self, store, ops):
        self._store, self._ops = store, ops

    def get(self, payment_id):
        return self._store.payments[payment_id]

    def insert_pending(self, payment):
        self._ops.append(lambda: self._store.payments.__setitem__(payment.id, payment))

    def set_status(self, payment_id, status):
        self._ops.append(lambda: setattr(self._store.payments[payment_id], "status", status))

    def stale_in_flight(self, cutoff):
        return []                                    # worker-only; unused here


class FakeAttemptsRepo:
    def __init__(self, store, ops):
        self._store, self._ops = store, ops

    def record(self, attempt):
        self._ops.append(lambda: self._store.attempts.append(attempt))


class FakeUnitOfWork:
    """Buffers staged writes; applies them atomically on commit, drops them on
    rollback / un-committed exit. fail_on_commit models a transaction that dies at
    commit time (nothing lands) — used for the atomicity observable."""
    def __init__(self, store, fail_on_commit=None):
        self.store = store
        self.fail_on_commit = fail_on_commit         # commit number to fail (1-based), or None
        self.commit_count = 0
        self.committed = False
        self._ops = []
        self.keys = FakeKeysRepo(store, self._ops)
        self.payments = FakePaymentsRepo(store, self._ops)
        self.attempts = FakeAttemptsRepo(store, self._ops)

    def __enter__(self):
        self._ops.clear()
        self.committed = False
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.committed:
            self._ops.clear()                        # rollback: discard staged writes
        return False

    def commit(self):
        self.commit_count += 1
        if self.commit_count == self.fail_on_commit:  # nothing applies -> atomic failure
            raise RuntimeError("commit failed")
        for op in self._ops:
            op()
        self._ops.clear()
        self.committed = True

    def rollback(self):
        self._ops.clear()


class FakeProcessor:
    """Scriptable outcome + dedup on processor_key. `real_charges` counts actual
    money movements; `calls` counts every invocation (incl. deduped re-drives)."""
    def __init__(self, outcome=ChargeOutcome.SUCCESS):
        self._scripted = outcome
        self._memory = {}       # processor_key -> definite outcome
        self.calls = 0
        self.real_charges = 0

    def charge(self, processor_key, amount, currency, user_id):
        self.calls += 1
        if processor_key in self._memory:
            return self._memory[processor_key]       # dedup: no new charge
        outcome = self._scripted
        if outcome is ChargeOutcome.SUCCESS:
            self.real_charges += 1
            self._memory[processor_key] = outcome
        elif outcome is ChargeOutcome.DECLINED:
            self._memory[processor_key] = outcome    # definite, no money moved
        # UNKNOWN: not remembered — a later retry could still resolve it
        return outcome


class FakeClock:
    def __init__(self, now):
        self._now = now

    def now(self):
        return self._now

    def advance(self, delta):
        self._now += delta


class FakeIdGen:
    def __init__(self):
        self._p = self._k = 0

    def new_payment_id(self):
        self._p += 1
        return f"pay_{self._p}"

    def new_processor_key(self):
        self._k += 1
        return f"pk_{self._k}"


def build(processor_outcome=ChargeOutcome.SUCCESS, now=T0, store=None, processor=None, config=None):
    # store / processor can be shared across use-case instances to simulate a
    # different process hitting the same persisted state.
    store = store if store is not None else Store()
    processor = processor if processor is not None else FakeProcessor(processor_outcome)
    config = config if config is not None else Config()
    usecase = CreatePayment(FakeUnitOfWork(store), processor, FakeClock(now), FakeIdGen(), config)
    return usecase, store, processor


def an_input(key="abc", amount=1000, currency="USD", user_id="user_1"):
    return CreatePaymentInput(
        idempotency_key=key, amount=amount, currency=currency,
        user_id=user_id, source_ip="1.2.3.4",
    )


def seed_in_flight(store, key="abc", started_at=T0, amount=1000, currency="USD", user_id="user_1"):
    # Simulate another request that claimed the key and is mid-charge (IN_FLIGHT).
    # request_hash matches an_input's default body so the fingerprint check passes.
    payment = Payment(
        id="pay_seed", idempotency_key=key, processor_key="pk_seed",
        amount=amount, currency=currency, user_id=user_id,
        status=PaymentStatus.PENDING, created_at=started_at,
    )
    store.payments[payment.id] = payment
    store.keys[key] = IdempotencyKey(
        key=key, state=KeyState.IN_FLIGHT,
        request_hash=fingerprint(amount, currency, user_id),
        created_at=started_at, started_at=started_at, payment_id=payment.id,
    )


def seed_completed(store, key="abc", created_at=T0, amount=1000, payment_id="pay_old"):
    # A payment that completed at `created_at`. Used to build an EXPIRED key.
    payment = Payment(
        id=payment_id, idempotency_key=key, processor_key="pk_" + payment_id,
        amount=amount, currency="USD", user_id="user_1",
        status=PaymentStatus.SUCCEEDED, created_at=created_at,
    )
    store.payments[payment_id] = payment
    store.keys[key] = IdempotencyKey(
        key=key, state=KeyState.SUCCEEDED,
        request_hash=fingerprint(amount, "USD", "user_1"),
        created_at=created_at, started_at=created_at, payment_id=payment_id,
    )


# --- tests ------------------------------------------------------------------

def test_new_key_charges_once_and_succeeds():
    usecase, store, processor = build(ChargeOutcome.SUCCESS)

    result = usecase.execute(an_input(key="abc"))

    assert result.is_ok
    assert result.value.status == PaymentStatus.SUCCEEDED
    assert processor.real_charges == 1
    assert len(store.payments) == 1
    key = store.keys["abc"]
    assert key.state == KeyState.SUCCEEDED
    assert store.payments["pay_1"].status == PaymentStatus.SUCCEEDED   # reply reconstructs from this


def test_terminal_key_replays_reply_without_charging():
    # terminal (SUCCEEDED/FAILED) -> return the same reply (reconstructed from the
    # immutable payment row), never charge again. Non-terminal states have their own tests.
    usecase, store, processor = build(ChargeOutcome.SUCCESS)
    first = usecase.execute(an_input(key="abc"))

    # fresh use case, SAME store + processor — proves the replay comes from the
    # persisted store, not in-memory carryover (survives a "restart").
    usecase2, _, _ = build(store=store, processor=processor)
    second = usecase2.execute(an_input(key="abc"))

    assert second.is_ok
    assert second.value == first.value      # identical reply, read from the store
    assert processor.calls == 1             # never charged again
    assert len(store.payments) == 1


def test_live_key_with_different_body_is_rejected():
    # live = not expired. Same key + different body while still in-window -> 409.
    # (expired + different body reclaims instead — see the expiry test.)
    usecase, store, processor = build(ChargeOutcome.SUCCESS)
    usecase.execute(an_input(key="abc", amount=1000))           # establish a live key

    result = usecase.execute(an_input(key="abc", amount=2000))  # same key, different body

    assert not result.is_ok
    assert isinstance(result.error, KeyReused)
    assert processor.calls == 1                                 # not charged again
    assert len(store.payments) == 1                            # no new payment row


def test_missing_key_rejected():
    usecase, store, processor = build(ChargeOutcome.SUCCESS)

    result = usecase.execute(an_input(key=""))

    assert not result.is_ok
    assert isinstance(result.error, MissingIdempotencyKey)
    assert processor.calls == 0                 # nothing happened
    assert len(store.payments) == 0


def test_fresh_in_flight_returns_come_back_no_charge():
    usecase, store, processor = build(ChargeOutcome.SUCCESS, now=T0)
    seed_in_flight(store, key="abc", started_at=T0)     # another request is mid-charge, fresh

    result = usecase.execute(an_input(key="abc"))        # same key, same body

    assert not result.is_ok
    assert isinstance(result.error, PaymentInProgress)
    assert processor.calls == 0                          # do NOT charge
    assert len(store.payments) == 1                      # no new payment row


def test_stale_in_flight_redrives_same_key_charges_once():
    _, store, processor = build(ChargeOutcome.SUCCESS, now=T0)
    # another request charged pk_seed, then died before writing terminal (in-flight).
    seed_in_flight(store, key="abc", started_at=T0)
    processor.charge("pk_seed", 1000, "USD", "user_1")     # the original charge that landed
    assert processor.real_charges == 1

    # 10 min later (> recovery_timeout of 5m) a retry arrives -> takes over.
    usecase, _, _ = build(now=T0 + timedelta(minutes=10), store=store, processor=processor)
    result = usecase.execute(an_input(key="abc"))          # same key, same body

    assert result.is_ok
    assert result.value.status == PaymentStatus.SUCCEEDED
    assert processor.real_charges == 1                     # dedup: no second money movement
    assert store.keys["abc"].state == KeyState.SUCCEEDED
    assert len(store.payments) == 1                        # re-drive uses the existing payment


def test_charge_unknown_leaves_in_flight():
    usecase, store, processor = build(ChargeOutcome.UNKNOWN)

    result = usecase.execute(an_input(key="abc"))

    assert not result.is_ok
    assert isinstance(result.error, PaymentInProgress)          # "come back"
    assert store.keys["abc"].state == KeyState.IN_FLIGHT        # NOT terminal — don't fabricate
    assert store.payments["pay_1"].status == PaymentStatus.PENDING
    assert processor.calls == 1                                 # attempted once
    assert processor.real_charges == 0                         # no definite charge


def test_declined_returns_failed_single_attempt():
    usecase, store, processor = build(ChargeOutcome.DECLINED)

    result = usecase.execute(an_input(key="abc"))

    assert result.is_ok                                        # a declined payment is a valid outcome
    assert result.value.status == PaymentStatus.FAILED
    assert store.keys["abc"].state == KeyState.FAILED
    assert store.payments["pay_1"].status == PaymentStatus.FAILED
    assert processor.calls == 1                                # definite "no" — no retry storm
    assert processor.real_charges == 0


def test_expired_key_reclaims_new_payment_old_untouched():
    store = Store()
    seed_completed(store, key="abc", created_at=T0 - timedelta(hours=25), amount=500)  # >24h ago

    usecase, _, processor = build(ChargeOutcome.SUCCESS, now=T0, store=store)
    result = usecase.execute(an_input(key="abc", amount=2000))   # expired -> new payment

    assert result.is_ok
    assert result.value.status == PaymentStatus.SUCCEEDED
    assert result.value.amount == 2000                   # the NEW payment, not the old 500
    assert processor.real_charges == 1                   # the new payment charged
    assert len(store.payments) == 2                      # old + new coexist
    assert store.payments["pay_old"].amount == 500       # old payment untouched
    assert store.payments["pay_old"].status == PaymentStatus.SUCCEEDED
    assert store.keys["abc"].payment_id != "pay_old"     # key now points at the new payment


def test_expired_in_flight_key_is_not_reclaimed():
    # An in-flight key older than 24h must NOT be reclaimed — its original charge may
    # still be outstanding, so recycling it risks orphaning money / double-charging.
    # It's resolved via the in-flight path (stale -> re-drive), never recycled.
    _, store, processor = build(ChargeOutcome.SUCCESS, now=T0)
    seed_in_flight(store, key="abc", started_at=T0 - timedelta(hours=25))  # expired AND stale
    processor.charge("pk_seed", 1000, "USD", "user_1")     # the original charge that landed
    assert processor.real_charges == 1

    usecase, _, _ = build(now=T0, store=store, processor=processor)
    result = usecase.execute(an_input(key="abc"))

    assert result.is_ok
    assert len(store.payments) == 1                        # NOT reclaimed — no new payment
    assert processor.real_charges == 1                     # dedup: re-drove the same charge
    assert store.keys["abc"].state == KeyState.SUCCEEDED   # resolved, not recycled


def test_terminal_write_failure_returns_internal_and_leaves_in_flight():
    store = Store()
    processor = FakeProcessor(ChargeOutcome.SUCCESS)
    uow = FakeUnitOfWork(store, fail_on_commit=2)     # fail the terminal commit (claim is 1st)
    usecase = CreatePayment(uow, processor, FakeClock(T0), FakeIdGen(), Config())

    result = usecase.execute(an_input(key="abc"))

    assert not result.is_ok
    assert isinstance(result.error, Internal)                # observable, not a bare exception
    # atomicity: the terminal write is all-or-nothing, so it landed NOTHING.
    assert store.keys["abc"].state == KeyState.IN_FLIGHT       # never flipped to terminal
    assert store.payments["pay_1"].status == PaymentStatus.PENDING
    # the charge DID happen — the stuck-in-flight case recovery/reconciliation resolves.
    assert processor.real_charges == 1
