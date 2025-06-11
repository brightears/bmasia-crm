# Soundtrack API Setup

## ✅ WORKING AS OF v1.0-soundtrack-working (2025-06-11)

The Soundtrack API integration is fully functional with the following confirmed features:
- Account-specific zone queries using GraphQL
- Real-time zone status tracking (online/offline/no_device)
- Device pairing status
- Bulk synchronization for multiple companies
- Tested and working with Hilton Pattaya (4 zones)

## Environment Variables

To enable Soundtrack API integration, you need to set the following environment variables:

1. **For Local Development:**
   - Copy `.env.example` to `.env`
   - Add your Soundtrack API credentials:
     ```
     SOUNDTRACK_API_TOKEN=your-api-token
     SOUNDTRACK_CLIENT_ID=your-client-id
     SOUNDTRACK_CLIENT_SECRET=your-client-secret
     ```

2. **For Render Deployment:**
   - Go to your Render dashboard
   - Navigate to your service's Environment settings
   - Add the same three environment variables

## Security Notes

- **NEVER** commit API credentials to version control
- Keep your `.env` file in `.gitignore`
- Use different API credentials for development and production
- Rotate credentials regularly

## Using Zone Tracking

1. **For Soundtrack Zones:**
   - Enter the Soundtrack account ID (e.g., `QWNjb3VudCwsMXN4N242NTZyeTgv`)
   - The system will automatically sync zone status via API
   - Use the "Sync with Soundtrack API" action in admin to manually refresh

2. **For Beat Breeze Zones:**
   - Manually enter zone names and status
   - Update status as needed through admin interface

## Zone Statuses

- **Online**: Zone is active and streaming
- **Offline**: Zone is configured but not currently streaming
- **No Device Paired**: No device is associated with this zone
- **Subscription Expired**: The subscription for this zone has expired
- **Pending Activation**: Zone is created but not yet activated