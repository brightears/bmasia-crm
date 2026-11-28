"""Win-back agent: find customers who left, draft a come-back email with Claude,
send only after a person approves it, learn why they left, and turn that into a plan.

The loop:

1. ``scan()`` finds companies whose last recurring contract ended, was cancelled or
   was marked churned inside the window (default 183 days) and that have nothing
   live or in flight today. One ``WinBackCandidate`` per churned contract.
2. ``draft_email()`` asks Claude for a personalised email built from CRM facts
   (product, zones, tenure, support history). The draft waits as ``pending_review``.
3. ``approve_and_send()`` is the only path that sends. The API allows it only to a
   person signed in to the website (never an API token or agent account).
4. ``record_feedback()`` stores what the customer said (an email reply caught by the
   reply checker, or call notes) and has Claude classify why they left.
5. ``generate_insights()`` asks Claude to analyse every reason in the window and
   write a 5-step improvement plan, saved as a ``ChurnInsightReport``.

Claude only reads CRM facts listed in ``build_context()``: no notes, ticket
descriptions or email bodies of other conversations are sent to the API.
"""

import json
import logging
import re
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags

from crm_app.dates import business_today
from crm_app.services.renewal_candidates import exclude_one_offs

logger = logging.getLogger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:  # pragma: no cover - the package is in requirements.txt
    HAS_ANTHROPIC = False

DEFAULT_WINDOW_DAYS = 183
DEFAULT_MODEL = 'claude-opus-5-5'
FALLBACK_BETA = 'server-side-fallback-2026-07-01'

LIVE_STATUSES = ('Active', 'Sent')
CHURN_STATUSES = ('Expired', 'Cancelled')
REASON_KEYS = (
    'price', 'music', 'technical', 'service', 'competitor', 'free_alternative',
    'venue_closed', 'ownership_change', 'renovation', 'licensing', 'no_longer_needed',
    'other', 'unknown',
)


class WinBackError(Exception):
    """A step that cannot run (wrong status, AI unavailable, nothing to send)."""


# --------------------------------------------------------------------- helpers

def ai_model():
    return getattr(settings, 'WINBACK_AI_MODEL', '') or DEFAULT_MODEL


def default_offer():
    return getattr(settings, 'WINBACK_DEFAULT_OFFER', '') or (
        '2 months free when they sign a new 12-month plan'
    )


def product_of(contract):
    """'beatbreeze', 'soundtrack' or 'other' for a contract, falling back to the company."""
    service = (contract.service_type or '').lower()
    if service.startswith('beat_breeze'):
        return 'beatbreeze'
    if service.startswith('soundtrack'):
        return 'soundtrack'
    platforms = {p for p in contract.service_locations.values_list('platform', flat=True)}
    if platforms == {'beatbreeze'}:
        return 'beatbreeze'
    if platforms == {'soundtrack'}:
        return 'soundtrack'
    company_product = getattr(contract.company, 'contracted_product', '') or ''
    if company_product in ('beatbreeze', 'soundtrack'):
        return company_product
    return 'other'


def churn_date(contract):
    """The day the customer left, per the record that shows it."""
    if contract.lifecycle_type == 'churn' and contract.lifecycle_effective_date:
        return contract.lifecycle_effective_date, 'lifecycle_churn'
    if contract.status == 'Cancelled':
        return contract.end_date or contract.updated_at.date(), 'cancelled'
    return contract.end_date, 'expired'


def _has_live_or_pending_contract(company, today):
    from crm_app.models import Contract
    live = Contract.objects.filter(company=company, status__in=LIVE_STATUSES).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    )
    # A Draft that starts recently or later is a renewal or return in progress.
    in_flight = Contract.objects.filter(
        company=company, status='Draft', start_date__gte=today - timedelta(days=60),
    )
    return live.exists() or in_flight.exists()


def pick_contact(company, contract=None):
    """The person to write to: the contract's customer contact, else primary, else decision maker."""
    contacts = company.contacts.filter(is_active=True, unsubscribed=False, receives_notifications=True)
    contacts = contacts.exclude(email='')
    if contract is not None and contract.customer_contact_email:
        match = contacts.filter(email__iexact=contract.customer_contact_email).first()
        if match:
            return match
    return (contacts.filter(is_primary=True).first()
            or contacts.filter(contact_type='Decision Maker').first()
            or contacts.order_by('created_at').first())


