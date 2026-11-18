"""REST API for activities and change proposals (``/api/v1/activities/``, ``/api/v1/change-proposals/``).

Authenticated users only. Writes answer 403 ``not_enabled`` while their switch
is off; reads always work. Accepting or rejecting needs a person signed in to
the website (``agent_inbox.policy.review_refusal``). Agent accounts see only
their own proposals, and other recorders' activity bodies are withheld from
them.
"""
import django_filters
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from agent_inbox import activities as activity_service
from agent_inbox import policy
from agent_inbox import proposals as proposal_service
from agent_inbox.models import (
    ACTIVITY_DIRECTION_CHOICES, ACTIVITY_KIND_CHOICES, PROPOSAL_KIND_CHOICES, PROPOSAL_STATUS_CHOICES,
    PROPOSAL_TARGET_CHOICES, PROPOSER_KIND_CHOICES, SOURCE_SYSTEM_CHOICES, Activity, ChangeProposal,
)
from agent_inbox.serializers import ActivitySerializer, ChangeProposalSerializer
from agent_inbox.validation import ServiceError


def _error(exc):
    return Response(exc.body(), status=exc.status)


def _body(request):
    return request.data


class ActivityFilter(django_filters.FilterSet):
    company = django_filters.UUIDFilter(field_name='company_id')
    contact = django_filters.UUIDFilter(field_name='contact_id')
    contract = django_filters.UUIDFilter(field_name='contract_id')
    quote = django_filters.UUIDFilter(field_name='quote_id')
    opportunity = django_filters.UUIDFilter(field_name='opportunity_id')
    kind = django_filters.MultipleChoiceFilter(choices=ACTIVITY_KIND_CHOICES)
    direction = django_filters.ChoiceFilter(choices=ACTIVITY_DIRECTION_CHOICES)
    source_system = django_filters.ChoiceFilter(choices=SOURCE_SYSTEM_CHOICES)
    source_ref = django_filters.CharFilter()
    recorded_by = django_filters.CharFilter(field_name='recorded_by_username', lookup_expr='iexact')
    occurred_after = django_filters.IsoDateTimeFilter(field_name='occurred_at', lookup_expr='gte')
    occurred_before = django_filters.IsoDateTimeFilter(field_name='occurred_at', lookup_expr='lt')
    include_void = django_filters.BooleanFilter(method='filter_void')

    class Meta:
        model = Activity
        fields = []

    def filter_void(self, queryset, name, value):
        return queryset  # applied in qs, so that leaving it out also hides voided rows

    @property
    def qs(self):
        queryset = super().qs
        if not self.form.cleaned_data.get('include_void'):
            queryset = queryset.filter(is_void=False)
        return queryset


class ActivityViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """List, retrieve, create (idempotent) and void activities."""

    serializer_class = ActivitySerializer
    filterset_class = ActivityFilter
    parser_classes = (JSONParser,)
    ordering_fields = ['occurred_at', 'created_at']
    ordering = ['-occurred_at', '-created_at']
    search_fields = ['summary']

    def get_queryset(self):
        return Activity.objects.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = getattr(self.request, 'user', None)
        if policy.is_agent_account(user):
            context['agent_viewer'] = user
        return context

    def _with_recorders(self, rows):
        context = self.get_serializer_context()
        if 'agent_viewer' in context:
            context['agent_recorder_ids'] = policy.agent_account_ids({row.recorded_by_id for row in rows})
        return ActivitySerializer(rows, many=True, context=context).data

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        rows = list(page if page is not None else queryset)
        data = self._with_recorders(rows)
        return self.get_paginated_response(data) if page is not None else Response(data)

    def retrieve(self, request, *args, **kwargs):
        return Response(self._with_recorders([self.get_object()])[0])

    def create(self, request):
        try:
            activity, replayed = activity_service.record_activity(
                request.user, _body(request), via=policy.recorded_via_for(request))
        except ServiceError as exc:
            return _error(exc)
        data = {**self._with_recorders([activity])[0], 'replayed': replayed}
        return Response(data, status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        try:
            activity = activity_service.void_activity(request.user, pk, _body(request))
        except ServiceError as exc:
            return _error(exc)
        return Response(self._with_recorders([activity])[0])


class ChangeProposalFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=PROPOSAL_STATUS_CHOICES, method='filter_status')
    kind = django_filters.MultipleChoiceFilter(choices=PROPOSAL_KIND_CHOICES)
    target_collection = django_filters.ChoiceFilter(choices=PROPOSAL_TARGET_CHOICES)
    target_id = django_filters.CharFilter()
    company = django_filters.UUIDFilter(field_name='company_id')
    activity = django_filters.UUIDFilter(field_name='activity_id')
    proposer = django_filters.CharFilter(field_name='proposer_username', lookup_expr='iexact')
    proposer_kind = django_filters.ChoiceFilter(choices=PROPOSER_KIND_CHOICES)
    batch_key = django_filters.CharFilter()
    created_after = django_filters.IsoDateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.IsoDateTimeFilter(field_name='created_at', lookup_expr='lt')
    record_changed = django_filters.BooleanFilter(field_name='target_changed_at', lookup_expr='isnull',
                                                  exclude=True)

    class Meta:
        model = ChangeProposal
        fields = []

    def filter_status(self, queryset, name, value):
        # Read-only: an open proposal past its expiry counts as expired here.
        return proposal_service.with_effective_status(queryset, value) if value else queryset


class ChangeProposalViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """List, retrieve and create proposals; accept, accept with edits, reject, reopen, bulk reject.

    Every decision carries the proposal's seen_version from the last read.
    """

    serializer_class = ChangeProposalSerializer
    filterset_class = ChangeProposalFilter
    parser_classes = (JSONParser,)
    ordering_fields = ['created_at', 'expires_at', 'reviewed_at', 'confidence']
    ordering = ['-created_at']
    search_fields = ['rationale', 'evidence_quote', 'company__name']

    def get_queryset(self):
        queryset = ChangeProposal.objects.select_related('company', 'activity')
        user = getattr(self.request, 'user', None)
        if policy.is_agent_account(user):
            queryset = queryset.filter(Q(proposer=user))
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = getattr(self.request, 'user', None)
        if policy.is_agent_account(user):
            context['hide_private_from'] = user.pk
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        rows = list(page if page is not None else queryset)
        proposal_service.refresh_snapshots(rows)
        context = {**self.get_serializer_context(), 'conflicts': proposal_service.conflicts_for(rows)}
        data = ChangeProposalSerializer(rows, many=True, context=context).data
        return self.get_paginated_response(data) if page is not None else Response(data)

    def retrieve(self, request, *args, **kwargs):
        proposal = self.get_object()
        proposal_service.refresh_snapshots([proposal])
        return Response(self.get_serializer(proposal).data)

    def create(self, request):
        try:
            proposal, replayed = proposal_service.create_proposal(request.user, _body(request), via='rest')
        except ServiceError as exc:
            return _error(exc)
        data = {**self.get_serializer(proposal).data, 'replayed': replayed}
        return Response(data, status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        return self._accept(request, pk, with_edits=False)

    @action(detail=True, methods=['post'], url_path='accept-with-edits')
    def accept_with_edits(self, request, pk=None):
        return self._accept(request, pk, with_edits=True)

    def _accept(self, request, pk, with_edits):
        try:
            proposal, reply = proposal_service.accept(request, pk, _body(request), with_edits=with_edits)
        except ServiceError as exc:
            return _error(exc)
        data = {**self.get_serializer(proposal).data, 'apply_result': reply}
        if proposal.kind == 'new_contact':
            data['created_contact_id'] = proposal.applied_record_id
            data['apply_note'] = proposal_service.NEW_CONTACT_INACTIVE_NOTE
        return Response(data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        try:
            proposal = proposal_service.reject(request, pk, _body(request))
        except ServiceError as exc:
            return _error(exc)
        return Response(self.get_serializer(proposal).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        try:
            proposal = proposal_service.reopen(request, pk, _body(request))
        except ServiceError as exc:
            return _error(exc)
        return Response(self.get_serializer(proposal).data)

    @action(detail=False, methods=['post'], url_path='bulk-reject')
    def bulk_reject(self, request):
        try:
            result = proposal_service.bulk_reject(request, _body(request))
        except ServiceError as exc:
            return _error(exc)
        return Response(result)

    @action(detail=False, methods=['get'])
    def allowlist(self, request):
        """What proposals may change, for the review page and for agents."""
        return Response({
            'kinds': {
                kind: {collection: sorted(fields) for collection, fields in targets.items()}
                for kind, targets in policy.PROPOSAL_ALLOWLIST.items()
            },
            'proposals_enabled': policy.proposals_enabled(),
            'activity_writes_enabled': policy.activity_writes_enabled(),
            **policy.account_status(request),
        })
