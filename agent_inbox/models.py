"""Activity log and change-proposal models.

Both tables are additive and are written only through ``agent_inbox.services``
(REST in ``agent_inbox.api``, MCP tools in ``crm_app.mcp``). Free text is stored
as plain text and never rendered as HTML.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

# ------------------------------------------------------------------ size caps
# One place for every text limit; the services validate against these before
# anything is stored, and the column sizes follow them.
SUMMARY_MAX = 500
BODY_MAX = 20_000
SOURCE_REF_MAX = 500  # an RFC 822 Message-ID can be long; the capture app keeps up to 500
SOURCE_URL_MAX = 500
KEY_MAX = 200
REASON_MAX = 500
PARTICIPANTS_MAX = 50
PARTICIPANT_NAME_MAX = 200
PARTICIPANT_ADDRESS_MAX = 320
EVIDENCE_QUOTE_MAX = 2_000
RATIONALE_MAX = 1_000
DECISION_NOTE_MAX = 1_000
PATCH_VALUE_MAX = 5_000
MODEL_NAME_MAX = 100
BATCH_KEY_MAX = 100
APPLY_ERROR_MAX = 500

ACTIVITY_KIND_CHOICES = [
    ('email', 'Email'),
    ('call', 'Call'),
    ('meeting', 'Meeting'),
    ('chat', 'Chat'),
    ('note', 'Note'),
    ('document', 'Document'),
    ('other', 'Other'),
]
ACTIVITY_DIRECTION_CHOICES = [
    ('inbound', 'Inbound'),
    ('outbound', 'Outbound'),
    ('internal', 'Internal'),
]
SOURCE_SYSTEM_CHOICES = [
    ('gmail', 'Gmail'),
    ('google_chat', 'Google Chat'),
    ('calendar', 'Calendar'),
    ('phone', 'Phone'),
    ('sheet', 'Google Sheet'),
    ('drive', 'Google Drive'),
    ('agent', 'Agent conversation'),
    ('crm', 'CRM record'),
    ('manual', 'Entered by a person'),
    ('other', 'Other'),
]
RECORDED_VIA_CHOICES = [
    ('rest', 'REST API'),
    ('mcp', 'MCP tool'),
    ('ui', 'CRM website'),
    ('job', 'Background job'),
]
PARTICIPANT_ROLES = ('from', 'to', 'cc', 'bcc', 'attendee', 'organizer', 'caller', 'callee', 'other')

PROPOSAL_KIND_CHOICES = [
    ('field_update', 'Field update'),
    ('new_contact', 'New contact'),
    ('link', 'Link records'),
    ('task', 'New task'),
    ('note', 'Append to notes'),
    ('other', 'Other'),
]
PROPOSAL_TARGET_CHOICES = [
    ('company', 'Company'),
    ('contact', 'Contact'),
    ('task', 'Task'),
]
PROPOSER_KIND_CHOICES = [
    ('agent', 'Agent'),
    ('ai', 'AI model step'),
    ('job', 'Deterministic job'),
    ('human', 'Person'),
]
PROPOSAL_STATUS_CHOICES = [
    ('proposed', 'Proposed'),
    ('accepted', 'Accepted'),
    ('edited', 'Accepted with edits'),
    ('rejected', 'Rejected'),
    ('expired', 'Expired'),
    ('superseded', 'Superseded'),
    ('failed', 'Failed'),
]
# The target as last compared with the suggestion. For an update: the record is
# there, was made inactive (is_active false), moved to another company (a contact)
# or was deleted. For a new contact:
# whether a contact with the proposed email or name exists at the company.
TARGET_STATE_CHOICES = [
    ('', 'As when suggested'),
    ('present', 'Present'),
    ('inactive', 'Made inactive'),
    ('moved', 'Moved to another company'),
    ('missing', 'Deleted'),
    ('no_duplicate', 'No contact with that email or name'),
    ('duplicate', 'A contact with that email or name exists'),
]
# Only one open proposal per fingerprint (enforced by a partial unique index).
# An agent may not raise again a fingerprint that was decided; a person may.
OPEN_STATUS = 'proposed'
DECIDED_STATUSES = ('accepted', 'edited', 'rejected')


class Activity(models.Model):
    """One interaction with a customer: an email, call, meeting, chat, note or document.

    Append-only apart from voiding: a wrong row is voided with a reason, never
    deleted. ``idempotency_key`` is unique per recording user, so a retried
    write returns the stored row instead of a duplicate.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECT: deleting a company must not erase its interaction log.
    company = models.ForeignKey(
        'crm_app.Company', on_delete=models.PROTECT, related_name='inbox_activities',
    )
    contact = models.ForeignKey(
        'crm_app.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='inbox_activities',
    )
    contract = models.ForeignKey(
        'crm_app.Contract', on_delete=models.SET_NULL, null=True, blank=True, related_name='inbox_activities',
    )
    quote = models.ForeignKey(
        'crm_app.Quote', on_delete=models.SET_NULL, null=True, blank=True, related_name='inbox_activities',
    )
    opportunity = models.ForeignKey(
        'crm_app.Opportunity', on_delete=models.SET_NULL, null=True, blank=True, related_name='inbox_activities',
    )
    kind = models.CharField(max_length=20, choices=ACTIVITY_KIND_CHOICES)
    direction = models.CharField(max_length=10, choices=ACTIVITY_DIRECTION_CHOICES)
    occurred_at = models.DateTimeField(help_text='When the interaction happened')
    summary = models.CharField(max_length=SUMMARY_MAX, help_text='One plain-text line')
    body = models.TextField(blank=True, default='', help_text='Optional plain text; never rendered as HTML')
    participants = models.JSONField(
        default=list, blank=True, help_text='List of {name, address, role}',
    )
    source_system = models.CharField(max_length=20, choices=SOURCE_SYSTEM_CHOICES)
    source_ref = models.CharField(
        max_length=SOURCE_REF_MAX, blank=True, default='',
        help_text='Identifier in the source system, e.g. a message id',
    )
    source_url = models.CharField(max_length=SOURCE_URL_MAX, blank=True, default='')
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    recorded_by_username = models.CharField(max_length=150)
    recorded_via = models.CharField(max_length=10, choices=RECORDED_VIA_CHOICES)
    idempotency_key = models.CharField(max_length=KEY_MAX)
    payload_sha256 = models.CharField(max_length=64)
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=REASON_MAX, blank=True, default='')
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    duplicate_of = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text='The captured record that replaced this one for the same source',
    )
    restricted = models.BooleanField(
        default=False, help_text='Set by the recorder: the body is not shown to agent accounts',
    )
    is_redacted = models.BooleanField(
        default=False, help_text='Summary, body and participants were removed because the source was purged',
    )
    redacted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-occurred_at', '-created_at']
        verbose_name_plural = 'activities'
        indexes = [
            models.Index(fields=['company', '-occurred_at'], name='inbox_act_company_time'),
            models.Index(fields=['contact', '-occurred_at'], name='inbox_act_contact_time'),
            models.Index(fields=['recorded_by', 'created_at'], name='inbox_act_recorder_time'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['recorded_by', 'idempotency_key'], name='inbox_activity_unique_key',
            ),
            models.UniqueConstraint(
                fields=['company', 'source_system', 'source_ref'],
                condition=~Q(source_ref='') & Q(is_void=False),
                name='inbox_activity_unique_source',
            ),
        ]

    def __str__(self):
        return f'{self.kind} {self.direction} {self.occurred_at:%Y-%m-%d}'


