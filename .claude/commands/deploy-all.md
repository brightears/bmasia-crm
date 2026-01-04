# Deploy All Services

Deploy both backend and frontend to Render in parallel.

## Pre-flight Checks
1. Check git status for uncommitted changes
2. Verify all changes are committed and pushed to main branch
3. If uncommitted changes, ask user what to do

## Deployment Steps
1. Trigger BOTH deployments in parallel:

Backend:
```bash
curl -X POST -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" -H "Content-Type: application/json" -d '{}' "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys"
```

Frontend:
```bash
curl -X POST -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" -H "Content-Type: application/json" -d '{}' "https://api.render.com/v1/services/srv-d3clctt6ubrc73etb580/deploys"
```

2. Poll both deployment statuses until both are "live" or one fails

3. Report final status for both services

## Verification
After both deployments are live:
1. Test backend API: https://bmasia-crm.onrender.com/api/v1/
2. Test frontend loads: https://bmasia-crm-frontend.onrender.com
3. Test login works end-to-end

## Service IDs
- Backend: srv-d13ukt8gjchc73fjat0g
- Frontend: srv-d3clctt6ubrc73etb580
