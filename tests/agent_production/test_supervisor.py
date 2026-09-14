import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest

spec = importlib.util.spec_from_file_location('sources', Path(__file__).resolve().parents[2] / 'tools/agent_crm_production_sources.py')
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)


def test_source_child_rejects_wrong_uid_before_source_access():
    with patch.object(sources.os, 'geteuid', return_value=0):
        with pytest.raises(ValueError, match='source_uid_mismatch'):
            sources.child('theo')


def test_source_child_rejects_retained_capabilities_before_source_access():
    with patch.object(sources.os, 'geteuid', return_value=1008), patch.object(sources.os, 'getuid', return_value=1008), patch.object(sources.Path, 'read_text', return_value='CapEff:\t00000080\nCapPrm:\t00000080\nCapAmb:\t0\n'):
        with pytest.raises(ValueError, match='source_child_must_have_no_capabilities'):
            sources.child('theo')


def test_supervisor_has_only_uid_transition_capabilities_and_unix_network():
    unit = (Path(__file__).resolve().parents[2] / 'deploy/agent-production/vera-agent-production-sources.service').read_text()
    assert 'CapabilityBoundingSet=CAP_SETUID CAP_SETGID\n' in unit
    assert 'AmbientCapabilities=CAP_SETUID CAP_SETGID\n' in unit
    assert 'RestrictAddressFamilies=AF_UNIX\n' in unit
    assert 'ProtectSystem=strict\n' in unit