class ChangeProposal(models.Model):
    """A proposed change to one CRM record, waiting for a person to decide.

    Nothing is applied when a proposal is stored. Accepting it applies
    ``applied_patch`` through the guarded MCP write path as the reviewer; the
    resulting AuditLog row id is kept in ``applied_audit_id``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECT: deleting a company must not erase the decision log.
    company = models.ForeignKey(
        'crm_app.Company', on_delete=models.PROTECT, related_name='change_proposals',
        help_text='The customer the proposal is about (the target or its company)',
    )
    target_collection = models.CharField(max_length=20, choices=PROPOSAL_TARGET_CHOICES)
    target_id = models.CharField(
        max_length=64, blank=True, default='', help_text='Empty for a proposal that creates a record',
    )
    kind = models.CharField(max_length=20, choices=PROPOSAL_KIND_CHOICES)
    patch = models.JSONField(help_text='Field -> proposed value, as proposed')
    applied_patch = models.JSONField(null=True, blank=True, help_text='What was applied (after edits)')
    current_values = models.JSONField(default=dict, blank=True, help_text='Target values when last read')
    expected_version = models.CharField(max_length=40, blank=True, default='')
    evidence_quote = models.TextField(blank=True, default='')
    evidence_verified = models.BooleanField(
        default=False, help_text='The quote was found verbatim in the referenced activity body',
    )
    evidence_source_system = models.CharField(max_length=20, choices=SOURCE_SYSTEM_CHOICES, blank=True, default='')
    evidence_source_ref = models.CharField(max_length=SOURCE_REF_MAX, blank=True, default='')
    evidence_source_url = models.CharField(max_length=SOURCE_URL_MAX, blank=True, default='')
    activity = models.ForeignKey(
        Activity, on_delete=models.SET_NULL, null=True, blank=True, related_name='change_proposals',
    )
    evidence_occurred_at = models.DateTimeField(
        null=True, blank=True, help_text='When the source said it (the activity time when one is linked)',
    )
    evidence_recorder_is_agent = models.BooleanField(
        default=False, help_text='The linked activity was recorded by an agent account',
    )
    rationale = models.CharField(max_length=RATIONALE_MAX, blank=True, default='')
    proposer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    proposer_username = models.CharField(max_length=150)
    proposer_kind = models.CharField(max_length=10, choices=PROPOSER_KIND_CHOICES)
    proposed_via = models.CharField(max_length=10, choices=RECORDED_VIA_CHOICES)
    model = models.CharField(max_length=MODEL_NAME_MAX, blank=True, default='')
    prompt_version = models.CharField(max_length=MODEL_NAME_MAX, blank=True, default='')
    confidence = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=PROPOSAL_STATUS_CHOICES, default='proposed')
    fingerprint = models.CharField(max_length=64)
    batch_key = models.CharField(max_length=BATCH_KEY_MAX, blank=True, default='')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    reviewer_username = models.CharField(max_length=150, blank=True, default='')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=DECISION_NOTE_MAX, blank=True, default='')
    target_changed_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Set when a watched value or the target state changed since the suggestion; '
                  'current_values were re-read then',
    )
    target_state = models.CharField(
        max_length=12, choices=TARGET_STATE_CHOICES, blank=True, default='',
        help_text='The target as last compared. Empty on rows from before this was kept: read as present '
                  '(an update) or no_duplicate (a new contact)',
    )
    last_apply_error = models.CharField(max_length=APPLY_ERROR_MAX, blank=True, default='')
    applied_record_id = models.CharField(max_length=64, blank=True, default='')
    applied_audit_id = models.UUIDField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    history = models.JSONField(
        default=list, blank=True, help_text='Earlier decisions and reopenings: [{action, by, at, note}]',
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='inbox_prop_status_time'),
            models.Index(fields=['company', 'status'], name='inbox_prop_company_status'),
            models.Index(fields=['proposer', '-created_at'], name='inbox_prop_proposer_time'),
            models.Index(fields=['batch_key'], name='inbox_prop_batch'),
            models.Index(fields=['target_collection', 'target_id'], name='inbox_prop_target'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['fingerprint'], condition=Q(status=OPEN_STATUS),
                name='inbox_proposal_unique_open_fingerprint',
            ),
        ]

    def __str__(self):
        return f'{self.kind} {self.target_collection} {self.status}'


class RedactedSource(models.Model):
    """A source whose content was removed here; it cannot be recorded or cited again.

    Holds no content: the source system and canonical reference, when, and why.
    """

    id = models.BigAutoField(primary_key=True)
    source_system = models.CharField(max_length=20, choices=SOURCE_SYSTEM_CHOICES)
    source_ref = models.CharField(max_length=SOURCE_REF_MAX)
    reason = models.CharField(max_length=REASON_MAX, blank=True, default='')
    redacted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-redacted_at']
        constraints = [
            models.UniqueConstraint(fields=['source_system', 'source_ref'], name='inbox_redacted_source_unique'),
        ]
        indexes = [models.Index(fields=['source_ref'], name='inbox_redacted_ref')]

    def __str__(self):
        return f'{self.source_system} redacted {self.redacted_at:%Y-%m-%d}'


class ProposalRefusal(models.Model):
    """A refused proposal attempt, counted with stored proposals against the daily cap."""

    id = models.BigAutoField(primary_key=True)
    proposer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    code = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['proposer', 'created_at'], name='inbox_refusal_proposer_time')]

    def __str__(self):
        return f'{self.code} {self.created_at:%Y-%m-%d %H:%M}'
