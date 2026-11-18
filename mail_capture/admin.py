"""Django admin for mail capture: superusers only, read-mostly.

Until per-mailbox visibility is enforced in a real screen, every page of this
app (captured data and configuration alike) is visible to active superusers
only. Captured data is view-only: no add, change or delete here.
Configuration (mailboxes, rules, company domains) is editable by superusers.

* Changing a mailbox's ``enabled``, ``body_mode`` or ``visibility`` (or
  creating one) is written to the mailbox access log with the actor. A
  mailbox's address cannot change after it is created.
* There is no search box on captured data or on rule values: Django admin
  search puts the terms in the URL, and URLs reach request logs. Use the
  filters.
* Parked messages (``CaptureFailure``) have an "Unpark" action; the next run
  of that mailbox retries them. ``manage.py mail_capture_unpark`` does the same.
* Saving a rule never purges by itself. A rule blocks new capture at once;
  removing mail already stored needs a second step: the confirmation page
  shows how many messages, conversations and queue rows would go, and only
  "Confirm purge" starts it (``purge.confirm_rule`` then ``enforce_rules``,
  capped per call; later runs continue). The page carries the previewed
  rule's fingerprint and count; if the rule changed since the preview the
  confirmation is refused ("the rule changed since the preview: preview
  again") and nothing is purged.
* A mailbox marked "needs attention" (repeated failed runs) shows it in the
  list; the "Clear needs attention" action lets runs start again.
"""
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .models import (
    CaptureFailure, CaptureMailbox, CapturePurge, CaptureRule, CaptureRun, CaptureSkip, CompanyDomain,
    MailboxAccessLog, MailboxCopy, MailConversation, MailMatch, MailMessage, MailParticipant,
    UnmatchedSender,
)
from .purge import RuleChanged, confirm_rule, enforce_rules, preview_rule


def _superuser(request):
    user = request.user
    return bool(user.is_active and user.is_superuser)


class SuperuserAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return _superuser(request)

    def has_view_permission(self, request, obj=None):
        return _superuser(request)

    def has_add_permission(self, request, obj=None):
        return _superuser(request)

    def has_change_permission(self, request, obj=None):
        return _superuser(request)

    def has_delete_permission(self, request, obj=None):
        return _superuser(request)


class ReadOnlyAdmin(SuperuserAdmin):
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


AUDITED_MAILBOX_FIELDS = ('enabled', 'body_mode', 'visibility')


