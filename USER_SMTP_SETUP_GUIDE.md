# User SMTP Setup Guide - BMAsia CRM

## Overview

This guide shows you how to configure email credentials for your team members (Pom, Nikki, Keith, etc.) so they can send emails from their own Gmail accounts through the CRM system.

**What this enables:**
- Each person sends emails from their own Gmail address
- Clients' replies go directly to the correct person's inbox
- Each person sees sent emails in their own Gmail Sent folder
- Professional email delivery with proper sender authentication

## Prerequisites

Before you start, you need:
- ✅ Admin access to Django admin panel
- ✅ Admin credentials (username: `admin`, password: `bmasia123`)
- ✅ Team member's Gmail address (e.g., `pom@bmasiamusic.com`)
- ✅ Team member has 2-Step Verification enabled on their Google account

## Team Members to Configure

Use this checklist to track who's been set up:

- [ ] **Pom** (Finance) - pom@bmasiamusic.com
- [ ] **Nikki** (Sales) - nikki.h@bmasiamusic.com
- [ ] **Keith** (Support) - keith@bmasiamusic.com
- [ ] **Others** - Add as needed

## Step-by-Step Setup Process

### Part 1: Team Member Creates Gmail App Password

**The team member needs to do this themselves** (it requires their Google account login):

#### 1. Enable 2-Step Verification (if not already enabled)

1. Go to: https://myaccount.google.com/security
2. Click on "2-Step Verification"
3. Follow the prompts to enable it (requires phone number)
4. Complete the setup

#### 2. Create App Password

1. Go to: https://myaccount.google.com/apppasswords
2. Sign in with their Gmail account (e.g., pom@bmasiamusic.com)
3. You may be prompted to verify with 2-Step Verification
4. Under "Select app", choose: **Mail**
5. Under "Select device", choose: **Other (Custom name)**
6. Type: `BMAsia CRM`
7. Click **Generate**
8. Google will show a 16-character password in a yellow box:
   ```
   abcd efgh ijkl mnop
   ```
9. **IMPORTANT**: Copy this password immediately
10. Click **Done**

#### 3. Send Password to Admin

The team member should send you the 16-character password securely:
- Email (if acceptable)
- Slack/Teams message
- In person
- Password manager

**Note**: The password looks like: `abcdefghijklmnop` (remove spaces when entering)

---

### Part 2: You (Admin) Add Credentials to Django

#### 1. Access Django Admin

1. Open browser and go to: **https://bmasia-crm.onrender.com/admin/**
2. Login with:
   - Username: `admin`
   - Password: `bmasia123`
3. You'll see the Django administration panel

#### 2. Navigate to Users

1. In the left sidebar, find **"CRM_APP"** section
2. Click on **"Users"**
3. You'll see a list of all users

#### 3. Edit the User

1. Click on the user you want to configure (e.g., click on **"pom"**)
2. You'll see the user edit form
3. Scroll down until you see the section:
   ```
   Email SMTP Configuration
   Configure Gmail credentials for sending emails as this user.
   Get app password from: https://myaccount.google.com/apppasswords
   ```

#### 4. Enter SMTP Credentials

Fill in the two fields:

**SMTP Email:**
```
pom@bmasiamusic.com
```
(Their Gmail address)

**SMTP Password:**
```
abcdefghijklmnop
```
(The 16-character app password they gave you, **remove all spaces**)

#### 5. Save Changes

1. Scroll to the bottom of the page
2. Click the **"Save"** button (big blue button)
3. You'll see a success message: "The user "pom" was changed successfully."

---

### Part 3: Test the Setup

#### 1. Team Member Logs In

1. Go to: **https://bmasia-crm-frontend.onrender.com**
2. Login with their credentials:
   - Email: `pom@bmasiamusic.com`
   - Password: (their CRM password, not Gmail password)

#### 2. Send Test Email

1. Navigate to **Contracts** or **Quotes**
2. Find any contract/quote
3. Click the **⋮ (three dots)** menu button
4. Click **"Send Email"**
5. The email dialog opens
6. Select a test recipient (preferably yourself or an internal email)
7. Review the pre-filled subject and body
8. Click **"Send Email"** button
9. Wait for success message: "Email sent successfully"

#### 3. Verify Email Delivery

**Check Recipient Inbox:**
1. Open the recipient's email inbox
2. Look for the email
3. Verify "From" shows: `pom@bmasiamusic.com`
4. Verify PDF attachment is present
5. Click **"Reply"** button
6. Verify reply is addressed to `pom@bmasiamusic.com`

**Check Sender's Gmail Sent Folder:**
1. Have Pom check her Gmail account
2. Go to "Sent" folder
3. The email should appear there
4. This confirms it was sent through her Gmail account

✅ **If all checks pass, setup is complete for this user!**

---

## Quick Reference

### Important URLs

