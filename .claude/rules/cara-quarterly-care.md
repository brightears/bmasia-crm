# Cara customer-care read integration

## Scope and defaults

The separate Cara principal can use only these GET endpoints:

- `/api/v1/cara/capabilities/`
- `/api/v1/cara/customer-care/`

It is not a Django user, generic API bearer, Rene credential, or CRM writer.
Session authentication and unrelated tokens do not grant access. All non-GET
methods and unknown/duplicate query parameters are denied. Empty or expired
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
