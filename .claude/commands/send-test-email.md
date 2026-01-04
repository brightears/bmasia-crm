# Send Test Email

Send a test email to verify the email system is working.

## Usage
```
/send-test-email [recipient_email]
```

Example:
- `/send-test-email platzer.norbert@gmail.com`

## Steps

### 1. Authenticate
Get API token for authenticated requests

### 2. Find a Quote to Send
```bash
curl -s -H "Authorization: Bearer {token}" \
  "https://bmasia-crm.onrender.com/api/v1/quotes/?page_size=1"
```

### 3. Send Test Email
```bash
curl -s -X POST -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "recipients": ["{recipient_email}"],
    "subject": "Test Email from BMAsia CRM",
    "body": "This is a test email to verify the email system is working correctly."
  }' \
  "https://bmasia-crm.onrender.com/api/v1/quotes/{quote_id}/send/"
```

### 4. Report Result
- Success: "Email sent successfully to {recipient}"
- Failure: Show error message

## Alternative: Send via Sequence Enrollment
If no quotes exist, can test by:
1. Creating a test enrollment in a sequence
2. Triggering immediate send

## SMTP Configuration
Emails are sent via:
- SMTP Host: smtp.gmail.com
- From: norbert@bmasiamusic.com (or department-specific)

## Verification
Ask user to check their inbox for the test email.
