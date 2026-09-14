# Agent-maintained CRM: shadow stage

Owner: Vera (code), Cira (any eventual customer-record/document writes).
Decision: Norbert approved the staged existing-CRM approach on 13 September 2026.

## What this release does

The existing BMAsia CRM remains the sole customer system of record. A separate,
private SQLite ledger records source-bound proposals, comparisons, exceptions
and follow-ups. It has no CRM write, mail, HTTP or model client. Its only writes
are to its own explicitly selected shadow database. No production database
migration, new API, credential, scheduler or agent policy is introduced by the
ledger itself. The separately approved synthetic transport is described below.

The command-line review is an operator review artifact, not a new CRM UI or an
automatically monitored dashboard. No live customer reporting is connected.
`ready_for_cira_review` means reviewable proposal, never applied or approved.
Even matched evidence bytes establish provenance, not the truth of a claim.

The approved print-light A4 quotations, all contracts (including Hilton),
invoices and proformas are unchanged. BMAsia signature/stamp artwork stays blank.
This feature cannot add contract clauses, customer remarks or payment terms.

## Included components

- `crm_app/services/agent_shadow.py`: strict versioned report validation,
  deterministic policy/comparison and durable private shadow ledger.
- `tools/agent_crm_shadow.py`: dependency-free synthetic exercise, local trusted
  ingestion and JSON/Markdown review. Does not initialize Django.
- `manage.py agent_crm_shadow_snapshot`: optional exact-ID, one-query read-only
  projection from the current CRM models. No name-based matching or bulk scan.
- `tools/agent_shadow_candidate/`: reproducible static compatibility probe
  against pinned Comp AI source. Not running-app integration evidence.
- `deploy/agent-shadow/`: the separately authorized, Linux UID-authenticated
  synthetic report-only channel; see [channel operations](agent-report-channel.md).

There is no apply/promote/send/activate operation. Routine ingestion consumes no
model tokens. This does not measure the cost of producing reports upstream.

## Report and trust contract

`bmasia.agent-report.v1` requires precisely:

```json
{
  "schema": "bmasia.agent-report.v1",
  "event_id": "00000000-0000-0000-0000-000000000001",
  "reporter": "lyra",
  "observed_at": "2026-09-13T12:00:00+00:00",
  "record": {"collection": "contacts", "id": "00000000-0000-0000-0000-000000000101"},
  "changes": [{"field": "title", "before": "", "after": "Synthetic manager"}],
  "evidence": [{"kind": "agent_receipt", "reference": "synthetic:lyra", "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],
  "follow_up": null
}
```

This example is fake and its hash is illustrative, not verified evidence.
IDs identify existing exact records; this stage cannot create accounts or
invent identifiers. Use a new event ID for a deliberate revision. Changed
content under an existing event ID is a conflict, never an overwrite.
Collision attempts retain the bounded attempted report and trusted context.
An identical retry preserves the original historical assessment; it never
silently reassesses a changed CRM snapshot. If evidence verification is
downgraded, the retry instead produces an unverified-source exception. To
upgrade previously unverified evidence, submit a deliberate new event ID and
a fresh snapshot; original receipts remain immutable.

The context is a **separate trusted operator/adapter input**, not part of an
agent's payload. It uses `bmasia.agent-shadow-context.v1`, `sender`, `request_id`,
`report_sha256`, `verified_evidence_sha256`, `verified`, and `environment`
(`synthetic` or `shadow`). A producer must never supply its own context.
Hashes use sorted-key, compact UTF-8 JSON with non-finite values rejected.

The CLI is not an authentication service. A local operator can supply a trusted
context for tests; that is not proof that a named production agent submitted
it. In a future live adapter, set verification only after authenticating the
submitting Unix account and independently resolving the exact evidence bytes.
Claimed references or hashes alone are insufficient. Never fetch an arbitrary
URL or filesystem path from a report.

Snapshot input contains only `collection`, `id`, `observed_at`, `updated_at`
and the exact projected `fields`. A snapshot must be recent and its identity
must bind to the report and be observed no earlier than the report. Matching a supplied `before` value is advisory; any
later write still needs a fresh CRM version check and Cira's normal authority.

