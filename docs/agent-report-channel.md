# Authenticated synthetic report channel

Authorization: Norbert, 14 September 2026. Owner: Vera. This is synthetic-only,
not live CRM synchronization. Comp AI is not installed. Cira retains sole
CRM/document mutation authority; no write allowlists or agent policies change.

## Boundary

One Unix socket, `/run/bmasia-agent-shadow/collector.sock`, accepts framed JSON
reports. The server obtains Linux `SO_PEERCRED` before reading the payload:

| Source | Runtime account | UID |
| --- | --- | --- |
| Theo | theo_ai | 1008 |
| Lyra | bmasia | 1000 |
| Riff | riff_ai | 1007 |
| Nina | nina | 1004 |

These are OS-account identities, not process/model/person attestation. Lyra's
existing `bmasia` operator account has sudo authority and is part of the trusted
host-administrator boundary. A host administrator can impersonate any runtime;
this protocol does not claim protection from root or a compromised administrator.

Reporter names must match the actual peer UID. Context, verification flags and
request IDs are server-constructed; sender-supplied metadata is rejected. Every
accepted report must exactly match a hash in the operator-installed synthetic
registry. Non-allowlisted report content is neither echoed nor persisted.
Evidence verification binds literal synthetic bytes, not factual truth. There
is no URL/path resolver, network call, model, Cira queue or CRM connection.

Shared socket permissions do not imply report authority: other group members
are rejected by UID. The state directory is owned by Vera and mode 0700; code,
configuration and registry are operator-owned and not writable by producers.
The service has only AF_UNIX networking, protected system/home paths and explicit
write paths. Existing Vera services do not need restarting.

## Limits and receipts

- Requests: 32 KiB, exact schema, duplicate JSON keys/nonfinite values rejected.
- Responses: 128 KiB. Client timeout 5 seconds; no automatic retry/fallback.
- Local read deadline: 0.2 seconds; 10 connections/minute per source UID;
  unknown peers share one rate bucket. Serialized processing is suitable only
  for this bounded synthetic acceptance stage, not a production availability SLA.
- The root-installed registry contains at most 32 exact fake report variants.
- Request metadata keeps the most recent 10,000 entries; oldest metadata is
  rotated transactionally. Immutable synthetic result receipts remain retained.
  No real-customer retention policy is implied by this synthetic setting.

`accepted` means recorded in the private shadow ledger, never applied to CRM.
Identical retries are `replayed` with the original receipt ID; changed content
under the same event ID is `conflict`. Missing evidence is
`needs_source_verification`. Clients exit nonzero for anything except accepted
or replayed, and never send a customer message.

Core receipts and channel request metadata use two SQLite databases. They are
not one atomic transaction. An audit failure returns `indeterminate` /
`audit_unavailable`, not success or a rollback claim: a private core receipt may
already exist. Retrying the **identical** event after recovery recovers its stable
receipt and records the channel audit. Do not generate a new event to retry an
uncertain result. This cannot produce a CRM/customer effect.

## Installation and operator checks

Deploy a versioned, root-owned directory under
`/opt/vera-hermes/deploy/agent-shadow/releases/`, including collector.py and a
pinned copy of `crm_app/services/agent_shadow.py` as agent_shadow.py. `current`
selects that release. Install config.synthetic.json as config.json and freshly
generated make_synthetic_fixtures.py registry.json at the parent path.

Install client.py root-owned under `/usr/local/lib/bmasia-agent-shadow/` and the
provided wrapper as `/usr/local/bin/bmasia-agent-report`. Only fake fixtures may
be installed under `/usr/local/share/bmasia-agent-shadow/synthetic/` for acceptance.
Create `/opt/vera-hermes/data/runtime/agent-shadow-channel` owned by vera_ai and
mode 0700. Validate the exact supplied systemd unit before enabling/starting it.
The only new unit is `vera-agent-shadow-collector.service`.

Run each fake report as its actual runtime user, using the shared host transport:

```bash
sudo -n -u theo_ai /usr/local/bin/bmasia-agent-report --report /usr/local/share/bmasia-agent-shadow/synthetic/theo-valid.json
sudo -n -u vera_ai /usr/bin/python3 -I -B /opt/vera-hermes/deploy/agent-shadow/current/collector.py --config /opt/vera-hermes/deploy/agent-shadow/config.json --status
```

Repeat the exact valid report for replay; submit its collision and unverified
variants. Check all four real UIDs, raw-socket impersonation rejection, unknown
UID rejection, and replay after restarting only the new unit. Record receipts,
file modes, unit sandbox settings and unchanged existing-service PIDs. Do not
mark live agent reporting connected merely from these tests.

## Rollback and next gate

Stop and disable **only** `vera-agent-shadow-collector.service`. Leave the
private synthetic ledger and versioned release available for diagnosis; no CRM
rollback or customer record cleanup is needed. Repoint `current` only to a
validated compatible release while stopped. Preserve the fixture registry when
checking historical retries.

Live shadow reporting needs a separately approved exact account/record scope,
evidence resolver, fresh read-only CRM snapshot adapter, access/retention policy,
producer workflow wiring, availability design and monitoring targets. Changing
`environment` to `shadow` is explicitly rejected by this implementation. It is
not an activation switch. CRM promotions require a further explicit Cira-owned
approval, fresh version checks and readback.
