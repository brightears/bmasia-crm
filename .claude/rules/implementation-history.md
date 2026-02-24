# Implementation History - BMAsia CRM

> **Full history**: See `docs/IMPLEMENTATION_ARCHIVE.md` for detailed implementation records.
> **Lessons learned**: Key gotchas are documented in MEMORY.md.

## This Week (Feb 19-23, 2026)

| Date | Feature | Key Files | Commit |
|------|---------|-----------|--------|
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

- **PDF footers**: Use canvas-based `onPage` callbacks, not flowables (can't split across pages)
- **Partial updates**: Always use PATCH, not PUT (DRF requires all fields with PUT)
- **Write-only serializer fields**: Frontend sends `field_id`, not `field` (e.g., `category_id`)
- **Contract status lifecycle**: Draft → Sent → Active → Renewed/Expired/Cancelled
- **Service locations**: Auto-derived from line items via `syncLocationsFromLineItems()`
- **QuickBooks IIF**: DD/MM/YYYY dates, negative QNTY for SPL rows, VAT as separate row

## Quick Migration Reference (Recent)

| Migration | Purpose |
|-----------|---------|
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
