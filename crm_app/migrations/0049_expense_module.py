# Generated manually for Expense Module (Finance Phase 3)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0048_finance_revenue_tracking'),
    ]

    operations = [
        # Create Vendor model
        migrations.CreateModel(
            name='Vendor',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Vendor/supplier name', max_length=255)),
                ('legal_name', models.CharField(blank=True, help_text='Official registered company name for invoices', max_length=255)),
                ('tax_id', models.CharField(blank=True, help_text='Tax ID / VAT number', max_length=50)),
                ('contact_name', models.CharField(blank=True, max_length=255)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('website', models.URLField(blank=True)),
                ('address', models.TextField(blank=True)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('country', models.CharField(blank=True, max_length=100)),
                ('payment_terms', models.CharField(choices=[('immediate', 'Due on Receipt'), ('net_15', 'Net 15'), ('net_30', 'Net 30'), ('net_45', 'Net 45'), ('net_60', 'Net 60')], default='net_30', help_text='Standard payment terms for this vendor', max_length=20)),
                ('default_currency', models.CharField(default='THB', help_text='Default currency for this vendor', max_length=3)),
                ('bank_name', models.CharField(blank=True, max_length=255)),
                ('bank_account_number', models.CharField(blank=True, max_length=50)),
                ('bank_account_name', models.CharField(blank=True, max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('billing_entity', models.CharField(choices=[('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'), ('bmasia_hk', 'BMAsia Limited'), ('both', 'Both Entities')], default='bmasia_th', help_text='Which BMAsia entity pays this vendor', max_length=20)),
            ],
            options={
                'verbose_name': 'Vendor',
                'verbose_name_plural': 'Vendors',
                'ordering': ['name'],
            },
        ),
        migrations.AddIndex(
            model_name='vendor',
            index=models.Index(fields=['name'], name='crm_app_ven_name_8b1234_idx'),
        ),
        migrations.AddIndex(
            model_name='vendor',
            index=models.Index(fields=['billing_entity'], name='crm_app_ven_billing_a1b2c3_idx'),
        ),
        migrations.AddIndex(
            model_name='vendor',
            index=models.Index(fields=['is_active'], name='crm_app_ven_is_acti_d4e5f6_idx'),
        ),

        # Create ExpenseCategory model
        migrations.CreateModel(
            name='ExpenseCategory',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Category name', max_length=255)),
                ('description', models.TextField(blank=True)),
                ('category_type', models.CharField(choices=[('opex_cogs', 'Operating - COGS'), ('opex_gna', 'Operating - G&A'), ('opex_sales', 'Operating - Sales & Marketing'), ('capex', 'Capital Expenditure')], help_text='Which section of P&L this appears in', max_length=20)),
                ('is_depreciable', models.BooleanField(default=False, help_text='For CapEx: whether assets in this category depreciate')),
                ('useful_life_months', models.PositiveIntegerField(blank=True, help_text='For CapEx: standard useful life in months (e.g., 36 for 3 years)', null=True)),
                ('depreciation_rate', models.DecimalField(blank=True, decimal_places=2, help_text='Annual depreciation rate as percentage (e.g., 33.33 for 3-year assets)', max_digits=5, null=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('parent_category', models.ForeignKey(blank=True, help_text='Parent category for nesting', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='subcategories', to='crm_app.expensecategory')),
            ],
            options={
                'verbose_name': 'Expense Category',
                'verbose_name_plural': 'Expense Categories',
                'ordering': ['category_type', 'sort_order', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='expensecategory',
            index=models.Index(fields=['category_type'], name='crm_app_exp_cat_typ_g7h8i9_idx'),
        ),
        migrations.AddIndex(
            model_name='expensecategory',
            index=models.Index(fields=['parent_category'], name='crm_app_exp_parent_j0k1l2_idx'),
        ),

        # Create RecurringExpense model
        migrations.CreateModel(
            name='RecurringExpense',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Expense description', max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, help_text='Monthly amount', max_digits=15)),
                ('currency', models.CharField(default='THB', max_length=3)),
                ('billing_entity', models.CharField(choices=[('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'), ('bmasia_hk', 'BMAsia Limited')], default='bmasia_th', max_length=20)),
                ('start_date', models.DateField(help_text='When this expense starts')),
                ('end_date', models.DateField(blank=True, help_text='When this expense ends (null = ongoing)', null=True)),
                ('payment_day', models.PositiveIntegerField(default=1, help_text='Day of month when payment is typically due (1-28)')),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('last_generated_month', models.DateField(blank=True, help_text='Last month for which an entry was auto-generated', null=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='recurring_expenses', to='crm_app.expensecategory')),
                ('vendor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurring_expenses', to='crm_app.vendor')),
            ],
            options={
                'verbose_name': 'Recurring Expense',
                'verbose_name_plural': 'Recurring Expenses',
                'ordering': ['name'],
            },
        ),
        migrations.AddIndex(
            model_name='recurringexpense',
            index=models.Index(fields=['category'], name='crm_app_rec_cat_m3n4o5_idx'),
        ),
        migrations.AddIndex(
            model_name='recurringexpense',
            index=models.Index(fields=['billing_entity'], name='crm_app_rec_billing_p6q7r8_idx'),
        ),
        migrations.AddIndex(
            model_name='recurringexpense',
            index=models.Index(fields=['is_active'], name='crm_app_rec_is_acti_s9t0u1_idx'),
        ),
        migrations.AddIndex(
            model_name='recurringexpense',
            index=models.Index(fields=['start_date', 'end_date'], name='crm_app_rec_start_v2w3x4_idx'),
        ),

        # Create ExpenseEntry model
        migrations.CreateModel(
            name='ExpenseEntry',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('description', models.CharField(help_text='Expense description', max_length=500)),
                ('amount', models.DecimalField(decimal_places=2, help_text='Expense amount', max_digits=15)),
                ('currency', models.CharField(default='THB', max_length=3)),
                ('tax_amount', models.DecimalField(decimal_places=2, default=0, help_text='Tax amount (VAT, etc.)', max_digits=15)),
                ('is_tax_inclusive', models.BooleanField(default=True, help_text='Whether the amount includes tax')),
                ('billing_entity', models.CharField(choices=[('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'), ('bmasia_hk', 'BMAsia Limited')], default='bmasia_th', max_length=20)),
                ('expense_date', models.DateField(help_text='Date expense was incurred')),
                ('due_date', models.DateField(blank=True, help_text='Payment due date', null=True)),
                ('payment_date', models.DateField(blank=True, help_text='Actual payment date', null=True)),
                ('vendor_invoice_number', models.CharField(blank=True, help_text="Vendor's invoice number", max_length=100)),
                ('vendor_invoice_date', models.DateField(blank=True, help_text="Date on vendor's invoice", null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending Approval'), ('approved', 'Approved'), ('paid', 'Paid'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('payment_method', models.CharField(blank=True, choices=[('bank_transfer', 'Bank Transfer'), ('credit_card', 'Credit Card'), ('cash', 'Cash'), ('cheque', 'Cheque'), ('auto_debit', 'Auto Debit')], max_length=20)),
                ('payment_reference', models.CharField(blank=True, help_text='Bank transfer reference, cheque number, etc.', max_length=255)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('receipt_file', models.FileField(blank=True, help_text='Scanned receipt or invoice', null=True, upload_to='expense_receipts/%Y/%m/')),
                ('notes', models.TextField(blank=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_expenses', to=settings.AUTH_USER_MODEL)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='expense_entries', to='crm_app.expensecategory')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_expenses', to=settings.AUTH_USER_MODEL)),
                ('recurring_expense', models.ForeignKey(blank=True, help_text='If auto-generated from a recurring expense', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_entries', to='crm_app.recurringexpense')),
                ('vendor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='expense_entries', to='crm_app.vendor')),
            ],
            options={
                'verbose_name': 'Expense Entry',
                'verbose_name_plural': 'Expense Entries',
                'ordering': ['-expense_date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='expenseentry',
            index=models.Index(fields=['category'], name='crm_app_exp_cat_y5z6a7_idx'),
        ),
        migrations.AddIndex(
            model_name='expenseentry',
            index=models.Index(fields=['vendor'], name='crm_app_exp_vendor_b8c9d0_idx'),
        ),
        migrations.AddIndex(
            model_name='expenseentry',
            index=models.Index(fields=['billing_entity'], name='crm_app_exp_billing_e1f2g3_idx'),
        ),
        migrations.AddIndex(
            model_name='expenseentry',
            index=models.Index(fields=['expense_date'], name='crm_app_exp_exp_dat_h4i5j6_idx'),
        ),
        migrations.AddIndex(
            model_name='expenseentry',
            index=models.Index(fields=['due_date'], name='crm_app_exp_due_dat_k7l8m9_idx'),
        ),
        migrations.AddIndex(
            model_name='expenseentry',
            index=models.Index(fields=['status'], name='crm_app_exp_status_n0o1p2_idx'),
        ),
        migrations.AddIndex(
            model_name='expenseentry',
            index=models.Index(fields=['payment_date'], name='crm_app_exp_pay_dat_q3r4s5_idx'),
        ),
        migrations.AddIndex(
            model_name='expenseentry',
            index=models.Index(fields=['-expense_date', 'billing_entity'], name='crm_app_exp_exp_bil_t6u7v8_idx'),
        ),
    ]
