"""Switches, limits, the proposal allowlist and how agent accounts are recognised.

Everything a reviewer of this app needs to approve sits in this one file.
"""
from __future__ import annotations

from django.conf import settings

# ------------------------------------------------------------------ switches


def activity_writes_enabled() -> bool:
    """AGENT_ACTIVITY_WRITES_ENABLED; anything but a real True is off."""
    return getattr(settings, 'AGENT_ACTIVITY_WRITES_ENABLED', False) is True


def proposals_enabled() -> bool:
    """CHANGE_PROPOSALS_ENABLED; anything but a real True is off."""
    return getattr(settings, 'CHANGE_PROPOSALS_ENABLED', False) is True


ACTIVITY_DISABLED_DETAIL = 'Agent activity writes are not enabled on this server (AGENT_ACTIVITY_WRITES_ENABLED is off).'
PROPOSALS_DISABLED_DETAIL = 'Change proposals are not enabled on this server (CHANGE_PROPOSALS_ENABLED is off).'

# ------------------------------------------------------------------ limits


def _positive_int(name, default):
    value = getattr(settings, name, default)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else default


def proposal_expiry_days() -> int:
    """Days a proposal stays open before it expires (CHANGE_PROPOSAL_EXPIRY_DAYS, default 30)."""
    return _positive_int('CHANGE_PROPOSAL_EXPIRY_DAYS', 30)


def proposal_daily_cap() -> int:
    """Proposals one proposer may store in any rolling 24 hours (CHANGE_PROPOSALS_DAILY_CAP, default 200)."""
    return _positive_int('CHANGE_PROPOSALS_DAILY_CAP', 200)


def activity_daily_cap() -> int:
    """Activities one user may record in any rolling 24 hours (AGENT_ACTIVITY_DAILY_CAP, default 2000)."""
    return _positive_int('AGENT_ACTIVITY_DAILY_CAP', 2000)


# ------------------------------------------------------------------ the allowlist
#
# PROPOSAL_ALLOWLIST is the only list of what a ChangeProposal may change:
# kind -> target collection -> fields. Anything not listed is refused when the
# proposal is made and again when it is accepted. Deliberately absent tonight:
# every contract, quote and invoice field (status, money, prices, tax, discount,
# term dates, numbers), company identity and billing fields (name, legal name,
# tax id, branch, billing entity), contact email preferences and is_primary,
# task status and assignment, and any delete or merge. Widening it is a reviewed
# code change.
#
# kind 'note' appends its text to the record's notes (never replaces them).
# kind 'new_contact' and 'task' create a record on the proposal's company.
PROPOSAL_ALLOWLIST = {
    'field_update': {
        'contact': frozenset({
            'name', 'email', 'phone', 'mobile', 'title', 'department',
            'preferred_contact_method', 'linkedin_url',
        }),
        'company': frozenset({
            'phone', 'email', 'website', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country',
        }),
    },
    'note': {
        'contact': frozenset({'notes'}),
        'company': frozenset({'notes'}),
    },
    'new_contact': {
        'contact': frozenset({
            'name', 'email', 'phone', 'mobile', 'title', 'department',
            'preferred_contact_method', 'linkedin_url', 'notes',
        }),
    },
    'task': {
        'task': frozenset({
            'title', 'description', 'priority', 'task_type', 'due_date',
            'related_contact', 'related_contract', 'related_opportunity',
        }),
    },
}

# Fields a creating proposal must carry.
PROPOSAL_REQUIRED_FIELDS = {
    'new_contact': frozenset({'name', 'email'}),
    'task': frozenset({'title'}),
}

# Kinds that update an existing record, and kinds that create one.
UPDATE_KINDS = frozenset({'field_update', 'note'})
CREATE_KINDS = frozenset({'new_contact', 'task'})
# 'link' and 'other' exist in the model for later use; they are refused tonight.
APPLICABLE_KINDS = UPDATE_KINDS | CREATE_KINDS

NOTE_SEPARATOR = '\n\n'


def allowed_fields(kind: str, collection: str) -> frozenset:
    return PROPOSAL_ALLOWLIST.get(kind, {}).get(collection, frozenset())


def collections_for(kind: str) -> tuple:
    return tuple(sorted(PROPOSAL_ALLOWLIST.get(kind, {})))


# ------------------------------------------------------------------ agent accounts
#
# Agent accounts are told apart the way the agent gate does today: by CRM
# username, through crm_app.agent_policy (cira, vera, theo, lyra, riff, nina,
# cara, sales, ruby; mint_agent_tokens creates its users under those names).
# AGENT_INBOX_AGENT_USERNAMES adds more names without a code change. Research
# note 08 replaces this with AgentPrincipal rows; is_agent_account() is the one
# place to switch over.

AGENT_PROPOSER_KINDS = frozenset({'agent', 'ai'})
EVIDENCE_REQUIRED_KINDS = frozenset({'agent', 'ai'})
REVIEW_AUTH_METHODS = frozenset({'jwt', 'session'})


def extra_agent_usernames() -> frozenset:
    raw = getattr(settings, 'AGENT_INBOX_AGENT_USERNAMES', ()) or ()
    if isinstance(raw, str):
        raw = raw.split(',')
    return frozenset(str(name).strip().lower() for name in raw if str(name).strip())


def is_agent_account(user) -> bool:
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    username = str(getattr(user, 'username', '') or '').strip().lower()
    from crm_app import agent_policy
    return agent_policy.principal_for_username(username) is not None or username in extra_agent_usernames()


def review_refusal(request) -> str | None:
    """Why this request may not accept or reject a proposal, or None.

    A decision needs a signed-in person: not an agent account, and signed in
    with the website's JWT or a session. DRF tokens are the credential every
    agent holds today, so a decision made with one cannot be told apart from
    an agent's.
    """
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return 'Sign in to review proposals.'
    if is_agent_account(user):
        return 'Agent accounts cannot accept or reject proposals; a person reviews them on the website.'
    from crm_app.auth_observability import auth_method
    if auth_method(request) not in REVIEW_AUTH_METHODS:
        return 'Proposal decisions need a website sign-in (JWT or session), not an API token.'
    return None
