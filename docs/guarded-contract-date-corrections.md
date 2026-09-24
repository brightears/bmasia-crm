# Guarded Sent-contract date corrections

This is a Cira-only CRM writer lane for routine, source-verified term corrections
on an existing **Sent but unsigned** contract. It does not send a document,
alter a contract's status or number, or approve a signed-contract amendment.

Call `update_record` with the exact contract UUID, a nonempty subset of
`start_date` and `end_date` as canonical `YYYY-MM-DD` strings, the current
serialized `updated_at` in `expected_version`, and `expected_values` containing
exactly the same keys with their current serialized values. The authorization
context is a JSON string with exactly these keys:

```json
{
  "kind": "routine_contract_date_correction",
  "requested_by": "norbert",
  "source_reference": "traceable message or thread reference",
  "reason": "brief correction description"
}
```

`requested_by` is exactly one of `norbert`, `lyra`, or `theo`. Cira must
authenticate its writer and verify the actual source before forwarding; the
context records provenance and is not itself proof of the sender. The source
reference and reason must be nonempty, trimmed, printable strings (at most 512
and 1000 characters respectively). No fresh owner approval is required for
routine corrections under the standing instruction, but an ambiguous or
commercially material change must still be held for review.

The CRM locks the exact row, requires `status=Sent`, rejects any associated
`ContractDocument` with `is_signed=true` or a `signed_date`, validates the
resulting complete `start_date <= end_date` interval, and checks version and
before values before saving. It then independently reads back the changed
dates and verifies company, contract number, status, and sent date were not
changed. A matching `AuditLog` entry is written in the same transaction;
failure rolls back both the date change and audit. The response includes the
post-version and audit ID. Cira must independently read back the exact record
and audit before treating the correction as complete. The unguarded MCP path
refuses date edits on an existing Sent contract.

The authenticated contract detail API exposes `contract_documents` with
`is_signed` and `signed_date` for Cira's preflight. An empty list means no
signed document is recorded in CRM; it does not prove that no off-system signed
copy exists. If evidence suggests one, hold the correction for the signed
amendment workflow. The CRM's transaction-time document check remains
mandatory even after Cira preflight.
