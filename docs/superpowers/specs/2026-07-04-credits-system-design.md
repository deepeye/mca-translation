# Credit System — Design

**Date:** 2026-07-04
**Status:** Approved for implementation
**Scope:** Character-based credit consumption on translation & review, admin recharge, user-facing balance/trend UI

## Background

CulturalBridge currently provides translation + cultural-adaptation + review with no usage cap. LLM calls cost money and there is no rate limit: a single user can drain budget by repeatedly translating large inputs.

The product asks for a credit-based meter:
- Every character submitted for translation or review consumes 1 credit.
- Deduction happens at completion (not upfront).
- Failed work refunds what was charged.
- Admins top up users; users cannot self-recharge.
- Users see balance, recent consumption, and full transaction history; admins see and adjust all users.

## Goals

1. Add a credits balance to every user (default `1000`), deduct on successful translation/review completion, refund on full failure per language.
2. Add `is_admin` role and a separate `/admin/users` page to view users and adjust credits.
3. Add a `/account` user center page showing balance, 7/30-day consumption chart, and full transaction history.
4. Show balance in the top nav; block translation & review UI with a "contact admin" message when balance is 0.
5. Persist every credit movement (consume, refund, admin top-up, admin revoke, signup bonus) with an audit trail.

## Non-Goals

- No payment-gateway integration. Recharge is admin-driven only.
- No per-language pricing differences; cost basis is the input/source text only, not translation outputs.
- No team/org pooling. Credits are per-user.
- No credit expiration.
- No negative balance. Tasks that would push balance below zero for a sub-step fail at that sub-step only.
- No changes to translation prompt templates or risk-annotation logic.

## Design

### 1. Data model

**`users` table — add two columns**

| Column          | Type    | Default | Notes                            |
|-----------------|---------|---------|----------------------------------|
| `is_admin`      | Boolean | `false` | Role flag; gates admin endpoints |
| `credit_balance`| Integer | `1000`  | Current balance (denormalized)   |

`credit_balance` is denormalized for fast reads (badge, chart) and updated atomically with each transaction. The audit trail (`credit_transactions`) is the source of truth for history.

**New `credit_transactions` table**

| Column      | Type                    | Notes                                                                  |
|-------------|-------------------------|------------------------------------------------------------------------|
| `id`        | UUID PK                 |                                                                        |
| `user_id`   | UUID FK `users.id`, idx |                                                                        |
| `delta`     | Integer                 | Positive = credit added (topup/refund); negative = consumed            |
| `tx_type`   | String(16)              | `consume \| refund \| admin_topup \| admin_revoke \| signup_bonus`     |
| `reason`    | String(255)             | Human-readable; e.g. `"翻译消耗: en"` or `"管理员充值 (admin@x)"`        |
| `job_id`    | UUID nullable           | Set for `consume`/`refund` rows from translation tasks                 |
| `review_id` | UUID nullable           | Set for `consume`/`refund` rows from review tasks                      |
| `created_at`| timestamptz             | server default `now()`                                                 |

Index on `(user_id, created_at desc)` for trend/history queries.

### 2. Cost basis

| Workflow | Cost unit       | Per-language?                                |
|----------|-----------------|----------------------------------------------|
| Translation | `len(source_text)` | Yes — deducted once per successfully translated target language |
| Review — dual  | `len(source_text)`     | N/A (single review call)                  |
| Review — single | `len(translated_text)` | N/A                                       |

All characters count — Chinese, ASCII, emoji, punctuation, whitespace between words. Whitespace-only characters still count.

### 3. Charge / refund timing

Deduction happens **after** successful completion, not at submission. This keeps failed jobs from inflating the meter and lets refund be a simple "did we already charge this unit of work?" check.

**Translation pipeline** (`backend/app/tasks.py:run_translation`):
- Per target language, after `TranslationResult.status` flips to `completed`:
  - call `credits.deduct_for_translation(user_id, source_text, lang, job_id)`
  - if returned `INSUFFICIENT`: flip status to `failed` with `metadata.reason = "insufficient_credits"`, no deduction
- If a language's `status` flips to `failed` (LLM error, validation error, timeout):
  - if a `consume` transaction for `(job_id, language)` exists → emit a corresponding `refund` transaction (idempotent: guard by `metadata` key on consume row)

**Review pipeline** (`backend/app/api/reviews.py`):
- After successful LLM response: `credits.deduct_for_review(user_id, input_len, review_id, mode)`
- On exception (LLM error / 5xx): no deduction → no refund needed
- Insufficient balance → return `402 Payment Required` to caller

### 4. Transaction integrity

Each movement runs in a single SQLAlchemy transaction:

```sql
BEGIN;
  SELECT credit_balance FROM users WHERE id = ? FOR UPDATE;
  -- compute new_balance; refuse if consuming and new_balance < 0
  UPDATE users SET credit_balance = ? WHERE id = ?;
  INSERT INTO credit_transactions (...);
COMMIT;
```

`SELECT FOR UPDATE` serializes concurrent deductions for the same user (rare but possible: simultaneous translation + review submissions).

### 5. API endpoints

