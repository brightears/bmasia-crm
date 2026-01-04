# BMAsia CRM - Email Automation User Guide

**Last Updated**: January 4, 2026
**Status**: Fully Operational

---

## Quick Overview

The email automation system sends professional emails automatically based on triggers:
- **Contract renewals** (30, 14, 7, 2 days before expiry)
- **Payment reminders** (7, 14, 21+ days overdue)
- **Quarterly check-ins** (every 90 days)

All emails use professionally designed templates with BMAsia branding.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTOMATIC EMAIL WORKFLOW                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. TEMPLATES (Pre-configured)                                      │
│     └─→ 10 professional templates with BMAsia branding             │
│                                                                     │
│  2. SEQUENCES (3 Automatic + Manual)                                │
│     ├─→ Contract Renewal Reminders (30/14/7/2 days before expiry)  │
│     ├─→ Payment Reminders (7/14/21+ days overdue)                  │
│     └─→ Quarterly Check-ins (every 90 days)                        │
│                                                                     │
│  3. CRON JOB (Daily at 10 AM Singapore)                            │
│     └─→ Checks for due emails and sends automatically             │
│                                                                     │
│  4. EMAILS SENT                                                     │
│     └─→ Variables replaced with real data (company, contact, etc.) │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Accessing the Email System

### Frontend (Recommended)

**Email Automations Page**: https://bmasia-crm-frontend.onrender.com/email-automations
- View all sequences (automatic and manual)
- Create new sequences
- Manage enrollments
- View step configurations

**Email Templates Page**: https://bmasia-crm-frontend.onrender.com/email-templates
- View and edit all email templates
- Rich text editor with formatting
- Variable guide with all available placeholders

### Django Admin (Advanced)

**Admin Panel**: https://bmasia-crm.onrender.com/admin/
- Login: admin / bmasia123
- Navigate to: CRM_APP → Email templates
- Full HTML editing access

---

## Email Templates Available

| Template | Type | When It's Sent |
|----------|------|----------------|
| 30-Day Renewal Reminder | `renewal_30_days` | 30 days before contract expires |
| 14-Day Renewal Reminder | `renewal_14_days` | 14 days before contract expires |
| 7-Day Renewal Reminder | `renewal_7_days` | 7 days before contract expires |
| Urgent Renewal Notice | `renewal_urgent` | 2 days before contract expires |
| Payment Reminder (7 Days) | `payment_reminder_7_days` | 7 days after invoice due |
| Payment Reminder (14 Days) | `payment_reminder_14_days` | 14 days after invoice due |
| Payment Overdue Notice | `payment_overdue` | 21+ days after invoice due |
| Quarterly Check-in | `quarterly_checkin` | Every 90 days for active customers |
| Welcome Email | `welcome` | After new customer onboarding |
| Contract Signed | `contract_signed` | After contract signature |

---

## Template Variables

Variables are automatically replaced with real data when emails are sent:

### Common Variables (All Templates)
| Variable | Description |
|----------|-------------|
| `{{company_name}}` | Customer's company name |
| `{{contact_name}}` | Contact's full name |
| `{{current_year}}` | Current year (e.g., 2026) |
| `{{unsubscribe_url}}` | Link to unsubscribe |

### Contract/Renewal Variables
| Variable | Description |
|----------|-------------|
| `{{contract_number}}` | Contract reference number |
| `{{start_date}}` | Contract start date |
| `{{end_date}}` | Contract end date |
| `{{days_until_expiry}}` | Days until contract expires |
| `{{monthly_value}}` | Monthly contract value |
| `{{currency}}` | Currency code (THB, USD, etc.) |
| `{{number_of_zones}}` | Number of zones in contract |

### Invoice/Payment Variables
| Variable | Description |
|----------|-------------|
| `{{invoice_number}}` | Invoice reference number |
| `{{invoice_date}}` | Date invoice was issued |
| `{{due_date}}` | Payment due date |
| `{{days_overdue}}` | Days past due |
| `{{amount_due}}` | Outstanding amount |
| `{{payment_link}}` | Online payment link |

---

## Automatic Sequences

### 1. Contract Renewal Reminders
**Type**: `auto_renewal`
**Status**: Active
**Trigger**: Based on contract end dates

| Step | Timing | Template |
|------|--------|----------|
| 1 | 30 days before expiry | 30-Day Renewal Reminder |
| 2 | 14 days before expiry | 14-Day Renewal Reminder |
| 3 | 7 days before expiry | 7-Day Renewal Reminder |
| 4 | 2 days before expiry | Urgent Renewal Notice |

