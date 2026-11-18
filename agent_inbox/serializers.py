"""Read-only representations. Writes go through agent_inbox.activities / .proposals."""
from rest_framework import serializers

from agent_inbox.models import Activity, ChangeProposal


class ActivitySerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    contact_id = serializers.UUIDField(read_only=True, allow_null=True)
    contract_id = serializers.UUIDField(read_only=True, allow_null=True)
    quote_id = serializers.UUIDField(read_only=True, allow_null=True)
    opportunity_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Activity
        fields = [
            'id', 'company_id', 'contact_id', 'contract_id', 'quote_id', 'opportunity_id',
            'kind', 'direction', 'occurred_at', 'summary', 'body', 'participants',
            'source_system', 'source_ref', 'source_url',
            'recorded_by_username', 'recorded_via', 'idempotency_key',
            'is_void', 'void_reason', 'voided_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Bodies and participants of other recorders are withheld from agent
        # accounts, as on the MCP query boundary.
        if self.context.get('hide_private_from') is not None and (
            instance.recorded_by_id != self.context['hide_private_from']
        ):
            data.pop('body', None)
            data.pop('participants', None)
            data.pop('idempotency_key', None)
        return data


class ChangeProposalSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    activity_id = serializers.UUIDField(read_only=True, allow_null=True)
    superseded_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = ChangeProposal
        fields = [
            'id', 'company_id', 'company_name', 'target_collection', 'target_id', 'kind',
            'patch', 'applied_patch', 'current_values', 'expected_version',
            'evidence_quote', 'evidence_verified', 'evidence_source_system', 'evidence_source_ref',
            'evidence_source_url', 'activity_id', 'rationale',
            'proposer_username', 'proposer_kind', 'proposed_via', 'model', 'prompt_version', 'confidence',
            'status', 'fingerprint', 'batch_key', 'reviewer_username', 'reviewed_at', 'decision_note',
            'target_changed_at', 'last_apply_error', 'applied_record_id', 'applied_audit_id',
            'superseded_by_id', 'expires_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
