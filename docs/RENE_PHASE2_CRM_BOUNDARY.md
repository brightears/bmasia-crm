# Rene Phase 2 CRM boundary

Status: **LOCAL REVIEW BRANCH ONLY — NOT DEPLOYED** (2026-08-24).

This boundary implements the CRM half of the frozen
`bmasia.cira.rene.v1` contract. It does not activate Rene, send email, call
Cira, change a live CRM, or expose a general CRM write credential.

## Exact surfaces

| Surface | Authentication | Authority |
|---|---|---|
| `GET /api/v1/auth/token-capabilities/` | Rene opaque bearer | Return the exact read capability receipt |
| `GET /api/v1/contracts/renewal-book/` | Existing JWT/session/DRF token, or Rene opaque bearer | Read the renewal book only |
| `POST /mcp/rene-phase2/` with MCP tool `rene_phase2_request(request_json)` | Dedicated `Authorization: Rene <opaque-secret>` credential, bound to one exact active User UUID | Execute or look up only the frozen Rene operations |
| Existing `/mcp/` transport | Existing DRF token/query-token authentication | Existing generic CRM tools; the Rene tool is absent |

The existing renewal-book router action remains the public path for current
authenticated CRM callers. There is no shadow route. Rene's bearer is accepted
only by the capability endpoint and that existing action. It is never accepted
by MCP.

The Cira boundary has its own stateless `DjangoMCP` instance, tool manager,
handler, authentication class, and permission class. Its registry contains
only the library's harmless `get_server_instructions` tool and
`rene_phase2_request`; generic query/create/update/delete, convert, and PDF
tools remain only on `/mcp/`. The Rene tool is not registered globally.

The endpoint accepts one separately generated opaque secret in the `Rene`
authorization scheme. Only its SHA-256 digest is configured. The authentication
class constant-time compares the digest, then loads the exact canonical UUID in
`CIRA_RENE_MCP_USER_ID` and requires that user to remain active. It also attaches
a request-local scoped credential marker that the permission and tool both
recheck. The secret is not a DRF Token: it cannot authenticate at `/mcp/` or any
REST route, while an ordinary DRF token (including one for the same user) cannot
authenticate at `/mcp/rene-phase2/`. Query-parameter tokens are not accepted on
the dedicated endpoint.

This patch does not mint a user, token, role, or permission. The relay must hold
only this scoped plaintext secret, invoke only the dedicated endpoint/tool, and
must never receive a generic CRM token or adapt the envelope to generic CRUD or
`duplicate_for_renewal`. The obsolete direct REST write adapter and its bearer
settings are deliberately absent.

The CRM stores only SHA-256 token digests and reviewed expiries:

```text
RENE_RENEWAL_BOOK_TOKEN_SHA256
RENE_RENEWAL_BOOK_TOKEN_EXPIRES_AT
CIRA_RENE_MCP_TOKEN_SHA256
CIRA_RENE_MCP_USER_ID
```

The CRM stores only credential digests (plus the read-token expiry). Plain
tokens remain in their respective secret stores. Missing, malformed, expired,
wrong, or non-canonical settings fail closed; a missing, inactive, or unknown
configured MCP user disables the dedicated endpoint.

## Stable renewal-book identity

Every renewal-book row now returns `contract_id`, `company_id`, `version`, and
`updated_at`. `version` is a deterministic SHA-256 binding of the stable
contract ID and exact `updated_at` timestamp.

This change deliberately preserves the existing totals contracts:
`totals_by_product` remains a product-keyed object whose values are exactly
`{"contracts": <integer>, "zones": <integer>, "value": <number>}`, while
`totals_by_status` remains a status-keyed object of integer counts. Rene's
strict reader must accept those two distinct shapes; the server does not
flatten product totals to satisfy a client parser.

An undated CRM contract cannot appear in a month filter. A caller that already
has its exact stable ID may therefore repeat canonical query parameters:

```text
contract_id=<canonical-uuid>&contract_id=<canonical-uuid>
```

At most 100 distinct lowercase-hyphen UUIDs are accepted. When supplied, the
response adds:

- `requested_contract_ids`: exact request order;
- `referenced_undated_rows`: the ordered subsequence whose exact IDs have SQL
  `end_date IS NULL` and meet the existing currency/non-Draft boundary.

