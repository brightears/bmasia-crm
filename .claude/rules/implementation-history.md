# Implementation History - BMAsia CRM

> **Full history**: See `docs/IMPLEMENTATION_ARCHIVE.md` for detailed implementation records.
> **Lessons learned**: Key gotchas are documented in MEMORY.md.

## This Week (Feb 28 - Mar 6, 2026)

| Date | Feature | Key Files | Commit |
|------|---------|-----------|--------|
| Mar 11 | Hilton combined PDF: Attachment A + Exhibit D with full signature blocks (image+stamp) | `views.py` | pending |
| Mar 11 | Client Tech Details: default collapsed + preserve scroll/expansion on duplicate/delete/save | `ClientTechDetails.tsx` | `1a84c062` |
| Mar 11 | Revenue recognition: monthly calc for BMAT (1st-start) + zero-balance guarantee | `revenue_recognition_service.py` | `d41569f6` |
| Mar 9 | Fix Ascott template Notices clause: {{venue_names}} → {{company_name}} in DB content (data migration) | `0088` | `cc5f5f38` |
| Mar 9 | Fix QuoteForm: searchable company Autocomplete + load all companies (was Select with page_size:100) | `QuoteForm.tsx`, `Quotes.tsx` | `65f68614` |
| Mar 7 | Client Tech Details: duplicate/clone + group by company with collapsible headers | `views.py`, `ClientTechDetails.tsx`, `api.ts` | `180d949b` |
| Mar 7 | Fix HK revenue accrual timeout: N+1 query elimination (4,372→2 queries) + independent frontend fetches + 30s timeout | `revenue_recognition_service.py`, `RevenueAccrual.tsx`, `api.ts` | `4354b30b` |
| Mar 7 | Auto-generate revenue recognition on invoice create/update | `views.py` | `b3f7024b` |
| Mar 6 | Fix revenue accrual 0% recognition: parallel list for import quarterly data + cumulative balance fix + frontend hint banner | `revenue_recognition_service.py`, `RevenueAccrual.tsx` | `21333cdc` |
| Mar 6 | Fix email sequences cron: SequenceEnrollment.trigger_entity_id UUID→CharField for seasonal string keys | `models.py`, `0087` | `d38fffe4` |
| Mar 6 | Revenue Accrual module: models, service, API, frontend, Excel import, Balance Sheet integration | `models.py`, `revenue_recognition_service.py`, `views.py`, `RevenueAccrual.tsx`, `0086` | `2c58ff5b` |
| Mar 6 | 8 corporate templates: Hilton HPA, Minor PPSA, Ascott Supply Agreement, Centara PPSA (Thailand + International each) + {{rate_per_zone}} variable | `views.py`, `ContractTemplateForm.tsx`, API | `d7b55717` |
| Mar 6 | Fix email sequences cron crash: invalid Contact field names (is_primary_contact → is_primary) | `auto_enrollment_service.py` | `8b1ae239` |
| Mar 3 | Fix contract PDF AnonymousUser crash + custom duration sync | `views.py`, `ContractForm.tsx` | `c5ffe0bd` |
| Mar 2 | Paid invoice UX: receipt visibility, send/resend, status indicators | `InvoiceDetail.tsx`, `Invoices.tsx`, `EmailSendDialog.tsx` | `91eb7c1a` |
| Mar 2 | Receipt/Tax Invoice: auto-generate on mark paid + PDF + email | `models.py`, `views.py`, `email_service.py`, `InvoiceDetail.tsx`, `0085` | `754ecc6c` |
| Mar 2 | Fix contract email PDF empty body (was using broken fallback) | `email_service.py` | `e8b87d3a` |
| Mar 1 | Contact document preferences + CC field in EmailSendDialog | `ContactForm.tsx`, `EmailSendDialog.tsx`, `email_service.py`, `0084` | `9d290559` |
| Feb 28 | Allow editing Active contracts (for date/term changes) | `Contracts.tsx`, `ContractDetail.tsx` | `c71d67a8` |
| Feb 28 | Remove number input spinner arrows from QuoteForm line items | `QuoteForm.tsx` | `b762c8d7` |
| Feb 28 | Fix contract list stale after status change in detail modal | `ContractDetail.tsx`, `Contracts.tsx` | `adc2d437` |
| Feb 28 | Fix "Mark as Signed": PUT→PATCH in updateContract() | `api.ts` | `6119bc4b` |
| Feb 28 | Contract follow-ups for unsigned contracts (Day 5 + Day 10) | `models.py`, `email_service.py`, `send_emails.py`, `0083_contract_followup_fields.py` | `881e79b4` |
| Feb 28 | Fix OpportunityForm: choice expansion + scroll-to-error | `models.py`, `OpportunityForm.tsx`, `0082_opportunity_choice_expansion.py` | `325ed350`, `47aac8cc` |
| Feb 28 | AI Sales Automation Phase 4: Reply detection & smart routing | `reply_detection_service.py`, `check_prospect_replies.py`, `0081_prospect_reply_model.py` | `bee2bb8d` |
| Feb 27 | AI Sales Automation: product knowledge training | `ai_service.py` (SYSTEM_PROMPT enrichment) | `60913e4f` |
| Feb 27 | AI Sales Automation: OpportunityDetail Automation tab | `OpportunityDetail.tsx`, `serializers.py` | `c87bd9c2` |
| Feb 27 | AI Sales Automation: auto-enrollment triggers | `prospect_enrollment_service.py`, `views.py`, `process_prospect_sequences.py` | `50c9dbcb` |
| Feb 27 | AI Sales Automation: default sequences + cron | `0080_default_prospect_sequences.py`, `deployment.md` | `406893e1` |
| Feb 27 | AI Sales Automation: full stack (Phase 1+2+3) | `models.py`, `ai_service.py`, `views.py`, `ProspectSequences.tsx`, `AIEmailDrafts.tsx` | `1956eddd`, `43b04513` |
| Feb 26 | Client Tech: SYB Account Type (Essential/Unlimited) | `models.py`, `ClientTechDetailForm.tsx`, `ClientTechDetails.tsx` | `6f05849a` |
| Feb 26 | Client Tech: BMS/DM platforms + 5 date fields | `models.py`, `ClientTechDetailForm.tsx`, `ClientTechDetails.tsx` | `df2f4a37` |
| Feb 25 | Keith's Tech Support: 5 improvements | `ClientTechDetails.tsx`, `TicketForm.tsx`, `KnowledgeBaseArticle.tsx` | `65c83909` |
| Feb 25 | Documentation restructure (87k→2.8k) | `implementation-history.md`, `IMPLEMENTATION_ARCHIVE.md` | `45e7c87c` |
| Feb 22 | Contract PDF footer: canvas-based (no overflow) | `views.py` | `0bc3dcfd` |
| Feb 22 | Contract PDF validity date: 2-line format | `views.py` | `de3cfc95` |
| Feb 22 | Contract edit restrictions by status | `Contracts.tsx`, `ContractDetail.tsx` | `29081fb0` |
| Feb 22 | Contract editing: 4 bug fixes | `ContractForm.tsx`, `Contracts.tsx` | `93bfeb5d` |
| Feb 20-21 | Flexible contract duration + PDF fixes | Multiple | Multiple |
| Feb 19 | QuickBooks export improvements (4 rounds) | `quickbooks_export_service.py` | Multiple |
| Feb 19 | Client Tech Details module + PDF | `ClientTechDetails.tsx`, `views.py` | Multiple |

