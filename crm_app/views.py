from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth import login, logout
from rest_framework.authtoken.models import Token
from django.db import transaction
from django.http import HttpResponse
import csv
import json

from .models import (
    User, Company, Contact, Note, Task, AuditLog,
    Opportunity, OpportunityActivity, Contract, Invoice
)
from .serializers import (
    UserSerializer, CompanySerializer, ContactSerializer, NoteSerializer,
    TaskSerializer, OpportunitySerializer, OpportunityActivitySerializer,
    ContractSerializer, InvoiceSerializer, AuditLogSerializer,
    LoginSerializer, DashboardStatsSerializer, BulkOperationSerializer
)
from .permissions import (
    RoleBasedPermission, DepartmentPermission, CompanyAccessPermission,
    TaskAssigneePermission, ReadOnlyForNonOwner
)


class BaseModelViewSet(viewsets.ModelViewSet):
    """Base viewset with common functionality"""
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    def get_queryset(self):
        """Override to apply role-based filtering"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Admin sees everything
        if user.role == 'Admin':
            return queryset
        
        # Apply role-based filtering
        if user.role == 'Sales':
            # Sales sees companies they have opportunities for
            if self.basename == 'company':
                company_ids = Opportunity.objects.filter(owner=user).values_list('company_id', flat=True)
                return queryset.filter(Q(id__in=company_ids) | Q(opportunities__owner=user)).distinct()
        
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
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    search_fields = ['name', 'website', 'notes', 'zone']
    ordering_fields = ['name', 'created_at', 'zone', 'industry']
    ordering = ['name']
    permission_classes = [IsAuthenticated, CompanyAccessPermission]
    filterset_fields = ['zone', 'industry', 'company_size', 'is_active']
    
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
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """User login"""
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        login(request, user)
        
        # Create or get token for API access
        token, created = Token.objects.get_or_create(user=user)
        
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
            'token': token.key,
            'user': UserSerializer(user).data
        })
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """User logout"""
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
            
            # Delete token
            Token.objects.filter(user=request.user).delete()
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
