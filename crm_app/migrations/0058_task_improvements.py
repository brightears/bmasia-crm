import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def convert_task_statuses(apps, schema_editor):
    """Convert old status values to new ones."""
    Task = apps.get_model('crm_app', 'Task')
    Task.objects.filter(status='Pending').update(status='To Do')
    Task.objects.filter(status='Completed').update(status='Done')
    Task.objects.filter(status='Review').update(status='Done')


def reverse_task_statuses(apps, schema_editor):
    """Reverse status conversion."""
    Task = apps.get_model('crm_app', 'Task')
    Task.objects.filter(status='To Do').update(status='Pending')
    Task.objects.filter(status='Done').update(status='Completed')


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0057_opportunity_service_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add new fields to Task
        migrations.AddField(
            model_name='task',
            name='task_type',
            field=models.CharField(
                blank=True,
                choices=[('Call', 'Call'), ('Email', 'Email'), ('Follow-up', 'Follow-up'), ('Meeting', 'Meeting'), ('Other', 'Other')],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='related_opportunity',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tasks',
                to='crm_app.opportunity',
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='related_contract',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tasks',
                to='crm_app.contract',
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='related_contact',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tasks',
                to='crm_app.contact',
            ),
        ),
        # Remove unused fields
        migrations.RemoveField(model_name='task', name='estimated_hours'),
        migrations.RemoveField(model_name='task', name='actual_hours'),
        migrations.RemoveField(model_name='task', name='department'),
        migrations.RemoveField(model_name='task', name='tags'),
        # Fix status choices and default
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.CharField(
                choices=[('To Do', 'To Do'), ('In Progress', 'In Progress'), ('Done', 'Done'), ('Cancelled', 'Cancelled'), ('On Hold', 'On Hold')],
                default='To Do',
                max_length=20,
            ),
        ),
        # Make description optional (blank=True)
        migrations.AlterField(
            model_name='task',
            name='description',
            field=models.TextField(blank=True),
        ),
        # Convert existing status data
        migrations.RunPython(convert_task_statuses, reverse_task_statuses),
        # Create TaskComment model
        migrations.CreateModel(
            name='TaskComment',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('comment', models.TextField()),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='crm_app.task')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