def _zones_for(contract):
    count = contract.service_locations.count()
    if count:
        return count
    company = contract.company
    return company.contracted_zone_count or company.music_zone_count or 0


# ------------------------------------------------------------------------ scan

def find_churned(window_days=DEFAULT_WINDOW_DAYS, product='all', today=None):
    """Churned customers in the window: one row per company (its latest churned contract).

    A company counts when its latest recurring contract ended, was cancelled or was
    marked churned inside the window, and it has no Active/Sent contract running today
    and no recent Draft (a renewal or comeback already in progress).
    """
    from crm_app.models import Contract

    today = today or business_today()
    since = today - timedelta(days=window_days)

    churn_q = (
        Q(lifecycle_type='churn', lifecycle_effective_date__gte=since, lifecycle_effective_date__lte=today)
        | Q(status__in=CHURN_STATUSES, end_date__gte=since, end_date__lte=today)
        | Q(status='Cancelled', end_date__isnull=True, updated_at__date__gte=since)
    )
    # Churn records are classed as one-offs for renewals; keep them here.
    recurring = exclude_one_offs(Contract.objects.exclude(lifecycle_type='churn')) | Contract.objects.filter(
        lifecycle_type='churn')
    contracts = (recurring.filter(churn_q)
                 .select_related('company')
                 .order_by('company_id', '-end_date'))

    rows = {}
    for contract in contracts:
        when, signal = churn_date(contract)
        if when is None or when < since or when > today:
            continue
        current = rows.get(contract.company_id)
        if current and current['churned_on'] >= when:
            continue
        rows[contract.company_id] = {
            'company': contract.company,
            'contract': contract,
            'churned_on': when,
            'signal': signal,
        }

    results = []
    for row in rows.values():
        if _has_live_or_pending_contract(row['company'], today):
            continue
        row['product'] = product_of(row['contract'])
        if product != 'all' and row['product'] != product:
            continue
        results.append(row)
    results.sort(key=lambda r: r['churned_on'], reverse=True)
    return results


def scan(window_days=DEFAULT_WINDOW_DAYS, product='all', today=None):
    """Create a candidate for every churned customer not already on the list. Sends nothing."""
    from crm_app.models import WinBackCandidate

    created, existing = [], 0
    for row in find_churned(window_days=window_days, product=product, today=today):
        contract = row['contract']
        if WinBackCandidate.objects.filter(company=row['company'], churned_contract=contract).exists():
            existing += 1
            continue
        contact = pick_contact(row['company'], contract)
        candidate = WinBackCandidate.objects.create(
            company=row['company'],
            churned_contract=contract,
            contact=contact,
            product=row['product'],
            churned_on=row['churned_on'],
            churn_signal=row['signal'],
            zones=_zones_for(contract),
            annual_value=contract.value,
            currency=contract.currency or '',
            status='identified' if contact else 'needs_contact',
        )
        created.append(candidate)
    return {'created': created, 'already_listed': existing}


# --------------------------------------------------------------------- context

