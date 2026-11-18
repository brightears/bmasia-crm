"""Django admin for mail capture: read-mostly.

Captured data (messages, copies, participants, conversations, matches, the
queue, runs and the access log) is view-only: no add, change or delete here.
Configuration (mailboxes, rules, company domains) is editable by staff with
the model permissions. Saving a rule applies the rules to stored
mail at once (``purge.enforce_rules``).
"""
from django.contrib import admin, messages

from .models import (
    CaptureMailbox, CaptureRule, CaptureRun, CompanyDomain, MailboxAccessLog, MailboxCopy,
    MailConversation, MailMatch, MailMessage, MailParticipant, UnmatchedSender,
)
from .purge import enforce_rules


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CaptureMailbox)
class CaptureMailboxAdmin(admin.ModelAdmin):
    list_display = ('email', 'kind', 'enabled', 'body_mode', 'visibility', 'last_poll_at',
                    'needs_resync', 'consecutive_errors')
    list_filter = ('enabled', 'kind', 'body_mode', 'needs_resync')
    search_fields = ('email',)
    readonly_fields = (
        'history_id', 'newest_internal_date', 'last_poll_at', 'last_full_sync_at',
        'needs_resync', 'last_error', 'consecutive_errors', 'enforced_label_ids',
        'lease_token', 'lease_expires_at', 'created_at', 'updated_at',
    )

    def has_delete_permission(self, request, obj=None):
        return False  # switch a mailbox off with "enabled"; its access log must stay


@admin.register(CaptureRule)
class CaptureRuleAdmin(admin.ModelAdmin):
    list_display = ('kind', 'value', 'action', 'scope', 'mailbox', 'created_at')
    list_filter = ('kind', 'action', 'scope')
    search_fields = ('value', 'note')
    readonly_fields = ('created_by', 'created_at')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        counts = enforce_rules()
        messages.info(
            request,
            'Rules applied to stored mail: {purged} messages purged, {copies_dropped} copies '
            'dropped, {bodies_cleared} bodies cleared, {queue_removed} queue rows removed.'.format(**counts),
        )


@admin.register(CompanyDomain)
class CompanyDomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'company', 'is_primary', 'shared_group_domain', 'created_at')
    list_filter = ('shared_group_domain', 'is_primary')
    search_fields = ('domain', 'company__name')
    autocomplete_fields = ('company',)
    readonly_fields = ('created_by', 'created_at')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class MailboxCopyInline(admin.TabularInline):
    model = MailboxCopy
    extra = 0
    can_delete = False
    fields = ('mailbox', 'gmail_id', 'gmail_thread_id', 'label_ids', 'internal_date')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class MailParticipantInline(admin.TabularInline):
    model = MailParticipant
    extra = 0
    can_delete = False
    fields = ('role', 'address', 'display_name', 'domain', 'is_internal', 'contact')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MailMessage)
class MailMessageAdmin(ReadOnlyAdmin):
    list_display = ('sent_at', 'direction', 'subject', 'capture_state', 'conversation')
    list_filter = ('direction', 'capture_state', 'message_id_synthetic')
    search_fields = ('subject', 'rfc_message_id', 'from_address')
    date_hierarchy = 'sent_at'
    exclude = ('body_text',)
    inlines = (MailParticipantInline, MailboxCopyInline)


@admin.register(MailConversation)
class MailConversationAdmin(ReadOnlyAdmin):
    list_display = ('subject_normalised', 'company', 'link_state', 'message_count',
                    'last_message_at', 'last_inbound_at', 'last_outbound_at')
    list_filter = ('link_state',)
    search_fields = ('subject_normalised', 'conversation_key')


@admin.register(MailboxCopy)
class MailboxCopyAdmin(ReadOnlyAdmin):
    list_display = ('mailbox', 'gmail_id', 'internal_date')
    list_filter = ('mailbox',)


@admin.register(MailParticipant)
class MailParticipantAdmin(ReadOnlyAdmin):
    list_display = ('role', 'address', 'domain', 'is_internal', 'contact')
    list_filter = ('role', 'is_internal')
    search_fields = ('address', 'domain')


@admin.register(MailMatch)
class MailMatchAdmin(ReadOnlyAdmin):
    list_display = ('target_type', 'target_id', 'method', 'confidence', 'status', 'created_at')
    list_filter = ('target_type', 'method', 'status', 'confidence')


@admin.register(UnmatchedSender)
class UnmatchedSenderAdmin(ReadOnlyAdmin):
    list_display = ('address', 'domain', 'reason', 'status', 'message_count', 'last_seen', 'expires_at')
    list_filter = ('status', 'reason')
    search_fields = ('address', 'domain', 'display_name')


@admin.register(CaptureRun)
class CaptureRunAdmin(ReadOnlyAdmin):
    list_display = ('started_at', 'mailbox', 'kind', 'dry_run', 'outcome', 'fetched', 'stored',
                    'matched', 'unmatched', 'errors')
    list_filter = ('kind', 'outcome', 'dry_run')


@admin.register(MailboxAccessLog)
class MailboxAccessLogAdmin(ReadOnlyAdmin):
    list_display = ('at', 'mailbox', 'purpose', 'actor', 'dry_run', 'api_calls', 'messages_read',
                    'bodies_read')
    list_filter = ('purpose', 'dry_run')
