# Deployment Rules for BMAsia CRM

## CRITICAL: THIS PROJECT RUNS ON RENDER.COM - NOT LOCALHOST

### Deployment Requirements
- **NEVER suggest local testing** (no `python manage.py runserver`, no `npm start`)
- **ALWAYS deploy to Render** using MCP access
- **ALWAYS test on production URLs** after deployment

### Production Infrastructure
| Service | URL/ID |
|---------|--------|
| Platform | Render.com |
| Backend URL | https://bmasia-crm.onrender.com |
| Frontend URL | https://bmasia-crm-frontend.onrender.com |
| Admin Panel | https://bmasia-crm.onrender.com/admin/ |
| Database | PostgreSQL (dpg-d3cbikd6ubrc73el0ke0-a) |

### Render Service IDs
- Backend (Django): `srv-d13ukt8gjchc73fjat0g`
- Frontend (React): `srv-d3clctt6ubrc73etb580`
- Email Automation Cron: `crn-d4b9g875r7bs7391al2g`
- Soundtrack Sync Cron: `crn-d5ea7j2li9vc73dccnb0`
- Task Digest Cron: `crn-d65drn75r7bs73cpu72g` (daily 02:00 UTC / 9 AM Bangkok)

### Standard Deployment Workflow
1. Make code changes
2. Commit to Git: `git add . && git commit -m "message"`
3. Push to GitHub: `git push origin main`
4. Deploy backend: `curl -X POST -H "Authorization: Bearer $RENDER_API_KEY" https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys`
5. Deploy frontend: `curl -X POST -H "Authorization: Bearer $RENDER_API_KEY" https://api.render.com/v1/services/srv-d3clctt6ubrc73etb580/deploys`
6. Wait for deployments to complete (check status via Render API)
7. Test on production URLs

### Render API Key
- Value: `rnd_QAJKR0jggzsxSLOCx3HfovreCzOd`
- Available via MCP access for deployment automation