Missing, dated, Draft, and wrong-currency IDs remain in the echo but are absent
from the returned rows. Without `contract_id`, both new fields are omitted, so
existing consumers receive the prior response shape. The endpoint never lists
all undated contracts and never matches by company name.

## Human-reviewed policies

Migration `0097_rene_phase2_contract_boundary` creates one unseeded
`ReneRenewalPolicy` record. There is deliberately no default business answer.
Only an active Django superuser may create or edit the single `global` record;
Rene and Cira have no policy-write route. Policy and journal records cannot be
deleted through the admin.

The record separately binds:

- renewal start rule, policy ID, evidence SHA, source reference/label, revision;
- renewal end rule, policy ID, evidence SHA, source reference/label, revision;
- final-number rule, policy ID, evidence SHA, source reference/label, revision;
- post-send state rule, policy ID, evidence SHA, source reference/label,
  revision, and explicit reviewed flag.

The final-number rule is exactly
`RESERVE_UNUSED_DOCUMENT_SEQUENCE_BEFORE_PDF`. The post-send rule is exactly
`PREPARED_TO_SENT_SOURCE_UNCHANGED`. Unknown, placeholder, pending, malformed,
or unreviewed evidence is a hold. Revisions can never decrease, and the admin
requires a revision increase whenever policy evidence or a rule changes,
including while a record is pending or while a review flag is being changed.
Service execution re-reads these records and mutating operations lock the
policy row.

Operator path: a superuser records the exact reviewed Chat/record reference and
evidence hash in Django admin, checks the source label and rule, increments the
applicable revision, then sets the review gate. If that reviewed operator path
is not available in the deployed CRM, preparation and/or post-send bookkeeping
must remain blocked; Rene cannot substitute its own answer.

## Cira-only MCP operation

`rene_phase2_request` accepts one JSON **string** containing a bounded UTF-8
object (2 MiB maximum), rejects duplicate keys at every nesting level,
recomputes the canonical intent hash and request key, and allowlists only:

- `inspect_renewal_source`;
- `validate_only`;
- `prepare_renewal_contract`;
- `verify_prepared_contract`;
- `record_prepared_contract_sent`;
- `fill_blank_renewal_date`;
- `receipt_lookup` through its separate lookup schema.

An inspection also requires positive integer `evidence_revision`. It is derived
by Rene from the exact typed action/clarification evidence revision, appears in
the inspection receipt and binding, and is part of the content-derived request
key. It is not an operator override. A genuinely revised action therefore has
a new key, fresh evidence, and a new owner permit; changing only `request_id`
cannot bypass dedupe.

Durable `ReneCiraRequest` rows bind request ID, content-derived key, exact
canonical envelope, operation state, and final receipt. They have no TTL.
Same-ID payload drift is rejected. The same content key under another request
ID returns `REQUEST_KEY_IDENTITY_MISMATCH` bound to the new envelope, with
`transaction_committed=null` and `effect_persisted=null`; it never translates
the original ID-bound receipt and never repeats the effect. Accepted or crash-
uncertain requests remain lookup-only.

A typed operation rejection rolls back the complete operation transaction,
then durably stores state `failed` plus one exact
`bmasia.cira.rene.crm-terminal-rejection.v1` receipt. It binds request ID/key,
intent hash, operation, code/message, and this proof:

```json
{
  "boundary": "crm_atomic_rollback",
  "crm_mcp_invoked": true,
  "transaction_committed": false,
  "effect_persisted": false,
  "request_state": "failed"
}
```

Receipt lookup returns `status=rejected_terminal` and that exact receipt.
Submitting the same request again returns the same terminal result and never
reopens it, even if a missing policy or artifact was later fixed. Recovery
requires a genuinely new evidence revision, fresh live evidence, and a new
owner permit. Malformed, unbound, or internal MCP failures use
`bmasia.cira.rene.crm-uncertain.v1`; they never claim rollback proof.

### Inspect

Inspection is non-mutating. It requires one exact stable contract/company
identity, an optimistic version match, one and only one official signed
`ContractDocument`, actual bounded PDF bytes, a signed date, reviewed start/end
policies, a 1–120 month term, and explicit pricing evidence. Only one simple
non-zone total may proceed; line-item, service-location, per-zone, or mixed
pricing becomes clarification rather than inference.

