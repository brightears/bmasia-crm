# Hand-trimmed: makemigrations also proposed pre-existing, unrelated drift
# (index renames, documentsequence.id, emaillog.email_type choices). Those are
# left out on purpose; this migration only adds the LeadResearchRun and
# ResearchLead tables and the 'AI Research' opportunity lead source.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm_app", "0105_care_touch"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeadResearchRun",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="running",
                        max_length=20,
                    ),
                ),
                (
                    "segments",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Segments searched, e.g. ['hotel', 'retail', 'qsr']",
                    ),
                ),
                ("countries", models.JSONField(blank=True, default=list)),
                ("model", models.CharField(blank=True, max_length=100)),
                ("leads_proposed", models.IntegerField(default=0)),
                ("leads_saved", models.IntegerField(default=0)),
                ("duplicates_skipped", models.IntegerField(default=0)),
                ("web_searches", models.IntegerField(default=0)),
                ("input_tokens", models.IntegerField(default=0)),
                ("output_tokens", models.IntegerField(default=0)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ResearchLead",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="new",
                        max_length=20,
                    ),
                ),
                ("venue_name", models.CharField(max_length=255)),
                ("brand_or_group", models.CharField(blank=True, max_length=255)),
                (
                    "segment",
                    models.CharField(
                        choices=[
                            ("hotel", "Hotel / Resort"),
                            ("retail", "Retail"),
                            ("qsr", "Quick Service Restaurant"),
                            ("fnb", "Restaurant / Bar / Cafe"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                ("country", models.CharField(blank=True, max_length=100)),
                ("city", models.CharField(blank=True, max_length=100)),
                (
                    "opening_timeframe",
                    models.CharField(
                        blank=True,
                        help_text="As reported, e.g. 'Q2 2027' or 'opened Nov 2026'",
                        max_length=100,
                    ),
                ),
                (
                    "signal",
                    models.TextField(
                        help_text="What happened: opening, rebrand, renovation, new outlets"
                    ),
                ),
                ("source_urls", models.JSONField(blank=True, default=list)),
                ("website", models.URLField(blank=True)),
                ("estimated_zones", models.IntegerField(blank=True, null=True)),
                (
                    "suggested_product",
                    models.CharField(
                        choices=[
                            ("beatbreeze", "Beat Breeze"),
                            ("soundtrack", "Soundtrack"),
                        ],
                        default="beatbreeze",
                        max_length=20,
                    ),
                ),
                ("fit_reason", models.TextField(blank=True)),
                ("decision_maker_name", models.CharField(blank=True, max_length=255)),
                ("decision_maker_title", models.CharField(blank=True, max_length=255)),
                (
                    "contact_email",
                    models.EmailField(
                        blank=True,
                        help_text="Only a publicly listed business address",
                        max_length=254,
                    ),
                ),
                (
                    "personal_hook",
                    models.TextField(
                        blank=True,
                        help_text="A specific detail to open the outreach with",
                    ),
                ),
                (
                    "score",
                    models.IntegerField(
                        default=0, help_text="Fit score 0-100 from the research model"
                    ),
                ),
                ("dedupe_key", models.CharField(db_index=True, max_length=255)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "ordering": ["-score", "-created_at"],
            },
        ),
        migrations.AlterField(
            model_name="opportunity",
            name="lead_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Website", "Website"),
                    ("Website Inquiry", "Website Inquiry"),
                    ("Referral", "Referral"),
                    ("Cold Call", "Cold Call"),
                    ("Email Campaign", "Email Campaign"),
                    ("Social Media", "Social Media"),
                    ("Trade Show", "Trade Show"),
                    ("Partner", "Partner"),
                    ("Direct Mail", "Direct Mail"),
                    ("Webinar", "Webinar"),
                    ("AI Research", "AI Research"),
                    ("Other", "Other"),
                ],
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="leadresearchrun",
            name="triggered_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lead_research_runs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="researchlead",
            name="matched_company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="research_leads",
                to="crm_app.company",
            ),
        ),
        migrations.AddField(
            model_name="researchlead",
            name="opportunity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="research_leads",
                to="crm_app.opportunity",
            ),
        ),
        migrations.AddField(
            model_name="researchlead",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_research_leads",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="researchlead",
            name="run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="leads",
                to="crm_app.leadresearchrun",
            ),
        ),
        migrations.AddIndex(
            model_name="researchlead",
            index=models.Index(
                fields=["status", "-score"], name="crm_app_res_status_a94242_idx"
            ),
        ),
    ]
