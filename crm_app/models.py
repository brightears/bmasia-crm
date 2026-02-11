from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import EmailValidator, RegexValidator
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.db.models import signals
import uuid


class TimestampedModel(models.Model):
    """Abstract base model with created_at and updated_at timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class User(AbstractUser):
    """Enhanced User model with role-based permissions"""
    ROLE_CHOICES = [
        ('Sales', 'Sales'),
        ('Finance', 'Finance'),
        ('Tech', 'Tech Support'),
        ('Music', 'Music Design'),
        ('Admin', 'Admin'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Sales')
    is_active = models.BooleanField(default=True)
    phone = models.CharField(max_length=20, blank=True, validators=[
        RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    ])
    department = models.CharField(max_length=50, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # Email SMTP configuration for per-user email sending
    smtp_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Gmail address for sending emails (e.g., user@bmasiamusic.com)"
    )
    smtp_password = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Gmail app password (will be encrypted)"
    )

    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.role})"

    def has_role(self, role):
        """Check if user has specific role"""
        return self.role == role

    def can_edit_company(self, company):
        """Check if user can edit a specific company"""
        if self.role == 'Admin':
            return True
        if self.role == 'Sales':
            return company.opportunities.filter(owner=self).exists()
        return False

    def get_smtp_config(self):
        """Return user's SMTP configuration or None if not configured"""
        if self.smtp_email and self.smtp_password:
            return {
                'email': self.smtp_email,
                'password': self.smtp_password,
                'host': 'smtp.gmail.com',
                'port': 587,
                'use_tls': True,
            }
        return None


