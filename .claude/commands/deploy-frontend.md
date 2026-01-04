# Deploy Frontend to Render

Deploy the React frontend to Render and wait for completion.

## Pre-flight Checks
1. Check git status for uncommitted changes in bmasia-crm-frontend/
2. If changes exist, ask user to commit first or proceed anyway

## Deployment Steps
1. Trigger deployment via Render API:
```bash
curl -X POST -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" -H "Content-Type: application/json" -d '{}' "https://api.render.com/v1/services/srv-d3clctt6ubrc73etb580/deploys"
```

2. Extract deployment ID from response

3. Poll deployment status every 15 seconds until "live" or "failed":
```bash
curl -s -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" "https://api.render.com/v1/services/srv-d3clctt6ubrc73etb580/deploys/{deploy_id}"
```

4. Report final status to user

## Verification
After deployment is live:
- Check frontend loads: https://bmasia-crm-frontend.onrender.com
- Report success or failure

## Service Details
- Service ID: srv-d3clctt6ubrc73etb580
- URL: https://bmasia-crm-frontend.onrender.com
