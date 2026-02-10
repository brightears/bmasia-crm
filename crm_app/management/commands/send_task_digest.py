"""
Daily Task Digest Email

Sends each user a morning summary of:
- Tasks due today
- Overdue tasks
- New tasks assigned since yesterday

Run daily at 9 AM Bangkok time (02:00 UTC):
    python manage.py send_task_digest
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from crm_app.models import Task

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Send daily task digest email to users with due/overdue tasks'

    def handle(self, *args, **options):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        yesterday = now - timedelta(days=1)

        users = User.objects.filter(is_active=True, email__isnull=False).exclude(email='')
        emails_sent = 0

        for user in users:
            due_today = Task.objects.filter(
                assigned_to=user,
                due_date__gte=today_start,
                due_date__lt=today_end,
                status__in=['To Do', 'In Progress'],
            ).select_related('company')

            overdue = Task.objects.filter(
                assigned_to=user,
                due_date__lt=today_start,
                status__in=['To Do', 'In Progress'],
            ).select_related('company')

            new_assigned = Task.objects.filter(
                assigned_to=user,
                created_at__gte=yesterday,
                status__in=['To Do', 'In Progress'],
            ).exclude(created_by=user).select_related('company')

            if not due_today.exists() and not overdue.exists() and not new_assigned.exists():
                continue

            html = self._build_email(user, due_today, overdue, new_assigned)
            subject = f'[BMAsia CRM] Your daily task summary - {now.strftime("%B %d, %Y")}'

            try:
                send_mail(
                    subject=subject,
                    message=f'You have {due_today.count()} tasks due today and {overdue.count()} overdue tasks.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html,
                    fail_silently=True,
                )
                emails_sent += 1
                logger.info(f"Task digest sent to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send digest to {user.email}: {e}")

        self.stdout.write(self.style.SUCCESS(f'Task digest sent to {emails_sent} users'))

    def _build_email(self, user, due_today, overdue, new_assigned):
        name = user.first_name or user.username

        sections = []

        if overdue.exists():
            rows = ''.join(
                f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{t.title}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{t.company.name}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:#d32f2f;">{t.due_date.strftime("%b %d") if t.due_date else "-"}</td></tr>'
                for t in overdue
            )
            sections.append(f"""
                <h3 style="color:#d32f2f;margin:20px 0 10px;">Overdue ({overdue.count()})</h3>
                <table style="width:100%;border-collapse:collapse;">
                    <tr style="background:#ffebee;"><th style="text-align:left;padding:8px 10px;">Task</th><th style="text-align:left;padding:8px 10px;">Company</th><th style="text-align:left;padding:8px 10px;">Due</th></tr>
                    {rows}
                </table>
            """)

        if due_today.exists():
            rows = ''.join(
                f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{t.title}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{t.company.name}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{t.priority}</td></tr>'
                for t in due_today
            )
            sections.append(f"""
                <h3 style="color:#FFA500;margin:20px 0 10px;">Due Today ({due_today.count()})</h3>
                <table style="width:100%;border-collapse:collapse;">
                    <tr style="background:#fff3e0;"><th style="text-align:left;padding:8px 10px;">Task</th><th style="text-align:left;padding:8px 10px;">Company</th><th style="text-align:left;padding:8px 10px;">Priority</th></tr>
                    {rows}
                </table>
            """)

        if new_assigned.exists():
            rows = ''.join(
                f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{t.title}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{t.company.name}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{t.priority}</td></tr>'
                for t in new_assigned
            )
            sections.append(f"""
                <h3 style="color:#2196f3;margin:20px 0 10px;">New Tasks Assigned ({new_assigned.count()})</h3>
                <table style="width:100%;border-collapse:collapse;">
                    <tr style="background:#e3f2fd;"><th style="text-align:left;padding:8px 10px;">Task</th><th style="text-align:left;padding:8px 10px;">Company</th><th style="text-align:left;padding:8px 10px;">Priority</th></tr>
                    {rows}
                </table>
            """)

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;">
            <div style="background:#FFA500;padding:15px;color:white;">
                <h2 style="margin:0;">Daily Task Summary</h2>
            </div>
            <div style="padding:20px;border:1px solid #e0e0e0;">
                <p>Hi {name},</p>
                <p>Here's your task summary for today:</p>
                {''.join(sections)}
                <p style="margin-top:20px;"><a href="https://bmasia-crm-frontend.onrender.com/tasks" style="background:#FFA500;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;display:inline-block;">View All Tasks</a></p>
            </div>
            <div style="padding:10px;color:#999;font-size:12px;">
                BMAsia CRM - Daily Task Digest
            </div>
        </div>
        """
