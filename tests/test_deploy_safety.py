import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _stub_commands(tmp_path):
    calls = tmp_path / "calls.log"
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()

    python_stub = stub_bin / "python"
    python_stub.write_text(
        "#!/bin/sh\n"
        "printf 'python %s\\n' \"$*\" >> \"$DEPLOY_TEST_CALLS\"\n"
        "if [ \"$*\" = 'manage.py migrate --check' ] "
        "&& [ \"${DEPLOY_TEST_PENDING_MIGRATIONS:-0}\" = '1' ]; then\n"
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    )
    python_stub.chmod(0o755)

    for name in ("pip", "gunicorn"):
        stub = stub_bin / name
        stub.write_text(
            "#!/bin/sh\n"
            f"printf '{name} %s\\n' \"$*\" >> \"$DEPLOY_TEST_CALLS\"\n"
            "exit 0\n"
        )
        stub.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "DEPLOY_TEST_CALLS": str(calls),
            "PATH": f"{stub_bin}:{env['PATH']}",
            "PORT": "8000",
        }
    )
    return calls, env


def test_build_skips_crm_bootstrap_by_default(tmp_path):
    calls, env = _stub_commands(tmp_path)

    subprocess.run(["bash", "build.sh"], cwd=ROOT, env=env, check=True)

    invoked = calls.read_text()
    assert "python manage.py collectstatic --no-input" in invoked
    assert "manage.py shell" not in invoked
    assert "create_email_templates" not in invoked
    assert "set_seasonal_dates" not in invoked


def test_start_is_read_only_by_default(tmp_path):
    calls, env = _stub_commands(tmp_path)

    subprocess.run(["bash", "start.sh"], cwd=ROOT, env=env, check=True)

    invoked = calls.read_text()
    assert "python manage.py migrate --check" in invoked
    assert "python manage.py collectstatic --noinput" in invoked
    assert "create_campaign_table_direct.py" not in invoked
    assert "fix_smtp_columns.py" not in invoked
    assert "fix_zone_migration.py" not in invoked
    assert "manage.py migrate --noinput" not in invoked
    assert "apply_migration_0025" not in invoked
    assert "gunicorn bmasia_crm.wsgi:application" in invoked


def test_start_fails_closed_when_migrations_are_pending(tmp_path):
    calls, env = _stub_commands(tmp_path)
    env["DEPLOY_TEST_PENDING_MIGRATIONS"] = "1"

    result = subprocess.run(["bash", "start.sh"], cwd=ROOT, env=env)

    assert result.returncode != 0
    invoked = calls.read_text()
    assert "python manage.py migrate --check" in invoked
    assert "python manage.py showmigrations crm_app" in invoked
    assert "gunicorn" not in invoked


def test_render_release_flags_are_explicit():
    blueprint = (ROOT / "render.yaml").read_text()

    for key, value in (
        ("COMMERCIAL_DOCUMENT_V2_QUOTE_LIVE", "True"),
        ("COMMERCIAL_DOCUMENT_V2_INVOICE_LIVE", "True"),
        ("COMMERCIAL_DOCUMENT_V2_RECEIPT_LIVE", "False"),
        ("RUN_DEPLOY_BOOTSTRAP", "False"),
        ("RUN_LEGACY_DEPLOY_REPAIRS", "False"),
    ):
        assert f"- key: {key}\n        value: \"{value}\"" in blueprint
