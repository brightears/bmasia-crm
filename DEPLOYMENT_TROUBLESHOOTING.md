# Render Deployment Troubleshooting Guide

## Overview
This guide documents common deployment issues encountered with the BMAsia CRM system on Render.com and their solutions.

**Last Updated**: October 12, 2025
**Status**: Production stable and operational ✅

---

## Table of Contents
1. [Environment Variable Issues](#environment-variable-issues)
2. [Database Connection Problems](#database-connection-problems)
3. [Email/SMTP Issues](#emailsmtp-issues)
4. [Deployment Process](#deployment-process)
5. [Quick Reference](#quick-reference)

---

## Environment Variable Issues

### Problem: Variables Disappearing After Updates
**Symptoms**:
- Login stops working with "no such table: auth_user"
- Database falls back to SQLite
- Email sending fails with authentication errors

**Root Cause**:
Render's PUT endpoint for environment variables **REPLACES** the entire configuration instead of merging changes.

**Solution**:
**ALWAYS set ALL critical variables together in a SINGLE request:**

```bash
curl -X PUT \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[
    {"key":"DATABASE_URL","value":"postgresql://bmasia_crm_user:IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v@dpg-d3cbikd6ubrc73el0ke0-a/bmasia_crm"},
    {"key":"EMAIL_HOST_USER","value":"norbert@bmasiamusic.com"},
    {"key":"EMAIL_HOST_PASSWORD","value":"fblgduekghmvixse"},
    {"key":"DEFAULT_FROM_EMAIL","value":"BMAsia Music <norbert@bmasiamusic.com>"}
  ]' \
  "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/env-vars"
```

**Prevention**:
1. Never set individual environment variables
2. Always include ALL 4 critical variables in every update
3. Keep a backup copy of all environment variables in a secure location

---

## Database Connection Problems

### Problem 1: "no such table: auth_user"
**Symptoms**:
- Login page shows database error
- Django error: `OperationalError: no such table: auth_user`
- Admin panel inaccessible

**Diagnosis**:
```bash
# Check if DATABASE_URL is set
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/env-vars" | \
  grep -i database
```

**Root Cause**:
- `DATABASE_URL` environment variable is missing
- Django falls back to SQLite (empty database)

**Solution**:
Set DATABASE_URL using the [Environment Variable Solution](#problem-variables-disappearing-after-updates) above.

---

### Problem 2: "SSL connection has been closed unexpectedly"
**Symptoms**:
```
OperationalError: connection to server at "dpg-d3cbikd6ubrc73el0ke0-a.singapore-postgres.render.com" (3.0.216.9), port 5432 failed: SSL connection has been closed unexpectedly
```

**Root Cause**:
Using external PostgreSQL connection string which requires SSL certificate verification that fails with Render's certificates.

**Solution**:
Use the **INTERNAL** connection string (services within Render's network):

✅ **CORRECT** (Internal - no SSL issues):
```
postgresql://bmasia_crm_user:IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v@dpg-d3cbikd6ubrc73el0ke0-a/bmasia_crm
```

❌ **WRONG** (External - causes SSL errors):
```
postgresql://bmasia_crm_user:IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v@dpg-d3cbikd6ubrc73el0ke0-a.singapore-postgres.render.com:5432/bmasia_crm
```

**Key Differences**:
- Internal: Just the database ID as hostname, no port
- External: Full hostname with region and port 5432

**Django Configuration** (`bmasia_crm/settings.py`):
```python
if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
    # Add SSL options - 'prefer' tries SSL but doesn't fail without it
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'prefer',
    }
```

---

### Problem 3: Getting the Correct Connection String
**How to retrieve internal connection string**:

```bash
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/postgres/dpg-d3cbikd6ubrc73el0ke0-a/connection-info" | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Internal: {d[\"internalConnectionString\"]}')"
```

**Expected Output**:
```
Internal: postgresql://bmasia_crm_user:IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v@dpg-d3cbikd6ubrc73el0ke0-a/bmasia_crm
```

---

## Email/SMTP Issues

### Problem: "(530, b'5.7.0 Authentication Required')"
**Symptoms**:
- Email sending fails
- Error message: "Failed to send quote to any recipients"
- Detailed error (thanks to improved error reporting): `(530, b'5.7.0 Authentication Required')`

**Root Cause**:
- `EMAIL_HOST_USER` and/or `EMAIL_HOST_PASSWORD` not set
- System cannot authenticate with Gmail SMTP

**Solution**:
Set all email variables using the [Environment Variable Solution](#problem-variables-disappearing-after-updates) above.

**Verification**:
```bash
# Test email sending
TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"bmasia123"}' \
  "https://bmasia-crm.onrender.com/api/v1/auth/login/" | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")

curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://bmasia-crm.onrender.com/api/v1/quotes/QUOTE_ID/send/"
```

**Expected Success Response**:
```json
{
  "message": "Quote sent successfully to 1 recipient(s)",
  "status": "Sent",
  "sent_date": "2025-10-12"
}
```

---

## Deployment Process

### How Deployments Work on Render

1. **Automatic Deployments**:
   - Triggered by git pushes to `main` branch
   - GitHub webhook notifies Render
   - Build starts automatically

2. **Manual Deployments**:
   - Triggered via Render dashboard
   - Triggered via Render API
   - Useful after environment variable changes

3. **Environment Variable Changes**:
   - Setting/changing variables does NOT auto-trigger deployment
   - **You MUST manually trigger a deployment after env var changes**

### Manual Deployment via API

```bash
# Trigger deployment
curl -X POST \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys"

# Response includes deployment ID
# {"id":"dep-xxxxx","status":"build_in_progress",...}
```

### Monitoring Deployment Status

```bash
# Replace dep-xxxxx with your deployment ID
DEPLOY_ID="dep-xxxxx"

# Check status
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys/$DEPLOY_ID" | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['status'])"

# Possible statuses:
# - build_in_progress
# - update_in_progress
# - live
# - build_failed
# - update_failed
```

### Deployment Timeline
Typical deployment takes 4-6 minutes:
- **Build phase** (2-3 minutes): Installing dependencies, building image
- **Update phase** (2-3 minutes): Deploying new version, running migrations
- **Live**: Service is now serving the new version

---

## Quick Reference

### Critical Environment Variables (ALL 4 Required)

| Variable | Value | Purpose |
|----------|-------|---------|
| `DATABASE_URL` | `postgresql://bmasia_crm_user:IUEmiG1IFKkzZOsR9HBpYoRGM7zhoI7v@dpg-d3cbikd6ubrc73el0ke0-a/bmasia_crm` | Internal PostgreSQL connection |
| `EMAIL_HOST_USER` | `norbert@bmasiamusic.com` | SMTP authentication username |
| `EMAIL_HOST_PASSWORD` | `fblgduekghmvixse` | Gmail App Password |
| `DEFAULT_FROM_EMAIL` | `BMAsia Music <norbert@bmasiamusic.com>` | Default sender for emails |

### Render Service IDs

| Service | ID | Purpose |
|---------|-------|---------|
| Backend | `srv-d13ukt8gjchc73fjat0g` | Django API |
| Frontend | `srv-d3clctt6ubrc73etb580` | React App |
| Database | `dpg-d3cbikd6ubrc73el0ke0-a` | PostgreSQL |

### Common Commands

**Check Environment Variables**:
```bash
curl -s -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" \
  "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/env-vars" | \
  python3 -c "import sys, json; [print(item['envVar']['key']) for item in json.load(sys.stdin)]"
```

**Check Service Status**:
```bash
curl -s -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" \
  "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g" | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"Status: {d['serviceDetails']['state']}\")"
```

**View Latest Deployment**:
```bash
curl -s -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" \
  "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys?limit=1" | \
  python3 -c "import sys, json; d=json.load(sys.stdin)[0]['deploy']; print(f\"Status: {d['status']}\\nCommit: {d['commit']['message'][:50]}\")"
```

**Test Login**:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"bmasia123"}' \
  "https://bmasia-crm.onrender.com/api/v1/auth/login/" | python3 -m json.tool
```

---

## Troubleshooting Flowchart

### Issue: Login Not Working

1. **Check DATABASE_URL is set**:
   ```bash
   curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
     "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/env-vars" | \
     grep -i database_url
   ```

2. **If missing**: Set all 4 env vars together (see above)

3. **If present**: Check if it's the internal connection string (no .singapore-postgres.render.com)

4. **Trigger deployment** after any env var changes

5. **Wait for LIVE status** before testing

### Issue: Email Sending Not Working

1. **Test login first** - If login fails, fix that first

2. **Check email env vars are set**:
   ```bash
   curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
     "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/env-vars" | \
     grep -i email
   ```

3. **If missing**: Set all 4 env vars together

4. **Check error message** - Should show detailed SMTP error thanks to improved error reporting

5. **Verify Gmail App Password** is correct (check .env file)

---

## Prevention Checklist

Before making any environment variable changes:

- [ ] Have backup of all current environment variables
- [ ] Know ALL 4 critical variables (DATABASE_URL, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL)
- [ ] Plan to set them ALL in one PUT request
- [ ] Have deployment trigger command ready
- [ ] Have monitoring/testing commands ready
- [ ] Allow 5-10 minutes for deployment + testing

---

## Emergency Recovery

If production is completely broken:

1. **Don't panic** - We have backups and known working configurations

2. **Set all 4 environment variables** using the values from [Quick Reference](#quick-reference)

3. **Trigger deployment**

4. **Monitor deployment** until LIVE

5. **Test login** - If this works, everything else should work

6. **Test email** - Send a test quote

7. **Check this document** for specific error messages if issues persist

---

## Support Resources

- **Session Checkpoints**: `SESSION_CHECKPOINT_2025-10-12*.md`
- **Email System Guide**: `USER_SMTP_SETUP_GUIDE.md`
- **Main Documentation**: `CLAUDE.md`
- **Render Dashboard**: https://dashboard.render.com
- **Render API Docs**: https://render.com/docs/api

---

**Remember**: When in doubt, set all 4 environment variables together and redeploy. This fixes 90% of issues.

---

*Last verified working: October 12, 2025*
*Deployment ID: dep-d3ls16ogjchc73clvu80*
*Git commit: 19b9629*
