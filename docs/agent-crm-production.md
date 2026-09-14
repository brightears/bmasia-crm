# Agent-maintained CRM production lane

The existing CRM remains authoritative. Comp AI CRM is not installed. No
customer data is transferred to a new vendor. Commercial PDF rendering is
unchanged: approved print-light layout, no signature/stamp artwork.

## Operating components

- Vera private collector accepts actual source snapshots and explicit,
  field-scoped correction intents through a local Unix socket.
- A fixed, credential-free supervisor exports Theo/Lyra activity ledgers,
  Riff queue metadata and Nina workstream hash/mtime every five minutes. Each
  exporter runs under its own exact Linux UID. These are local observations,
  not a complete business inventory or proof of completed customer work.
- Cara and BMAsia Sales have pure metadata-only local exporters. They do not
  trigger source scans, send messages, mutate a source, or call a provider.
  A Vera task heartbeat imports them while the Mac and Codex are available.
  Existing Cara/Sales operational schedules retain their own authority.
- The Vera worker validates exact CRM IDs/company binding, version and before
  values, then routes eligible corrections to Cira. Only Cira calls the
  authenticated writer. The worker independently reads back the requested
  fields; acceptance, a queue state and a model assertion are not completion.

## Agent workflow

For a verified new fact encountered during an already authorized customer
task, read the exact CRM record and company first. If the field is already
current, do not submit a correction. Otherwise prepare one private JSON file
with this exact envelope (placeholders below are not usable customer data):

```json
{
  "schema": "bmasia.agent-correction.v1",
  "source": "lyra",
  "event_id": "UUID unique to this exact intent",
  "observed_at": "timezone-aware actual evidence timestamp",
  "company_id": "exact CRM company UUID",
  "record": {"collection": "contact", "id": "exact CRM record UUID"},
  "expected_version": "updated_at from the fresh CRM read",
  "changes": {"title": {"before": "exact current value", "after": "verified new value"}},
  "evidence": [{"kind": "email_message", "reference": "exact retrievable message reference", "sha256": "actual evidence digest"}],
  "reason": "short factual reason without copied email prose"
}
```

Run `/usr/local/bin/bmasia-agent-crm submit --file /absolute/private/request.json`.
Never invent a company ID, before-value, timestamp, evidence hash or reference.
An authenticated account and a matching hash do not prove a fact. Cira must
independently retrieve/validate evidence or hold the request.

`/usr/local/bin/bmasia-agent-crm status` reads the caller's own receipt summary.
Vera sees all sources. `PENDING` is accepted for validation; `HOLD` requires
reconciliation or a genuine missing fact; `VERIFIED` means Cira returned success
and the requested values were independently read back. `ALREADY_CURRENT` is a
read-only no-op. Do not resubmit an uncertain intent with a different event ID.
The durable event-ID/content hash has no TTL. Conflicts and stale before-values
are held. Interrupted/uncertain writes are not automatically replayed.

Allowed routine metadata: Theo contact title/department/last-contact and
opportunity qualification/nonterminal stage/dates; Lyra and Cara contact
metadata; Sales opportunity metadata; Riff ticket priority/nonterminal status;
Nina zone notes. Actual schemas remain authoritative. No record creation,
deletion, identity re-binding, contacts/email addresses, pricing, currencies,
banking, contract/invoice/quote changes, terminal outcomes or customer sends
are authorized by this lane. Existing owner approvals still apply where
required. Nina remains on-demand for Norbert/assigned LINE groups; no new
estate sweeps, client-design ownership or proactive work is created.

Existing approved document and commercial workflows continue through Cira.
Do not duplicate an existing Cira request or the Sales project's guarded writer.

## Cira requirements

For `vera:correction:<hash>` with `guarded_update_required`, independently verify
the exact company/record, original-source evidence and requested field values.
Use `update_record(collection,id,data,expected_version,expected_values)` with
the unchanged version and before-values. Never drop the guard or retry with a
new version to force a change. If unavailable, stale, conflicting or factually
unverified, return a held/rejected response. If values are already current,
return already_current without any CRM mutation or audit create. Preserve the
original request ID/key, then independently read back after any actual update.

## Health and limitations

Transport freshness is different from evidence freshness. A successful import
of a four-day-old report is not fresh business evidence. `coverage.complete`
means the named source store was fully enumerated, not the CRM or all agent
work. Native stores explicitly retain `agent_inventory_complete=false` and
`legacy_baseline_complete=false`. Unbound and failed rows remain visible and
cannot become CRM changes. Cara attention cases do not imply contact edits;
Riff queue completion does not imply ticket resolution; Nina prose is not
parsed into verified customer facts. Partial snapshots preserve prior rows
without silently declaring them current; old observations expire after 30 days.
Correction receipts remain private durable audit records (no raw mail bodies).

Operator checks: exact three `vera-agent-production-*.service` units, their
journals, then the collector `status`. No unrelated service or legacy poller
should be started. Worker throughput is bounded to one new request/minute;
outbox overload is rejected rather than dropped. No model is invoked on an
unchanged source export.

## Deployment and rollback

Install tested code under root-owned versioned
`/usr/local/lib/bmasia-agent-production/releases/`, switch `current`, install
the three exact units and private Vera-owned state directory. Existing
synthetic-only collector/state stay separate as rollback history; production
never accepts fictional fixtures as live evidence. CRM API guard deployment
must be Live before starting the correction worker.

Rollback: stop the three exact production units, retain the private database,
restore the previous root-owned code symlink and backed-up instruction files.
Do not delete, rewrite or roll back CRM records automatically. If a correction
is uncertain, reconcile exact persisted values and Cira receipts first.

Tests: `python -m pytest tests/agent_production
crm_app/tests/test_agent_correction_concurrency.py`; native fake-database tests
must run without production DATABASE_URL. Existing commercial document tests
remain required for a CRM release. Never make a fake customer edit to prove
the production write path.