class Company(TimestampedModel):
    """Enhanced Company model with better tracking and validation"""
    COMPANY_SIZE_CHOICES = [
        ('Single Location', 'Single Location'),
        ('Small Chain', 'Small Chain (2-5 locations)'),
        ('Medium Chain', 'Medium Chain (6-20 locations)'),
        ('Large Chain', 'Large Chain (21-100 locations)'),
        ('Major Chain', 'Major Chain (100+ locations)'),
        ('Franchise', 'Franchise Network'),
    ]
    
    INDUSTRY_CHOICES = [
        ('Hotels', 'Hotels & Resorts'),
        ('Restaurants', 'Restaurants'),
        ('Bars', 'Bars & Nightlife'),
        ('Quick Service Restaurants', 'Quick Service Restaurants'),
        ('Retail Fashion', 'Retail Fashion'),
        ('Retail Food', 'Retail Food'),
        ('Malls', 'Shopping Malls'),
        ('Offices', 'Offices & Corporate'),
        ('Hospitals', 'Hospitals & Medical'),
        ('Spas', 'Spas & Wellness'),
        ('Fun Parks', 'Fun Parks & Entertainment'),
        ('Cafes', 'Cafes & Coffee Shops'),
        ('Gyms', 'Gyms & Fitness Centers'),
        ('Salons', 'Salons & Beauty'),
        ('Banks', 'Banks & Financial'),
        ('Other', 'Other'),
    ]

    BILLING_ENTITY_CHOICES = [
        ('BMAsia Limited', 'BMAsia Limited (Hong Kong)'),
        ('BMAsia (Thailand) Co., Ltd.', 'BMAsia (Thailand) Co., Ltd.'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    country = models.CharField(max_length=100, blank=True, db_index=True)
    current_plan = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=50, choices=INDUSTRY_CHOICES, blank=True)
    # Removed annual_revenue - not needed for BMAsia
    
    # BMAsia specific fields
    location_count = models.IntegerField(default=1, help_text="Number of physical locations")
    music_zone_count = models.IntegerField(default=1, help_text="Total number of music zones across all locations")
    
    # Soundtrack integration
    soundtrack_account_id = models.CharField(max_length=100, blank=True, help_text="Soundtrack Your Brand account ID for API integration")
    
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    # Email preferences
    seasonal_emails_enabled = models.BooleanField(
        default=True,
        help_text="Receive seasonal/holiday email campaigns (Christmas, CNY, Songkran, etc.)"
    )

    # Soundtrack alert preferences
    soundtrack_offline_alerts_enabled = models.BooleanField(
        default=True,
        help_text="Send email alerts when music zones go offline"
    )

    # Address fields
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # Billing entity
    billing_entity = models.CharField(
        max_length=50,
        choices=BILLING_ENTITY_CHOICES,
        default='BMAsia Limited',
        help_text="Legal entity for billing and invoicing"
    )

    # Legal entity name (for official registered company name)
    legal_entity_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Legal registered company name (if different from display name)"
    )

    # IT notes
    it_notes = models.TextField(
        blank=True,
        help_text="General IT notes: remote access details, contact preferences, configurations"
    )

    # Corporate structure
    parent_company = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_companies',
        help_text="Corporate parent company (e.g., Hilton Corporate)"
    )

    is_corporate_parent = models.BooleanField(
        default=False,
        help_text="True if this is a corporate HQ that manages multiple venues"
    )

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name', 'country']),
            models.Index(fields=['industry']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def full_address(self):
        """Return formatted address"""
        parts = [self.address_line1, self.address_line2, self.city, self.state, self.postal_code, self.country]
        return ', '.join(filter(None, parts))
    
    @property
    def total_contract_value(self):
        """Calculate total value of active contracts"""
        return self.contracts.filter(is_active=True).aggregate(
            total=models.Sum('value')
        )['total'] or 0
    
    @property
    def avg_zones_per_location(self):
        """Calculate average music zones per location"""
        if self.location_count > 0:
            return round(self.music_zone_count / self.location_count, 1)
        return 0

    @property
    def is_subsidiary(self):
        """Check if this company is a subsidiary of a parent company"""
        return self.parent_company is not None

    @property
    def has_subsidiaries(self):
        """Check if this company has child companies"""
        return self.child_companies.exists()

    def sync_soundtrack_zones(self):
        """Sync zones from Soundtrack API"""
        if not self.soundtrack_account_id:
            return 0, 0
        
        from .services.soundtrack_api import soundtrack_api
        return soundtrack_api.sync_company_zones(self)


class Contact(TimestampedModel):
    """Enhanced Contact model with better validation and tracking"""
    CONTACT_TYPE_CHOICES = [
        ('Primary', 'Primary Contact'),
        ('Technical', 'Technical Contact'),
        ('Billing', 'Billing Contact'),
        ('Decision Maker', 'Decision Maker'),
        ('Other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=100)
    email = models.EmailField(validators=[EmailValidator()])
    phone = models.CharField(max_length=20, blank=True, validators=[
        RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    ])
    title = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPE_CHOICES, default='Other')
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    linkedin_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    last_contacted = models.DateTimeField(null=True, blank=True)
    
    # Email notification preferences
    receives_notifications = models.BooleanField(default=True, help_text="Master switch: receives any automated emails")
    notification_types = models.JSONField(default=list, blank=True, help_text="List of notification types this contact should receive")
    preferred_language = models.CharField(max_length=2, choices=[('en', 'English'), ('th', 'Thai')], default='en')
    unsubscribed = models.BooleanField(default=False, help_text="Has unsubscribed from all emails")
    unsubscribe_token = models.CharField(max_length=64, blank=True, help_text="Token for unsubscribe links")

    # Granular email preferences (only apply if receives_notifications=True)
    receives_renewal_emails = models.BooleanField(default=True, help_text="Receives contract renewal reminders")
    receives_seasonal_emails = models.BooleanField(default=True, help_text="Receives seasonal/holiday campaign emails")
    receives_payment_emails = models.BooleanField(default=True, help_text="Receives payment reminder emails")
    receives_quarterly_emails = models.BooleanField(default=True, help_text="Receives quarterly check-in emails")
    receives_soundtrack_alerts = models.BooleanField(default=False, help_text="Receives alerts when music zones go offline")

    class Meta:
        unique_together = ['company', 'email']
        ordering = ['name']
        indexes = [
            models.Index(fields=['company', 'is_primary']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.company.name}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            # Ensure only one primary contact per company
            Contact.objects.filter(company=self.company, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        
        # Generate unsubscribe token if not set
        if not self.unsubscribe_token:
            import secrets
            self.unsubscribe_token = secrets.token_urlsafe(32)
        
        super().save(*args, **kwargs)
    
    def get_notification_preferences(self):
        """Get notification preferences for this contact"""
        if self.unsubscribed or not self.receives_notifications:
            return []
        
        # Default notification types based on contact type
        default_types = {
            'Primary': ['renewal', 'quarterly', 'seasonal'],
            'Billing': ['invoice', 'payment'],
            'Technical': ['support', 'zone_alerts'],
            'Decision Maker': ['renewal', 'quarterly'],
        }
        
        if self.notification_types:
            return self.notification_types
        
        return default_types.get(self.contact_type, ['renewal'])


class Note(TimestampedModel):
    """Enhanced Note model with better categorization"""
    NOTE_TYPE_CHOICES = [
        ('General', 'General'),
        ('Meeting', 'Meeting'),
        ('Call', 'Phone Call'),
        ('Email', 'Email'),
        ('Task', 'Task'),
        ('Follow-up', 'Follow-up'),
        ('Issue', 'Issue/Problem'),
        ('Resolution', 'Resolution'),
    ]
    
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_notes')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='notes')
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name='contact_notes')
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='General')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    title = models.CharField(max_length=200, blank=True)
    text = models.TextField()
    is_private = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', '-created_at']),
            models.Index(fields=['note_type', 'priority']),
        ]
    
    def __str__(self):
        return f"{self.title or 'Note'} - {self.company.name}"


class Task(TimestampedModel):
    """Task model for sales team task management"""
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('To Do', 'To Do'),
        ('In Progress', 'In Progress'),
        ('Done', 'Done'),
        ('Cancelled', 'Cancelled'),
        ('On Hold', 'On Hold'),
    ]

    TASK_TYPE_CHOICES = [
        ('Call', 'Call'),
        ('Email', 'Email'),
        ('Follow-up', 'Follow-up'),
        ('Meeting', 'Meeting'),
        ('Other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tasks')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='To Do')
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    related_opportunity = models.ForeignKey('Opportunity', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    related_contract = models.ForeignKey('Contract', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    related_contact = models.ForeignKey('Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')

    class Meta:
        ordering = ['-priority', 'due_date', '-created_at']
        indexes = [
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['company', 'due_date']),
            models.Index(fields=['priority', 'status']),
        ]

    def __str__(self):
        return f"{self.title} - {self.company.name}"

    @property
    def is_overdue(self):
        """Check if task is overdue"""
        return self.due_date and self.due_date < timezone.now() and self.status != 'Done'

    def save(self, *args, **kwargs):
        if self.status == 'Done' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != 'Done':
            self.completed_at = None
        super().save(*args, **kwargs)


class TaskComment(TimestampedModel):
    """Comments on tasks for team collaboration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    comment = models.TextField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.user} on {self.task.title}"


class AuditLog(models.Model):
    """Enhanced Audit Log for tracking all changes"""
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('VIEW', 'Viewed'),
        ('EXPORT', 'Exported'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    record_id = models.CharField(max_length=100)  # Changed to CharField to support UUID
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    changes = models.JSONField(null=True, blank=True)
    additional_data = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['model_name', 'record_id']),
            models.Index(fields=['action', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} {self.action} {self.model_name} at {self.timestamp}"


# Sales Funnel Models
class Opportunity(TimestampedModel):
    """Enhanced Opportunity model with better tracking and analytics"""
    STAGE_CHOICES = [
        ('Contacted', 'Contacted'),
        ('Quotation Sent', 'Quotation Sent'),
        ('Contract Sent', 'Contract Sent'),
        ('Won', 'Won'),
        ('Lost', 'Lost'),
    ]
    
    LEAD_SOURCE_CHOICES = [
        ('Website', 'Website'),
        ('Referral', 'Referral'),
        ('Cold Call', 'Cold Call'),
        ('Email Campaign', 'Email Campaign'),
        ('Social Media', 'Social Media'),
        ('Trade Show', 'Trade Show'),
        ('Partner', 'Partner'),
        ('Other', 'Other'),
    ]
    
    CONTACT_METHOD_CHOICES = [
        ('Email', 'Email'),
        ('Phone', 'Phone Call'),
        ('Meeting', 'In-Person Meeting'),
        ('Video Call', 'Video Call'),
        ('Demo', 'Product Demo'),
        ('Presentation', 'Presentation'),
    ]

    SERVICE_TYPE_CHOICES = [
        ('soundtrack', 'Soundtrack'),
        ('beatbreeze', 'Beat Breeze'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='opportunities')
    name = models.CharField(max_length=255)
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, blank=True, null=True, help_text="Primary service/product for this opportunity")
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES, default='Contacted')
    expected_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    probability = models.IntegerField(default=0, help_text="Probability of closing (0-100%)")
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='opportunities')
    lead_source = models.CharField(max_length=50, choices=LEAD_SOURCE_CHOICES, blank=True)
    contact_method = models.CharField(max_length=20, choices=CONTACT_METHOD_CHOICES, blank=True)
    last_contact_date = models.DateField(null=True, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    expected_close_date = models.DateField(null=True, blank=True)
    actual_close_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    competitors = models.CharField(max_length=500, blank=True, help_text="Comma-separated competitor names")
    pain_points = models.TextField(blank=True)
    decision_criteria = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-expected_value', '-created_at']
        indexes = [
            models.Index(fields=['stage', 'owner']),
            models.Index(fields=['expected_close_date', 'stage']),
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['service_type', 'stage']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.company.name} ({self.stage})"
    
    @property
    def weighted_value(self):
        """Calculate weighted value based on probability"""
        if self.expected_value and self.probability:
            return (self.expected_value * self.probability) / 100
        return 0
    
    @property
    def days_in_stage(self):
        """Calculate days since last stage change"""
        return (timezone.now().date() - self.updated_at.date()).days
    
    @property
    def is_overdue(self):
        """Check if follow-up is overdue"""
        return self.follow_up_date and self.follow_up_date < timezone.now().date()


class OpportunityActivity(TimestampedModel):
    """Track all activities related to an opportunity"""
    ACTIVITY_TYPE_CHOICES = [
        ('Call', 'Phone Call'),
        ('Email', 'Email'),
        ('Meeting', 'Meeting'),
        ('Demo', 'Product Demo'),
        ('Proposal', 'Proposal Sent'),
        ('Follow-up', 'Follow-up'),
        ('Quote', 'Quote Sent'),
        ('Contract', 'Contract Sent'),
        ('Other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    duration_minutes = models.IntegerField(null=True, blank=True)
    outcome = models.TextField(blank=True)
    next_steps = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Opportunity Activities'
    
    def __str__(self):
        return f"{self.activity_type}: {self.subject} - {self.opportunity.name}"


# Finance Models
class Contract(TimestampedModel):
    """Enhanced Contract model with better tracking and alerts"""
    CONTRACT_TYPE_CHOICES = [
        ('Annual', 'Annual Subscription'),
        ('Monthly', 'Monthly Subscription'),
        ('One-time', 'One-time Service'),
        ('Custom', 'Custom Agreement'),
    ]
    
    CONTRACT_STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Renewed', 'Renewed'),
        ('Expired', 'Expired'),
        ('Cancelled', 'Cancelled'),
    ]
    
    SERVICE_TYPE_CHOICES = [
        # Soundtrack Plans
        ('soundtrack_essential_monthly', 'Soundtrack Essential (Monthly)'),
        ('soundtrack_essential_yearly', 'Soundtrack Essential (Yearly)'),
        ('soundtrack_unlimited_monthly', 'Soundtrack Unlimited (Monthly)'),
        ('soundtrack_unlimited_yearly', 'Soundtrack Unlimited (Yearly)'),
        ('soundtrack_enterprise', 'Soundtrack Enterprise (Custom)'),
        # Beat Breeze
        ('beat_breeze_monthly', 'Beat Breeze (Monthly)'),
        ('beat_breeze_yearly', 'Beat Breeze (Yearly)'),
        # Other Services
        ('custom_package', 'Custom Package'),
        ('one_time_setup', 'One-time Setup'),
        ('consulting', 'Consulting Services'),
        ('maintenance', 'Maintenance & Support'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'USD - US Dollar'),
        ('THB', 'THB - Thai Baht'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contracts')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')
    quote = models.ForeignKey('Quote', on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')
    contract_number = models.CharField(max_length=50, unique=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES, default='Annual')
    service_type = models.CharField(max_length=50, choices=SERVICE_TYPE_CHOICES, blank=True, help_text="Specific service or plan")
    status = models.CharField(max_length=20, choices=CONTRACT_STATUS_CHOICES, default='Active')
    start_date = models.DateField()
    end_date = models.DateField()
    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Base contract value (excluding VAT/tax)"
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Tax rate percentage (e.g., 7 for 7% VAT)"
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Calculated: value × tax_rate"
    )
    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total including tax: value + tax_amount"
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    auto_renew = models.BooleanField(default=False)
    renewal_period_months = models.IntegerField(default=12)
    is_active = models.BooleanField(default=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    billing_frequency = models.CharField(max_length=20, default='Annual')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    # Soundtrack account override
    soundtrack_account_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Soundtrack account ID for this contract (overrides company's)"
    )

    # Renewal tracking
    renewed_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renewals',
        help_text="Previous contract this was renewed from"
    )
    renewal_notice_sent = models.BooleanField(default=False)
    renewal_notice_date = models.DateField(null=True, blank=True)
    send_renewal_reminders = models.BooleanField(
        default=True,
        help_text="Send automatic renewal reminder emails for this contract"
    )

    # Corporate contract fields
    CONTRACT_CATEGORY_CHOICES = [
        ('standard', 'Standard Contract'),
        ('corporate_master', 'Corporate Master Agreement'),
        ('participation', 'Participation Agreement'),
    ]

    contract_category = models.CharField(
        max_length=20,
        choices=CONTRACT_CATEGORY_CHOICES,
        default='standard',
    )

    master_contract = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='participation_agreements',
        help_text="Reference to master agreement (for participation agreements)"
    )

    customer_signatory_name = models.CharField(max_length=255, blank=True)
    customer_signatory_title = models.CharField(max_length=255, blank=True)
    additional_customer_signatories = models.JSONField(
        default=list,
        blank=True,
        help_text='Additional customer signatories: [{"name": "...", "title": "..."}]'
    )
    bmasia_signatory_name = models.CharField(max_length=255, blank=True)
    bmasia_signatory_title = models.CharField(max_length=255, blank=True)
    custom_terms = models.TextField(blank=True, help_text="Custom terms for master agreements")

    # Zone relationship
    zones = models.ManyToManyField(
        'Zone',  # Use string reference since Zone is defined later
        through='ContractZone',
        related_name='contracts',
        blank=True,
        help_text="Music zones covered by this contract"
    )

    # Contract Content Management - Template selections
    preamble_template = models.ForeignKey(
        'ContractTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contracts_preamble',
        limit_choices_to={'template_type': 'preamble'}
    )
    preamble_custom = models.TextField(blank=True, help_text="Custom preamble text (overrides template)")

    payment_template = models.ForeignKey(
        'ContractTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contracts_payment'
    )
    payment_custom = models.TextField(blank=True, help_text="Custom payment terms (overrides template)")

    activation_template = models.ForeignKey(
        'ContractTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contracts_activation',
        limit_choices_to={'template_type': 'activation'}
    )
    activation_custom = models.TextField(blank=True, help_text="Custom activation terms (overrides template)")

    # Service package (Many-to-Many + custom items)
    service_items = models.ManyToManyField(
        'ServicePackageItem',
        blank=True,
        related_name='contracts'
    )
    custom_service_items = models.JSONField(
        default=list,
        blank=True,
        help_text='Custom service items: [{"name": "...", "description": "..."}]'
    )

    # Zone pricing configuration
    show_zone_pricing_detail = models.BooleanField(
        default=True,
        help_text="Show per-zone pricing in PDF"
    )
    price_per_zone = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price per zone per year"
    )

    # Contact information
    bmasia_contact_name = models.CharField(max_length=255, blank=True)
    bmasia_contact_email = models.EmailField(blank=True)
    bmasia_contact_title = models.CharField(max_length=255, blank=True)
    customer_contact_name = models.CharField(max_length=255, blank=True)
    customer_contact_email = models.EmailField(blank=True)
    customer_contact_title = models.CharField(max_length=255, blank=True)

    # Finance tracking - Revenue lifecycle
    LIFECYCLE_TYPE_CHOICES = [
        ('new', 'New Contract'),
        ('renewal', 'Renewal'),
        ('addon', 'Add-on (Zone Addition)'),
        ('churn', 'Canceled/Churned'),
    ]

    lifecycle_type = models.CharField(
        max_length=20,
        choices=LIFECYCLE_TYPE_CHOICES,
        blank=True,
        help_text="Revenue type classification for finance tracking"
    )
    lifecycle_type_manually_set = models.BooleanField(
        default=False,
        help_text="If true, lifecycle_type was manually set and won't be auto-updated"
    )
    lifecycle_effective_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when this lifecycle type became effective"
    )

    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['end_date', 'auto_renew']),
            models.Index(fields=['status', 'end_date']),
            models.Index(fields=['lifecycle_type', 'lifecycle_effective_date']),
        ]
    
    def __str__(self):
        return f"{self.contract_number} - {self.company.name}"
    
    @property
    def days_until_expiry(self):
        """Calculate days until contract expires"""
        if self.end_date:
            return (self.end_date - timezone.now().date()).days
        return 0
    
    @property
    def is_expiring_soon(self):
        """Check if contract expires within 60 days"""
        if self.end_date:
            return 0 <= self.days_until_expiry <= 60
        return False
    
    @property
    def monthly_value(self):
        """Calculate monthly value of contract"""
        if self.end_date and self.start_date and self.value:
            # Calculate the difference in months more accurately
            months = ((self.end_date.year - self.start_date.year) * 12 +
                     (self.end_date.month - self.start_date.month))
            # Add 1 because we want inclusive months (e.g., Jan to Dec = 12 months, not 11)
            if self.end_date.day >= self.start_date.day:
                months += 1
            if months > 0:
                return round(float(self.value) / months, 2)
        return 0

    @property
    def effective_soundtrack_account_id(self):
        """Get Soundtrack account ID (contract-level or company-level)"""
        return self.soundtrack_account_id or self.company.soundtrack_account_id

    def clean(self):
        """Validate corporate contract relationships"""
        from django.core.exceptions import ValidationError

        # Participation agreements must have a master contract
        if self.contract_category == 'participation' and not self.master_contract:
            raise ValidationError({
                'master_contract': 'Participation agreements must reference a master contract.'
            })

        # Master contract must be a corporate_master type
        if self.master_contract and self.master_contract.contract_category != 'corporate_master':
            raise ValidationError({
                'master_contract': 'Master contract must be of type "Corporate Master Agreement".'
            })

        # Corporate master agreements should not have a master contract
        if self.contract_category == 'corporate_master' and self.master_contract:
            raise ValidationError({
                'master_contract': 'Corporate Master Agreements cannot reference another master contract.'
            })

    def get_active_zones(self):
        """Get currently active zones for this contract"""
        return self.zones.filter(
            zone_contracts__contract=self,
            zone_contracts__is_active=True
        )

    def get_historical_zones(self, as_of_date=None):
        """
        Get zones that were active on a specific date.
        If no date provided, returns all zones ever linked to this contract.
        """
        if not as_of_date:
            # Return all zones ever linked
            return self.zones.all()

        # Return zones active on specific date
        from django.db.models import Q
        return self.zones.filter(
            Q(zone_contracts__contract=self,
              zone_contracts__start_date__lte=as_of_date,
              zone_contracts__end_date__gte=as_of_date) |
            Q(zone_contracts__contract=self,
              zone_contracts__start_date__lte=as_of_date,
              zone_contracts__end_date__isnull=True)
        ).distinct()

    def get_zone_count(self):
        """Get count of currently active zones"""
        return self.get_active_zones().count()


class ContractZone(TimestampedModel):
    """
    Links zones to contracts with historical tracking.
    Supports contract renewals and maintains complete audit trail.

    Example:
    - Contract #001 (Jan-Dec 2024) → 4 zones (lobby, dining, gym, pool)
    - Contract #002 (Jan 2025+) → same 4 zones (renewal)
    - Each zone has 2 ContractZone records (one per contract)
    - Historical queries work: "What zones were on Contract #001?"
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='contract_zones',
        help_text="Contract covering this zone"
    )

    zone = models.ForeignKey(
        'Zone',  # String reference since Zone is defined later
        on_delete=models.PROTECT,  # Can't delete zone if linked to contract
        related_name='zone_contracts',
        help_text="Zone covered by this contract"
    )

    start_date = models.DateField(
        help_text="Date when zone was added to this contract (typically contract start_date)"
    )

    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when zone was removed from this contract (null = currently active)"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this zone is currently covered by this contract"
    )

    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this zone-contract relationship"
    )

    class Meta:
        ordering = ['-start_date', 'zone__name']
        unique_together = [['contract', 'zone', 'start_date']]  # Prevent duplicate links
        indexes = [
            models.Index(fields=['contract', 'is_active']),
            models.Index(fields=['zone', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        active_status = "active" if self.is_active else "ended"
        return f"{self.zone.name} on {self.contract.contract_number} ({active_status})"


# ============================================================================
# Contract Content Management System
# ============================================================================

class CorporatePdfTemplate(models.Model):
    """PDF layout template for corporate parent companies"""

    TEMPLATE_FORMAT_CHOICES = [
        ('standard', 'Standard BMAsia Format'),
        ('hilton_hpa', 'Hilton HPA Format'),
        ('marriott', 'Marriott Format'),
        ('ihg', 'IHG Format'),
        ('accor', 'Accor Format'),
        ('custom', 'Custom Format'),
    ]

    name = models.CharField(max_length=100)
    template_format = models.CharField(max_length=30, choices=TEMPLATE_FORMAT_CHOICES, default='standard')
    include_exhibit_d = models.BooleanField(default=False, help_text="Generate legal terms exhibit")
    include_attachment_a = models.BooleanField(default=True, help_text="Generate scope of work")
    header_text = models.TextField(blank=True, help_text="Custom header/preamble for this corporate")
    legal_terms = models.TextField(blank=True, help_text="Corporate-specific legal clauses")
    warranty_text = models.TextField(blank=True, help_text="Warranty section text")
    company = models.OneToOneField('Company', on_delete=models.CASCADE, related_name='pdf_template', limit_choices_to={'is_corporate_parent': True})
    use_corporate_branding = models.BooleanField(default=False)
    corporate_logo = models.ImageField(upload_to='corporate_logos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Corporate PDF Template"
        verbose_name_plural = "Corporate PDF Templates"

    def __str__(self):
        return f"{self.name} ({self.get_template_format_display()})"


class ContractTemplate(models.Model):
    """Pre-approved contract templates with standard language"""

    TEMPLATE_TYPE_CHOICES = [
        ('preamble', 'Preamble/Introduction'),
        ('service_standard', 'Service Package - Standard'),
        ('service_managed', 'Service Package - Managed'),
        ('service_custom', 'Service Package - Custom'),
        ('payment_thailand', 'Payment Terms - Thailand'),
        ('payment_international', 'Payment Terms - International'),
        ('activation', 'Activation Terms'),
    ]

    PDF_FORMAT_CHOICES = [
        ('standard', 'Standard Contract'),
        ('corporate_master', 'Corporate Master Agreement'),
        ('participation', 'Participation Agreement'),
    ]

    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPE_CHOICES, default='preamble')
    content = models.TextField(help_text="Template text with {{variables}} for substitution")
    pdf_format = models.CharField(
        max_length=20,
        choices=PDF_FORMAT_CHOICES,
        default='standard',
        help_text='Which PDF structure to use when generating contracts'
    )
    is_default = models.BooleanField(default=False, help_text="Auto-select for new contracts")
    is_active = models.BooleanField(default=True)
    version = models.CharField(max_length=20, default='1.0')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Contract Template"
        verbose_name_plural = "Contract Templates"

    def __str__(self):
        return self.name


class ServicePackageItem(models.Model):
    """Pre-defined service package items"""

    name = models.CharField(max_length=100)
    description = models.TextField(help_text="Full description of this service item")
    is_standard = models.BooleanField(default=True, help_text="Show in selector for new contracts")
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "Service Package Item"
        verbose_name_plural = "Service Package Items"

    def __str__(self):
        return self.name


class ContractDocument(models.Model):
    """Attached documents for contracts"""

    DOCUMENT_TYPE_CHOICES = [
        ('generated', 'System Generated PDF'),
        ('principal_terms', 'Principal Terms'),
        ('attachment_a', 'Attachment A - Scope of Work'),
        ('exhibit_d', 'Exhibit D - Legal Terms'),
        ('master_agreement', 'Master Agreement'),
        ('participation_agreement', 'Participation Agreement'),
        ('standard_terms', 'Standard Terms & Conditions'),
        ('insurance', 'Insurance Certificate'),
        ('other', 'Other'),
    ]

    contract = models.ForeignKey('Contract', on_delete=models.CASCADE, related_name='contract_documents')
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='contract_documents/%Y/%m/')
    is_official = models.BooleanField(default=False, help_text="Mark as official signing version")
    is_signed = models.BooleanField(default=False)
    signed_date = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-is_official', 'document_type', '-uploaded_at']
        verbose_name = "Contract Document"
        verbose_name_plural = "Contract Documents"

    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()})"


