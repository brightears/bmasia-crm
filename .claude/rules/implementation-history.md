# Implementation History - BMAsia CRM

> **Full history**: See `docs/IMPLEMENTATION_ARCHIVE.md` for detailed implementation records.
> **Lessons learned**: Key gotchas are documented in MEMORY.md.

## This Week (Feb 19-28, 2026)

| Date | Feature | Key Files | Commit |
|------|---------|-----------|--------|
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

- **Model choices ↔ frontend options**: Must stay in sync. Mismatch causes 400 errors (e.g. `lead_source`, `contact_method`)
- **PDF footers**: Use canvas-based `onPage` callbacks, not flowables (can't split across pages)
- **Partial updates**: Always use PATCH, not PUT (DRF requires all fields with PUT)
- **Write-only serializer fields**: Frontend sends `field_id`, not `field` (e.g., `category_id`)
- **Contract status lifecycle**: Draft → Sent → Active → Renewed/Expired/Cancelled
- **Service locations**: Auto-derived from line items via `syncLocationsFromLineItems()`
- **QuickBooks IIF**: DD/MM/YYYY dates, negative QNTY for SPL rows, VAT as separate row

## Quick Migration Reference (Recent)

| Migration | Purpose |
|-----------|---------|
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
