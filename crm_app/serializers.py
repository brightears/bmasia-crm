from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Sum
from .models import (
    User, Company, Contact, Note, Task, AuditLog,
    Opportunity, OpportunityActivity, Contract, Invoice, Zone, ContractZone,
    Quote, QuoteLineItem, QuoteAttachment, QuoteActivity,
    EmailCampaign, CampaignRecipient, EmailTemplate,
    EmailSequence, SequenceStep, SequenceEnrollment, SequenceStepExecution,
    CustomerSegment, Ticket, TicketComment, TicketAttachment,
    KBCategory, KBTag, KBArticle, KBArticleView, KBArticleRating,
    KBArticleRelation, KBArticleAttachment, TicketKBArticle,
    Device, StaticDocument,
    ContractTemplate, ServicePackageItem, CorporatePdfTemplate, ContractDocument,
    SeasonalTriggerDate
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with role-based field access"""
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    smtp_configured = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'phone', 'department', 'is_active',
            'smtp_email', 'smtp_configured',  # Never expose smtp_password
            'last_login', 'date_joined', 'password'
        ]
        read_only_fields = ['id', 'last_login', 'date_joined']
        extra_kwargs = {
            'smtp_email': {'required': False},
        }

    def get_smtp_configured(self, obj):
        """Check if user has SMTP configured"""
        return bool(obj.smtp_email and obj.smtp_password)

    def get_full_name(self, obj):
        """Return full name or username as fallback"""
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def create(self, validated_data):
        """Create user with hashed password"""
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        """Update user with password hashing if provided"""
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')

        # Hide sensitive fields from non-admin users
        if request and request.user.is_authenticated and request.user.role != 'Admin':
            if request.user != instance:
                data.pop('phone', None)
                data.pop('email', None)
                data.pop('smtp_email', None)

        return data


class ContactSerializer(serializers.ModelSerializer):
    """Serializer for Contact model with enhanced validation"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Contact
        fields = [
            'id', 'company', 'company_name', 'name', 'email', 'phone',
            'title', 'department', 'contact_type', 'is_primary', 'is_active',
            'linkedin_url', 'notes', 'last_contacted', 'created_at', 'updated_at',
            # Granular email preferences
            'receives_renewal_emails', 'receives_seasonal_emails',
            'receives_payment_emails', 'receives_quarterly_emails'
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


class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for Device model"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    zone_count = serializers.IntegerField(read_only=True)
    zones = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            'id', 'company', 'company_name', 'name', 'device_type',
            'model_info', 'notes', 'zone_count', 'zones',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_zones(self, obj):
        """Return list of zone names running on this device"""
        return [{'id': str(z.id), 'name': z.name} for z in obj.zones.all()]


class ZoneSerializer(serializers.ModelSerializer):
    """Serializer for Zone model"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    device_display_name = serializers.CharField(source='device.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    soundtrack_account_id = serializers.CharField(source='company.soundtrack_account_id', read_only=True)

    # NEW FIELDS for contracts
    current_contract = serializers.SerializerMethodField()
    contract_count = serializers.SerializerMethodField()

    class Meta:
        model = Zone
        fields = [
            'id', 'company', 'company_name', 'device', 'device_display_name', 'name', 'platform',
            'status', 'status_display', 'soundtrack_account_id', 'soundtrack_zone_id',
            'soundtrack_admin_email', 'device_name', 'last_seen_online', 'notes', 'last_api_sync',
            'is_online', 'current_contract', 'contract_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'soundtrack_account_id', 'last_api_sync', 'created_at', 'updated_at']

    def get_current_contract(self, obj):
        """Get the currently active contract for this zone"""
        active_link = obj.zone_contracts.filter(is_active=True).select_related('contract').first()
        if active_link:
            return {
                'id': str(active_link.contract.id),
                'contract_number': active_link.contract.contract_number,
                'status': active_link.contract.status,
                'start_date': active_link.start_date,
                'end_date': active_link.end_date,
            }
        return None

    def get_contract_count(self, obj):
        """Total number of contracts this zone has been linked to"""
        return obj.zone_contracts.count()


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

    # Corporate structure fields
    parent_company_name = serializers.CharField(source='parent_company.name', read_only=True, allow_null=True)
    is_subsidiary = serializers.SerializerMethodField()
    child_companies_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'legal_entity_name', 'country', 'website', 'industry',
            'location_count', 'music_zone_count', 'avg_zones_per_location',
            'soundtrack_account_id', 'is_active', 'seasonal_emails_enabled', 'notes', 'it_notes',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            'billing_entity', 'full_address', 'total_contract_value', 'contacts', 'zones', 'zones_summary',
            'subscription_summary', 'primary_contact', 'opportunities_count',
            'active_contracts_count',
            # Corporate structure
            'parent_company', 'parent_company_name', 'is_corporate_parent',
            'is_subsidiary', 'child_companies_count',
            'created_at', 'updated_at'
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

    def get_is_subsidiary(self, obj):
        """Check if company is a subsidiary (has a parent)"""
        return obj.parent_company is not None

    def get_child_companies_count(self, obj):
        """Count of child companies (only for corporate parents)"""
        if obj.is_corporate_parent:
            return obj.child_companies.count()
        return 0


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


class ContractZoneSerializer(serializers.ModelSerializer):
    """
    Serializer for ContractZone intermediate model.
    Shows the relationship between a contract and a zone with historical tracking.
    """
    zone_id = serializers.UUIDField(source='zone.id', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    zone_platform = serializers.CharField(source='zone.platform', read_only=True)
    zone_status = serializers.CharField(source='zone.status', read_only=True)
    contract_number = serializers.CharField(source='contract.contract_number', read_only=True)
    company_name = serializers.CharField(source='contract.company.name', read_only=True)

    class Meta:
        model = ContractZone
        fields = [
            'id', 'contract', 'contract_number', 'zone', 'zone_id', 'zone_name',
            'zone_platform', 'zone_status', 'company_name',
            'start_date', 'end_date', 'is_active', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


# Contract Content Management Serializers (defined before ContractSerializer which uses them)
# ============================================================================

class ServicePackageItemSerializer(serializers.ModelSerializer):
    """Serializer for ServicePackageItem model"""
    class Meta:
        model = ServicePackageItem
        fields = ['id', 'name', 'description', 'is_standard', 'display_order']


class ContractDocumentSerializer(serializers.ModelSerializer):
    """Serializer for ContractDocument model"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True, default='')
    contract_number = serializers.CharField(source='contract.contract_number', read_only=True)

    class Meta:
        model = ContractDocument
        fields = ['id', 'contract', 'contract_number', 'document_type', 'title',
                  'file', 'is_official', 'is_signed', 'signed_date',
                  'uploaded_by', 'uploaded_by_name', 'uploaded_at', 'notes']
        read_only_fields = ['uploaded_at', 'uploaded_by']


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

    # NEW FIELDS for zones
    contract_zones = ContractZoneSerializer(many=True, read_only=True)
    active_zone_count = serializers.SerializerMethodField()
    total_zone_count = serializers.SerializerMethodField()

    # Corporate contract fields
    master_contract_number = serializers.CharField(source='master_contract.contract_number', read_only=True, allow_null=True)
    participation_agreements_count = serializers.SerializerMethodField()

    # Contract Content Management fields
    preamble_template_name = serializers.CharField(source='preamble_template.name', read_only=True, allow_null=True)
    payment_template_name = serializers.CharField(source='payment_template.name', read_only=True, allow_null=True)
    activation_template_name = serializers.CharField(source='activation_template.name', read_only=True, allow_null=True)
    service_items = serializers.PrimaryKeyRelatedField(many=True, queryset=ServicePackageItem.objects.all(), required=False)
    service_items_detail = ServicePackageItemSerializer(source='service_items', many=True, read_only=True)
    contract_documents = ContractDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Contract
        fields = [
            'id', 'company', 'company_name', 'opportunity', 'opportunity_name',
            'contract_number', 'contract_type', 'status', 'start_date', 'end_date',
            'value', 'currency', 'auto_renew', 'renewal_period_months', 'is_active',
            'payment_terms', 'billing_frequency', 'discount_percentage', 'notes',
            'renewal_notice_sent', 'renewal_notice_date', 'days_until_expiry',
            'is_expiring_soon', 'monthly_value', 'invoices', 'paid_invoices_count',
            'outstanding_amount', 'contract_zones', 'active_zone_count', 'total_zone_count',
            # Corporate contract fields
            'contract_category', 'master_contract', 'master_contract_number',
            'customer_signatory_name', 'customer_signatory_title',
            'bmasia_signatory_name', 'bmasia_signatory_title', 'custom_terms',
            'participation_agreements_count',
            # Contract Content Management fields
            'preamble_template', 'preamble_template_name', 'preamble_custom',
            'payment_template', 'payment_template_name', 'payment_custom',
            'activation_template', 'activation_template_name', 'activation_custom',
            'service_items', 'service_items_detail', 'custom_service_items',
            'show_zone_pricing_detail', 'price_per_zone',
            'bmasia_contact_name', 'bmasia_contact_email', 'bmasia_contact_title',
            'customer_contact_name', 'customer_contact_email', 'customer_contact_title',
            'contract_documents',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'contract_number', 'created_at', 'updated_at']
        extra_kwargs = {
            'contract_number': {'required': False}
        }

    def get_paid_invoices_count(self, obj):
        return obj.invoices.filter(status='Paid').count()

    def get_outstanding_amount(self, obj):
        outstanding = obj.invoices.exclude(status='Paid').aggregate(
            total=Sum('total_amount')
        )['total']
        return outstanding or 0

    def get_active_zone_count(self, obj):
        """Count of currently active zones"""
        return obj.contract_zones.filter(is_active=True).count()

    def get_total_zone_count(self, obj):
        """Total count of all zones (active + historical)"""
        return obj.contract_zones.count()

    def get_participation_agreements_count(self, obj):
        """Count of participation agreements under this master contract"""
        if obj.contract_category == 'corporate_master':
            return obj.participation_agreements.count()
        return 0

    def create(self, validated_data):
        """Create contract with auto-generated contract number"""
        # Auto-generate contract number if not provided
        if not validated_data.get('contract_number'):
            today = timezone.now().date()
            date_str = today.strftime('%Y-%m%d')
            # Count existing contracts for today
            count = Contract.objects.filter(
                contract_number__startswith=f'C-{date_str}'
            ).count() + 1
            validated_data['contract_number'] = f'C-{date_str}-{count:03d}'

        return super().create(validated_data)


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
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
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


class QuoteLineItemSerializer(serializers.ModelSerializer):
    """Serializer for QuoteLineItem model"""

    class Meta:
        model = QuoteLineItem
        fields = [
            'id', 'quote', 'product_service', 'description', 'quantity',
            'unit_price', 'discount_percentage', 'tax_rate', 'line_total',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'quote', 'line_total', 'created_at', 'updated_at']
        extra_kwargs = {
            'quote': {'required': False}  # Not required during nested creation
        }


class QuoteAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for QuoteAttachment model"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)

    class Meta:
        model = QuoteAttachment
        fields = [
            'id', 'quote', 'name', 'file', 'size', 'uploaded_by',
            'uploaded_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'size', 'created_at']


class QuoteActivitySerializer(serializers.ModelSerializer):
    """Serializer for QuoteActivity model"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = QuoteActivity
        fields = [
            'id', 'quote', 'user', 'user_name', 'activity_type',
            'description', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class QuoteSerializer(serializers.ModelSerializer):
    """Serializer for Quote model with nested line items and activities"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    opportunity_name = serializers.CharField(source='opportunity.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    is_expired = serializers.ReadOnlyField()
    days_until_expiry = serializers.ReadOnlyField()
    line_items = QuoteLineItemSerializer(many=True, required=False)
    attachments = QuoteAttachmentSerializer(many=True, read_only=True)
    activities = QuoteActivitySerializer(many=True, read_only=True)

    class Meta:
        model = Quote
        fields = [
            'id', 'quote_number', 'company', 'company_name', 'contact', 'contact_name',
            'opportunity', 'opportunity_name', 'status', 'valid_from', 'valid_until',
            'subtotal', 'tax_amount', 'discount_amount', 'total_value', 'currency',
            'terms_conditions', 'notes', 'is_expired', 'days_until_expiry',
            'sent_date', 'accepted_date', 'rejected_date', 'expired_date',
            'created_by', 'created_by_name', 'line_items', 'attachments', 'activities',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_expired', 'days_until_expiry', 'created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create quote with nested line items"""
        line_items_data = validated_data.pop('line_items', [])

        # Set created_by from request user
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user

        quote = Quote.objects.create(**validated_data)

        # Create line items
        for item_data in line_items_data:
            QuoteLineItem.objects.create(quote=quote, **item_data)

        # Create activity log
        QuoteActivity.objects.create(
            quote=quote,
            user=request.user if request and request.user.is_authenticated else None,
            activity_type='Created',
            description=f'Quote {quote.quote_number} was created'
        )

        return quote

    def update(self, instance, validated_data):
        """Update quote and handle nested line items"""
        line_items_data = validated_data.pop('line_items', None)

        # Track status changes for activity log
        old_status = instance.status
        new_status = validated_data.get('status', old_status)

        # Update quote fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update line items if provided
        if line_items_data is not None:
            # Delete existing line items
            instance.line_items.all().delete()

            # Create new line items
            for item_data in line_items_data:
                QuoteLineItem.objects.create(quote=instance, **item_data)

        # Create activity log for status changes
        request = self.context.get('request')
        if old_status != new_status:
            QuoteActivity.objects.create(
                quote=instance,
                user=request.user if request and request.user.is_authenticated else None,
                activity_type=new_status,
                description=f'Quote status changed from {old_status} to {new_status}'
            )
        else:
            QuoteActivity.objects.create(
                quote=instance,
                user=request.user if request and request.user.is_authenticated else None,
                activity_type='Updated',
                description=f'Quote {instance.quote_number} was updated'
            )

        return instance


class CampaignRecipientSerializer(serializers.ModelSerializer):
    """Serializer for CampaignRecipient model"""
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    contact_email = serializers.EmailField(source='contact.email', read_only=True)
    contact_company = serializers.CharField(source='contact.company.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CampaignRecipient
        fields = [
            'id', 'campaign', 'contact', 'contact_name', 'contact_email',
            'contact_company', 'email_log', 'status', 'status_display',
            'sent_at', 'delivered_at', 'opened_at', 'clicked_at',
            'bounced_at', 'failed_at', 'error_message',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'contact_name', 'contact_email', 'contact_company',
            'status_display', 'sent_at', 'delivered_at', 'opened_at',
            'clicked_at', 'bounced_at', 'failed_at', 'created_at', 'updated_at'
        ]


class EmailCampaignSerializer(serializers.ModelSerializer):
    """Serializer for EmailCampaign model with analytics"""
    campaign_type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True, allow_null=True)
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    bounce_rate = serializers.ReadOnlyField()
    recipients_count = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()
    sent_count = serializers.SerializerMethodField()
    failed_count = serializers.SerializerMethodField()

    class Meta:
        model = EmailCampaign
        fields = [
            'id', 'name', 'campaign_type', 'campaign_type_display',
            'subject', 'template', 'template_name',
            'target_audience', 'audience_count', 'recipients_count',
            'scheduled_send_date', 'actual_send_date', 'status', 'status_display',
            'send_immediately', 'sender_email', 'reply_to_email',
            'total_sent', 'total_delivered', 'total_bounced',
            'total_opened', 'total_clicked', 'total_unsubscribed', 'total_complained',
            'open_rate', 'click_rate', 'bounce_rate',
            'pending_count', 'sent_count', 'failed_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'campaign_type_display', 'status_display', 'template_name',
            'actual_send_date', 'open_rate', 'click_rate', 'bounce_rate',
            'total_sent', 'total_delivered', 'total_bounced',
            'total_opened', 'total_clicked', 'total_unsubscribed', 'total_complained',
            'recipients_count', 'pending_count', 'sent_count', 'failed_count',
            'created_at', 'updated_at'
        ]

    def get_recipients_count(self, obj):
        """Get total number of recipients"""
        return obj.recipients.count()

    def get_pending_count(self, obj):
        """Get number of pending recipients"""
        return obj.recipients.filter(status='pending').count()

    def get_sent_count(self, obj):
        """Get number of sent recipients"""
        return obj.recipients.filter(status__in=['sent', 'delivered', 'opened', 'clicked']).count()

    def get_failed_count(self, obj):
        """Get number of failed/bounced recipients"""
        return obj.recipients.filter(status__in=['failed', 'bounced']).count()

    def validate_scheduled_send_date(self, value):
        """Ensure scheduled date is in the future"""
        if value and value < timezone.now():
            raise serializers.ValidationError(
                "Scheduled send date must be in the future."
            )
        return value

    def validate(self, data):
        """Validate campaign data"""
        # Template is optional - if not provided, campaign will use subject as body
        # This allows for simple, custom campaigns without needing pre-defined templates

        # If send_immediately is True, clear scheduled_send_date
        if data.get('send_immediately'):
            data['scheduled_send_date'] = None

        # If scheduled_send_date is provided, set send_immediately to False
        if data.get('scheduled_send_date'):
            data['send_immediately'] = False

        return data


class EmailCampaignDetailSerializer(EmailCampaignSerializer):
    """Detailed serializer for EmailCampaign with recipients"""
    recipients = CampaignRecipientSerializer(many=True, read_only=True)

    class Meta(EmailCampaignSerializer.Meta):
        fields = EmailCampaignSerializer.Meta.fields + ['recipients']


class EmailTemplateSerializer(serializers.ModelSerializer):
    """Serializer for EmailTemplate model with variable list"""
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    variable_list = serializers.SerializerMethodField()
    campaigns_using = serializers.SerializerMethodField()

    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'template_type', 'template_type_display',
            'language', 'language_display', 'subject', 'body_text', 'body_html',
            'is_active', 'department', 'notes', 'variable_list',
            'created_at', 'updated_at', 'campaigns_using'
        ]
        read_only_fields = ['id', 'body_text', 'created_at', 'updated_at']

    def get_campaigns_using(self, obj):
        """Return count of campaigns using this template"""
        return obj.campaigns.count()

    def get_variable_list(self, obj):
        """Return list of available variables for this template type"""
        # Common variables available to all templates
        common_vars = [
            {'name': 'company_name', 'description': 'Company name'},
            {'name': 'contact_name', 'description': 'Contact person name'},
            {'name': 'current_year', 'description': 'Current year'},
            {'name': 'unsubscribe_url', 'description': 'Unsubscribe link'},
        ]

        # Template-type specific variables
        type_vars_map = {
            # Renewal templates
            'renewal_30_days': [
                {'name': 'contract_number', 'description': 'Contract number'},
                {'name': 'end_date', 'description': 'Contract end date'},
                {'name': 'days_until_expiry', 'description': 'Days until contract expires'},
                {'name': 'monthly_value', 'description': 'Monthly contract value'},
            ],
            'renewal_14_days': [
                {'name': 'contract_number', 'description': 'Contract number'},
                {'name': 'end_date', 'description': 'Contract end date'},
                {'name': 'days_until_expiry', 'description': 'Days until contract expires'},
                {'name': 'monthly_value', 'description': 'Monthly contract value'},
            ],
            'renewal_7_days': [
                {'name': 'contract_number', 'description': 'Contract number'},
                {'name': 'end_date', 'description': 'Contract end date'},
                {'name': 'days_until_expiry', 'description': 'Days until contract expires'},
                {'name': 'monthly_value', 'description': 'Monthly contract value'},
            ],
            'renewal_urgent': [
                {'name': 'contract_number', 'description': 'Contract number'},
                {'name': 'end_date', 'description': 'Contract end date'},
                {'name': 'days_until_expiry', 'description': 'Days until contract expires'},
                {'name': 'monthly_value', 'description': 'Monthly contract value'},
            ],
            # Invoice templates
            'invoice_new': [
                {'name': 'invoice_number', 'description': 'Invoice number'},
                {'name': 'due_date', 'description': 'Payment due date'},
                {'name': 'total_amount', 'description': 'Total invoice amount'},
                {'name': 'payment_url', 'description': 'Payment link'},
            ],
            'payment_reminder_7_days': [
                {'name': 'invoice_number', 'description': 'Invoice number'},
                {'name': 'due_date', 'description': 'Payment due date'},
                {'name': 'total_amount', 'description': 'Total invoice amount'},
                {'name': 'payment_url', 'description': 'Payment link'},
                {'name': 'days_overdue', 'description': 'Days payment is overdue'},
            ],
            'payment_reminder_14_days': [
                {'name': 'invoice_number', 'description': 'Invoice number'},
                {'name': 'due_date', 'description': 'Payment due date'},
                {'name': 'total_amount', 'description': 'Total invoice amount'},
                {'name': 'payment_url', 'description': 'Payment link'},
                {'name': 'days_overdue', 'description': 'Days payment is overdue'},
            ],
            'payment_overdue': [
                {'name': 'invoice_number', 'description': 'Invoice number'},
                {'name': 'due_date', 'description': 'Payment due date'},
                {'name': 'total_amount', 'description': 'Total invoice amount'},
                {'name': 'payment_url', 'description': 'Payment link'},
                {'name': 'days_overdue', 'description': 'Days payment is overdue'},
            ],
            # Zone offline templates
            'zone_offline_48h': [
                {'name': 'zone_name', 'description': 'Zone name'},
                {'name': 'offline_duration', 'description': 'How long zone has been offline'},
                {'name': 'support_email', 'description': 'Support contact email'},
            ],
            'zone_offline_7d': [
                {'name': 'zone_name', 'description': 'Zone name'},
                {'name': 'offline_duration', 'description': 'How long zone has been offline'},
                {'name': 'support_email', 'description': 'Support contact email'},
            ],
            # General templates
            'welcome': [
                {'name': 'login_url', 'description': 'Login URL'},
            ],
            'contract_signed': [
                {'name': 'contract_number', 'description': 'Contract number'},
                {'name': 'start_date', 'description': 'Contract start date'},
            ],
        }

        # Get template-specific variables
        type_vars = type_vars_map.get(obj.template_type, [])

        # Return combined list
        return common_vars + type_vars

    def validate_template_type(self, value):
        """Validate that template_type is unique (enforced by model)"""
        # Check for uniqueness (excluding current instance if updating)
        query = EmailTemplate.objects.filter(template_type=value)

        if self.instance:
            query = query.exclude(pk=self.instance.pk)

        if query.exists():
            raise serializers.ValidationError(
                f"A template with type '{value}' already exists. Each template type can only have one template."
            )

        return value


class SequenceStepSerializer(serializers.ModelSerializer):
    """Serializer for SequenceStep model"""
    email_template_name = serializers.CharField(source='email_template.name', read_only=True)

    class Meta:
        model = SequenceStep
        fields = [
            'id', 'sequence', 'step_number', 'name',
            'email_template', 'email_template_name',
            'delay_days', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmailSequenceSerializer(serializers.ModelSerializer):
    """Serializer for EmailSequence model"""
    steps = SequenceStepSerializer(many=True, read_only=True)
    total_steps = serializers.IntegerField(source='get_total_steps', read_only=True)
    active_enrollments = serializers.IntegerField(source='get_active_enrollments', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = EmailSequence
        fields = [
            'id', 'name', 'description', 'status',
            'sequence_type', 'trigger_days_before', 'is_system_default',
            'steps', 'total_steps', 'active_enrollments',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class SequenceStepExecutionSerializer(serializers.ModelSerializer):
    """Serializer for SequenceStepExecution model"""
    step_name = serializers.CharField(source='step.name', read_only=True)
    contact_email = serializers.CharField(source='enrollment.contact.email', read_only=True)

    class Meta:
        model = SequenceStepExecution
        fields = [
            'id', 'enrollment', 'step', 'step_name', 'contact_email',
            'scheduled_for', 'sent_at', 'email_log', 'status',
            'error_message', 'attempt_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SequenceEnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for SequenceEnrollment model"""
    sequence_name = serializers.CharField(source='sequence.name', read_only=True)
    contact_name = serializers.CharField(source='contact.get_full_name', read_only=True)
    contact_email = serializers.CharField(source='contact.email', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True, allow_null=True)
    progress = serializers.CharField(source='get_progress', read_only=True)
    step_executions = SequenceStepExecutionSerializer(many=True, read_only=True)

    class Meta:
        model = SequenceEnrollment
        fields = [
            'id', 'sequence', 'sequence_name',
            'contact', 'contact_name', 'contact_email',
            'company', 'company_name',
            'enrolled_at', 'started_at', 'completed_at',
            'status', 'current_step_number', 'progress',
            'enrollment_source', 'trigger_entity_type', 'trigger_entity_id',
            'notes', 'step_executions',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'enrolled_at', 'started_at', 'completed_at', 'created_at', 'updated_at']


class CustomerSegmentSerializer(serializers.ModelSerializer):
    """Serializer for CustomerSegment model"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    member_preview = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = CustomerSegment
        fields = [
            'id', 'name', 'description', 'segment_type', 'status',
            'filter_criteria', 'member_count', 'last_calculated_at',
            'created_by', 'created_by_name', 'tags',
            'last_used_at', 'times_used', 'member_preview', 'can_edit',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'member_count', 'last_calculated_at', 'last_used_at',
            'times_used', 'created_at', 'updated_at'
        ]

    def get_member_preview(self, obj):
        """Return preview of first 5 members"""
        try:
            preview = obj.preview_members(limit=5)
            return ContactSerializer(preview, many=True, context=self.context).data
        except Exception as e:
            return []

    def get_can_edit(self, obj):
        """Check if current user can edit this segment"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        return request.user.role == 'Admin' or request.user == obj.created_by

    def validate_filter_criteria(self, value):
        """Validate filter_criteria JSON structure"""
        if self.initial_data.get('segment_type') == 'dynamic':
            if not value:
                raise serializers.ValidationError("Filter criteria required for dynamic segments")

            # Validate structure
            if not isinstance(value, dict):
                raise serializers.ValidationError("Filter criteria must be a JSON object")

            if 'entity' not in value or value['entity'] not in ['company', 'contact']:
                raise serializers.ValidationError("Must specify entity: 'company' or 'contact'")

            if 'rules' not in value or not isinstance(value['rules'], list):
                raise serializers.ValidationError("Must include 'rules' array")

            # Validate each rule
            for rule in value['rules']:
                if not isinstance(rule, dict):
                    raise serializers.ValidationError("Each rule must be an object")
                if 'field' not in rule or 'operator' not in rule:
                    raise serializers.ValidationError("Each rule must have 'field' and 'operator'")

        return value

    def create(self, validated_data):
        """Auto-set created_by and calculate initial member count"""
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user

        segment = super().create(validated_data)

        # Calculate initial member count
        try:
            segment.update_member_count()
        except Exception as e:
            # Log error but don't fail creation
            print(f"Error calculating member count: {e}")

        return segment


# Support Ticket System Serializers
class TicketAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for TicketAttachment model"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)

    class Meta:
        model = TicketAttachment
        fields = [
            'id', 'ticket', 'file', 'name', 'size',
            'uploaded_by', 'uploaded_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'uploaded_by_name', 'created_at']


class TicketCommentSerializer(serializers.ModelSerializer):
    """Serializer for TicketComment model"""
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    author_role = serializers.CharField(source='author.role', read_only=True)

    class Meta:
        model = TicketComment
        fields = [
            'id', 'ticket', 'author', 'author_name', 'author_role',
            'text', 'is_internal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'author_name', 'author_role', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Auto-set author from request user"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user
        return super().create(validated_data)


class TicketSerializer(serializers.ModelSerializer):
    """Serializer for Ticket model with nested comments and attachments"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    contact_name = serializers.CharField(source='contact.name', read_only=True, allow_null=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)

    # Computed fields
    first_response_time_hours = serializers.ReadOnlyField()
    resolution_time_hours = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()

    # Nested data
    comments = TicketCommentSerializer(many=True, read_only=True)
    attachments = TicketAttachmentSerializer(many=True, read_only=True)

    # Count fields
    comments_count = serializers.SerializerMethodField()
    internal_notes_count = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_number', 'subject', 'description',
            'status', 'priority', 'category',
            'company', 'company_name', 'contact', 'contact_name',
            'assigned_to', 'assigned_to_name', 'assigned_team',
            'created_by', 'created_by_name',
            'first_response_at', 'resolved_at', 'closed_at', 'due_date',
            'first_response_time_hours', 'resolution_time_hours', 'is_overdue',
            'tags', 'comments', 'attachments',
            'comments_count', 'internal_notes_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'ticket_number', 'company_name', 'contact_name',
            'assigned_to_name', 'created_by_name', 'first_response_at',
            'resolved_at', 'closed_at', 'first_response_time_hours',
            'resolution_time_hours', 'is_overdue', 'comments_count',
            'internal_notes_count', 'created_at', 'updated_at'
        ]

    def get_comments_count(self, obj):
        """Count public comments (exclude internal notes)"""
        return obj.comments.filter(is_internal=False).count()

    def get_internal_notes_count(self, obj):
        """Count internal notes"""
        return obj.comments.filter(is_internal=True).count()

    def create(self, validated_data):
        """Auto-set created_by from request user"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


# ============================================================================
# Knowledge Base System Serializers
# ============================================================================

class KBCategorySerializer(serializers.ModelSerializer):
    """Serializer for KBCategory model with hierarchical support"""
    # Nested parent display
    parent_detail = serializers.SerializerMethodField()

    # Read-only computed fields
    article_count = serializers.ReadOnlyField()
    full_path = serializers.CharField(source='get_full_path', read_only=True)

    # Children categories (recursive, depth limited to 2)
    children = serializers.SerializerMethodField()

    class Meta:
        model = KBCategory
        fields = [
            'id', 'name', 'slug', 'description', 'parent', 'parent_detail',
            'icon', 'display_order', 'is_active', 'article_count',
            'full_path', 'children', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'article_count', 'full_path', 'created_at', 'updated_at']

    def get_parent_detail(self, obj):
        """Return nested parent category info"""
        if obj.parent:
            return {
                'id': obj.parent.id,
                'name': obj.parent.name,
                'slug': obj.parent.slug
            }
        return None

    def get_children(self, obj):
        """Return children categories (max depth 2 to avoid recursion issues)"""
        # Only include children if this is not already a nested call
        depth = self.context.get('depth', 0)
        if depth >= 2:
            return []

        children = obj.children.filter(is_active=True)
        # Pass incremented depth to prevent infinite recursion
        context = self.context.copy()
        context['depth'] = depth + 1
        return KBCategorySerializer(children, many=True, context=context).data


class KBTagSerializer(serializers.ModelSerializer):
    """Serializer for KBTag model"""
    article_count = serializers.ReadOnlyField()

    class Meta:
        model = KBTag
        fields = [
            'id', 'name', 'slug', 'color', 'article_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'article_count', 'created_at', 'updated_at']


class KBArticleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for KBArticle list views (better performance)"""
    category_detail = serializers.SerializerMethodField()
    helpfulness_ratio = serializers.SerializerMethodField()

    class Meta:
        model = KBArticle
        fields = [
            'id', 'article_number', 'title', 'slug', 'excerpt',
            'category_detail', 'status', 'visibility', 'view_count',
            'helpful_count', 'not_helpful_count', 'helpfulness_ratio',
            'published_at', 'featured'
        ]
        read_only_fields = [
            'id', 'article_number', 'slug', 'view_count', 'helpful_count',
            'not_helpful_count', 'helpfulness_ratio', 'published_at'
        ]

    def get_category_detail(self, obj):
        """Return minimal category info"""
        return {
            'id': obj.category.id,
            'name': obj.category.name,
            'slug': obj.category.slug
        }

    def get_helpfulness_ratio(self, obj):
        """Calculate helpfulness percentage"""
        return obj.get_helpfulness_ratio()


class KBArticleSerializer(serializers.ModelSerializer):
    """Full serializer for KBArticle model with all nested data"""
    # Nested reads
    category = KBCategorySerializer(read_only=True)
    tags = KBTagSerializer(many=True, read_only=True)
    author_detail = serializers.SerializerMethodField()

    # Write support
    category_id = serializers.UUIDField(write_only=True, source='category')
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True
    )

    # Read-only computed fields
    helpfulness_ratio = serializers.SerializerMethodField()
    related_articles = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = KBArticle
        fields = [
            'id', 'article_number', 'title', 'slug', 'content', 'excerpt',
            'category', 'category_id', 'tags', 'tag_ids',
            'status', 'visibility', 'author', 'author_detail', 'featured',
            'view_count', 'helpful_count', 'not_helpful_count',
            'helpfulness_ratio', 'published_at', 'related_articles',
            'attachments', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'article_number', 'slug', 'view_count', 'helpful_count',
            'not_helpful_count', 'published_at', 'created_at', 'updated_at'
        ]

    def get_author_detail(self, obj):
        """Return author info"""
        if obj.author:
            return {
                'id': obj.author.id,
                'username': obj.author.username,
                'full_name': obj.author.get_full_name()
            }
        return None

    def get_helpfulness_ratio(self, obj):
        """Calculate helpfulness percentage"""
        return obj.get_helpfulness_ratio()

    def get_related_articles(self, obj):
        """Get related articles from relations"""
        related = obj.outgoing_relations.select_related('to_article').all()
        return [{
            'id': rel.to_article.id,
            'article_number': rel.to_article.article_number,
            'title': rel.to_article.title,
            'relation_type': rel.relation_type
        } for rel in related]

    def get_attachments(self, obj):
        """Get article attachments"""
        attachments = obj.attachments.all()
        return [{
            'id': att.id,
            'filename': att.filename,
            'file_size': att.file_size,
            'file_extension': att.get_file_extension(),
            'file_url': att.file.url if att.file else None,
            'uploaded_at': att.uploaded_at
        } for att in attachments]

    def validate_content(self, value):
        """Validate content length (minimum 100 chars)"""
        # Strip HTML tags for length check
        import re
        text = re.sub('<[^<]+?>', '', value)
        if len(text.strip()) < 100:
            raise serializers.ValidationError(
                "Article content must be at least 100 characters (excluding HTML tags)."
            )
        return value

    def validate(self, data):
        """Validate title uniqueness per category"""
        title = data.get('title')
        category = data.get('category')

        if title and category:
            # Check for duplicate title in same category
            query = KBArticle.objects.filter(title=title, category=category)

            # Exclude current instance if updating
            if self.instance:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise serializers.ValidationError({
                    'title': f"An article with title '{title}' already exists in this category."
                })

        return data

    def create(self, validated_data):
        """Create article with author from request user and handle tags"""
        # Extract tag_ids if provided
        tag_ids = validated_data.pop('tag_ids', [])

        # Auto-set author from request user
        request = self.context.get('request')
        if request and request.user.is_authenticated and not validated_data.get('author'):
            validated_data['author'] = request.user

        # Create article
        article = KBArticle.objects.create(**validated_data)

        # Add tags
        if tag_ids:
            tags = KBTag.objects.filter(id__in=tag_ids)
            article.tags.set(tags)

        return article

    def update(self, instance, validated_data):
        """Update article and handle tags"""
        # Extract tag_ids if provided
        tag_ids = validated_data.pop('tag_ids', None)

        # Update article fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update tags if provided
        if tag_ids is not None:
            tags = KBTag.objects.filter(id__in=tag_ids)
            instance.tags.set(tags)

        return instance


class KBArticleViewSerializer(serializers.ModelSerializer):
    """Serializer for KBArticleView model (analytics)"""
    article_detail = serializers.SerializerMethodField()
    user_detail = serializers.SerializerMethodField()

    class Meta:
        model = KBArticleView
        fields = [
            'id', 'article', 'article_detail', 'user', 'user_detail',
            'ip_address', 'session_id', 'viewed_at', 'created_at'
        ]
        read_only_fields = ['id', 'viewed_at', 'created_at']

    def get_article_detail(self, obj):
        """Return minimal article info"""
        return {
            'id': obj.article.id,
            'article_number': obj.article.article_number,
            'title': obj.article.title
        }

    def get_user_detail(self, obj):
        """Return user info"""
        if obj.user:
            return {
                'id': obj.user.id,
                'username': obj.user.username
            }
        return None


class KBArticleRatingSerializer(serializers.ModelSerializer):
    """Serializer for KBArticleRating model"""
    article_detail = serializers.SerializerMethodField()
    user_detail = serializers.SerializerMethodField()

    class Meta:
        model = KBArticleRating
        fields = [
            'id', 'article', 'article_detail', 'user', 'user_detail',
            'is_helpful', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_article_detail(self, obj):
        """Return minimal article info"""
        return {
            'id': obj.article.id,
            'article_number': obj.article.article_number,
            'title': obj.article.title
        }

    def get_user_detail(self, obj):
        """Return user info"""
        if obj.user:
            return {
                'id': obj.user.id,
                'username': obj.user.username
            }
        return None

    def validate(self, data):
        """Validate: One vote per user per article"""
        article = data.get('article')
        user = data.get('user')

        if article and user:
            # Check for existing rating
            query = KBArticleRating.objects.filter(article=article, user=user)

            # Exclude current instance if updating
            if self.instance:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise serializers.ValidationError(
                    "You have already rated this article. Please update your existing rating instead."
                )

        return data


class KBArticleRelationSerializer(serializers.ModelSerializer):
    """Serializer for KBArticleRelation model"""
    from_article_detail = serializers.SerializerMethodField()
    to_article_detail = serializers.SerializerMethodField()

    class Meta:
        model = KBArticleRelation
        fields = [
            'id', 'from_article', 'from_article_detail',
            'to_article', 'to_article_detail', 'relation_type',
            'display_order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_from_article_detail(self, obj):
        """Return minimal from_article info"""
        return {
            'id': obj.from_article.id,
            'article_number': obj.from_article.article_number,
            'title': obj.from_article.title
        }

    def get_to_article_detail(self, obj):
        """Return minimal to_article info"""
        return {
            'id': obj.to_article.id,
            'article_number': obj.to_article.article_number,
            'title': obj.to_article.title
        }

    def validate(self, data):
        """Validate: Cannot relate article to itself"""
        from_article = data.get('from_article')
        to_article = data.get('to_article')

        if from_article and to_article and from_article == to_article:
            raise serializers.ValidationError(
                "Cannot relate an article to itself."
            )

        return data


class KBArticleAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for KBArticleAttachment model"""
    article_detail = serializers.SerializerMethodField()
    uploaded_by_detail = serializers.SerializerMethodField()
    file_extension = serializers.CharField(source='get_file_extension', read_only=True)

    class Meta:
        model = KBArticleAttachment
        fields = [
            'id', 'article', 'article_detail', 'file', 'filename',
            'file_size', 'file_extension', 'uploaded_by', 'uploaded_by_detail',
            'uploaded_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'filename', 'file_size', 'file_extension',
            'uploaded_at', 'created_at', 'updated_at'
        ]

    def get_article_detail(self, obj):
        """Return minimal article info"""
        return {
            'id': obj.article.id,
            'article_number': obj.article.article_number,
            'title': obj.article.title
        }

    def get_uploaded_by_detail(self, obj):
        """Return user info"""
        if obj.uploaded_by:
            return {
                'id': obj.uploaded_by.id,
                'username': obj.uploaded_by.username
            }
        return None

    def create(self, validated_data):
        """Auto-set uploaded_by from request user"""
        request = self.context.get('request')
        if request and request.user.is_authenticated and not validated_data.get('uploaded_by'):
            validated_data['uploaded_by'] = request.user
        return super().create(validated_data)


class TicketKBArticleSerializer(serializers.ModelSerializer):
    """Serializer for TicketKBArticle link model"""
    ticket_detail = serializers.SerializerMethodField()
    article_detail = serializers.SerializerMethodField()
    linked_by_detail = serializers.SerializerMethodField()

    class Meta:
        model = TicketKBArticle
        fields = [
            'id', 'ticket', 'ticket_detail', 'article', 'article_detail',
            'linked_by', 'linked_by_detail', 'linked_at', 'is_helpful',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'linked_at', 'created_at', 'updated_at']

    def get_ticket_detail(self, obj):
        """Return minimal ticket info"""
        return {
            'id': obj.ticket.id,
            'ticket_number': obj.ticket.ticket_number,
            'subject': obj.ticket.subject
        }

    def get_article_detail(self, obj):
        """Return minimal article info"""
        return {
            'id': obj.article.id,
            'article_number': obj.article.article_number,
            'title': obj.article.title
        }

    def get_linked_by_detail(self, obj):
        """Return user info"""
        if obj.linked_by:
            return {
                'id': obj.linked_by.id,
                'username': obj.linked_by.username
            }
        return None

    def create(self, validated_data):
        """Auto-set linked_by from request user"""
        request = self.context.get('request')
        if request and request.user.is_authenticated and not validated_data.get('linked_by'):
            validated_data['linked_by'] = request.user
        return super().create(validated_data)


class StaticDocumentSerializer(serializers.ModelSerializer):
    """Serializer for StaticDocument model (standard T&Cs, etc.)"""
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = StaticDocument
        fields = [
            'id', 'name', 'document_type', 'document_type_display',
            'file', 'file_url', 'version', 'effective_date', 'description',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_file_url(self, obj):
        """Return the file URL if file exists"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


# ============================================================================
# Contract Content Management Serializers (Part 2 - remaining serializers)
# ============================================================================

class ContractTemplateSerializer(serializers.ModelSerializer):
    """Serializer for ContractTemplate model"""
    class Meta:
        model = ContractTemplate
        fields = ['id', 'name', 'template_type', 'content', 'is_default', 'is_active', 'version', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class CorporatePdfTemplateSerializer(serializers.ModelSerializer):
    """Serializer for CorporatePdfTemplate model"""
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = CorporatePdfTemplate
        fields = ['id', 'name', 'company', 'company_name', 'template_format',
                  'include_exhibit_d', 'include_attachment_a', 'header_text',
                  'legal_terms', 'warranty_text', 'use_corporate_branding',
                  'corporate_logo', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


# ============================================================================
# Equipment Management Serializers - REMOVED (replaced by simpler Device model)
# ============================================================================


# ============================================================================
# Settings Serializers
# ============================================================================

class SeasonalTriggerDateSerializer(serializers.ModelSerializer):
    """Serializer for SeasonalTriggerDate model - Variable holiday dates"""
    holiday_type_display = serializers.CharField(source='get_holiday_type_display', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True, default='')

    class Meta:
        model = SeasonalTriggerDate
        fields = [
            'id', 'holiday_type', 'holiday_type_display', 'year',
            'trigger_date', 'holiday_date', 'notes',
            'updated_by', 'updated_by_name', 'updated_at', 'created_at'
        ]
        read_only_fields = ['id', 'updated_by', 'updated_at', 'created_at']