class Invoice(TimestampedModel):
    """Enhanced Invoice model with better tracking"""
    INVOICE_STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Sent', 'Sent'),
        ('Paid', 'Paid'),
        ('Overdue', 'Overdue'),
        ('Cancelled', 'Cancelled'),
        ('Refunded', 'Refunded'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'USD - US Dollar'),
        ('THB', 'THB - Thai Baht'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='invoices')
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    invoice_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=INVOICE_STATUS_CHOICES, default='Draft')
    issue_date = models.DateField()
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    payment_terms = models.CharField(max_length=50, blank=True, default='Net 30')
    payment_terms_text = models.TextField(blank=True)
    service_period_start = models.DateField(null=True, blank=True)
    service_period_end = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    # Reminder tracking
    first_reminder_sent = models.BooleanField(default=False)
    second_reminder_sent = models.BooleanField(default=False)
    final_notice_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-issue_date']
        indexes = [
            models.Index(fields=['contract', 'status']),
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['issue_date']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.company.name}"
    
    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if self.status != 'Paid' and self.due_date and self.due_date < timezone.now().date():
            return (timezone.now().date() - self.due_date).days
        return 0
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        return self.days_overdue > 0
    
    def save(self, *args, **kwargs):
        # Auto-calculate total amount
        self.total_amount = self.amount + self.tax_amount - self.discount_amount
        super().save(*args, **kwargs)


class InvoiceLineItem(TimestampedModel):
    """Line items for invoices"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.description} - {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        """Auto-calculate line total"""
        subtotal = self.quantity * self.unit_price
        tax = subtotal * (self.tax_rate / 100)
        self.line_total = subtotal + tax
        super().save(*args, **kwargs)


class ContractLineItem(TimestampedModel):
    """Line items for contracts — mirrors QuoteLineItem/InvoiceLineItem"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='line_items')
    product_service = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.product_service} - {self.contract.contract_number}"

    def save(self, *args, **kwargs):
        """Auto-calculate line total"""
        subtotal = self.quantity * self.unit_price
        discount = subtotal * (self.discount_percentage / 100)
        self.line_total = subtotal - discount
        super().save(*args, **kwargs)


# DEPRECATED: Use Contract model with service_type field instead
"""
class SubscriptionPlan(TimestampedModel):
    # Track multiple subscription tiers for a company
    TIER_CHOICES = [
        ('Soundtrack Essential (Serviced)', 'Soundtrack Essential (Serviced)'),
        ('Soundtrack Essential (Self-Managed)', 'Soundtrack Essential (Self-Managed)'),
        ('Soundtrack Unlimited (Serviced)', 'Soundtrack Unlimited (Serviced)'),
        ('Soundtrack Unlimited (Self-Managed)', 'Soundtrack Unlimited (Self-Managed)'),
        ('Beat Breeze', 'Beat Breeze'),
    ]
    
    BILLING_PERIOD_CHOICES = [
        ('Monthly', 'Monthly'),
        ('Yearly', 'Yearly'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'USD - US Dollar'),
        ('THB', 'THB - Thai Baht'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='subscription_plans')
    tier = models.CharField(max_length=100, choices=TIER_CHOICES)
    zone_count = models.IntegerField(default=1)
    billing_period = models.CharField(max_length=20, choices=BILLING_PERIOD_CHOICES, default='Monthly')
    price_per_zone = models.IntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['company', 'tier']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['tier']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.tier} ({self.zone_count} zones)"
    
    @property
    def total_value(self):
        # Calculate total value for this tier
        if self.price_per_zone:
            return self.zone_count * self.price_per_zone
        return 0
    
    @property
    def monthly_value(self):
        # Calculate monthly value for comparison
        if not self.price_per_zone:
            return 0
        total = self.zone_count * self.price_per_zone
        if self.billing_period == 'Yearly':
            return total / 12
        return total
    
    @property
    def display_price(self):
        # Display price with currency
        if self.price_per_zone:
            return f"{self.currency} {self.price_per_zone:,}"
        return "Not set"
"""


class Device(TimestampedModel):
    """
    Simple device tracking - one device can run multiple zones.
    Example: One Windows PC running 3 Soundtrack zones.
    """
    DEVICE_TYPE_CHOICES = [
        ('pc', 'PC / Computer'),
        ('tablet', 'Tablet'),
        ('music_player', 'Music Player Box'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='devices'
    )
    name = models.CharField(
        max_length=100,
        help_text="Device name (e.g., 'Lobby PC', 'Restaurant Tablet')"
    )
    device_type = models.CharField(
        max_length=20,
        choices=DEVICE_TYPE_CHOICES,
        default='pc'
    )
    model_info = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional: Model name, serial number, or other identifier"
    )
    notes = models.TextField(
        blank=True,
        help_text="Tech support notes about this device"
    )

    class Meta:
        ordering = ['company', 'name']
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'

    def __str__(self):
        return f"{self.name} ({self.get_device_type_display()}) - {self.company.name}"

    @property
    def zone_count(self):
        """Number of zones running on this device"""
        return self.zones.count()


class Zone(TimestampedModel):
    """Track individual music zones for companies"""
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('no_device', 'No Device Paired'),
        ('expired', 'Subscription Expired'),
        ('pending', 'Pending Activation'),
        ('cancelled', 'Cancelled'),  # For terminated contracts
    ]
    
    PLATFORM_CHOICES = [
        ('soundtrack', 'Soundtrack Your Brand'),
        ('beatbreeze', 'Beat Breeze'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='zones')
    device = models.ForeignKey(
        'Device',
        on_delete=models.SET_NULL,
        related_name='zones',
        null=True,
        blank=True,
        help_text="Physical device running this zone (optional)"
    )
    name = models.CharField(max_length=100)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='soundtrack')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # For Soundtrack integration - zone specific data
    soundtrack_zone_id = models.CharField(max_length=100, blank=True, help_text="Zone ID from Soundtrack API")
    soundtrack_admin_email = models.EmailField(blank=True, help_text="Admin email from Soundtrack API")
    
    # Manual tracking fields
    device_name = models.CharField(max_length=100, blank=True)
    last_seen_online = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    # Orphaned zone tracking
    is_orphaned = models.BooleanField(
        default=False,
        help_text="Zone exists in CRM but not found in Soundtrack API"
    )
    orphaned_at = models.DateTimeField(null=True, blank=True)

    # Auto-update from API
    last_api_sync = models.DateTimeField(null=True, blank=True)
    api_raw_data = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['company', 'name']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['platform', 'company']),
        ]
    
    def __str__(self):
        # Extract just the zone name (after " - ") for minimal header display
        if " - " in self.name:
            return self.name.split(" - ")[-1]  # Return just "Drift Bar", "Edge", etc.
        return self.name
    
    @property
    def soundtrack_account_id(self):
        """Get soundtrack account ID from company"""
        return self.company.soundtrack_account_id
    
    @property
    def is_online(self):
        return self.status == 'online'
    
    def update_from_api(self, api_data):
        """Update zone status from Soundtrack API data"""
        self.api_raw_data = api_data
        self.last_api_sync = timezone.now()
        
        # Parse API data to update status
        # This will be implemented based on actual API response structure
        if api_data.get('is_online'):
            self.status = 'online'
            self.last_seen_online = timezone.now()
        elif api_data.get('device_paired') is False:
            self.status = 'no_device'
        elif api_data.get('subscription_active') is False:
            self.status = 'expired'
        else:
            self.status = 'offline'
        
        # Update admin email if available
        if api_data.get('admin_email'):
            self.soundtrack_admin_email = api_data['admin_email']

        self.save()

    def get_active_contract(self):
        """Get the currently active contract for this zone"""
        active_link = self.zone_contracts.filter(is_active=True).first()
        return active_link.contract if active_link else None

    def mark_as_cancelled(self):
        """
        Mark zone as cancelled when contract terminates.
        Used by signal handler when contract status changes to 'Terminated'.
        """
        self.status = 'cancelled'
        self.save(update_fields=['status'])

    def get_contract_history(self):
        """Get all contracts this zone has ever been linked to"""
        return self.zone_contracts.all().order_by('-start_date')


class ZoneOfflineAlert(TimestampedModel):
    """Track offline events and notifications with smart cooldown"""
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='offline_alerts')
    detected_at = models.DateTimeField(help_text="When zone first went offline")
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="When zone came back online")
    is_resolved = models.BooleanField(default=False)

    # Notification tracking
    first_notification_sent = models.BooleanField(default=False)
    first_notification_at = models.DateTimeField(null=True, blank=True)
    last_notification_at = models.DateTimeField(null=True, blank=True)
    notification_count = models.IntegerField(default=0)
    notified_contacts = models.ManyToManyField('Contact', blank=True, related_name='offline_alert_notifications')

    class Meta:
        ordering = ['-detected_at']
        verbose_name = 'Zone Offline Alert'
        verbose_name_plural = 'Zone Offline Alerts'

    def __str__(self):
        status = "Resolved" if self.is_resolved else "Active"
        return f"{self.zone.name} - {status} ({self.detected_at.strftime('%Y-%m-%d %H:%M')})"

    def should_send_notification(self):
        """Smart notification logic: 4hr first, then every 24hr"""
        now = timezone.now()
        hours_offline = (now - self.detected_at).total_seconds() / 3600

        # Not offline long enough for first alert (4 hours)
        if hours_offline < 4:
            return False

        # First notification
        if not self.first_notification_sent:
            return True

        # Subsequent notifications: 24-hour cooldown
        if self.last_notification_at:
            hours_since_last = (now - self.last_notification_at).total_seconds() / 3600
            return hours_since_last >= 24

        return False

    @property
    def hours_offline(self):
        """Calculate hours since zone went offline"""
        end_time = self.resolved_at if self.is_resolved else timezone.now()
        return (end_time - self.detected_at).total_seconds() / 3600


