"""Who is asking: a person signed in to the website, or an agent / API token.

Decided by how the request is authenticated, not by what the account holds elsewhere:
- a person: authenticated by a website sign-in (JWT or session) with an account that is not
  on the agent-name list (crm_app.permissions.PersonSignedInToWebsite);
- an agent request: anything else that is authenticated (an API token, an agent account).

Roles come from crm_app.permissions (one rule); the classes here add "on the website" to them
for exports, configuration writes and actions that change many records or reach outside the CRM.
"""
from rest_framework import permissions

from crm_app.permissions import (
    IsAdminOrStaff, IsAdminRole, IsFinanceOrAdmin, IsSalesOrAdmin, IsTechAdminOrStaff, PersonSignedInToWebsite,
)


def is_website_person(request) -> bool:
    """A person signed in to the website: crm_app.permissions.PersonSignedInToWebsite."""
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return PersonSignedInToWebsite().has_permission(request, None)


def is_agent_request(request) -> bool:
    user = getattr(request, 'user', None)
    return bool(user is not None and getattr(user, 'is_authenticated', False) and not is_website_person(request))


class OnWebsite(permissions.BasePermission):
    """``role_permission`` (a crm_app.permissions role class) and a person signed in to the website."""

    role_permission = None
    website_message = 'This action needs a person signed in to the CRM website, not an API token or agent.'
    message = website_message

    def has_permission(self, request, view):
        if self.role_permission is not None:
            role = self.role_permission()
            if not role.has_permission(request, view):
                self.message = role.message
                return False
        if not is_website_person(request):
            self.message = self.website_message
            return False
        return True


class WritesOnWebsite(permissions.BasePermission):
    """Reads pass (the role classes beside it decide); writes need a person on the website."""

    message = OnWebsite.website_message

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or is_website_person(request)


class FinanceOrAdminOnWebsite(OnWebsite):
    role_permission = IsFinanceOrAdmin


class SalesOrAdminOnWebsite(OnWebsite):
    role_permission = IsSalesOrAdmin


class AdminOnWebsite(OnWebsite):
    role_permission = IsAdminRole


class StaffOrTechOnWebsite(OnWebsite):
    role_permission = IsTechAdminOrStaff


class StaffOrAdminOnWebsite(OnWebsite):
    role_permission = IsAdminOrStaff


def agent_may_write(request, collection, method) -> bool:
    """True when the agent-policy principal of this account may create (POST) or update (PUT/PATCH)
    ``collection``, as for the same write through MCP. Deletes are never covered."""
    if not collection or method not in ('POST', 'PUT', 'PATCH'):
        return False
    from crm_app import agent_policy
    principal = agent_policy.principal_for_username(getattr(getattr(request, 'user', None), 'username', '') or '')
    if principal is None or principal.retired:
        return False
    rules = principal.create if method == 'POST' else principal.update
    return collection in rules


class PersonForConfigurationWrites(permissions.BasePermission):
    """Configuration records are read by anyone signed in, and changed by a person on the website.

    A viewset may name an agent-policy collection (``agent_write_collection``): the principal that
    may write that collection through MCP may create and update it here too.
    """
    message = {'error': 'Configuration is changed by a person signed in to the CRM website, not by an API token '
                        'or agent.', 'code': 'not_for_agents'}
    # The record's own writes. Other actions (enrol, recalculate, validate) keep their own rules.
    CONFIGURATION_ACTIONS = frozenset({'create', 'update', 'partial_update', 'destroy', 'bulk_operations',
                                       'duplicate'})

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if getattr(view, 'action', None) not in self.CONFIGURATION_ACTIONS:
            return True
        if is_website_person(request):
            return True
        return agent_may_write(request, getattr(view, 'agent_write_collection', None), request.method)
