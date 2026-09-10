# Commercial document design and tailoring

The approved print-light BMAsia A4 design is mandatory for every generated
quotation, invoice, proforma invoice and contract, including Hilton full-text
agreements, Hilton corporate participation packages, master service agreements
and generic participation PDFs. The retired BMAsia design is not a selectable
fallback, including from standalone preview tooling. Previously stored PDFs and
immutable uploaded source binaries are not rewritten by a renderer release.

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
   Supplier signing lines remain blank for manual execution: generated
   contracts never embed Chris Andrews' signature image or a BMAsia stamp.
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
The former quote, invoice and contract live flags are retained only for
configuration compatibility and cannot restore the retired renderer. Previews
remain controlled by the preview flag. Receipt rendering remains separately
configured because a receipt is not an invoice draft.

Native regression coverage: contract PDF routes, direct renewal renderers,
long clauses and zone schedules, contract numbering, unchanged legal text,
no-write previews/MCP, document issuer and financial attribution, quote
conversion, exact tax retention, and frontend form preservation.

## Mandatory contract layout regression gate

The September 2026 contract reviews exposed gaps in text-only QA: nested
`KeepTogether` wrappers forced a small zone schedule to a new page, legacy
negative padding misaligned signing lines, and very long source paragraphs
could paint continuation text into the running header. The V2 adapter now
flattens wrappers, splits explicit legal lines before pagination, and lays out
blank signing areas on shared rows. It does not add signature/stamp artwork,
alter terms, or replace stored documents.

For every contract renderer/layout change, run:

```bash
python -m pytest crm_app/tests/test_contract_layout_regressions.py crm_app/tests/test_contract_pdf_v2.py crm_app/tests/test_contract_signature_blocks.py
```

The geometry checks require a short one-zone agreement to use no more than two
pages, keep the short schedule with the introduction, keep final contract text
with its signing block, align signing-rule baselines, and prove no supplier
signature/stamp artwork is embedded. They also exercise long zone schedules,
additional signatories, long names/POA text, every-page running furniture and
unchanged CRM state.

Export raster-review fixtures with `CONTRACT_LAYOUT_REVIEW_DIR=<private-dir>`
when running the regression file. Vera must inspect every page of the affected
document and representative long/multi-signer cases before calling a release
verified. Cira must check the newly generated PDF, not an earlier attachment,
before the separately authorized document-save/send step. Test success or a
PDF-generation receipt alone is not a visual acceptance or a customer-send receipt.