| Purpose | URL |
|---------|-----|
| Django Admin Panel | https://bmasia-crm.onrender.com/admin/ |
| CRM Frontend | https://bmasia-crm-frontend.onrender.com |
| Create Gmail App Password | https://myaccount.google.com/apppasswords |
| Google Security Settings | https://myaccount.google.com/security |

### Admin Credentials

- **Username**: `admin`
- **Password**: `bmasia123`

### Team Email Addresses

| Person | Role | Email Address |
|--------|------|---------------|
| Norbert | Admin | norbert@bmasiamusic.com |
| Pom | Finance | pom@bmasiamusic.com |
| Nikki | Sales | nikki.h@bmasiamusic.com |
| Keith | Support | keith@bmasiamusic.com |

---

## Troubleshooting

### Issue 1: "I can't find the app password option"

**Cause**: 2-Step Verification is not enabled

**Solution**:
1. Go to https://myaccount.google.com/security
2. Enable "2-Step Verification" first
3. Then app passwords option will appear

---

### Issue 2: "Authentication failed" when sending email

**Causes**:
- Incorrect app password (spaces not removed)
- Wrong email address
- App password was revoked

**Solution**:
1. Generate a **new** app password
2. Copy it carefully (remove all spaces)
3. Update in Django admin
4. Try sending again

---

### Issue 3: Email goes to spam

**Cause**: Gmail trust/reputation issue

**Solution**:
- Send a few test emails to known addresses first
- Emails sent through user's own Gmail should not go to spam
- If persistent, check Gmail "Less secure app access" settings
- Wait a few days for Gmail to build trust

---

### Issue 4: "No recipients found" error

**Cause**: Company has no contacts with email addresses

**Solution**:
1. Go to the company detail page
2. Add contacts with email addresses
3. Mark contacts as "Active"
4. Try sending email again

---

### Issue 5: User forgot their CRM password

**Solution**:
1. Login to Django admin: https://bmasia-crm.onrender.com/admin/
2. Go to Users
3. Click on their user
4. Scroll to "Password" section
5. Click "this form" link to reset password
6. Enter new password twice
7. Save

**Note**: This is the CRM login password, NOT their Gmail password!

---

## Adding New Team Members (Future)

When you hire someone new:

### 1. Create User Account

1. Go to Django admin → Users
2. Click "Add User" button
3. Enter:
   - Username: (e.g., `sarah`)
   - Password: (temporary password)
4. Click "Save"
5. Fill in additional details:
   - Email: `sarah@bmasiamusic.com`
   - First name, Last name
   - Role: (Sales/Finance/Tech/Music/Admin)
   - Mark as "Active"
6. Save again

### 2. Configure SMTP

Follow the same process in Part 2 above to add their SMTP credentials.

### 3. Send Welcome Email

Send them:
- CRM URL: https://bmasia-crm-frontend.onrender.com
- Their username
- Temporary password (ask them to change it after first login)
- Link to this guide

---

## Security Best Practices

### For Team Members:

1. **Never share Gmail app passwords** with anyone except the admin
2. **Keep Gmail password separate** from CRM password
3. **Enable 2-Step Verification** on Google account
4. **Revoke app passwords** if:
   - You leave the company
   - You suspect password was compromised
   - You're no longer using the CRM

### For You (Admin):

1. **Store app passwords securely** (password manager recommended)
2. **Revoke access** immediately when someone leaves:
   - Django admin → Users → Deactivate user
   - Ask them to revoke the Gmail app password
3. **Monitor email logs** in Django admin for suspicious activity
4. **Regular audits**: Check who has SMTP configured every 6 months

---

## FAQ

**Q: Can users change their own SMTP credentials?**
A: No, only admins can configure SMTP credentials in Django admin. Users cannot see or change them.

**Q: What if someone leaves the company?**
A:
1. Deactivate their user account in Django admin
2. Ask them to revoke the Gmail app password
3. Alternatively, change their email password to revoke all app passwords

**Q: Can one person have multiple email addresses?**
A: No, one user = one SMTP email. If they need to send from different addresses, create separate user accounts.

**Q: What happens if SMTP is not configured?**
A: The system falls back to the default: norbert@bmasiamusic.com

**Q: How do I know who sent an email?**
A: Check the Email Logs in Django admin. Each sent email is logged with the sender's user account.

**Q: Can I test this without sending real emails?**
A: Send test emails to yourself or internal addresses first. The system sends real emails, there's no "test mode."

---

## Support

If you encounter issues not covered in this guide:

1. Check Django admin logs for error messages
2. Check Render deployment logs: https://dashboard.render.com
3. Verify the team member's Google account has 2-Step Verification enabled
4. Try generating a fresh app password
5. Test with a different user to isolate the issue

---

**Last Updated**: October 12, 2025
**Version**: 1.0
**System**: BMAsia CRM - Per-User SMTP Email System
