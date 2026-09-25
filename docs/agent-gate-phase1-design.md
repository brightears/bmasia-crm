# Phase 1 — Agent gate in the CRM (design note)

Status: **DESIGN FOR REVIEW — rev 2 (addresses Vera's CHANGES_REQUESTED, INC-20260925-02b84f)** · 2026-09-25 · Author: CRM desk (Claude Code) · Reviewer: Vera ·
Approver: Norbert. Implementation starts only after Vera's review and Norbert's go.

## In one paragraph (for Norbert)

Today "only Cira writes to the CRM" is a promise the agents make, not something the CRM
checks. Every agent login is an **Admin** that can change or permanently delete anything, and
most agent changes leave no record of which agent made them. Phase 1 moves the gate *into the
CRM*: each agent gets its own login with a written list of what it may read and change; the CRM
refuses everything else, records every agent change (who, what, before/after, on whose
approval), and lets an agent safely retry a change without doing it twice. Cira stays the only
agent that creates or changes quotes, contracts, invoices, PDFs, statuses and money. Riff becomes
the first agent allowed to update technical data (zones, devices, tech details, tickets)
directly. Nothing changes for humans using the CRM website, and the approved PDF designs are
untouched.

## 1. What we measured (2026-09-25)

| Fact | Evidence |
|---|---|
| All agent logins are `role=Admin` | `/api/v1/auth/me/` for cira, theo, riff, vera, lyra, nina tokens; `mint_agent_tokens.py:50` |
| A retired agent's Admin token is still live | `scripts/crm_snapshot.py` (desk repo) token → user `ruby`, Admin |
| MCP tools don't know the caller | module-level `@mcp_server.tool()` functions in `crm_app/mcp.py`; only `RenePhase2MCPToolset` reads `self.request` |
| Field allowlist is opt-in | `_GUARDED_UPDATE_FIELDS` only applies when the caller passes `expected_version`/`expected_values` (`mcp.py:914`) |
| Agents can hard-delete | `delete_record` (`mcp.py:1324`) — only templates/service locations blocked |
| Most agent writes aren't audited in the CRM | `AuditLog` written by REST viewsets only; MCP path writes one AuditLog (Sent-date correction) with `user=None` |
| Tokens are stored in plaintext and accepted in URLs | DRF `authtoken` stores the key; `QueryParamTokenAuthentication` accepts `?token=` (Nina's config uses it) |
| "Held" writes are never retried | Theo's `crm_bookkeep` refuses replay after any uncertainty; 4 contracts sat Draft 11–18 days (fixed 2026-09-25) |
| Two writers bypass Cira already | BMAsia Sales agent writes via `/mcp/` directly; Cara's old desk wrote `contact.last_contacted` directly |
| Scope lists are duplicated 3× | `mcp.py` `_GUARDED_UPDATE_FIELDS`, `services/agent_shadow.py:18-24`, `tools/agent_crm_production.py:36-44` |

## 2. Design

### 2.1 Agent principals (who is calling)

New model **`AgentPrincipal`**: `name` (cira, vera, theo, lyra, riff, nina, cara, sales),
one-to-one `user`, `policy` (key into the policy file), `token_sha256` (hashed — the plaintext
is shown once at minting and never stored), `mode` (`observe` | `enforce`), `expires_at`,
`revoked_at`, `last_used_at`.

New authentication class **`AgentTokenAuthentication`**: `Authorization: Agent <token>` header
only (no query-string tokens), constant-time hash compare, rejects revoked/expired, attaches the
principal as `request.auth`. Pattern copied from Vera's `rene_auth.py`. A new CRM user role
`Agent` replaces `Admin` for these users, so a leaked agent token can't use the website/admin.

### 2.2 One policy file (what each agent may do)

`crm_app/agent_policy.py` — plain, version-controlled data reviewed like code; the single
source of truth (the shadow/production lanes will import it instead of keeping their own
copies). Default is **deny**. Draft:

| Principal | Read | Create | Update (fields) | Notes |
|---|---|---|---|---|
| **cira** | all | **every collection in `_COLLECTION_MAP`** (company, contact, contract, contracttemplate, invoice, quote, opportunity, task, zone, clienttechdetail, device, ticket, kbarticle, quotelineitem, contractlineitem, servicelocation, invoicelineitem) | every field of those collections | plus `convert_quote_to_contract`, renewal-number reservation and the Rene phase-2 tool; all existing guarded rules (signed Sent receipts, explicit-user commercial authorization, date contexts, service-item/contact guards, template guards) run unchanged |
| **riff** (new) | all | ticket, device, clienttechdetail | zone: notes, platform (status comes from the Soundtrack sync, not agents); clienttechdetail: hardware/remote-access fields; device: all non-identity fields; ticket: status (non-terminal), priority, comments | every write carries `basis`: `keith_approved` + Google Chat message ref, or `riff_confident` (Norbert 2026-09-25: act alone only when very confident; otherwise ask Keith in their Chat) |
| **sales** | all | company; contact and opportunity (incl. upsells) | opportunity: any field; **Won/Lost only through the existing guarded `explicit_user_commercial` path** (who decided + source thread, bound to record and patch — guard unchanged); lead companies/contacts: any field | Norbert 2026-09-25: full lead/pipeline authority. **Existing-customer boundary:** a company with any `Contract.status in ('Active','Sent')` — its company and contact records (update, and contact create) stay Cira-only. No deletes |
| **cara** | customer-care view (separate Cara bearer) | activity (care feedback) | contact: title, department, last_contacted | Django-token writes, if any, attributed to user `cara` |
| **theo** | all | activity | contact: title, department, last_contacted; opportunity: stage (non-terminal), last_contact_date, follow_up_date, expected_close_date, pain_points, decision_criteria | = the approved production-lane scope (`tools/agent_crm_production.py` FIELDS['theo']); anything else → Cira |
| **lyra** | all | activity | contact: title, department, last_contacted | anything else → request to Cira (unchanged) |
| **nina** | companies, zones, contracts (read) | activity | zone: programme notes | |
| **vera** | all | — | — | code owner; data fixes still routed via Cira |

**Nobody in the table may delete.** `delete_record` becomes human-only (website/admin);
agents cancel or deactivate instead. Terminal transitions (Won/Lost, Cancelled/Expired,
Resolved/Closed) stay Cira-only and guarded, **with one exception**: Sales may set Won/Lost, but
only through the existing guarded explicit-user commercial path (the guard is not relaxed).

"Activity" = the existing `Note`/`OpportunityActivity` models exposed as an **append-only**
MCP tool `log_activity(company_id, kind, summary, evidence_ref, occurred_at)` — agents can add
to a client's timeline but never edit or remove entries. This is what later lets the CRM
replace free-text Sheet remarks and follow-up columns.

### 2.3 One gate every write goes through

A new service `crm_app/services/agent_gate.py` called by **every** MCP write tool
(`create_record`, `update_record`, `delete_record`, `convert_quote_to_contract`,
`generate_contract_pdf` number reservation, `log_activity`, and — observed only — the Rene
phase-2 tool, whose frozen boundary stays outside the generic gate). The caller is read from
django-mcp-server's `django_request_ctx` (the same context variable it uses to give toolsets
`self.request`), so the generic tools stay registered as they are. In Stage A, DRF-token callers
are attributed by an **explicit username → principal map**, not by token type. For agent
principals the gate:

1. checks the policy (collection, verb, exact field names) — unknown field ⇒ refuse, with the
   reason in the reply;
2. **requires** `request_key` and, for updates, **both** `expected_version` and
   `expected_values` — i.e. the existing guarded mode becomes mandatory for agents; neither the
   version nor the before-value checks are weakened;
3. looks up the idempotency ledger (below) — an identical retry returns the original result;
4. applies the write inside a transaction with `select_for_update` and re-reads it;
5. writes the audit record.

REST (`/api/v1/`) stays for humans and read-only agent use: a DRF permission blocks non-GET
requests from agent principals, so there is exactly one agent write path to reason about.
Existing guarded rules (signed Sent receipts, commercial authorization, date contexts) run
unchanged *inside* the gate.

### 2.4 Idempotency ledger = audit trail = safe retries

New append-only model **`AgentRequest`** (Stage A ships the observe subset). **It never stores
values**: `principal`, `username`, `tool`, `verb`, `collection`, `record_id`, changed **field
names** (≤200), `request_key`, `payload_sha256`, `response_sha256`, `outcome` code
(applied / already_current / refused / conflict / error), reason codes (≤20 × 300 chars),
`on_behalf_of`, evidence **references** (ids/hashes only), timestamps. No before/after values,
no response bodies, and never PDF bytes (a number reservation records only the contract id,
number and artifact SHA-256/size). Before/after values stay where they already live: the
existing `AuditLog` row (written with the principal's user) and Cira's audit.

**Retention and access:** 180 days (`agent_gate_purge`, dry-run default, 30-day minimum);
read-only Django admin for staff users only (agent users are not staff), no agent-facing read
endpoint except `get_request_status` for the caller's own keys.

**Signed Sent receipts:** for `theo:renewal-sent:*` writes the outer `request_key` must equal
the key embedded in the signed receipt. `ContractSendReceiptUse` remains the authority for
receipt replay/conflict (nonce, digest, record, version, before-values, patch); the ledger is an
outer layer: an identical replay returns the stored outcome without re-running the write, and a
changed payload under the same key is a conflict — it never bypasses or re-consumes a receipt.

- Same key + same payload ⇒ the stored outcome (ok, id, updated_at, error code) is returned,
  nothing is written twice. This
  makes **retrying always safe**, which removes the "held forever, no automatic replay" failure
  (Theo's 4 stuck contracts).
- Same key + different payload ⇒ `conflict`, nothing written.
- New read tool `get_request_status(request_key)` so an agent that timed out asks "did it
  land?" instead of holding.
- A **"needs attention"** list (refused/conflict/error requests with no later success after
  24 h) exposed at `/api/v1/agent-requests/attention/` for a daily digest (wiring the digest
  to Telegram is a small follow-up, not in this PR).

### 2.5 Token hygiene (in the same rollout)

Mint hashed `Agent` tokens for all principals; move Nina off the `?token=` URL; revoke the old
DRF tokens after cut-over; deactivate `ruby`; remove the plaintext token from the desk's
`scripts/crm_snapshot.py` (it will read an env var). Query-string auth stays for humans' Claude.ai
connectors only.

## 3. Rollout — staged, reversible, never a live auth flip

| Stage | What | Reversal |
|---|---|---|
| **A. Observe** | Deploy models + policy + gate in `observe` mode for every principal: writes behave exactly as today, but the gate records what it *would* refuse. Old tokens keep working. | Flag off |
| **B. Review** | One week of observe data reviewed with Vera: adjust the policy where a legitimate write would be refused. | Policy edit |
| **C. Riff first** | Mint Riff's `Agent` token, `enforce` mode; wire Riff's tech updates (needs a small Riff-side tool; Keith approval stays in Riff's lane). | Revoke token |
| **D. Cut-over one by one** | nina → lyra → cara → theo → sales → vera → **cira last**: new token, `enforce`, verify a real read/write, then revoke that agent's old DRF token. | Per-principal `mode` back to observe; old token kept 7 days before revocation |
| **E. Close** | All agent users `role=Agent`; `delete_record` refuses agents; ruby deactivated; plaintext token gone. | — |

Migrations are additive (new tables + one new role value) — no change to existing columns.

## 4. Tests (written with the code, run in CI/Vera's review)

Policy matrix (every principal × collection × verb × allowed/denied field); idempotent replay
and conflict; observe vs enforce; revoked/expired/URL-token rejection; REST write blocked for
agents; existing guarded-contract and Rene suites still green; no change to PDF fixture tests.

## 5. Out of scope (later phases)

Contract/opportunity **state machine** and automatic term-end flips (Phase 1b, needs the
lifecycle decisions); data repairs (Phase 2: the 28-Mar-2026 finance-sheet import, missing
contracts); Renewal Book page and Sheet parity (Phase 3); evidence-scored field proposals and
email intake (Phase 4). The existing off-server shadow/production correction lanes are left
running; after Stage D they become redundant and Vera decides whether to retire them.

## 6. Decisions (Norbert, 2026-09-25)

1. **Invoices stay in QuickBooks for now.** Pom keeps invoicing in QuickBooks Pro 2016; the CRM
   does not mint invoice numbers in Phase 1. The existing `qbmcp` bridge (Render
   `srv-d7c6lh7lk1mc7391ac40`, QuickBooks Web Connector, built April 2026) is deployed but has
   had no Web Connector traffic in the last 30 days, i.e. Pom's PC was likely never connected.
   Proposed later phase: connect it and **read** invoices + payments into the CRM nightly
   (Paid/Unpaid without the Sheet's INV tabs), CRM-created invoices pushed to QuickBooks after that.
2. **Riff** may write alone when very confident; otherwise asks Keith in their Google Chat and
   records the approval reference. The gate stores the `basis` of every Riff write.
3. **Sales agent**: full authority over leads and pipeline (create/edit leads, any opportunity
   stage incl. Won/Lost), bounded away from existing customers' records and deletes. The current
   explicit-user binding required for Won/Lost in guarded mode (`mcp.py:613-643`) will accept the
   Sales principal as its own authority — Vera to confirm.
4. **Cara** writes care feedback (activity) and `contact.last_contacted` directly.

## 7. Review checklist for Vera

- Does any current Cira/Theo/Sales workflow need a field or collection missing from §2.2?
- Is moving the generic tools into an `MCPToolset` compatible with the pinned `mcp==1.28.1` /
  django-mcp-server 0.5.7 and the Rene transport?
- Any conflict with the signed-receipt, commercial-authorization or Rene guards?
- Observe-mode storage/retention acceptable (AgentRequest has no customer prose; evidence is
  references only)?
