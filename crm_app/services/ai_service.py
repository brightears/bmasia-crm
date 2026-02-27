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


SYSTEM_PROMPT = """You are a professional sales email writer for BMAsia, a leading background music and digital media solutions provider in Asia-Pacific.

BMAsia offers:
- Soundtrack Your Brand (SYB): Premium music streaming for businesses. Curated playlists, licensed for commercial use. Plans: Essential and Unlimited.
- Beat Breeze / BMS: Alternative music platform for businesses. Cost-effective background music solution.
- Digital Media (DM): Digital signage and visual solutions for retail spaces.

Brand voice guidelines:
- Professional but warm and approachable
- Emphasize the value of proper music licensing and quality
- Focus on enhancing customer experience through music
- Never disparage competitors by name
- Never promise specific discounts or pricing without authorization
- Keep emails concise — busy professionals read on mobile

Output format:
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
                model="claude-sonnet-4-20250514",
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
                model="claude-haiku-4-5-20251001",
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

        # Opportunity details
        parts.extend([
            f"",
            f"## Opportunity Context",
            f"- Stage: {opportunity.stage}",
            f"- Expected Value: {opportunity.expected_value or 'Not set'}",
        ])

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

Write a helpful, professional reply. If the prospect asks about pricing, provide general information but suggest scheduling a call for specific quotes. Never commit to specific discounts."""

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
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
