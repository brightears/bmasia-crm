"""Tables for mail capture (research/11 section B.7).

On-delete policy, so that capture never removes or blocks CRM records:

* Every foreign key into ``crm_app`` (company, contact, user, EmailLog) is
  nullable with ``SET_NULL``. Deleting a company, contact or user through the
  existing delete flows keeps working and only unlinks captured mail. Nothing
  here is ``CASCADE`` or ``PROTECT`` towards a CRM record, except
  ``CompanyDomain`` which is configuration of the company itself and goes with
  it (``CASCADE`` from the company side; it can never delete the company).
* ``MailMatch`` points at its target by type and id (like ``AuditLog``), so it
  never blocks a delete; a match whose target is gone is ignored by readers.
* Inside the app, a mailbox is ``PROTECT``-ed by its copies, runs and access
  log (switch a mailbox off with ``enabled``; the access log must survive).
  A message owns its copies, participants and matches (``CASCADE``); purging a
  message removes all of them.

Beyond B.7: ``CapturePurge`` (one counts-only row per purge chunk) and
``CaptureFailure`` (messages that failed, retried then parked; Gmail id and
error class only).
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


# --- mailboxes -------------------------------------------------------------

class CaptureMailbox(models.Model):
    """One Google Workspace mailbox on the capture allowlist.

    ``enabled`` is the per-mailbox switch: the sync engine refuses a disabled
    mailbox before it asks for a client, and the credential factory (next PR)
    must refuse to mint credentials for it as well.
    """

    KIND_CHOICES = [('person', 'Person'), ('shared', 'Shared mailbox')]
    BODY_MODE_CHOICES = [('headers', 'Headers only'), ('body', 'Headers and body')]
    VISIBILITY_CHOICES = [('owner', 'Owner and admins'), ('team', 'Whole team')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, help_text='Mailbox address, lower-case')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='person')
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='capture_mailboxes',
    )
    enabled = models.BooleanField(default=False)
    body_mode = models.CharField(max_length=10, choices=BODY_MODE_CHOICES, default='headers')
    capture_calendar = models.BooleanField(default=False)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='owner')
    backfill_since = models.DateField(null=True, blank=True)

    # Sync cursor and health.
    history_id = models.CharField(max_length=32, blank=True, default='')
    newest_internal_date = models.DateTimeField(
        null=True, blank=True, help_text='Newest message date seen; bounds a resync',
    )
    last_poll_at = models.DateTimeField(null=True, blank=True)
    last_full_sync_at = models.DateTimeField(null=True, blank=True)
    needs_resync = models.BooleanField(default=False)
    last_error = models.CharField(
        max_length=200, blank=True, default='',
        help_text='Error class and status only; never a subject or address',
    )
    consecutive_errors = models.PositiveIntegerField(default=0)
    enforced_label_ids = models.JSONField(
        default=dict, blank=True,
        help_text='Label ids of label rules last applied to stored copies',
    )

    # Lease that keeps one runner per mailbox (taken under SKIP LOCKED).
    lease_token = models.CharField(max_length=64, blank=True, default='')
    lease_expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['email']
        verbose_name = 'capture mailbox'
        verbose_name_plural = 'capture mailboxes'

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or '').strip().lower()
        super().save(*args, **kwargs)


# --- conversations and messages -------------------------------------------

class MailConversation(models.Model):
    """Messages joined across mailboxes by RFC threading headers.

    ``conversation_key`` is the first id in References, else In-Reply-To, else
    the message's own Message-ID (``parse.conversation_key``). The ``last_*``
    times drive the unanswered clock in a later PR.
    """

    LINK_STATE_CHOICES = [
        ('none', 'Not linked'),
        ('auto', 'Linked automatically'),
        ('confirmed', 'Confirmed by a person'),
        ('ambiguous', 'Ambiguous'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_key = models.CharField(max_length=512, unique=True)
    subject_normalised = models.CharField(max_length=300, blank=True, default='')
    first_message_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    last_outbound_at = models.DateTimeField(null=True, blank=True)
    last_claimed_internal_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Latest message whose From claims an internal sender but no captured '
                  'copy carries SENT: a hint only; it never moves last_outbound_at',
    )
    message_count = models.PositiveIntegerField(default=0)
    company = models.ForeignKey(
        'crm_app.Company', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mail_conversations',
    )
    link_state = models.CharField(max_length=10, choices=LINK_STATE_CHOICES, default='none')
    is_mixed = models.BooleanField(
        default=False,
        help_text='Participants from more than one customer; the company link needs a person',
    )
    link_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    link_confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_message_at']
        indexes = [
            models.Index(fields=['company', '-last_message_at'], name='mc_conv_company_last'),
            models.Index(fields=['subject_normalised'], name='mc_conv_subject'),
        ]

    def __str__(self):
        return f'conversation {self.pk} ({self.message_count} messages)'


class MailMessage(models.Model):
    """One email, stored once however many mailboxes hold it.

    ``rfc_message_id`` is the canonical Message-ID (``identity.canonical_source_ref``).
    When a message has none, a fallback key ``synthetic:<sha256>`` is used and
    ``message_id_synthetic`` is set (``parse.synthetic_message_id`` states its limits).

    Times: ``sent_at`` is Gmail's internal date, the clock a sender cannot set;
    retention and the conversation clocks use it. ``claimed_date`` is the Date
    header, kept for display; a claim far from Gmail's date is flagged.

    Direction: ``outbound`` only when a captured mailbox's copy carries Gmail's
    SENT label; a From header that merely claims an internal sender is
    ``claimed_internal`` and moves neither clock.

    ``body_text`` stays empty unless the capturing mailbox has
    ``body_mode='body'`` and the message matched a company. Purging deletes the
    row (with copies, participants and matches); no tombstone is kept.
    """

    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound (SENT label on a captured copy)'),
        ('claimed_internal', 'From claims an internal sender; not verified'),
    ]
    CAPTURE_STATE_CHOICES = [('headers', 'Headers only'), ('body', 'Headers and body')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfc_message_id = models.CharField(max_length=512, unique=True)
    message_id_synthetic = models.BooleanField(default=False)
    conversation = models.ForeignKey(
        MailConversation, on_delete=models.PROTECT, related_name='messages',
    )
    sent_at = models.DateTimeField(
        help_text="Gmail's internal date (the trusted clock), earliest over the copies",
    )
    claimed_date = models.DateTimeField(
        null=True, blank=True, help_text='The Date header as the sender claims it; display only',
    )
    from_address = models.CharField(max_length=320, blank=True, default='')
    from_name = models.CharField(max_length=200, blank=True, default='')
    subject = models.CharField(max_length=300, blank=True, default='')
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES)
    flags = models.JSONField(
        default=list, blank=True, help_text='truncated, bounded, date_mismatch, synthetic_id',
    )
    in_reply_to = models.CharField(max_length=512, blank=True, default='')
    references = models.JSONField(default=list, blank=True)
    has_attachments = models.BooleanField(
        default=False,
        help_text='Known only when the body was read (format=full); under headers-only '
                  'capture False means unknown, not "no attachments"',
    )
    attachments = models.JSONField(
        default=list, blank=True,
        help_text='Metadata only: filename, mime_type, size, gmail ids to fetch it',
    )
    body_text = models.TextField(null=True, blank=True)
    body_sha256 = models.CharField(max_length=64, blank=True, default='')
    capture_state = models.CharField(
        max_length=10, choices=CAPTURE_STATE_CHOICES, default='headers',
    )
    headers_only_rule = models.BooleanField(
        default=False, help_text='A headers-only rule applies; never store a body',
    )
    email_log = models.ForeignKey(
        'crm_app.EmailLog', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='captured_messages',
        help_text='Set when the CRM itself sent this message',
    )
    first_seen_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['conversation', 'sent_at'], name='mc_msg_conv_sent'),
            models.Index(fields=['sent_at'], name='mc_msg_sent'),
        ]

    def __str__(self):
        return f'message {self.pk} ({self.direction}, {self.sent_at:%Y-%m-%d})'


class MailboxCopy(models.Model):
    """The appearance of a message in one mailbox (Gmail ids are per mailbox)."""

    id = models.BigAutoField(primary_key=True)
    message = models.ForeignKey(MailMessage, on_delete=models.CASCADE, related_name='copies')
    mailbox = models.ForeignKey(CaptureMailbox, on_delete=models.PROTECT, related_name='copies')
    gmail_id = models.CharField(max_length=64)
    gmail_thread_id = models.CharField(max_length=64, blank=True, default='')
    label_ids = models.JSONField(default=list, blank=True)
    internal_date = models.DateTimeField(null=True, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['mailbox', 'gmail_id'], name='mc_copy_unique_gmail_id'),
            models.UniqueConstraint(fields=['mailbox', 'message'], name='mc_copy_unique_message'),
        ]
        indexes = [
            models.Index(fields=['mailbox', 'internal_date'], name='mc_copy_mailbox_date'),
        ]

    def __str__(self):
        return f'copy {self.gmail_id} in {self.mailbox_id}'


class MailParticipant(models.Model):
    """One address on a message. BCC is never stored."""

    ROLE_CHOICES = [('from', 'From'), ('to', 'To'), ('cc', 'Cc'), ('reply_to', 'Reply-To')]

    id = models.BigAutoField(primary_key=True)
    message = models.ForeignKey(MailMessage, on_delete=models.CASCADE, related_name='participants')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    address = models.CharField(max_length=320, help_text='Lower-case, as written')
    display_name = models.CharField(max_length=200, blank=True, default='')
    domain = models.CharField(max_length=253, blank=True, default='')
    is_internal = models.BooleanField(default=False)
    contact = models.ForeignKey(
        'crm_app.Contact', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mail_participations',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'role', 'address'], name='mc_participant_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['address'], name='mc_part_address'),
            models.Index(fields=['domain'], name='mc_part_domain'),
        ]

    def __str__(self):
        return f'{self.role} participant on {self.message_id}'


class MailMatch(models.Model):
    """A link from a message or a conversation to a CRM record.

    Unique per (message, target) and per (conversation, target). A row with
    ``status='rejected'`` blocks the same link from being proposed or applied
    again, because the matcher reads rejections from the snapshot and the
    writer never updates a rejected row.
    """

    TARGET_CHOICES = [
        ('company', 'Company'), ('contact', 'Contact'), ('contract', 'Contract'),
        ('quote', 'Quote'), ('invoice', 'Invoice'), ('opportunity', 'Opportunity'),
        ('ticket', 'Ticket'),
    ]
    METHOD_CHOICES = [
        ('contact_email', 'Contact email'), ('company_domain', 'Company domain'),
        ('thread', 'Thread'), ('doc_number', 'Document number'),
        ('crm_sent', 'Sent by the CRM'), ('manual', 'Manual'), ('proposal', 'Proposal'),
    ]
    CONFIDENCE_CHOICES = [('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]
    STATUS_CHOICES = [
        ('auto', 'Automatic'), ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'), ('proposed', 'Proposed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        MailMessage, on_delete=models.CASCADE, null=True, blank=True, related_name='matches',
    )
    conversation = models.ForeignKey(
        MailConversation, on_delete=models.CASCADE, null=True, blank=True, related_name='matches',
    )
    target_type = models.CharField(max_length=12, choices=TARGET_CHOICES)
    target_id = models.CharField(max_length=64)
    method = models.CharField(max_length=16, choices=METHOD_CHOICES)
    confidence = models.CharField(max_length=8, choices=CONFIDENCE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    detail = models.JSONField(default=dict, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(message__isnull=False, conversation__isnull=True)
                    | Q(message__isnull=True, conversation__isnull=False)
                ),
                name='mc_match_message_xor_conversation',
            ),
            models.UniqueConstraint(
                fields=['message', 'target_type', 'target_id'],
                condition=Q(message__isnull=False),
                name='mc_match_unique_message_target',
            ),
            models.UniqueConstraint(
                fields=['conversation', 'target_type', 'target_id'],
                condition=Q(conversation__isnull=False),
                name='mc_match_unique_conversation_target',
            ),
        ]
        indexes = [
            models.Index(fields=['target_type', 'target_id'], name='mc_match_target'),
            models.Index(fields=['status'], name='mc_match_status'),
        ]

    def __str__(self):
        return f'{self.target_type} match ({self.method}, {self.status})'


# --- matching reference data -----------------------------------------------

class CompanyDomain(models.Model):
    """A mail domain that identifies a company.

    A domain on more than one company counts as shared automatically, and a
    shared domain never matches by itself (``match.py`` rule 5).
    """

    id = models.BigAutoField(primary_key=True)
    company = models.ForeignKey(
        'crm_app.Company', on_delete=models.CASCADE, related_name='mail_domains',
    )
    domain = models.CharField(max_length=253)
    is_primary = models.BooleanField(default=False)
    shared_group_domain = models.BooleanField(
        default=False, help_text='A group domain used by several companies; never auto-matches',
    )
    note = models.CharField(max_length=200, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'domain'], name='mc_company_domain_unique'),
        ]
        indexes = [models.Index(fields=['domain'], name='mc_company_domain')]

    def __str__(self):
        return self.domain

    def clean(self):
        from django.core.exceptions import ValidationError
        from .rules import company_domain_problem
        self.domain = normalise_rule_value('domain', self.domain)
        problem = company_domain_problem(self.domain)
        if problem:
            raise ValidationError({'domain': problem})

    def save(self, *args, **kwargs):
        # Refused on every path, not only in forms: a freemail, public-suffix
        # or internal domain would match far more than one company.
        from django.core.exceptions import ValidationError
        from .rules import company_domain_problem
        self.domain = normalise_rule_value('domain', self.domain)
        problem = company_domain_problem(self.domain)
        if problem:
            raise ValidationError({'domain': problem})
        super().save(*args, **kwargs)



class UnmatchedSender(models.Model):
    """Review queue of unknown external addresses. Headers only, never a body.

    No ``MailMessage`` is stored for unmatched mail; this row is all that is
    kept (address, name, domain, counts, up to three subjects). Each sample
    and each counted message carries its hashed message key and the mailbox
    it came from, so a purge can remove exactly what belongs to a purged
    message or mailbox. Open rows expire 30 days after Gmail last delivered a
    message from them (``purge.purge_expired_unmatched``).
    """

    STATUS_CHOICES = [
        ('open', 'Open'), ('linked', 'Linked'), ('ignored', 'Ignored'),
        ('never_log', 'Never log'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    address = models.CharField(max_length=320, unique=True)
    domain = models.CharField(max_length=253, blank=True, default='')
    display_name = models.CharField(max_length=200, blank=True, default='')
    first_seen = models.DateTimeField(help_text="Gmail's internal date of the first message")
    last_seen = models.DateTimeField(help_text="Gmail's internal date of the latest message")
    message_count = models.PositiveIntegerField(default=0)
    message_keys = models.JSONField(
        default=list, blank=True,
        help_text='[hashed message key, mailbox] pairs already counted; keeps re-runs '
                  'idempotent and lets a purge find what to remove',
    )
    mailboxes = models.JSONField(default=list, blank=True)
    samples = models.JSONField(
        default=list, blank=True,
        help_text='Up to three {"k": message key, "m": mailbox, "s": subject}',
    )
    candidate_company_ids = models.JSONField(default=list, blank=True)
    reason = models.CharField(
        max_length=20, blank=True, default='',
        help_text='unknown, freemail, shared_domain, ambiguous or domain_match',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['status', 'expires_at'], name='mc_unmatched_status'),
            models.Index(fields=['domain'], name='mc_unmatched_domain'),
        ]

    def __str__(self):
        return f'unmatched sender ({self.status}, {self.message_count} messages)'


class CaptureRule(models.Model):
    """The never-log list and related rules.

    ``kind`` address (plus-addressed variants included) or domain (its
    subdomains included), or label (a Gmail label name, matched
    case-insensitively). The built-in label ``CRM private`` always applies and
    needs no row. Values that would match too much (our own domains, public
    suffixes, freemail domains, Gmail system labels, wildcards) are refused
    (``rules.rule_problem``).

    Actions: ``skip`` stores nothing; ``private`` does the same (meant for
    labels); ``headers_only`` never stores a body. A rule blocks new capture as
    soon as it is saved. Removing mail already stored is a separate step: the
    rule starts ``awaiting_confirmation``; a superuser confirms it after seeing
    a preview; the purge then runs in capped chunks (``purge.enforce_rules``)
    until nothing is left (``done``). This holds for every rule a person
    creates: address, domain and label, organisation or mailbox scope. Only the
    built-in ``CRM private`` label purges at once.

    Changing a rule's kind, value, scope or action sends it back to
    ``awaiting_confirmation``. The confirmation also stores a fingerprint of
    what was confirmed; a rule that no longer matches its fingerprint (for
    example after ``QuerySet.update()``) is treated as unconfirmed everywhere
    (``is_confirmed``).
    """

    KIND_CHOICES = [('address', 'Address'), ('domain', 'Domain'), ('label', 'Gmail label')]
    SCOPE_CHOICES = [('org', 'Whole organisation'), ('mailbox', 'One mailbox')]
    ACTION_CHOICES = [
        ('skip', 'Never log'), ('headers_only', 'Headers only'), ('private', 'Private'),
    ]
    PURGE_STATE_CHOICES = [
        ('awaiting_confirmation', 'Stored mail not yet purged; awaiting confirmation'),
        ('confirmed', 'Confirmed; purge in progress'),
        ('done', 'Stored mail purged'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    value = models.CharField(max_length=320)
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='org')
    mailbox = models.ForeignKey(
        CaptureMailbox, on_delete=models.CASCADE, null=True, blank=True, related_name='rules',
    )
    action = models.CharField(max_length=12, choices=ACTION_CHOICES, default='skip')
    note = models.CharField(max_length=200, blank=True, default='')
    purge_state = models.CharField(
        max_length=24, choices=PURGE_STATE_CHOICES, default='awaiting_confirmation',
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    purge_done_at = models.DateTimeField(null=True, blank=True)
    confirmed_fingerprint = models.CharField(
        max_length=64, blank=True, default='',
        help_text='Hash of kind, value, scope, mailbox and action at confirmation; a rule '
                  'that no longer matches it counts as unconfirmed, however it was changed',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['kind', 'value']
        constraints = [
            # Two conditional constraints because NULL mailboxes never collide.
            models.UniqueConstraint(
                fields=['kind', 'value'], condition=Q(scope='org'), name='mc_rule_unique_org',
            ),
            models.UniqueConstraint(
                fields=['kind', 'value', 'mailbox'], condition=Q(scope='mailbox'),
                name='mc_rule_unique_mailbox',
            ),
            models.CheckConstraint(
                condition=(
                    Q(scope='org', mailbox__isnull=True)
                    | Q(scope='mailbox', mailbox__isnull=False)
                ),
                name='mc_rule_scope_mailbox',
            ),
        ]
        indexes = [models.Index(fields=['purge_state'], name='mc_rule_purge_state')]

    def __str__(self):
        return f'{self.kind} rule ({self.action}, {self.scope})'

    def fingerprint(self):
        return rule_fingerprint(self.kind, self.value, self.scope, self.mailbox_id, self.action)

    @property
    def is_confirmed(self):
        """Confirmed (or done) and unchanged since the confirmation."""
        return (self.purge_state in ('confirmed', 'done')
                and bool(self.confirmed_fingerprint)
                and self.confirmed_fingerprint == self.fingerprint())

    def clean(self):
        from django.core.exceptions import ValidationError
        from .rules import rule_problem
        self.value = normalise_rule_value(self.kind, self.value)
        problem = rule_problem(self.kind, self.value)
        if problem:
            raise ValidationError({'value': problem})

    def save(self, *args, **kwargs):
        self.value = normalise_rule_value(self.kind, self.value)
        if self.pk is not None and not self._state.adding:
            old = type(self).objects.filter(pk=self.pk).values(
                'kind', 'value', 'scope', 'mailbox_id', 'action').first()
            new = {'kind': self.kind, 'value': self.value, 'scope': self.scope,
                   'mailbox_id': self.mailbox_id, 'action': self.action}
            if old is not None and old != new:
                self.purge_state = 'awaiting_confirmation'
                self.confirmed_by = None
                self.confirmed_at = None
                self.purge_done_at = None
                self.confirmed_fingerprint = ''
        super().save(*args, **kwargs)


def rule_fingerprint(kind, value, scope, mailbox_id, action):
    import hashlib
    text = '|'.join([kind or '', normalise_rule_value(kind, value), scope or '',
                     str(mailbox_id or ''), action or ''])
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def normalise_rule_value(kind, value):
    value = (value or '').strip()
    if kind in ('address', 'domain'):
        value = value.lower().lstrip('@').rstrip('.')
    return value


class CapturePurge(models.Model):
    """One purge chunk: what a rule, a label or a deletion removed. Counts only."""

    REASON_CHOICES = [
        ('rule', 'Never-log rule'), ('label', 'Private or label rule'),
        ('gmail_deleted', 'Deleted in Gmail'), ('expiry', 'Queue expiry'),
    ]

    id = models.BigAutoField(primary_key=True)
    at = models.DateTimeField()
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    rule = models.ForeignKey(
        CaptureRule, on_delete=models.SET_NULL, null=True, blank=True, related_name='purges',
    )
    mailbox = models.ForeignKey(
        CaptureMailbox, on_delete=models.SET_NULL, null=True, blank=True, related_name='purges',
    )
    actor = models.CharField(max_length=80, blank=True, default='')
    messages = models.PositiveIntegerField(default=0)
    copies = models.PositiveIntegerField(default=0)
    conversations = models.PositiveIntegerField(default=0)
    queue_rows = models.PositiveIntegerField(default=0)
    queue_samples = models.PositiveIntegerField(default=0)
    bodies_cleared = models.PositiveIntegerField(default=0)
    remaining = models.BooleanField(default=False, help_text='The cap was reached; more follows')

    class Meta:
        ordering = ['-at']
        indexes = [models.Index(fields=['at'], name='mc_purge_at')]

    def __str__(self):
        return f'purge {self.pk} ({self.reason}, {self.messages} messages)'


class CaptureFailure(models.Model):
    """A message that could not be processed. The cursor moves on without it;
    it is retried on later runs and parked after ``sync.MAX_MESSAGE_ATTEMPTS``.
    Holds the Gmail id and the error class only, never content."""

    id = models.BigAutoField(primary_key=True)
    mailbox = models.ForeignKey(
        CaptureMailbox, on_delete=models.CASCADE, related_name='failures',
    )
    gmail_id = models.CharField(max_length=64)
    attempts = models.PositiveIntegerField(default=1)
    error = models.CharField(max_length=80, blank=True, default='')
    code_version = models.CharField(
        max_length=80, blank=True, default='',
        help_text='Code version that failed; parked messages are retried when it changes',
    )
    parked = models.BooleanField(default=False)
    first_failed_at = models.DateTimeField()
    last_failed_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['mailbox', 'gmail_id'], name='mc_failure_unique'),
        ]
        indexes = [models.Index(fields=['mailbox', 'parked'], name='mc_failure_mailbox')]

    def __str__(self):
        return f'failure {self.gmail_id} ({self.attempts}, parked={self.parked})'


# --- runs and access log ---------------------------------------------------

class CaptureRun(models.Model):
    """One run of the sync engine (or of the self-check). Counts only."""

    KIND_CHOICES = [
        ('incremental', 'Incremental'), ('backfill', 'Backfill'), ('resync', 'Resync'),
        ('check', 'Check'), ('selfcheck', 'Self-check'),
    ]
    OUTCOME_CHOICES = [
        ('running', 'Running'), ('ok', 'OK'), ('partial', 'Partial; continues next run'),
        ('ok_with_failures', 'Finished; some messages failed or were parked'),
        ('disabled', 'Capture disabled'), ('busy', 'Another runner holds the mailbox'),
        ('resync_needed', 'Resync needed'), ('rate_limited', 'Rate limited'), ('error', 'Error'),
    ]

    id = models.BigAutoField(primary_key=True)
    mailbox = models.ForeignKey(
        CaptureMailbox, on_delete=models.PROTECT, null=True, blank=True, related_name='runs',
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    dry_run = models.BooleanField(default=False)
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES, default='running')
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    listed = models.PositiveIntegerField(default=0)
    fetched = models.PositiveIntegerField(default=0)
    stored = models.PositiveIntegerField(default=0)
    copies_added = models.PositiveIntegerField(default=0)
    already_known = models.PositiveIntegerField(default=0)
    skipped_internal = models.PositiveIntegerField(default=0)
    skipped_by_rule = models.PositiveIntegerField(default=0)
    skipped_system = models.PositiveIntegerField(default=0)
    matched = models.PositiveIntegerField(default=0)
    ambiguous = models.PositiveIntegerField(default=0)
    unmatched = models.PositiveIntegerField(default=0)
    purged = models.PositiveIntegerField(default=0)
    malformed = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    parked = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    quota_units_est = models.PositiveIntegerField(default=0)
    failed_gmail_ids = models.JSONField(
        default=list, blank=True, help_text='Gmail ids of messages that failed (at most 100)',
    )
    history_id_start = models.CharField(max_length=32, blank=True, default='')
    history_id_end = models.CharField(max_length=32, blank=True, default='')
    error_summary = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['mailbox', '-started_at'], name='mc_run_mailbox_started'),
            models.Index(fields=['started_at'], name='mc_run_started'),
        ]

    def __str__(self):
        return f'{self.kind} run {self.pk} ({self.outcome})'


class MailboxAccessLog(models.Model):
    """Every read of a mailbox, and every change to a mailbox's capture settings.

    A run writes its row before the first Gmail call and updates it at the
    end, so a run that dies half-way is still on record (``finished_at``
    empty). Kept ``CAPTURE_ACCESS_LOG_RETENTION_DAYS`` (``purge.purge_old_records``).
    """

    PURPOSE_CHOICES = [
        ('poll', 'Incremental poll'), ('backfill', 'Backfill'), ('resync', 'Resync'),
        ('body', 'Body fetch'), ('attachment', 'Attachment'), ('check', 'Check'),
        ('selfcheck', 'Self-check'), ('config', 'Capture settings changed'),
    ]

    id = models.BigAutoField(primary_key=True)
    mailbox = models.ForeignKey(
        CaptureMailbox, on_delete=models.PROTECT, related_name='access_log',
    )
    run = models.ForeignKey(
        CaptureRun, on_delete=models.SET_NULL, null=True, blank=True, related_name='access_log',
    )
    at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=12, choices=PURPOSE_CHOICES)
    actor = models.CharField(max_length=80, help_text='Job name, or user:<id>')
    dry_run = models.BooleanField(default=False)
    api_calls = models.PositiveIntegerField(default=0)
    messages_read = models.PositiveIntegerField(default=0)
    bodies_read = models.PositiveIntegerField(default=0)
    detail = models.JSONField(
        default=dict, blank=True,
        help_text='For config changes: field, old and new value. Never mail content',
    )

    class Meta:
        ordering = ['-at']
        indexes = [
            models.Index(fields=['mailbox', '-at'], name='mc_access_mailbox_at'),
            models.Index(fields=['at'], name='mc_access_at'),
        ]

    def __str__(self):
        return f'{self.purpose} on {self.mailbox_id} at {self.at:%Y-%m-%d %H:%M}'
