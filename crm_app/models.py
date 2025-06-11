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
    country = models.CharField(max_length=100, blank=True)
    
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
        super().save(*args, **kwargs)


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
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contracts')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')
    contract_number = models.CharField(max_length=50, unique=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES, default='Annual')
    status = models.CharField(max_length=20, choices=CONTRACT_STATUS_CHOICES, default='Draft')
    start_date = models.DateField()
    end_date = models.DateField()
    value = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
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
        if self.end_date and self.start_date:
            months = ((self.end_date.year - self.start_date.year) * 12 + 
                     (self.end_date.month - self.start_date.month))
            return self.value / months if months > 0 else 0
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
    currency = models.CharField(max_length=3, default='USD')
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


class SubscriptionPlan(TimestampedModel):
    """Track multiple subscription tiers for a company"""
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
    zone_count = models.IntegerField(default=1, help_text="Number of music zones for this tier")
    billing_period = models.CharField(max_length=20, choices=BILLING_PERIOD_CHOICES, default='Monthly')
    price_per_zone = models.IntegerField(null=True, blank=True, help_text="Price per zone (no decimals)")
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
        """Calculate total value for this tier"""
        if self.price_per_zone:
            return self.zone_count * self.price_per_zone
        return 0
    
    @property
    def monthly_value(self):
        """Calculate monthly value for comparison"""
        if not self.price_per_zone:
            return 0
        total = self.zone_count * self.price_per_zone
        if self.billing_period == 'Yearly':
            return total / 12
        return total
    
    @property
    def display_price(self):
        """Display price with currency"""
        if self.price_per_zone:
            return f"{self.currency} {self.price_per_zone:,}"
        return "Not set"


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
        # Simple display for inline admin headers
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
