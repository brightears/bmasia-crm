"""
Data migration: Create default prospect sequences.

1. "New Lead Follow-up" — 5 steps over 12 days for new opportunities
2. "Stale Deal Re-engagement" — 3 steps over 7 days for stale deals
"""

import uuid
from django.db import migrations


def create_default_sequences(apps, schema_editor):
    ProspectSequence = apps.get_model('crm_app', 'ProspectSequence')
    ProspectSequenceStep = apps.get_model('crm_app', 'ProspectSequenceStep')

    # ── Sequence 1: New Lead Follow-up ──────────────────────────────
    seq1 = ProspectSequence.objects.create(
        id=uuid.uuid4(),
        name='New Lead Follow-up',
        description=(
            'Automated 5-step outreach for new prospects. '
            'Sends introduction, case study, call task, objection handler, and break-up email over 12 days. '
            'Auto-stops when the prospect replies.'
        ),
        trigger_type='new_opportunity',
        target_stages=['Contacted'],
        is_active=True,
        billing_entity='',
        max_enrollments_per_company=1,
        stale_days_threshold=14,
    )

    # Step 1: Day 0 — AI introduction email
    ProspectSequenceStep.objects.create(
        id=uuid.uuid4(),
        sequence=seq1,
        step_number=1,
        delay_days=0,
        action_type='ai_email',
        ai_prompt_instructions=(
            'Write a warm introduction email. Mention BMAsia\'s background music solutions. '
            'Reference the prospect\'s industry if known. Keep it under 150 words. '
            'End with a soft call-to-action like "Would you be open to a brief call this week?"'
        ),
        email_subject_template='',
        email_body_template='',
        task_title_template='',
        task_type='',
        stage_to_set='',
    )

    # Step 2: Day 3 — AI case study / social proof
    ProspectSequenceStep.objects.create(
        id=uuid.uuid4(),
        sequence=seq1,
        step_number=2,
        delay_days=3,
        action_type='ai_email',
        ai_prompt_instructions=(
            'Share a brief case study or social proof about how BMAsia helped similar businesses. '
            'Focus on tangible benefits: better customer experience, proper licensing, hassle-free management. '
            'Keep it under 120 words. End with "Would this be relevant for {{company_name}}?"'
        ),
        email_subject_template='',
        email_body_template='',
        task_title_template='',
        task_type='',
        stage_to_set='',
    )

    # Step 3: Day 3 — Task: Call the prospect
    ProspectSequenceStep.objects.create(
        id=uuid.uuid4(),
        sequence=seq1,
        step_number=3,
        delay_days=3,
        action_type='task',
        task_title_template='Call {{contact_name}} at {{company_name}} — follow up on emails',
        task_type='Call',
        ai_prompt_instructions='',
        email_subject_template='',
        email_body_template='',
        stage_to_set='',
    )

    # Step 4: Day 6 — AI email addressing common objections
    ProspectSequenceStep.objects.create(
        id=uuid.uuid4(),
        sequence=seq1,
        step_number=4,
        delay_days=6,
        action_type='ai_email',
        ai_prompt_instructions=(
            'Address common objections: "We already have music" (licensing compliance), '
            '"It\'s too expensive" (cost of non-compliance, value of curated playlists), '
            '"We\'re not interested" (new angle — focus on customer experience and brand identity). '
            'Pick the most relevant angle. Keep it under 100 words.'
        ),
        email_subject_template='',
        email_body_template='',
        task_title_template='',
        task_type='',
        stage_to_set='',
    )

    # Step 5: Day 12 — AI break-up email (highest reply rate due to loss aversion)
    ProspectSequenceStep.objects.create(
        id=uuid.uuid4(),
        sequence=seq1,
        step_number=5,
        delay_days=12,
        action_type='ai_email',
        ai_prompt_instructions=(
            'This is the FINAL follow-up (break-up email). Research shows these get the highest reply rates. '
            'Be direct and short (under 80 words). Mention this is your last email. '
            'Use loss aversion: "I\'ll close your file" or "I won\'t reach out again." '
            'Leave the door open: "If timing changes in the future, feel free to reach out."'
        ),
        email_subject_template='',
        email_body_template='',
        task_title_template='',
        task_type='',
        stage_to_set='',
    )

    # ── Sequence 2: Stale Deal Re-engagement ────────────────────────
    seq2 = ProspectSequence.objects.create(
        id=uuid.uuid4(),
        name='Stale Deal Re-engagement',
        description=(
            'Re-engage opportunities that have gone quiet for 14+ days. '
            '3-step sequence over 7 days with check-in, new angle, and break-up email.'
        ),
        trigger_type='stale_deal',
        target_stages=['Contacted', 'Quotation Sent'],
        is_active=True,
        billing_entity='',
        max_enrollments_per_company=1,
        stale_days_threshold=14,
    )

    # Step 1: Day 0 — AI check-in email
    ProspectSequenceStep.objects.create(
        id=uuid.uuid4(),
        sequence=seq2,
        step_number=1,
        delay_days=0,
        action_type='ai_email',
        ai_prompt_instructions=(
            'Write a brief check-in email. The prospect went quiet after initial contact. '
            'Be empathetic ("I understand things get busy"). '
            'Ask a simple yes/no question to lower the barrier to reply. '
            'Keep it under 60 words.'
        ),
        email_subject_template='',
        email_body_template='',
        task_title_template='',
        task_type='',
        stage_to_set='',
    )

    # Step 2: Day 3 — AI new angle / updated offer
    ProspectSequenceStep.objects.create(
        id=uuid.uuid4(),
        sequence=seq2,
        step_number=2,
        delay_days=3,
        action_type='ai_email',
        ai_prompt_instructions=(
            'Try a different angle from the original outreach. '
            'Mention a new feature, seasonal promotion, or industry trend. '
            'Keep it fresh and relevant. Under 100 words.'
        ),
        email_subject_template='',
        email_body_template='',
        task_title_template='',
        task_type='',
        stage_to_set='',
    )

    # Step 3: Day 7 — AI break-up + create review task
    ProspectSequenceStep.objects.create(
        id=uuid.uuid4(),
        sequence=seq2,
        step_number=3,
        delay_days=7,
        action_type='ai_email',
        ai_prompt_instructions=(
            'Final re-engagement attempt. Short break-up email (under 50 words). '
            'Let them know you won\'t follow up again unless they reach out. '
            'Professional and respectful. Leave the door open.'
        ),
        email_subject_template='',
        email_body_template='',
        task_title_template='',
        task_type='',
        stage_to_set='',
    )


def remove_default_sequences(apps, schema_editor):
    ProspectSequence = apps.get_model('crm_app', 'ProspectSequence')
    ProspectSequence.objects.filter(
        name__in=['New Lead Follow-up', 'Stale Deal Re-engagement']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0079_sales_automation'),
    ]

    operations = [
        migrations.RunPython(create_default_sequences, remove_default_sequences),
    ]