### 2. Payment Reminders
**Type**: `auto_payment`
**Status**: Active
**Trigger**: Based on invoice due dates

| Step | Timing | Template |
|------|--------|----------|
| 1 | 7 days overdue | Payment Reminder (7 Days) |
| 2 | 14 days overdue | Payment Reminder (14 Days) |
| 3 | 21+ days overdue | Payment Overdue Notice |

### 3. Quarterly Check-ins
**Type**: `auto_quarterly`
**Status**: Active
**Trigger**: Every 90 days for active customers

| Step | Timing | Template |
|------|--------|----------|
| 1 | Immediate | Quarterly Check-in |

---

## Creating Manual Campaigns

### Step 1: Create a New Sequence

1. Go to **Email Automations** page
2. Click **"+ New Sequence"**
3. Fill in:
   - **Name**: Campaign name (e.g., "Holiday Promotion 2026")
   - **Description**: What this campaign is for
   - **Type**: Select "Manual"
4. Click **Save**

### Step 2: Add Steps

1. Open your sequence
2. Click **"+ Add Step"**
3. Configure:
   - **Step Name**: (e.g., "Initial Outreach")
   - **Email Template**: Select from dropdown
   - **Delay Days**: Days after enrollment to send (0 = immediate)
4. Add more steps as needed

### Step 3: Enroll Contacts

1. Click **"Enroll Contact"**
2. Select companies/contacts to enroll
3. Emails will be sent based on step delays

---

## Editing Templates

### Via Frontend

1. Go to https://bmasia-crm-frontend.onrender.com/email-templates
2. Click on a template to edit
3. Use the rich text editor to modify content
4. Click "Save"

### Via Django Admin

1. Go to https://bmasia-crm.onrender.com/admin/
2. Login: admin / bmasia123
3. Navigate to: CRM_APP → Email templates
4. Click on a template to edit
5. Edit the HTML directly in the body_html field
6. Click "Save"

---

## Checking Email Status

### View Enrollments

1. Go to **Email Automations** page
2. Click on a sequence
3. View the **Enrollments** tab
4. See status: Active, Completed, Paused, or Cancelled

### View Email History

- Enrollment records show which emails have been sent
- Check the "Last Sent" and "Next Send" dates

---

## Troubleshooting

### Emails Not Sending?

1. **Check cron job is running**:
   - Go to Render Dashboard → Cron Jobs
   - Verify `bmasia-crm-email-automation` is active
   - Schedule: Daily at 10 AM Singapore time

2. **Check SMTP configuration**:
   - Email: norbert@bmasiamusic.com
   - Verify Gmail App Password is set

3. **Check sequence is active**:
   - Go to Email Automations
   - Ensure sequence status is "Active" (not Paused)

4. **Check template exists**:
   - Verify the template for each step has content
   - Templates need subject and body

### Test Email Sending

You can test email sending by:
1. Sending a quote via the Quotes page
2. Manually enrolling a contact in a sequence

---

## SMTP Configuration

**Current Setup**:
- **SMTP Host**: Gmail (smtp.gmail.com)
- **SMTP Email**: norbert@bmasiamusic.com
- **From Email**: BMAsia Music <norbert@bmasiamusic.com>

To configure per-user SMTP (optional):
1. Go to Django Admin → Users
2. Edit user profile
3. Set smtp_email and smtp_password fields

---

## Cron Job Details

**Service**: bmasia-crm-email-automation
**Schedule**: `0 10 * * *` (Daily at 10:00 AM Singapore time)
**Command**: `python manage.py send_emails --type all`

The cron job:
1. Checks for contracts expiring soon → sends renewal reminders
2. Checks for overdue invoices → sends payment reminders
3. Checks for quarterly check-in timing → sends check-in emails
4. Processes manual sequence enrollments → sends scheduled emails

---

## Support

For technical issues:
- Check the Render logs for error messages
- Review the CLAUDE.md file for development context
- Contact the development team

---

## Quick Reference

| Task | Where to Go |
|------|-------------|
| View sequences | https://bmasia-crm-frontend.onrender.com/email-automations |
| Edit templates | https://bmasia-crm-frontend.onrender.com/email-templates |
| Admin access | https://bmasia-crm.onrender.com/admin/ |
| Cron job logs | Render Dashboard → Cron Jobs → bmasia-crm-email-automation |
