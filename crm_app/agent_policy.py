"""Per-agent CRM write policy (Phase 1 agent gate).

Single, reviewed source of truth for what each fleet agent may change through
the MCP write tools. Default is deny. Design: docs/agent-gate-phase1-design.md.

Stage A (observe) only *evaluates* this policy and records the verdict in
``AgentRequest``; it never blocks a write. Changing this file changes what the
gate would refuse, so treat edits like code: reviewed by Vera, approved by
Norbert.

Principals are resolved from the authenticated CRM username. Users that are not
listed here are treated as humans and are not gated.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ANY = '*'

# Verbs recorded by the gate.
CREATE, UPDATE, DELETE = 'create', 'update', 'delete'
CONVERT, RESERVE_NUMBER, RENE = 'convert_quote', 'reserve_number', 'rene_request'

# Fields an agent may never set on the tech collections it maintains: they bind
# the row to a customer/identity and must stay stable.
_IDENTITY = frozenset({'id', 'company', 'company_id', 'created_at', 'updated_at'})

TICKET_TERMINAL = frozenset({'resolved', 'closed'})
OPPORTUNITY_TERMINAL = frozenset({'Won', 'Lost'})
LIVE_CONTRACT_STATUSES = ('Active', 'Sent')


@dataclass(frozen=True)
class Rule:
    """Allowed fields for one verb on one collection.

    ``fields`` is ANY or a frozenset of field names. ``exclude`` removes fields
    even when ``fields`` is ANY. ``condition`` names an extra check implemented
    in ``crm_app.services.agent_gate``.
    """
    fields: object = ANY
    exclude: frozenset = frozenset()
    condition: str = ''


@dataclass(frozen=True)
class Principal:
    name: str
    create: dict = field(default_factory=dict)
    update: dict = field(default_factory=dict)
    verbs: frozenset = frozenset()          # extra tool verbs (convert_quote, reserve_number)
    retired: bool = False
    note: str = ''


# Exhaustive: the collections crm_app.mcp._COLLECTION_MAP exposes today. A new
# collection is denied to every agent (Cira included) until it is added here on review.
CIRA_COLLECTIONS = frozenset({
    'company', 'contact', 'contract', 'contracttemplate', 'invoice', 'invoicelineitem',
    'quote', 'quotelineitem', 'opportunity', 'task', 'zone', 'clienttechdetail', 'device',
    'ticket', 'kbarticle', 'contractlineitem', 'servicelocation',
})

_CONTACT_METADATA = Rule(frozenset({'title', 'department', 'last_contacted'}))
_OPPORTUNITY_QUALIFICATION = Rule(
    frozenset({'stage', 'last_contact_date', 'follow_up_date', 'expected_close_date',
               'pain_points', 'decision_criteria'}),
    condition='opportunity_non_terminal',
)

PRINCIPALS = {
    # Cira: the gatekeeper and sole commercial writer. Everything except delete;
    # existing guarded rules in crm_app/mcp.py still apply on top.
    'cira': Principal(
        name='cira',
        create={name: Rule() for name in CIRA_COLLECTIONS},
        update={name: Rule() for name in CIRA_COLLECTIONS},
        verbs=frozenset({CONVERT, RESERVE_NUMBER, RENE}),
        note='sole creator/changer of quotes, contracts, invoices, statuses and money',
    ),
    # Vera: code owner. Data fixes are routed through Cira.
    'vera': Principal(name='vera', note='read-only; data fixes via Cira'),
    # Theo: same scope as the approved production correction lane
    # (tools/agent_crm_production.py FIELDS['theo']).
    'theo': Principal(
        name='theo',
        update={'contact': _CONTACT_METADATA, 'opportunity': _OPPORTUNITY_QUALIFICATION},
        note='renewals; everything else via Cira',
    ),
    'lyra': Principal(name='lyra', update={'contact': _CONTACT_METADATA},
                      note="Norbert's PA; everything else via Cira"),
    # Riff: tech data. Every write must carry a basis (keith_approved + Chat ref,
    # or riff_confident); recorded from Stage C when the tool accepts it.
    'riff': Principal(
        name='riff',
        create={
            'ticket': Rule(exclude=_IDENTITY - {'company', 'company_id'}),
            'device': Rule(exclude=_IDENTITY - {'company', 'company_id'}),
            'clienttechdetail': Rule(exclude=_IDENTITY - {'company', 'company_id'}),
        },
        update={
            'zone': Rule(frozenset({'notes', 'platform'})),
            'clienttechdetail': Rule(exclude=_IDENTITY),
            'device': Rule(exclude=_IDENTITY),
            'ticket': Rule(frozenset({'status', 'priority'}), condition='ticket_non_terminal'),
        },
        note='tech data; act alone only when very confident, else ask Keith in Google Chat',
    ),
    'nina': Principal(name='nina', update={'zone': Rule(frozenset({'notes'}))},
                      note='music design; zone programme notes only'),
    # Cara: client care. Reads use her separate Cara bearer; any Django-token
    # writes are limited to contact metadata (care feedback activity arrives later).
    'cara': Principal(name='cara', update={'contact': _CONTACT_METADATA},
                      note='client care; care-feedback activities in a later stage'),
    # BMAsia Sales agent: full lead/pipeline authority, never existing customers.
    # Its CRM username is not yet confirmed; Stage A observe data will show it.
    'sales': Principal(
        name='sales',
        create={'company': Rule(), 'contact': Rule(condition='lead_company_only'),
                'opportunity': Rule()},  # upsells to existing customers are sales work
        update={
            # Won/Lost only with the existing explicit-user commercial authorization
            # (crm_app/mcp.py guarded path: who decided + source); that guard is unchanged.
            'opportunity': Rule(condition='terminal_needs_explicit_authorization'),
            'company': Rule(condition='lead_company_only'),
            'contact': Rule(condition='lead_company_only'),
        },
        note='leads + pipeline incl. Won/Lost; companies with Active/Sent contracts stay Cira-only',
    ),
    # Retired agent whose Admin token is still live: every write is a violation.
    'ruby': Principal(name='ruby', retired=True, note='retired agent; token to be revoked'),
}

# CRM username -> principal (explicit: DRF-token users are attributed by username).
USERNAME_TO_PRINCIPAL = {name: name for name in PRINCIPALS}


def principal_for_username(username: str) -> Principal | None:
    key = USERNAME_TO_PRINCIPAL.get((username or '').strip().lower())
    return PRINCIPALS.get(key) if key else None


def _rule_for(rules: dict, collection: str) -> Rule | None:
    return rules.get(collection) or rules.get(ANY)


def field_violations(rule: Rule, fields) -> list[str]:
    requested = set(fields)
    if rule.fields == ANY:
        blocked = requested & set(rule.exclude)
    else:
        blocked = (requested - set(rule.fields)) | (requested & set(rule.exclude))
    return sorted(blocked)


def evaluate(principal: Principal, verb: str, collection: str, fields) -> tuple[list[str], str]:
    """Return (policy reasons, condition-to-check) for one attempted write.

    An empty reasons list means the policy allows it, subject to ``condition``
    (checked against the database by the gate).
    """
    if principal.retired:
        return [f'principal {principal.name} is retired'], ''
    if verb == DELETE:
        return ['agents may not delete records'], ''
    if verb in (CONVERT, RESERVE_NUMBER, RENE):
        if verb in principal.verbs:
            return [], ''
        return [f'{verb} is Cira-only'], ''
    rules = principal.create if verb == CREATE else principal.update if verb == UPDATE else {}
    rule = _rule_for(rules, collection)
    if rule is None:
        return [f'{principal.name} may not {verb} {collection}'], ''
    blocked = field_violations(rule, fields)
    if blocked:
        return [f'{principal.name} may not set {collection}.{name}' for name in blocked], rule.condition
    return [], rule.condition
