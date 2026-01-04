# Test API Endpoint

Test a specific API endpoint on the production server.

## Usage
```
/test-api [endpoint]
```

Examples:
- `/test-api companies` - Test companies list
- `/test-api email-templates` - Test email templates
- `/test-api contracts` - Test contracts list

## Steps
1. Get fresh authentication token:
```bash
curl -s -X POST -H "Content-Type: application/json" -d '{"username":"admin","password":"bmasia123"}' "https://bmasia-crm.onrender.com/api/v1/auth/login/"
```

2. Extract access token from response

3. Call the specified endpoint:
```bash
curl -s -H "Authorization: Bearer {token}" "https://bmasia-crm.onrender.com/api/v1/{endpoint}/"
```

4. Parse and display results:
   - Show count of items
   - Show first few items as sample
   - Report any errors

## Common Endpoints
| Endpoint | Description |
|----------|-------------|
| companies | List companies |
| contacts | List contacts |
| contracts | List contracts |
| quotes | List quotes |
| invoices | List invoices |
| email-templates | List email templates |
| email-sequences | List email sequences |
| sequence-enrollments | List enrollments |

## Base URL
https://bmasia-crm.onrender.com/api/v1/