## Last Week (Feb 12-18, 2026)

| Date | Feature | Summary |
|------|---------|---------|
| Feb 17 | Email delivery tracking | Tracking pixel, EmailLog API, Email History UI |
| Feb 17 | KB article save fix | category_id/tag_ids field names |
| Feb 17 | Service locations ↔ line items sync | Auto-derive from music line items |
| Feb 16-17 | Contract service locations | New model, replaced EnhancedZonePicker |
| Feb 13 | Contract Draft/Sent status | New lifecycle: Draft→Sent→Active |
| Feb 13 | Visual refresh | Dark sidebar, avatars, music quotes |
| Feb 12 | Email system fix | Python 3.12.8 pin, simplejwt upgrade |
| Feb 12 | Invoice improvements | 5 phases from Pom's feedback |
| Feb 12 | Audit bug fixes | N+1 queries, logo, phone/email fields |

## Key Recent Patterns

- **Detail modal → list sync**: Status changes in detail modals must notify parent list via callback (e.g. `onContractUpdated`)
- **Model choices ↔ frontend options**: Must stay in sync. Mismatch causes 400 errors (e.g. `lead_source`, `contact_method`)
- **PDF footers**: Use canvas-based `onPage` callbacks, not flowables (can't split across pages)
- **Partial updates**: Always use PATCH, not PUT (DRF requires all fields with PUT)
- **Write-only serializer fields**: Frontend sends `field_id`, not `field` (e.g., `category_id`)
- **Contract status lifecycle**: Draft → Sent → Active → Renewed/Expired/Cancelled
- **Service locations**: Auto-derived from line items via `syncLocationsFromLineItems()`
- **QuickBooks IIF**: DD/MM/YYYY dates, negative QNTY for SPL rows, VAT as separate row
- **Email PDF generation**: All send methods (quote/contract/invoice/receipt) must use `RequestFactory` → viewset `pdf()` to generate full PDF. Never use inline fallback generators. `BaseModelViewSet.log_action()` skips audit log for AnonymousUser
- **Invoice PDF shared builder**: `_build_invoice_pdf(invoice, is_receipt=False)` — parameterizes title, metadata, filename for both invoice and receipt PDFs
- **Contact model fields**: `is_primary` (NOT `is_primary_contact`). No `is_decision_maker` field exists. Use `contact_type` for role-based logic
- **bulk_create() loses object attrs**: Never store data as `obj._custom_attr` before `bulk_create()` — use parallel list instead
- **Render cron deploys**: Cron jobs are SEPARATE services — deploying backend does NOT deploy crons. Must trigger each cron's deploy via its own service ID
- **Contract template content in DB**: `ContractTemplate.content` is stored in the database, not code. Use `{{company_name}}` for hotel/company name, NOT `{{venue_names}}` (which gives zone names like "Lobby and Corridor")
- **Revenue recognition dual-mode**: BMAT (Thailand) + service starts on 1st → monthly calc. All else → daily calc. Zero-balance guarantee adjusts last entry for rounding

## Quick Migration Reference (Recent)

| Migration | Purpose |
|-----------|---------|
| `0088` | Fix Ascott template Notices: `{{venue_names}}` → `{{company_name}}` (data migration) |
| `0087` | SequenceEnrollment trigger_entity_id UUID→CharField |
| `0086` | Revenue Recognition module (Schedule + Entry models, deferred_revenue on BS) |
| `0085` | Invoice receipt_number + receipt_sent fields |
| `0084` | Contact document email preferences (receives_quote/contract/invoice_emails) |
| `0083` | Contract follow-up fields (sent_date, first/second_followup_sent) |
| `0082` | Opportunity lead_source + contact_method choice expansion |
| `0081` | ProspectReply model + EmailLog 'sequence' type |
| `0080` | Default prospect sequences (data migration) |
| `0079` | Sales automation (5 models + Opportunity.stage_changed_at) |
| `0078` | ClientTechDetail syb_account_type |
| `0077` | ClientTechDetail BMS/DM platforms + date fields |
| `0076` | ClientTechDetail platform_type |
| `0075` | Quote contract_duration_months |
| `0074` | ClientTechDetail OS/PC Name fields |
| `0073` | ClientTechDetail model |
| `0072` | Email delivery confirmation |
| `0071` | ContractServiceLocation model |
| `0070` | Contract Draft/Sent statuses |
| `0069` | Quote followup tracking flags |
| `0068` | Quote quote_type field |

---

> For detailed implementation notes, patterns, and gotchas, see `docs/IMPLEMENTATION_ARCHIVE.md`