# Email System Models
class EmailTemplate(TimestampedModel):
    """Store reusable email templates for different communication types"""
    TEMPLATE_TYPE_CHOICES = [
        # Sales templates
        ('renewal_30_days', '30-Day Renewal Reminder'),
        ('renewal_14_days', '14-Day Renewal Reminder'),
        ('renewal_7_days', '7-Day Renewal Reminder'),
        ('renewal_urgent', 'Urgent Renewal Notice'),
        
        # Finance templates
        ('invoice_new', 'New Invoice'),
        ('payment_reminder_7_days', '7-Day Payment Reminder'),
        ('payment_reminder_14_days', '14-Day Payment Reminder'),
        ('payment_overdue', 'Payment Overdue Notice'),
        
        # Music Design templates
        ('quarterly_checkin', 'Quarterly Check-in'),
        ('seasonal_christmas', 'Christmas Season Preparation'),
        ('seasonal_newyear', 'Chinese New Year Preparation'),
        ('seasonal_valentines', "Valentine's Day Preparation"),
        ('seasonal_songkran', 'Songkran Preparation'),
        ('seasonal_loy_krathong', 'Loy Krathong Preparation'),
        ('seasonal_ramadan', 'Ramadan Preparation'),
        ('seasonal_singapore_national_day', 'Singapore National Day Preparation'),
        ('seasonal_diwali', 'Diwali Preparation'),
        ('seasonal_mid_autumn', 'Mid-Autumn Festival Preparation'),
        ('seasonal_eid_fitr', 'Eid al-Fitr Preparation'),
        
        # Technical Support templates
        ('zone_offline_alert', 'Zone Offline Alert (Auto)'),
        ('zone_offline_48h', 'Zone Offline 48 Hours'),
        ('zone_offline_7d', 'Zone Offline 7 Days'),
        
        # General templates
        ('welcome', 'Welcome Email'),
        ('contract_signed', 'Contract Signed Confirmation'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('th', 'Thai'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPE_CHOICES, unique=True)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='en')
    subject = models.CharField(max_length=200)
    body_html = models.TextField(blank=True, help_text="HTML email body. Use variables like {{company_name}}, {{contact_name}}, {{days_until_expiry}}")
    body_text = models.TextField(help_text="Plain text email body for non-HTML clients")
    is_active = models.BooleanField(default=True)
    
    # Template metadata
    department = models.CharField(max_length=20, choices=User.ROLE_CHOICES, blank=True)
    notes = models.TextField(blank=True, help_text="Internal notes about when to use this template")
    
    class Meta:
        ordering = ['template_type', 'language']
        indexes = [
            models.Index(fields=['template_type', 'language', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.language})"
    
    def render(self, context):
        """Render template with context variables"""
        from django.template import Template, Context
        
        # Render subject
        subject_template = Template(self.subject)
        rendered_subject = subject_template.render(Context(context))
        
        # Render text body
        text_template = Template(self.body_text)
        rendered_text = text_template.render(Context(context))
        
        # Generate HTML from text if HTML is empty
        if not self.body_html or self.body_html.strip() == '':
            from crm_app.utils.email_utils import text_to_html
            rendered_html = text_to_html(rendered_text)
        else:
            # Render HTML body
            html_template = Template(self.body_html)
            rendered_html = html_template.render(Context(context))
        
        return {
            'subject': rendered_subject,
            'body_html': rendered_html,
            'body_text': rendered_text
        }
    
    def save(self, *args, **kwargs):
        """Auto-generate plain text from HTML"""
        from crm_app.utils.email_utils import html_to_text, text_to_html

        # If HTML is provided, generate plain text from it
        if self.body_html and self.body_html.strip():
            self.body_text = html_to_text(self.body_html)
        # If only plain text provided (backward compatibility)
        elif self.body_text and self.body_text.strip():
            # Generate HTML from text for old templates
            self.body_html = text_to_html(self.body_text)
        else:
            # Neither provided - validation error
            from django.core.exceptions import ValidationError
            raise ValidationError("Email body is required (HTML or text)")

        super().save(*args, **kwargs)


class EmailLog(TimestampedModel):
    """Track all emails sent by the system"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('unsubscribed', 'Unsubscribed'),
    ]
    
    EMAIL_TYPE_CHOICES = [
        ('renewal', 'Renewal Reminder'),
        ('invoice', 'Invoice'),
        ('payment', 'Payment Reminder'),
        ('quarterly', 'Quarterly Check-in'),
        ('seasonal', 'Seasonal Campaign'),
        ('support', 'Technical Support'),
        ('manual', 'Manual Email'),
        ('test', 'Test Email'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='email_logs')
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, related_name='email_logs')
    email_type = models.CharField(max_length=20, choices=EMAIL_TYPE_CHOICES)
    template_used = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True)
    
    # Email details
    from_email = models.EmailField()
    to_email = models.EmailField()
    cc_emails = models.TextField(blank=True, help_text="Comma-separated CC emails")
    subject = models.CharField(max_length=200)
    body_html = models.TextField()
    body_text = models.TextField()
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Related objects
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')
    
    # Tracking
    message_id = models.CharField(max_length=255, blank=True, help_text="Email message ID for tracking")
    in_reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    # Attachments
    attachments = models.ManyToManyField('DocumentAttachment', blank=True, related_name='email_logs')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status', '-created_at']),
            models.Index(fields=['email_type', 'status']),
            models.Index(fields=['contact', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.email_type} to {self.to_email} - {self.status}"
    
    def mark_as_sent(self):
        """Mark email as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()
        
        # Also create a Note for tracking
        Note.objects.create(
            company=self.company,
            contact=self.contact,
            title=f"Email sent: {self.subject}",
            text=f"Email sent to {self.to_email}\nType: {self.get_email_type_display()}\nStatus: Sent",
            note_type='Email',
            author=None  # System generated
        )
    
    def mark_as_failed(self, error_message):
        """Mark email as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.save()


class EmailCampaign(TimestampedModel):
    """Track email campaigns and blast emails with advanced targeting and analytics"""
    CAMPAIGN_TYPE_CHOICES = [
        ('renewal_sequence', 'Renewal Reminder Sequence'),
        ('payment_sequence', 'Payment Reminder Sequence'),
        ('seasonal', 'Seasonal Campaign'),
        ('quarterly', 'Quarterly Check-in'),
        ('custom', 'Custom Campaign'),
        ('newsletter', 'Newsletter'),
        ('promotion', 'Promotional Campaign'),
        ('onboarding', 'Onboarding Sequence'),
        ('engagement', 'Engagement Campaign'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Campaign name for internal tracking")
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPE_CHOICES)
    subject = models.CharField(max_length=200, blank=True, default='', help_text="Email subject line")
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns', help_text="Optional: Use existing template")

    # Legacy fields (kept for backward compatibility)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='email_campaigns', null=True, blank=True, help_text="Optional: Specific company for single-company campaigns")
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_campaigns')

    # Targeting & Scheduling
    target_audience = models.JSONField(
        blank=True,
        null=True,
        help_text='Segmentation criteria e.g. {"industry": "Hotels", "country": "Thailand", "contact_type": "Primary"}'
    )
    audience_count = models.IntegerField(default=0, help_text="Cached count of recipients (auto-updated)")
    scheduled_send_date = models.DateTimeField(null=True, blank=True, help_text="When to send this campaign")
    actual_send_date = models.DateTimeField(null=True, blank=True, help_text="When campaign was actually sent")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    send_immediately = models.BooleanField(default=False, help_text="Send as soon as status is changed to 'sending'")

    # Campaign Content
    sender_email = models.EmailField(blank=True, help_text="Email address to send from (leave blank to use default)")
    reply_to_email = models.EmailField(blank=True, null=True, help_text="Reply-to email address")

    # Analytics (all IntegerFields for performance)
    total_sent = models.IntegerField(default=0, help_text="Total emails sent")
    total_delivered = models.IntegerField(default=0, help_text="Successfully delivered")
    total_bounced = models.IntegerField(default=0, help_text="Bounced emails")
    total_opened = models.IntegerField(default=0, help_text="Unique opens")
    total_clicked = models.IntegerField(default=0, help_text="Unique clicks")
    total_unsubscribed = models.IntegerField(default=0, help_text="Unsubscribed from this campaign")
    total_complained = models.IntegerField(default=0, help_text="Marked as spam")

    # Legacy tracking fields (kept for backward compatibility)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    emails_sent = models.IntegerField(default=0)
    last_email_sent = models.DateTimeField(null=True, blank=True)
    stop_on_reply = models.BooleanField(default=True)
    replied = models.BooleanField(default=False)

    class Meta:
        db_table = 'crm_app_email_campaign'
        verbose_name = 'Email Campaign'
        verbose_name_plural = 'Email Campaigns'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['campaign_type', 'status']),
            models.Index(fields=['scheduled_send_date', 'status']),
            models.Index(fields=['company', 'is_active']),  # Legacy index
        ]

    def __str__(self):
        if self.company:
            return f"{self.name} - {self.company.name}"
        return self.name

    @property
    def open_rate(self):
        """Calculate email open rate percentage"""
        if self.total_sent > 0:
            return round((self.total_opened / self.total_sent) * 100, 2)
        return 0

    @property
    def click_rate(self):
        """Calculate email click rate percentage"""
        if self.total_sent > 0:
            return round((self.total_clicked / self.total_sent) * 100, 2)
        return 0

    @property
    def bounce_rate(self):
        """Calculate email bounce rate percentage"""
        if self.total_sent > 0:
            return round((self.total_bounced / self.total_sent) * 100, 2)
        return 0

    def update_analytics(self):
        """Recalculate analytics from campaign recipients"""
        from django.db.models import Count, Q

        recipients = self.recipients.all()

        self.total_sent = recipients.filter(status__in=['sent', 'delivered', 'opened', 'clicked', 'bounced']).count()
        self.total_delivered = recipients.filter(status__in=['delivered', 'opened', 'clicked']).count()
        self.total_bounced = recipients.filter(status='bounced').count()
        self.total_opened = recipients.filter(status__in=['opened', 'clicked']).count()
        self.total_clicked = recipients.filter(status='clicked').count()
        self.total_unsubscribed = recipients.filter(status='unsubscribed').count()

        # Update legacy fields
        self.emails_sent = self.total_sent
        if self.total_sent > 0:
            last_sent = recipients.exclude(sent_at__isnull=True).order_by('-sent_at').first()
            if last_sent:
                self.last_email_sent = last_sent.sent_at

        self.save()


class CampaignRecipient(TimestampedModel):
    """Track individual recipients in email campaigns with detailed status"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('bounced', 'Bounced'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('unsubscribed', 'Unsubscribed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        EmailCampaign,
        on_delete=models.CASCADE,
        related_name='recipients',
        help_text="Email campaign this recipient belongs to"
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='campaign_receipts',
        help_text="Contact receiving the campaign email"
    )
    email_log = models.ForeignKey(
        EmailLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_recipient',
        help_text="Link to the actual email sent"
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of this campaign recipient"
    )

    # Detailed timestamps for tracking email journey
    sent_at = models.DateTimeField(null=True, blank=True, help_text="When email was sent")
    delivered_at = models.DateTimeField(null=True, blank=True, help_text="When email was delivered")
    opened_at = models.DateTimeField(null=True, blank=True, help_text="First time email was opened")
    clicked_at = models.DateTimeField(null=True, blank=True, help_text="First time link was clicked")
    bounced_at = models.DateTimeField(null=True, blank=True, help_text="When email bounced")
    failed_at = models.DateTimeField(null=True, blank=True, help_text="When sending failed")

    # Error tracking
    error_message = models.TextField(blank=True, help_text="Error details if sending failed")

    class Meta:
        db_table = 'crm_app_campaign_recipient'
        verbose_name = 'Campaign Recipient'
        verbose_name_plural = 'Campaign Recipients'
        unique_together = [['campaign', 'contact']]  # One recipient per campaign
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['contact', 'status']),
            models.Index(fields=['sent_at']),
            models.Index(fields=['status', '-sent_at']),
        ]

    def __str__(self):
        return f"{self.campaign.name} - {self.contact.email}"

    def mark_as_sent(self):
        """Mark recipient as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()

    def mark_as_delivered(self):
        """Mark recipient as delivered"""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save()

    def mark_as_opened(self):
        """Mark recipient as opened"""
        if self.status not in ['opened', 'clicked']:
            self.status = 'opened'
            self.opened_at = timezone.now()
            self.save()

    def mark_as_clicked(self):
        """Mark recipient as clicked"""
        self.status = 'clicked'
        if not self.clicked_at:
            self.clicked_at = timezone.now()
        if not self.opened_at:
            self.opened_at = timezone.now()
        self.save()

    def mark_as_bounced(self, error_msg=''):
        """Mark recipient as bounced"""
        self.status = 'bounced'
        self.bounced_at = timezone.now()
        self.error_message = error_msg
        self.save()

    def mark_as_failed(self, error_msg=''):
        """Mark recipient as failed"""
        self.status = 'failed'
        self.failed_at = timezone.now()
        self.error_message = error_msg
        self.save()


class SeasonalTriggerDate(models.Model):
    """
    Admin-configurable trigger dates for holidays with variable dates.
    Each year, admin sets when to send seasonal campaign emails.
    """
    HOLIDAY_TYPE_CHOICES = [
        ('auto_seasonal_cny', 'Chinese New Year'),
        ('auto_seasonal_ramadan', 'Ramadan'),
        ('auto_seasonal_loy_krathong', 'Loy Krathong'),
        ('auto_seasonal_diwali', 'Diwali'),
        ('auto_seasonal_mid_autumn', 'Mid-Autumn Festival'),
        ('auto_seasonal_eid_fitr', 'Eid al-Fitr'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    holiday_type = models.CharField(
        max_length=50,
        choices=HOLIDAY_TYPE_CHOICES,
        help_text="Which holiday this trigger date is for"
    )
    trigger_date = models.DateField(
        help_text="Date to send campaign emails (typically 2 weeks before the holiday)"
    )
    year = models.IntegerField(
        help_text="Year this trigger date applies to"
    )
    holiday_date = models.DateField(
        null=True,
        blank=True,
        help_text="Actual holiday date (for reference)"
    )
    notes = models.TextField(
        blank=True,
        help_text="Any notes about this year's campaign"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seasonal_trigger_updates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['holiday_type', 'year']
        ordering = ['-year', 'trigger_date']
        verbose_name = 'Seasonal Trigger Date'
        verbose_name_plural = 'Seasonal Trigger Dates'

    def __str__(self):
        return f"{self.get_holiday_type_display()} {self.year} - Send: {self.trigger_date}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Validate trigger_date is before holiday_date if both set
        if self.trigger_date and self.holiday_date:
            if self.trigger_date >= self.holiday_date:
                raise ValidationError("Trigger date must be before the holiday date")


class DocumentAttachment(TimestampedModel):
    """Store documents that can be attached to emails"""
    DOCUMENT_TYPE_CHOICES = [
        ('contract', 'Contract'),
        ('invoice', 'Invoice'),
        ('proposal', 'Proposal'),
        ('brochure', 'Brochure'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=200)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    file = models.FileField(upload_to='documents/%Y/%m/')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Related objects
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'document_type']),
        ]

    def __str__(self):
        return f"{self.name} - {self.company.name}"


# Quote Management Models
class Quote(TimestampedModel):
    """Quote model for managing sales quotes and proposals"""
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Sent', 'Sent'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
        ('Expired', 'Expired'),
    ]

    CURRENCY_CHOICES = [
        ('USD', 'USD - US Dollar'),
        ('THB', 'THB - Thai Baht'),
        ('EUR', 'EUR - Euro'),
        ('GBP', 'GBP - British Pound'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote_number = models.CharField(max_length=50, unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='quotes')
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name='quotes')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True, related_name='quotes')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    valid_from = models.DateField()
    valid_until = models.DateField()

    # Financial fields
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')

    # Additional information
    terms_conditions = models.TextField(blank=True, help_text="Terms and conditions for this quote")
    notes = models.TextField(blank=True, help_text="Internal notes about this quote")

    # Status tracking
    sent_date = models.DateField(null=True, blank=True)
    accepted_date = models.DateField(null=True, blank=True)
    rejected_date = models.DateField(null=True, blank=True)
    expired_date = models.DateField(null=True, blank=True)

    # Creator tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='quotes_created')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['quote_number']),
            models.Index(fields=['valid_until', 'status']),
        ]

    def __str__(self):
        return f"{self.quote_number} - {self.company.name}"

    @property
    def is_expired(self):
        """Check if quote has expired"""
        return self.valid_until < timezone.now().date() and self.status not in ['Accepted', 'Rejected', 'Expired']

    @property
    def days_until_expiry(self):
        """Calculate days until quote expires"""
        if self.valid_until:
            return (self.valid_until - timezone.now().date()).days
        return 0

    def save(self, *args, **kwargs):
        """Auto-update status dates"""
        if self.status == 'Sent' and not self.sent_date:
            self.sent_date = timezone.now().date()
        elif self.status == 'Accepted' and not self.accepted_date:
            self.accepted_date = timezone.now().date()
        elif self.status == 'Rejected' and not self.rejected_date:
            self.rejected_date = timezone.now().date()
        elif self.status == 'Expired' and not self.expired_date:
            self.expired_date = timezone.now().date()

        super().save(*args, **kwargs)


class QuoteLineItem(TimestampedModel):
    """Line items for quotes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='line_items')
    product_service = models.CharField(max_length=200)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.product_service} - {self.quote.quote_number}"

    def save(self, *args, **kwargs):
        """Auto-calculate line total"""
        subtotal = self.quantity * self.unit_price
        discount_amount = subtotal * (self.discount_percentage / 100)
        self.line_total = subtotal - discount_amount
        super().save(*args, **kwargs)


