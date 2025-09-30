from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Sum
from .models import (
    User, Company, Contact, Note, Task, AuditLog,
    Opportunity, OpportunityActivity, Contract, Invoice, Zone
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with role-based field access"""
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'department', 'is_active', 'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        # Hide sensitive fields from non-admin users
        if request and request.user.role != 'Admin':
            if request.user != instance:
                data.pop('phone', None)
                data.pop('email', None)
        
        return data


class ContactSerializer(serializers.ModelSerializer):
    """Serializer for Contact model with enhanced validation"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Contact
        fields = [
            'id', 'company', 'company_name', 'name', 'email', 'phone',
            'title', 'department', 'contact_type', 'is_primary', 'is_active',
            'linkedin_url', 'notes', 'last_contacted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_email(self, value):
        """Ensure email is unique within the company"""
        company = self.initial_data.get('company')
        if company:
            existing = Contact.objects.filter(
                company=company, 
                email=value
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "A contact with this email already exists for this company."
                )
        return value


class ZoneSerializer(serializers.ModelSerializer):
    """Serializer for Zone model"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    soundtrack_account_id = serializers.CharField(source='company.soundtrack_account_id', read_only=True)
    
    class Meta:
        model = Zone
        fields = [
            'id', 'company', 'company_name', 'name', 'platform', 'status', 'status_display',
            'soundtrack_account_id', 'soundtrack_zone_id', 'soundtrack_admin_email',
            'device_name', 'last_seen_online', 'notes', 'last_api_sync',
            'is_online', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'soundtrack_account_id', 'last_api_sync', 'created_at', 'updated_at']


# SubscriptionPlanSerializer removed - use ContractSerializer with service_type instead


class CompanySerializer(serializers.ModelSerializer):
    """Serializer for Company model with related data"""
    contacts = serializers.SerializerMethodField()
    zones = serializers.SerializerMethodField()
    zones_summary = serializers.SerializerMethodField()
    subscription_summary = serializers.SerializerMethodField()
    primary_contact = serializers.SerializerMethodField()
    total_contract_value = serializers.ReadOnlyField()
    full_address = serializers.ReadOnlyField()
    avg_zones_per_location = serializers.ReadOnlyField()
    opportunities_count = serializers.SerializerMethodField()
    active_contracts_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'country', 'website', 'industry',
            'location_count', 'music_zone_count', 'avg_zones_per_location',
            'soundtrack_account_id', 'is_active', 'notes',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'full_address', 'total_contract_value', 'contacts', 'zones', 'zones_summary',
            'subscription_summary', 'primary_contact', 'opportunities_count',
            'active_contracts_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        """Override to handle errors in nested serializers gracefully"""
        try:
            data = super().to_representation(instance)
            return data
        except Exception as e:
            # If complete serialization fails, return a minimal safe representation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error serializing company {instance.id}: {str(e)}")

            # Return minimal safe data
            return {
                'id': instance.id,
                'name': instance.name,
                'country': instance.country,
                'is_active': instance.is_active,
                'contacts': [],
                'zones': [],
                'zones_summary': 'Error loading data',
                'primary_contact': None,
                'opportunities_count': 0,
                'active_contracts_count': 0,
            }

    def get_contacts(self, obj):
        """Get all contacts with error handling"""
        try:
            contacts = obj.contacts.all()
            return ContactSerializer(contacts, many=True).data
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error serializing contacts for company {obj.id}: {str(e)}")
            return []

    def get_zones(self, obj):
        """Get all zones with error handling"""
        try:
            zones = obj.zones.all()
            return ZoneSerializer(zones, many=True).data
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error serializing zones for company {obj.id}: {str(e)}")
            return []

    def get_primary_contact(self, obj):
        try:
            primary = obj.contacts.filter(is_primary=True, is_active=True).first()
            if primary:
                return ContactSerializer(primary).data
            return None
        except Exception as e:
            # Log the error but don't crash the entire serialization
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error serializing primary contact for company {obj.id}: {str(e)}")
            return None

    def get_opportunities_count(self, obj):
        try:
            return obj.opportunities.filter(is_active=True).count()
        except Exception:
            return 0

    def get_active_contracts_count(self, obj):
        try:
            return obj.contracts.filter(is_active=True).count()
        except Exception:
            return 0
    
    def get_subscription_summary(self, obj):
        """Get a summary of active contracts/subscriptions"""
        try:
            active_contracts = obj.contracts.filter(is_active=True)
            if not active_contracts:
                return "No active subscriptions"

            contract_types = {}
            for contract in active_contracts:
                contract_type = contract.contract_type
                contract_types[contract_type] = contract_types.get(contract_type, 0) + 1

            summary_parts = []
            for contract_type, count in contract_types.items():
                if count > 1:
                    summary_parts.append(f"{count} {contract_type}")
                else:
                    summary_parts.append(contract_type)

            return ", ".join(summary_parts)
        except Exception:
            return "Error loading subscriptions"

    def get_zones_summary(self, obj):
        """Get a summary of zone statuses"""
        try:
            zones = obj.zones.all()
            if not zones:
                return "No zones configured"

            status_counts = {}
            for zone in zones:
                status = zone.get_status_display()
                status_counts[status] = status_counts.get(status, 0) + 1

            summary_parts = []
            for status, count in status_counts.items():
                summary_parts.append(f"{count} {status}")

            return ", ".join(summary_parts)
        except Exception:
            return "Error loading zones"


class NoteSerializer(serializers.ModelSerializer):
    """Serializer for Note model"""
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    
    class Meta:
        model = Note
        fields = [
            'id', 'company', 'company_name', 'author', 'author_name',
            'contact', 'contact_name', 'note_type', 'priority', 'title', 'text',
            'is_private', 'follow_up_date', 'tags', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model with enhanced fields"""
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'company', 'company_name', 'assigned_to', 'assigned_to_name',
            'created_by', 'created_by_name', 'department', 'title', 'description',
            'priority', 'status', 'due_date', 'completed_at', 'estimated_hours',
            'actual_hours', 'tags', 'is_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'completed_at', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class OpportunityActivitySerializer(serializers.ModelSerializer):
    """Serializer for OpportunityActivity model"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    
    class Meta:
        model = OpportunityActivity
        fields = [
            'id', 'opportunity', 'user', 'user_name', 'contact', 'contact_name',
            'activity_type', 'subject', 'description', 'duration_minutes',
            'outcome', 'next_steps', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class OpportunitySerializer(serializers.ModelSerializer):
    """Serializer for Opportunity model with analytics"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    weighted_value = serializers.ReadOnlyField()
    days_in_stage = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    activities = OpportunityActivitySerializer(many=True, read_only=True)
    recent_activities = serializers.SerializerMethodField()
    
    class Meta:
        model = Opportunity
        fields = [
            'id', 'company', 'company_name', 'name', 'stage', 'expected_value',
            'probability', 'owner', 'owner_name', 'lead_source', 'contact_method',
            'last_contact_date', 'follow_up_date', 'expected_close_date',
            'actual_close_date', 'notes', 'is_active', 'competitors',
            'pain_points', 'decision_criteria', 'weighted_value', 'days_in_stage',
            'is_overdue', 'activities', 'recent_activities', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_recent_activities(self, obj):
        recent = obj.activities.all()[:5]
        return OpportunityActivitySerializer(recent, many=True).data


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Invoice model"""
    contract_number = serializers.CharField(source='contract.contract_number', read_only=True)
    company_name = serializers.CharField(source='contract.company.name', read_only=True)
    days_overdue = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'contract', 'contract_number', 'company_name', 'invoice_number',
            'status', 'issue_date', 'due_date', 'paid_date', 'amount', 'tax_amount',
            'discount_amount', 'total_amount', 'currency', 'payment_method',
            'transaction_id', 'notes', 'days_overdue', 'is_overdue',
            'first_reminder_sent', 'second_reminder_sent', 'final_notice_sent',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_amount', 'created_at', 'updated_at']


class ContractSerializer(serializers.ModelSerializer):
    """Serializer for Contract model with renewal tracking"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    opportunity_name = serializers.CharField(source='opportunity.name', read_only=True)
    days_until_expiry = serializers.ReadOnlyField()
    is_expiring_soon = serializers.ReadOnlyField()
    monthly_value = serializers.ReadOnlyField()
    invoices = InvoiceSerializer(many=True, read_only=True)
    paid_invoices_count = serializers.SerializerMethodField()
    outstanding_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = [
            'id', 'company', 'company_name', 'opportunity', 'opportunity_name',
            'contract_number', 'contract_type', 'status', 'start_date', 'end_date',
            'value', 'currency', 'auto_renew', 'renewal_period_months', 'is_active',
            'payment_terms', 'billing_frequency', 'discount_percentage', 'notes',
            'renewal_notice_sent', 'renewal_notice_date', 'days_until_expiry',
            'is_expiring_soon', 'monthly_value', 'invoices', 'paid_invoices_count',
            'outstanding_amount', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_paid_invoices_count(self, obj):
        return obj.invoices.filter(status='Paid').count()
    
    def get_outstanding_amount(self, obj):
        outstanding = obj.invoices.exclude(status='Paid').aggregate(
            total=Sum('total_amount')
        )['total']
        return outstanding or 0


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'action', 'model_name', 'record_id',
            'timestamp', 'ip_address', 'user_agent', 'changes', 'additional_data'
        ]
        read_only_fields = ['id', 'timestamp']


class LoginSerializer(serializers.Serializer):
    """Serializer for user authentication"""
    username = serializers.CharField()
    password = serializers.CharField(style={'input_type': 'password'})
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            user = authenticate(
                request=self.context.get('request'),
                username=username,
                password=password
            )
            
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include username and password')


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    total_companies = serializers.IntegerField()
    active_opportunities = serializers.IntegerField()
    opportunities_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_contracts = serializers.IntegerField()
    contracts_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    overdue_tasks = serializers.IntegerField()
    overdue_invoices = serializers.IntegerField()
    pending_renewals = serializers.IntegerField()
    
    # Sales funnel stats
    contacted_count = serializers.IntegerField()
    quotation_count = serializers.IntegerField()
    contract_count = serializers.IntegerField()
    won_count = serializers.IntegerField()
    lost_count = serializers.IntegerField()
    
    # Monthly stats
    monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_new_opportunities = serializers.IntegerField()
    monthly_closed_deals = serializers.IntegerField()


class BulkOperationSerializer(serializers.Serializer):
    """Serializer for bulk operations"""
    action = serializers.ChoiceField(choices=[
        ('delete', 'Delete'),
        ('update_status', 'Update Status'),
        ('assign', 'Assign'),
        ('export', 'Export'),
    ])
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1
    )
    data = serializers.JSONField(required=False, help_text="Additional data for the operation")
    
    def validate(self, attrs):
        action = attrs.get('action')
        data = attrs.get('data', {})
        
        # Validate required data for specific actions
        if action == 'update_status' and 'status' not in data:
            raise serializers.ValidationError('Status is required for update_status action')
        
        if action == 'assign' and 'assigned_to' not in data:
            raise serializers.ValidationError('assigned_to is required for assign action')
        
        return attrs