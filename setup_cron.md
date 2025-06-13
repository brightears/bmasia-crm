# Setting Up Automated Email Sending

Since Render's cron jobs need separate configuration, here's how to set up automated emails:

## Option 1: Use Render's Built-in Cron Jobs (Recommended)

1. Go to https://dashboard.render.com
2. Click "New +" → "Cron Job"
3. Configure as follows:
   - **Name**: bmasia-crm-daily-emails
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Command**: `python manage.py send_emails --type all`
   - **Schedule**: `0 2 * * *` (This is 9 AM Bangkok time in UTC)
   - **Git Repository**: Same as your main app

4. Add the SAME environment variables as your main app:
   - All the EMAIL_* variables
   - SECRET_KEY
   - DATABASE_URL (if using PostgreSQL)
   - SOUNDTRACK_* variables

## Option 2: Use External Service (Alternative)

Use a service like Zapier, IFTTT, or cron-job.org to hit this endpoint daily:
`https://bmasia-crm.onrender.com/api/trigger-emails/`

We would need to create this endpoint with authentication.

## Testing Schedule

- Renewal reminders: Check contracts expiring in 30, 14, 7, 2 days
- Payment reminders: Check overdue invoices (7, 14, 21+ days)
- Quarterly check-ins: Every 90 days from last contact

## Email Schedule (Bangkok Time)

- 9:00 AM: Daily email run
- Business days only (Mon-Fri)
- Skips Thai public holidays (to be configured)