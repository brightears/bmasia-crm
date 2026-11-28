"""Weekly lead research: Claude searches the web for new venues and proposes leads.

The routine only writes ResearchLead rows with status 'new'. A person reviews
each lead in the CRM; approving one creates the company, contact and
opportunity (which then enters the existing prospect sequences, whose AI
emails wait for approval in AI Email Drafts). Nothing here sends email.
"""

import json
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from crm_app.models import (
    Company,
    Contact,
    LeadResearchRun,
    Opportunity,
    ResearchLead,
    Task,
)

logger = logging.getLogger(__name__)

try:
    import anthropic
except ImportError:  # pragma: no cover - the package is in requirements.txt
    anthropic = None

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_SEGMENTS = ["hotel", "retail", "qsr"]
DEFAULT_COUNTRIES = ["Thailand", "Vietnam", "Malaysia", "Singapore", "Indonesia", "Cambodia"]
# A lead already proposed (any status) within this window is not proposed again.
DEDUPE_WINDOW_DAYS = 180
MAX_LOOP_TURNS = 12

SEGMENT_INDUSTRY = {
    "hotel": "Hotels",
    "retail": "Retail Fashion",
    "qsr": "Quick Service Restaurants",
    "fnb": "Restaurants",
    "other": "Other",
}

SYSTEM_PROMPT = """You are the research assistant for BMAsia Group, a background music company \
based in Bangkok that has served hotels, restaurants and retail across Southeast Asia since 2002.

Products:
- Beat Breeze: all-inclusive licensed background music, USD 290 per zone per year. \
Fully royalty-free, so no separate music-licence fees. Best for independent and mid-size \
venues, QSR and retail chains that want simple, low-cost, legally safe music. Sold priority.
- Soundtrack Your Brand: premium streaming background music, USD 400 per zone per year. \
Best for international hotel brands and premium/luxury retail with brand-curated music.

Your job: find REAL, RECENT, VERIFIABLE signals that a venue will soon need background music:
- Hotels: openings or reopenings in the next 12 months or the last 6 months, rebrands, \
major renovations. Minimum 50 rooms, 3-star or higher.
- Fashion retail: international brands entering the market, flagship openings (200+ sqm), \
chains adding 5+ stores.
- QSR / F&B chains: regional chains with 10+ outlets announcing expansion.

Rules:
- Use web search. Only record a lead you found in a source published in the last 6 months, \
and include that source URL. Never invent a venue, a person or an email address.
- contact_email: only a business address published on the venue's or company's own site \
or in a press release (e.g. sales@, info@, gm@). Leave it empty otherwise. Never guess \
an address from a name pattern. Do not record personal or private contact details.
- decision_maker_name: only if a public source names the person in that role \
(GM, F&B Director, Head of Retail Operations, Operations Director). Otherwise leave empty.
- personal_hook: one concrete, specific detail a salesperson can open with \
(the concept, the designer, the opening date, a quote from the GM). Not generic flattery.
- suggested_product: "beatbreeze" unless the venue is an international luxury brand that \
will want brand-curated music, then "soundtrack".
- Skip any venue in the EXCLUDE list below; those are already in the CRM or already proposed.
- Call record_lead once per lead. When you have recorded the leads you found (up to the \
maximum), stop and reply with a one-paragraph summary."""