class QuoteAttachment(TimestampedModel):
    """Attachments for quotes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='attachments')
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='quotes/attachments/%Y/%m/')
    size = models.IntegerField(help_text="File size in bytes")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.quote.quote_number}"


class QuoteActivity(TimestampedModel):
    """Track activities related to quotes"""
    ACTIVITY_TYPE_CHOICES = [
        ('Created', 'Created'),
        ('Sent', 'Sent'),
        ('Viewed', 'Viewed'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
        ('Expired', 'Expired'),
        ('Updated', 'Updated'),
        ('Converted', 'Converted to Contract'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField()

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Quote Activities'

    def __str__(self):
        return f"{self.activity_type} - {self.quote.quote_number}"


# Email Sequence Models (Drip Campaign System)
class EmailSequence(TimestampedModel):
    """Define a multi-step automated email sequence"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('archived', 'Archived'),
    ]

    SEQUENCE_TYPE_CHOICES = [
        ('manual', 'Manual Enrollment'),
        ('auto_renewal', 'Auto: Contract Renewal'),
        ('auto_payment', 'Auto: Payment Reminders'),
        ('auto_quarterly', 'Auto: Quarterly Check-ins'),
        # Fixed date holidays
        ('auto_seasonal_christmas', 'Auto: Christmas (All)'),
        ('auto_seasonal_valentines', 'Auto: Valentines Day (All)'),
        ('auto_seasonal_songkran', 'Auto: Songkran (Thailand)'),
        ('auto_seasonal_singapore_nd', 'Auto: Singapore National Day'),
        # Variable date holidays (configured in Settings)
        ('auto_seasonal_cny', 'Auto: Chinese New Year (Asia)'),
        ('auto_seasonal_loy_krathong', 'Auto: Loy Krathong (Thailand)'),
        ('auto_seasonal_ramadan', 'Auto: Ramadan (Middle East)'),
        ('auto_seasonal_diwali', 'Auto: Diwali (India/SE Asia)'),
        ('auto_seasonal_mid_autumn', 'Auto: Mid-Autumn Festival (Asia)'),
        ('auto_seasonal_eid_fitr', 'Auto: Eid al-Fitr (Indonesia/Malaysia)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="e.g., 'New Customer Onboarding'")
    description = models.TextField(blank=True, help_text="What this sequence does")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_sequences')

    # Unified automation fields
    sequence_type = models.CharField(
        max_length=30,
        choices=SEQUENCE_TYPE_CHOICES,
        default='manual',
        help_text="Type of automation - manual requires enrollment, auto types trigger automatically"
    )
    trigger_days_before = models.IntegerField(
        null=True,
        blank=True,
        help_text="For auto types: days before/after event to trigger (e.g., 30 for 30 days before contract expiry)"
    )
    is_system_default = models.BooleanField(
        default=False,
        help_text="System default automations created during setup"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email Sequence'
        verbose_name_plural = 'Email Sequences'

    def __str__(self):
        return self.name

    def get_total_steps(self):
        """Return count of related steps"""
        return self.steps.count()

    def get_active_enrollments(self):
        """Return count of enrollments with status='active'"""
        return self.enrollments.filter(status='active').count()


class SequenceStep(TimestampedModel):
    """Individual step in a sequence (one email)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.ForeignKey(EmailSequence, on_delete=models.CASCADE, related_name='steps')
    step_number = models.PositiveIntegerField(help_text="Order in sequence (1, 2, 3...)")
    name = models.CharField(max_length=200, help_text="e.g., 'Welcome Email', 'Day 3 Tips'")
    email_template = models.ForeignKey(EmailTemplate, on_delete=models.PROTECT, related_name='sequence_steps')
    delay_days = models.PositiveIntegerField(default=0, help_text="Send X days after previous step (or enrollment for step 1)")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sequence', 'step_number']
        unique_together = [['sequence', 'step_number']]
        verbose_name = 'Sequence Step'
        verbose_name_plural = 'Sequence Steps'

    def __str__(self):
        return f"{self.sequence.name} - Step {self.step_number}: {self.name}"

    def clean(self):
        """Validate delay_days >= 0"""
        from django.core.exceptions import ValidationError
        if self.delay_days < 0:
            raise ValidationError({'delay_days': 'Delay days must be 0 or greater'})


class SequenceEnrollment(TimestampedModel):
    """Track which contacts are enrolled in which sequences"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('unsubscribed', 'Unsubscribed'),
    ]

    ENROLLMENT_SOURCE_CHOICES = [
        ('manual', 'Manual'),
        ('auto_trigger', 'Auto Trigger'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.ForeignKey(EmailSequence, on_delete=models.CASCADE, related_name='enrollments')
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='sequence_enrollments')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name='sequence_enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True, help_text="When enrolled")
    started_at = models.DateTimeField(null=True, blank=True, help_text="When first email sent")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When all steps done")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    current_step_number = models.PositiveIntegerField(default=1, help_text="Which step is next")
    notes = models.TextField(blank=True)

    # Unified automation fields
    enrollment_source = models.CharField(
        max_length=20,
        choices=ENROLLMENT_SOURCE_CHOICES,
        default='manual',
        help_text="How this enrollment was created"
    )
    trigger_entity_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Type of entity that triggered enrollment: contract, invoice, company"
    )
    trigger_entity_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the triggering entity for deduplication"
    )

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = [['sequence', 'contact']]
        verbose_name = 'Sequence Enrollment'
        verbose_name_plural = 'Sequence Enrollments'
        indexes = [
            models.Index(fields=['status', '-enrolled_at']),
            models.Index(fields=['sequence', 'status']),
        ]

    def __str__(self):
        return f"{self.contact} enrolled in {self.sequence.name}"

    def get_progress(self):
        """Return progress as formatted string"""
        total_steps = self.sequence.get_total_steps()
        completed_steps = self.step_executions.filter(status='sent').count()

        # Return as "X/Y" format
        progress_str = f"{completed_steps}/{total_steps}"

        # Also calculate percentage
        if total_steps > 0:
            percentage = round((completed_steps / total_steps) * 100, 1)
            return f"{progress_str} ({percentage}%)"

        return progress_str


class SequenceStepExecution(TimestampedModel):
    """Track each individual step execution per enrollment (audit log + scheduling)"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(SequenceEnrollment, on_delete=models.CASCADE, related_name='step_executions')
    step = models.ForeignKey(SequenceStep, on_delete=models.CASCADE, related_name='executions')
    scheduled_for = models.DateTimeField(help_text="When this step should be sent")
    sent_at = models.DateTimeField(null=True, blank=True, help_text="When actually sent")
    email_log = models.ForeignKey(EmailLog, on_delete=models.SET_NULL, null=True, blank=True, related_name='sequence_executions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    error_message = models.TextField(blank=True)
    attempt_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['scheduled_for']
        unique_together = [['enrollment', 'step']]
        verbose_name = 'Step Execution'
        verbose_name_plural = 'Step Executions'
        indexes = [
            models.Index(fields=['status', 'scheduled_for']),
            models.Index(fields=['enrollment', 'status']),
        ]

    def __str__(self):
        return f"{self.step.name} for {self.enrollment.contact} - {self.status}"

    def is_due(self):
        """Return True if scheduled_for <= timezone.now() and status='scheduled'"""
        return self.scheduled_for <= timezone.now() and self.status == 'scheduled'


# Customer Segmentation Models
class CustomerSegment(TimestampedModel):
    """
    Dynamic customer segmentation for targeted marketing campaigns.
    Segments automatically update based on filter criteria.
    """

    SEGMENT_TYPE_CHOICES = [
        ('dynamic', 'Dynamic - Auto-updates based on rules'),
        ('static', 'Static - Manually curated list'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('archived', 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True, help_text="Segment name (e.g., 'High-Value Hotels in Thailand')")
    description = models.TextField(blank=True, help_text="What this segment represents")
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES, default='dynamic')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Filter criteria stored as JSON (for dynamic segments)
    filter_criteria = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dynamic filter rules in JSON format"
    )

    # For static segments - manually selected contacts/companies
    static_contacts = models.ManyToManyField(
        'Contact',
        blank=True,
        related_name='segments',
        help_text="Manually selected contacts (for static segments)"
    )
    static_companies = models.ManyToManyField(
        'Company',
        blank=True,
        related_name='segments',
        help_text="Manually selected companies (for static segments)"
    )

    # Performance caching
    member_count = models.IntegerField(
        default=0,
        help_text="Cached count of members (auto-updated)"
    )
    last_calculated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When member count was last recalculated"
    )

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_segments'
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags for organization"
    )

    # Usage tracking
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this segment was last used in a campaign"
    )
    times_used = models.IntegerField(
        default=0,
        help_text="How many times used in campaigns/sequences"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer Segment'
        verbose_name_plural = 'Customer Segments'
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['segment_type', 'status']),
            models.Index(fields=['created_by', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.member_count} members)"

    def get_members(self, limit=None):
        """
        Get all contacts matching this segment's criteria.
        Returns QuerySet of Contact objects.
        """
        if self.segment_type == 'static':
            queryset = self.static_contacts.filter(is_active=True, unsubscribed=False)
        else:
            queryset = self._evaluate_dynamic_filters()

        if limit:
            return queryset[:limit]
        return queryset

    def _evaluate_dynamic_filters(self):
        """
        Build Django QuerySet from filter_criteria JSON.
        Returns QuerySet of Contact objects.
        """
        from django.db.models import Q

        if not self.filter_criteria or not self.filter_criteria.get('rules'):
            return Contact.objects.none()

        entity = self.filter_criteria.get('entity', 'contact')
        match_type = self.filter_criteria.get('match_type', 'all')
        rules = self.filter_criteria.get('rules', [])

        # Build Q objects from rules
        q_objects = []
        for rule in rules:
            q_obj = self._build_q_object(rule, entity)
            if q_obj:
                q_objects.append(q_obj)

        if not q_objects:
            return Contact.objects.none()

        # Combine Q objects with AND or OR
        if match_type == 'all':
            combined_q = q_objects[0]
            for q in q_objects[1:]:
                combined_q &= q
        else:  # 'any'
            combined_q = q_objects[0]
            for q in q_objects[1:]:
                combined_q |= q

        # Apply filters based on entity type
        if entity == 'company':
            # Filter companies, then get their contacts
            companies = Company.objects.filter(combined_q)
            return Contact.objects.filter(
                company__in=companies,
                is_active=True,
                unsubscribed=False
            ).distinct()
        else:  # 'contact'
            return Contact.objects.filter(
                combined_q,
                is_active=True,
                unsubscribed=False
            ).distinct()

    def _build_q_object(self, rule, entity):
        """
        Convert a single filter rule to Django Q object.

        Rule format:
        {
            "field": "industry",
            "operator": "equals",
            "value": "Hotels"
        }
        """
        from django.db.models import Q

        field = rule.get('field')
        operator = rule.get('operator')
        value = rule.get('value')

        if not field or not operator:
            return None

        # Map field paths for contact entity accessing company fields
        if entity == 'contact' and field.startswith('company.'):
            # Contact accessing company field
            field_path = field.replace('company.', 'company__')
        elif entity == 'contact' and field.startswith('contract.'):
            # Contact accessing contract through company
            field_path = field.replace('contract.', 'company__contracts__')
        elif entity == 'company':
            # Company field direct access
            field_path = field
        else:
            field_path = field

        # Define boolean fields that should use __exact instead of __iexact
        boolean_fields = [
            'is_active', 'unsubscribed', 'is_billing_contact',
            'is_decision_maker', 'is_primary_contact',
            'company.is_active'
        ]

        # Check if this is a boolean field
        is_boolean = field in boolean_fields

        # Build Q object based on operator
        # Use case-sensitive exact match for booleans, case-insensitive for strings
        operator_mapping = {
            'equals': f'{field_path}__exact' if is_boolean else f'{field_path}__iexact',
            'not_equals': f'{field_path}__exact' if is_boolean else f'{field_path}__iexact',
            'contains': f'{field_path}__icontains',
            'not_contains': f'{field_path}__icontains',
            'starts_with': f'{field_path}__istartswith',
            'ends_with': f'{field_path}__iendswith',
            'greater_than': f'{field_path}__gt',
            'greater_than_or_equal': f'{field_path}__gte',
            'less_than': f'{field_path}__lt',
            'less_than_or_equal': f'{field_path}__lte',
            'between': f'{field_path}__range',
            'in_list': f'{field_path}__in',
            'is_empty': f'{field_path}__isnull',
            'is_not_empty': f'{field_path}__isnull',
        }

        lookup = operator_mapping.get(operator)
        if not lookup:
            return None

        # Special handling for negation operators
        if operator == 'not_equals':
            return ~Q(**{operator_mapping['equals']: value})
        elif operator == 'not_contains':
            return ~Q(**{operator_mapping['contains']: value})
        elif operator == 'is_empty':
            return Q(**{lookup: True}) | Q(**{f'{field_path}__exact': ''})
        elif operator == 'is_not_empty':
            return Q(**{lookup: False}) & ~Q(**{f'{field_path}__exact': ''})
        else:
            return Q(**{lookup: value})

    def update_member_count(self):
        """Recalculate and cache member count"""
        self.member_count = self.get_members().count()
        self.last_calculated_at = timezone.now()
        self.save(update_fields=['member_count', 'last_calculated_at'])
        return self.member_count

    def preview_members(self, limit=10):
        """Get preview of segment members for UI"""
        return self.get_members(limit=limit)

    def mark_as_used(self):
        """Track segment usage when used in campaigns"""
        self.last_used_at = timezone.now()
        self.times_used += 1
        self.save(update_fields=['last_used_at', 'times_used'])


# Support Ticket System Models
class Ticket(TimestampedModel):
    """
    Support ticket system for tracking customer issues and requests.
    Auto-generates ticket numbers and manages ticket lifecycle.
    """
    STATUS_CHOICES = [
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending Customer Response'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    CATEGORY_CHOICES = [
        ('technical', 'Technical Issue'),
        ('billing', 'Billing Question'),
        ('zone_config', 'Zone Configuration'),
        ('account', 'Account Management'),
        ('feature_request', 'Feature Request'),
        ('general', 'General Inquiry'),
    ]

    # Category to team mapping for auto-assignment
    CATEGORY_TEAM_MAP = {
        'technical': 'Tech',
        'billing': 'Finance',
        'zone_config': 'Music',
        'account': 'Sales',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Auto-generated ticket number (T-YYYYMMDD-NNNN)"
    )

    # Ticket details
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium', db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')

    # Relationships
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='tickets',
        help_text="Company this ticket is for"
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        help_text="Contact who submitted the ticket"
    )
    zone = models.ForeignKey(
        'Zone',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        help_text="Music zone related to this ticket (optional)"
    )

    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        help_text="User assigned to handle this ticket"
    )
    assigned_team = models.CharField(
        max_length=20,
        choices=User.ROLE_CHOICES,
        blank=True,
        help_text="Team responsible for this ticket"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tickets',
        help_text="User who created this ticket"
    )

    # Time tracking
    first_response_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When first comment/response was added"
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ticket was marked as resolved"
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ticket was closed"
    )
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ticket should be resolved by"
    )

    # Additional metadata
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags for categorization"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Support Ticket'
        verbose_name_plural = 'Support Tickets'
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.ticket_number} - {self.subject}"

    def save(self, *args, **kwargs):
        """Auto-generate ticket number and set timestamps"""
        # Generate ticket number if not set
        if not self.ticket_number:
            self.ticket_number = self._generate_ticket_number()

        # Auto-set timestamps based on status changes
        if self.status == 'resolved' and not self.resolved_at:
            self.resolved_at = timezone.now()
        elif self.status == 'closed' and not self.closed_at:
            self.closed_at = timezone.now()

        # Auto-assign team based on category if not already set
        if not self.assigned_team and self.category in self.CATEGORY_TEAM_MAP:
            self.assigned_team = self.CATEGORY_TEAM_MAP[self.category]

        super().save(*args, **kwargs)

    def _generate_ticket_number(self):
        """Generate unique ticket number in format T-YYYYMMDD-NNNN"""
        today = timezone.now().date()
        date_prefix = f"T-{today.strftime('%Y%m%d')}"

        # Find the highest ticket number for today
        from django.db.models import Max
        latest_ticket = Ticket.objects.filter(
            ticket_number__startswith=date_prefix
        ).aggregate(Max('ticket_number'))

        latest_number = latest_ticket['ticket_number__max']

        if latest_number:
            # Extract the counter and increment
            counter = int(latest_number.split('-')[-1]) + 1
        else:
            # First ticket of the day
            counter = 1

        return f"{date_prefix}-{counter:04d}"

    @property
    def first_response_time_hours(self):
        """Calculate hours between creation and first response"""
        if self.first_response_at:
            delta = self.first_response_at - self.created_at
            return round(delta.total_seconds() / 3600, 2)
        return None

    @property
    def resolution_time_hours(self):
        """Calculate hours between creation and resolution"""
        if self.resolved_at:
            delta = self.resolved_at - self.created_at
            return round(delta.total_seconds() / 3600, 2)
        return None

    @property
    def is_overdue(self):
        """Check if ticket is past due date and not resolved/closed"""
        if self.due_date and self.status not in ['resolved', 'closed']:
            return timezone.now() > self.due_date
        return False


class TicketComment(TimestampedModel):
    """
    Comments and internal notes for support tickets.
    Tracks communication history and first response time.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='comments',
        help_text="Ticket this comment belongs to"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        help_text="User who wrote this comment"
    )
    text = models.TextField(help_text="Comment text")
    is_internal = models.BooleanField(
        default=False,
        help_text="True for internal notes, False for public comments"
    )

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Ticket Comment'
        verbose_name_plural = 'Ticket Comments'
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
        ]

    def __str__(self):
        comment_type = 'Internal Note' if self.is_internal else 'Comment'
        return f"{comment_type} on {self.ticket.ticket_number}"

    def save(self, *args, **kwargs):
        """Set first_response_at on ticket when first comment is added"""
        is_new = self._state.adding

        super().save(*args, **kwargs)

        # Update ticket's first_response_at if this is the first comment
        if is_new and not self.ticket.first_response_at and not self.is_internal:
            self.ticket.first_response_at = self.created_at
            self.ticket.save(update_fields=['first_response_at'])


