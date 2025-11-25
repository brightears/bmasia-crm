from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth import login, logout
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.management import call_command
import csv
import json
import os

from .models import (
    User, Company, Contact, Note, Task, AuditLog,
    Opportunity, OpportunityActivity, Contract, Invoice, ContractZone,
    Quote, QuoteLineItem, QuoteAttachment, QuoteActivity,
    EmailTemplate, EmailSequence, SequenceStep, SequenceEnrollment, SequenceStepExecution,
    CustomerSegment, EmailCampaign, CampaignRecipient,
    Ticket, TicketComment, TicketAttachment,
    KBCategory, KBTag, KBArticle, KBArticleView, KBArticleRating,
    KBArticleRelation, KBArticleAttachment, TicketKBArticle,
    Zone, Device
)
from .serializers import (
    UserSerializer, CompanySerializer, ContactSerializer, NoteSerializer,
    TaskSerializer, OpportunitySerializer, OpportunityActivitySerializer,
    ContractSerializer, ContractZoneSerializer, InvoiceSerializer, AuditLogSerializer,
    LoginSerializer, DashboardStatsSerializer, BulkOperationSerializer,
    QuoteSerializer, QuoteLineItemSerializer, QuoteAttachmentSerializer, QuoteActivitySerializer,
    EmailTemplateSerializer, EmailSequenceSerializer, SequenceStepSerializer,
    SequenceEnrollmentSerializer, SequenceStepExecutionSerializer,
    CustomerSegmentSerializer, TicketSerializer, TicketCommentSerializer, TicketAttachmentSerializer,
    KBCategorySerializer, KBTagSerializer, KBArticleSerializer, KBArticleListSerializer,
    KBArticleViewSerializer, KBArticleRatingSerializer, KBArticleRelationSerializer,
    KBArticleAttachmentSerializer, TicketKBArticleSerializer,
    ZoneSerializer, DeviceSerializer
)
from .permissions import (
    RoleBasedPermission, DepartmentPermission, CompanyAccessPermission,
    TaskAssigneePermission, ReadOnlyForNonOwner
)


class BaseModelViewSet(viewsets.ModelViewSet):
    """Base viewset with common functionality"""
    permission_classes = [AllowAny]  # Disabled auth for development
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    def get_queryset(self):
        """Override to apply role-based filtering"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # For development: if no authenticated user, return all
        if not user.is_authenticated:
            return queryset
        
        # Admin sees everything
        if user.role == 'Admin':
            return queryset
        
        # Apply role-based filtering
        # TEMPORARILY DISABLED for development - all authenticated users see all data
        # TODO: Re-enable role-based filtering in production
        # if user.role == 'Sales':
        #     # Sales sees companies they have opportunities for
        #     if self.basename == 'company':
        #         company_ids = Opportunity.objects.filter(owner=user).values_list('company_id', flat=True)
        #         return queryset.filter(Q(id__in=company_ids) | Q(opportunities__owner=user)).distinct()

        return queryset
    
    def perform_create(self, serializer):
        """Add audit logging on create"""
        instance = serializer.save()
        self.log_action('CREATE', instance)
    
    def perform_update(self, serializer):
        """Add audit logging on update"""
        old_instance = self.get_object()
        old_data = self.get_serializer(old_instance).data
        
        instance = serializer.save()
        new_data = self.get_serializer(instance).data
        
        changes = {}
        for key, new_value in new_data.items():
            old_value = old_data.get(key)
            if old_value != new_value:
                changes[key] = {'old': old_value, 'new': new_value}
        
        self.log_action('UPDATE', instance, changes)
    
    def perform_destroy(self, instance):
        """Add audit logging on delete"""
        self.log_action('DELETE', instance)
        instance.delete()
    
    def log_action(self, action, instance, changes=None):
        """Create audit log entry"""
        request = self.request
        AuditLog.objects.create(
            user=request.user,
            action=action,
            model_name=instance.__class__.__name__,
            record_id=str(instance.pk),
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            changes=changes,
            additional_data={
                'timestamp': timezone.now().isoformat(),
                'view': self.__class__.__name__
            }
        )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=False, methods=['post'])
    def bulk_operations(self, request):
        """Handle bulk operations on multiple records"""
        serializer = BulkOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action_type = serializer.validated_data['action']
        ids = serializer.validated_data['ids']
        data = serializer.validated_data.get('data', {})
        
        # Get queryset filtered by IDs
        queryset = self.get_queryset().filter(id__in=ids)
        
        if action_type == 'delete':
            count = queryset.count()
            for obj in queryset:
                self.log_action('DELETE', obj)
            queryset.delete()
            return Response({'message': f'{count} records deleted'})
        
        elif action_type == 'update_status':
            count = queryset.update(**data)
            return Response({'message': f'{count} records updated'})
        
        elif action_type == 'assign':
            if 'assigned_to' in data:
                count = queryset.update(assigned_to_id=data['assigned_to'])
                return Response({'message': f'{count} records assigned'})
        
        elif action_type == 'export':
            return self.export_csv(queryset)
        
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
    
    def export_csv(self, queryset):
        """Export queryset to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.basename}_export.csv"'
        
        writer = csv.writer(response)
        
        # Get field names from serializer
        serializer = self.get_serializer(queryset.first())
        headers = list(serializer.data.keys())
        writer.writerow(headers)
        
        # Write data rows
        for obj in queryset:
            serializer = self.get_serializer(obj)
            row = [str(value) for value in serializer.data.values()]
            writer.writerow(row)
        
        return response


class UserViewSet(BaseModelViewSet):
    """ViewSet for User management"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['username', 'email', 'date_joined']
    ordering = ['-date_joined']


class CompanyViewSet(BaseModelViewSet):
    """ViewSet for Company management with enhanced features"""
    queryset = Company.objects.all().prefetch_related(
        'contacts',
        'zones',
        'opportunities',
        'contracts'
    )
    serializer_class = CompanySerializer
    search_fields = ['name', 'website', 'notes', 'country']
    ordering_fields = ['name', 'created_at', 'industry', 'country']
    ordering = ['name']
    # Inherits permission_classes = [AllowAny] from BaseModelViewSet for development
    filterset_fields = ['industry', 'is_active', 'country']

    def get_queryset(self):
        """Override to dynamically optimize queryset based on action"""
        queryset = super().get_queryset()

        # For list action, optimize for serialization
        if self.action == 'list':
            # Prefetch related objects that are used in the serializer
            queryset = queryset.prefetch_related(
                'contacts',
                'zones',
                'opportunities',
                'contracts'
            )
        elif self.action == 'retrieve':
            # For detail view, include even more related data
            queryset = queryset.prefetch_related(
                'contacts',
                'zones',
                'opportunities',
                'opportunities__activities',
                'contracts',
                'contracts__invoices',
                'tasks'
            )

        return queryset

    def list(self, request, *args, **kwargs):
        """Override list method to add error handling"""
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            # Log the actual Python exception for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in CompanyViewSet.list(): {type(e).__name__}: {str(e)}", exc_info=True)

            # Return meaningful error response instead of 500
            return Response(
                {
                    'error': 'Failed to retrieve companies',
                    'detail': str(e),
                    'type': type(e).__name__
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """Get company dashboard data"""
        company = self.get_object()
        
        # Get related statistics
        opportunities = company.opportunities.filter(is_active=True)
        contracts = company.contracts.filter(is_active=True)
        tasks = company.tasks.all()
        
        dashboard_data = {
            'company': self.get_serializer(company).data,
            'stats': {
                'opportunities_count': opportunities.count(),
                'opportunities_value': opportunities.aggregate(Sum('expected_value'))['expected_value__sum'] or 0,
                'contracts_count': contracts.count(),
                'contracts_value': contracts.aggregate(Sum('value'))['value__sum'] or 0,
                'open_tasks': tasks.filter(status__in=['Pending', 'In Progress']).count(),
                'overdue_tasks': sum(1 for task in tasks if task.is_overdue),
            },
            'recent_activities': self.get_recent_activities(company),
            'upcoming_tasks': self.get_upcoming_tasks(company),
        }
        
        return Response(dashboard_data)
    
    def get_recent_activities(self, company):
        """Get recent activities for a company"""
        activities = []
        
        # Recent notes
        recent_notes = company.company_notes.all()[:5]
        for note in recent_notes:
            activities.append({
                'type': 'note',
                'title': note.title or 'Note added',
                'date': note.created_at,
                'user': note.author.get_full_name() if note.author else 'Unknown'
            })
        
        # Recent opportunity activities
        for opp in company.opportunities.all()[:3]:
            recent_activities = opp.activities.all()[:2]
            for activity in recent_activities:
                activities.append({
                    'type': 'opportunity_activity',
                    'title': f"{activity.activity_type}: {activity.subject}",
                    'date': activity.created_at,
                    'user': activity.user.get_full_name() if activity.user else 'Unknown'
                })
        
        # Sort by date and return top 10
        activities.sort(key=lambda x: x['date'], reverse=True)
        return activities[:10]
    
    def get_upcoming_tasks(self, company):
        """Get upcoming tasks for a company"""
        upcoming = company.tasks.filter(
            status__in=['Pending', 'In Progress'],
            due_date__gte=timezone.now().date()
        ).order_by('due_date')[:5]

        return TaskSerializer(upcoming, many=True).data

    @action(detail=False, methods=['get'])
    def debug(self, request):
        """Debug endpoint to find problematic companies"""
        import logging
        logger = logging.getLogger(__name__)

        results = {
            'total_companies': 0,
            'serialization_errors': [],
            'successful': [],
            'error_summary': {}
        }

        companies = Company.objects.all()
        results['total_companies'] = companies.count()

        for company in companies:
            try:
                # Try to serialize this specific company
                serializer = CompanySerializer(company)
                data = serializer.data
                results['successful'].append({
                    'id': str(company.id),
                    'name': company.name
                })
            except Exception as e:
                error_info = {
                    'id': str(company.id),
                    'name': company.name,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'industry': company.industry,
                    'country': company.country,
                }
                results['serialization_errors'].append(error_info)
                logger.error(f"Company {company.id} ({company.name}) serialization failed: {str(e)}")

                # Track error types
                error_type = type(e).__name__
                if error_type not in results['error_summary']:
                    results['error_summary'][error_type] = 0
                results['error_summary'][error_type] += 1

        return Response(results)


class ContactViewSet(BaseModelViewSet):
    """ViewSet for Contact management"""
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    search_fields = ['name', 'email', 'phone', 'title', 'company__name']
    ordering_fields = ['name', 'email', 'created_at', 'last_contacted']
    ordering = ['name']
    filterset_fields = ['company', 'contact_type', 'is_primary', 'is_active']


class NoteViewSet(BaseModelViewSet):
    """ViewSet for Note management"""
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    search_fields = ['title', 'text', 'tags']
    ordering_fields = ['created_at', 'priority', 'note_type']
    ordering = ['-created_at']
    filterset_fields = ['company', 'note_type', 'priority', 'is_private']
    
    def get_queryset(self):
        """Filter private notes based on user permissions"""
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.role != 'Admin':
            # Non-admin users can't see private notes from others
            queryset = queryset.filter(
                Q(is_private=False) | Q(author=user)
            )
        
        return queryset


class TaskViewSet(BaseModelViewSet):
    """ViewSet for Task management"""
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    search_fields = ['title', 'description', 'tags']
    ordering_fields = ['created_at', 'due_date', 'priority', 'status']
    ordering = ['-priority', 'due_date']
    permission_classes = [IsAuthenticated, TaskAssigneePermission]
    filterset_fields = ['company', 'assigned_to', 'priority', 'status', 'department']
    
    @action(detail=False, methods=['get'])
    def my_tasks(self, request):
        """Get tasks assigned to current user"""
        tasks = self.get_queryset().filter(assigned_to=request.user)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue tasks"""
        overdue_tasks = [task for task in self.get_queryset() if task.is_overdue]
        serializer = self.get_serializer(overdue_tasks, many=True)
        return Response(serializer.data)


class OpportunityViewSet(BaseModelViewSet):
    """ViewSet for Opportunity management"""
    queryset = Opportunity.objects.all()
    serializer_class = OpportunitySerializer
    search_fields = ['name', 'company__name', 'notes']
    ordering_fields = ['created_at', 'expected_value', 'expected_close_date', 'stage']
    ordering = ['-expected_value', 'expected_close_date']
    filterset_fields = ['company', 'stage', 'owner', 'lead_source', 'is_active']
    
    def get_queryset(self):
        """Filter opportunities based on user role"""
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.role == 'Sales':
            # Sales users only see their own opportunities
            return queryset.filter(owner=user)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def pipeline(self, request):
        """Get sales pipeline data"""
        queryset = self.get_queryset().filter(is_active=True)
        
        pipeline_data = {}
        for stage, _ in Opportunity.STAGE_CHOICES:
            stage_opps = queryset.filter(stage=stage)
            pipeline_data[stage] = {
                'count': stage_opps.count(),
                'value': stage_opps.aggregate(Sum('expected_value'))['expected_value__sum'] or 0,
                'weighted_value': sum(opp.weighted_value for opp in stage_opps),
                'opportunities': OpportunitySerializer(stage_opps[:5], many=True).data
            }
        
        return Response(pipeline_data)
    
    @action(detail=True, methods=['post'])
    def advance_stage(self, request, pk=None):
        """Advance opportunity to next stage"""
        opportunity = self.get_object()
        
        stage_order = [choice[0] for choice in Opportunity.STAGE_CHOICES]
        current_index = stage_order.index(opportunity.stage)
        
        if current_index < len(stage_order) - 1:
            opportunity.stage = stage_order[current_index + 1]
            opportunity.save()
            
            self.log_action('UPDATE', opportunity, {
                'stage': {'old': stage_order[current_index], 'new': opportunity.stage}
            })
            
            return Response({'message': f'Opportunity advanced to {opportunity.stage}'})
        
        return Response({'error': 'Opportunity is already at final stage'}, 
                       status=status.HTTP_400_BAD_REQUEST)


class OpportunityActivityViewSet(BaseModelViewSet):
    """ViewSet for OpportunityActivity management"""
    queryset = OpportunityActivity.objects.all()
    serializer_class = OpportunityActivitySerializer
    search_fields = ['subject', 'description', 'outcome']
    ordering_fields = ['created_at', 'activity_type']
    ordering = ['-created_at']
    filterset_fields = ['opportunity', 'activity_type', 'user']


