# CRM agent-first self-audit — 2026-07-02

Method: 6 parallel subsystem auditors (agent-surface, templates, funnel-gap, bug-hunt, doc-pipeline, agent-ergonomics)
→ adversarial verification of every claimed bug. **91 findings · 39 claimed bugs · 18 CONFIRMED · 0 refuted.**
Report (visual): claude.ai artifact `audit-v1`.

## Shipped during the audit
- `a5f33bc` — MCP `update_record`/`create_record` surface silently-dropped patch keys (read-back of persisted values + `warning_ignored_keys` with did-you-mean hints; all-dropped patch refused). Ends the false-success class for agent writers.
- `5b8c2e0` — **security: 3 live unauthenticated holes closed.** (1) `/reset-admin/` + `/setup-admin/` — anon superuser takeover recreating admin with fixed pwd `bmasia123` (routes removed, view disabled). (2) `StaticDocumentViewSet` AllowAny→IsAuthenticated (anon could publish forged legal T&Cs served on every contract pack). (3) `AutomationViewSet` AllowAny→IsAuthenticated (anon `test-run` could email customers). **ACTION: rotate the admin password — `bmasia123` is compromised.**
- `f90d466` — **renewal endpoint fixed.** `duplicate_for_renewal` referenced 8 nonexistent Contract fields → HTTP 500 on every call since 2026-01-14 (the native renewal flow never worked; BR3's Draft fix `2904baa` edited a block that always crashed). Now real field names + copies service_items (M2M), service_locations, line_items; sets `lifecycle_type='renewal'`. **Verify on a live test renewal.**

## Confirmed bugs still open
Ready to fix (T1): revenue snapshot billing_entity slug/display mismatch (matches 0 contracts, `revenue_tracking_service.py:444`); MCP line-item create broken (parent FK read-only, `serializers.py:980`); line-item writes don't re-total parent (`serializers.py:1067`); Quote→Contract convert endpoint missing (frontend calls phantom endpoints, `api.ts:506`); MCP query schemas wrong for 6 collections (`mcp.py:119`); corporate/participation template content ignored by renderer (`views.py:1307`).
Needs Norbert decision (T3): churn/zone-cleanup gate on invalid `'Terminated'` status (`revenue_tracking_service.py:98`, `signals.py:42`) — needs churn-semantics call; `start.sh` RESET_DB can wipe prod DB on boot (`start.sh:12`) — confirm removal.
Long tail: no status state-machine; nothing expires contracts past end_date; MCP writes bypass AuditLog; no low-privilege agent token; optimistic-locking convention-only.

## Your two contract scenarios
- **One-off format:** today impossible without polluting the GLOBAL template list, or you're locked to the hard-coded clause skeleton. Fix: per-contract full-document body override, or scoped one-off templates (company FK + is_one_off, hidden from the shared dropdown).
- **Ingest a corporate contract → template:** no path today (templates aren't even on MCP). Fix (staged): expose templates to MCP + a preview-without-saving tool; then an ingest tool (upload → extract text → agent fills `{{vars}}` → preview → approve).
- **Risk under both:** template content is live-rendered, unversioned, unaudited — an edit rewrites every future AND re-downloaded PDF. Fix: **snapshot-on-Sent** (freeze the signed artifact) + audit template edits.

## Retiring the Google Sheets
Missing: expiring-by-month "renewal book" view; zones+value by product (SYB vs BB) rollup; funnel↔CRM parity report (the trust gate). Partial: corporate-group rollup; paid-at-a-glance; quarterly-billing automation. Missing (low): hardware-sale classification.
**Highest-leverage build:** a `GET /contracts/renewal-book/?year&month` endpoint (+ MCP tool) that returns one funnel tab (rows + product totals), DB-side, agent-first — plus a monthly parity report as the evidence to justify the switch.

## Ideas
Generate the MCP schema from the models + drift test; teach-through-errors (return the legal alternatives on every rejection); tax as one overridable service; snapshot every signed document.