RECORD_LEAD_TOOL = {
    "name": "record_lead",
    "description": (
        "Record one qualified lead: a specific venue or chain with a recent opening, "
        "expansion or renovation signal. Call once per lead."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "venue_name": {"type": "string", "description": "Venue or chain name as it will trade"},
            "brand_or_group": {"type": "string", "description": "Operator, brand or parent group; empty if unknown"},
            "segment": {"type": "string", "enum": ["hotel", "retail", "qsr", "fnb", "other"]},
            "country": {"type": "string"},
            "city": {"type": "string"},
            "opening_timeframe": {"type": "string", "description": "e.g. 'opening Q2 2027' or 'opened Oct 2026'"},
            "signal": {"type": "string", "description": "What happened, in one or two sentences"},
            "source_urls": {"type": "array", "items": {"type": "string"}},
            "website": {"type": "string", "description": "Official website URL; empty if none"},
            "estimated_zones": {"type": "integer", "description": "Estimated music zones (lobby, restaurant, bar, spa, each store...)"},
            "suggested_product": {"type": "string", "enum": ["beatbreeze", "soundtrack"]},
            "fit_reason": {"type": "string"},
            "decision_maker_name": {"type": "string"},
            "decision_maker_title": {"type": "string"},
            "contact_email": {"type": "string", "description": "Published business address only, else empty"},
            "personal_hook": {"type": "string"},
            "score": {"type": "integer", "description": "Fit 0-100: size, timing, budget and product fit"},
        },
        "required": [
            "venue_name", "brand_or_group", "segment", "country", "city", "opening_timeframe",
            "signal", "source_urls", "website", "estimated_zones", "suggested_product",
            "fit_reason", "decision_maker_name", "decision_maker_title", "contact_email",
            "personal_hook", "score",
        ],
        "additionalProperties": False,
    },
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalise_name(name):
    """Lower-case a venue or company name and drop punctuation and filler words."""
    text = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower())
    filler = {"the", "hotel", "hotels", "resort", "and", "co", "ltd", "limited", "company", "group", "thailand"}
    words = [w for w in text.split() if w not in filler]
    return " ".join(words) or text.strip()


def dedupe_key(venue_name, city):
    return f"{normalise_name(venue_name)}|{(city or '').strip().lower()}"[:255]


def find_matching_company(venue_name, brand_or_group=""):
    """Return an existing Company whose normalised name equals the venue's or brand's, if any."""
    wanted = {normalise_name(venue_name)}
    if brand_or_group:
        wanted.add(normalise_name(brand_or_group))
    wanted.discard("")
    if not wanted:
        return None
    from django.db.models import Q
    query = Q()
    for name in wanted:
        query |= Q(name__icontains=max(name.split(), key=len))
    for company in Company.objects.filter(query).only("id", "name")[:500]:
        if normalise_name(company.name) in wanted:
            return company
    return None


def _exclude_list(limit=150):
    """Names Claude should skip: recent proposals plus the newest companies in the CRM."""
    since = timezone.now() - timedelta(days=DEDUPE_WINDOW_DAYS)
    proposed = list(
        ResearchLead.objects.filter(created_at__gte=since)
        .order_by('-created_at').values_list('venue_name', flat=True)[:limit]
    )
    companies = list(Company.objects.order_by('-created_at').values_list('name', flat=True)[:limit])
    return sorted(set(proposed + companies))


