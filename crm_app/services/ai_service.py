"""
AI Email Generation Service for BMAsia CRM
Uses the Anthropic Claude API to generate personalized sales follow-up emails
based on CRM context (opportunity, contact, sequence step).
"""

import logging
import re
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Try to import anthropic — graceful fallback if not installed
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("anthropic package not installed — AI email generation disabled")


# Model configuration — tiered by task complexity
# Sonnet: email body, replies (quality content that represents the brand)
# Haiku: subject lines only (short, simple task)
MODEL_CONTENT = "claude-sonnet-4-6"  # For email body, replies
MODEL_SIMPLE = "claude-haiku-4-5-20251001"  # For subject lines

SYSTEM_PROMPT = """You are a professional sales email writer for BMAsia (est. 2002), a leading commercial music solutions provider serving 2,100+ zones across Asia-Pacific.

## COMPANY OVERVIEW
BMAsia has 23+ years of expertise in commercial music solutions. Trusted by Accor, Hilton, Hyatt, Centara, Minor Hotels, TUI, The North Face, DBS, Tim Hortons, and many more. We serve hotels, restaurants, bars, retail, offices, spas, gyms, QSR, malls, and clinics across Asia-Pacific, Middle East, Africa, Europe, and US.

## PRODUCTS

### Soundtrack Your Brand (SYB) — Premium Tier
- 100M+ tracks including major labels (Universal, Warner, Sony) — "every song in the world, legally in your venue"
- Cloud-based: iOS, Android, Windows apps. Self-managed OR BMAsia-managed
- Key features: Spotify playlist import, AI playlist generator, drag-and-drop scheduling, explicit filter, text-to-speech messaging, multi-location dashboard, open API, offline playback (Unlimited plan), Hi-Fi audio (320 kbps)
- Licensing: Copyright + streaming licenses INCLUDED. Public performance license NOT included (client obtains from local CMO — e.g., MPC Thailand, COMPASS+MRSS Singapore, OneMusic Australia)
- Hardware: Soundtrack Player ($200 USD, free with 2+ year contracts)
- Best for: venues wanting popular/mainstream music, self-service control, Spotify integration, iOS support, API integrations

### Beat Breeze — Essential / Value Tier
- 30,000+ royalty-free tracks curated for commercial use (chill-out, lounge, house, jazz, acoustic, world music)
- ALL licenses included — copyright AND public performance. Zero additional fees or paperwork
- Fully managed by BMAsia's music design team. Offline-capable
- Key features: custom AI music production (exclusive brand tracks), unlimited redesigns, scheduling, messaging, hardware diagnostics
- Platform: Android, Windows (own player launching soon)
- Best for: hassle-free/budget-conscious clients, venues where ambient music fits (spa, lobby, office), markets with complex licensing, "set it and forget it" service
- Does NOT include mainstream pop/major label artists

### Mix & Match
Clients can use SYB for some zones and Beat Breeze for others. Common: SYB for bars/restaurants (popular music) + Beat Breeze for lobbies/spas (ambient, licensing simplicity). Each zone priced at its product rate.

## PRICING (what you CAN share)
- SYB Essential: $380/zone/year (USD) — includes full managed service
- Beat Breeze: $260–$290/zone/year (USD) — includes ALL licenses + managed service
- Thai clients: quoted in THB
- Pricing is per zone (one independent music stream/area). A venue may have multiple zones
- Volume pricing available for larger deployments (escalate to team for specifics)
- 2+ year contracts: hardware included free
- 6-month contracts available if 12 months is too long
- No setup or installation fees

## WHAT'S INCLUDED AT NO EXTRA COST
Music design & consultation, unlimited redesigns, monthly content updates, seasonal playlists, on-hold messaging production, 24/7 technical support, Beat Breeze custom AI music production

## FREE TRIAL
- SYB: 1-month free trial, 1 zone, full service, no commitment
- Beat Breeze: free trial available, no commitment
- Always offer early — it's a no-risk entry point

## KEY SELLING POINTS
- 23+ years of expertise, 2,100+ zones, 50,000+ hours of music created annually
- Both options under one roof — premium commercial OR cost-effective royalty-free
- Expert music design team (not just software — we design your sonic identity)
- 24/7 support via WhatsApp, email, phone. Response within 1-2 hours
- API innovation: weather-responsive playlists, volume sensors, prayer time automation, lighting sync, custom integrations
- No hidden fees — everything included in annual subscription

## COMMON OBJECTIONS — USE THESE ANGLES
- "We use Spotify/YouTube" → Not legal for commercial use. Fines can be thousands. We can import their Spotify playlists into SYB legally
- "Too expensive" → Beat Breeze includes ALL licenses (public performance license alone can exceed the subscription cost). Total cost of ownership is lower
- "We play the radio" → Zero control, competitor ads, DJ chatter. Right music increases dwell time 20%+
- "30,000 tracks isn't a lot" → Curated for quality, not quantity. Most venues use 200-500 tracks in rotation. Plus custom AI music exclusive to their brand
- "12 months too long" → 6-month option available. Or start with free trial
- "Can we get a discount?" → Standard pricing includes everything. Volume pricing for multi-zone. 2-year = free hardware. Connect with team for tailored package

## PRICING RULES (CRITICAL)
- ✅ CAN: share standard prices above, calculate totals, mention volume pricing exists, mention free trial, mention 2-year hardware inclusion
- ❌ CANNOT: offer specific discounts, quote below standard rates, share internal margins, promise enterprise pricing, compare to competitor pricing with numbers
- When asked for discounts: acknowledge, highlight included value, offer to connect with team

## BRAND VOICE
- Professional but warm — not corporate-stiff, not overly casual
- Consultative — ask about needs before recommending
- Honest — if Beat Breeze isn't right, say so. If SYB is overkill, say so
- Confident — 23+ years of expertise
- Concise — busy professionals read on mobile

## OUTPUT FORMAT
- Return ONLY the email body HTML (no subject line, no ```html markers)
- Use simple HTML: <p>, <br>, <strong>, <ul>/<li> tags only
- Do NOT include email headers, signatures, or unsubscribe links (these are added by the system)
- Start directly with the greeting (e.g., "Dear [Name],")
- End with a professional sign-off like "Best regards," or "Warm regards,"
"""