def build_context(candidate):
    """CRM facts Claude may use. Deliberately excludes notes, ticket text and email bodies."""
    from crm_app.models import Contract, Ticket, ZoneOfflineAlert

    company = candidate.company
    contract = candidate.churned_contract
    first = Contract.objects.filter(company=company).exclude(status='Draft').order_by('start_date').first()
    year_ago = timezone.now() - timedelta(days=365)
    tickets = Ticket.objects.filter(company=company, created_at__gte=year_ago)
    categories = Counter(tickets.values_list('category', flat=True))
    offline = ZoneOfflineAlert.objects.filter(zone__company=company, detected_at__gte=year_ago).count()
    contact = candidate.contact

    return {
        'company_name': company.name,
        'industry': company.get_industry_display() if company.industry else '',
        'country': company.country,
        'product': candidate.get_product_display(),
        'zones': candidate.zones,
        'locations': company.location_count,
        'customer_since': first.start_date.isoformat() if first else None,
        'left_on': candidate.churned_on.isoformat(),
        'how_it_ended': {
            'expired': 'contract ran out and was not renewed',
            'cancelled': 'contract was cancelled',
            'lifecycle_churn': 'recorded as churned',
        }.get(candidate.churn_signal, candidate.churn_signal),
        'last_contract_value': str(candidate.annual_value) if candidate.annual_value is not None else None,
        'currency': candidate.currency,
        'last_contract_type': contract.get_contract_type_display() if contract else '',
        'support_tickets_last_12_months': tickets.count(),
        'support_ticket_categories': dict(categories),
        'zone_offline_alerts_last_12_months': offline,
        'contact_name': contact.name if contact else '',
        'contact_title': contact.title if contact else '',
        'contact_language': contact.get_preferred_language_display() if contact else 'English',
        'sender_name': getattr(settings, 'WINBACK_SENDER_NAME', '') or 'Norbert',
        'sender_title': getattr(settings, 'WINBACK_SENDER_TITLE', '') or 'Director of Operations, BMAsia',
    }


# ----------------------------------------------------------------------- Claude

_DRAFT_SYSTEM = """You write win-back emails for BMAsia (est. 2002), a background music provider for hotels, restaurants, retail and QSR across Asia-Pacific. Two products:
- Beat Breeze: curated royalty-free music with every licence included (copyright and public performance), fully managed by BMAsia's music designers, offline capable, custom AI-produced brand tracks.
- Soundtrack Your Brand: 100M+ licensed mainstream tracks, self-service scheduling, iOS/Android/Windows; public performance licence is arranged locally by the venue.

The reader was a customer and left. Write as the named sender, personally, to the named contact.

Goals, in order:
1. Ask, genuinely and briefly, why they left. Make it effortless to answer (a one-line reply is fine).
2. Show you remember them: use the concrete facts given (product, zones, how long they were with us, their industry). Never invent facts, names, results or quotes.
3. Make the come-back offer exactly as given. Do not change its terms or add other discounts.
4. One clear, low-pressure next step (reply, or a 15-minute call).

Style: warm, direct, no hype, no guilt. 90-160 words. Short paragraphs. Plain business English unless the contact's language is Thai, in which case write in polite Thai. If support history shows problems, acknowledge them honestly without admitting legal fault. Simple HTML only: <p>, <br>, <strong>, <ul>/<li>. Start with the greeting, end with the sender's name and title. No unsubscribe line (the system adds it)."""

_DRAFT_SCHEMA = {
    'type': 'object',
    'properties': {
        'subject': {'type': 'string', 'description': 'Under 60 characters, personal, no clickbait'},
        'body_html': {'type': 'string'},
        'personalisation_notes': {
            'type': 'string',
            'description': 'One or two sentences for the reviewer: which facts you used and why',
        },
    },
    'required': ['subject', 'body_html', 'personalisation_notes'],
    'additionalProperties': False,
}

_FEEDBACK_SYSTEM = """You classify why a former BMAsia background-music customer left, from what they told us. Use only what the text says; if it gives no reason, use "unknown". Keep churn_reason_detail to one factual sentence in English."""

_FEEDBACK_SCHEMA = {
    'type': 'object',
    'properties': {
        'churn_reason': {'type': 'string', 'enum': list(REASON_KEYS)},
        'churn_reason_detail': {'type': 'string'},
        'sentiment': {'type': 'string', 'enum': ['positive', 'neutral', 'negative']},
        'win_back_likelihood': {'type': 'string', 'enum': ['high', 'medium', 'low', 'none']},
        'suggested_next_step': {'type': 'string', 'description': 'One concrete action for the sales team'},
    },
    'required': ['churn_reason', 'churn_reason_detail', 'sentiment', 'win_back_likelihood', 'suggested_next_step'],
    'additionalProperties': False,
}

