"""Read-only representations. Writes go through agent_inbox.activities / .proposals."""
from rest_framework import serializers

from agent_inbox.models import Activity, ChangeProposal

# Withheld from an agent account for activities another recorder made.
PRIVATE_ACTIVITY_FIELDS = ('body', 'participants', 'idempotency_key', 'source_url')


class ActivitySerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    contact_id = serializers.UUIDField(read_only=True, allow_null=True)
    contract_id = serializers.UUIDField(read_only=True, allow_null=True)
    quote_id = serializers.UUIDField(read_only=True, allow_null=True)
    opportunity_id = serializers.UUIDField(read_only=True, allow_null=True)
    duplicate_of_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Activity
        fields = [
            'id', 'company_id', 'contact_id', 'contract_id', 'quote_id', 'opportunity_id',
            'kind', 'direction', 'occurred_at', 'summary', 'body', 'participants',
            'source_system', 'source_ref', 'source_url',
            'recorded_by_username', 'recorded_via', 'idempotency_key',
            'is_void', 'void_reason', 'voided_at', 'duplicate_of_id', 'is_redacted',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Bodies, participants, keys and links of other recorders are withheld
        # from agent accounts, as on the MCP query boundary.
        if self.context.get('hide_private_from') is not None and (
            instance.recorded_by_id != self.context['hide_private_from']
        ):
            for name in PRIVATE_ACTIVITY_FIELDS:
                data.pop(name, None)
        return data


def evidence_state(proposal):
    """verified_captured | verified_agent_recorded | unverified.

    Verified means the quote was found in the linked activity's stored body and
    that activity is still live. Captured means the activity was recorded by an
    account that is not an agent (a capture job or a person); agent-recorded
    means an agent wrote that body.
    """
    activity = proposal.activity
    if not proposal.evidence_verified or activity is None or activity.is_void:
        return 'unverified'
    return 'verified_agent_recorded' if proposal.evidence_recorder_is_agent else 'verified_captured'


class ChangeProposalSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    activity_id = serializers.UUIDField(read_only=True, allow_null=True)
    superseded_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    seen_version = serializers.SerializerMethodField()
    evidence = serializers.SerializerMethodField()
    evidence_recorded_by = serializers.SerializerMethodField()
    evidence_recorded_via = serializers.SerializerMethodField()
    conflicts_with = serializers.SerializerMethodField()

    class Meta:
        model = ChangeProposal
        fields = [
            'id', 'seen_version', 'company_id', 'company_name', 'target_collection', 'target_id', 'kind',
            'patch', 'applied_patch', 'current_values', 'expected_version',
            'evidence', 'evidence_quote', 'evidence_verified', 'evidence_source_system', 'evidence_source_ref',
            'evidence_source_url', 'evidence_occurred_at', 'activity_id', 'evidence_recorded_by',
            'evidence_recorded_via', 'evidence_recorder_is_agent', 'rationale',
            'proposer_username', 'proposer_kind', 'proposed_via', 'model', 'prompt_version', 'confidence',
            'status', 'fingerprint', 'batch_key', 'reviewer_username', 'reviewed_at', 'decision_note',
            'history', 'conflicts_with', 'target_changed_at', 'last_apply_error', 'applied_record_id',
            'applied_audit_id', 'superseded_by_id', 'expires_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_seen_version(self, proposal):
        from agent_inbox.proposals import seen_version
        return seen_version(proposal)

    def get_evidence(self, proposal):
        return evidence_state(proposal)

    def get_evidence_recorded_by(self, proposal):
        return proposal.activity.recorded_by_username if proposal.activity else None

    def get_evidence_recorded_via(self, proposal):
        return proposal.activity.recorded_via if proposal.activity else None

    def get_conflicts_with(self, proposal):
        from agent_inbox.proposals import conflicts_for

        index = self.context.get('conflicts')
        if index is None:
            index = conflicts_for([proposal])
        own_only = self.context.get('hide_private_from')
        return [
            {
                'id': str(other.pk), 'proposer_username': other.proposer_username,
                'patch': {key: value for key, value in (other.patch or {}).items() if key in (proposal.patch or {})},
                'evidence_occurred_at': other.evidence_occurred_at, 'created_at': other.created_at,
            }
            for other in index.get(proposal.pk, [])
            if own_only is None or other.proposer_id == own_only
        ]
