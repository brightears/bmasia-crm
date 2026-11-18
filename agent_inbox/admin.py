"""Read-only admin views. Decisions are made through the API, never in the admin."""
from django.contrib import admin

from agent_inbox.models import Activity, ChangeProposal, ProposalRefusal


class _ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        return {}

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(Activity)
class ActivityAdmin(_ReadOnlyAdmin):
    list_display = ('occurred_at', 'company', 'kind', 'direction', 'summary', 'recorded_by_username', 'is_void')
    list_filter = ('kind', 'direction', 'source_system', 'recorded_via', 'is_void')
    search_fields = ('summary', 'company__name', 'source_ref', 'recorded_by_username')
    date_hierarchy = 'occurred_at'
    list_select_related = ('company',)


@admin.register(ChangeProposal)
class ChangeProposalAdmin(_ReadOnlyAdmin):
    list_display = ('created_at', 'company', 'kind', 'target_collection', 'status', 'proposer_username',
                    'reviewer_username', 'expires_at')
    list_filter = ('status', 'kind', 'target_collection', 'proposer_kind')
    search_fields = ('company__name', 'proposer_username', 'batch_key', 'fingerprint', 'target_id')
    date_hierarchy = 'created_at'
    list_select_related = ('company',)


@admin.register(ProposalRefusal)
class ProposalRefusalAdmin(_ReadOnlyAdmin):
    list_display = ('created_at', 'proposer', 'code')
    list_filter = ('code',)
