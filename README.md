# Expense Sharing Service

Backend for the **Decentro SDE Intern assignment**: users create groups, record shared expenses, view history and see who owes whom. Includes one product enhancement: **Smart Settlement Suggestions**.

- **Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2, SQLite (PostgreSQL-ready), pytest + FastAPI TestClient, Docker.
- **Scope:** everything in the assignment's mandatory sections. No auth and no frontend (not requested). Unequal splits and settling (optional bonuses) are *not* implemented; see [Known limitations](#known-limitations).

## Contents
1. [Quick start (Windows / PowerShell)](#quick-start-windows--powershell)
2. [Architecture](#architecture)
3. [Database design](#database-design)
4. [Assumptions and business rules](#assumptions-and-business-rules)
5. [Money and rounding](#money-and-rounding)
6. [Balance algorithm](#balance-algorithm)
7. [Product enhancement: Smart Settlement Suggestions](#product-enhancement-smart-settlement-suggestions)
8. [API reference](#api-reference)
9. [Sample scenario (verified)](#sample-scenario-verified)
10. [Testing](#testing)
11. [Docker](#docker)
12. [Known limitations / future work](#known-limitations)

## Quick start (Windows / PowerShell)

```powershell
cd expense-sharing-service
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt

python -m app.db.init_db              # optional: tables are also created automatically on startup
uvicorn app.main:app --reload         # http://127.0.0.1:8000  (interactive docs: /docs)
```

**Configuration:** one environment variable, `DATABASE_URL` (default `sqlite:///./expense_sharing.db`, see `.env.example`).
PowerShell: `$env:DATABASE_URL = "sqlite:///./other.db"`. For PostgreSQL install a driver (`pip install "psycopg[binary]"`) and use `postgresql+psycopg://user:pass@host:5432/db`. No code change is needed; the schema uses only portable constructs. *(PostgreSQL has not been run in this project; only SQLite was exercised.)*

**Run tests:** `pytest` (each test uses its own in-memory database; no local DB needed).

## Architecture

```
app/
  main.py            FastAPI app, router wiring, startup table creation
  core/              config (env vars), exceptions + uniform error responses
  db/                declarative Base, engine/session (FK enforcement for SQLite), init_db
  models/            SQLAlchemy tables
  schemas/           Pydantic request/response contracts (validation lives here)
  services/          business logic - no HTTP imports
    balance_engine.py   PURE functions: equal split, pairwise netting, net balances, settlements
    money.py            rupees <-> paise
    *_service.py        use-cases: validate, query, commit/rollback
  api/               thin routers: parse -> call service -> return schema
tests/               pytest suite (API, engine unit tests, DB constraints, rollback)
```

Layering rule: routers contain no business logic; services own transactions (`commit` / `rollback`); `balance_engine` knows nothing about databases or HTTP, so it is unit-tested with plain integers. I deliberately skipped a repository layer: with five tables it would only add indirection.

## Database design

```mermaid
erDiagram
    users ||--o{ group_members : "joins"
    groups ||--o{ group_members : "has"
    groups ||--o{ expenses : "contains"
    group_members ||--o{ expenses : "payer must be a member"
    users ||--o{ expenses : "paid_by"
    expenses ||--|{ expense_participants : "split into"
    users ||--o{ expense_participants : "charged"

    users { int id PK
            string name "unique, case-insensitive"
            datetime created_at }
    groups { int id PK
             string name
             datetime created_at }
    group_members { int group_id PK,FK
                    int user_id PK,FK
                    datetime joined_at }
    expenses { int id PK
               int group_id FK
               int paid_by FK
               int amount_paise "CHECK > 0"
               string description
               datetime created_at }
    expense_participants { int expense_id PK,FK
                           int user_id PK,FK
                           int share_paise "CHECK >= 0" }
```

| Table | Why it exists |
|---|---|
| `users` | People. Unique `lower(name)` index so a name identifies one person (needed for the name-keyed balance view). |
| `groups` | A trip / flat / event. Group names are not unique (two "Goa Trip" groups are legitimate). |
| `group_members` | Many-to-many users⇄groups. **Composite PK (group_id, user_id)** makes duplicate memberships impossible at the DB level. No surrogate id: nothing references a membership by id. Extra index on `user_id` for "groups of a user". |
| `expenses` | One row per expense: group, payer, `amount_paise`, description, timestamp. |
| `expense_participants` | **Snapshot of the split**: who was charged what *at creation time*. Composite PK (expense_id, user_id), `share_paise >= 0`. |

**Key constraints and indexes**
- `fk_expenses_payer_is_member`: composite FK `(group_id, paid_by) → group_members(group_id, user_id)`. The database itself refuses an expense whose payer is not in the group, even if application code had a bug.
- `CHECK (amount_paise > 0)`, `CHECK (share_paise >= 0)`, all FKs `NOT NULL`.
- `ix_expenses_group_created (group_id, created_at, id)` serves the history query and its ordering; `ix_expense_participants_user_id` serves per-user aggregation.
- SQLite does not enforce FKs by default; `db/session.py` runs `PRAGMA foreign_keys=ON` on every connection (covered by tests).

**How history stays stable.** Membership is a *current* list; an expense's participants are a *frozen copy* in `expense_participants`. Adding a member later inserts one `group_members` row and touches no existing expense, so old splits cannot change. Balances are computed from `expense_participants`, never from "current members".

**How the schema supports balances.** One aggregate query (`SUM(share_paise)` grouped by participant and payer, skipping payer = participant) yields every "X owes Y" total. No per-expense Python loops.

**Deliberate trade-offs**
- Shares are stored (denormalised) instead of recomputed: costs a few rows, buys correctness under membership changes and a trivial balance query.
- "Sum of shares = amount" is enforced in the service inside one transaction; a plain CHECK cannot express it across tables (a trigger could, but is overkill here and less portable).
- No member removal and no expense edit/delete: history is append-only, which keeps balances auditable. (`ON DELETE RESTRICT` on user FKs backs this up.)
- Tables are created with `create_all` (no Alembic migrations) to keep the project small.

## Assumptions and business rules

| Topic | Decision |
|---|---|
| Duplicate user name | `409 CONFLICT`; names are trimmed and compared case-insensitively. |
| Group names | May repeat. |
| Repeat membership request | `409 CONFLICT` (not silently idempotent, so clients learn about the mistake). Group unchanged. |
| Empty group | Valid. Lists no members, no expenses, no balances. Recording an expense in it is rejected because the payer cannot be a member. |
| Unknown group / user | `404`. |
| Payer not in group | `422 BUSINESS_RULE_VIOLATION`. |
| Participants of an expense | All members of the group **at the moment of creation**, including the payer. |
| Payer's own share | Stored, but never counted as a debt (the payer does not owe themselves). |
| Single-member group | Expense accepted; the payer bears 100%; no balances. |
| Body `group_id` in `POST /groups/{id}/members` | Optional (the assignment's example includes it); must match the URL, else `422`. |
| Currency | INR only. |
| Balance scope | **Both**: `GET /balances` is system-wide (all groups), `GET /balances?group_id=N` and `GET /groups/{N}/balances` are per-group. |
| Settlement suggestions | Per group only (suggesting payments across unrelated groups would mix unrelated debts). |
| Expense order | Oldest first (`created_at`, then `id`). |

## Money and rounding

- **Internally:** integer **paise** everywhere (DB column, arithmetic). No `float` is ever used for money.
- **Input:** `amount` in **rupees**, JSON number or string, **max 2 decimal places**, `> 0`, at most 12 digits (e.g. `1200`, `1200.50`, `"10.10"`). Pydantic parses it as `Decimal` (JSON numbers are read from their text, so `10.10` is exactly 1010 paise). `10.123`, `NaN`, `0`, negatives and non-numbers → `422`.
- **Output:** money as **strings with two decimals** (`"400.00"`) plus an `*_paise` integer. Strings avoid JSON float surprises. (The assignment's sample shows bare numbers; this is a deliberate precision trade-off.)
- **Remainder rule:** `base = amount // n`, `remainder = amount % n`; the **first `remainder` participants, ordered by ascending user id, get +1 paisa**. Shares always sum exactly to the amount and differ by at most 1 paisa. Example: ₹100.00 among ids 1,2,3 → 33.34 / 33.33 / 33.33. The rule depends only on the amount and the set of members, so it is deterministic. Trade-off: the lowest ids always take the extra paisa; rotating by expense id would be fairer but harder to explain.

## Balance algorithm

All steps live in `app/services/balance_engine.py` as pure functions on integers.

1. **Raw debts.** From stored shares: for each expense and each participant ≠ payer, *participant owes payer share*. The database sums these per (participant, payer) pair.
2. **Pairwise netting** (`pairwise_balances`). Merge duplicates and cancel opposite directions: A→B 700 and B→A 300 become A→B 400; exact cancellation removes the pair. Output sorted by (debtor, creditor). O(n log n) in the number of pairs.
3. **Net balances** (`net_balances`). `net[creditor] += x`, `net[debtor] -= x` for every debt. Positive = is owed, negative = owes. **Invariant:** every debt adds +x and −x, so the sum is exactly 0 (asserted in tests, including 300 randomized ledgers). Zero entries are dropped.

Edge cases covered: no expenses, empty group, single member, remainder paise, full cancellation, multiple payers, expenses in several groups.

The balance response contains three consistent views: `balances` (explicit debtor / creditor / amount list), `owes` (the assignment's name-keyed shape) and `net_balances`.

## Product enhancement: Smart Settlement Suggestions

`GET /groups/{group_id}/settlements`

- **Problem:** after a trip, the pairwise list can be long and chained (A owes B, B owes C...). People want to know the *fewest transfers* that make everyone even.
- **Algorithm (greedy):** compute net balances; put debtors and creditors in two max-heaps; repeatedly take the largest debtor and largest creditor, transfer `min(owed, credit)`, push back any remainder. Each step fully clears at least one person, so at most *(people with non-zero balance − 1)* payments result. O(n log n). Ties break by lowest user id, so output is deterministic. Integer paise throughout; zero transfers never occur.
- **Why this algorithm:** the true minimum number of transfers is NP-hard (it is a subset-sum partition problem). The greedy approach is simple, explainable, fast and bounded by n−1, which is the right trade for a small group.
- **Limitations:** not always the absolute minimum; it ignores who "prefers" to pay whom; and its payments can differ from the real pairwise debts (e.g. it may ask A to pay C directly even though A only ever owed B). That is why both views are kept separate.
- **Read-only:** suggestions never change balances or record any payment. (Recording settlements is the optional bonus feature and is not implemented.)

## API reference

Errors always use `{"error": {"code": "...", "message": "...", "details": [...]}}` with codes `VALIDATION_ERROR` (422), `NOT_FOUND` (404), `CONFLICT` (409), `BUSINESS_RULE_VIOLATION` (422).

| Method & path | Purpose | Success |
|---|---|---|
| `POST /users` `{"name"}` | Create user | 201 `{id, name}` |
| `GET /users` | List users | 200 |
| `POST /groups` `{"name"}` | Create group | 201 `{id, name}` |
| `GET /groups` | List groups (extra) | 200 |
| `POST /groups/{id}/members` `{"user_id"}` | Add member | 201 `{id, name, joined_at}` |
| `GET /groups/{id}/members` | List members | 200 |
| `POST /expenses` `{group_id, paid_by, amount, description}` | Record expense, split equally | 201 |
| `GET /groups/{id}/expenses` | Expense history | 200 |
| `GET /balances[?group_id=N]` | Balances (system-wide or one group) | 200 |
| `GET /groups/{id}/balances` | Same as `?group_id=` | 200 |
| `GET /groups/{id}/settlements` | Smart settlement suggestions | 200 |
| `GET /health` | Liveness | 200 |

**POST /expenses** (`paid_by` is a user id in the request; the response gives the payer's name in `paid_by` like the assignment's sample, plus `paid_by_id`):

```json
{ "id": 1, "group_id": 1, "description": "Dinner", "amount": "1200.00", "amount_paise": 120000,
  "paid_by": "Mohit", "paid_by_id": 1, "created_at": "2026-10-13T04:50:42.611535Z",
  "participants": [ {"user_id": 1, "name": "Mohit", "share": "400.00", "share_paise": 40000},
                    {"user_id": 2, "name": "Rahul", "share": "400.00", "share_paise": 40000},
                    {"user_id": 3, "name": "Ankit", "share": "400.00", "share_paise": 40000} ] }
```

**GET /balances?group_id=1** (after the dinner only):

```json
{ "scope": {"type": "group", "group_id": 1}, "currency": "INR",
  "balances": [
    {"debtor": {"id": 2, "name": "Rahul"}, "creditor": {"id": 1, "name": "Mohit"}, "amount": "400.00", "amount_paise": 40000},
    {"debtor": {"id": 3, "name": "Ankit"}, "creditor": {"id": 1, "name": "Mohit"}, "amount": "400.00", "amount_paise": 40000} ],
  "owes": {"Rahul": {"owes": {"Mohit": "400.00"}}, "Ankit": {"owes": {"Mohit": "400.00"}}},
  "net_balances": [ {"user": {"id": 1, "name": "Mohit"}, "net": "800.00", "net_paise": 80000},
                    {"user": {"id": 2, "name": "Rahul"}, "net": "-400.00", "net_paise": -40000},
                    {"user": {"id": 3, "name": "Ankit"}, "net": "-400.00", "net_paise": -40000} ] }
```

**Validation error** (`amount: -5`):
`{"error":{"code":"VALIDATION_ERROR","message":"Request validation failed","details":[{"field":"amount","message":"Input should be greater than 0"}]}}`

## Sample scenario (verified)

Run against the real server with a real SQLite file. Users Mohit(1), Rahul(2), Ankit(3) in group "Goa Trip".

1. Mohit pays ₹1200 "Dinner" → shares 400 / 400 / 400.
2. Rahul pays ₹100.00 "Taxi" → 100.00 / 3: Mohit 33.34, Rahul 33.33, Ankit 33.33 (remainder paisa to the lowest id).

| Pair | Calculation | Result |
|---|---|---|
| Rahul → Mohit | 400.00 − 33.34 (Mohit owes Rahul) | **366.66** |
| Ankit → Mohit | 400.00 | **400.00** |
| Ankit → Rahul | 33.33 | **33.33** |

Net: Mohit **+766.66**, Rahul **−333.33**, Ankit **−433.33** → sum **0.00**.
Settlement suggestion: Ankit → Mohit 433.33, Rahul → Mohit 333.33 (2 payments clear everything). The same numbers are returned by the live API.

## Testing

`pytest` runs 96 tests (isolated in-memory DB per test, order-independent). Highlights:

| Requirement | Tests |
|---|---|
| User create / list / duplicate / invalid payloads | `test_users_groups.py::TestUsers` |
| Group create, add member, duplicate membership, unknown user/group, empty group | `test_users_groups.py::TestGroups` |
| Expense validation (amount ≤ 0, bad decimals, unknown group/payer, payer not member, single member) | `test_expenses.py::TestCreateExpense` |
| Equal split, remainder paise, exact decimals | `test_expenses.py`, `test_balance_engine.py::TestSplitEqually` |
| History order and details; late member does not alter old split | `test_expenses.py::TestHistory` |
| Balances: example, multiple payers, cancellation, settled, zero-sum, system-wide | `test_balances.py` |
| Settlement suggestions clear all balances, read-only, deterministic, fewer than pairwise | `test_settlements.py`, engine property tests |
| Atomic creation / rollback; DB constraints (payer membership, CHECKs, PK, FK, unique name) | `test_transactions_and_constraints.py` |
| Malformed payloads | `test_users_groups.py`, `test_expenses.py` |

## Docker

```powershell
docker compose up --build        # API on http://localhost:8000, data in the named volume expense_data
docker compose down              # add -v to also delete the data
```
The Docker setup is written following standard practice but **was not built or run in the environment where this project was developed**; please run the command above once to confirm it on your machine.

## Known limitations

- Equal splits only; no custom splits, no recorded settlements (optional bonus features).
- No authentication, no pagination, no expense edit/delete or member removal (history is append-only by design).
- Single currency; the +1 paisa remainder always favours the lowest user ids.
- `create_all` instead of migrations; PostgreSQL support is by design but untested here.
- Settlement suggestions are greedy, not guaranteed minimal.

**With more time:** Alembic migrations, recorded settlements (a `settlements` table feeding the same netting step), custom splits using the existing `expense_participants` table (no schema change needed), pagination, auth, PostgreSQL CI, a Postman collection.