```
GET  /api/credits/balance              { balance: int }
GET  /api/credits/transactions?limit   [Transaction]    (newest first)
GET  /api/credits/trend?days=7|30      [{ date: "2026-07-04", consumed: 42 }, ...]
GET  /api/admin/users                  [{ id, username, is_admin, credit_balance, last_active }]
POST /api/admin/users/{id}/credits     body: { delta: int, reason: str }   admin only
GET  /api/admin/transactions?user_id   audit trail scoped to user          admin only
```

New FastAPI dependency `require_admin` (`backend/app/api/deps.py`) wrapping `get_current_user` and checking `user.is_admin` — `403` otherwise.

`POST /api/jobs` and `POST /api/reviews` are extended:
- After auth: read `user.credit_balance`. If `== 0` → `402 Payment Required` with body `{ "detail": "INSUFFICIENT_CREDITS", "balance": 0 }`. (Per-language deductions can still drain a non-zero balance mid-batch; we don't block those upfront since each failing language also drains naturally.)

### 6. Frontend

**Top nav (`frontend/app/(main)/layout.tsx`)**
- Insert a balance badge before `Sign out`: `🪙 {formatNumber(balance)}`
- When `balance === 0`: red styling + tooltip "信用分已用完，请联系管理员充值"
- On click: navigate to `/account`
- Fetched lazily once after login + on focus

**User center `/account` (new page)**
- Big balance number
- Tabs: 7d / 30d → bar chart of `consumed` per day. Project has no chart library today, so render with plain SVG (one rect per day, height proportional to consumed). No new npm dependency.
- Transactions table: time / type chip / delta (+/- colored) / resulting balance / reason
- Pure read-only

**Admin `/admin/users` (new page, admin-only route)**
- Guarded client-side: redirect non-admins to `/workspace` and server-side via `require_admin`
- Table: username / role / balance / last active (latest transaction time) / `[调整]` button
- Adjust modal: signed `delta` input + reason textarea + `[确认]` button → calls `POST /api/admin/users/{id}/credits`
- Click row → drawer/modal showing that user's full transaction history

**Workspace (`/workspace`) and Review (`/review`)**
- When `balance === 0`: render `Alert` at top of input panel: `"信用分已用完，翻译功能不可用，请联系管理员充值"`
- Translate / Review buttons disabled when `balance === 0`, with the same message as tooltip
- On API `402`: surface the message above and keep the user's text intact

**Balance updates after a translation/review completes**
- After a job settles, the workspace's existing `pollJobStatus` callback also `POSTs` to `/api/credits/balance?refresh=1` or simply `setUserBalance` on the global balance store so the nav badge reflects the deduction without a page reload.

### 7. New accounts

The codebase has no `/api/auth/signup` endpoint today — users are added externally (operators create accounts by other means, or admins will gain one as part of this work). The migration sets `credit_balance = 1000` and `is_admin = false` for any user row that lacks them. No `signup_bonus` transaction is needed for existing users; new accounts created via whatever signup path exists in the future will get the default `1000` from the column default and do not need to emit a `signup_bonus` row. (If a `signup_bonus` row is later required for symmetry with admin adjustments, it is a one-line add at the call site.)

### 8. Promoting the first admin

A CLI script `backend/app/scripts/promote_admin.py`:

```bash
python -m app.scripts.promote_admin <username>
```

Sets `is_admin = true` for the named user. No initial admin is created by migration — operator runs this once after deploy. Logged as a `admin_self_promote` audit entry outside the `credit_transactions` table (this is a role change, not a credit movement, so it is out-of-scope for credit audit — kept here only as the call site).

### 9. Migration

```python
# alembic revision
op.add_column("users", sa.Column("is_admin", sa.Boolean, server_default=sa.text("false")))
op.add_column("users", sa.Column("credit_balance", sa.Integer, server_default="1000"))
op.create_table(
    "credit_transactions",
    sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), ForeignKey("users.id"), index=True),
    sa.Column("delta", sa.Integer, nullable=False),
    sa.Column("tx_type", sa.String(16), nullable=False),
    sa.Column("reason", sa.String(255)),
    sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("review_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)
op.create_index("ix_credit_tx_user_created", "credit_transactions", ["user_id", "created_at"])
```

### 10. Testing strategy

- `backend/tests/services/test_credits.py`:
  - Happy-path deduction creates `consume` row, decrements balance
  - Refund emits symmetric `refund` row matching `delta`
  - Idempotency: dedupe via `(user_id, job_id, language)` metadata key → no double-refund
  - Insufficient: `deduct` returns `INSUFFICIENT`, no row written
  - `admin_adjust` accepts any signed delta, records `reason`
  - Trend groups transactions by `created_at::date`
- API integration: `POST /api/jobs` with `balance=0` returns 402; with `balance=200` and 200-char source translating to 3 languages: each completion deducts 200, partial failures refund
- Frontend: badge color, `/account` chart, admin adjust modal — covered with component tests in `frontend/components/account/__tests__/credits-page.test.tsx` and admin tests

## Open questions

None — all major decisions resolved during brainstorming.