class ContractViewSet(BaseModelViewSet):
    """ViewSet for Contract management"""
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    search_fields = ['contract_number', 'company__name']
    ordering_fields = ['created_at', 'start_date', 'end_date', 'value']
    ordering = ['-start_date']
    filterset_fields = ['company', 'contract_type', 'status', 'auto_renew', 'is_active']
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get contracts expiring within 30 days"""
        expiring = [contract for contract in self.get_queryset() if contract.is_expiring_soon]
        serializer = self.get_serializer(expiring, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Send contract via email with PDF attachment"""
        from crm_app.services.email_service import EmailService

        contract = self.get_object()
        email_service = EmailService()

        # Extract email parameters from request
        recipients = request.data.get('recipients', [])
        subject = request.data.get('subject')
        body = request.data.get('body')

        # Send email via EmailService (passes request for per-user SMTP)
        success, message = email_service.send_contract_email(
            contract_id=contract.id,
            recipients=recipients if recipients else None,
            subject=subject if subject else None,
            body=body if body else None,
            sender='admin',  # Legacy parameter, will use request.user
            request=request   # Critical for per-user SMTP authentication
        )

        if not success:
            return Response(
                {'error': message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Email service updates the status, refresh from DB
        contract.refresh_from_db()

        self.log_action('UPDATE', contract, {
            'status': {'old': contract.status, 'new': 'Sent'},
            'action': 'Email sent',
            'recipients': recipients
        })

        return Response({
            'message': message,
            'status': contract.status
        })

    @action(detail=True, methods=['post'])
    def send_renewal_notice(self, request, pk=None):
        """Mark renewal notice as sent"""
        contract = self.get_object()
        contract.renewal_notice_sent = True
        contract.renewal_notice_date = timezone.now().date()
        contract.save()

        self.log_action('UPDATE', contract, {
            'renewal_notice_sent': {'old': False, 'new': True}
        })

        return Response({'message': 'Renewal notice marked as sent'})

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Generate and download PDF for contract"""
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from io import BytesIO
        from django.conf import settings
        import os

        contract = self.get_object()
        company = contract.company

        # Get entity-specific details based on billing_entity
        billing_entity = company.billing_entity
        if billing_entity == 'BMAsia (Thailand) Co., Ltd.':
            entity_name = 'BMAsia (Thailand) Co., Ltd.'
            entity_address = '725 S-Metro Building, Suite 144, Level 20, Sukhumvit Road, Klongtan Nuea Watthana, Bangkok 10110, Thailand'
            entity_phone = '+66 2153 3520'
            entity_tax = '0105548025073'
            entity_bank = 'TMBThanachart Bank, Thonglor Soi 17 Branch'
            entity_swift = 'TMBKTHBK'
            entity_account = '916-1-00579-9'
            payment_terms_default = 'by bank transfer on a net received, paid in full basis, with no offset to BMA\'s TMB-Thanachart Bank, Bangkok, Thailand due immediately on invoicing to activate the music subscription. All outbound and inbound bank transfer fees are borne by the Client in remitting payments as invoiced less Withholding Tax required by Thai Law.'
        else:  # BMAsia Limited (Hong Kong)
            entity_name = 'BMAsia Limited'
            entity_address = '22nd Floor, Tai Yau Building, 181 Johnston Road, Wanchai, Hong Kong'
            entity_phone = '+66 2153 3520'
            entity_tax = None
            entity_bank = 'HSBC, HK'
            entity_swift = 'HSBCHKHHHKH'
            entity_account = '808-021570-838'
            payment_terms_default = 'by bank transfer on a net received, paid in full basis, with no offset to BMA\'s HSBC Bank, Hong Kong due immediately as invoiced to activate the music subscription. All Bank transfer fees, and all taxes are borne by the Client in remitting payments as invoiced.'

        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.4*inch, bottomMargin=0.4*inch)

        # Container for PDF elements
        elements = []
        styles = getSampleStyleSheet()

        # Custom styles - Modern 2025 design
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#424242'),
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#424242'),
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#424242'),
            leading=14
        )

        small_style = ParagraphStyle(
            'SmallText',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#757575'),
            leading=11
        )

        # Header - BMAsia Logo (properly sized with aspect ratio preserved)
        logo_path = os.path.join(settings.BASE_DIR, 'crm_app', 'static', 'crm_app', 'images', 'bmasia_logo.png')
        try:
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=160, height=64, kind='proportional')
                logo.hAlign = 'LEFT'
                elements.append(logo)
            else:
                # Fallback to text if logo not found
                elements.append(Paragraph("BM ASIA", title_style))
        except Exception:
            # Fallback to text if image loading fails
            elements.append(Paragraph("BM ASIA", title_style))

        # Orange accent line
        elements.append(Spacer(1, 0.1*inch))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#FFA500'), spaceBefore=0, spaceAfter=0))
        elements.append(Spacer(1, 0.2*inch))

        # Contract title with orange color
        contract_title_style = ParagraphStyle(
            'ContractTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#FFA500'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("CONTRACT AGREEMENT", contract_title_style))

        # Document metadata table (modern grid layout)
        metadata_data = [
            ['Contract Number', 'Date', 'Status', 'Validity'],
            [contract.contract_number,
             contract.start_date.strftime('%b %d, %Y'),
             contract.status,
             f"{contract.start_date.strftime('%b %d, %Y')} - {contract.end_date.strftime('%b %d, %Y')}"]
        ]

        metadata_table = Table(metadata_data, colWidths=[1.7*inch, 1.7*inch, 1.7*inch, 1.8*inch])
        metadata_table.setStyle(TableStyle([
            # Header row - orange background
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFA500')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),

            # Data row
            ('FONT', (0, 1), (-1, 1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#424242')),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('TOPPADDING', (0, 1), (-1, 1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 10),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(metadata_table)
        elements.append(Spacer(1, 0.2*inch))

        # Two-column From/Bill To section
        from_bill_data = [
            [Paragraph('<b>FROM:</b>', heading_style), Paragraph('<b>BILL TO:</b>', heading_style)],
            [
                Paragraph(f"""
                <b>{entity_name}</b><br/>
                {entity_address.replace(', ', '<br/>')}<br/>
                Phone: {entity_phone}
                {f"<br/>Tax No.: {entity_tax}" if entity_tax else ""}
                """, body_style),
                Paragraph(f"""
                <b>{company.legal_entity_name or company.name}</b><br/>
                {company.full_address.replace(', ', '<br/>') if company.full_address else (company.country or '')}
                """, body_style)
            ]
        ]

        from_bill_table = Table(from_bill_data, colWidths=[3.45*inch, 3.45*inch])
        from_bill_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, 1), 6),
        ]))
        elements.append(from_bill_table)
        elements.append(Spacer(1, 0.2*inch))

        # Service Details Section
        elements.append(Paragraph("SERVICE DETAILS", heading_style))

        service_details_text = f"<b>Service Type:</b> {contract.get_service_type_display() if contract.service_type else 'Professional Services'}<br/>"
        service_details_text += f"<b>Contract Type:</b> {contract.get_contract_type_display()}<br/>"
        if contract.billing_frequency:
            service_details_text += f"<b>Billing Frequency:</b> {contract.billing_frequency}"

        elements.append(Paragraph(service_details_text, body_style))
        elements.append(Spacer(1, 0.3*inch))

        # Contract Value Section - Modern card-style layout
        elements.append(Paragraph("CONTRACT VALUE", heading_style))

        # Currency symbol
        currency_symbol = {'USD': '$', 'THB': 'THB ', 'EUR': 'EUR ', 'GBP': 'GBP '}.get(contract.currency, contract.currency + ' ')

        value_data = [
            ['Total Contract Value', f"{currency_symbol}{contract.value:,.2f} {contract.currency}"]
        ]

        if contract.discount_percentage > 0:
            value_data.append(['Discount Applied', f"{contract.discount_percentage}%"])

        if contract.monthly_value > 0:
            value_data.append(['Monthly Value', f"{currency_symbol}{contract.monthly_value:,.2f}"])

        value_table = Table(value_data, colWidths=[3.45*inch, 3.45*inch])
        value_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
            ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(value_table)
        elements.append(Spacer(1, 0.3*inch))

        # Terms Section - Modern table layout
        elements.append(Paragraph("CONTRACT TERMS", heading_style))

        terms_data = [
            ['Contract Period', f"{contract.start_date.strftime('%B %d, %Y')} to {contract.end_date.strftime('%B %d, %Y')}"],
            ['Billing Frequency', contract.billing_frequency or 'One-time'],
            ['Auto-Renewal', 'Yes' if contract.auto_renew else 'No'],
        ]

        if contract.auto_renew:
            terms_data.append(['Renewal Period', f"{contract.renewal_period_months} months"])

        terms_table = Table(terms_data, colWidths=[3.45*inch, 3.45*inch])
        terms_table.setStyle(TableStyle([
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
            ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(terms_table)
        elements.append(Spacer(1, 0.3*inch))

        # Bank Details Section - Organized blocks with background
        elements.append(Paragraph("BANK DETAILS FOR PAYMENT", heading_style))

        bank_data = [
            ['Beneficiary', entity_name],
            ['Bank', entity_bank],
            ['SWIFT Code', entity_swift],
            ['Account Number', entity_account],
        ]

        bank_table = Table(bank_data, colWidths=[2*inch, 4.9*inch])
        bank_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
            ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(bank_table)
        elements.append(Spacer(1, 0.15*inch))

        # Payment Terms
        elements.append(Paragraph("PAYMENT TERMS", heading_style))

        # Use contract payment terms if specified, otherwise use entity default
        payment_terms_text = contract.payment_terms if contract.payment_terms else payment_terms_default
        payment_terms_formatted = payment_terms_text.replace('\n', '<br/>')

        elements.append(Paragraph(payment_terms_formatted, body_style))
        elements.append(Spacer(1, 0.3*inch))

        # Additional Terms and Conditions
        if contract.notes:
            elements.append(Paragraph("ADDITIONAL TERMS AND CONDITIONS", heading_style))

            # Handle multi-line notes
            notes_text = contract.notes.replace('\n', '<br/>')
            elements.append(Paragraph(notes_text, body_style))
            elements.append(Spacer(1, 0.3*inch))

        # Contract Status Indicator
        if contract.status == 'Active':
            status_style = ParagraphStyle(
                'ActiveStatus',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#2e7d32'),
                alignment=TA_CENTER,
                spaceBefore=12,
                spaceAfter=12
            )
            elements.append(Paragraph("<b>✓ ACTIVE CONTRACT</b>", status_style))
        elif contract.status == 'Expired':
            expired_style = ParagraphStyle(
                'ExpiredStatus',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#c62828'),
                alignment=TA_CENTER,
                spaceBefore=12,
                spaceAfter=12
            )
            elements.append(Paragraph("<b>⚠ EXPIRED</b>", expired_style))
        elif contract.status == 'Signed':
            signed_style = ParagraphStyle(
                'SignedStatus',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#1976d2'),
                alignment=TA_CENTER,
                spaceBefore=12,
                spaceAfter=12
            )
            elements.append(Paragraph("<b>✓ SIGNED</b>", signed_style))

        elements.append(Spacer(1, 0.3*inch))

        # Signatures Section
        elements.append(Paragraph("SIGNATURES", heading_style))
        elements.append(Spacer(1, 0.2*inch))

        # Create signature table
        signature_data = [
            ['', ''],
            ['_' * 40, '_' * 40],
            [entity_name, company.name],
            ['Authorized Representative', 'Authorized Representative'],
            ['', ''],
            ['Date: _________________', 'Date: _________________'],
        ]

        signature_table = Table(signature_data, colWidths=[3.45*inch, 3.45*inch])
        signature_table.setStyle(TableStyle([
            ('FONT', (0, 1), (-1, 1), 'Helvetica', 10),
            ('FONT', (0, 2), (-1, 3), 'Helvetica-Bold', 10),
            ('FONT', (0, 5), (-1, 5), 'Helvetica', 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(signature_table)
        elements.append(Spacer(1, 0.3*inch))

        # Footer - entity-specific with separator
        elements.append(Spacer(1, 0.15*inch))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0'), spaceBefore=0, spaceAfter=8))

        footer_text = f"""
        <b>{entity_name}</b> | {entity_address.replace(', ', ' | ')} | Phone: {entity_phone}
        """
        elements.append(Paragraph(footer_text, small_style))

        # Build PDF
        doc.build(elements)

        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()

        # Create response
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Contract_{contract.contract_number}.pdf"'

        # Log activity
        self.log_action('VIEW', contract, {
            'action': 'PDF generated and downloaded',
            'contract_number': contract.contract_number,
            'status': contract.status
        })

        return response

    @action(detail=True, methods=['post'], url_path='add-zones')
    def add_zones(self, request, pk=None):
        """
        Add zones to a contract (create new zones OR link existing zones).

        POST /api/v1/contracts/{id}/add-zones/
        Body: {
            "zones": [
                {"name": "Pool Bar", "platform": "soundtrack"},  # Creates new zone
                {"id": "existing-zone-uuid"},  # Links existing zone
            ]
        }

        Returns: List of created/linked zones
        """
        contract = self.get_object()
        zones_data = request.data.get('zones', [])

        if not zones_data:
            return Response(
                {'error': 'No zones provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_zones = []
        errors = []

        with transaction.atomic():
            for i, zone_data in enumerate(zones_data):
                try:
                    # Check if linking existing zone (has 'id') or creating new zone
                    if 'id' in zone_data:
                        # Link existing zone
                        try:
                            zone = Zone.objects.get(id=zone_data['id'])
                        except Zone.DoesNotExist:
                            errors.append(f"Zone {i+1}: Zone with id {zone_data['id']} not found")
                            continue
                    else:
                        # Create new zone
                        if 'name' not in zone_data or 'platform' not in zone_data:
                            errors.append(f"Zone {i+1}: Missing required fields 'name' or 'platform'")
                            continue

                        zone = Zone.objects.create(
                            company=contract.company,
                            name=zone_data['name'],
                            platform=zone_data['platform'],
                            status='pending',  # Default status for new zones
                            notes=zone_data.get('notes', '')
                        )

                    # Check if zone already linked to this contract
                    existing_link = ContractZone.objects.filter(
                        contract=contract,
                        zone=zone,
                        is_active=True
                    ).exists()

                    if existing_link:
                        errors.append(f"Zone {i+1}: Zone '{zone.name}' already linked to this contract")
                        continue

                    # Create ContractZone link
                    ContractZone.objects.create(
                        contract=contract,
                        zone=zone,
                        start_date=contract.start_date,
                        is_active=True,
                        notes=zone_data.get('notes', '')
                    )

                    created_zones.append(zone)

                except Exception as e:
                    errors.append(f"Zone {i+1}: {str(e)}")

        # Prepare response
        if errors:
            response_data = {
                'zones': ZoneSerializer(created_zones, many=True).data,
                'errors': errors,
                'success_count': len(created_zones),
                'error_count': len(errors)
            }
            return Response(response_data, status=status.HTTP_207_MULTI_STATUS)

        return Response(
            ZoneSerializer(created_zones, many=True).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'], url_path='zones')
    def get_zones(self, request, pk=None):
        """
        Get all zones (active and historical) for this contract.

        GET /api/v1/contracts/{id}/zones/
        Query params:
        - active: true/false (filter by is_active)
        - as_of: YYYY-MM-DD (get zones active on specific date)

        Returns: List of ContractZone relationships
        """
        contract = self.get_object()

        # Filter by active status if specified
        active_filter = request.query_params.get('active')
        if active_filter is not None:
            is_active = active_filter.lower() == 'true'
            queryset = contract.contract_zones.filter(is_active=is_active)
        else:
            queryset = contract.contract_zones.all()

        # Filter by date if specified
        as_of_date = request.query_params.get('as_of')
        if as_of_date:
            from datetime import datetime
            date_obj = datetime.strptime(as_of_date, '%Y-%m-%d').date()
            queryset = queryset.filter(
                start_date__lte=date_obj
            ).filter(
                Q(end_date__gte=date_obj) | Q(end_date__isnull=True)
            )

        queryset = queryset.select_related('zone', 'contract').order_by('-start_date')
        serializer = ContractZoneSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='remove-zone')
    def remove_zone(self, request, pk=None):
        """
        Remove a zone from this contract (set end_date and is_active=False).

        POST /api/v1/contracts/{id}/remove-zone/
        Body: {"zone_id": "uuid"}

        Returns: Updated ContractZone relationship
        """
        contract = self.get_object()
        zone_id = request.data.get('zone_id')

        if not zone_id:
            return Response(
                {'error': 'zone_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            contract_zone = ContractZone.objects.get(
                contract=contract,
                zone_id=zone_id,
                is_active=True
            )
        except ContractZone.DoesNotExist:
            return Response(
                {'error': 'Active zone link not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Close the relationship
        contract_zone.end_date = timezone.now().date()
        contract_zone.is_active = False
        contract_zone.save()

        return Response(
            ContractZoneSerializer(contract_zone).data,
            status=status.HTTP_200_OK
        )


class InvoiceViewSet(BaseModelViewSet):
    """ViewSet for Invoice management"""
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    search_fields = ['invoice_number', 'contract__company__name']
    ordering_fields = ['created_at', 'issue_date', 'due_date', 'total_amount']
    ordering = ['-issue_date']
    filterset_fields = ['contract', 'status', 'issue_date', 'due_date']

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue invoices"""
        overdue = [invoice for invoice in self.get_queryset() if invoice.is_overdue]
        serializer = self.get_serializer(overdue, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Send invoice via email with PDF attachment"""
        from crm_app.services.email_service import EmailService

        invoice = self.get_object()
        email_service = EmailService()

        # Extract email parameters from request
        recipients = request.data.get('recipients', [])
        subject = request.data.get('subject')
        body = request.data.get('body')

        # Send email via EmailService (passes request for per-user SMTP)
        success, message = email_service.send_invoice_email(
            invoice_id=invoice.id,
            recipients=recipients if recipients else None,
            subject=subject if subject else None,
            body=body if body else None,
            sender='admin',  # Legacy parameter, will use request.user
            request=request   # Critical for per-user SMTP authentication
        )

        if not success:
            return Response(
                {'error': message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Email service updates the status, refresh from DB
        invoice.refresh_from_db()

        self.log_action('UPDATE', invoice, {
            'status': {'old': invoice.status, 'new': 'Sent'},
            'action': 'Email sent',
            'recipients': recipients
        })

        return Response({
            'message': message,
            'status': invoice.status
        })

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark invoice as paid"""
        invoice = self.get_object()
        invoice.status = 'Paid'
        invoice.paid_date = timezone.now().date()
        invoice.save()

        self.log_action('UPDATE', invoice, {
            'status': {'old': invoice.status, 'new': 'Paid'}
        })

        return Response({'message': 'Invoice marked as paid'})

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Generate and download PDF for invoice"""
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from io import BytesIO
        from django.conf import settings
        import os

        invoice = self.get_object()
        company = invoice.contract.company

        # Get entity-specific details based on billing_entity
        billing_entity = company.billing_entity
        if billing_entity == 'BMAsia (Thailand) Co., Ltd.':
            entity_name = 'BMAsia (Thailand) Co., Ltd.'
            entity_address = '725 S-Metro Building, Suite 144, Level 20, Sukhumvit Road, Klongtan Nuea Watthana, Bangkok 10110, Thailand'
            entity_phone = '+66 2153 3520'
            entity_tax = '0105548025073'
            entity_bank = 'TMBThanachart Bank, Thonglor Soi 17 Branch'
            entity_swift = 'TMBKTHBK'
            entity_account = '916-1-00579-9'
            payment_terms_default = 'by bank transfer on a net received, paid in full basis, with no offset to BMA\'s TMB-Thanachart Bank, Bangkok, Thailand due immediately on invoicing to activate the music subscription. All outbound and inbound bank transfer fees are borne by the Client in remitting payments as invoiced less Withholding Tax required by Thai Law.'
        else:  # BMAsia Limited (Hong Kong)
            entity_name = 'BMAsia Limited'
            entity_address = '22nd Floor, Tai Yau Building, 181 Johnston Road, Wanchai, Hong Kong'
            entity_phone = '+66 2153 3520'
            entity_tax = None
            entity_bank = 'HSBC, HK'
            entity_swift = 'HSBCHKHHHKH'
            entity_account = '808-021570-838'
            payment_terms_default = 'by bank transfer on a net received, paid in full basis, with no offset to BMA\'s HSBC Bank, Hong Kong due immediately as invoiced to activate the music subscription. All Bank transfer fees, and all taxes are borne by the Client in remitting payments as invoiced.'

        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.4*inch, bottomMargin=0.4*inch)

        # Container for PDF elements
        elements = []
        styles = getSampleStyleSheet()

        # Custom styles - Modern 2025 design
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#424242'),
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#424242'),
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#424242'),
            leading=14
        )

        small_style = ParagraphStyle(
            'SmallText',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#757575'),
            leading=11
        )

        # Header - BMAsia Logo (properly sized with aspect ratio preserved)
        logo_path = os.path.join(settings.BASE_DIR, 'crm_app', 'static', 'crm_app', 'images', 'bmasia_logo.png')
        try:
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=160, height=64, kind='proportional')
                logo.hAlign = 'LEFT'
                elements.append(logo)
            else:
                # Fallback to text if logo not found
                elements.append(Paragraph("BM ASIA", title_style))
        except Exception:
            # Fallback to text if image loading fails
            elements.append(Paragraph("BM ASIA", title_style))

        # Orange accent line
        elements.append(Spacer(1, 0.1*inch))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#FFA500'), spaceBefore=0, spaceAfter=0))
        elements.append(Spacer(1, 0.2*inch))

        # Invoice title with orange color
        invoice_title_style = ParagraphStyle(
            'InvoiceTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#FFA500'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("INVOICE", invoice_title_style))

        # Document metadata table (modern grid layout)
        metadata_data = [
            ['Invoice Number', 'Issue Date', 'Due Date', 'Status'],
            [invoice.invoice_number,
             invoice.issue_date.strftime('%b %d, %Y'),
             invoice.due_date.strftime('%b %d, %Y'),
             invoice.status]
        ]

        metadata_table = Table(metadata_data, colWidths=[1.7*inch, 1.7*inch, 1.7*inch, 1.8*inch])
        metadata_table.setStyle(TableStyle([
            # Header row - orange background
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFA500')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),

            # Data row
            ('FONT', (0, 1), (-1, 1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#424242')),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('TOPPADDING', (0, 1), (-1, 1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 10),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(metadata_table)
        elements.append(Spacer(1, 0.2*inch))

        # Two-column From/Bill To section
        from_bill_data = [
            [Paragraph('<b>FROM:</b>', heading_style), Paragraph('<b>BILL TO:</b>', heading_style)],
            [
                Paragraph(f"""
                <b>{entity_name}</b><br/>
                {entity_address.replace(', ', '<br/>')}<br/>
                Phone: {entity_phone}
                {f"<br/>Tax No.: {entity_tax}" if entity_tax else ""}
                """, body_style),
                Paragraph(f"""
                <b>{company.legal_entity_name or company.name}</b><br/>
                {company.full_address.replace(', ', '<br/>') if company.full_address else (company.country or '')}
                """, body_style)
            ]
        ]

        from_bill_table = Table(from_bill_data, colWidths=[3.45*inch, 3.45*inch])
        from_bill_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, 1), 6),
        ]))
        elements.append(from_bill_table)
        elements.append(Spacer(1, 0.2*inch))

        # Contract reference
        contract_text = f"<b>Contract:</b> {invoice.contract.contract_number}<br/>"
        contract_text += f"<b>Service:</b> {invoice.contract.get_service_type_display() if invoice.contract.service_type else 'N/A'}"
        elements.append(Paragraph(contract_text, body_style))
        elements.append(Spacer(1, 0.3*inch))

        # Service description section
        elements.append(Paragraph("Services:", heading_style))

        # Currency symbol
        currency_symbol = {'USD': '$', 'THB': 'THB ', 'EUR': 'EUR ', 'GBP': 'GBP '}.get(invoice.currency, invoice.currency + ' ')

        # Create services table
        services_data = [
            ['Description', 'Amount']
        ]

        # Add main service line
        service_description = f"{invoice.contract.get_service_type_display() if invoice.contract.service_type else 'Professional Services'}"
        if invoice.contract.service_type:
            service_description += f"<br/><font size=8>Contract: {invoice.contract.contract_number}</font>"
            service_description += f"<br/><font size=8>Period: {invoice.contract.start_date.strftime('%b %d, %Y')} - {invoice.contract.end_date.strftime('%b %d, %Y')}</font>"

        services_data.append([
            Paragraph(service_description, body_style),
            f"{currency_symbol}{invoice.amount:,.2f}"
        ])

        # Create services table
        services_table = Table(services_data, colWidths=[5*inch, 1.9*inch])
        services_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFA500')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

            # Data rows
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#212121')),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))

        elements.append(services_table)
        elements.append(Spacer(1, 0.2*inch))

        # Totals section
        totals_data = []

        if invoice.amount > 0:
            totals_data.append(['Subtotal:', f"{currency_symbol}{invoice.amount:,.2f}"])

        if invoice.discount_amount > 0:
            discount_pct = (invoice.discount_amount / invoice.amount * 100) if invoice.amount > 0 else 0
            totals_data.append([f'Discount ({discount_pct:.0f}%):', f"-{currency_symbol}{invoice.discount_amount:,.2f}"])

        if invoice.tax_amount > 0:
            # Determine tax label based on billing entity
            tax_label = "VAT" if billing_entity == 'BMAsia (Thailand) Co., Ltd.' else "Tax"
            taxable_amount = invoice.amount - invoice.discount_amount
            tax_pct = (invoice.tax_amount / taxable_amount * 100) if taxable_amount > 0 else 0
            totals_data.append([f'{tax_label} ({tax_pct:.0f}%):', f"{currency_symbol}{invoice.tax_amount:,.2f}"])

        totals_data.append(['<b>Total Amount:</b>', f"<b>{currency_symbol}{invoice.total_amount:,.2f}</b>"])

        # Convert to Paragraphs for HTML rendering
        totals_data_parsed = []
        for label, value in totals_data:
            totals_data_parsed.append([
                Paragraph(label, body_style),
                Paragraph(value, body_style)
            ])

        totals_table = Table(totals_data_parsed, colWidths=[5*inch, 1.9*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            # Bold the last row (Total)
            ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 12),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#FFA500')),
        ]))

        elements.append(totals_table)
        elements.append(Spacer(1, 0.2*inch))

        # Bank Details Section - Organized blocks with background
        elements.append(Paragraph("BANK DETAILS FOR PAYMENT", heading_style))

        bank_data = [
            ['Beneficiary', entity_name],
            ['Bank', entity_bank],
            ['SWIFT Code', entity_swift],
            ['Account Number', entity_account],
        ]

        bank_table = Table(bank_data, colWidths=[2*inch, 4.9*inch])
        bank_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
            ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(bank_table)
        elements.append(Spacer(1, 0.15*inch))

        # Payment status indicator
        if invoice.status == 'Paid':
            paid_style = ParagraphStyle(
                'PaidStamp',
                parent=styles['Normal'],
                fontSize=16,
                textColor=colors.HexColor('#2e7d32'),
                alignment=TA_CENTER,
                spaceBefore=12,
                spaceAfter=12
            )
            elements.append(Paragraph("<b>✓ PAID</b>", paid_style))
            if invoice.paid_date:
                elements.append(Paragraph(f"Payment received on {invoice.paid_date.strftime('%B %d, %Y')}", body_style))
        elif invoice.is_overdue:
            overdue_style = ParagraphStyle(
                'OverdueStamp',
                parent=styles['Normal'],
                fontSize=14,
                textColor=colors.HexColor('#c62828'),
                alignment=TA_CENTER,
                spaceBefore=12,
                spaceAfter=12
            )
            elements.append(Paragraph(f"<b>⚠ OVERDUE - {invoice.days_overdue} days past due</b>", overdue_style))
        else:
            pending_style = ParagraphStyle(
                'PendingStamp',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor('#f57c00'),
                alignment=TA_CENTER,
                spaceBefore=12,
                spaceAfter=12
            )
            days_until_due = (invoice.due_date - timezone.now().date()).days
            if days_until_due > 0:
                elements.append(Paragraph(f"Payment due in {days_until_due} days", pending_style))
            else:
                elements.append(Paragraph("Payment due today", pending_style))

        elements.append(Spacer(1, 0.2*inch))

        # Payment terms
        elements.append(Paragraph("Payment Terms:", heading_style))
        # Use contract payment terms if specified, otherwise use entity default
        payment_terms_text = invoice.contract.payment_terms if invoice.contract.payment_terms else payment_terms_default
        payment_terms_formatted = payment_terms_text.replace('\n', '<br/>')
        elements.append(Paragraph(payment_terms_formatted, body_style))
        elements.append(Spacer(1, 0.2*inch))

        # Notes (if any)
        if invoice.notes:
            elements.append(Paragraph("Notes:", heading_style))
            notes_text = invoice.notes.replace('\n', '<br/>')
            elements.append(Paragraph(notes_text, body_style))
            elements.append(Spacer(1, 0.2*inch))

        # Footer - entity-specific with separator
        elements.append(Spacer(1, 0.15*inch))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0'), spaceBefore=0, spaceAfter=8))

        footer_text = f"""
        <b>{entity_name}</b> | {entity_address.replace(', ', ' | ')} | Phone: {entity_phone}
        """
        elements.append(Paragraph(footer_text, small_style))

        # Build PDF
        doc.build(elements)

        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()

        # Create response
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'

        # Log activity
        self.log_action('VIEW', invoice, {
            'action': 'PDF generated and downloaded',
            'invoice_number': invoice.invoice_number,
            'status': invoice.status
        })

        return response


class QuoteViewSet(BaseModelViewSet):
    """ViewSet for Quote management"""
    queryset = Quote.objects.all().prefetch_related(
        'line_items',
        'attachments',
        'activities'
    ).select_related('company', 'contact', 'opportunity', 'created_by')
    serializer_class = QuoteSerializer
    search_fields = ['quote_number', 'company__name', 'notes']
    ordering_fields = ['created_at', 'quote_number', 'total_value', 'valid_until', 'status']
    ordering = ['-created_at']
    filterset_fields = ['company', 'status', 'contact', 'opportunity', 'currency']

    def get_queryset(self):
        """Optimize queryset based on action"""
        queryset = super().get_queryset()

        if self.action == 'list':
            queryset = queryset.prefetch_related('line_items')
        elif self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                'line_items',
                'attachments',
                'attachments__uploaded_by',
                'activities',
                'activities__user'
            )

        return queryset

    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get quotes expiring within 7 days"""
        today = timezone.now().date()
        expiring = self.get_queryset().filter(
            valid_until__lte=today + timedelta(days=7),
            valid_until__gte=today,
            status__in=['Draft', 'Sent']
        )
        serializer = self.get_serializer(expiring, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Send quote via email with PDF attachment"""
        from crm_app.services.email_service import EmailService

        quote = self.get_object()
        email_service = EmailService()

        # Extract email parameters from request
        recipients = request.data.get('recipients', [])
        subject = request.data.get('subject')
        body = request.data.get('body')

        # Send email via EmailService (passes request for per-user SMTP)
        success, message = email_service.send_quote_email(
            quote_id=quote.id,
            recipients=recipients if recipients else None,
            subject=subject if subject else None,
            body=body if body else None,
            sender='admin',  # Legacy parameter, will use request.user
            request=request   # Critical for per-user SMTP authentication
        )

        if not success:
            return Response(
                {'error': message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Email service updates the status, refresh from DB
        quote.refresh_from_db()

        # Create activity
        QuoteActivity.objects.create(
            quote=quote,
            user=request.user if request.user.is_authenticated else None,
            activity_type='Sent',
            description=f'Quote {quote.quote_number} was sent to {quote.company.name}'
        )

        self.log_action('UPDATE', quote, {
            'status': {'old': 'Draft', 'new': 'Sent'},
            'action': 'Email sent',
            'recipients': recipients
        })

        return Response({
            'message': message,
            'status': quote.status,
            'sent_date': str(quote.sent_date) if quote.sent_date else None
        })

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Mark quote as accepted"""
        quote = self.get_object()
        quote.status = 'Accepted'
        quote.accepted_date = timezone.now().date()
        quote.save()

        # Create activity
        QuoteActivity.objects.create(
            quote=quote,
            user=request.user if request.user.is_authenticated else None,
            activity_type='Accepted',
            description=f'Quote {quote.quote_number} was accepted by {quote.company.name}'
        )

        return Response({'message': 'Quote marked as accepted'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Mark quote as rejected"""
        quote = self.get_object()
        quote.status = 'Rejected'
        quote.rejected_date = timezone.now().date()
        quote.save()

        # Create activity
        QuoteActivity.objects.create(
            quote=quote,
            user=request.user if request.user.is_authenticated else None,
            activity_type='Rejected',
            description=f'Quote {quote.quote_number} was rejected by {quote.company.name}'
        )

        return Response({'message': 'Quote marked as rejected'})

    @action(detail=True, methods=['post'])
    def add_attachment(self, request, pk=None):
        """Add attachment to quote"""
        quote = self.get_object()
        file = request.FILES.get('file')

        if not file:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attachment = QuoteAttachment.objects.create(
            quote=quote,
            name=file.name,
            file=file,
            size=file.size,
            uploaded_by=request.user if request.user.is_authenticated else None
        )

        serializer = QuoteAttachmentSerializer(attachment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Generate and download PDF for quote"""
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from io import BytesIO
        from django.conf import settings
        import os

        quote = self.get_object()

        # Get entity-specific details based on billing_entity
        billing_entity = quote.company.billing_entity
        if billing_entity == 'BMAsia (Thailand) Co., Ltd.':
            entity_name = 'BMAsia (Thailand) Co., Ltd.'
            entity_address = '725 S-Metro Building, Suite 144, Level 20, Sukhumvit Road, Klongtan Nuea Watthana, Bangkok 10110, Thailand'
            entity_phone = '+66 2153 3520'
            entity_tax = '0105548025073'
            entity_bank = 'TMBThanachart Bank, Thonglor Soi 17 Branch'
            entity_swift = 'TMBKTHBK'
            entity_account = '916-1-00579-9'
            payment_terms_default = 'by bank transfer on a net received, paid in full basis, with no offset to BMA\'s TMB-Thanachart Bank, Bangkok, Thailand due immediately on invoicing to activate the music subscription. All outbound and inbound bank transfer fees are borne by the Client in remitting payments as invoiced less Withholding Tax required by Thai Law.'
        else:  # BMAsia Limited (Hong Kong)
            entity_name = 'BMAsia Limited'
            entity_address = '22nd Floor, Tai Yau Building, 181 Johnston Road, Wanchai, Hong Kong'
            entity_phone = '+66 2153 3520'
            entity_tax = None
            entity_bank = 'HSBC, HK'
            entity_swift = 'HSBCHKHHHKH'
            entity_account = '808-021570-838'
            payment_terms_default = 'by bank transfer on a net received, paid in full basis, with no offset to BMA\'s HSBC Bank, Hong Kong due immediately as invoiced to activate the music subscription. All Bank transfer fees, and all taxes are borne by the Client in remitting payments as invoiced.'

        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.4*inch, bottomMargin=0.4*inch)

        # Container for PDF elements
        elements = []
        styles = getSampleStyleSheet()

        # Custom styles - Modern 2025 design
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#424242'),
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#424242'),
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#424242'),
            leading=14
        )

        small_style = ParagraphStyle(
            'SmallText',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.HexColor('#757575'),
            leading=10
        )

        terms_style = ParagraphStyle(
            'TermsText',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.HexColor('#757575'),
            leading=9
        )

        # Header - BMAsia Logo (properly sized with aspect ratio preserved)
        logo_path = os.path.join(settings.BASE_DIR, 'crm_app', 'static', 'crm_app', 'images', 'bmasia_logo.png')
        try:
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=140, height=56, kind='proportional')
                logo.hAlign = 'LEFT'
                elements.append(logo)
            else:
                # Fallback to text if logo not found
                elements.append(Paragraph("BM ASIA", title_style))
        except Exception:
            # Fallback to text if image loading fails
            elements.append(Paragraph("BM ASIA", title_style))

        # Orange accent line
        elements.append(Spacer(1, 0.05*inch))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#FFA500'), spaceBefore=0, spaceAfter=0))
        elements.append(Spacer(1, 0.15*inch))

        # Quote title with orange color
        quote_title_style = ParagraphStyle(
            'QuoteTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#FFA500'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("QUOTATION", quote_title_style))

        # Document metadata table (modern grid layout)
        metadata_data = [
            ['Quote Number', 'Date', 'Valid Until', 'Status'],
            [quote.quote_number,
             quote.valid_from.strftime('%b %d, %Y'),
             quote.valid_until.strftime('%b %d, %Y'),
             quote.status]
        ]

        metadata_table = Table(metadata_data, colWidths=[1.7*inch, 1.7*inch, 1.7*inch, 1.8*inch])
        metadata_table.setStyle(TableStyle([
            # Header row - orange background
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFA500')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('TOPPADDING', (0, 0), (-1, 0), 4),

            # Data row
            ('FONT', (0, 1), (-1, 1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#424242')),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('TOPPADDING', (0, 1), (-1, 1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 4),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(metadata_table)
        elements.append(Spacer(1, 0.15*inch))

        # Two-column From/Bill To section
        from_bill_data = [
            [Paragraph('<b>FROM:</b>', heading_style), Paragraph('<b>BILL TO:</b>', heading_style)],
            [
                Paragraph(f"""
                <b>{entity_name}</b><br/>
                {entity_address.replace(', ', '<br/>')}<br/>
                Phone: {entity_phone}
                {f"<br/>Tax No.: {entity_tax}" if entity_tax else ""}
                """, body_style),
                Paragraph(f"""
                <b>{quote.company.legal_entity_name or quote.company.name}</b><br/>
                {quote.company.full_address.replace(', ', '<br/>') if quote.company.full_address else (quote.company.country or '')}
                {f"<br/><br/><b>Contact:</b> {quote.contact.name}" if quote.contact else ""}
                {f"<br/>Email: {quote.contact.email}" if quote.contact and quote.contact.email else ""}
                {f"<br/>Phone: {quote.contact.phone}" if quote.contact and quote.contact.phone else ""}
                """, body_style)
            ]
        ]

        from_bill_table = Table(from_bill_data, colWidths=[3.45*inch, 3.45*inch])
        from_bill_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, 1), 6),
        ]))
        elements.append(from_bill_table)
        elements.append(Spacer(1, 0.15*inch))

        # Line items table
        elements.append(Paragraph("Items:", heading_style))

        # Prepare line items data
        line_items = quote.line_items.all()

        if line_items.exists():
            # Currency symbol
            currency_symbol = {'USD': '$', 'THB': 'THB ', 'EUR': 'EUR ', 'GBP': 'GBP '}.get(quote.currency, quote.currency + ' ')

            table_data = [
                ['Description', 'Quantity', 'Unit Price', 'Total']
            ]

            for item in line_items:
                table_data.append([
                    Paragraph(item.description, body_style),
                    str(item.quantity),
                    f"{currency_symbol}{item.unit_price:,.2f}",
                    f"{currency_symbol}{item.line_total:,.2f}"
                ])

            # Create line items table
            line_items_table = Table(table_data, colWidths=[3.5*inch, 1*inch, 1.2*inch, 1.2*inch])
            line_items_table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFA500')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

                # Data rows
                ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#212121')),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),

                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),

                # Alternating row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ]))

            elements.append(line_items_table)
        else:
            elements.append(Paragraph("No line items", body_style))

        elements.append(Spacer(1, 0.15*inch))

        # Totals section
        totals_data = []

        if quote.subtotal > 0:
            totals_data.append(['Subtotal:', f"{currency_symbol}{quote.subtotal:,.2f}"])

        # Calculate weighted average discount percentage from line items
        if quote.discount_amount > 0:
            total_before_discount = sum(item.quantity * item.unit_price for item in line_items)
            discount_pct = (quote.discount_amount / total_before_discount * 100) if total_before_discount > 0 else 0
            totals_data.append([f'Discount ({discount_pct:.0f}%):', f"-{currency_symbol}{quote.discount_amount:,.2f}"])

        # Calculate weighted average tax rate from line items
        if quote.tax_amount > 0:
            # Determine tax label based on billing entity
            tax_label = "VAT" if billing_entity == 'BMAsia (Thailand) Co., Ltd.' else "Tax"
            after_discount = quote.subtotal
            tax_pct = (quote.tax_amount / after_discount * 100) if after_discount > 0 else 0
            totals_data.append([f'{tax_label} ({tax_pct:.0f}%):', f"{currency_symbol}{quote.tax_amount:,.2f}"])

        totals_data.append(['<b>Total:</b>', f"<b>{currency_symbol}{quote.total_value:,.2f}</b>"])

        # Convert to Paragraphs for HTML rendering
        totals_data_parsed = []
        for label, value in totals_data:
            totals_data_parsed.append([
                Paragraph(label, body_style),
                Paragraph(value, body_style)
            ])

        totals_table = Table(totals_data_parsed, colWidths=[5*inch, 1.9*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            # Bold the last row (Total)
            ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 12),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#FFA500')),
        ]))

        elements.append(totals_table)
        elements.append(Spacer(1, 0.15*inch))

        # Bank Details Section - Organized blocks with background
        elements.append(Paragraph("BANK DETAILS FOR PAYMENT", heading_style))

        bank_data = [
            ['Beneficiary', entity_name],
            ['Bank', entity_bank],
            ['SWIFT Code', entity_swift],
            ['Account Number', entity_account],
        ]

        bank_table = Table(bank_data, colWidths=[2*inch, 4.9*inch])
        bank_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
            ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(bank_table)
        elements.append(Spacer(1, 0.1*inch))

        # Terms and conditions - integrated with bank details (no heading)
        if quote.terms_conditions:
            # Handle multi-line terms and conditions
            terms_text = quote.terms_conditions.replace('\n', '<br/>')
            elements.append(Paragraph(terms_text, terms_style))
        else:
            # Use default payment terms if no custom terms
            payment_terms_formatted = payment_terms_default.replace('\n', '<br/>')
            elements.append(Paragraph(payment_terms_formatted, terms_style))

        # Notes (internal - optional to show on PDF)
        if quote.notes:
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph("Notes:", heading_style))
            notes_text = quote.notes.replace('\n', '<br/>')
            elements.append(Paragraph(notes_text, terms_style))

        # Footer - entity-specific with separator
        elements.append(Spacer(1, 0.05*inch))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0'), spaceBefore=0, spaceAfter=8))

        footer_text = f"""
        <b>{entity_name}</b> | {entity_address.replace(', ', ' | ')} | Phone: {entity_phone}
        """
        elements.append(Paragraph(footer_text, small_style))

        # Build PDF
        doc.build(elements)

        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()

        # Create response
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Quote_{quote.quote_number}.pdf"'

        # Log activity
        QuoteActivity.objects.create(
            quote=quote,
            user=request.user if request.user.is_authenticated else None,
            activity_type='Viewed',
            description=f'Quote {quote.quote_number} PDF generated and downloaded'
        )

        return response


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for AuditLog (read-only)"""
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    search_fields = ['user__username', 'model_name', 'action']
    ordering_fields = ['timestamp', 'action', 'model_name']
    ordering = ['-timestamp']
    filterset_fields = ['user', 'action', 'model_name']


class DashboardViewSet(viewsets.ViewSet):
    """ViewSet for dashboard statistics"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get dashboard statistics"""
        user = request.user
        
        # Base querysets
        companies = Company.objects.filter(is_active=True)
        opportunities = Opportunity.objects.filter(is_active=True)
        contracts = Contract.objects.filter(is_active=True)
        tasks = Task.objects.all()
        invoices = Invoice.objects.all()
        
        # Apply role-based filtering
        if user.role == 'Sales':
            opportunities = opportunities.filter(owner=user)
            companies = companies.filter(opportunities__owner=user).distinct()
        elif user.role == 'Finance':
            pass  # Finance sees all financial data
        elif user.role in ['Tech', 'Music']:
            tasks = tasks.filter(Q(assigned_to=user) | Q(department=user.role))
            companies = companies.filter(tasks__in=tasks).distinct()
        
        # Calculate statistics
        stats = {
            'total_companies': companies.count(),
            'active_opportunities': opportunities.count(),
            'opportunities_value': opportunities.aggregate(Sum('expected_value'))['expected_value__sum'] or 0,
            'active_contracts': contracts.count(),
            'contracts_value': contracts.aggregate(Sum('value'))['value__sum'] or 0,
            'overdue_tasks': sum(1 for task in tasks if task.is_overdue),
            'overdue_invoices': sum(1 for invoice in invoices if invoice.is_overdue),
            'pending_renewals': sum(1 for contract in contracts if contract.is_expiring_soon),
        }
        
        # Sales funnel stats
        stats.update({
            'contacted_count': opportunities.filter(stage='Contacted').count(),
            'quotation_count': opportunities.filter(stage='Quotation Sent').count(),
            'contract_count': opportunities.filter(stage='Contract Sent').count(),
            'won_count': opportunities.filter(stage='Won').count(),
            'lost_count': opportunities.filter(stage='Lost').count(),
        })
        
        # Monthly stats
        current_month = timezone.now().replace(day=1)
        monthly_contracts = contracts.filter(start_date__gte=current_month)
        monthly_opportunities = opportunities.filter(created_at__gte=current_month)
        monthly_closed = opportunities.filter(
            actual_close_date__gte=current_month,
            stage='Won'
        )
        
        stats.update({
            'monthly_revenue': monthly_contracts.aggregate(Sum('value'))['value__sum'] or 0,
            'monthly_new_opportunities': monthly_opportunities.count(),
            'monthly_closed_deals': monthly_closed.count(),
        })
        
        serializer = DashboardStatsSerializer(stats)
        return Response(serializer.data)


