"""Offline Alert Service for Soundtrack zones"""
import logging
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


class OfflineAlertService:
    """Smart offline detection with notification cooldown

    Alert Logic:
    - First alert: After 4 hours offline
    - Subsequent alerts: Every 24 hours (to avoid spam)
    - Recipients: Contacts with receives_soundtrack_alerts=True
    """

    INITIAL_THRESHOLD_HOURS = 4   # First alert after 4 hours
    COOLDOWN_HOURS = 24           # Subsequent alerts every 24 hours

    def check_and_alert(self):
        """Run after each sync to detect offline zones and send alerts

        Returns:
            tuple: (alerts_created, notifications_sent)
        """
        alerts_created = self._update_offline_alerts()
        resolved_count = self._resolve_online_alerts()
        notifications_sent = self._send_pending_notifications()

        logger.info(
            f"Offline alert check: {alerts_created} new alerts, "
            f"{resolved_count} resolved, {notifications_sent} notifications sent"
        )

        return alerts_created, notifications_sent

    def _update_offline_alerts(self):
        """Create alerts for newly offline zones"""
        from crm_app.models import Zone, ZoneOfflineAlert

        alerts_created = 0

        # Find offline zones with alerts enabled at company level
        offline_zones = Zone.objects.filter(
            status='offline',
            company__soundtrack_offline_alerts_enabled=True
        ).select_related('company')

        for zone in offline_zones:
            # Check if there's already an active (unresolved) alert
            existing_alert = ZoneOfflineAlert.objects.filter(
                zone=zone,
                is_resolved=False
            ).first()

            if not existing_alert:
                # Create new alert
                ZoneOfflineAlert.objects.create(
                    zone=zone,
                    detected_at=zone.last_seen_online or timezone.now()
                )
                alerts_created += 1
                logger.info(f"Created offline alert for zone: {zone.name}")

        return alerts_created

    def _resolve_online_alerts(self):
        """Mark alerts as resolved for zones that came back online"""
        from crm_app.models import ZoneOfflineAlert

        resolved_count = ZoneOfflineAlert.objects.filter(
            zone__status='online',
            is_resolved=False
        ).update(
            is_resolved=True,
            resolved_at=timezone.now()
        )

        if resolved_count > 0:
            logger.info(f"Resolved {resolved_count} offline alerts (zones came back online)")

        return resolved_count

    def _send_pending_notifications(self):
        """Send notifications for alerts that meet threshold"""
        from crm_app.models import ZoneOfflineAlert

        notifications_sent = 0

        # Get unresolved alerts with alerts enabled
        pending_alerts = ZoneOfflineAlert.objects.filter(
            is_resolved=False,
            zone__company__soundtrack_offline_alerts_enabled=True
        ).select_related('zone', 'zone__company')

        for alert in pending_alerts:
            if alert.should_send_notification():
                sent = self._send_alert_email(alert)
                if sent:
                    notifications_sent += 1

        return notifications_sent

    def _send_alert_email(self, alert):
        """Send email to opted-in contacts

        Args:
            alert: ZoneOfflineAlert instance

        Returns:
            bool: True if email sent successfully
        """
        from crm_app.models import EmailTemplate, Contact

        # Get opted-in contacts
        contacts = Contact.objects.filter(
            company=alert.zone.company,
            is_active=True,
            receives_notifications=True,
            receives_soundtrack_alerts=True
        )

        if not contacts.exists():
            logger.info(f"No opted-in contacts for zone: {alert.zone.name}")
            return False

        # Get the email template
        try:
            template = EmailTemplate.objects.get(template_type='zone_offline_alert')
        except EmailTemplate.DoesNotExist:
            logger.warning("zone_offline_alert email template not found")
            return False

        # Prepare context for email
        context = {
            'zone_name': alert.zone.name,
            'company_name': alert.zone.company.name,
            'hours_offline': round(alert.hours_offline, 1),
            'last_seen_online': alert.detected_at.strftime('%Y-%m-%d %H:%M %Z'),
            'device_name': alert.zone.device_name or 'Unknown',
            'notification_type': 'the first' if not alert.first_notification_sent else 'a follow-up',
            'subsequent': alert.first_notification_sent,
        }

        # Send to each opted-in contact
        from crm_app.services.email_service import email_service

        sent_count = 0
        for contact in contacts:
            try:
                context['contact_name'] = contact.name

                # Render subject and body with variables
                subject = self._render_template(template.subject, context)
                body = self._render_template(template.body_text, context)
                html_body = self._render_template(template.body_html, context) if template.body_html else None

                # Send email
                success = email_service.send_email(
                    to_email=contact.email,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                    from_email=None  # Use default sender
                )

                if success:
                    sent_count += 1
                    logger.info(f"Sent offline alert to {contact.email} for zone {alert.zone.name}")
            except Exception as e:
                logger.error(f"Error sending alert to {contact.email}: {str(e)}")

        if sent_count > 0:
            # Update alert tracking
            now = timezone.now()
            if not alert.first_notification_sent:
                alert.first_notification_sent = True
                alert.first_notification_at = now
            alert.last_notification_at = now
            alert.notification_count += 1
            alert.save()

            # Track which contacts were notified
            alert.notified_contacts.add(*contacts)

            return True

        return False

    def _render_template(self, template_text, context):
        """Simple template variable replacement

        Args:
            template_text: Text with {{variable}} placeholders
            context: Dict of variable values

        Returns:
            str: Rendered text
        """
        result = template_text
        for key, value in context.items():
            result = result.replace(f'{{{{{key}}}}}', str(value))
        return result


# Singleton instance
offline_alert_service = OfflineAlertService()