class TicketAttachment(TimestampedModel):
    """
    File attachments for support tickets.
    Stores files and tracks metadata.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="Ticket this attachment belongs to"
    )
    file = models.FileField(
        upload_to='tickets/attachments/%Y/%m/',
        help_text="Upload file"
    )
    name = models.CharField(
        max_length=200,
        help_text="File name"
    )
    size = models.IntegerField(
        help_text="File size in bytes"
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        help_text="User who uploaded this file"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ticket Attachment'
        verbose_name_plural = 'Ticket Attachments'

    def __str__(self):
        return f"{self.name} - {self.ticket.ticket_number}"

    def save(self, *args, **kwargs):
        """Auto-populate name and size from file"""
        if self.file and not self.name:
            self.name = self.file.name
        if self.file and not self.size:
            self.size = self.file.size
        super().save(*args, **kwargs)


# Knowledge Base System Models
class KBCategory(TimestampedModel):
    """
    Hierarchical categories for organizing knowledge base articles.
    Supports parent/child relationships for nested categorization.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Category name")
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-friendly slug (auto-generated)")
    description = models.TextField(blank=True, help_text="Category description")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent category (null for top-level categories)"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon name (e.g., 'wrench', 'dollar-sign', 'music') for UI display"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order for displaying categories (lower numbers first)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this category is visible"
    )

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'KB Category'
        verbose_name_plural = 'KB Categories'
        indexes = [
            models.Index(fields=['parent', 'is_active']),
            models.Index(fields=['display_order', 'name']),
        ]

    def __str__(self):
        return self.get_full_path()

    def save(self, *args, **kwargs):
        """Auto-generate slug from name"""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_full_path(self):
        """Return full category path: 'Parent > Child'"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name

    @property
    def article_count(self):
        """Count articles in this category"""
        return self.articles.filter(status='published').count()


class KBTag(TimestampedModel):
    """
    Tags for knowledge base articles.
    Allows flexible categorization beyond hierarchical categories.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True, help_text="Tag name")
    slug = models.SlugField(max_length=50, unique=True, help_text="URL-friendly slug (auto-generated)")
    color = models.CharField(
        max_length=7,
        default='#3B82F6',
        help_text="Hex color code for UI display (e.g., #3B82F6)"
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'KB Tag'
        verbose_name_plural = 'KB Tags'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug from name"""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def article_count(self):
        """Count articles with this tag"""
        return self.articles.filter(status='published').count()


class KBArticle(TimestampedModel):
    """
    Core knowledge base article model with auto-generated article numbers.
    Includes full-text search, ratings, and view tracking.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    VISIBILITY_CHOICES = [
        ('public', 'Public - Visible to customers'),
        ('internal', 'Internal - Only visible to staff'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Auto-generated article number (KB-YYYYMMDD-NNNN)"
    )
    title = models.CharField(max_length=255, help_text="Article title")
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-friendly slug (auto-generated from title)"
    )
    content = models.TextField(help_text="Main article content (supports HTML)")
    excerpt = models.TextField(
        blank=True,
        help_text="Short summary/preview (optional, auto-generated from content if empty)"
    )

    # Categorization
    category = models.ForeignKey(
        KBCategory,
        on_delete=models.PROTECT,
        related_name='articles',
        help_text="Primary category for this article"
    )
    tags = models.ManyToManyField(
        KBTag,
        blank=True,
        related_name='articles',
        help_text="Tags for flexible categorization"
    )

    # Publishing
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
        help_text="Publication status"
    )
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='internal',
        help_text="Who can view this article"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='kb_articles',
        help_text="Article author"
    )
    featured = models.BooleanField(
        default=False,
        help_text="Feature this article on KB homepage"
    )

    # Analytics (updated automatically)
    view_count = models.IntegerField(
        default=0,
        editable=False,
        help_text="Total views"
    )
    helpful_count = models.IntegerField(
        default=0,
        editable=False,
        help_text="Number of 'helpful' votes"
    )
    not_helpful_count = models.IntegerField(
        default=0,
        editable=False,
        help_text="Number of 'not helpful' votes"
    )

    # Timestamps
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When article was published"
    )

    # Full-text search
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = 'KB Article'
        verbose_name_plural = 'KB Articles'
        indexes = [
            models.Index(fields=['status', 'visibility']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['featured', 'status']),
            models.Index(fields=['-published_at']),
            models.Index(fields=['article_number']),
        ]

    def __str__(self):
        return f"{self.article_number} - {self.title}"

    def save(self, *args, **kwargs):
        """Auto-generate article number and slug"""
        # Generate article number if not set
        if not self.article_number:
            self.article_number = self._generate_article_number()

        # Generate slug from title if not set
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure unique slug
            base_slug = self.slug
            counter = 1
            while KBArticle.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        # Set published_at when status changes to published
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()

        # Auto-generate excerpt from content if empty
        if not self.excerpt and self.content:
            # Strip HTML tags and take first 200 characters
            import re
            text = re.sub('<[^<]+?>', '', self.content)
            self.excerpt = text[:200] + ('...' if len(text) > 200 else '')

        super().save(*args, **kwargs)

        # Update search vector after save
        if self.status == 'published':
            self._update_search_vector()

    def _generate_article_number(self):
        """Generate unique article number in format KB-YYYYMMDD-NNNN"""
        today = timezone.now().date()
        date_prefix = f"KB-{today.strftime('%Y%m%d')}"

        # Find the highest article number for today
        from django.db.models import Max
        latest_article = KBArticle.objects.filter(
            article_number__startswith=date_prefix
        ).aggregate(Max('article_number'))

        latest_number = latest_article['article_number__max']

        if latest_number:
            # Extract the counter and increment
            counter = int(latest_number.split('-')[-1]) + 1
        else:
            # First article of the day
            counter = 1

        return f"{date_prefix}-{counter:04d}"

    def _update_search_vector(self):
        """Update PostgreSQL full-text search vector (PostgreSQL only)"""
        from django.db import connection

        # Only update search vector on PostgreSQL (not SQLite for local dev)
        if connection.vendor == 'postgresql':
            KBArticle.objects.filter(pk=self.pk).update(
                search_vector=SearchVector('title', weight='A') + SearchVector('content', weight='B')
            )

    def get_helpfulness_ratio(self):
        """Calculate helpfulness percentage (0-100)"""
        total_votes = self.helpful_count + self.not_helpful_count
        if total_votes == 0:
            return None
        return round((self.helpful_count / total_votes) * 100, 1)

    @property
    def helpfulness_percentage(self):
        """Alias for get_helpfulness_ratio()"""
        return self.get_helpfulness_ratio()


