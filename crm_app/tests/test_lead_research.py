"""Weekly lead research: Claude proposes leads, a person approves them, nothing is emailed here."""
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from crm_app.models import (
    Company, Contact, LeadResearchRun, Opportunity, ProspectEnrollment, ProspectSequence,
    ProspectSequenceStep, ResearchLead, Task, User,
)
from crm_app.services import lead_research_service as svc


def _lead_input(**overrides):
    data = {
        "venue_name": "Riverside Grand Bangkok",
        "brand_or_group": "Riverside Hospitality",
        "segment": "hotel",
        "country": "Thailand",
        "city": "Bangkok",
        "opening_timeframe": "opening Q2 2027",
        "signal": "A 220-room riverside hotel announced for Q2 2027 with three restaurants and a rooftop bar.",
        "source_urls": ["https://news.example.com/riverside-grand"],
        "website": "https://riverside.example.com",
        "estimated_zones": 6,
        "suggested_product": "beatbreeze",
        "fit_reason": "New build, several F&B outlets, needs licensed music from day one.",
        "decision_maker_name": "",
        "decision_maker_title": "",
        "contact_email": "",
        "personal_hook": "The rooftop bar is designed by a local studio known for Thai modernism.",
        "score": 82,
    }
    data.update(overrides)
    return data


def _block(type_, **kw):
    return SimpleNamespace(type=type_, **kw)


def _response(stop_reason, content, searches=0):
    usage = SimpleNamespace(input_tokens=100, output_tokens=50,
                            server_tool_use=SimpleNamespace(web_search_requests=searches))
    return SimpleNamespace(stop_reason=stop_reason, content=content, usage=usage)


