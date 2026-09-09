from django.db.migrations.loader import MigrationLoader
from django.test import override_settings


def test_commercial_release_has_one_migration_head():
    # Functional tests deliberately bypass the legacy from-zero schema chain;
    # still inspect the real graph so a branched release cannot escape coverage.
    with override_settings(MIGRATION_MODULES={}):
        loader = MigrationLoader(None, ignore_no_migrations=True)
    assert loader.detect_conflicts() == {}
    assert loader.graph.leaf_nodes('crm_app') == [
        ('crm_app', '0099_merge_commercial_issuer_and_rene')
    ]
