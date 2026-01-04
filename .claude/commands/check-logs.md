# Check Render Logs

View recent logs from Render services to debug issues.

## Usage
```
/check-logs [service]
```

Services:
- `backend` - Django backend logs
- `frontend` - React frontend logs
- `cron` - Email automation cron job logs

## Steps

### Backend Logs
```bash
curl -s -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" \
  "https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/logs?limit=50"
```

### Frontend Logs
```bash
curl -s -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" \
  "https://api.render.com/v1/services/srv-d3clctt6ubrc73etb580/logs?limit=50"
```

### Cron Job Logs
```bash
curl -s -H "Authorization: Bearer rnd_QAJKR0jggzsxSLOCx3HfovreCzOd" \
  "https://api.render.com/v1/services/crn-d4b9g875r7bs7391al2g/logs?limit=50"
```

## Service IDs
| Service | ID |
|---------|-----|
| Backend | srv-d13ukt8gjchc73fjat0g |
| Frontend | srv-d3clctt6ubrc73etb580 |
| Cron | crn-d4b9g875r7bs7391al2g |

## Common Issues to Look For
- Database connection errors
- Import/module errors
- SMTP/email failures
- Memory limits exceeded
- Build failures

## Dashboard Links
- Backend: https://dashboard.render.com/web/srv-d13ukt8gjchc73fjat0g
- Frontend: https://dashboard.render.com/static/srv-d3clctt6ubrc73etb580
- Cron: https://dashboard.render.com/cron/crn-d4b9g875r7bs7391al2g