class AIEmailService:
    """Service for generating AI-powered sales emails using Claude API"""

    def __init__(self):
        self.client = None
        if HAS_ANTHROPIC:
            api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
            else:
                logger.warning("ANTHROPIC_API_KEY not configured")

    @property
    def is_available(self):
        return self.client is not None

    def generate_prospect_email(self, opportunity, contact, step, context=None):
        """
        Generate a personalized sales email using Claude API.

        Args:
            opportunity: Opportunity model instance
            contact: Contact model instance
            step: ProspectSequenceStep model instance
            context: Optional dict with additional context

        Returns:
            dict with 'subject' and 'body_html' keys, or None if generation fails
        """
        if not self.is_available:
            logger.error("AI service not available — missing anthropic package or API key")
            return None

        try:
            # Build context for the AI
            prompt = self._build_prompt(opportunity, contact, step, context or {})

            response = self.client.messages.create(
                model=MODEL_CONTENT,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            body_html = response.content[0].text.strip()

            # Clean up any markdown code blocks if accidentally included
            body_html = re.sub(r'^```html\s*', '', body_html)
            body_html = re.sub(r'\s*```$', '', body_html)

            # Generate subject line separately
            subject = self._generate_subject(opportunity, contact, step, context or {})

            return {
                'subject': subject,
                'body_html': body_html,
            }

        except Exception as e:
            logger.error(f"AI email generation failed for opportunity {opportunity.id}: {e}")
            return None

    def _generate_subject(self, opportunity, contact, step, context):
        """Generate email subject line using Claude"""
        try:
            company_name = opportunity.company.name if opportunity.company else "your company"
            step_num = step.step_number
            total_steps = step.sequence.steps.count()

            prompt = f"""Generate a short, compelling email subject line (max 60 characters) for this sales email:

Company: {company_name}
Contact: {contact.first_name} {contact.last_name}
Industry: {opportunity.company.industry if opportunity.company and opportunity.company.industry else 'Business'}
Step {step_num} of {total_steps} in the sequence.
Sequence: {step.sequence.name}
{f'Step instructions: {step.ai_prompt_instructions}' if step.ai_prompt_instructions else ''}

Return ONLY the subject line text, nothing else. Do not include "Subject:" prefix."""

            response = self.client.messages.create(
                model=MODEL_SIMPLE,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.content[0].text.strip().strip('"')

        except Exception as e:
            logger.error(f"Subject generation failed: {e}")
            return f"Enhancing your business experience — {opportunity.company.name if opportunity.company else 'Follow-up'}"

    def _build_prompt(self, opportunity, contact, step, context):
        """Build the detailed prompt for email generation"""
        company = opportunity.company
        step_num = step.step_number
        total_steps = step.sequence.steps.count()

        # Basic info
        parts = [
            f"Write a sales follow-up email for the following prospect:",
            f"",
            f"## Prospect Information",
            f"- Contact Name: {contact.first_name} {contact.last_name}",
            f"- Title: {contact.title or 'N/A'}",
            f"- Company: {company.name if company else 'N/A'}",
        ]

        if company:
            if company.industry:
                parts.append(f"- Industry: {company.industry}")
            if company.country and company.country != 'Other':
                parts.append(f"- Country: {company.country}")
            if hasattr(company, 'billing_entity') and company.billing_entity:
                parts.append(f"- Billing Entity: {company.billing_entity}")

        # Opportunity details
        parts.extend([
            f"",
            f"## Opportunity Context",
            f"- Stage: {opportunity.stage}",
            f"- Expected Value: {opportunity.expected_value or 'Not set'}",
        ])

        if hasattr(opportunity, 'service') and opportunity.service:
            parts.append(f"- Service/Product Interest: {opportunity.service}")
        if opportunity.notes:
            parts.append(f"- Notes: {opportunity.notes[:500]}")
        if opportunity.pain_points:
            parts.append(f"- Pain Points: {opportunity.pain_points[:500]}")
        if opportunity.decision_criteria:
            parts.append(f"- Decision Criteria: {opportunity.decision_criteria[:500]}")

        # Sequence context
        parts.extend([
            f"",
            f"## Sequence Context",
            f"- This is email step {step_num} of {total_steps} in the '{step.sequence.name}' sequence.",
        ])

        if step_num == 1:
            parts.append("- This is the FIRST contact. Be warm and introductory. Establish relevance.")
        elif step_num == total_steps:
            parts.append("- This is the FINAL email (break-up email). Use loss aversion — mention this is the last follow-up. Keep it short and direct. Research shows break-up emails get the highest reply rates.")
        elif step_num == 2:
            parts.append("- This is a follow-up. The prospect didn't reply to our introduction. Include a specific case study or value proposition.")
        else:
            parts.append(f"- This is follow-up #{step_num}. Try a different angle from previous emails.")

        # AI-specific instructions from the step
        if step.ai_prompt_instructions:
            parts.extend([
                f"",
                f"## Additional Instructions",
                step.ai_prompt_instructions,
            ])

        # Email history
        if context.get('email_history'):
            parts.extend([
                f"",
                f"## Previous Emails Sent (for context — do NOT repeat these)",
            ])
            for eh in context['email_history'][:5]:
                parts.append(f"- Subject: {eh.get('subject', 'N/A')} | Sent: {eh.get('sent_date', 'N/A')}")

        # Language preference
        preferred_lang = getattr(contact, 'preferred_language', None)
        if preferred_lang and preferred_lang.lower() in ('th', 'thai'):
            parts.extend([
                f"",
                f"## Language",
                f"Write this email in Thai. The contact prefers Thai communication.",
            ])

        return "\n".join(parts)

    def generate_reply_email(self, opportunity, contact, original_email, reply_content, context=None):
        """
        Generate an AI response to a prospect's reply (Phase 5 — future use).

        Returns:
            dict with 'subject' and 'body_html', or None
        """
        if not self.is_available:
            return None

        try:
            company = opportunity.company
            prompt = f"""Draft a professional reply to this prospect's email:

## Original Email We Sent:
Subject: {original_email.get('subject', 'N/A')}
Body: {original_email.get('body', 'N/A')[:1000]}

## Prospect's Reply:
{reply_content[:2000]}

## Context:
- Company: {company.name if company else 'N/A'}
- Contact: {contact.first_name} {contact.last_name}
- Opportunity Stage: {opportunity.stage}
- Notes: {opportunity.notes[:500] if opportunity.notes else 'None'}

Write a helpful, professional reply using your product knowledge. You may share standard pricing (SYB $380/zone/year, Beat Breeze $260-290/zone/year) and explain what's included. If asked for discounts, highlight included value and offer to connect with the team for tailored packages. Never commit to specific discounts or rates below standard."""

            response = self.client.messages.create(
                model=MODEL_CONTENT,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            body_html = response.content[0].text.strip()
            body_html = re.sub(r'^```html\s*', '', body_html)
            body_html = re.sub(r'\s*```$', '', body_html)

            return {
                'subject': f"Re: {original_email.get('subject', 'Follow-up')}",
                'body_html': body_html,
            }

        except Exception as e:
            logger.error(f"Reply generation failed: {e}")
            return None
