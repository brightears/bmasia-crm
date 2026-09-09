# Commercial document design and tailoring

The approved print-light BMAsia A4 design is shared by quotation, invoice,
standard contract, master service agreement, and generic participation PDFs.
Maintained Hilton corporate-native forms retain their source format and legal
integrity gates. Previously stored PDFs and uploaded standard-terms binaries
are not rewritten by a renderer release.

## Vera / Cira workflow

1. Read `get_commercial_document_context(collection, id)` before editing. It
   returns the current record, effective issuer, writable fields and contract
   template slots. This tool does not save, reserve a number or send anything.
2. On an authorized document request, use CRM CRUD to change only the requested
   fields. A named template is optional for a standard agreement. Preserve
   approved principal and standard terms; `notes` are internal only.
3. Set document `billing_entity` for a one-off issuer exception, independently
   of currency and customer country. Blank retains the Company fallback.
   Never change the Company merely to issue one Thailand document in USD to a
   Hong Kong customer. Set the instructed tax treatment explicitly.
4. Quotations support exact line descriptions, `payment_schedule` and
   `terms_conditions` (the customer-facing payment prose). Contract fields are
   `preamble_custom`, `payment_custom`, `activation_custom`, `custom_terms`,
   `payment_schedule`, `custom_service_items`, locations and signatories.
5. Full templates may expose `{{preamble}}`, `{{payment_clause}}` /
   `{{payment_terms}}`, `{{activation_clause}}`, `{{additional_terms}}`,
   `{{payment_schedule}}`, and `{{service_items}}`. Additional terms and a
   schedule are inserted before signatures when their slots are absent. An
   exact clause already present is not printed twice. A replacement without a
   matching slot returns `422 clarification_required`, including the field and
   next action. Create a tailored template copy with the identified clause
   replaced by its slot; do not overwrite shared legal wording or append a
   contradictory paragraph. Template absence alone is not a blocker.
   Issuer-neutral copies can use `{{issuer_name}}`, `{{issuer_address}}`,
   `{{issuer_tax_id}}`, `{{issuer_registration_number}}`, `{{issuer_bank}}`,
   `{{issuer_account}}`, and `{{issuer_swift}}`. Fixed references to the other
   BMAsia supplier or its remittance details require clause-level tailoring.
6. Review `GET /api/v1/contracts/{id}/preview-pdf/` (equivalent quote/invoice
   routes already exist). These watermarked responses perform no document,
   audit, sequence or status writes. Normal MCP PDF generation is also
   non-mutating unless its separate renewal-number option is explicitly used.
7. Check effective issuer, currency, price, tax, dates, legal wording, placement
   and all pages before the existing authorized save/send workflow. PDF errors
   retain structured evidence through MCP. A successful PDF is not a send receipt.

Quote conversion preserves explicit payment text, schedule, issuer and tax
amounts. Wording-only edits preserve existing prices/tax. Issuer changes to an
issued invoice, receipt-bearing invoice or one with recognition schedules
require a deliberate reissue/reconciliation, not a silent ledger reassignment.

## Deployment and verification

Migration 0098 adds three blank optional issuer columns and an empty contract
payment-schedule column; it does not alter customer defaults or legal templates.
Migration 0099 merges this branch with the existing Rene 0098 migration and
has no database operations. The release tests inspect the real migration graph
as well as the isolated functional-test schema.
`COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE` controls standard/master/generic
participation rendering; previews remain available via the preview flag.
Receipt live rendering remains separately disabled.

Native regression coverage: contract PDF routes, direct renewal renderers,
long clauses and zone schedules, contract numbering, unchanged legal text,
no-write previews/MCP, document issuer and financial attribution, quote
conversion, exact tax retention, and frontend form preservation.