class AuthViewSet(viewsets.ViewSet):
    """ViewSet for authentication"""
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """User login"""
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        login(request, user)

        # Create JWT tokens
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        # Log login action
        AuditLog.objects.create(
            user=user,
            action='LOGIN',
            model_name='User',
            record_id=str(user.pk),
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        return Response({
            'access': str(access),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def refresh(self, request):
        """Refresh JWT token"""
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'error': 'Refresh token is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            refresh = RefreshToken(refresh_token)
            access = refresh.access_token

            return Response({
                'access': str(access)
            })
        except Exception as e:
            return Response(
                {'error': 'Invalid refresh token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current user info"""
        return Response(UserSerializer(request.user).data)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def logout(self, request):
        """User logout"""
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                # Try to blacklist the refresh token if blacklisting is available
                token = RefreshToken(refresh_token)
                # Only attempt blacklisting if the token_blacklist app is available
                if hasattr(token, 'blacklist'):
                    try:
                        token.blacklist()
                    except Exception:
                        # Blacklisting failed (probably missing database tables), continue anyway
                        pass
        except Exception:
            pass  # Continue with logout even if token handling fails

        if request.user.is_authenticated:
            # Log logout action
            AuditLog.objects.create(
                user=request.user,
                action='LOGOUT',
                model_name='User',
                record_id=str(request.user.pk),
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

            logout(request)

        return Response({'message': 'Logged out successfully'})
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@csrf_exempt
def reset_admin(request):
    """Reset admin password to default"""
    User = get_user_model()
    
    # Delete any existing admin users
    deleted_count = User.objects.filter(username='admin').delete()[0]
    
    # Create new admin user
    admin_user = User.objects.create_superuser(
        username='admin',
        email='admin@bmasia.com',
        password='bmasia123',
        role='Admin'
    )
    
    return HttpResponse(f"""
        <h2>✅ Admin Reset Successful!</h2>
        <p>Deleted {deleted_count} existing admin users</p>
        <p>Created fresh admin user:</p>
        <strong>Username:</strong> admin<br>
        <strong>Password:</strong> bmasia123<br><br>
        <a href="/admin/" style="background: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to Admin Login</a>
    """)


def debug_soundtrack_api(request):
    """Debug endpoint to check Soundtrack API configuration and test connection"""
    from .services.soundtrack_api import soundtrack_api
    
    # Check environment variables
    env_vars = {
        'SOUNDTRACK_API_TOKEN': os.environ.get('SOUNDTRACK_API_TOKEN', 'NOT SET'),
        'SOUNDTRACK_CLIENT_ID': os.environ.get('SOUNDTRACK_CLIENT_ID', 'NOT SET'),
        'SOUNDTRACK_CLIENT_SECRET': os.environ.get('SOUNDTRACK_CLIENT_SECRET', 'NOT SET'),
    }
    
    # Check if they're loaded in the service
    service_config = {
        'api_token': 'SET' if soundtrack_api.api_token else 'NOT SET',
        'client_id': 'SET' if soundtrack_api.client_id else 'NOT SET',
        'client_secret': 'SET' if soundtrack_api.client_secret else 'NOT SET',
        'base_url': soundtrack_api.base_url,
    }
    
    # Test API connection if requested
    test_results = {}
    if request.GET.get('test') == '1':
        test_account_id = request.GET.get('account_id', 'QWNjb3VudCwsMXN4N242NTZyeTgv')
        
        # Test basic authentication first
        try:
            import requests
            headers = {
                'Authorization': f'Basic {soundtrack_api.api_token}',
                'Content-Type': 'application/json',
            }
            
            # Try a GraphQL query
            test_url = soundtrack_api.base_url
            test_query = {
                'query': '{ account { id businessName } }'
            }
            response = requests.post(test_url, json=test_query, headers=headers, timeout=10)
            
            test_results['raw_api_test'] = {
                'url': test_url,
                'status_code': response.status_code,
                'headers_sent': {k: v[:20] + '...' if len(v) > 20 else v for k, v in headers.items()},
                'query': test_query,
                'response_json': response.json() if response.status_code == 200 else None,
                'response_text': response.text[:500] if response.text else 'No response body',
                'response_headers': dict(response.headers)
            }
        except Exception as e:
            test_results['raw_api_test'] = {
                'error': str(e)
            }
        
        # Test account info with GraphQL
        account_data = soundtrack_api.get_account_info()
        test_results['account_info'] = {
            'success': account_data is not None,
            'data': account_data if account_data else 'Failed to fetch'
        }
        
        # Test zones
        zones = soundtrack_api.get_account_zones(test_account_id)
        test_results['zones'] = {
            'success': zones is not None and len(zones) > 0,
            'count': len(zones) if zones else 0,
            'data': zones[:5] if zones else 'Failed to fetch'  # Show first 5 zones
        }
    
    return JsonResponse({
        'environment_variables': env_vars,
        'service_configuration': service_config,
        'test_results': test_results,
        'instructions': 'Add ?test=1&account_id=YOUR_ACCOUNT_ID to test API connection'
    }, json_dumps_params={'indent': 2})


@csrf_exempt
def initialize_database(request):
    """
    One-time database initialization endpoint.
    Access with: /initialize-database/?key=bmasia2024init
    """
    # Simple security check
    init_key = request.GET.get('key', '')
    if init_key != 'bmasia2024init':
        return HttpResponse('Unauthorized', status=401)

    try:
        # Run the initialization command
        call_command('initialize_database')
        return HttpResponse("""
            <h1>✓ Database Initialized Successfully!</h1>
            <p>The database has been set up with:</p>
            <ul>
                <li>All migrations applied</li>
                <li>Admin superuser created (admin/bmasia123)</li>
                <li>Email templates configured</li>
            </ul>
            <p><a href="/admin/">Go to Admin Login</a></p>
        """, content_type='text/html')
    except Exception as e:
        return HttpResponse(f'Initialization failed: {str(e)}', status=500)


@csrf_exempt
def apply_migration_0025_view(request):
    """
    Emergency endpoint to apply migration 0025 manually
    Access: /api/apply-migration-0025/?key=bmasia2024migrate
    """
    # Simple security check
    migrate_key = request.GET.get('key', '')
    if migrate_key != 'bmasia2024migrate':
        return HttpResponse('Unauthorized', status=401)

    try:
        from django.db import connection
        results = []

        with connection.cursor() as cursor:
            # Check if columns exist
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'auth_user'
                AND column_name IN ('smtp_email', 'smtp_password')
            """)
            existing = [row[0] for row in cursor.fetchall()]
            results.append(f"Existing columns: {existing}")

            if len(existing) == 2:
                results.append("✓ Both columns already exist!")
            else:
                # Add smtp_email
                if 'smtp_email' not in existing:
                    cursor.execute("""
                        ALTER TABLE auth_user
                        ADD COLUMN smtp_email VARCHAR(254) NULL
                    """)
                    results.append("✓ Added smtp_email column")

                # Add smtp_password
                if 'smtp_password' not in existing:
                    cursor.execute("""
                        ALTER TABLE auth_user
                        ADD COLUMN smtp_password VARCHAR(255) NULL
                    """)
                    results.append("✓ Added smtp_password column")

            # Record migration
            cursor.execute("""
                SELECT COUNT(*) FROM django_migrations
                WHERE app = 'crm_app'
                AND name = '0025_user_smtp_email_user_smtp_password'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES ('crm_app', '0025_user_smtp_email_user_smtp_password', NOW())
                """)
                results.append("✓ Migration recorded in django_migrations")
            else:
                results.append("✓ Migration already recorded")

            # Verify
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'auth_user'
                AND column_name IN ('smtp_email', 'smtp_password')
                ORDER BY column_name
            """)
            verify_results = cursor.fetchall()
            results.append("<br><b>Verification:</b>")
            for col_name, data_type, max_len, nullable in verify_results:
                results.append(f"  {col_name}: {data_type}({max_len}), nullable={nullable}")

        return HttpResponse(f"""
            <h1>✓ Migration 0025 Applied Successfully!</h1>
            <pre>{'<br>'.join(results)}</pre>
            <p><a href="/api/v1/auth/login/">Test Login</a></p>
        """, content_type='text/html')
    except Exception as e:
        import traceback
        return HttpResponse(f'Migration failed: {str(e)}<br><pre>{traceback.format_exc()}</pre>', status=500)


# ============================================================================
# CAMPAIGN API ENDPOINTS
# ============================================================================

class CampaignViewSet(BaseModelViewSet):
    """ViewSet for EmailCampaign management"""
    from .serializers import EmailCampaignSerializer, EmailCampaignDetailSerializer, CampaignRecipientSerializer
    from .models import EmailCampaign, CampaignRecipient, Contact

    queryset = EmailCampaign.objects.all()
    serializer_class = EmailCampaignSerializer
    search_fields = ['name', 'subject', 'campaign_type']
    ordering_fields = ['created_at', 'scheduled_send_date', 'actual_send_date', 'audience_count', 'total_sent']
    ordering = ['-created_at']
    filterset_fields = ['campaign_type', 'status', 'send_immediately']

    def get_serializer_class(self):
        """Use detail serializer for retrieve action"""
        from .serializers import EmailCampaignDetailSerializer
        if self.action == 'retrieve':
            return EmailCampaignDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related('recipients__contact__company')
        return queryset

    def create(self, request, *args, **kwargs):
        """
        Create campaign and handle contact_ids for recipients
        """
        from .models import CampaignRecipient, Contact
        from django.db import transaction
        import copy

        # Extract contact_ids from request data (not a model field)
        # Create mutable copy of request.data to avoid modifying original QueryDict
        data = copy.deepcopy(dict(request.data))
        contact_ids = data.get('contact_ids', [])

        # Create campaign using parent create method
        response = super().create(request, *args, **kwargs)
        campaign = self.queryset.get(id=response.data['id'])

        # Create campaign recipients from contact_ids
        if contact_ids:
            with transaction.atomic():
                for contact_id in contact_ids:
                    try:
                        contact = Contact.objects.get(id=contact_id, is_active=True)
                        CampaignRecipient.objects.create(
                            campaign=campaign,
                            contact=contact,
                            status='pending'
                        )
                    except Contact.DoesNotExist:
                        pass

                # Update audience_count
                campaign.audience_count = campaign.recipients.count()
                campaign.save(update_fields=['audience_count'])

        self.log_action('CREATE', campaign, {'recipients_count': len(contact_ids)})

        return response

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """
        POST /api/v1/campaigns/{id}/send/
        Send campaign to all recipients
        """
        from .models import CampaignRecipient, Contact, EmailLog
        from .services.email_service import EmailService
        from django.db import transaction

        campaign = self.get_object()
        email_service = EmailService()

        # Validate campaign can be sent
        if campaign.status == 'sent':
            return Response(
                {'error': 'Campaign has already been sent'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if campaign.status == 'cancelled':
            return Response(
                {'error': 'Cannot send cancelled campaign'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create recipients based on target_audience or manually selected contacts
        recipient_contact_ids = request.data.get('recipient_ids', [])

        if not campaign.recipients.exists() and recipient_contact_ids:
            # Create recipients from provided contact IDs
            for contact_id in recipient_contact_ids:
                try:
                    contact = Contact.objects.get(id=contact_id, is_active=True)
                    CampaignRecipient.objects.get_or_create(
                        campaign=campaign,
                        contact=contact,
                        defaults={'status': 'pending'}
                    )
                except Contact.DoesNotExist:
                    pass

        # Get all pending recipients
        pending_recipients = campaign.recipients.filter(status='pending')

        if not pending_recipients.exists():
            return Response(
                {'error': 'No pending recipients to send to'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update campaign status
        campaign.status = 'sending'
        campaign.actual_send_date = timezone.now()
        campaign.save()

        # Send emails to each recipient
        sent_count = 0
        failed_count = 0

        for recipient in pending_recipients:
            try:
                # Prepare email context
                context = {
                    'company_name': recipient.contact.company.name if recipient.contact.company else '',
                    'contact_name': recipient.contact.name,
                    'contact_email': recipient.contact.email,
                }

                # Render body with context if needed
                if campaign.template:
                    # Use template if specified
                    from .services.email_service import EmailService
                    body = EmailService().render_template(campaign.template, context)
                else:
                    # No template - extract custom body from target_audience JSON
                    # For Phase 1, campaigns store custom content in target_audience.custom_body
                    if campaign.target_audience and isinstance(campaign.target_audience, dict):
                        body = campaign.target_audience.get('custom_body', campaign.subject)
                    else:
                        body = campaign.subject

                # Send email
                success, message = email_service.send_email(
                    to_email=recipient.contact.email,
                    subject=campaign.subject,
                    body=body,
                    sender_email=campaign.sender_email or request.user.email,
                    request=request
                )

                if success:
                    recipient.mark_as_sent()
                    sent_count += 1
                else:
                    recipient.mark_as_failed(message)
                    failed_count += 1

            except Exception as e:
                recipient.mark_as_failed(str(e))
                failed_count += 1

        # Update campaign analytics
        campaign.update_analytics()
        campaign.status = 'sent'
        campaign.save()

        self.log_action('UPDATE', campaign, {
            'action': 'Campaign sent',
            'sent_count': sent_count,
            'failed_count': failed_count
        })

        return Response({
            'message': f'Campaign sent to {sent_count} recipients',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'status': campaign.status
        })

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        POST /api/v1/campaigns/{id}/test/
        Send test email to specified addresses
        """
        from .services.email_service import EmailService

        campaign = self.get_object()
        test_emails = request.data.get('test_emails', [])

        if not test_emails:
            return Response(
                {'error': 'No test email addresses provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        email_service = EmailService()
        results = []

        for email in test_emails:
            success, message = email_service.send_email(
                to_email=email,
                subject=f"[TEST] {campaign.subject}",
                body=campaign.body,
                sender_email=campaign.sender_email or request.user.email,
                request=request
            )
            results.append({
                'email': email,
                'success': success,
                'message': message
            })

        return Response({
            'message': 'Test emails sent',
            'results': results
        })

    @action(detail=True, methods=['get'])
    def recipients(self, request, pk=None):
        """
        GET /api/v1/campaigns/{id}/recipients/
        Get campaign recipients with pagination
        """
        from .serializers import CampaignRecipientSerializer

        campaign = self.get_object()
        recipients = campaign.recipients.select_related('contact__company', 'email_log').all()

        # Apply pagination
        page = self.paginate_queryset(recipients)
        if page is not None:
            serializer = CampaignRecipientSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CampaignRecipientSerializer(recipients, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_recipients(self, request, pk=None):
        """
        POST /api/v1/campaigns/{id}/add_recipients/
        Add contacts as campaign recipients
        """
        from .models import CampaignRecipient, Contact

        campaign = self.get_object()
        contact_ids = request.data.get('contact_ids', [])

        if not contact_ids:
            return Response(
                {'error': 'No contact IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        added_count = 0
        skipped_count = 0

        for contact_id in contact_ids:
            try:
                contact = Contact.objects.get(
                    id=contact_id,
                    is_active=True,
                    receives_notifications=True
                )
                _, created = CampaignRecipient.objects.get_or_create(
                    campaign=campaign,
                    contact=contact,
                    defaults={'status': 'pending'}
                )
                if created:
                    added_count += 1
                else:
                    skipped_count += 1
            except Contact.DoesNotExist:
                skipped_count += 1

        # Update audience count
        campaign.audience_count = campaign.recipients.count()
        campaign.save()

        return Response({
            'message': f'Added {added_count} recipients',
            'added_count': added_count,
            'skipped_count': skipped_count,
            'total_recipients': campaign.audience_count
        })

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """
        POST /api/v1/campaigns/{id}/pause/
        Pause a scheduled campaign
        """
        campaign = self.get_object()

        if campaign.status not in ['scheduled', 'sending']:
            return Response(
                {'error': 'Can only pause scheduled or sending campaigns'},
                status=status.HTTP_400_BAD_REQUEST
            )

        campaign.status = 'paused'
        campaign.save()

        self.log_action('UPDATE', campaign, {
            'action': 'Campaign paused'
        })

        return Response({
            'message': 'Campaign paused',
            'status': campaign.status
        })

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """
        POST /api/v1/campaigns/{id}/resume/
        Resume a paused campaign
        """
        campaign = self.get_object()

        if campaign.status != 'paused':
            return Response(
                {'error': 'Can only resume paused campaigns'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Resume to appropriate status
        if campaign.scheduled_send_date:
            campaign.status = 'scheduled'
        else:
            campaign.status = 'draft'
        campaign.save()

        self.log_action('UPDATE', campaign, {
            'action': 'Campaign resumed'
        })

        return Response({
            'message': 'Campaign resumed',
            'status': campaign.status
        })

    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """
        POST /api/v1/campaigns/{id}/schedule/
        Schedule campaign for future sending
        """
        campaign = self.get_object()
        scheduled_date = request.data.get('scheduled_send_date')

        if not scheduled_date:
            return Response(
                {'error': 'scheduled_send_date is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse and validate date
        try:
            from dateutil import parser
            scheduled_dt = parser.parse(scheduled_date)
            if scheduled_dt < timezone.now():
                return Response(
                    {'error': 'Scheduled date must be in the future'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except:
            return Response(
                {'error': 'Invalid date format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        campaign.scheduled_send_date = scheduled_dt
        campaign.status = 'scheduled'
        campaign.send_immediately = False
        campaign.save()

        self.log_action('UPDATE', campaign, {
            'action': 'Campaign scheduled',
            'scheduled_send_date': str(scheduled_dt)
        })

        return Response({
            'message': 'Campaign scheduled',
            'scheduled_send_date': campaign.scheduled_send_date,
            'status': campaign.status
        })


# ============================================================================
# AUTOMATION API ENDPOINTS
# ============================================================================

class AutomationViewSet(viewsets.ViewSet):
    """
    ViewSet for email automation status and manual triggering
    """
    permission_classes = [AllowAny]  # TODO: Restrict to admin in production

    @action(detail=False, methods=['get'], url_path='status')
    def get_status(self, request):
        """
        GET /api/v1/automation/status/
        Returns automation status, schedule, and recent statistics
        """
        from .models import EmailLog
        from datetime import datetime, timedelta

        # Calculate next run (cron: 0 2 * * * = daily at 2:00 AM UTC)
        now = timezone.now()
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now.hour >= 2:
            next_run += timedelta(days=1)

        # Get last run from most recent EmailLog
        last_email = EmailLog.objects.filter(
            email_type__in=['renewal', 'payment', 'quarterly']
        ).order_by('-sent_at').first()
        last_run = last_email.sent_at if last_email else None

        # Calculate statistics for last 7 days
        seven_days_ago = now - timedelta(days=7)
        recent_stats = {
            'renewal_sent': EmailLog.objects.filter(
                email_type='renewal',
                status='sent',
                sent_at__gte=seven_days_ago
            ).count(),
            'payment_sent': EmailLog.objects.filter(
                email_type='payment',
                status='sent',
                sent_at__gte=seven_days_ago
            ).count(),
            'quarterly_sent': EmailLog.objects.filter(
                email_type='quarterly',
                status='sent',
                sent_at__gte=seven_days_ago
            ).count(),
        }
        recent_stats['total_sent_last_7_days'] = sum(recent_stats.values())

        return Response({
            'enabled': True,  # Cron job is active on Render
            'cron_schedule': '0 2 * * *',  # Daily at 2 AM UTC
            'cron_description': 'Daily at 9:00 AM Bangkok time',
            'last_run': last_run.isoformat() if last_run else None,
            'next_run': next_run.isoformat(),
            'recent_stats': recent_stats,
        })

    @action(detail=False, methods=['post'], url_path='test-run')
    def test_run(self, request):
        """
        POST /api/v1/automation/test-run/
        Body: { "type": "renewal|payment|quarterly|all", "dry_run": true }
        Manually trigger email automation
        """
        import subprocess
        import sys

        email_type = request.data.get('type', 'all')
        dry_run = request.data.get('dry_run', True)

        # Validate type
        valid_types = ['all', 'renewal', 'payment', 'quarterly']
        if email_type not in valid_types:
            return Response(
                {'error': f'Invalid type. Must be one of: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build command
        cmd = [
            sys.executable,
            'manage.py',
            'send_emails',
            '--type', email_type,
            '--force'  # Force to run outside business hours
        ]
        if dry_run:
            cmd.append('--dry-run')

        try:
            # Run command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )

            return Response({
                'success': result.returncode == 0,
                'dry_run': dry_run,
                'type': email_type,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None,
            })
        except subprocess.TimeoutExpired:
            return Response(
                {'error': 'Command timed out after 60 seconds'},
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to run command: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='recent-emails')
    def recent_emails(self, request):
        """
        GET /api/v1/automation/recent-emails/
        Returns last 20 automated emails sent
        """
        from .models import EmailLog

        # Get recent automated emails (exclude manual/test)
        emails = EmailLog.objects.filter(
            email_type__in=['renewal', 'payment', 'quarterly']
        ).select_related(
            'company', 'contact', 'contract', 'invoice'
        ).order_by('-sent_at')[:20]

        # Serialize
        results = []
        for email in emails:
            results.append({
                'id': str(email.id),
                'date': email.sent_at.isoformat() if email.sent_at else email.created_at.isoformat(),
                'type': email.get_email_type_display(),
                'type_code': email.email_type,
                'recipients': email.to_email,
                'status': email.get_status_display(),
                'status_code': email.status,
                'subject': email.subject,
                'company': email.company.name if email.company else None,
                'contact': email.contact.name if email.contact else None,
            })

        return Response(results)


class EmailTemplateViewSet(BaseModelViewSet):
    """ViewSet for EmailTemplate management with preview and duplication"""
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'template_type', 'subject', 'body_text']
    ordering_fields = ['created_at', 'name', 'template_type', 'language']
    ordering = ['-created_at', 'name']
    filterset_fields = ['template_type', 'language', 'is_active', 'department']

    def get_queryset(self):
        """Override queryset to support has_campaigns filter"""
        queryset = super().get_queryset()

        # Filter by has_campaigns parameter
        has_campaigns = self.request.query_params.get('has_campaigns')
        if has_campaigns is not None:
            if has_campaigns.lower() in ['true', '1', 'yes']:
                # Only templates used in campaigns
                queryset = queryset.annotate(
                    campaign_count=Count('campaigns')
                ).filter(campaign_count__gt=0)
            elif has_campaigns.lower() in ['false', '0', 'no']:
                # Only templates NOT used in campaigns
                queryset = queryset.annotate(
                    campaign_count=Count('campaigns')
                ).filter(campaign_count=0)

        return queryset

    @action(detail=False, methods=['post'])
    def bulk_operations(self, request):
        """
        Handle bulk operations on email templates with activate/deactivate support.

        POST /api/v1/email-templates/bulk_operations/
        Body: {
            "action": "activate" | "deactivate" | "delete" | "export",
            "ids": ["uuid1", "uuid2", ...]
        }
        """
        serializer = BulkOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_type = serializer.validated_data['action']
        ids = serializer.validated_data['ids']

        # Get queryset filtered by IDs
        queryset = self.get_queryset().filter(id__in=ids)

        if action_type == 'activate':
            count = queryset.update(is_active=True)
            return Response({
                'message': f'{count} template{"s" if count != 1 else ""} activated',
                'count': count
            })

        elif action_type == 'deactivate':
            count = queryset.update(is_active=False)
            return Response({
                'message': f'{count} template{"s" if count != 1 else ""} deactivated',
                'count': count
            })

        elif action_type == 'delete':
            # Let parent class handle delete with audit logging
            return super().bulk_operations(request)

        elif action_type == 'export':
            # Let parent class handle export
            return super().bulk_operations(request)

        # If action is not recognized, fall back to parent
        return super().bulk_operations(request)

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        GET /api/v1/email-templates/{id}/preview/
        Renders template with sample data
        """
        template = self.get_object()

        # Sample context data for preview
        sample_context = {
            # Common variables
            'company_name': 'Acme Corp',
            'contact_name': 'John Doe',
            'current_year': '2025',
            'unsubscribe_url': 'https://example.com/unsubscribe',

            # Renewal variables
            'contract_number': 'C-2025-001',
            'end_date': '2025-12-31',
            'days_until_expiry': '30',
            'monthly_value': '$500',

            # Invoice variables
            'invoice_number': 'INV-2025-001',
            'due_date': '2025-02-15',
            'total_amount': '$1,500',
            'payment_url': 'https://example.com/pay/inv-001',
            'days_overdue': '7',

            # Zone variables
            'zone_name': 'Main Restaurant',
            'offline_duration': '48 hours',
            'support_email': 'support@bmasiamusic.com',

            # Other variables
            'login_url': 'https://example.com/login',
            'start_date': '2025-01-01',
        }

        # Render template
        rendered = template.render(sample_context)

        return Response({
            'subject': rendered['subject'],
            'body_text': rendered['body_text'],
            'body_html': rendered['body_html'],
            'sample_context': sample_context
        })

    @action(detail=False, methods=['get'])
    def variables(self, request):
        """
        GET /api/v1/email-templates/variables/?template_type=renewal_30_days
        Returns list of available variables for a template type
        """
        template_type = request.query_params.get('template_type')

        if not template_type:
            return Response(
                {'error': 'template_type query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Common variables available to all templates
        common_vars = [
            {'name': 'company_name', 'description': 'Company name', 'example': 'Acme Corp'},
            {'name': 'contact_name', 'description': 'Contact person name', 'example': 'John Doe'},
            {'name': 'current_year', 'description': 'Current year', 'example': '2025'},
            {'name': 'unsubscribe_url', 'description': 'Unsubscribe link', 'example': 'https://example.com/unsubscribe'},
        ]

        # Template-type specific variables
        type_vars_map = {
            # Renewal templates
            'renewal_30_days': [
                {'name': 'contract_number', 'description': 'Contract number', 'example': 'C-2025-001'},
                {'name': 'end_date', 'description': 'Contract end date', 'example': '2025-12-31'},
                {'name': 'days_until_expiry', 'description': 'Days until contract expires', 'example': '30'},
                {'name': 'monthly_value', 'description': 'Monthly contract value', 'example': '$500'},
            ],
            'renewal_14_days': [
                {'name': 'contract_number', 'description': 'Contract number', 'example': 'C-2025-001'},
                {'name': 'end_date', 'description': 'Contract end date', 'example': '2025-12-31'},
                {'name': 'days_until_expiry', 'description': 'Days until contract expires', 'example': '14'},
                {'name': 'monthly_value', 'description': 'Monthly contract value', 'example': '$500'},
            ],
            'renewal_7_days': [
                {'name': 'contract_number', 'description': 'Contract number', 'example': 'C-2025-001'},
                {'name': 'end_date', 'description': 'Contract end date', 'example': '2025-12-31'},
                {'name': 'days_until_expiry', 'description': 'Days until contract expires', 'example': '7'},
                {'name': 'monthly_value', 'description': 'Monthly contract value', 'example': '$500'},
            ],
            'renewal_urgent': [
                {'name': 'contract_number', 'description': 'Contract number', 'example': 'C-2025-001'},
                {'name': 'end_date', 'description': 'Contract end date', 'example': '2025-12-31'},
                {'name': 'days_until_expiry', 'description': 'Days until contract expires', 'example': '3'},
                {'name': 'monthly_value', 'description': 'Monthly contract value', 'example': '$500'},
            ],
            # Invoice templates
            'invoice_new': [
                {'name': 'invoice_number', 'description': 'Invoice number', 'example': 'INV-2025-001'},
                {'name': 'due_date', 'description': 'Payment due date', 'example': '2025-02-15'},
                {'name': 'total_amount', 'description': 'Total invoice amount', 'example': '$1,500'},
                {'name': 'payment_url', 'description': 'Payment link', 'example': 'https://example.com/pay'},
            ],
            'payment_reminder_7_days': [
                {'name': 'invoice_number', 'description': 'Invoice number', 'example': 'INV-2025-001'},
                {'name': 'due_date', 'description': 'Payment due date', 'example': '2025-02-15'},
                {'name': 'total_amount', 'description': 'Total invoice amount', 'example': '$1,500'},
                {'name': 'payment_url', 'description': 'Payment link', 'example': 'https://example.com/pay'},
                {'name': 'days_overdue', 'description': 'Days payment is overdue', 'example': '7'},
            ],
            'payment_reminder_14_days': [
                {'name': 'invoice_number', 'description': 'Invoice number', 'example': 'INV-2025-001'},
                {'name': 'due_date', 'description': 'Payment due date', 'example': '2025-02-15'},
                {'name': 'total_amount', 'description': 'Total invoice amount', 'example': '$1,500'},
                {'name': 'payment_url', 'description': 'Payment link', 'example': 'https://example.com/pay'},
                {'name': 'days_overdue', 'description': 'Days payment is overdue', 'example': '14'},
            ],
            'payment_overdue': [
                {'name': 'invoice_number', 'description': 'Invoice number', 'example': 'INV-2025-001'},
                {'name': 'due_date', 'description': 'Payment due date', 'example': '2025-02-15'},
                {'name': 'total_amount', 'description': 'Total invoice amount', 'example': '$1,500'},
                {'name': 'payment_url', 'description': 'Payment link', 'example': 'https://example.com/pay'},
                {'name': 'days_overdue', 'description': 'Days payment is overdue', 'example': '30'},
            ],
            # Zone offline templates
            'zone_offline_48h': [
                {'name': 'zone_name', 'description': 'Zone name', 'example': 'Main Restaurant'},
                {'name': 'offline_duration', 'description': 'How long zone has been offline', 'example': '48 hours'},
                {'name': 'support_email', 'description': 'Support contact email', 'example': 'support@bmasiamusic.com'},
            ],
            'zone_offline_7d': [
                {'name': 'zone_name', 'description': 'Zone name', 'example': 'Main Restaurant'},
                {'name': 'offline_duration', 'description': 'How long zone has been offline', 'example': '7 days'},
                {'name': 'support_email', 'description': 'Support contact email', 'example': 'support@bmasiamusic.com'},
            ],
            # General templates
            'welcome': [
                {'name': 'login_url', 'description': 'Login URL', 'example': 'https://example.com/login'},
            ],
            'contract_signed': [
                {'name': 'contract_number', 'description': 'Contract number', 'example': 'C-2025-001'},
                {'name': 'start_date', 'description': 'Contract start date', 'example': '2025-01-01'},
            ],
        }

        # Get template-specific variables
        type_vars = type_vars_map.get(template_type, [])

        return Response({
            'template_type': template_type,
            'variables': common_vars + type_vars
        })

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        POST /api/v1/email-templates/{id}/duplicate/
        Returns template data for duplication (frontend creates new template with different type)
        Note: Since template_type is unique, actual duplication must be done via POST /api/v1/email-templates/
        """
        original = self.get_object()

        # Return template data that can be used to create a new template
        # The frontend should create a new template with a different template_type
        return Response({
            'message': 'Use this data to create a new template with a different template type',
            'template_data': {
                'name': f"{original.name} (Copy)",
                'subject': original.subject,
                'body_text': original.body_text,
                'body_html': original.body_html,
                'language': original.language,
                'department': original.department,
                'is_active': False,
                'notes': f"Duplicated from {original.name}",
            }
        })


class EmailSequenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for EmailSequence model.
    Provides CRUD operations for email sequences.
    """
    queryset = EmailSequence.objects.all().prefetch_related('steps')
    serializer_class = EmailSequenceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        """Auto-set created_by to current user"""
        serializer.save(created_by=self.request.user)


class SequenceStepViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SequenceStep model.
    Provides CRUD operations for sequence steps.
    """
    queryset = SequenceStep.objects.all().select_related('sequence', 'email_template')
    serializer_class = SequenceStepSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['sequence', 'is_active']
    search_fields = ['name']
    ordering_fields = ['step_number', 'created_at']
    ordering = ['sequence', 'step_number']


class SequenceEnrollmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SequenceEnrollment model.
    Provides CRUD operations plus custom actions for enrollment management.
    """
    queryset = SequenceEnrollment.objects.all().select_related(
        'sequence', 'contact', 'company'
    ).prefetch_related('step_executions')
    serializer_class = SequenceEnrollmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'sequence', 'contact']
    search_fields = ['contact__email', 'contact__first_name', 'contact__last_name', 'company__name']
    ordering_fields = ['enrolled_at', 'started_at']
    ordering = ['-enrolled_at']

    @action(detail=False, methods=['post'])
    def enroll(self, request):
        """
        Enroll a contact in a sequence.

        Request body:
        {
            "sequence_id": "uuid",
            "contact_id": "uuid",
            "company_id": "uuid" (optional),
            "notes": "string" (optional)
        }
        """
        from crm_app.services.email_service import EmailService

        sequence_id = request.data.get('sequence_id')
        contact_id = request.data.get('contact_id')
        company_id = request.data.get('company_id')
        notes = request.data.get('notes', '')

        if not sequence_id or not contact_id:
            return Response(
                {'error': 'sequence_id and contact_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            email_service = EmailService()
            enrollment = email_service.enroll_contact_in_sequence(
                sequence_id=sequence_id,
                contact_id=contact_id,
                company_id=company_id,
                notes=notes
            )

            serializer = self.get_serializer(enrollment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to enroll contact: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def unenroll(self, request, pk=None):
        """
        Unenroll a contact from a sequence.

        Request body:
        {
            "reason": "manual" (optional)
        }
        """
        from crm_app.services.email_service import EmailService

        enrollment = self.get_object()
        reason = request.data.get('reason', 'manual')

        try:
            email_service = EmailService()
            success = email_service.unenroll_contact(
                enrollment_id=enrollment.id,
                reason=reason
            )

            if success:
                # Refresh from database
                enrollment.refresh_from_db()
                serializer = self.get_serializer(enrollment)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'Failed to unenroll contact'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            return Response(
                {'error': f'Failed to unenroll contact: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SequenceStepExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for SequenceStepExecution model.
    Read-only ViewSet for viewing execution logs.
    """
    queryset = SequenceStepExecution.objects.all().select_related(
        'enrollment__contact',
        'enrollment__sequence',
        'step',
        'email_log'
    )
    serializer_class = SequenceStepExecutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'enrollment', 'step']
    search_fields = ['enrollment__contact__email', 'step__name']
    ordering_fields = ['scheduled_for', 'sent_at']
    ordering = ['-scheduled_for']


class CustomerSegmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CustomerSegment model.
    Provides CRUD operations plus custom actions for segment management.
    """
    queryset = CustomerSegment.objects.all().select_related('created_by')
    serializer_class = CustomerSegmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'segment_type', 'created_by']
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['created_at', 'name', 'member_count', 'last_used_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter based on user role"""
        queryset = super().get_queryset()
        user = self.request.user

        # Non-admins only see their own segments + active public segments
        if user.role != 'Admin':
            queryset = queryset.filter(
                Q(created_by=user) | Q(status='active')
            )

        return queryset

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """
        Get all members of this segment.

        Query params:
        - limit: Max number of results (default: 100)
        - offset: Pagination offset
        """
        segment = self.get_object()
        limit = int(request.query_params.get('limit', 100))
        offset = int(request.query_params.get('offset', 0))

        try:
            members = segment.get_members()
            total_count = members.count()

            # Paginate
            members_page = members[offset:offset+limit]

            # Serialize
            serializer = ContactSerializer(members_page, many=True, context={'request': request})

            return Response({
                'count': total_count,
                'results': serializer.data,
                'segment_name': segment.name,
                'segment_type': segment.segment_type,
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """
        Manually recalculate segment member count.
        Useful after bulk data changes.
        """
        segment = self.get_object()

        try:
            new_count = segment.update_member_count()

            return Response({
                'message': 'Segment recalculated successfully',
                'member_count': new_count,
                'last_calculated_at': segment.last_calculated_at,
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def enroll_in_sequence(self, request, pk=None):
        """
        Enroll all segment members in an email sequence.

        Request body:
        {
            "sequence_id": "uuid",
            "notes": "string" (optional)
        }
        """
        from crm_app.services.email_service import EmailService

        segment = self.get_object()
        sequence_id = request.data.get('sequence_id')
        notes = request.data.get('notes', f'Enrolled via segment: {segment.name}')

        if not sequence_id:
            return Response(
                {'error': 'sequence_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify sequence exists
        try:
            sequence = EmailSequence.objects.get(id=sequence_id)
        except EmailSequence.DoesNotExist:
            return Response(
                {'error': 'Email sequence not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all segment members
        try:
            members = segment.get_members()
        except Exception as e:
            return Response(
                {'error': f'Error getting segment members: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        email_service = EmailService()
        enrolled_count = 0
        skipped_count = 0
        errors = []

        for contact in members:
            try:
                # Check if already enrolled
                existing = SequenceEnrollment.objects.filter(
                    sequence=sequence,
                    contact=contact
                ).exists()

                if existing:
                    skipped_count += 1
                    continue

                # Enroll contact
                email_service.enroll_in_sequence(
                    company=contact.company,
                    contact=contact,
                    sequence=sequence,
                    enrolled_by=request.user
                )
                enrolled_count += 1

            except Exception as e:
                errors.append(f'{contact.email}: {str(e)}')
                skipped_count += 1

        # Mark segment as used
        try:
            segment.mark_as_used()
        except Exception:
            pass  # Don't fail if tracking fails

        return Response({
            'message': f'Enrolled {enrolled_count} contacts in sequence',
            'enrolled_count': enrolled_count,
            'skipped_count': skipped_count,
            'total_members': members.count(),
            'errors': errors[:10],  # Limit error list
            'sequence_name': sequence.name,
            'segment_name': segment.name,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Duplicate this segment with a new name.

        Request body:
        {
            "name": "New Segment Name"
        }
        """
        segment = self.get_object()
        new_name = request.data.get('name')

        if not new_name:
            return Response(
                {'error': 'name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check name uniqueness
        if CustomerSegment.objects.filter(name=new_name).exists():
            return Response(
                {'error': 'Segment with this name already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Clone segment
        new_segment = CustomerSegment.objects.create(
            name=new_name,
            description=f'Cloned from: {segment.name}',
            segment_type=segment.segment_type,
            status='active',
            filter_criteria=segment.filter_criteria.copy() if segment.filter_criteria else {},
            created_by=request.user,
            tags=segment.tags,
        )

        # Copy static members if static segment
        if segment.segment_type == 'static':
            new_segment.static_contacts.set(segment.static_contacts.all())
            new_segment.static_companies.set(segment.static_companies.all())

        # Calculate member count
        try:
            new_segment.update_member_count()
        except Exception:
            pass  # Don't fail if calculation fails

        serializer = self.get_serializer(new_segment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def validate_filters(self, request):
        """
        Validate filter criteria and return estimated member count.
        Used for preview before saving.

        Request body:
        {
            "filter_criteria": {...}
        }
        """
        filter_criteria = request.data.get('filter_criteria')

        if not filter_criteria:
            return Response(
                {'error': 'filter_criteria is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create temporary segment (don't save)
        temp_segment = CustomerSegment(
            name='temp',
            segment_type='dynamic',
            filter_criteria=filter_criteria
        )

        try:
            members = temp_segment.get_members()
            count = members.count()
            preview = members[:5]

            return Response({
                'valid': True,
                'estimated_count': count,
                'preview': ContactSerializer(preview, many=True, context={'request': request}).data
            })
        except Exception as e:
            return Response({
                'valid': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# Support Ticket System ViewSets
class TicketViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing support tickets with filtering, search, and custom actions.
    Provides comprehensive ticket management including assignment, comments, and statistics.
    """
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'priority', 'category', 'company', 'assigned_to']
    search_fields = ['ticket_number', 'subject', 'description', 'company__name']
    ordering_fields = ['created_at', 'priority', 'status', 'due_date']
    ordering = ['-created_at']

    def get_queryset(self):
        """Apply custom filters and optimize queries"""
        queryset = super().get_queryset()

        # Custom filters from query parameters
        assigned_team = self.request.query_params.get('assigned_team', None)
        my_tickets = self.request.query_params.get('my_tickets', None)
        unassigned = self.request.query_params.get('unassigned', None)
        open_tickets = self.request.query_params.get('open', None)

        # Filter by team
        if assigned_team:
            queryset = queryset.filter(assigned_team=assigned_team)

        # Filter by current user's assigned tickets
        if my_tickets == 'true' and self.request.user.is_authenticated:
            queryset = queryset.filter(assigned_to=self.request.user)

        # Filter unassigned tickets
        if unassigned == 'true':
            queryset = queryset.filter(assigned_to__isnull=True)

        # Filter open tickets (exclude resolved and closed)
        if open_tickets == 'true':
            queryset = queryset.exclude(status__in=['resolved', 'closed'])

        # Optimize with select_related and prefetch_related
        queryset = queryset.select_related(
            'company', 'contact', 'assigned_to', 'created_by'
        ).prefetch_related('comments', 'attachments')

        return queryset

    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """
        Add a comment to a ticket.

        Request body:
        {
            "text": "Comment text here",
            "is_internal": false
        }
        """
        ticket = self.get_object()
        text = request.data.get('text')
        is_internal = request.data.get('is_internal', False)

        if not text:
            return Response(
                {'error': 'text is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Create the comment
            comment = TicketComment.objects.create(
                ticket=ticket,
                author=request.user,
                text=text,
                is_internal=is_internal
            )

            # Return updated ticket with new comment
            serializer = self.get_serializer(ticket)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Assign or unassign a ticket to a user.

        Request body:
        {
            "user_id": "uuid-string"  // or null to unassign
        }
        """
        ticket = self.get_object()
        user_id = request.data.get('user_id')

        try:
            if user_id:
                # Assign to user
                user = User.objects.get(pk=user_id)
                ticket.assigned_to = user
                ticket.assigned_team = user.role
                ticket.status = 'assigned'
            else:
                # Unassign ticket
                ticket.assigned_to = None
                ticket.assigned_team = ''
                ticket.status = 'new'

            ticket.save()

            # Return updated ticket
            serializer = self.get_serializer(ticket)
            return Response(serializer.data)

        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get ticket statistics including counts by status, priority, and user.

        Returns:
        {
            "total": 150,
            "by_status": {"new": 20, "assigned": 30, ...},
            "by_priority": {"low": 10, "medium": 50, ...},
            "my_open_tickets": 5,
            "unassigned": 10,
            "overdue": 3
        }
        """
        queryset = self.get_queryset()

        # Total tickets
        total = queryset.count()

        # Count by status
        by_status = {}
        for status_choice in Ticket.STATUS_CHOICES:
            status_key = status_choice[0]
            by_status[status_key] = queryset.filter(status=status_key).count()

        # Count by priority
        by_priority = {}
        for priority_choice in Ticket.PRIORITY_CHOICES:
            priority_key = priority_choice[0]
            by_priority[priority_key] = queryset.filter(priority=priority_key).count()

        # My open tickets
        my_open_tickets = 0
        if request.user.is_authenticated:
            my_open_tickets = queryset.filter(
                assigned_to=request.user
            ).exclude(status__in=['resolved', 'closed']).count()

        # Unassigned tickets
        unassigned = queryset.filter(assigned_to__isnull=True).count()

        # Overdue tickets (using property, so need to iterate)
        overdue_count = 0
        for ticket in queryset.exclude(status__in=['resolved', 'closed']):
            if ticket.is_overdue:
                overdue_count += 1

        return Response({
            'total': total,
            'by_status': by_status,
            'by_priority': by_priority,
            'my_open_tickets': my_open_tickets,
            'unassigned': unassigned,
            'overdue': overdue_count
        })


class TicketCommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ticket comments.
    Supports filtering by ticket and auto-sets author from request user.
    """
    queryset = TicketComment.objects.all()
    serializer_class = TicketCommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter by ticket if provided"""
        queryset = super().get_queryset()

        # Filter by ticket if provided in query params
        ticket_id = self.request.query_params.get('ticket', None)
        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id)

        # Optimize with select_related
        queryset = queryset.select_related('author', 'ticket')

        return queryset


class TicketAttachmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ticket file attachments.
    Supports file uploads with metadata tracking.
    """
    queryset = TicketAttachment.objects.all()
    serializer_class = TicketAttachmentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        """Handle file upload with metadata"""
        try:
            # Get file from request
            file = request.FILES.get('file')
            if not file:
                return Response(
                    {'error': 'file is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get ticket_id from request data
            ticket_id = request.data.get('ticket')
            if not ticket_id:
                return Response(
                    {'error': 'ticket is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verify ticket exists
            try:
                ticket = Ticket.objects.get(pk=ticket_id)
            except Ticket.DoesNotExist:
                return Response(
                    {'error': 'Ticket not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Create attachment
            attachment = TicketAttachment.objects.create(
                ticket=ticket,
                file=file,
                name=file.name,
                size=file.size,
                uploaded_by=request.user
            )

            # Serialize and return
            serializer = self.get_serializer(attachment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ============================================================================
# Knowledge Base System ViewSets
# ============================================================================

class KBCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing KB categories with hierarchical support.
    Supports parent/child relationships and active/inactive filtering.
    """
    queryset = KBCategory.objects.all().prefetch_related('parent', 'children')
    serializer_class = KBCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'parent']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'display_order']
    ordering = ['display_order', 'name']


class KBTagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing KB tags.
    Simple CRUD operations for article tagging.
    """
    queryset = KBTag.objects.all().order_by('name')
    serializer_class = KBTagSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering = ['name']


class KBArticleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing KB articles with full-text search and analytics.
    Supports custom actions for view tracking, ratings, and related articles.
    """
    queryset = KBArticle.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'visibility', 'category', 'featured', 'tags']
    search_fields = ['article_number', 'title', 'content', 'excerpt']
    ordering_fields = ['created_at', 'updated_at', 'published_at', 'view_count', 'helpful_count']
    ordering = ['-published_at', '-created_at']

    def get_queryset(self):
        """Optimize queryset with select_related and prefetch_related"""
        queryset = super().get_queryset()
        queryset = queryset.select_related('category', 'author').prefetch_related(
            'tags',
            'attachments',
            'outgoing_relations__to_article'
        )
        return queryset

    def get_serializer_class(self):
        """Use lightweight serializer for list views"""
        if self.action == 'list':
            return KBArticleListSerializer
        return KBArticleSerializer

    @action(detail=True, methods=['post'])
    def record_view(self, request, pk=None):
        """
        Record article view for analytics.
        POST /api/v1/kb/articles/{id}/record_view/
        Body: { "session_id": "unique-session-id" }
        """
        article = self.get_object()
        session_id = request.data.get('session_id')

        if not session_id:
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')

        # Create view record (unique constraint prevents duplicates)
        try:
            view_record = KBArticleView.objects.create(
                article=article,
                user=request.user if request.user.is_authenticated else None,
                ip_address=ip_address,
                session_id=session_id
            )

            # Increment view count
            article.view_count += 1
            article.save(update_fields=['view_count'])

            return Response({
                'message': 'View recorded',
                'view_count': article.view_count
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            # View already exists for this session
            return Response({
                'message': 'View already recorded for this session',
                'view_count': article.view_count
            }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        """
        Rate article as helpful or not helpful.
        POST /api/v1/kb/articles/{id}/rate/
        Body: { "is_helpful": true/false }
        """
        article = self.get_object()
        is_helpful = request.data.get('is_helpful')

        if is_helpful is None:
            return Response(
                {'error': 'is_helpful field is required (true or false)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create or update rating
        rating, created = KBArticleRating.objects.update_or_create(
            article=article,
            user=request.user,
            defaults={'is_helpful': is_helpful}
        )

        # Recalculate counts
        article.helpful_count = article.ratings.filter(is_helpful=True).count()
        article.not_helpful_count = article.ratings.filter(is_helpful=False).count()
        article.save(update_fields=['helpful_count', 'not_helpful_count'])

        return Response({
            'message': 'Rating saved' if created else 'Rating updated',
            'helpful_count': article.helpful_count,
            'not_helpful_count': article.not_helpful_count,
            'helpfulness_ratio': article.get_helpfulness_ratio()
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        """
        Get related articles.
        GET /api/v1/kb/articles/{id}/related/
        """
        article = self.get_object()
        relations = article.outgoing_relations.select_related('to_article').all()

        related_articles = []
        for relation in relations:
            related_articles.append({
                'id': relation.to_article.id,
                'article_number': relation.to_article.article_number,
                'title': relation.to_article.title,
                'slug': relation.to_article.slug,
                'relation_type': relation.relation_type,
                'relation_type_display': relation.get_relation_type_display()
            })

        return Response(related_articles)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def add_attachment(self, request, pk=None):
        """
        Upload file attachment to article.
        POST /api/v1/kb/articles/{id}/add_attachment/
        Body: multipart/form-data with 'file' field
        """
        article = self.get_object()
        file = request.FILES.get('file')

        if not file:
            return Response(
                {'error': 'file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create attachment
        attachment = KBArticleAttachment.objects.create(
            article=article,
            file=file,
            filename=file.name,
            file_size=file.size,
            uploaded_by=request.user
        )

        serializer = KBArticleAttachmentSerializer(attachment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def link_to_ticket(self, request, pk=None):
        """
        Link article to a support ticket.
        POST /api/v1/kb/articles/{id}/link_to_ticket/
        Body: { "ticket_id": "uuid", "is_helpful": true/false (optional) }
        """
        article = self.get_object()
        ticket_id = request.data.get('ticket_id')
        is_helpful = request.data.get('is_helpful')

        if not ticket_id:
            return Response(
                {'error': 'ticket_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify ticket exists
        try:
            ticket = Ticket.objects.get(pk=ticket_id)
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Create or update link
        link, created = TicketKBArticle.objects.update_or_create(
            ticket=ticket,
            article=article,
            defaults={
                'linked_by': request.user,
                'is_helpful': is_helpful
            }
        )

        serializer = TicketKBArticleSerializer(link)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Full-text search using PostgreSQL search_vector.
        GET /api/v1/kb/articles/search/?q=query
        Falls back to simple filtering on SQLite.
        """
        query = request.query_params.get('q', '').strip()

        if not query:
            return Response(
                {'error': 'q parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check database vendor
        from django.db import connection

        if connection.vendor == 'postgresql':
            # Use full-text search on PostgreSQL
            from django.contrib.postgres.search import SearchQuery
            search_query = SearchQuery(query)
            queryset = self.get_queryset().filter(
                search_vector=search_query,
                status='published'
            )
        else:
            # Fallback to icontains on SQLite
            queryset = self.get_queryset().filter(
                Q(title__icontains=query) | Q(content__icontains=query),
                status='published'
            )

        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = KBArticleListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = KBArticleListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Get featured articles.
        GET /api/v1/kb/articles/featured/
        """
        queryset = self.get_queryset().filter(
            status='published',
            featured=True
        ).order_by('-published_at')[:10]

        serializer = KBArticleListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def popular(self, request):
        """
        Get most viewed articles.
        GET /api/v1/kb/articles/popular/?limit=10
        """
        limit = int(request.query_params.get('limit', 10))
        queryset = self.get_queryset().filter(
            status='published'
        ).order_by('-view_count')[:limit]

        serializer = KBArticleListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def helpful(self, request):
        """
        Get most helpful articles.
        GET /api/v1/kb/articles/helpful/?limit=10
        """
        limit = int(request.query_params.get('limit', 10))
        queryset = self.get_queryset().filter(
            status='published'
        ).order_by('-helpful_count')[:limit]

        serializer = KBArticleListSerializer(queryset, many=True)
        return Response(serializer.data)


class KBArticleViewViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for KB article view analytics.
    Used for tracking and reporting purposes.
    """
    queryset = KBArticleView.objects.all().select_related('article', 'user')
    serializer_class = KBArticleViewSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['article', 'user', 'viewed_at']
    ordering = ['-viewed_at']


class KBArticleRatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing KB article ratings.
    Enforces unique constraint: one vote per user per article.
    """
    queryset = KBArticleRating.objects.all().select_related('article', 'user')
    serializer_class = KBArticleRatingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['article', 'user', 'is_helpful']
    ordering = ['-created_at']

    def create(self, request, *args, **kwargs):
        """
        Create rating with validation for unique constraint.
        Auto-sets user from request.
        """
        # Auto-set user from request
        data = request.data.copy()
        data['user'] = request.user.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class KBArticleRelationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing relationships between KB articles.
    Validates that articles cannot be related to themselves.
    """
    queryset = KBArticleRelation.objects.all().select_related('from_article', 'to_article')
    serializer_class = KBArticleRelationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['from_article', 'to_article', 'relation_type']
    ordering = ['from_article', 'display_order']


class KBArticleAttachmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing KB article file attachments.
    Supports file uploads with metadata tracking.
    """
    queryset = KBArticleAttachment.objects.all().select_related('article', 'uploaded_by')
    serializer_class = KBArticleAttachmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['article']
    ordering = ['-uploaded_at']
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        """
        Handle file upload with automatic metadata population.
        Auto-sets uploaded_by from request user.
        """
        # Validate file is present
        if 'file' not in request.FILES:
            return Response(
                {'error': 'file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Auto-set uploaded_by
        data = request.data.copy()
        # uploaded_by is auto-set in serializer.create()

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class TicketKBArticleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for linking KB articles to support tickets.
    Tracks which articles were helpful for resolving tickets.
    """
    queryset = TicketKBArticle.objects.all().select_related('ticket', 'article', 'linked_by')
    serializer_class = TicketKBArticleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['ticket', 'article', 'is_helpful']
    ordering = ['-linked_at']

    def create(self, request, *args, **kwargs):
        """
        Create ticket-article link.
        Auto-sets linked_by from request user.
        """
        # Auto-set linked_by
        data = request.data.copy()
        # linked_by is auto-set in serializer.create()

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# ============================================================================
# Equipment Management ViewSets - REMOVED (replaced by simpler Device model)
# ============================================================================


class DeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Device model - simple device tracking.
    """
    queryset = Device.objects.select_related('company').prefetch_related('zones')
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['company', 'device_type']
    search_fields = ['name', 'model_info', 'notes']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    @action(detail=False, methods=['get'])
    def by_company(self, request):
        """Get devices for a specific company"""
        company_id = request.query_params.get('company_id')
        if not company_id:
            return Response({'error': 'company_id required'}, status=400)
        devices = self.queryset.filter(company_id=company_id)
        serializer = self.get_serializer(devices, many=True)
        return Response(serializer.data)


class ZoneViewSet(viewsets.ModelViewSet):
    """ViewSet for Zone model with company filtering"""
    queryset = Zone.objects.select_related('company')
    serializer_class = ZoneSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['company', 'platform', 'status']
    search_fields = ['name', 'company__name']
    ordering = ['company__name', 'name']

    @action(detail=False, methods=['get'])
    def by_company(self, request):
        """Get zones filtered by company - for equipment form dropdown"""
        company_id = request.query_params.get('company_id')
        if not company_id:
            return Response(
                {'error': 'company_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        zones = self.queryset.filter(company_id=company_id)
        serializer = self.get_serializer(zones, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='contracts')
    def get_contracts(self, request, pk=None):
        """
        Get all contracts (active and historical) for this zone.

        GET /api/v1/zones/{id}/contracts/
        Query params:
        - active: true/false (filter by is_active)

        Returns: List of ContractZone relationships
        """
        zone = self.get_object()

        # Filter by active status if specified
        active_filter = request.query_params.get('active')
        if active_filter is not None:
            is_active = active_filter.lower() == 'true'
            queryset = zone.zone_contracts.filter(is_active=is_active)
        else:
            queryset = zone.zone_contracts.all()

        queryset = queryset.select_related('contract', 'zone').order_by('-start_date')
        serializer = ContractZoneSerializer(queryset, many=True)
        return Response(serializer.data)