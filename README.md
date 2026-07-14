# Ledger

An idempotent payment API built from scratch. Send the same request twice — a retry, a double-click, a network timeout that fired again — and the customer is charged **once**. The idempotency key is the contract: same key means same operation, and Ledger guarantees exactly one payment behind it, even when a dozen copies of the request land at the same instant.

<br/>

<p align="center">
  <img src="screenshots/dashboard-fired.png" alt="Ledger idempotency console – 10 concurrent requests collapsing to one payment" width="100%"/>
</p>

---

## What it does

- **Exactly-once charges** — one idempotency key produces one payment, no matter how many times the request is sent
- **Safe under concurrency** — N identical requests racing in parallel resolve to a single charge; the losers never create a second payment (the database `UNIQUE` constraint *is* the lock)
- **Charges outside the transaction** — the external call to the processor happens between two short commits, so a slow or hung processor never holds a database lock
- **Crash-safe** — if the process dies after charging but before recording the result, a background worker finds the stuck payment and resolves it; the processor dedupes the re-drive so the customer is never double-charged
- **Replay, don't recompute** — a repeated request after success replays the stored payment; it never re-runs the charge
- **Come back / conflict, cleanly** — an in-flight duplicate gets a "come back" 409; the *same key with a different body* gets a "key reused" 409, with no data from the original leaked back
- **Live console** — fire N concurrent requests from the browser and watch them collapse to one payment, then inspect any key's stored state and its payment

---

## Screenshots

### Idempotency console

<p align="center">
  <img src="screenshots/dashboard.png" alt="Ledger console – fire concurrent requests + key inspector" width="100%"/>
</p>

Two panels. **Fire concurrent requests** generates one fresh key and fires N `POST /payments` at the same instant — the result shows the winner (`200`) and the come-backs (`409`) collapsing to a single payment. **Inspect key** reads a key's stored state (`in_flight` / `succeeded` / `failed`) and the payment it points at, straight from `GET /admin/keys/{key}`.

### Concurrency, proven

10 requests fired simultaneously with one key:

```
10 concurrent, same key → {'200 succeeded': 1, '409 PaymentInProgress': 9}
unique payments created: 1
```

One winner charges; the nine that arrive while it's in flight get a "come back" — one payment, one charge.

---

## Architecture

```
  client
    │  POST /payments      Idempotency-Key: <uuid>
    ▼
┌───────────────────────┐       charge(processor_key)        ┌────────────────────┐
│     Ledger API        │ ─────────────────────────────────► │  Payment processor │
│     (FastAPI)         │       idempotent — deduped          │  (mock)            │
│                       │ ◄───────────────────────────────── │                    │
│  1. claim  (INSERT)   │                                     └────────────────────┘
│  2. drive  (charge)   │       the charge happens BETWEEN
│  3. terminal (commit) │       the two commits, never inside a txn
└──────────┬────────────┘
           │ PostgreSQL
┌───────────────────────┐        ┌───────────────────────────────┐
│  idempotency_keys     │        │  Recovery worker              │
│  payments             │ ◄───── │  (separate process): sweeps   │
│  idempotency_attempts │        │  stale in-flight keys and     │
└───────────────────────┘        │  re-drives them to terminal   │
                                 └───────────────────────────────┘
```

**A request runs in three beats:**

1. **Claim** — `INSERT` the key (`in_flight`) and a `pending` payment in one short transaction. The insert either wins the `UNIQUE` constraint (this call owns the payment) or loses it (someone else already claimed the key). *The write is the lock.*
2. **Charge** — call the processor with a per-payment `processor_key`, **outside** any transaction. This is the slow, external, failure-prone step; it holds no database lock.
3. **Terminal** — record the outcome (`succeeded` / `failed`) in one short atomic commit.

A key that already exists short-circuits: terminal → **replay** the stored payment; fresh in-flight → **come back**; stale in-flight (owner presumed dead) → **re-drive** with the same `processor_key`, which the processor dedupes.

**Recovery worker** (`python -m worker.main`) — a separate daemon that sweeps payments stuck `pending` past the recovery timeout (a beat-2 crash: charged, but the result was never recorded) and re-drives them. Because the `processor_key` is fixed per payment, the re-drive is deduped — resolving the record without charging again.

---

## The idea that makes it work

**You cannot lock a row that does not exist yet.**

The naïve design is: look up the key, and if it's missing, create the payment. But between the lookup and the create, a second identical request does the same lookup, also sees nothing, and also creates a payment. Two charges. A row lock can't help — there's no row to lock.

So Ledger doesn't lock; it **races to write**, and lets the database pick one winner. The key column has a `UNIQUE` constraint, and the claim is a single `INSERT ... ON CONFLICT DO NOTHING`. Every concurrent request tries to insert the same key; exactly one succeeds (`WON` — it owns the payment), the rest bounce off the constraint (`LOST` — they back off, re-read, and replay or come back). The write *is* the lock, and it's a lock you never have to acquire, hold, or release.