_INSIGHTS_SYSTEM = """You are a customer-retention analyst for BMAsia, a B2B background music company (Beat Breeze and Soundtrack Your Brand) serving hotels, restaurants, retail and QSR in Asia-Pacific. You get aggregated churn data and the customers' own reasons. Be specific and evidence-led: cite counts, name patterns, separate what the data shows from what you infer, and say plainly when the sample is too small to conclude. Write for the Director of Operations: short, structured, no filler."""

_INSIGHTS_SCHEMA = {
    'type': 'object',
    'properties': {
        'summary': {'type': 'string', 'description': '3-5 sentences: who left, the main reasons, what stands out'},
        'plan_markdown': {
            'type': 'string',
            'description': (
                'Markdown. Sections: "## Why customers left" (ranked reasons with counts), '
                '"## 5-step improvement plan" (exactly 5 numbered steps; each with owner, first action this '
                'week, and the metric that shows it worked), "## Win-back priorities" (which accounts to '
                'chase first and why), "## Data gaps" (what the CRM should start recording).'
            ),
        },
    },
    'required': ['summary', 'plan_markdown'],
    'additionalProperties': False,
}


def _client():
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
    if not (HAS_ANTHROPIC and api_key):
        raise WinBackError('Claude is not configured (ANTHROPIC_API_KEY is missing).')
    return anthropic.Anthropic(api_key=api_key)


def _ask_claude(system, prompt, schema, effort='medium', max_tokens=16000):
    """One structured call. Returns (parsed dict, model that answered)."""
    client = _client()
    response = client.beta.messages.create(
        model=ai_model(),
        max_tokens=max_tokens,
        system=system,
        messages=[{'role': 'user', 'content': prompt}],
        output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': schema}},
        betas=[FALLBACK_BETA],
        fallbacks='default',
    )
    if response.stop_reason == 'refusal':
        raise WinBackError('Claude declined this request.')
    if response.stop_reason == 'max_tokens':
        raise WinBackError('Claude ran out of room before finishing; try again.')
    text = ''.join(block.text for block in response.content if block.type == 'text').strip()
    try:
        return json.loads(text), getattr(response, 'model', ai_model())
    except json.JSONDecodeError as exc:
        raise WinBackError('Claude returned an unreadable answer; try again.') from exc


_ALLOWED_TAGS = re.compile(r'</?(?!(?:p|br|strong|b|em|i|ul|ol|li)\b)[a-zA-Z][^>]*>')


def _clean_html(html):
    html = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', '', html or '')
    html = re.sub(r'(?i)\son\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', html)
    return _ALLOWED_TAGS.sub('', html).strip()


# ------------------------------------------------------------------------ steps

def draft_email(candidate, offer=None, instructions=''):
    """Ask Claude for a personalised draft. The candidate waits for review; nothing is sent."""
    if candidate.status not in ('identified', 'pending_review'):
        raise WinBackError(f'Cannot draft for a candidate that is {candidate.get_status_display().lower()}.')
    if candidate.contact is None:
        raise WinBackError('Add a contact who can receive email before drafting.')

    offer = (offer or '').strip() or default_offer()
    context = build_context(candidate)
    prompt = (
        'Customer facts from our CRM (JSON):\n'
        f'{json.dumps(context, ensure_ascii=False, indent=2)}\n\n'
        f'Come-back offer to make, exactly: {offer}\n'
    )
    if instructions:
        prompt += f'\nExtra instructions from the reviewer: {instructions.strip()[:1000]}\n'
    data, model = _ask_claude(_DRAFT_SYSTEM, prompt, _DRAFT_SCHEMA, effort='medium')

    candidate.offer = offer[:500]
    candidate.draft_subject = (data.get('subject') or '').strip()[:500]
    candidate.draft_body_html = _clean_html(data.get('body_html'))
    candidate.personalisation_notes = (data.get('personalisation_notes') or '').strip()
    candidate.ai_model = model[:100]
    candidate.drafted_at = timezone.now()
    candidate.status = 'pending_review'
    candidate.save()
    return candidate


