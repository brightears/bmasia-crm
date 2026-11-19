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
    """The setting as a positive int; the default for anything else (e.g. '30d')."""
    value = getattr(settings, name, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, str):
        value = value.strip()
        if not value.isdigit():
            return default
        value = int(value)
    return value if isinstance(value, int) and value > 0 else default


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


# ------------------------------------------------------------------ agent accounts and reviewers
#
# An account is an agent account when any of these holds:
#   - its username is a principal in crm_app.agent_policy (the agent gate's map) or
#     is listed in AGENT_INBOX_AGENT_USERNAMES ("an agent by name");
#   - it holds a DRF API token and is not a listed reviewer. Every agent and the
#     shared headless account authenticate with one; people use the website sign-in.
# Usernames are compared case-insensitively. An agent account proposes as agent or
# ai (never human or job), must give evidence and sees only its own proposals.
#
# A reviewer is a person on CHANGE_PROPOSAL_REVIEWER_USERNAMES (default empty, so
# nobody can review until it is set). An agent by name is never a reviewer, even if
# listed (system check agent_inbox.W001). For a listed reviewer, holding an API
# token does not count against them, but every decision must still be made from a
# website sign-in (JWT or session). Research note 08 replaces the name rules with
# AgentPrincipal rows; is_agent_by_name() is the one place to switch over.

AGENT_PROPOSER_KINDS = frozenset({'agent', 'ai'})
EVIDENCE_REQUIRED_KINDS = frozenset({'agent', 'ai'})
REVIEW_AUTH_METHODS = frozenset({'jwt', 'session'})
# Source systems that say a person or the CRM itself wrote the text.
PERSON_SOURCE_SYSTEMS = frozenset({'manual', 'crm'})

NOT_CONFIGURED_DETAIL = ('Reviewing is not configured on this server: no reviewer is listed in '
                         'CHANGE_PROPOSAL_REVIEWER_USERNAMES.')
NOT_LISTED_DETAIL = 'Your account is not on the reviewer list (CHANGE_PROPOSAL_REVIEWER_USERNAMES).'


def _name(value) -> str:
    return str(value or '').strip().casefold()


def _names(setting) -> frozenset:
    raw = getattr(settings, setting, ()) or ()
    if isinstance(raw, str):
        raw = raw.split(',')
    return frozenset(_name(name) for name in raw if _name(name))


def extra_agent_usernames() -> frozenset:
    return _names('AGENT_INBOX_AGENT_USERNAMES')


def _agent_name(username) -> bool:
    from crm_app import agent_policy
    name = _name(username)
    return agent_policy.principal_for_username(name) is not None or name in extra_agent_usernames()


def listed_reviewer_names() -> frozenset:
    """CHANGE_PROPOSAL_REVIEWER_USERNAMES without agent names (those are never reviewers)."""
    return frozenset(name for name in _names('CHANGE_PROPOSAL_REVIEWER_USERNAMES') if not _agent_name(name))


def ignored_reviewer_names() -> frozenset:
    return frozenset(name for name in _names('CHANGE_PROPOSAL_REVIEWER_USERNAMES') if _agent_name(name))


def is_agent_by_name(user) -> bool:
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return _agent_name(getattr(user, 'username', ''))


def is_listed_reviewer(user) -> bool:
    if user is None or not getattr(user, 'is_authenticated', False) or is_agent_by_name(user):
        return False
    return _name(getattr(user, 'username', '')) in listed_reviewer_names()


def holds_api_token(user) -> bool:
    from rest_framework.authtoken.models import Token
    return Token.objects.filter(user_id=user.pk).exists()


def is_agent_account(user) -> bool:
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if is_agent_by_name(user):
        return True
    return holds_api_token(user) and not is_listed_reviewer(user)


def agent_account_ids(user_ids) -> set:
    """The ids among ``user_ids`` that are agent accounts, in two queries."""
    from django.contrib.auth import get_user_model
    from rest_framework.authtoken.models import Token

    ids = {pk for pk in user_ids if pk is not None}
    if not ids:
        return set()
    users = {user.pk: user for user in get_user_model().objects.filter(pk__in=ids).only('pk', 'username')}
    with_token = set(Token.objects.filter(user_id__in=ids).values_list('user_id', flat=True))
    reviewers = listed_reviewer_names()
    return {
        pk for pk, user in users.items()
        if _agent_name(user.username) or (pk in with_token and _name(user.username) not in reviewers)
    }


def can_read_activity_body(user, activity, recorder_is_agent=None) -> bool:
    """Whether ``user`` may read this activity's body.

    People read every body. An agent account reads the bodies it recorded, and
    the bodies recorded by a capture job or a person unless the recorder marked
    the activity ``restricted``. Bodies recorded by other agents stay hidden.
    """
    if not is_agent_account(user):
        return True
    if activity.recorded_by_id == getattr(user, 'pk', None):
        return True
    if activity.restricted or activity.recorded_by_id is None:
        return False
    if recorder_is_agent is None:
        recorder_is_agent = is_agent_account(activity.recorded_by)
    return not recorder_is_agent


def recorded_via_for(request) -> str:
    """'ui' for a person signed in to the website, otherwise 'rest'. Never taken from the body."""
    from crm_app.auth_observability import auth_method
    if auth_method(request) in REVIEW_AUTH_METHODS and not is_agent_account(getattr(request, 'user', None)):
        return 'ui'
    return 'rest'


def review_refusal(request, proposal=None) -> str | None:
    """Why this request may not decide on a proposal, or None.

    A reviewer is on the reviewer list, is not an agent by name, decides from a
    website sign-in (JWT or session), did not make the proposal and did not record
    its evidence.
    """
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return 'Sign in to review proposals.'
    if is_agent_by_name(user):
        return 'Agent accounts cannot decide on proposals; a person reviews them on the website.'
    from crm_app.auth_observability import auth_method
    if auth_method(request) not in REVIEW_AUTH_METHODS:
        return 'Proposal decisions need a website sign-in (JWT or session), not an API token.'
    if not listed_reviewer_names():
        return NOT_CONFIGURED_DETAIL
    if not is_listed_reviewer(user):
        return NOT_LISTED_DETAIL
    if proposal is not None:
        if proposal.proposer_id is not None and proposal.proposer_id == user.pk:
            return 'A reviewer must be a different person from the proposer.'
        activity = proposal.activity
        if activity is not None and activity.recorded_by_id == user.pk:
            return 'A reviewer must be a different person from the one who recorded the evidence.'
    return None


def account_status(request) -> dict:
    """What the calling account may do here, for the review page."""
    user = getattr(request, 'user', None)
    refusal = review_refusal(request)
    agent = is_agent_account(user)
    reason = None
    if agent:
        reason = 'agent name' if is_agent_by_name(user) else 'holds an API token and is not a listed reviewer'
    return {
        'you_can_review': refusal is None,
        'review_refusal': refusal,
        'treated_as_agent': agent,
        'treated_as_agent_because': reason,
        'reviewing_configured': bool(listed_reviewer_names()),
    }


