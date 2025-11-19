from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import EmailValidator, RegexValidator
from django.utils import timezone
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
    receives_notifications = models.BooleanField(default=True, help_text="Whether this contact receives automated emails")
    notification_types = models.JSONField(default=list, blank=True, help_text="List of notification types this contact should receive")
    preferred_language = models.CharField(max_length=2, choices=[('en', 'English'), ('th', 'Thai')], default='en')
    unsubscribed = models.BooleanField(default=False, help_text="Has unsubscribed from all emails")
    unsubscribe_token = models.CharField(max_length=64, blank=True, help_text="Token for unsubscribe links")
    
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
    """Enhanced Task model with better tracking and priorities"""
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('On Hold', 'On Hold'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tasks')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    department = models.CharField(max_length=20, choices=User.ROLE_CHOICES, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    
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
        return self.due_date and self.due_date < timezone.now() and self.status != 'Completed'
    
    def save(self, *args, **kwargs):
        if self.status == 'Completed' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != 'Completed':
            self.completed_at = None
        super().save(*args, **kwargs)


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
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='opportunities')
    name = models.CharField(max_length=255)
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
        ('Draft', 'Draft'),
        ('Sent', 'Sent for Signature'),
        ('Signed', 'Signed'),
        ('Active', 'Active'),
        ('Expired', 'Expired'),
        ('Terminated', 'Terminated'),
        ('Renewed', 'Renewed'),
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
    contract_number = models.CharField(max_length=50, unique=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES, default='Annual')
    service_type = models.CharField(max_length=50, choices=SERVICE_TYPE_CHOICES, blank=True, help_text="Specific service or plan")
    status = models.CharField(max_length=20, choices=CONTRACT_STATUS_CHOICES, default='Draft')
    start_date = models.DateField()
    end_date = models.DateField()
    value = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    auto_renew = models.BooleanField(default=False)
    renewal_period_months = models.IntegerField(default=12)
    is_active = models.BooleanField(default=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    billing_frequency = models.CharField(max_length=20, default='Annual')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    
    # Renewal tracking
    renewal_notice_sent = models.BooleanField(default=False)
    renewal_notice_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['end_date', 'auto_renew']),
            models.Index(fields=['status', 'end_date']),
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
        """Check if contract expires within 30 days"""
        if self.end_date:
            return 0 <= self.days_until_expiry <= 30
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
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='invoices')
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
        return f"{self.invoice_number} - {self.contract.company.name}"
    
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


class Zone(TimestampedModel):
    """Track individual music zones for companies"""
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('no_device', 'No Device Paired'),
        ('expired', 'Subscription Expired'),
        ('pending', 'Pending Activation'),
    ]
    
    PLATFORM_CHOICES = [
        ('soundtrack', 'Soundtrack Your Brand'),
        ('beatbreeze', 'Beat Breeze'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='zones')
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
        ('seasonal_songkran', 'Songkran Preparation'),
        ('seasonal_ramadan', 'Ramadan Preparation'),
        
        # Technical Support templates
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
            created_by=None  # System generated
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="e.g., 'New Customer Onboarding'")
    description = models.TextField(blank=True, help_text="What this sequence does")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_sequences')

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
