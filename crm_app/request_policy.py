"""Who is asking: a person signed in to the website, or an agent / API token.

Decided by how the request is authenticated, not by what the account holds elsewhere:
- a person: authenticated by a website sign-in (JWT or session) with an account that is not
  on the agent-name list (crm_app.agent_policy, plus AGENT_INBOX_AGENT_USERNAMES);
- an agent request: anything else that is authenticated (an API token, an agent account).

The permission classes below gate configuration writes and actions that change many records
or reach outside the CRM.
"""
from django.conf import settings
from rest_framework import permissions

WEBSITE_AUTH_METHODS = frozenset({'jwt', 'session'})


def _agent_name(user) -> bool:
    username = str(getattr(user, 'username', '') or '').strip().casefold()
    from crm_app import agent_policy
    if agent_policy.principal_for_username(username) is not None:
        return True
    extra = getattr(settings, 'AGENT_INBOX_AGENT_USERNAMES', ()) or ()
    if isinstance(extra, str):
        extra = extra.split(',')
    return username in {str(name).strip().casefold() for name in extra if str(name).strip()}


def is_website_person(request) -> bool:
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    from crm_app.auth_observability import auth_method
    return auth_method(request) in WEBSITE_AUTH_METHODS and not _agent_name(user)


def is_agent_request(request) -> bool:
    user = getattr(request, 'user', None)
    return bool(user is not None and getattr(user, 'is_authenticated', False) and not is_website_person(request))


def _has_role(user, roles) -> bool:
    return bool(getattr(user, 'is_superuser', False) or getattr(user, 'role', None) in roles)


class _WebsitePersonWith(permissions.BasePermission):
    roles = None  # None: any role
    staff = False
    message = 'This action needs a person signed in to the CRM website.'

    def has_permission(self, request, view):
        if not is_website_person(request):
            return False
        user = request.user
        if self.staff and getattr(user, 'is_staff', False):
            return True
        if self.roles is None:
            return not self.staff
        return _has_role(user, self.roles)


class FinanceOrAdminOnWebsite(_WebsitePersonWith):
    roles = ('Finance', 'Admin')
    message = 'This action needs a Finance or Admin user signed in to the CRM website.'


class SalesOrAdminOnWebsite(_WebsitePersonWith):
    roles = ('Sales', 'Admin')
    message = 'This action needs a Sales or Admin user signed in to the CRM website.'


class AdminOnWebsite(_WebsitePersonWith):
    roles = ('Admin',)
    message = 'This action needs an Admin user signed in to the CRM website.'


class StaffOrTechOnWebsite(_WebsitePersonWith):
    roles = ('Tech', 'Admin')
    staff = True
    message = 'This action needs a staff or Tech user signed in to the CRM website.'


class StaffOrAdminOnWebsite(_WebsitePersonWith):
    roles = ('Admin',)
    staff = True
    message = 'This action needs a staff or Admin user signed in to the CRM website.'


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
