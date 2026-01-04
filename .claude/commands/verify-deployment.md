# Verify Deployment

Comprehensive verification that both backend and frontend are working correctly.

## Verification Steps

### 1. Backend Health Check
```bash
curl -s "https://bmasia-crm.onrender.com/api/v1/" | head -100
```
Expected: API responds with available endpoints

### 2. Authentication Test
```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"bmasia123"}' \
  "https://bmasia-crm.onrender.com/api/v1/auth/login/"
```
Expected: Returns access token

### 3. Database Connectivity
Using the token, test a database query:
```bash
curl -s -H "Authorization: Bearer {token}" \
  "https://bmasia-crm.onrender.com/api/v1/companies/"
```
Expected: Returns company list (may be empty)

### 4. Frontend Loads
```bash
curl -s -o /dev/null -w "%{http_code}" "https://bmasia-crm-frontend.onrender.com"
```
Expected: HTTP 200

### 5. Static Assets
Check that React app loads properly by fetching main page

### 6. API Integration
Test that frontend can reach backend:
- CORS headers present
- API URL configured correctly

## Report Format
```
Deployment Verification Report
==============================
✓ Backend API responding
✓ Authentication working
✓ Database connected
✓ Frontend loading
✓ Static assets served
✓ CORS configured

All systems operational!
```

## Troubleshooting
If any check fails:
1. Check Render logs for errors
2. Verify environment variables
3. Check recent deployment status
