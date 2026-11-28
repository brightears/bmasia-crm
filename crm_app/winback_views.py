"""Win-back API: churned customers, Claude drafts, approve-to-send, feedback and insights.

Reading and drafting need the Sales or Admin role. Sending (approve) also needs a
person signed in to the website: API tokens and agent accounts are refused, so no
automation can send a win-back email without a human approving it.
"""
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ChurnInsightReport, WinBackCandidate
from .permissions import IsSalesOrAdmin, PersonSignedInToWebsite
from .services import winback_service
from .services.winback_service import WinBackError

PRODUCTS = ('all', 'beatbreeze', 'soundtrack', 'other')


class WinBackCandidateSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    company_industry = serializers.CharField(source='company.industry', read_only=True)
    company_country = serializers.CharField(source='company.country', read_only=True)
    contact_name = serializers.CharField(source='contact.name', read_only=True, default='')
    contact_email = serializers.CharField(source='contact.email', read_only=True, default='')
    contract_number = serializers.CharField(source='churned_contract.contract_number', read_only=True, default='')
    reviewer_name = serializers.SerializerMethodField()
    product_display = serializers.CharField(source='get_product_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    churn_reason_display = serializers.CharField(source='get_churn_reason_display', read_only=True)

    class Meta:
        model = WinBackCandidate
        fields = [
            'id', 'company', 'company_name', 'company_industry', 'company_country',
            'contact', 'contact_name', 'contact_email', 'churned_contract', 'contract_number',
            'product', 'product_display', 'churned_on', 'churn_signal', 'zones', 'annual_value', 'currency',
            'status', 'status_display', 'offer', 'draft_subject', 'draft_body_html', 'personalisation_notes',
            'drafted_at', 'ai_model', 'final_subject', 'final_body_html', 'reviewer', 'reviewer_name',
            'reviewed_at', 'sent_at', 'send_error', 'feedback_text', 'feedback_source', 'feedback_received_at',
            'churn_reason', 'churn_reason_display', 'churn_reason_detail', 'sentiment', 'win_back_likelihood',
            'suggested_next_step', 'outcome_notes', 'closed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [f for f in fields if f not in ('contact', 'outcome_notes')]

    def get_reviewer_name(self, obj):
        return obj.reviewer.get_full_name() or obj.reviewer.username if obj.reviewer else ''

    def validate_contact(self, contact):
        if contact is not None and contact.company_id != self.instance.company_id:
            raise serializers.ValidationError('The contact must belong to the same company.')
        return contact

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if 'contact' in validated_data and instance.status in ('identified', 'needs_contact'):
            instance.status = 'identified' if instance.contact_id else 'needs_contact'
            instance.save(update_fields=['status', 'updated_at'])
        return instance


class ChurnInsightReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChurnInsightReport
        fields = [
            'id', 'window_days', 'product', 'candidate_count', 'feedback_count', 'reason_counts',
            'stats', 'summary', 'plan_markdown', 'ai_model', 'created_at',
        ]
        read_only_fields = fields


def _error(exc, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': str(exc)}, status=code)


def _window(request):
    try:
        days = int(request.data.get('window_days', winback_service.DEFAULT_WINDOW_DAYS))
    except (TypeError, ValueError):
        days = winback_service.DEFAULT_WINDOW_DAYS
    return max(7, min(days, 730))


class WinBackCandidateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                              mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = WinBackCandidateSerializer
    permission_classes = [IsSalesOrAdmin]
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def get_queryset(self):
        qs = WinBackCandidate.objects.select_related(
            'company', 'contact', 'churned_contract', 'reviewer',
        )
        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status__in=params['status'].split(','))
        if params.get('product') and params['product'] != 'all':
            qs = qs.filter(product=params['product'])
        if params.get('open') == 'true':
            qs = qs.filter(status__in=WinBackCandidate.OPEN_STATUSES)
        return qs.order_by('-churned_on')

    def get_permissions(self):
        if self.action in ('approve',):
            return [IsSalesOrAdmin(), PersonSignedInToWebsite()]
        return super().get_permissions()

    @action(detail=False, methods=['post'])
    def scan(self, request):
        """Find customers who left in the window. Creates candidates; sends nothing."""
        product = request.data.get('product', 'all')
        if product not in PRODUCTS:
            return _error(f'product must be one of {", ".join(PRODUCTS)}')
        result = winback_service.scan(window_days=_window(request), product=product)
        return Response({
            'created': len(result['created']),
            'already_listed': result['already_listed'],
            'candidates': WinBackCandidateSerializer(result['created'], many=True).data,
        })

    @action(detail=True, methods=['post'])
    def draft(self, request, pk=None):
        """Ask Claude for a personalised draft. Waits for review; sends nothing."""
        candidate = self.get_object()
        try:
            winback_service.draft_email(
                candidate,
                offer=request.data.get('offer') or None,
                instructions=request.data.get('instructions') or '',
            )
        except WinBackError as exc:
            return _error(exc)
        return Response(WinBackCandidateSerializer(candidate).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Send the draft, as edited by the reviewer. A person must be signed in."""
        candidate = self.get_object()
        try:
            candidate = winback_service.approve_and_send(
                candidate, request.user,
                subject=request.data.get('subject'),
                body_html=request.data.get('body_html'),
            )
        except WinBackError as exc:
            return _error(exc)
        return Response(WinBackCandidateSerializer(candidate).data)

    @action(detail=True, methods=['post'])
    def skip(self, request, pk=None):
        candidate = self.get_object()
        try:
            winback_service.reject(candidate, request.user, note=request.data.get('note', ''))
        except WinBackError as exc:
            return _error(exc)
        return Response(WinBackCandidateSerializer(candidate).data)

    @action(detail=True, methods=['post'])
    def feedback(self, request, pk=None):
        """Record what the customer said (call notes, a forwarded reply); Claude classifies it."""
        candidate = self.get_object()
        source = request.data.get('source', 'manual')
        if source not in ('manual', 'call', 'email_reply'):
            source = 'manual'
        try:
            winback_service.record_feedback(candidate, request.data.get('text', ''), source=source)
        except WinBackError as exc:
            return _error(exc)
        return Response(WinBackCandidateSerializer(candidate).data)

    @action(detail=True, methods=['post'])
    def outcome(self, request, pk=None):
        candidate = self.get_object()
        try:
            winback_service.set_outcome(candidate, request.data.get('outcome', ''), request.data.get('note', ''))
        except WinBackError as exc:
            return _error(exc)
        return Response(WinBackCandidateSerializer(candidate).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        from collections import Counter
        qs = WinBackCandidate.objects.all()
        return Response({
            'by_status': dict(Counter(qs.values_list('status', flat=True))),
            'by_reason': dict(Counter(qs.exclude(churn_reason='unknown').values_list('churn_reason', flat=True))),
            'pending_review': qs.filter(status='pending_review').count(),
            'default_offer': winback_service.default_offer(),
        })


class ChurnInsightReportViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChurnInsightReportSerializer
    permission_classes = [IsSalesOrAdmin]
    queryset = ChurnInsightReport.objects.all()

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Claude analyses why customers left and writes a 5-step improvement plan."""
        product = request.data.get('product', '')
        if product == 'all':
            product = ''
        if product and product not in PRODUCTS:
            return _error(f'product must be one of {", ".join(PRODUCTS)}')
        try:
            report = winback_service.generate_insights(
                window_days=_window(request), product=product, user=request.user,
            )
        except WinBackError as exc:
            return _error(exc)
        return Response(ChurnInsightReportSerializer(report).data, status=status.HTTP_201_CREATED)
