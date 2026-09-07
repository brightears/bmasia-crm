# Cara hermetic integration tests

These tests use actual CRM model definitions and Django REST Framework against
an in-memory SQLite database. Business signals, production settings and third-
party pytest plugins are not loaded. No email is sent, credential provisioned,
or production database accessed. This does not start a local CRM server or
replace required live Render verification after deployment.

Test-only dependencies in an isolated environment:

- Django `5.2.2`
- djangorestframework `3.15.2`
- pytest `8.4.2`
- psycopg2-binary `2.9.10` (model imports only, no PostgreSQL connection)

From repository root, using that environment's Python:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /absolute/path/to/test-venv/bin/python -m pytest \
  -c tests/cara_readonly/pytest.ini -p no:cacheprovider tests/cara_readonly
```

Coverage includes the dedicated bearer and expiry boundary, non-GET denial,
bounded exact-identity queries, contact preferences, field minimization, stable
hashes, incomplete related sets, pagination, and all three CRM quarterly
handover gates. Gate tests execute the real patched methods but deliberately
stop before SMTP or business bookkeeping; formal renewal behavior remains
ungated. The standard CRM regression suite remains independently required by
the accountable deployment workflow.