This is why the charge can live **outside** the transaction. The claim commits in microseconds and releases immediately; the slow processor call happens with no lock held; the terminal write is another microsecond commit. A processor that hangs for 30 seconds blocks nothing. Contrast a "lock the row, charge, unlock" design, where that same hang would pin a database row for the whole call.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | Straightforward sync code; the use case is request/response, not streaming |
| Web | FastAPI | Thin HTTP edge; `def` handlers run in a threadpool, matching the sync stack |
| Database | PostgreSQL 16 | `UNIQUE` constraint as the claim lock; atomic terminal commit |
| DB driver | psycopg 3 (sync) + pool | Sync throughout; a connection pool, one connection checked out per request |
| Processor client | httpx (sync) | Calls the mock processor; the one external, failure-prone hop |
| Migrations | plain SQL | Run by Postgres on first init via `docker-entrypoint-initdb.d` |
| Tests | pytest | 56 tests; every use case TDD'd from the domain up, fakes in the test file |
| Architecture | clean / ports & adapters | `domain` / `infra` / `usecases`; `Protocol` interfaces per use case; DI at a composition root |
| Dashboard | single self-contained HTML | Served at `GET /`, same-origin, no build step, no CORS |

No ORM. No async. No framework magic reaching into the core — config is built once at the app entrance and passed down.

---

## Getting started

### Prerequisites

- Docker + Docker Compose
- Python 3.11+ (only if you want to run the app or tests outside Docker)

### 1. Start the stack

```bash
docker compose up -d --build
```

This brings up three services:

| Service | Port | What |
|---|---|---|
| **app** (Ledger API + console) | **8000** | `http://localhost:8000/` — the dashboard; the API under `/payments`, `/admin` |
| **db** (PostgreSQL 16) | **5432** | `postgres://ledger:ledger@localhost:5432/ledger`; runs `migrations/` on first init |
| **processor_mock** | **9000** | Stand-in payment processor that dedupes on `processor_key` |

Open **http://localhost:8000/** and hit **Fire N requests with ONE key**.

### 2. Try it from the terminal

```bash
KEY=$(uuidgen)

# Fire the same request twice — one charge, the second replays.
curl -s -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" -H "Idempotency-Key: $KEY" \
  -d '{"amount":1000,"currency":"USD","user_id":"user_1"}'

curl -s -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" -H "Idempotency-Key: $KEY" \
  -d '{"amount":1000,"currency":"USD","user_id":"user_1"}'   # same payment_id, no second charge

# Inspect the key's stored state + payment.
curl -s http://localhost:8000/admin/keys/$KEY
```

### 3. Run the tests

```bash
pip install -e ".[dev]"
pytest -q          # 56 passed
```

The recovery worker runs as its own process:

```bash
python -m worker.main
```

---

## REST API

Every response is enveloped as `{ "data": ..., "error": ... }`.

| Method | Path | Description | Notable statuses |
|---|---|---|---|
| `POST` | `/payments` | Create a payment. Requires an `Idempotency-Key` header. | `200` created/replayed · `409` in progress / key reused with a different body · `400` missing key · `500` internal |
| `GET` | `/payments/{payment_id}` | Fetch a payment by id | `200` · `404` not found |
| `GET` | `/admin/keys/{key}` | Inspect a key's state and its payment | `200` · `404` unknown key |
| `GET` | `/` | The idempotency console (HTML) | `200` |

**Idempotency semantics for `POST /payments`:**

| Situation | Result |
|---|---|
| New key | Charge once, `200` with the new payment |
| Same key, same body, prior success | **Replay** the stored payment — no charge |
| Same key, request still in flight | `409` **come back** — a charge is already underway |
| Same key, **different body** | `409` **key reused** — the key is bound to its first operation (no original data echoed back) |
| Same key, aged past 24h, terminal | Reclaimed as a fresh payment |

---

## Project structure

