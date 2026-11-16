# Cara customer-care read integration

## Scope and defaults

The separate Cara principal can read only these GET endpoints:

- `/api/v1/cara/capabilities/`
- `/api/v1/cara/customer-care/`

It is not a Django user, generic API bearer, Rene credential, or general CRM
writer; its only writes are the two switched care endpoints described below.
Session authentication and unrelated tokens do not grant access. On the read
endpoints all non-GET methods and unknown/duplicate query parameters are denied. Empty or expired
credential settings disable access. Responses are private and `no-store`.

Configure `CARA_CUSTOMER_CARE_TOKEN_SHA256` and
`CARA_CUSTOMER_CARE_TOKEN_EXPIRES_AT` using the accountable deployment operator.
Only a SHA-256 digest of a separately generated, high-entropy Cara bearer is
stored by this server. The plaintext token belongs only in Cara's private
runtime, never Git, command arguments, deployment logs, or these documents.
Do not use `mint_agent_tokens --agent cara`, which creates a broader role.

The projection provides active-contract company identities, contact preference
flags, subscription dates, support metadata/counts and positive CRM renewal
activity. It includes contradictory inactive-company flags for review instead
of silently dropping active subscriptions. At most 50 accounts and 25 related
records of each kind are returned. All truncated sets are explicit. It never
reads notes, support descriptions, email bodies, attachments, remote-access
details or financial values. Relationship personalization comes from separately
authorized email history, not this metadata projection.

Complete cross-agent history and absence of formal renewal activity cannot be
inferred from CRM silence. Those fields remain UNKNOWN unless positive CRM
activity provides a hold. A CRM email log is not a Gmail delivery guarantee.

## Care-touch and care-summary writes

Two write endpoints accept the same Cara bearer (no session, JWT or DRF token),
and only while `CARA_CARE_WRITES_ENABLED` is true. It defaults to off; when off
both return 403 "Cara care writes are disabled" and the capability lists are
unchanged (`care_writes_enabled: false`). The read endpoints stay GET-only.

- `POST /api/v1/cara/touches/` records one append-only `CareTouch` (strict JSON,
  unknown keys and query parameters refused). `idempotency_key` makes retries
  safe: same key and same body returns 200 `replayed: true`; same key with a
  different body, or a (`mailbox`, `gmail_message_id`) already stored under
  another key, returns 409. Only a `check_in` with `source=send` and a contact
  moves that contact's `last_contacted`, and never backwards; the old value is
  kept on the touch (`previous_last_contacted`). `source=gmail_backfill` needs a
  `backfill_batch` and never changes contacts.
- `PUT /api/v1/cara/companies/<uuid>/care-summary/` replaces the company's care
  summary (max 2000 characters) under an optimistic lock on
  `expected_updated_at` (null for the first write); a stale value returns 409
  with the current timestamp. The website and MCP show these fields read-only.

Each write leaves one `AuditLog` row with the auth method and principal, never
the summary text or email addresses. A backfill batch is reverted with a dry
run first, then execute, in a Render one-off shell:

```bash
python manage.py shell -c "from crm_app.services.care_touches import revert_backfill_batch as r; print(r('<batch>'))"
python manage.py shell -c "from crm_app.services.care_touches import revert_backfill_batch as r; print(r('<batch>', execute=True))"
```

The projection adds `care_summary`, `care_summary_updated_at`,
`last_care_touch`, `last_care_check_in` per account and `current_by_date` per
contract row. These fields are part of `evidence_sha256`, so a new touch or
summary changes the account's evidence hash. Unlike the original read patch,
this addition ships a migration (`0105_care_touch`: one new table and three
nullable/defaulted company columns).

## Reversible CRM quarterly handover

`CARA_QUARTERLY_OWNER` defaults to `legacy`, preserving existing behavior.
Set it to `cara` only as part of a verified customer-care takeover. This holds
the direct quarterly sender, automatic quarterly enrollment and already queued
automatic quarterly step execution. Existing rows and attempts remain intact;
formal renewal paths are not changed. Invalid settings fail closed. Expiration
of Cara's credential never automatically restores the old sender.

The capability advertises ownership only for `CRM_QUARTERLY_SENDERS_ONLY`.
It does not establish ownership of Lyra or any other agent's check-ins. The
operator must separately reconcile those lanes and pending deliveries before
activation. Rollback to `legacy` is explicit, after reconciling Cara's uncertain
or accepted sends; never operate both owners concurrently.

## Verification and rollout

Run synthetic tests as described in `tests/cara_readonly/README.md`, review the
exact diff, publish through the authorized owner Git/Render workflow, and
verify the deployed commit plus a live Cara capability. No schema migration,
dependency update, boot script change or customer-record mutation is included
in this patch. The repository's existing deployment hooks still perform their
normal migration/seed checks; confirm the live migration state before rollout.
Do not equate a Git push or process-health check with a successful Cara read.
