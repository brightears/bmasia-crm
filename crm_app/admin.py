from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.admin import SimpleListFilter
from django.utils.html import format_html
from .models import (
    User, Company, Contact, Note, Task, AuditLog,
    Opportunity, OpportunityActivity, Contract, Invoice, SubscriptionPlan, Zone
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('CRM Info', {'fields': ('role', 'phone', 'department', 'last_login_ip')}),
    )
    list_display = ['username', 'email', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0
    fields = ['name', 'email', 'phone', 'title', 'contact_type', 'is_primary', 'is_active']


class NoteInline(admin.TabularInline):
    model = Note
    extra = 0
    fields = ['title', 'note_type', 'priority', 'text']


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ['title', 'assigned_to', 'priority', 'status', 'due_date']


class SubscriptionPlanInline(admin.TabularInline):
    model = SubscriptionPlan
    extra = 1
    fields = ['tier', 'zone_count', 'billing_period', 'price_per_zone', 'currency', 'is_active', 'start_date', 'end_date']
    verbose_name = "Subscription Tier"
    verbose_name_plural = "Subscription Tiers (can have multiple tiers)"
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Remove spinners from numeric fields
        if db_field.name in ['price_per_zone', 'zone_count']:
            kwargs['widget'] = admin.widgets.AdminTextInputWidget(attrs={'type': 'text'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class CompanyZoneInline(admin.TabularInline):
    model = Zone
    extra = 0
    fields = ['name', 'currently_playing_display', 'status_badge_inline', 'device_name', 'last_seen_online']
    readonly_fields = ['name', 'currently_playing_display', 'status_badge_inline', 'last_seen_online', 'platform']
    verbose_name = "Music Zone"
    verbose_name_plural = "Music Zones (auto-synced from Soundtrack)"
    can_delete = False
    
    def currently_playing_display(self, obj):
        """Display what's currently playing instead of zone ID"""
        if obj.api_raw_data and obj.api_raw_data.get('currently_playing'):
            return obj.api_raw_data.get('currently_playing')
        return "No active playlist/schedule"
    currently_playing_display.short_description = "Currently Playing"
    
    def status_badge_inline(self, obj):
        """Display status with color coding"""
        colors = {
            "online": "green",
            "offline": "red", 
            "no_device": "#DAA520",  # Golden yellow
            "expired": "gray",
            "pending": "gray"
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            "<span style=\"padding: 3px 8px; border-radius: 3px; color: white; background-color: {}; font-size: 11px;\">{}</span>",
            color, obj.get_status_display()
        )
    status_badge_inline.short_description = "Status"
    
    def has_add_permission(self, request, obj):
        # Don't allow manual adding for Soundtrack companies
        return False
    
    def get_queryset(self, request):
        # Only show Soundtrack zones
        qs = super().get_queryset(request)
        return qs.filter(platform='soundtrack')


class BeatBreezeZoneInline(admin.TabularInline):
    model = Zone
    extra = 1
    fields = ['name', 'status', 'device_name', 'notes']
    verbose_name = "Beat Breeze Zone"
    verbose_name_plural = "Beat Breeze Zones (manual entry)"
    
    def get_queryset(self, request):
        # Only show Beat Breeze zones
        qs = super().get_queryset(request)
        return qs.filter(platform='beatbreeze')
    
    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'platform':
            kwargs['initial'] = 'beatbreeze'
        return super().formfield_for_choice_field(db_field, request, **kwargs)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'industry', 'location_count', 'music_zone_count', 'soundtrack_status']
    list_filter = ['country', 'industry']
    search_fields = ['name', 'website', 'notes', 'soundtrack_account_id']
    readonly_fields = ['created_at', 'updated_at', 'current_subscription_summary', 'zones_status_summary']
    actions = ['sync_soundtrack_zones']
    
    def get_inlines(self, request, obj):
        """Show different inlines based on whether company has Soundtrack account"""
        if obj and obj.soundtrack_account_id:
            return [CompanyZoneInline, SubscriptionPlanInline, ContactInline, NoteInline, TaskInline]
        else:
            return [BeatBreezeZoneInline, SubscriptionPlanInline, ContactInline, NoteInline, TaskInline]
    
    def soundtrack_status(self, obj):
        if obj.soundtrack_account_id:
            return format_html('<span style="color: green;">✓ Connected</span>')
        return format_html('<span style="color: gray;">Not connected</span>')
    soundtrack_status.short_description = "Soundtrack"
    
    def zones_status_summary(self, obj):
        """Display summary of zone statuses from Soundtrack API"""
        if not obj.soundtrack_account_id:
            return "No Soundtrack account ID configured"
        
        try:
            from .services.soundtrack_api import soundtrack_api
            # Get zones specifically for this account ID
            api_zones = soundtrack_api.get_account_zones(obj.soundtrack_account_id)
            
            if not api_zones:
                return "No zones found for this account ID"
            
            status_counts = {}
            zone_details = []
            
            for zone in api_zones:
                status = zone.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # Create detailed zone info with playlist/schedule
                currently_playing = zone.get('currently_playing', 'No active playlist/schedule')
                zone_details.append(f"• <strong>{zone.get('zone_name', 'Unknown')}</strong>: {currently_playing} <em>({status})</em>")
            
            # Create summary with counts
            summary_parts = []
            for status, count in status_counts.items():
                summary_parts.append(f"{count} {status.title()}")
            
            summary = ", ".join(summary_parts)
            
            # Add detailed zone list
            details = "<br>".join(zone_details)
            
            return format_html(f"{summary}<br><br><small>{details}</small>")
            
        except Exception as e:
            return f"Error fetching zones: {str(e)}"
    zones_status_summary.short_description = "Zone Status Summary"
    
    def sync_soundtrack_zones(self, request, queryset):
        """Sync zones with Soundtrack API for selected companies"""
        from .services.soundtrack_api import soundtrack_api
        
        total_synced = 0
        total_errors = 0
        
        for company in queryset:
            if company.soundtrack_account_id:
                try:
                    synced, errors = soundtrack_api.sync_company_zones(company)
                    total_synced += synced
                    total_errors += errors
                    if synced > 0:
                        self.message_user(request, f"✓ {company.name}: Synced {synced} zones")
                except Exception as e:
                    self.message_user(request, f"✗ {company.name}: Error - {str(e)}", level='ERROR')
                    total_errors += 1
            else:
                self.message_user(request, f"✗ {company.name}: No Soundtrack account ID", level='WARNING')
        
        if total_synced > 0:
            self.message_user(request, f"Successfully synced {total_synced} zones total")
    sync_soundtrack_zones.short_description = "Sync Soundtrack zones"
    
    def save_model(self, request, obj, form, change):
        """Auto-sync zones when Soundtrack account ID is added or changed"""
        import logging
        logger = logging.getLogger(__name__)
        
        old_account_id = None
        if change and obj.pk:
            old_obj = Company.objects.get(pk=obj.pk)
            old_account_id = old_obj.soundtrack_account_id
        
        super().save_model(request, obj, form, change)
        
        logger.info(f"Saving company {obj.name}, soundtrack_account_id: {obj.soundtrack_account_id}, old: {old_account_id}")
        
        # If Soundtrack account ID was added or changed, sync zones
        if obj.soundtrack_account_id and obj.soundtrack_account_id != old_account_id:
            from .services.soundtrack_api import soundtrack_api
            try:
                logger.info(f"Attempting to sync zones for {obj.name}")
                synced, errors = soundtrack_api.sync_company_zones(obj)
                logger.info(f"Sync result: {synced} synced, {errors} errors")
                if synced > 0:
                    self.message_user(request, f"✓ Automatically synced {synced} zones from Soundtrack", 'SUCCESS')
                else:
                    self.message_user(request, f"No zones synced. Check the API connection.", 'WARNING')
            except Exception as e:
                logger.error(f"Error syncing zones: {str(e)}")
                self.message_user(request, f"Could not sync zones: {str(e)}", 'WARNING')
    
    def current_subscription_summary(self, obj):
        """Display a summary of current subscription plans"""
        plans = obj.subscription_plans.filter(is_active=True)
        if not plans:
            return "No active subscription plans"
        
        summary = []
        total_zones = 0
        for plan in plans:
            summary.append(f"{plan.tier}: {plan.zone_count} zones")
            total_zones += plan.zone_count
        
        return " | ".join(summary) + f" (Total: {total_zones} zones)"
    
    current_subscription_summary.short_description = "Current Subscription Plans"
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'country', 'industry', 'website', 'location_count', 'music_zone_count'),
        }),
        ('Soundtrack Integration', {
            'fields': ('soundtrack_account_id', 'zones_status_summary'),
        }),
        ('Subscription Details', {
            'fields': ('current_subscription_summary',),
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'email', 'phone', 'contact_type', 'is_primary', 'is_active']
    list_filter = ['contact_type', 'is_primary', 'is_active', 'company__country']
    search_fields = ['name', 'email', 'company__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'author', 'note_type', 'priority', 'created_at']
    list_filter = ['note_type', 'priority', 'is_private', 'created_at']
    search_fields = ['title', 'text', 'company__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'assigned_to', 'priority', 'status', 'due_date', 'is_overdue']
    list_filter = ['priority', 'status', 'department', 'created_at']
    search_fields = ['title', 'description', 'company__name']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    
    def is_overdue(self, obj):
        return obj.is_overdue
    is_overdue.boolean = True


class OpportunityActivityInline(admin.TabularInline):
    model = OpportunityActivity
    extra = 0
    fields = ['activity_type', 'subject', 'user', 'contact', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'stage', 'expected_value', 'probability', 'owner', 'expected_close_date']
    list_filter = ['stage', 'lead_source', 'is_active', 'created_at']
    search_fields = ['name', 'company__name', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'weighted_value', 'days_in_stage']
    inlines = [OpportunityActivityInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('company', 'name', 'stage', 'owner', 'is_active')
        }),
        ('Financial', {
            'fields': ('expected_value', 'probability', 'weighted_value')
        }),
        ('Source & Method', {
            'fields': ('lead_source', 'contact_method')
        }),
        ('Dates', {
            'fields': ('last_contact_date', 'follow_up_date', 'expected_close_date', 'actual_close_date')
        }),
        ('Details', {
            'fields': ('competitors', 'pain_points', 'decision_criteria', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'days_in_stage'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OpportunityActivity)
class OpportunityActivityAdmin(admin.ModelAdmin):
    list_display = ['subject', 'opportunity', 'activity_type', 'user', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['subject', 'description', 'opportunity__name']
    readonly_fields = ['created_at', 'updated_at']


class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    fields = ['invoice_number', 'status', 'issue_date', 'due_date', 'total_amount']


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ['contract_number', 'company', 'contract_type', 'status', 'start_date', 'end_date', 'value', 'is_expiring_soon']
    list_filter = ['contract_type', 'status', 'auto_renew', 'is_active']
    search_fields = ['contract_number', 'company__name']
    readonly_fields = ['created_at', 'updated_at', 'days_until_expiry', 'monthly_value']
    inlines = [InvoiceInline]
    
    def is_expiring_soon(self, obj):
        return obj.is_expiring_soon
    is_expiring_soon.boolean = True
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('company', 'opportunity', 'contract_number', 'contract_type', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'days_until_expiry')
        }),
        ('Financial', {
            'fields': ('value', 'monthly_value', 'currency', 'discount_percentage')
        }),
        ('Terms', {
            'fields': ('payment_terms', 'billing_frequency', 'auto_renew', 'renewal_period_months')
        }),
        ('Renewal Tracking', {
            'fields': ('renewal_notice_sent', 'renewal_notice_date'),
            'classes': ('collapse',)
        }),
        ('Other', {
            'fields': ('is_active', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'contract', 'status', 'issue_date', 'due_date', 'total_amount', 'days_overdue']
    list_filter = ['status', 'issue_date', 'due_date']
    search_fields = ['invoice_number', 'contract__company__name', 'contract__contract_number']
    readonly_fields = ['created_at', 'updated_at', 'total_amount', 'days_overdue']
    
    def days_overdue(self, obj):
        return obj.days_overdue if obj.is_overdue else 0
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('contract', 'invoice_number', 'status')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date', 'paid_date', 'days_overdue')
        }),
        ('Financial', {
            'fields': ('amount', 'tax_amount', 'discount_amount', 'total_amount', 'currency')
        }),
        ('Payment', {
            'fields': ('payment_method', 'transaction_id')
        }),
        ('Reminders', {
            'fields': ('first_reminder_sent', 'second_reminder_sent', 'final_notice_sent'),
            'classes': ('collapse',)
        }),
        ('Other', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'record_id', 'timestamp']
    list_filter = ['action', 'model_name', 'timestamp']
    search_fields = ['user__username', 'model_name', 'record_id']
    readonly_fields = ['user', 'action', 'model_name', 'record_id', 'timestamp', 'ip_address', 'user_agent', 'changes', 'additional_data']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['company', 'tier', 'zone_count', 'billing_period', 'display_price_per_zone', 'display_total_value', 'currency', 'is_active']
    list_filter = ['tier', 'billing_period', 'currency', 'is_active', 'start_date', 'end_date']
    search_fields = ['company__name', 'tier', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'display_total_value', 'display_monthly_value']
    
    def display_price_per_zone(self, obj):
        if obj.price_per_zone:
            return f"{obj.currency} {obj.price_per_zone:,}"
        return "-"
    display_price_per_zone.short_description = "Price per Zone"
    
    def display_total_value(self, obj):
        if obj.total_value:
            return f"{obj.currency} {obj.total_value:,} ({obj.billing_period})"
        return "-"
    display_total_value.short_description = "Total Value"
    
    def display_monthly_value(self, obj):
        if obj.monthly_value:
            return f"{obj.currency} {obj.monthly_value:,.0f}/month"
        return "-"
    display_monthly_value.short_description = "Monthly Equivalent"
    
    fieldsets = (
        ('Company & Tier', {
            'fields': ('company', 'tier')
        }),
        ('Pricing', {
            'fields': ('zone_count', 'billing_period', 'price_per_zone', 'currency', 'display_total_value', 'display_monthly_value'),
            'description': 'Enter whole numbers only for pricing (e.g., 25 for USD 25, 900 for THB 900)'
        }),
        ('Duration', {
            'fields': ('is_active', 'start_date', 'end_date')
        }),
        ('Additional Info', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )



@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ["zone_name_with_company", "platform", "currently_playing_admin", "status_badge", "last_seen_online", "last_api_sync"]
    list_filter = ["platform", "status", "company"]
    search_fields = ["name", "company__name", "company__soundtrack_account_id"]
    readonly_fields = ["created_at", "updated_at", "last_api_sync", "api_raw_data", "status_badge", "soundtrack_account_id", "currently_playing_admin"]
    
    def zone_name_with_company(self, obj):
        return f"{obj.company.name} - {obj.name}"
    zone_name_with_company.short_description = "Zone"
    zone_name_with_company.admin_order_field = "company__name"
    
    def currently_playing_admin(self, obj):
        """Display what's currently playing"""
        if obj.api_raw_data and obj.api_raw_data.get('currently_playing'):
            return obj.api_raw_data.get('currently_playing')
        return "No active playlist/schedule"
    currently_playing_admin.short_description = "Currently Playing"
    
    def status_badge(self, obj):
        colors = {
            "online": "green",
            "offline": "orange",
            "no_device": "red",
            "expired": "gray",
            "pending": "blue"
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            "<span style=\"padding: 3px 10px; border-radius: 3px; color: white; background-color: {};\">{}</span>",
            color, obj.get_status_display()
        )
    status_badge.short_description = "Status"
    
    fieldsets = (
        ("Zone Information", {
            "fields": ("company", "name", "platform")
        }),
        ("Status", {
            "fields": ("status", "status_badge", "currently_playing_admin", "last_seen_online", "device_name")
        }),
        ("Soundtrack Integration", {
            "fields": ("soundtrack_account_id", "soundtrack_zone_id", "soundtrack_admin_email"),
            "description": "Account ID is inherited from the company. Zone-specific data from API is shown here."
        }),
        ("API Sync", {
            "fields": ("last_api_sync", "api_raw_data"),
            "classes": ("collapse",)
        }),
        ("Additional Info", {
            "fields": ("notes",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    actions = ["sync_with_soundtrack_api"]
    
    def sync_with_soundtrack_api(self, request, queryset):
        """Action to sync selected zones with Soundtrack API"""
        from django.utils import timezone
        from .services.soundtrack_api import soundtrack_api
        
        # Group zones by company for efficient syncing
        companies_to_sync = set()
        for zone in queryset.filter(platform="soundtrack"):
            if zone.company.soundtrack_account_id:
                companies_to_sync.add(zone.company)
        
        total_synced = 0
        for company in companies_to_sync:
            try:
                synced, errors = soundtrack_api.sync_company_zones(company)
                total_synced += synced
                if synced > 0:
                    self.message_user(request, f"✓ Synced {synced} zones for {company.name}")
            except Exception as e:
                self.message_user(request, f"Error syncing {company.name}: {str(e)}", level="ERROR")
        
        if total_synced > 0:
            self.message_user(request, f"Successfully synced {total_synced} zones total")
    sync_with_soundtrack_api.short_description = "Sync with Soundtrack API"
