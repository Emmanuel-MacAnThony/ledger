-- idempotency_keys: the reusable dedup handle. One row per client key; mutable
-- (reset on reclaim). EXPIRED is computed from created_at, not stored.
CREATE TABLE idempotency_keys (
    key          TEXT PRIMARY KEY,                    -- the client UUID; UNIQUE = the claim lock
    state        TEXT NOT NULL
                 CHECK (state IN ('in_flight', 'succeeded', 'failed')),
    request_hash TEXT NOT NULL,                       -- fingerprint of the operation
    payment_id   TEXT,                                -- points at the CURRENT payment
    created_at   TIMESTAMPTZ NOT NULL,                -- drives the 24h expiry window
    started_at   TIMESTAMPTZ NOT NULL                 -- drives in-flight age (recovery)
);

-- payments: the permanent money record. One row per real charge, append-only.
CREATE TABLE payments (
    id              TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL,                    -- which client key produced it (audit link)
    processor_key   TEXT NOT NULL UNIQUE,             -- our per-payment handle to the processor
    amount          BIGINT NOT NULL,                  -- minor units (cents)
    currency        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    status          TEXT NOT NULL
                    CHECK (status IN ('pending', 'succeeded', 'failed')),
    created_at      TIMESTAMPTZ NOT NULL
);

-- idempotency_attempts: append-only audit, anchored on the payment (not the reused key).
CREATE TABLE idempotency_attempts (
    id         BIGSERIAL PRIMARY KEY,
    payment_id TEXT NOT NULL,
    key        TEXT NOT NULL,                         -- the client key sent (context)
    seen_state TEXT NOT NULL,                         -- key state when this hit arrived, or 'new'
    source_ip  TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX payments_pending_idx  ON payments (status) WHERE status = 'pending';
CREATE INDEX attempts_payment_idx  ON idempotency_attempts (payment_id);