class KBArticleView(TimestampedModel):
    """
    Track article views for analytics.
    Prevents duplicate counting per session/user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article = models.ForeignKey(
        KBArticle,
        on_delete=models.CASCADE,
        related_name='views',
        help_text="Article that was viewed"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kb_article_views',
        help_text="User who viewed (null for anonymous)"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of viewer"
    )
    session_id = models.CharField(
        max_length=100,
        help_text="Session ID to prevent duplicate counting"
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']
        verbose_name = 'KB Article View'
        verbose_name_plural = 'KB Article Views'
        unique_together = [['article', 'session_id']]
        indexes = [
            models.Index(fields=['article', '-viewed_at']),
            models.Index(fields=['user', '-viewed_at']),
        ]

    def __str__(self):
        user_info = f"by {self.user.username}" if self.user else "anonymous"
        return f"View of {self.article.article_number} {user_info}"


class KBArticleRating(TimestampedModel):
    """
    Helpful/Not Helpful votes for articles.
    One vote per user per article.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article = models.ForeignKey(
        KBArticle,
        on_delete=models.CASCADE,
        related_name='ratings',
        help_text="Article being rated"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='kb_article_ratings',
        help_text="User who voted"
    )
    is_helpful = models.BooleanField(help_text="True = Helpful, False = Not Helpful")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'KB Article Rating'
        verbose_name_plural = 'KB Article Ratings'
        unique_together = [['article', 'user']]
        indexes = [
            models.Index(fields=['article', 'is_helpful']),
        ]

    def __str__(self):
        vote_type = "Helpful" if self.is_helpful else "Not Helpful"
        return f"{vote_type} vote for {self.article.article_number}"


class KBArticleRelation(TimestampedModel):
    """
    Related articles feature.
    Links articles together with relationship types.
    """
    RELATION_TYPE_CHOICES = [
        ('related', 'Related Article'),
        ('see_also', 'See Also'),
        ('prerequisite', 'Prerequisite Reading'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_article = models.ForeignKey(
        KBArticle,
        on_delete=models.CASCADE,
        related_name='outgoing_relations',
        help_text="Source article"
    )
    to_article = models.ForeignKey(
        KBArticle,
        on_delete=models.CASCADE,
        related_name='incoming_relations',
        help_text="Related article"
    )
    relation_type = models.CharField(
        max_length=20,
        choices=RELATION_TYPE_CHOICES,
        default='related',
        help_text="Type of relationship"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order for displaying related articles"
    )

    class Meta:
        ordering = ['from_article', 'display_order']
        verbose_name = 'KB Article Relation'
        verbose_name_plural = 'KB Article Relations'
        unique_together = [['from_article', 'to_article']]
        indexes = [
            models.Index(fields=['from_article', 'relation_type']),
        ]

    def __str__(self):
        return f"{self.from_article.article_number} → {self.to_article.article_number} ({self.get_relation_type_display()})"


class KBArticleAttachment(TimestampedModel):
    """
    File attachments for KB articles.
    Supports PDFs, images, documents, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article = models.ForeignKey(
        KBArticle,
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="Article this attachment belongs to"
    )
    file = models.FileField(
        upload_to='kb_attachments/%Y/%m/',
        help_text="Attachment file"
    )
    filename = models.CharField(
        max_length=200,
        help_text="Original filename"
    )
    file_size = models.IntegerField(
        help_text="File size in bytes"
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='kb_attachments',
        help_text="User who uploaded this file"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'KB Article Attachment'
        verbose_name_plural = 'KB Article Attachments'
        indexes = [
            models.Index(fields=['article', '-uploaded_at']),
        ]

    def __str__(self):
        return f"{self.filename} - {self.article.article_number}"

    def save(self, *args, **kwargs):
        """Auto-populate filename and file_size from file"""
        if self.file and not self.filename:
            self.filename = self.file.name
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def get_file_extension(self):
        """Extract file extension from filename"""
        import os
        return os.path.splitext(self.filename)[1].lower()


class TicketKBArticle(TimestampedModel):
    """
    Link KB articles to support tickets.
    Tracks which articles were helpful for resolving tickets.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='kb_articles',
        help_text="Support ticket"
    )
    article = models.ForeignKey(
        KBArticle,
        on_delete=models.CASCADE,
        related_name='linked_tickets',
        help_text="KB article linked to this ticket"
    )
    linked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ticket_kb_links',
        help_text="User who linked this article"
    )
    linked_at = models.DateTimeField(auto_now_add=True)
    is_helpful = models.BooleanField(
        null=True,
        blank=True,
        help_text="Was this article helpful for resolving the ticket? (optional)"
    )

    class Meta:
        ordering = ['-linked_at']
        verbose_name = 'Ticket KB Article Link'
        verbose_name_plural = 'Ticket KB Article Links'
        unique_together = [['ticket', 'article']]
        indexes = [
            models.Index(fields=['ticket', '-linked_at']),
            models.Index(fields=['article', '-linked_at']),
        ]

    def __str__(self):
        return f"{self.article.article_number} linked to {self.ticket.ticket_number}"


# ============================================================================
# Equipment Management System - REMOVED (replaced by simpler Device model)
# ============================================================================


# ============================================================================
# Static Document Management
# ============================================================================

class StaticDocument(models.Model):
    """Static document templates like Standard Terms and Conditions"""
    DOCUMENT_TYPE_CHOICES = [
        ('standard_terms_th', 'Standard Terms - Thailand/Hong Kong'),
        ('standard_terms_intl', 'Standard Terms - International'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES, unique=True)
    file = models.FileField(upload_to='static_documents/')
    version = models.CharField(max_length=20, default='1.0')
    effective_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Static Document'
        verbose_name_plural = 'Static Documents'

    def __str__(self):
        return f"{self.name} (v{self.version})"


# ============================================================================
# Finance & Accounting Module
# ============================================================================

class MonthlyRevenueSnapshot(TimestampedModel):
    """
    Monthly revenue snapshot for tracking contracted value and cash received.
    Used for dashboard metrics and finance reporting.
    """
    CATEGORY_CHOICES = [
        ('new', 'New Contract'),
        ('renewal', 'Renewal'),
        ('addon', 'Add-on (Zone Addition)'),
        ('churn', 'Canceled/Churned'),
    ]

    CURRENCY_CHOICES = [
        ('USD', 'USD - US Dollar'),
        ('THB', 'THB - Thai Baht'),
        ('EUR', 'EUR - Euro'),
        ('GBP', 'GBP - British Pound'),
    ]

    BILLING_ENTITY_CHOICES = [
        ('bmasia_hk', 'BMAsia Limited (Hong Kong)'),
        ('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    year = models.IntegerField(help_text="Year of the snapshot (e.g., 2026)")
    month = models.IntegerField(help_text="Month of the snapshot (1-12)")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text="Revenue category (new/renewal/addon/churn)"
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD',
        help_text="Currency for this snapshot"
    )
    billing_entity = models.CharField(
        max_length=20,
        choices=BILLING_ENTITY_CHOICES,
        help_text="Which BMAsia entity is billing"
    )

    # Metrics
    contract_count = models.IntegerField(
        default=0,
        help_text="Number of contracts in this category for the month"
    )
    contracted_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total contract value for this category"
    )
    cash_received = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Actual cash received in this period"
    )

    # Manual override capability
    is_manually_overridden = models.BooleanField(
        default=False,
        help_text="If true, values were manually entered and won't be auto-calculated"
    )
    override_reason = models.TextField(
        blank=True,
        help_text="Reason for manual override"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this snapshot"
    )

    class Meta:
        ordering = ['-year', '-month', 'category']
        unique_together = [['year', 'month', 'category', 'currency', 'billing_entity']]
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['category', 'year', 'month']),
            models.Index(fields=['billing_entity', 'year', 'month']),
            models.Index(fields=['currency', 'year', 'month']),
        ]
        verbose_name = 'Monthly Revenue Snapshot'
        verbose_name_plural = 'Monthly Revenue Snapshots'

    def __str__(self):
        return f"{self.year}-{self.month:02d} | {self.get_category_display()} | {self.currency} | {self.billing_entity}"


class MonthlyRevenueTarget(TimestampedModel):
    """
    Monthly revenue targets set by management for forecasting and goal tracking.
    Separate from actual snapshots to enable comparison.
    """
    CATEGORY_CHOICES = MonthlyRevenueSnapshot.CATEGORY_CHOICES
    CURRENCY_CHOICES = MonthlyRevenueSnapshot.CURRENCY_CHOICES
    BILLING_ENTITY_CHOICES = MonthlyRevenueSnapshot.BILLING_ENTITY_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    year = models.IntegerField(help_text="Target year (e.g., 2026)")
    month = models.IntegerField(help_text="Target month (1-12)")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text="Revenue category for this target"
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD',
        help_text="Currency for this target"
    )
    billing_entity = models.CharField(
        max_length=20,
        choices=BILLING_ENTITY_CHOICES,
        help_text="Which BMAsia entity this target applies to"
    )

    # Target metrics
    target_contract_count = models.IntegerField(
        default=0,
        help_text="Target number of contracts for this category"
    )
    target_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Target contracted revenue"
    )
    target_cash_flow = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Target cash collection"
    )

    notes = models.TextField(
        blank=True,
        help_text="Notes about this target or assumptions"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revenue_targets',
        help_text="User who set this target"
    )

    class Meta:
        ordering = ['-year', '-month', 'category']
        unique_together = [['year', 'month', 'category', 'currency', 'billing_entity']]
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['category', 'year', 'month']),
            models.Index(fields=['billing_entity', 'year', 'month']),
        ]
        verbose_name = 'Monthly Revenue Target'
        verbose_name_plural = 'Monthly Revenue Targets'

    def __str__(self):
        return f"Target: {self.year}-{self.month:02d} | {self.get_category_display()} | {self.currency}"


class CashFlowSnapshot(TimestampedModel):
    """
    Stores cash flow data for a specific period.
    Includes opening balance and allows manual overrides.
    Part of Finance Module - Phase 5 (Cash Flow Statement).
    """
    BILLING_ENTITY_CHOICES = [
        ('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'),
        ('bmasia_hk', 'BMAsia Limited'),
    ]
    CURRENCY_CHOICES = [
        ('THB', 'Thai Baht'),
        ('USD', 'US Dollar'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Period
    year = models.IntegerField(help_text="Year (e.g., 2026)")
    month = models.IntegerField(help_text="Month (1-12)")

    # Entity and currency
    billing_entity = models.CharField(
        max_length=20,
        choices=BILLING_ENTITY_CHOICES,
        help_text="Which BMAsia entity this applies to"
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='THB'
    )

    # Opening balance (manually entered or carried forward)
    opening_cash_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Cash balance at start of period"
    )

    # Operating Activities (null = calculate from data, value = override)
    cash_from_customers = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Cash received from customer invoice payments"
    )
    cash_to_suppliers = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Cash paid to suppliers (non-salary OpEx)"
    )
    cash_to_employees = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Cash paid for salaries/payroll"
    )
    other_operating_cash = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Other operating cash flows (manual entry)"
    )

    # Investing Activities
    capex_purchases = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Cash paid for capital expenditures"
    )
    asset_sales = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Cash received from asset sales"
    )
    other_investing_cash = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Other investing cash flows"
    )

    # Financing Activities (manual entry - no auto-calculation)
    loan_proceeds = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Cash received from new loans"
    )
    loan_repayments = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Cash paid to repay loans"
    )
    equity_injections = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Cash received from equity investments"
    )
    dividends_paid = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Cash paid as dividends"
    )
    other_financing_cash = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Other financing cash flows"
    )

    # Metadata
    notes = models.TextField(blank=True, help_text="Notes about this period")
    is_finalized = models.BooleanField(
        default=False,
        help_text="Mark as finalized to prevent auto-recalculation"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_flow_snapshots'
    )

    class Meta:
        unique_together = ['year', 'month', 'billing_entity', 'currency']
        ordering = ['-year', '-month']
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['billing_entity', 'year', 'month']),
        ]
        verbose_name = 'Cash Flow Snapshot'
        verbose_name_plural = 'Cash Flow Snapshots'

    def __str__(self):
        return f"Cash Flow: {self.year}-{self.month:02d} | {self.currency} | {self.billing_entity}"