```
20-ledger/
├── app/
│   ├── main.py                     # Composition root: build infra once, wire factories, serve the console at /
│   ├── config.py                   # key_ttl (24h) + recovery_timeout (5m); built at the entrance, passed down
│   ├── api/
│   │   ├── router.py               # Each handler registers its own routes
│   │   └── handlers/               # payment_handler (/payments), admin_handler (/admin/keys)
│   ├── db/
│   │   └── connection.py           # psycopg3 connection pool
│   ├── payment/
│   │   ├── domain/                 # Pure core — no I/O
│   │   │   ├── states.py           # KeyState, PaymentStatus, ChargeOutcome, ClaimOutcome (WON/LOST)
│   │   │   ├── fingerprint.py      # sha256 of the canonical request — detects key-reuse
│   │   │   └── entities/           # IdempotencyKey (expiry/staleness computed), Payment, Attempt
│   │   ├── infra/                  # Adapters: clock, idgen, processor client, repositories, unit_of_work
│   │   └── usecases/               # One folder per use case: dtos, errors, interfaces (Protocol), service, tests
│   │       ├── create_payment/     #   the three-beat claim → drive → terminal
│   │       ├── drive_payment/      #   shared: idempotent charge + atomic terminal write
│   │       ├── get_payment/
│   │       ├── inspect_key/
│   │       └── recover_stale/      #   used by the worker
│   └── shared/
│       ├── result.py               # Result[T, E] — errors as values, mapped to HTTP status at the edge
│       └── response.py             # One envelope shape; one place sets the status
├── worker/
│   └── main.py                     # Recovery daemon: python -m worker.main
├── processor_mock/                 # Stand-in processor that dedupes on processor_key
├── migrations/
│   └── 001_init.sql                # idempotency_keys, payments, idempotency_attempts
├── web/
│   └── index.html                  # The idempotency console (self-contained, served at /)
├── screenshots/
└── docker-compose.yml
```

---

## Design notes

**Why the write is the lock, not a row lock?**
The claim you need to serialize is the *creation* of the payment — and you can't take a row lock on a row that doesn't exist yet. Two concurrent requests would both find nothing, both proceed, both charge. So the claim is a single `INSERT` guarded by a `UNIQUE` constraint on the key: the database admits exactly one winner (`ClaimOutcome.WON`) and rejects the rest (`LOST`). The loser doesn't error — it backs off, re-reads the now-existing key, and takes the replay/come-back path. One round trip, no lock manager, no deadlocks.

**Why does the charge happen outside the transaction?**
Because the processor call is slow and can hang, and you must never hold a database lock across it. The request is three beats: a microsecond commit to claim, then the external charge holding *nothing*, then a microsecond commit to record the result. A processor that stalls for 30 seconds stalls one HTTP request and zero database rows.

**Why a per-payment `processor_key`, generated by us?**
It's the handle that makes the charge *repeatable*. We generate it, persist it before charging, and send it on every (re-)drive. The processor dedupes on it — so a retry, a recovery sweep, or a stale-key re-drive all hit the same charge, and the customer is charged once. It's what lets recovery be "just call drive again" instead of a careful, fragile reconciliation.

**Why is expiry computed, not stored?**
A key expires 24h after `created_at`. Storing an `expires_at` (or a background job that flips keys to `expired`) is a second source of truth that can drift or lag. `now - created_at > 24h` can't be stale — it's evaluated at read time against the one timestamp that matters. Same for in-flight staleness: `now - started_at > recovery_timeout`.

**Why is reclaim terminal-only?**
An expired key that's still `in_flight` must **not** be recycled — its original charge may still be outstanding at the processor. Only a *terminal* key past the 24h window reclaims into a fresh payment. An expired-but-in-flight key falls through to the in-flight branch and gets resolved by a re-drive, not thrown away.

**Why drop the cached response instead of storing it?**
The first design stored the full response on the key to replay it verbatim. But that's duplicated truth — the payment row already holds everything the response needs. So the response column was dropped; a replay reconstructs the reply from the immutable payment row. One record, no risk of the cached copy disagreeing with the real payment.

**Why three separate clocks?**
Recovery timeout (minutes) ≪ key TTL (24h) ≈ processor memory (24h). The recovery timeout must be short enough to un-stick a crashed charge quickly, but longer than a healthy charge takes. The key TTL must be long enough that legitimate client retries still dedupe, and it lives *within* the window the processor remembers the `processor_key` — otherwise a reclaim could collide with a charge the processor still knows about.

**Why a recovery worker at all, if state is computed on the fly?**
Reads are self-healing (staleness is computed), but a payment stuck `pending` after a beat-2 crash won't fix itself without a *write*. The worker is the thing that performs that write: it sweeps `pending` payments older than the recovery timeout and re-drives them to terminal. It's a separate process so an API outage doesn't stop recovery, and vice versa.

---

## What's not built yet

- **Real processor** — `processor_mock` stands in for a real gateway (Stripe, Adyen); the contract it models is "dedupe on the key we send"
- **Attempt auditing** — the `idempotency_attempts` table exists (append-only audit of every hit against a payment) but isn't written on every request yet
- **Failed-charge policy** — a `failed` terminal state is recorded but there's no retry/backoff schedule for declines
- **Config from env** — `Config.from_env()` currently returns the defaults; the wiring point exists but env overrides aren't read yet
- **Auth** — the `/admin` inspector is open; no authn/authz layer
