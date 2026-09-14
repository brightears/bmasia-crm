# Real-data CRM reporting pilot

This stage imports narrowly selected observations from BMAsia Sales and Cara,
compares exact IDs with current CRM reads, and produces an operator review.
It does not replace the CRM, enable automatic updates, send messages, run either
source's workflow, or add a new scheduled task. Existing Sales mutation authority
and Cira's document workflow are unchanged.

## Roles

- Theo, Lyra, Riff and Nina remain intended domain reporting sources. The existing
  UID-authenticated collector still accepts only its registered synthetic fixtures;
  this stage does not turn that socket into a live-data feed.
- Cara contributes relationship-care holds and existing follow-up metadata from
  its read-only context database. Its collection age and unknown runtime health
  remain visible. A stored WAITING case is not a newly verified overdue task.
- BMAsia Sales contributes selected facts from its sealed heartbeat reports.
  It already has separately guarded CRM workflows: importing reports does not
  disable, replace, or expand them.
- Cira is the review/document role, not another duplicate observation feed. This
  module does not send Cira a message or give it additional write authority.

Cara and Sales run on a shared operator computer, so imports are labelled
`operator_import_not_process_attestation`. A source name or hash is provenance,
not proof that an independently authenticated agent sent a report.

## Three explicit read-only steps

1. Create a private `bmasia.live-pilot-scope.v1` JSON file containing a UUID
   `scope_id`, an aware `expires_at` in the next seven days, and 1–10 `accounts`.
   Each account contains `source` (`cara` or `bmasia_sales`), exact UUID
   `company_id`, `record: {collection, id}`, and absolute `source_path`.
   Source paths are limited to the configured Cara context database or Sales
   report directory; credentials, mail bodies, outboxes and executors are not
   inputs. Store scope and output outside Git with private permissions.
2. On the source computer, run `tools/agent_crm_source_observations.py --scope
   PRIVATE_SCOPE`. It selects small metadata projections, preserves absent versus
   null values, retains fixed holds, and returns stable observation IDs. Individual
   source failures are reported without raw provider prose. Capture stdout privately.
3. Under Vera's existing CRM read identity, run
   `tools/agent_crm_pilot_snapshots.py --scope PRIVATE_SCOPE`. It uses only the
   configured HTTPS MCP endpoint and `query_data_collections`, exact UUID matches,
   narrow fields and duplicate detection. It neither loads another agent's
   credentials nor invokes mutation tools. Preserve stdout even on exit 2: that
   can contain useful rows alongside missing/error rows. Compare outputs with
   `tools/agent_crm_pilot_review.py --observations PRIVATE_OBSERVATIONS --snapshots
   PRIVATE_SNAPSHOTS`.

Python 3.11+ is required. Pure tests run with `python -B -m unittest discover
-s tests/agent_live -v`; the existing CRM test environment supplies the MCP SDK
for the live snapshot step. No additional hosted service or subscription is used.

## Interpretation and gates

The comparison checks exact company foreign keys, source and snapshot timestamps,
duplicates, missing fields, and current record versions. Sources older than 24
hours remain labelled stale even when their values agree with today's CRM.
Missing evidence is unknown, not clearance. Cara's attention cases are not turned
into invented contact-field changes. Every output has empty `proposed_edits`,
zero CRM writes, no customer outbound, and automatic updates disabled.

Do not call a source connected or live based on a one-off operator import.
Production reporting requires separately validated producer wiring and health;
source authority, freshness and deduplication must be preserved. The next write
stage needs the operator-reviewed real-data results and explicitly agreed fields
and owners; it must re-read record versions and hold ambiguity/conflicts. Contract,
invoice, pricing, legal identity, permission and customer-send effects are outside
this pilot. Approved print-light documents and blank signature/stamp artwork are
unchanged.

## Recovery

There is no daemon, timer, database migration, CRM mutation or queue write to roll
back. Stop invoking the importer/snapshot commands to stop the pilot. Retain the
private evidence only for the agreed review/retention period. Reverting this
release removes the tools and additive read projections; it does not revert CRM
data or affect the existing synthetic collector.