Initial reviewable field scope is deliberately narrow:

- Theo: opportunity stage, contact/follow-up/expected-close dates, pain points
  and decision criteria; contact title, department and last-contact timestamp.
- Lyra: contact title, department and last-contact timestamp.
- Riff: ticket status and priority.
- Nina: zone programme notes, not zone identity or technical online status.

These are proposal-routing scopes, **not CRM write permissions**. Unknown fields
go to manual review; malformed envelopes are rejected. Contract, invoice,
quotation, legal-entity, pricing, payment, consent and activation changes cannot
be promoted through this component. The current schema supports observations
expressed as before/after proposals, not the full universe of CRM activities.

## Reproducible synthetic exercise

From repository root, choose a new directory inside an existing private parent:

```bash
python3 tools/agent_crm_shadow.py demo --directory /absolute/private/path/new-demo
python3 tools/agent_crm_shadow.py report --ledger /absolute/private/path/new-demo/shadow.sqlite3 --format markdown
python3 -m unittest discover -s tests/agent_shadow -v
```

The demo uses four fictional source owners and UUIDs, each with an initial
report, an identical replay and a changed-content collision. It also submits
unverified evidence. It creates only synthetic fixtures, a shadow SQLite ledger,
receipts and a review. It does **not** test production Unix sender identities.
Do not mix synthetic and real shadow data; the ledger enforces one environment.

For a future approved live-shadow case, a trusted operator can generate an exact
snapshot (stdout may contain customer data; keep it in a private workspace):

```bash
python manage.py agent_crm_shadow_snapshot --collection contacts --record-id EXACT-UUID --fields title department
python3 tools/agent_crm_shadow.py ingest --ledger PRIVATE-LEDGER --report REPORT.json --context TRUSTED-CONTEXT.json --snapshot SNAPSHOT.json
```

Do not paste secrets, raw mailbox bodies or full documents into reports. Use
short fact values and immutable evidence references. The ledger is private but
not encrypted; no indefinite production retention policy has been approved.
Review access, retention and backup before collecting real customer reports.

## Live-customer activation gates (still closed)

The live Cira inspection found that the existing shared intake accepts an
asserted sender name; Riff/Nina lack an active report route. Do not reuse that
channel as authenticated report ingestion and do not widen the CRM write
allowlist just to carry reports. Current Cira dispatch may invoke a model.

Norbert authorized the separate synthetic channel on 14 September 2026. Steps
1, 2 and synthetic acceptance in step 4 are its scope; steps 3 and 5 remain
separate approvals, and no producer workflow automatically submits live data:

1. A separate Vera-owned local report-only Unix socket, with kernel peer-UID
   identity, bounded payloads and server-constructed context. Revalidate actual
   runtime UIDs at activation. No shared relay that erases the original UID.
2. Per-source clients for Theo, Lyra, Riff and Nina, without changing their CRM
   mutation authority or customer-send rules. No Cira queue/model fallback.
3. A small approved read-only account scope, retention and evidence resolver;
   unresolved email/ticket references must remain unverified.
4. Synthetic acceptance with each real runtime UID, crash/retry tests and exact
   receipt readback before live-shadow monitoring is enabled.
5. Only after shadow results are reviewed: separately approved Cira promotion
   of a narrow class of factual updates with fresh reads, version checks,
   authority, audit and readback. Never infer permission from a shadow receipt.

Pilot success should measure reporting coverage by source, evidence verification,
duplicates/conflicts, overdue follow-ups, lag and cost per accepted factual
update. Missing sources are `no_data`, not successful synchronization. Define
numeric targets and the account list with the live-pilot approval.

Comp AI remains uninstalled and receives no customer data. Its static probe
does not establish API/runtime/auth behavior. Retaining the BMAsia commercial
backend avoids losing contracts, invoices, zones, renewals or the approved design.

## Recovery and deployment

The ledger adds files only. No HTTP route, model, migration, renderer or existing
workflow changes. The optional channel adds one isolated Vera service; use its
documented stop/disable procedure before removing its tooling. Retain private
receipts for audit if any real pilot was approved.
Never point the ledger at a CRM SQLite database. It rejects unrelated database
tables and separates synthetic/shadow environments.