class FakeClient:
    """Plays back scripted responses and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def _client_recording(leads):
    blocks = [_block("tool_use", id=f"tu_{i}", name="record_lead", input=lead) for i, lead in enumerate(leads)]
    return FakeClient([
        _response("pause_turn", [_block("text", text="searching")], searches=3),
        _response("tool_use", blocks, searches=2),
        _response("end_turn", [_block("text", text="Found the leads above.")]),
    ])


def _person(role="Sales", username="sales-person"):
    return User.objects.create_user(username=username, email=f"{username}@example.com",
                                    password="test-only-password", role=role, is_active=True)


def _website(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def _token(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
    return client


# --- the research run ----------------------------------------------------------------------

def test_run_stores_new_leads_and_counts_usage():
    client = _client_recording([_lead_input(), _lead_input(venue_name="Kopi Corner", segment="qsr",
                                                            city="Ho Chi Minh City", country="Vietnam")])
    run = svc.LeadResearchService(client=client).run(max_leads=5)

    assert run.status == "completed"
    assert run.leads_proposed == 2 and run.leads_saved == 2
    assert run.web_searches == 5
    assert run.input_tokens == 300
    assert ResearchLead.objects.filter(status="new").count() == 2
    lead = ResearchLead.objects.get(venue_name="Riverside Grand Bangkok")
    assert lead.run_id == run.id and lead.score == 82

    first = client.calls[0]
    assert first["model"] == "claude-opus-5-5"
    assert first["tools"][0]["type"] == "web_search_20260209"
    assert first["tools"][1]["name"] == "record_lead" and first["tools"][1]["strict"] is True
    # The paused turn is sent back so the server continues it.
    assert client.calls[1]["messages"][-1]["role"] == "assistant"
    # Tool results go back in one user message.
    results = client.calls[2]["messages"][-1]
    assert results["role"] == "user" and len(results["content"]) == 2


def test_run_skips_leads_without_a_source_or_already_known():
    Company.objects.create(name="Kopi Corner")
    Opportunity.objects.create(company=Company.objects.get(name="Kopi Corner"), name="Existing deal")
    leads = [
        _lead_input(),
        _lead_input(),                                   # duplicate within the run
        _lead_input(venue_name="No Source Hotel", source_urls=[]),
        _lead_input(venue_name="Kopi Corner"),           # already worked in the CRM
        _lead_input(venue_name="Guessed Mail Hotel", contact_email="not-an-email"),
    ]
    run = svc.LeadResearchService(client=_client_recording(leads)).run(max_leads=10)

    assert set(ResearchLead.objects.values_list("venue_name", flat=True)) == {
        "Riverside Grand Bangkok", "Guessed Mail Hotel"}
    assert run.duplicates_skipped == 2
    assert ResearchLead.objects.get(venue_name="Guessed Mail Hotel").contact_email == ""


def test_lead_proposed_in_an_earlier_run_is_not_proposed_again():
    svc.LeadResearchService(client=_client_recording([_lead_input()])).run()
    run = svc.LeadResearchService(client=_client_recording([_lead_input(venue_name="The Riverside Grand, Bangkok")])).run()
    assert run.leads_saved == 0 and run.duplicates_skipped == 1


def test_dry_run_saves_nothing():
    run = svc.LeadResearchService(client=_client_recording([_lead_input()])).run(dry_run=True)
    assert run.leads_saved == 1 and len(run.dry_run_leads) == 1
    assert not ResearchLead.objects.exists() and not LeadResearchRun.objects.exists()


def test_run_without_api_key_fails_cleanly(settings):
    settings.ANTHROPIC_API_KEY = ""
    run = svc.LeadResearchService().run()
    assert run.status == "failed" and "ANTHROPIC_API_KEY" in run.error_message


def test_refusal_marks_the_run_failed():
    client = FakeClient([_response("refusal", [])])
    run = svc.LeadResearchService(client=client).run()
    assert run.status == "failed"
    assert not ResearchLead.objects.exists()


def test_command_does_nothing_while_switched_off(monkeypatch, capsys):
    monkeypatch.delenv("LEAD_RESEARCH_ENABLED", raising=False)
    called = []
    monkeypatch.setattr(svc.LeadResearchService, "run", lambda *a, **k: called.append(1))
    call_command("research_new_venues")
    assert not called
    assert "off" in capsys.readouterr().out


# --- review ---------------------------------------------------------------------------------

def _stored_lead(**overrides):
    fields = svc._clean_lead(_lead_input(**overrides))
    return ResearchLead.objects.create(dedupe_key=svc.dedupe_key(fields["venue_name"], fields["city"]), **fields)


def test_approve_without_email_creates_company_opportunity_and_task_but_no_enrollment():
    user = _person()
    sequence = ProspectSequence.objects.create(name="New lead", trigger_type="new_opportunity")
    ProspectSequenceStep.objects.create(sequence=sequence, step_number=1, action_type="ai_email")
    lead = _stored_lead()

    response = _website(user).post(f"/api/v1/research-leads/{lead.id}/approve/", {}, format="json")

    assert response.status_code == 200, response.content
    lead.refresh_from_db()
    assert lead.status == "approved" and lead.reviewed_by == user
    company = lead.matched_company
    assert company.name == "Riverside Grand Bangkok"
    assert company.billing_entity == "BMAsia (Thailand) Co., Ltd."
    assert not Contact.objects.filter(company=company).exists()
    opp = lead.opportunity
    assert opp.lead_source == "AI Research" and opp.service_type == "beatbreeze"
    assert opp.expected_value == 290 * 6
    assert Task.objects.get(related_opportunity=opp).title.startswith("Find the decision maker")
    assert not ProspectEnrollment.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_approve_with_published_email_enrolls_in_new_opportunity_sequences():
    user = _person()
    sequence = ProspectSequence.objects.create(name="New lead", trigger_type="new_opportunity")
    ProspectSequenceStep.objects.create(sequence=sequence, step_number=1, action_type="ai_email")
    lead = _stored_lead(contact_email="sales@riverside.example.com", decision_maker_name="Somchai P.",
                        decision_maker_title="General Manager")

    response = _website(user).post(f"/api/v1/research-leads/{lead.id}/approve/",
                                   {"service_type": "soundtrack"}, format="json")

    assert response.status_code == 200, response.content
    lead.refresh_from_db()
    contact = Contact.objects.get(company=lead.matched_company)
    assert contact.email == "sales@riverside.example.com" and contact.is_primary
    assert lead.opportunity.service_type == "soundtrack"
    enrollment = ProspectEnrollment.objects.get()
    assert enrollment.contact == contact and enrollment.opportunity == lead.opportunity


def test_approve_twice_is_refused():
    user = _person()
    lead = _stored_lead()
    client = _website(user)
    assert client.post(f"/api/v1/research-leads/{lead.id}/approve/").status_code == 200
    assert client.post(f"/api/v1/research-leads/{lead.id}/approve/").status_code == 400
    assert Opportunity.objects.count() == 1


def test_reject_records_reason():
    user = _person()
    lead = _stored_lead()
    response = _website(user).post(f"/api/v1/research-leads/{lead.id}/reject/", {"reason": "Too small"}, format="json")
    assert response.status_code == 200
    lead.refresh_from_db()
    assert lead.status == "rejected" and lead.rejection_reason == "Too small"
    assert not Company.objects.exists()


def test_agents_and_api_tokens_can_read_but_not_approve():
    user = _person()
    lead = _stored_lead()
    client = _token(user)
    assert client.get("/api/v1/research-leads/").status_code == 200
    assert client.post(f"/api/v1/research-leads/{lead.id}/approve/").status_code == 403
    lead.refresh_from_db()
    assert lead.status == "new"


def test_roles_without_sales_access_cannot_see_leads():
    _stored_lead()
    tech = _person(role="Tech", username="tech-person")
    assert _website(tech).get("/api/v1/research-leads/").status_code == 403


def test_approve_reuses_an_existing_company_with_the_same_name():
    existing = Company.objects.create(name="Riverside Grand Bangkok")
    lead = _stored_lead()
    lead.matched_company = existing
    lead.save()
    svc.approve_lead(lead, _person())
    lead.refresh_from_db()
    assert lead.matched_company == existing
    assert Company.objects.count() == 1
