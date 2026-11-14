"""Auth-method observability: recorded and logged, never a credential, no behaviour change."""
import json
import logging
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from mcp_server.djangomcp import django_request_ctx
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from crm_app import auth_observability as obs
from crm_app.cara_api import CaraPrincipal
from crm_app.mcp import create_record
from crm_app.models import AgentRequest, AuditLog, Company
from crm_app.rene_auth import RenePhase2MCPCredential, ReneRenewalPrincipal

UA = 'observability-test/1.0'


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


@pytest.fixture
def auth_log():
    handler = _ListHandler()
    logger = logging.getLogger('crm_app.auth')
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield handler.lines
    logger.removeHandler(handler)
    logger.setLevel(previous)


def _user(username, role='Admin'):
    user, _ = get_user_model().objects.get_or_create(
        username=username, defaults={'email': f'{username}@example.test', 'role': role},
    )
    return user


def _token(username):
    return Token.objects.get_or_create(user=_user(username))[0].key


def _mcp(client, payload, *, path='/mcp/', authorization=None):
    extra = {'HTTP_ACCEPT': 'application/json, text/event-stream', 'HTTP_USER_AGENT': UA}
    if authorization is not None:
        extra['HTTP_AUTHORIZATION'] = authorization
    return client.post(path, payload, format='json', **extra)


def _tools_list():
    return {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}


def _crm_lines(lines):
    return [line for line in lines if line.startswith('crm_auth ')]


# ------------------------------------------------------------------ MCP


def test_mcp_header_token_is_logged_by_method_and_user(auth_log):
    key = _token('theo')
    response = _mcp(APIClient(), _tools_list(), authorization=f'Token {key}')
    assert response.status_code == 200
    lines = _crm_lines(auth_log)
    assert len(lines) == 1
    line = lines[0]
    assert 'path=/mcp/ ' in line
    assert 'method=token_header' in line and 'presented=header:Token' in line
    assert 'user=theo' in line and 'principal=theo' in line and 'status=200' in line
    assert f'ua="{UA}"' in line
    assert key not in ' '.join(auth_log)


def test_mcp_query_token_is_logged_without_the_token_or_query_string(auth_log):
    key = _token('reader-one')
    response = _mcp(APIClient(), _tools_list(), path=f'/mcp/?token={key}')
    assert response.status_code == 200
    lines = _crm_lines(auth_log)
    assert len(lines) == 1
    assert 'method=token_query' in lines[0] and 'presented=query' in lines[0]
    assert 'path=/mcp/ ' in lines[0]
    assert key not in ' '.join(auth_log)
    assert 'token=' not in ' '.join(auth_log)


def test_refused_mcp_credential_is_logged_by_kind_only(auth_log):
    bogus = 'f' * 40
    response = _mcp(APIClient(), _tools_list(), path=f'/mcp/?token={bogus}')
    assert response.status_code == 401
    lines = _crm_lines(auth_log)
    assert len(lines) == 1
    assert 'method=anonymous' in lines[0] and 'presented=query' in lines[0]
    assert 'status=401' in lines[0] and 'user=- ' in lines[0]
    assert bogus not in ' '.join(auth_log)


def test_request_without_any_credential_is_not_logged(auth_log):
    assert _mcp(APIClient(), _tools_list()).status_code == 401
    assert _crm_lines(auth_log) == []


@contextmanager
def _mcp_caller(username, *, in_url):
    """The MCP request context as the transport leaves it after DRF authentication."""
    user = _user(username)
    request = SimpleNamespace(
        user=user, auth=Token.objects.get_or_create(user=user)[0],
        META={'REMOTE_ADDR': '10.0.0.9', 'HTTP_USER_AGENT': UA},
    )
    if in_url:
        obs.mark_query_token(request)
    token = django_request_ctx.set(request)
    try:
        yield request
    finally:
        django_request_ctx.reset(token)


def _create(name):
    return json.loads(create_record('company', json.dumps({'name': name, 'billing_entity': 'BMAsia Limited'})))


def test_mcp_write_records_auth_method_and_principal_in_audit_and_gate():
    with _mcp_caller('cira', in_url=False) as header_request:
        header_id = _create('Header caller co')['id']
    with _mcp_caller('cira', in_url=True):
        query_id = _create('Query caller co')['id']

    header_row = AuditLog.objects.get(record_id=str(header_id))
    query_row = AuditLog.objects.get(record_id=str(query_id))
    assert header_row.additional_data['auth_method'] == 'token_header'
    assert query_row.additional_data['auth_method'] == 'token_query'
    assert header_row.additional_data['principal'] == query_row.additional_data['principal'] == 'cira'
    assert header_row.user.username == 'cira'
    key = header_request.auth.key
    assert key not in json.dumps(header_row.additional_data) + json.dumps(query_row.additional_data)

    gate_rows = list(AgentRequest.objects.filter(username='cira').order_by('created_at'))
    assert len(gate_rows) == 2
    assert obs.CREDENTIAL_IN_URL not in gate_rows[0].protocol_gaps
    assert obs.CREDENTIAL_IN_URL in gate_rows[1].protocol_gaps
    assert gate_rows[1].decision == gate_rows[0].decision == 'allow'
    # The existing gaps are unchanged; the new code is only appended.
    assert gate_rows[1].protocol_gaps[:-1] == gate_rows[0].protocol_gaps