@admin.register(CaptureMailbox)
class CaptureMailboxAdmin(SuperuserAdmin):
    list_display = ('email', 'kind', 'enabled', 'body_mode', 'visibility', 'last_poll_at',
                    'needs_resync', 'consecutive_errors', 'needs_attention', 'attention_reason')
    list_filter = ('enabled', 'kind', 'body_mode', 'needs_resync', 'needs_attention')
    search_fields = ('email',)
    readonly_fields = (
        'history_id', 'newest_internal_date', 'last_poll_at', 'last_full_sync_at',
        'needs_resync', 'last_error', 'consecutive_errors', 'needs_attention', 'attention_reason',
        'attention_code_version', 'enforced_label_ids',
        'lease_token', 'lease_expires_at', 'created_at', 'updated_at',
    )
    actions = ('clear_needs_attention',)

    @admin.action(description='Clear needs attention: let runs start again')
    def clear_needs_attention(self, request, queryset):
        if not _superuser(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        from .sync import clear_attention
        count = 0
        for mailbox in queryset.filter(needs_attention=True):
            clear_attention(mailbox, f'user:{request.user.pk}', 'cleared in the admin')
            count += 1
        messages.info(request, f'{count} mailboxes cleared; the next run starts again where it stopped.')

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields + ('email',) if obj is not None else fields

    def has_delete_permission(self, request, obj=None):
        return False  # switch a mailbox off with "enabled"; its access log must stay

    def save_model(self, request, obj, form, change):
        old = {}
        if change and obj.pk:
            old = CaptureMailbox.objects.filter(pk=obj.pk).values(*AUDITED_MAILBOX_FIELDS).first() or {}
        super().save_model(request, obj, form, change)
        actor = f'user:{request.user.pk}'
        changes = [
            {'field': name, 'old': old.get(name) if change else None, 'new': getattr(obj, name)}
            for name in AUDITED_MAILBOX_FIELDS
            if not change or old.get(name) != getattr(obj, name)
        ]
        for item in changes:
            MailboxAccessLog.objects.create(
                mailbox=obj, at=timezone.now(), purpose='config', actor=actor, detail=item,
            )


@admin.register(CaptureRule)
class CaptureRuleAdmin(SuperuserAdmin):
    list_display = ('kind', 'value', 'action', 'scope', 'mailbox', 'purge_state', 'created_at')
    list_filter = ('kind', 'action', 'scope', 'purge_state')
    readonly_fields = ('purge_state', 'confirmed_by', 'confirmed_at', 'purge_done_at',
                       'created_by', 'created_at', 'updated_at')

    def get_urls(self):
        return [
            path('<uuid:rule_id>/confirm-purge/', self.admin_site.admin_view(self.confirm_view),
                 name='mail_capture_capturerule_confirm'),
        ] + super().get_urls()

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def _confirm_redirect(self, obj):
        return HttpResponseRedirect(reverse('admin:mail_capture_capturerule_confirm', args=[obj.pk]))

    def response_add(self, request, obj, post_url_continue=None):
        return self._confirm_redirect(obj)

    def response_change(self, request, obj):
        if obj.purge_state == 'awaiting_confirmation':
            return self._confirm_redirect(obj)
        return super().response_change(request, obj)

    def confirm_view(self, request, rule_id):
        if not _superuser(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        rule = get_object_or_404(CaptureRule.objects.select_related('mailbox'), pk=rule_id)
        if request.method == 'POST' and request.POST.get('confirm') == 'yes':
            try:
                confirm_rule(rule, request.user,
                             expected_fingerprint=str(request.POST.get('fingerprint', ''))[:64])
            except RuleChanged as exc:
                messages.error(request, str(exc))
                return HttpResponseRedirect(reverse('admin:mail_capture_capturerule_confirm', args=[rule.pk]))
            counts = enforce_rules(rules=[rule], actor=f'user:{request.user.pk}')
            previewed = str(request.POST.get('previewed', ''))[:12]
            messages.info(
                request,
                'Purge confirmed (preview showed {previewed} messages): {messages} messages, {copies} '
                'copies, {queue_rows} queue rows removed so far. Any remainder continues on the next '
                'runs.'.format(previewed=previewed if previewed.isdigit() else 'no count', **counts),
            )
            return HttpResponseRedirect(reverse('admin:mail_capture_capturerule_changelist'))
        context = dict(
            self.admin_site.each_context(request),
            title='Confirm purge of stored mail',
            rule=rule,
            fingerprint=rule.fingerprint(),
            preview=preview_rule(rule),
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/mail_capture/confirm_purge.html', context)


@admin.register(CompanyDomain)
class CompanyDomainAdmin(SuperuserAdmin):
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

    def has_view_permission(self, request, obj=None):
        return _superuser(request)


class MailParticipantInline(admin.TabularInline):
    model = MailParticipant
    extra = 0
    can_delete = False
    fields = ('role', 'address', 'display_name', 'domain', 'is_internal', 'contact')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return _superuser(request)


@admin.register(MailMessage)
class MailMessageAdmin(ReadOnlyAdmin):
    list_display = ('sent_at', 'direction', 'subject', 'capture_state', 'conversation')
    list_filter = ('direction', 'capture_state', 'message_id_synthetic')
    date_hierarchy = 'sent_at'
    exclude = ('body_text',)
    inlines = (MailParticipantInline, MailboxCopyInline)


@admin.register(MailConversation)
class MailConversationAdmin(ReadOnlyAdmin):
    list_display = ('subject_normalised', 'company', 'link_state', 'is_mixed', 'message_count',
                    'last_message_at', 'last_inbound_at', 'last_outbound_at')
    list_filter = ('link_state', 'is_mixed')


@admin.register(MailboxCopy)
class MailboxCopyAdmin(ReadOnlyAdmin):
    list_display = ('mailbox', 'gmail_id', 'internal_date')
    list_filter = ('mailbox',)


@admin.register(MailParticipant)
class MailParticipantAdmin(ReadOnlyAdmin):
    list_display = ('role', 'address', 'domain', 'is_internal', 'contact')
    list_filter = ('role', 'is_internal')


@admin.register(MailMatch)
class MailMatchAdmin(ReadOnlyAdmin):
    list_display = ('target_type', 'target_id', 'method', 'confidence', 'status', 'created_at')
    list_filter = ('target_type', 'method', 'status', 'confidence')


@admin.register(UnmatchedSender)
class UnmatchedSenderAdmin(ReadOnlyAdmin):
    list_display = ('address', 'domain', 'reason', 'status', 'message_count', 'last_seen', 'expires_at')
    list_filter = ('status', 'reason')


@admin.register(CaptureRun)
class CaptureRunAdmin(ReadOnlyAdmin):
    list_display = ('started_at', 'mailbox', 'kind', 'dry_run', 'outcome', 'fetched', 'stored',
                    'matched', 'unmatched', 'failed', 'gone', 'errors', 'error_class', 'error_gmail_id')
    list_filter = ('kind', 'outcome', 'dry_run')


@admin.register(MailboxAccessLog)
class MailboxAccessLogAdmin(ReadOnlyAdmin):
    list_display = ('at', 'mailbox', 'purpose', 'actor', 'dry_run', 'api_calls', 'messages_read',
                    'bodies_read', 'finished_at')
    list_filter = ('purpose', 'dry_run')


@admin.register(CapturePurge)
class CapturePurgeAdmin(ReadOnlyAdmin):
    list_display = ('at', 'reason', 'rule', 'mailbox', 'messages', 'copies', 'conversations',
                    'queue_rows', 'remaining')
    list_filter = ('reason', 'remaining')


@admin.register(CaptureSkip)
class CaptureSkipAdmin(ReadOnlyAdmin):
    list_display = ('created_at', 'mailbox', 'gmail_id', 'actor', 'reason', 'used_at')
    list_filter = ('mailbox',)


@admin.register(CaptureFailure)
class CaptureFailureAdmin(ReadOnlyAdmin):
    list_display = ('mailbox', 'gmail_id', 'attempts', 'error', 'parked', 'code_version', 'last_failed_at')
    list_filter = ('parked', 'error', 'mailbox')
    actions = ('unpark',)

    @admin.action(description='Unpark: retry on the next run of the mailbox')
    def unpark(self, request, queryset):
        if not _superuser(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        count = queryset.update(parked=False, attempts=0)
        messages.info(request, f'{count} messages will be retried on the next run.')
