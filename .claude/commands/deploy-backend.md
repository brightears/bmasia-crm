# Deploy Backend to Render

Deploy the Django backend to Render and wait for completion.

## Pre-flight Checks
1. Check git status for uncommitted changes
2. If changes exist, ask user to commit first or proceed anyway

## Deployment Steps
1. Trigger deployment via Render API:
```bash
curl -X POST -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" -H "Content-Type: application/json" -d '{}' "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys"
```

2. Extract deployment ID from response

3. Poll deployment status every 15 seconds until "live" or "failed":
```bash
curl -s -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys/{deploy_id}"
```

4. Report final status to user

## Verification
After deployment is live:
- Hit the health check endpoint: https://bmasia-crm.onrender.com/api/v1/
- Report success or failure

## Service Details
- Service ID: srv-d13ukt8gjchc73fjat0g
- URL: https://bmasia-crm.onrender.com
