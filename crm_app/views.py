from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
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
    Opportunity, OpportunityActivity, Contract, Invoice,
    Quote, QuoteLineItem, QuoteAttachment, QuoteActivity
)
from .serializers import (
    UserSerializer, CompanySerializer, ContactSerializer, NoteSerializer,
    TaskSerializer, OpportunitySerializer, OpportunityActivitySerializer,
    ContractSerializer, InvoiceSerializer, AuditLogSerializer,
    LoginSerializer, DashboardStatsSerializer, BulkOperationSerializer,
    QuoteSerializer, QuoteLineItemSerializer, QuoteAttachmentSerializer, QuoteActivitySerializer
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
        """Mark quote as sent"""
        quote = self.get_object()
        quote.status = 'Sent'
        quote.sent_date = timezone.now().date()
        quote.save()

        # Create activity
        QuoteActivity.objects.create(
            quote=quote,
            user=request.user if request.user.is_authenticated else None,
            activity_type='Sent',
            description=f'Quote {quote.quote_number} was sent to {quote.company.name}'
        )

        self.log_action('UPDATE', quote, {
            'status': {'old': 'Draft', 'new': 'Sent'}
        })

        return Response({'message': 'Quote marked as sent'})

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