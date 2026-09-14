#!/usr/bin/env python3
"""Fixed source supervisor. Drop to each exact UID before opening its data.

Root-owned code only; no agent-controlled executable, environment, path or
arguments are used. No credentials, network or customer mutations.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('production', ROOT / 'agent_crm_production.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def once():
    results = {}
    for uid, source in core.UIDS.items():
        account = pwd.getpwnam(core.ACCOUNTS[uid])
        if account.pw_uid != uid:
            raise ValueError('account_uid_changed')
        # Export and submit run in ONE child with source UID. The Unix socket
        # authenticates that UID; the root supervisor cannot label a body as it.
        command = ['/usr/bin/python3', '-I', '-B', str(ROOT / 'agent_crm_production_sources.py'), '--child', source]
        result = subprocess.run(command, user=uid, group=account.pw_gid,
                                extra_groups=os.getgrouplist(account.pw_name, account.pw_gid),
                                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': account.pw_dir},
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=90)
        results[source] = 'accepted' if result.returncode == 0 else 'failed'
    return results


def child(source):
    if core.UIDS.get(os.geteuid()) != source or os.getuid() != os.geteuid():
        raise ValueError('source_uid_mismatch')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    if any(int(status.get(key, '1').strip(), 16) for key in ('CapEff', 'CapPrm', 'CapAmb')):
        raise ValueError('source_child_must_have_no_capabilities')
    spec = importlib.util.spec_from_file_location('native_export', ROOT / 'agent_crm_native_export.py')
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    document = exporter.export(source)
    response = core.request(document)
    print(json.dumps({'source': source, 'accepted': response.get('accepted') is True,
                      'reason': response.get('reason')}))
    return 0 if response.get('accepted') is True else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--child', choices=core.UIDS.values())
    args = parser.parse_args()
    if args.child:
        return child(args.child)
    if os.geteuid() != 0:
        raise ValueError('supervisor_requires_uid_transition_authority')
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    while running:
        try:
            print(json.dumps(once()), flush=True)
        except Exception as exc:
            print(json.dumps({'source_supervisor': 'failed', 'error_type': type(exc).__name__,
                              'errno': getattr(exc, 'errno', None)}), flush=True)
        if args.once:
            return 0
        for _ in range(300):
            if not running:
                break
            time.sleep(1)


if __name__ == '__main__':
    raise SystemExit(main())