def _clean_lead(raw):
    """Coerce one record_lead input into model fields; returns None if unusable."""
    venue = (raw.get("venue_name") or "").strip()
    signal = (raw.get("signal") or "").strip()
    urls = [u for u in (raw.get("source_urls") or []) if isinstance(u, str) and u.startswith("http")]
    if not venue or not signal or not urls:
        return None
    email = (raw.get("contact_email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        email = ""
    website = (raw.get("website") or "").strip()
    if website and not website.startswith("http"):
        website = ""
    segment = raw.get("segment") if raw.get("segment") in dict(ResearchLead.SEGMENT_CHOICES) else "other"
    product = raw.get("suggested_product") if raw.get("suggested_product") in dict(ResearchLead.PRODUCT_CHOICES) else "beatbreeze"
    zones = raw.get("estimated_zones")
    zones = zones if isinstance(zones, int) and 0 < zones < 1000 else None
    score = raw.get("score") if isinstance(raw.get("score"), int) else 0
    return {
        "venue_name": venue[:255],
        "brand_or_group": (raw.get("brand_or_group") or "")[:255],
        "segment": segment,
        "country": (raw.get("country") or "")[:100],
        "city": (raw.get("city") or "")[:100],
        "opening_timeframe": (raw.get("opening_timeframe") or "")[:100],
        "signal": signal,
        "source_urls": urls[:10],
        "website": website[:200],
        "estimated_zones": zones,
        "suggested_product": product,
        "fit_reason": raw.get("fit_reason") or "",
        "decision_maker_name": (raw.get("decision_maker_name") or "")[:255],
        "decision_maker_title": (raw.get("decision_maker_title") or "")[:255],
        "contact_email": email[:254],
        "personal_hook": raw.get("personal_hook") or "",
        "score": max(0, min(100, score)),
    }


class LeadResearchService:
    """Runs one research pass and stores the proposed leads for review."""

    def __init__(self, client=None, model=None):
        self.model = model or getattr(settings, "LEAD_RESEARCH_MODEL", "") or DEFAULT_MODEL
        if client is not None:
            self.client = client
        else:
            api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
            self.client = anthropic.Anthropic(api_key=api_key) if (anthropic and api_key) else None

    def is_available(self):
        return self.client is not None

    def _user_prompt(self, segments, countries, max_leads):
        today = timezone.localdate().isoformat()
        exclude = _exclude_list()
        return (
            f"Today is {today}. Find up to {max_leads} new leads.\n"
            f"Segments: {', '.join(segments)}.\n"
            f"Countries: {', '.join(countries)}.\n"
            "Spread the leads across segments and countries where the evidence allows; "
            "quality over quantity. Fewer real leads beat padded ones.\n\n"
            "EXCLUDE (already known):\n" + "\n".join(f"- {name}" for name in exclude)
        )

    def run(self, segments=None, countries=None, max_leads=15, user=None, dry_run=False):
        """Run one research pass. Returns the LeadResearchRun (unsaved when dry_run)."""
        segments = segments or DEFAULT_SEGMENTS
        countries = countries or DEFAULT_COUNTRIES
        run = LeadResearchRun(
            segments=segments, countries=countries, model=self.model, triggered_by=user,
        )
        if not dry_run:
            run.save()
        if not self.is_available():
            return self._fail(run, "Claude is not configured (missing ANTHROPIC_API_KEY)", dry_run)

        proposed = []
        try:
            proposed = self._converse(run, segments, countries, max_leads)
        except Exception as exc:  # recorded on the run; the cron keeps going next week
            logger.exception("Lead research run failed")
            return self._fail(run, str(exc)[:2000], dry_run)

        run.leads_proposed = len(proposed)
        saved, dupes = self._store(run, proposed[:max_leads], dry_run)
        run.leads_saved = len(saved)
        run.duplicates_skipped = dupes
        run.status = "completed"
        run.finished_at = timezone.now()
        run.dry_run_leads = saved if dry_run else []
        if not dry_run:
            run.save()
        return run

    def _fail(self, run, message, dry_run):
        run.status = "failed"
        run.error_message = message
        run.finished_at = timezone.now()
        run.dry_run_leads = []
        if not dry_run:
            run.save()
        return run

    def _converse(self, run, segments, countries, max_leads):
        tools = [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": max(10, max_leads * 3)},
            RECORD_LEAD_TOOL,
        ]
        messages = [{"role": "user", "content": self._user_prompt(segments, countries, max_leads)}]
        proposed = []

        for _ in range(MAX_LOOP_TURNS):
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
                output_config={"effort": "high"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                run.input_tokens += getattr(usage, "input_tokens", 0) or 0
                run.output_tokens += getattr(usage, "output_tokens", 0) or 0
                server_use = getattr(usage, "server_tool_use", None)
                run.web_searches += getattr(server_use, "web_search_requests", 0) or 0

            if response.stop_reason == "refusal":
                raise RuntimeError("The model declined the research request")

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "pause_turn":
                continue

            tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses:
                break

            results = []
            for block in tool_uses:
                if block.name != "record_lead":
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": "Unknown tool", "is_error": True})
                    continue
                raw = block.input if isinstance(block.input, dict) else json.loads(block.input)
                proposed.append(raw)
                remaining = max_leads - len(proposed)
                note = "Recorded." if remaining > 0 else "Recorded. That is the maximum; stop and summarise."
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": note})
            messages.append({"role": "user", "content": results})
        return proposed

    def _store(self, run, proposed, dry_run):
        since = timezone.now() - timedelta(days=DEDUPE_WINDOW_DAYS)
        saved, dupes, seen = [], 0, set()
        for raw in proposed:
            fields = _clean_lead(raw)
            if fields is None:
                continue
            key = dedupe_key(fields["venue_name"], fields["city"])
            if key in seen or ResearchLead.objects.filter(dedupe_key=key, created_at__gte=since).exists():
                dupes += 1
                continue
            seen.add(key)
            company = find_matching_company(fields["venue_name"], fields["brand_or_group"])
            if company is not None and company.opportunities.filter(is_active=True).exists():
                # Already being worked in the CRM.
                dupes += 1
                continue
            lead = ResearchLead(run=None if dry_run else run, dedupe_key=key, matched_company=company, **fields)
            if not dry_run:
                lead.save()
            saved.append(lead)
        return saved, dupes


def _unique_company_name(base):
    name = base[:255]
    if not Company.objects.filter(name__iexact=name).exists():
        return name
    for n in range(2, 50):
        candidate = f"{base[:245]} ({n})"
        if not Company.objects.filter(name__iexact=candidate).exists():
            return candidate
    raise ValueError("Could not find a free company name")


@transaction.atomic
def approve_lead(lead, user, service_type=None, owner=None):
    """Turn a reviewed lead into CRM records and enter it into the prospect sequences.

    Creates (or reuses) the company, adds the contact only when the lead has a
    published business email, creates an opportunity in 'Contacted' with lead
    source 'AI Research', a follow-up task, and auto-enrolls through the
    existing new_opportunity trigger. Sequences' AI emails still wait in
    AI Email Drafts for approval.
    """
    lead = ResearchLead.objects.select_for_update().get(pk=lead.pk)
    if lead.status != "new":
        raise ValueError("Only new leads can be approved")

    product = service_type or lead.suggested_product
    owner = owner or user
    company = lead.matched_company
    if company is None:
        company = Company.objects.create(
            name=_unique_company_name(lead.venue_name),
            country=lead.country,
            website=lead.website,
            industry=SEGMENT_INDUSTRY.get(lead.segment, "Other"),
            music_zone_count=lead.estimated_zones or 1,
            notes=f"Found by AI lead research: {lead.signal}",
            billing_entity=('BMAsia (Thailand) Co., Ltd.' if lead.country.strip().lower() == 'thailand'
                            else 'BMAsia Limited'),
        )

    if lead.contact_email and not Contact.objects.filter(company=company, email__iexact=lead.contact_email).exists():
        Contact.objects.create(
            company=company,
            name=(lead.decision_maker_name or f"{lead.venue_name} team")[:100],
            title=lead.decision_maker_title[:100],
            email=lead.contact_email,
            is_primary=not Contact.objects.filter(company=company, is_primary=True).exists(),
        )

    price = 290 if product == "beatbreeze" else 400
    zones = lead.estimated_zones or 1
    sources = "\n".join(lead.source_urls)
    opportunity = Opportunity.objects.create(
        company=company,
        name=f"{lead.venue_name} - {'Beat Breeze' if product == 'beatbreeze' else 'Soundtrack'}",
        service_type=product,
        stage="Contacted",
        expected_value=price * zones,
        probability=10,
        owner=owner,
        lead_source="AI Research",
        notes=(
            f"Signal: {lead.signal}\n"
            f"Timing: {lead.opening_timeframe}\n"
            f"Why it fits: {lead.fit_reason}\n"
            f"Opening hook: {lead.personal_hook}\n"
            f"Decision maker: {lead.decision_maker_name} {lead.decision_maker_title}".rstrip()
            + f"\nSources:\n{sources}"
        ),
    )

    needs_contact = not lead.contact_email
    Task.objects.create(
        company=company,
        assigned_to=owner,
        created_by=user,
        title=(f"Find the decision maker at {company.name}" if needs_contact
               else f"Follow up with {company.name}"),
        description=(
            f"AI research lead: {lead.signal}\nHook: {lead.personal_hook}\n"
            + ("No published email was found, so no sequence was started. "
               "Add a contact, then enroll them in a prospect sequence." if needs_contact else "")
        ),
        priority="Medium",
        status="To Do",
        task_type="Follow-up",
        due_date=timezone.now() + timedelta(days=3),
        related_opportunity=opportunity,
    )

    lead.status = "approved"
    lead.matched_company = company
    lead.opportunity = opportunity
    lead.reviewed_by = user
    lead.reviewed_at = timezone.now()
    lead.save()

    enrolled = 0
    if not needs_contact:
        from crm_app.services.prospect_enrollment_service import ProspectEnrollmentService
        transaction.on_commit(lambda: ProspectEnrollmentService.auto_enroll_new_opportunity(opportunity))
        enrolled = 1
    return lead, enrolled


def reject_lead(lead, user, reason=""):
    if lead.status != "new":
        raise ValueError("Only new leads can be rejected")
    lead.status = "rejected"
    lead.rejection_reason = (reason or "")[:255]
    lead.reviewed_by = user
    lead.reviewed_at = timezone.now()
    lead.save()
    return lead