class ContractRevenueEvent(TimestampedModel):
    """
    Tracks revenue-impacting events for contracts (renewals, add-ons, churns, payments).
    Used for detailed audit trail and revenue recognition.
    """
    EVENT_TYPE_CHOICES = [
        ('new_contract', 'New Contract Signed'),
        ('renewal', 'Contract Renewed'),
        ('addon_zones', 'Zones Added'),
        ('removal_zones', 'Zones Removed'),
        ('value_increase', 'Value Increased'),
        ('value_decrease', 'Value Decreased'),
        ('payment_received', 'Payment Received'),
        ('payment_overdue', 'Payment Overdue'),
        ('churn', 'Contract Churned/Canceled'),
        ('reactivation', 'Contract Reactivated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='revenue_events',
        help_text="Contract associated with this event"
    )
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES,
        help_text="Type of revenue event"
    )
    event_date = models.DateField(
        help_text="Date when this event occurred"
    )

    # Financial impact
    contract_value_change = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Change in total contract value (positive or negative)"
    )
    monthly_value_change = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Change in monthly recurring value"
    )
    zone_count_change = models.IntegerField(
        default=0,
        help_text="Change in number of zones (positive or negative)"
    )

    # Payment tracking
    expected_payment_date = models.DateField(
        null=True,
        blank=True,
        help_text="When payment was expected"
    )
    actual_payment_date = models.DateField(
        null=True,
        blank=True,
        help_text="When payment was actually received"
    )
    payment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount of payment received"
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional details about this event"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contract_revenue_events',
        help_text="User who logged this event"
    )

    class Meta:
        ordering = ['-event_date', '-created_at']
        indexes = [
            models.Index(fields=['contract', 'event_date']),
            models.Index(fields=['event_type', 'event_date']),
            models.Index(fields=['event_date']),
            models.Index(fields=['contract', 'event_type']),
        ]
        verbose_name = 'Contract Revenue Event'
        verbose_name_plural = 'Contract Revenue Events'

    def __str__(self):
        return f"{self.contract.contract_number} | {self.get_event_type_display()} | {self.event_date}"


# Signal handlers for KB system
def update_article_rating_counts(sender, instance, **kwargs):
    """Update article's helpful/not_helpful counts when rating is saved"""
    article = instance.article
    article.helpful_count = article.ratings.filter(is_helpful=True).count()
    article.not_helpful_count = article.ratings.filter(is_helpful=False).count()
    article.save(update_fields=['helpful_count', 'not_helpful_count'])


# Connect signals
signals.post_save.connect(update_article_rating_counts, sender=KBArticleRating)
signals.post_delete.connect(update_article_rating_counts, sender=KBArticleRating)


# =============================================================================
# EXPENSE & ACCOUNTS PAYABLE MODELS (Finance Module - Phase 3)
# =============================================================================

class Vendor(TimestampedModel):
    """
    Supplier/vendor master for expense tracking and AP management.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Basic info
    name = models.CharField(max_length=255, help_text="Vendor/supplier name")
    legal_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Official registered company name for invoices"
    )
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Tax ID / VAT number"
    )

    # Contact info
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)

    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Payment info
    PAYMENT_TERMS_CHOICES = [
        ('immediate', 'Due on Receipt'),
        ('net_15', 'Net 15'),
        ('net_30', 'Net 30'),
        ('net_45', 'Net 45'),
        ('net_60', 'Net 60'),
    ]
    payment_terms = models.CharField(
        max_length=20,
        choices=PAYMENT_TERMS_CHOICES,
        default='net_30',
        help_text="Standard payment terms for this vendor"
    )
    default_currency = models.CharField(
        max_length=3,
        default='THB',
        help_text="Default currency for this vendor"
    )

    # Bank details for payments
    bank_name = models.CharField(max_length=255, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_account_name = models.CharField(max_length=255, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    # Billing entity association
    BILLING_ENTITY_CHOICES = [
        ('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'),
        ('bmasia_hk', 'BMAsia Limited'),
        ('both', 'Both Entities'),
    ]
    billing_entity = models.CharField(
        max_length=20,
        choices=BILLING_ENTITY_CHOICES,
        default='bmasia_th',
        help_text="Which BMAsia entity pays this vendor"
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['billing_entity']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = 'Vendor'
        verbose_name_plural = 'Vendors'

    def __str__(self):
        return self.name


class ExpenseCategory(TimestampedModel):
    """
    Hierarchical expense categories for P&L reporting.

    Top-level categories:
    - COGS (Cost of Goods Sold): Soundtrack licenses, hardware costs
    - G&A (General & Administrative): Salaries, rent, utilities, insurance
    - Sales & Marketing: Marketing campaigns, sales commissions, travel
    - CapEx (Capital Expenditure): Equipment, software licenses (capitalized)
    """
    CATEGORY_TYPE_CHOICES = [
        ('opex_cogs', 'Operating - COGS'),
        ('opex_gna', 'Operating - G&A'),
        ('opex_sales', 'Operating - Sales & Marketing'),
        ('capex', 'Capital Expenditure'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Category name")
    description = models.TextField(blank=True)

    category_type = models.CharField(
        max_length=20,
        choices=CATEGORY_TYPE_CHOICES,
        help_text="Which section of P&L this appears in"
    )

    # Hierarchy support
    parent_category = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        help_text="Parent category for nesting"
    )

    # For CapEx categories - depreciation settings
    is_depreciable = models.BooleanField(
        default=False,
        help_text="For CapEx: whether assets in this category depreciate"
    )
    useful_life_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="For CapEx: standard useful life in months (e.g., 36 for 3 years)"
    )
    depreciation_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Annual depreciation rate as percentage (e.g., 33.33 for 3-year assets)"
    )

    # Display order
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category_type', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['category_type']),
            models.Index(fields=['parent_category']),
        ]
        verbose_name = 'Expense Category'
        verbose_name_plural = 'Expense Categories'

    def __str__(self):
        if self.parent_category:
            return f"{self.parent_category.name} > {self.name}"
        return self.name

    @property
    def full_path(self):
        """Return full category path (e.g., 'G&A > Utilities > Electricity')"""
        if self.parent_category:
            return f"{self.parent_category.full_path} > {self.name}"
        return self.name


class RecurringExpense(TimestampedModel):
    """
    Fixed recurring monthly expenses.
    Auto-generates ExpenseEntry records each month.

    Examples: Office rent, Soundtrack licenses, software subscriptions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Basic info
    name = models.CharField(max_length=255, help_text="Expense description")
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name='recurring_expenses'
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_expenses'
    )

    # Amount
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Monthly amount"
    )
    currency = models.CharField(max_length=3, default='THB')

    # Billing entity
    BILLING_ENTITY_CHOICES = [
        ('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'),
        ('bmasia_hk', 'BMAsia Limited'),
    ]
    billing_entity = models.CharField(
        max_length=20,
        choices=BILLING_ENTITY_CHOICES,
        default='bmasia_th'
    )

    # Schedule
    start_date = models.DateField(help_text="When this expense starts")
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="When this expense ends (null = ongoing)"
    )
    payment_day = models.PositiveIntegerField(
        default=1,
        help_text="Day of month when payment is typically due (1-28)"
    )

    # Status
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    # Last auto-generated entry date (for cron job tracking)
    last_generated_month = models.DateField(
        null=True,
        blank=True,
        help_text="Last month for which an entry was auto-generated"
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['billing_entity']),
            models.Index(fields=['is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        verbose_name = 'Recurring Expense'
        verbose_name_plural = 'Recurring Expenses'

    def __str__(self):
        return f"{self.name} ({self.currency} {self.amount}/mo)"


class ExpenseEntry(TimestampedModel):
    """
    Individual expense record.
    Can be manually entered or auto-generated from RecurringExpense.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Basic info
    description = models.CharField(max_length=500, help_text="Expense description")
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name='expense_entries'
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense_entries'
    )

    # Link to recurring expense if auto-generated
    recurring_expense = models.ForeignKey(
        RecurringExpense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_entries',
        help_text="If auto-generated from a recurring expense"
    )

    # Amount
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Expense amount"
    )
    currency = models.CharField(max_length=3, default='THB')

    # Tax handling
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Tax amount (VAT, etc.)"
    )
    is_tax_inclusive = models.BooleanField(
        default=True,
        help_text="Whether the amount includes tax"
    )

    # Billing entity
    BILLING_ENTITY_CHOICES = [
        ('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'),
        ('bmasia_hk', 'BMAsia Limited'),
    ]
    billing_entity = models.CharField(
        max_length=20,
        choices=BILLING_ENTITY_CHOICES,
        default='bmasia_th'
    )

    # Dates
    expense_date = models.DateField(
        help_text="Date expense was incurred"
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Payment due date"
    )
    payment_date = models.DateField(
        null=True,
        blank=True,
        help_text="Actual payment date"
    )

    # Vendor invoice info
    vendor_invoice_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Vendor's invoice number"
    )
    vendor_invoice_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date on vendor's invoice"
    )

    # Status and workflow
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Payment info
    PAYMENT_METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('auto_debit', 'Auto Debit'),
    ]
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True
    )
    payment_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bank transfer reference, cheque number, etc."
    )

    # Approval workflow
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expenses'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Attachment (receipt/invoice)
    receipt_file = models.FileField(
        upload_to='expense_receipts/%Y/%m/',
        blank=True,
        null=True,
        help_text="Scanned receipt or invoice"
    )

    # Notes
    notes = models.TextField(blank=True)

    # Created by
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_expenses'
    )

    class Meta:
        ordering = ['-expense_date', '-created_at']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['vendor']),
            models.Index(fields=['billing_entity']),
            models.Index(fields=['expense_date']),
            models.Index(fields=['due_date']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['-expense_date', 'billing_entity']),
        ]
        verbose_name = 'Expense Entry'
        verbose_name_plural = 'Expense Entries'

    def __str__(self):
        return f"{self.expense_date} | {self.description[:50]} | {self.currency} {self.amount}"

    @property
    def total_amount(self):
        """Total amount including tax"""
        if self.is_tax_inclusive:
            return self.amount
        return self.amount + self.tax_amount

    @property
    def is_overdue(self):
        """Check if payment is overdue"""
        if self.status == 'paid' or not self.due_date:
            return False
        return self.due_date < timezone.now().date()

    @property
    def days_overdue(self):
        """Calculate days overdue (0 if not overdue)"""
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days


# =============================================================================
# BALANCE SHEET MODELS (Finance Module - Phase 6)
# =============================================================================

class BalanceSheetSnapshot(TimestampedModel):
    """
    Stores balance sheet data for a specific quarter.
    Allows manual overrides while calculating from underlying data when possible.
    Part of Finance Module - Phase 6 (Balance Sheet).

    Balance Sheet Structure:
    - ASSETS
      - Current Assets: Cash & Bank, Accounts Receivable, Other Current Assets
      - Fixed Assets: Equipment (less Accumulated Depreciation)
    - LIABILITIES
      - Current Liabilities: Accounts Payable, Accrued Expenses, Other Current
      - Long-term Liabilities: Long-term Debt, Other Long-term
    - EQUITY
      - Share Capital, Additional Paid-in Capital, Retained Earnings, Other Equity

    Accounting Equation: Assets = Liabilities + Equity
    """
    BILLING_ENTITY_CHOICES = [
        ('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'),
        ('bmasia_hk', 'BMAsia Limited'),
    ]
    CURRENCY_CHOICES = [
        ('THB', 'Thai Baht'),
        ('USD', 'US Dollar'),
    ]
    QUARTER_CHOICES = [
        (1, 'Q1 (Jan-Mar)'),
        (2, 'Q2 (Apr-Jun)'),
        (3, 'Q3 (Jul-Sep)'),
        (4, 'Q4 (Oct-Dec)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Period
    year = models.IntegerField(help_text="Year (e.g., 2026)")
    quarter = models.IntegerField(
        choices=QUARTER_CHOICES,
        help_text="Quarter (1-4)"
    )

    # Entity and currency
    billing_entity = models.CharField(
        max_length=20,
        choices=BILLING_ENTITY_CHOICES,
        help_text="Which BMAsia entity this applies to"
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='THB'
    )

    # ==========================================================================
    # ASSETS (null = calculate from data, value = override)
    # ==========================================================================

    # Current Assets
    cash_and_bank = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Cash and bank balances (from CashFlowSnapshot closing balance)"
    )
    accounts_receivable = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Outstanding customer invoices (Sent + Overdue)"
    )
    other_current_assets = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Manual entry: Prepaid expenses, deposits, etc."
    )

    # Fixed Assets
    gross_fixed_assets = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Total CapEx purchases (computer equipment, office equipment)"
    )
    accumulated_depreciation = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Total accumulated depreciation"
    )

    # ==========================================================================
    # LIABILITIES
    # ==========================================================================

    # Current Liabilities
    accounts_payable = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Outstanding vendor payments (pending + approved expenses)"
    )
    accrued_expenses = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Manual entry: Accrued salaries, taxes, etc."
    )
    other_current_liabilities = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Manual entry: Short-term portions of loans, etc."
    )

    # Long-term Liabilities
    long_term_debt = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Manual entry: Long-term loans and borrowings"
    )
    other_long_term_liabilities = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Manual entry: Deferred tax liabilities, etc."
    )

    # ==========================================================================
    # EQUITY
    # ==========================================================================

    share_capital = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Manual entry: Issued share capital"
    )
    additional_paid_in_capital = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Manual entry: Share premium / APIC"
    )
    retained_earnings = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text="Override: Cumulative net profit (calculated from P&L)"
    )
    other_equity = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Manual entry: Other reserves, adjustments"
    )

    # ==========================================================================
    # METADATA
    # ==========================================================================

    notes = models.TextField(blank=True, help_text="Notes about this period")
    is_finalized = models.BooleanField(
        default=False,
        help_text="Mark as finalized to prevent auto-recalculation"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='balance_sheet_snapshots'
    )

    class Meta:
        unique_together = ['year', 'quarter', 'billing_entity', 'currency']
        ordering = ['-year', '-quarter']
        indexes = [
            models.Index(fields=['year', 'quarter']),
            models.Index(fields=['billing_entity', 'year', 'quarter']),
        ]
        verbose_name = 'Balance Sheet Snapshot'
        verbose_name_plural = 'Balance Sheet Snapshots'

    def __str__(self):
        return f"Balance Sheet: {self.year} Q{self.quarter} | {self.currency} | {self.billing_entity}"

    @property
    def quarter_name(self):
        """Return quarter display name"""
        quarter_names = {1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4'}
        return quarter_names.get(self.quarter, f'Q{self.quarter}')