def approve_and_send(candidate, user, subject=None, body_html=None):
    """Send the (optionally edited) draft. The only function in this module that sends email."""
    from crm_app.models import EmailLog, WinBackCandidate
    from crm_app.services.email_service import EmailService

    with transaction.atomic():
        locked = WinBackCandidate.objects.select_for_update().get(pk=candidate.pk)
        if locked.status != 'pending_review':
            raise WinBackError('Only a draft waiting for review can be sent.')
        contact = locked.contact
        if contact is None or contact.unsubscribed or not contact.receives_notifications or not contact.email:
            raise WinBackError('This contact cannot receive email (missing, unsubscribed or switched off).')
        final_subject = (subject if subject is not None else locked.draft_subject).strip()[:500]
        final_body = _clean_html(body_html if body_html is not None else locked.draft_body_html)
        if not final_subject or not final_body:
            raise WinBackError('Subject and body are both needed.')
        # Claim the send so a double click cannot send twice.
        locked.status = 'sent'
        locked.final_subject = final_subject
        locked.final_body_html = final_body
        locked.reviewer = user
        locked.reviewed_at = timezone.now()
        locked.send_error = ''
        locked.save()

    started = timezone.now()
    success, message = EmailService().send_email(
        to_email=contact.email,
        subject=final_subject,
        body_html=final_body,
        body_text=strip_tags(final_body),
        company=locked.company,
        contact=contact,
        email_type='winback',
        reply_to=getattr(settings, 'WINBACK_REPLY_TO', None) or None,
    )
    if not success:
        locked.status = 'pending_review'
        locked.send_error = (message or 'Send failed')[:2000]
        locked.save(update_fields=['status', 'send_error', 'updated_at'])
        raise WinBackError(f'Email was not sent: {message}')

    locked.sent_at = timezone.now()
    locked.email_log = (EmailLog.objects
                        .filter(company=locked.company, contact=contact, email_type='winback',
                                created_at__gte=started - timedelta(seconds=5))
                        .order_by('-created_at').first())
    locked.save(update_fields=['sent_at', 'email_log', 'updated_at'])
    if contact.last_contacted is None or contact.last_contacted < locked.sent_at:
        contact.last_contacted = locked.sent_at
        contact.save(update_fields=['last_contacted', 'updated_at'])
    return locked


def reject(candidate, user, note=''):
    if candidate.status not in ('identified', 'needs_contact', 'pending_review'):
        raise WinBackError('Only a candidate that has not been emailed can be skipped.')
    candidate.status = 'skipped'
    candidate.reviewer = user
    candidate.reviewed_at = timezone.now()
    candidate.closed_at = timezone.now()
    if note:
        candidate.outcome_notes = note.strip()[:2000]
    candidate.save()
    return candidate


def classify_feedback(text):
    data, _model = _ask_claude(
        _FEEDBACK_SYSTEM,
        f'What the former customer said:\n"""\n{text.strip()[:6000]}\n"""',
        _FEEDBACK_SCHEMA,
        effort='low',
        max_tokens=4000,
    )
    reason = data.get('churn_reason')
    if reason not in REASON_KEYS:
        data['churn_reason'] = 'unknown'
    return data


def record_feedback(candidate, text, source='manual', classify=True, message_id=''):
    """Store what the customer said and, when Claude is available, why they left."""
    text = (text or '').strip()
    if not text:
        raise WinBackError('Feedback text is empty.')
    candidate.feedback_text = text[:10000]
    candidate.feedback_source = source[:20]
    candidate.feedback_received_at = timezone.now()
    if message_id and message_id not in candidate.reply_message_id:
        # Every reply Message-ID seen, space separated, so the reply checker never records one twice.
        candidate.reply_message_id = f'{candidate.reply_message_id} {message_id}'.strip()[-2000:]
    if candidate.status in ('sent', 'identified', 'pending_review', 'needs_contact'):
        candidate.status = 'replied'
    if classify:
        try:
            data = classify_feedback(text)
        except WinBackError as exc:
            logger.warning('Win-back feedback not classified for %s: %s', candidate.pk, exc)
        else:
            candidate.churn_reason = data['churn_reason']
            candidate.churn_reason_detail = (data.get('churn_reason_detail') or '')[:500]
            candidate.sentiment = (data.get('sentiment') or '')[:20]
            candidate.win_back_likelihood = (data.get('win_back_likelihood') or '')[:20]
            candidate.suggested_next_step = (data.get('suggested_next_step') or '')[:500]
    candidate.save()
    return candidate