def test_unlisted_user_writing_with_a_url_token_gets_only_the_url_gap():
    with _mcp_caller('someone', in_url=True):
        assert 'id' in _create('Human query co')
    row = AgentRequest.objects.get(username='someone')
    assert row.decision == 'not_agent'
    assert row.protocol_gaps == [obs.CREDENTIAL_IN_URL]
    with _mcp_caller('someone-else', in_url=False):
        _create('Human header co')
    assert AgentRequest.objects.get(username='someone-else').protocol_gaps == []


# ------------------------------------------------------------------ REST


def test_rest_agent_token_request_is_logged(auth_log):
    key = _token('theo')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {key}', HTTP_USER_AGENT=UA)
    assert client.get('/api/v1/companies/').status_code == 200
    lines = _crm_lines(auth_log)
    assert len(lines) == 1
    assert 'path=/api/v1/companies/ ' in lines[0]
    assert 'method=token_header' in lines[0] and 'user=theo' in lines[0] and 'principal=theo' in lines[0]
    assert key not in ' '.join(auth_log)


def test_rest_human_token_request_is_logged_without_principal(auth_log):
    key = _token('desk-reader')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {key}')
    assert client.get('/api/v1/companies/?search=nothing').status_code == 200
    lines = _crm_lines(auth_log)
    assert len(lines) == 1
    assert 'user=desk-reader' in lines[0] and 'principal=-' in lines[0]
    assert 'search=' not in lines[0]


def test_website_jwt_requests_are_not_logged(auth_log):
    user = _user('website-person', role='Sales')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    assert client.get('/api/v1/companies/').status_code == 200
    assert _crm_lines(auth_log) == []


def test_rest_responses_are_unchanged_by_the_middleware():
    key = _token('theo')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {key}')
    Company.objects.create(name='Visible co', billing_entity='BMAsia Limited')
    response = client.get('/api/v1/companies/')
    assert response.status_code == 200
    assert 'Visible co' in json.dumps(response.json())


# ------------------------------------------------------------------ classification


def test_auth_method_classification():
    user = _user('classify')
    assert obs.auth_method(None) == obs.ANONYMOUS
    assert obs.auth_method(SimpleNamespace(user=SimpleNamespace(is_authenticated=False))) == obs.ANONYMOUS
    token = Token.objects.get_or_create(user=user)[0]
    assert obs.auth_method(SimpleNamespace(user=user, auth=token)) == obs.TOKEN_HEADER
    flagged = SimpleNamespace(user=user, auth=token)
    obs.mark_query_token(flagged)
    assert obs.auth_method(flagged) == obs.TOKEN_QUERY
    assert obs.auth_method(SimpleNamespace(user=user, auth=AccessToken.for_user(user))) == obs.JWT
    assert obs.auth_method(SimpleNamespace(user=user, auth=None)) == obs.SESSION
    credential = RenePhase2MCPCredential(token_fingerprint_sha256='0' * 64, user_id=str(user.pk))
    assert obs.auth_method(SimpleNamespace(user=user, auth=credential)) == obs.RENE_MCP
    rene = ReneRenewalPrincipal(token_fingerprint_sha256='0' * 64)
    assert obs.auth_method(SimpleNamespace(user=rene, auth=None)) == obs.RENE_BEARER
    cara = CaraPrincipal(token_fingerprint_sha256='0' * 64)
    assert obs.auth_method(SimpleNamespace(user=cara, auth=None)) == obs.CARA_BEARER
    assert obs.auth_method(SimpleNamespace(user=user, auth=object())) == obs.OTHER


def test_presented_credential_names_the_kind_only():
    def req(meta=None, query=None):
        return SimpleNamespace(META=meta or {}, GET=query or {})
    assert obs.presented_credential(req({'HTTP_AUTHORIZATION': 'Token abc'})) == 'header:Token'
    assert obs.presented_credential(req({'HTTP_AUTHORIZATION': 'Bearer abc'})) == 'header:Bearer'
    assert obs.presented_credential(req({'HTTP_AUTHORIZATION': 'Weird abc'})) == 'header:other'
    assert obs.presented_credential(req(query={'token': 'abc'})) == 'query'
    assert obs.presented_credential(req()) == 'none'


def test_user_agent_cannot_break_the_log_line(auth_log):
    key = _token('reader-two')
    client = APIClient()
    client.post(
        '/mcp/', _tools_list(), format='json', HTTP_ACCEPT='application/json, text/event-stream',
        HTTP_AUTHORIZATION=f'Token {key}', HTTP_USER_AGENT='evil" user=admin\nnext',
    )
    line = _crm_lines(auth_log)[0]
    assert '\n' not in line
    assert 'ua="evil\' user=admin next"' in line
    assert line.count(' user=') == 2  # the real field plus the quoted user-agent text
