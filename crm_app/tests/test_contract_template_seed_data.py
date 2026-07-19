import importlib
from types import SimpleNamespace


class FakeManager:
    def __init__(self):
        self.records = {}
        self.last_filter = None

    def get_or_create(self, name, defaults):
        if name in self.records:
            return self.records[name], False
        self.records[name] = {'name': name, **defaults}
        return self.records[name], True

    def filter(self, **kwargs):
        self.last_filter = kwargs
        return self

    def delete(self):
        name = self.last_filter.get('name')
        version = self.last_filter.get('version')
        record = self.records.get(name)
        if record and record.get('version') == version:
            del self.records[name]
            return 1, {}
        return 0, {}


class FakeApps:
    def __init__(self):
        self.manager = FakeManager()
        self.model = SimpleNamespace(objects=self.manager)

    def get_model(self, app_label, model_name):
        assert app_label == 'crm_app'
        assert model_name == 'ContractTemplate'
        return self.model


def test_seed_beat_breeze_participation_template_creates_active_participation_template():
    migration = importlib.import_module(
        'crm_app.migrations.0097_seed_beat_breeze_participation_template'
    )
    apps = FakeApps()

    migration.create_bb_participation_template(apps, None)

    record = apps.manager.records['Beat Breeze Participation Agreement']
    assert record['template_type'] == 'preamble'
    assert record['pdf_format'] == 'participation'
    assert record['is_active'] is True
    assert record['is_default'] is False
    assert 'Beat Breeze' in record['content']


def test_seed_beat_breeze_participation_template_is_idempotent():
    migration = importlib.import_module(
        'crm_app.migrations.0097_seed_beat_breeze_participation_template'
    )
    apps = FakeApps()

    migration.create_bb_participation_template(apps, None)
    migration.create_bb_participation_template(apps, None)

    assert list(apps.manager.records) == ['Beat Breeze Participation Agreement']


def test_reverse_only_removes_seeded_beat_breeze_participation_template_version():
    migration = importlib.import_module(
        'crm_app.migrations.0097_seed_beat_breeze_participation_template'
    )
    apps = FakeApps()

    migration.create_bb_participation_template(apps, None)
    migration.reverse_bb_participation_template(apps, None)

    assert apps.manager.records == {}