def set_outcome(candidate, outcome, note=''):
    if outcome not in ('won_back', 'lost'):
        raise WinBackError("Outcome must be 'won_back' or 'lost'.")
    candidate.status = outcome
    candidate.closed_at = timezone.now()
    if note:
        candidate.outcome_notes = note.strip()[:2000]
    candidate.save()
    return candidate


def match_reply(in_reply_to, references, from_email):
    """The candidate an inbound email answers, by Message-ID headers, else by sender."""
    from crm_app.models import WinBackCandidate

    ids = [i.strip() for i in [in_reply_to or ''] + (references or '').split() if i.strip()]
    base = WinBackCandidate.objects.filter(status__in=('sent', 'replied')).select_related('email_log')
    if ids:
        found = base.filter(email_log__message_id__in=ids).order_by('-sent_at').first()
        if found:
            return found
    if from_email:
        return base.filter(
            contact__email__iexact=from_email, sent_at__gte=timezone.now() - timedelta(days=45),
        ).order_by('-sent_at').first()
    return None


# ---------------------------------------------------------------------- insights

def generate_insights(window_days=DEFAULT_WINDOW_DAYS, product='', user=None, today=None):
    """Analyse every candidate in the window and save Claude's 5-step improvement plan."""
    from crm_app.models import ChurnInsightReport, WinBackCandidate

    today = today or business_today()
    since = today - timedelta(days=window_days)
    candidates = WinBackCandidate.objects.filter(churned_on__gte=since).select_related('company')
    if product:
        candidates = candidates.filter(product=product)
    candidates = list(candidates)
    if not candidates:
        raise WinBackError('No churned customers in this window yet. Run a scan first.')

    reasons = Counter(c.churn_reason for c in candidates)
    status_counts = Counter(c.status for c in candidates)
    by_product = Counter(c.product for c in candidates)
    by_industry = Counter((c.company.industry or 'unknown') for c in candidates)
    lost_value = {}
    for c in candidates:
        if c.annual_value is not None:
            lost_value[c.currency or '?'] = lost_value.get(c.currency or '?', Decimal('0')) + c.annual_value
    with_feedback = [c for c in candidates if c.feedback_text]
    sent = sum(1 for c in candidates if c.sent_at)
    stats = {
        'window_days': window_days,
        'product_filter': product or 'all',
        'churned_customers': len(candidates),
        'zones_lost': sum(c.zones for c in candidates),
        'contract_value_lost_by_currency': {k: str(v) for k, v in lost_value.items()},
        'by_product': dict(by_product),
        'by_industry': dict(by_industry),
        'by_status': dict(status_counts),
        'emails_sent': sent,
        'replies': len(with_feedback),
        'won_back': status_counts.get('won_back', 0),
    }
    feedback = [
        {
            'company': c.company.name,
            'industry': c.company.industry or '',
            'product': c.product,
            'zones': c.zones,
            'reason': c.churn_reason,
            'detail': c.churn_reason_detail,
            'likelihood': c.win_back_likelihood,
            'said': c.feedback_text[:800],
        }
        for c in with_feedback
    ]
    prompt = (
        f'Churn statistics (JSON):\n{json.dumps(stats, indent=2)}\n\n'
        f'Reason counts (unknown = no answer yet):\n{json.dumps(dict(reasons), indent=2)}\n\n'
        f'What customers told us ({len(feedback)} answers, JSON):\n'
        f'{json.dumps(feedback, ensure_ascii=False, indent=2)}\n'
    )
    data, model = _ask_claude(_INSIGHTS_SYSTEM, prompt, _INSIGHTS_SCHEMA, effort='high', max_tokens=32000)

    return ChurnInsightReport.objects.create(
        window_days=window_days,
        product=product or '',
        candidate_count=len(candidates),
        feedback_count=len(with_feedback),
        reason_counts=dict(reasons),
        stats=stats,
        summary=(data.get('summary') or '').strip(),
        plan_markdown=(data.get('plan_markdown') or '').strip(),
        ai_model=model[:100],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )
