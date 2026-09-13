#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PINNED_COMMIT = "6d4793dd6d7aeea91aa6a034e00b17d7408a2d08"
MODEL_NAMES = ("Company", "Contact", "Activity", "Deal", "Invoice", "Contract", "Zone")
REQUIRED = {"Company": {"name", "website", "country", "city", "phone", "email", "industry"}, "Contact": {"firstName", "lastName", "email", "phone", "title", "companyId"}, "Activity": {"type", "subject", "body", "occurredAt", "companyId", "contactId"}}
REQUIRED_ROUTES = {"company": {"POST /companies", "PATCH /companies/{id}"}, "contact": {"POST /contacts", "PATCH /contacts/{id}"}, "activity": {"POST /activities", "PATCH /activities/{id}/complete"}}
ROUTERS = ("companies", "contacts", "activities", "deals")


def block_after_model(schema, model):
    match = re.search(rf"^model {model} \{{(.*?)^\}}", schema, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def fields_in_model(schema, model):
    return sorted(match.group(1) for match in re.finditer(r"^\s{2}([A-Za-z][A-Za-z0-9_]*)\s+", block_after_model(schema, model), re.MULTILINE))


def routes_in_router(path):
    return [f"{method} {route}" for method, route in re.findall(r'restMeta\("([A-Z]+)", "([^"]+)"', path.read_text())]


def git_output(candidate, *args):
    return subprocess.run(["git", "-C", str(candidate), *args], check=True, capture_output=True, text=True).stdout.strip()


def source_digest(paths, root):
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def fixture_references(fixture):
    company_id = fixture["company"]["bmasia_id"]
    contact_id = fixture["contact"]["bmasia_id"]
    checks = {"company_has_id": bool(company_id), "contact_has_id": bool(contact_id), "contact_company_matches": fixture["contact"]["company_bmasia_id"] == company_id, "activity_company_matches": fixture["activity"]["company_bmasia_id"] == company_id, "activity_contact_matches": fixture["activity"]["contact_bmasia_id"] == contact_id}
    return checks, all(checks.values())


def shadow_round_trip(fixture):
    company, contact, activity = fixture["company"], fixture["contact"], fixture["activity"]
    candidate_ids = {"company": "candidate-company-001", "contact": "candidate-contact-001"}
    projected = {"company": {key: company[key] for key in ("name", "website", "country", "city", "phone", "email", "industry")}, "contact": {"firstName": contact["first_name"], "lastName": contact["last_name"], "email": contact["email"], "phone": contact["phone"], "title": contact["title"], "companyId": candidate_ids["company"]}, "activity": {"type": activity["kind"].upper(), "subject": activity["subject"], "body": activity["body"], "occurredAt": activity["occurred_at"], "companyId": candidate_ids["company"], "contactId": candidate_ids["contact"]}}
    recovered = {"company": projected["company"], "contact": {"first_name": projected["contact"]["firstName"], "last_name": projected["contact"]["lastName"], "email": projected["contact"]["email"], "phone": projected["contact"]["phone"], "title": projected["contact"]["title"]}, "activity": {"kind": projected["activity"]["type"].lower(), "subject": projected["activity"]["subject"], "body": projected["activity"]["body"], "occurred_at": projected["activity"]["occurredAt"]}}
    expected = {"company": {key: company[key] for key in projected["company"]}, "contact": {key: contact[key] for key in recovered["contact"]}, "activity": {key: activity[key] for key in recovered["activity"]}}
    return {"candidate_ids": candidate_ids, "projected": projected, "recovered": recovered, "matches_fixture": recovered == expected}


def probe(candidate, fixture_path, expected_commit=PINNED_COMMIT):
    candidate = candidate.resolve()
    schema_path = candidate / "packages/db/prisma/schema.prisma"
    source_paths = [schema_path, *(candidate / f"apps/api/src/{router}/{router}.router.ts" for router in ROUTERS)]
    schema = schema_path.read_text()
    fields = {model: fields_in_model(schema, model) for model in MODEL_NAMES}
    routes = {router: routes_in_router(candidate / f"apps/api/src/{router}/{router}.router.ts") for router in ROUTERS}
    fixture = json.loads(fixture_path.read_text())
    reference_checks, references_valid = fixture_references(fixture)
    round_trip = shadow_round_trip(fixture)
    observed_commit = git_output(candidate, "rev-parse", "HEAD")
    clean = not git_output(candidate, "status", "--porcelain")
    base_checks = {"pinned_commit_matches": observed_commit == expected_commit, "candidate_source_clean": clean, "fixture_references_valid": references_valid, "round_trip_matches_fixture": round_trip["matches_fixture"]}
    verified_static = []
    for model, required_fields in REQUIRED.items():
        record = model.lower()
        found = set(fields[model])
        missing_fields = sorted(required_fields - found)
        route_set = set(routes[{"company": "companies", "contact": "contacts", "activity": "activities"}[record]])
        missing_routes = sorted(REQUIRED_ROUTES[record] - route_set)
        gates = {**base_checks, "model_present": bool(fields[model]), "required_fields_present": not missing_fields, "required_routes_present": not missing_routes}
        verified_static.append({"record": record, "status": "verified_static" if all(gates.values()) else "blocked_static", "gates": gates, "schema_fields_present": sorted(required_fields & found), "schema_fields_missing": missing_fields, "required_routes_missing": missing_routes})
    unsupported = []
    for model in ("Contract", "Invoice", "Zone"):
        present = bool(fields[model])
        unsupported.append({"record": model.lower(), "status": "present_static_unassessed" if present else "missing_static", "reason": f"{model} Prisma model {'exists' if present else 'does not exist'}."})
    return {"assessment_type": "static_schema_and_router_contract_probe", "running_application_proof": False, "network_used": False, "packages_installed": False, "live_records_created": False, "candidate": {"expected_commit": expected_commit, "observed_commit": observed_commit, "commit_matches_expected": observed_commit == expected_commit, "source_clean": clean, "tracked_source_sha256": source_digest(source_paths, candidate)}, "fixture": {"references": reference_checks, "round_trip": round_trip}, "schema": {"models": {model: {"present": bool(fields[model]), "fields": fields[model]} for model in MODEL_NAMES}}, "api_manifest": {"routes": routes, "source_files": [str(path.relative_to(candidate)) for path in source_paths]}, "mapping": {"verified_static": verified_static, "unsupported": unsupported, "implementation_gates": ["Resolve BMAsia identifiers to candidate identifiers before relational writes.", "Supply an authenticated candidate user for Activity.createdById and Deal.ownerId.", "This static probe does not prove running application behavior."]}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=Path(__file__).with_name("synthetic_bmasia_fixture.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(probe(args.candidate, args.fixture), indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
