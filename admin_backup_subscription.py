# Backup of SubscriptionPlan code for reference

class SubscriptionPlanInline(admin.TabularInline):
    model = SubscriptionPlan
    extra = 1
    fields = ['tier', 'zone_count', 'billing_period', 'price_per_zone', 'currency']
    verbose_name = "Subscription Tier"
    verbose_name_plural = "Subscription Tiers (can have multiple tiers)"
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Remove spinners from numeric fields and make them smaller
        if db_field.name in ['price_per_zone', 'zone_count']:
            kwargs['widget'] = admin.widgets.AdminTextInputWidget(attrs={
                'type': 'text',
                'style': 'width: 80px;'
            })
        return super().formfield_for_dbfield(db_field, request, **kwargs)


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