### Prepare

Preparation requires its exact successful `validate_only` receipt and stored
inspection receipt. It rechecks the source version, timestamp, status, signed
document bytes, policy evidence, terms, and pricing. It uses a dedicated clone
implementation—not `duplicate_for_renewal`—and creates only:

```text
new Contract: Draft, is_active=false
RenePreparedContract: ready_for_review
source Contract: unchanged
```

The target ID must be one canonical lowercase UUID. Renewal price is positive
canonical two-decimal money, and base value, derived tax, and derived total
must each fit the CRM `DecimalField(12,2)` before number reservation. Migration
`0098_unique_rene_preparation_per_source` also enforces at most one Rene
preparation for a source. Validation and execution fail closed if any generic
or Rene renewal successor already points at that source; only replay of the
exact already-journaled request returns its existing receipt.

The reviewed rule reserves the next unused official `DocumentSequence` number
inside the transaction before PDF rendering. The review PDF is generated from
the normal CRM renderer with that non-temporary number already present. Exact
portable bytes are stored exactly once on `RenePreparedContract`. Durable
request receipts store only the bound filename, size, SHA-256, and portable
operation binding; the dedicated MCP response reconstructs `content_base64`
from the immutable stored bytes for first response, exact duplicate, and
receipt lookup.
No email, publication, source renewal, activation, retirement, or deactivation
occurs.

The service does not trust asserted PDF metadata. It parses the actual rendered
bytes with pinned `pypdf==6.16.1`, rejects encrypted/unparseable/empty or
over-200-page artifacts, extracts normalized visible text, and requires the
final contract number, exact start/end dates, currency, and exact amount to be
visible before the prepare transaction can commit. The renderer test also
proves that changing the expected final number makes the existing PDF fail.

### Verify and record sent

Verification is a new nonce-bound, non-mutating re-read of the exact prepared
draft, final number, source binding, current reviewed number policy, and stored
PDF bytes. It returns the live portable PDF.

Record-sent is a separate validated transaction after exact Gmail Sent proof.
It accepts only authenticated mailbox `norbert@bmasiamusic.com`, visible sender
`nikki.h@bmasiamusic.com`, exact recipients/content/attachment hashes, Gmail
IDs, RFC Message-ID, and matching Gmail `internalDate`/sent time. After the
reviewed post-send policy passes, it changes only the prepared contract from
Draft/`ready_for_review` to Sent and stores the Gmail and policy evidence. The
final number/PDF/source binding remain unchanged. The source contract is never
changed. A bookkeeping failure can never authorize another customer email.

### Fill blank date

Fill requires exact validation, stable contract/company IDs, optimistic
version, and bound Sheet tab/row/column-E evidence. Under a row transaction it
allows only SQL null to that exact date. A non-null value or changed version is
a contradiction; overwrite is forbidden.

## Deployment gates

The sanitized response fixtures at
`docs/fixtures/rene-renewal-book-monthly-v1.json` and
`docs/fixtures/rene-renewal-book-requested-undated-v1.json` preserve the exact
nested product totals, integer status totals, and requested-undated shapes.
They are intended for direct cross-repository parsing by Rene.

Before deployment, review the migration and dedicated MCP endpoint, run focused
and full tests under the production Python version and PostgreSQL, install the
pinned dependency, generate a separate high-entropy MCP secret, configure only
its SHA-256 as `CIRA_RENE_MCP_TOKEN_SHA256`, configure
`CIRA_RENE_MCP_USER_ID` as one exact canonical existing active user UUID, and
record the exact reviewed policies. Do not create a DRF Token from or alongside
the scoped secret for the relay. Configure the forced-command relay/Hermes lane
with only the scoped plaintext secret and `/mcp/rene-phase2/`.

After deployment, perform read-only checks of Rene's capability receipt,
existing JWT renewal-book access, dedicated `tools/list` exact allowlist,
dedicated `tools/call`, wrong/unset/malformed scoped-auth denial, scoped-secret
denial on global MCP and REST, generic-token denial on the dedicated endpoint,
global absence of `rene_phase2_request`, duplicate/oversized input rejection,
lookup semantics, and visible-PDF inspection. Do not activate Phase 2 from this
CRM change. Rene's own activation gates and supervised-first-send ceremony
remain separate.
