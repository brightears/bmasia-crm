# BMAsia CRM Authentication System

This document describes the enhanced JWT-based authentication system implemented for the BMAsia CRM frontend.

## Overview

The authentication system provides:
- JWT token-based authentication with automatic refresh
- Role-based access control (RBAC)
- Permission-based UI controls
- Session management with timeout warnings
- "Remember Me" functionality
- Secure token storage and management

## Architecture

### Core Components

1. **AuthService** (`/services/authService.ts`)
   - JWT token management
   - API authentication calls
   - Token refresh logic
   - Secure storage handling

2. **AuthContext** (`/contexts/AuthContext.tsx`)
   - Global authentication state
   - React hooks for auth operations
   - Permission checking utilities

3. **ProtectedRoute** (`/components/ProtectedRoute.tsx`)
   - Route-level authentication/authorization
   - Automatic redirects for unauthorized access

4. **PermissionWrapper** (`/components/PermissionWrapper.tsx`)
   - Component-level permission controls
   - Conditional rendering based on permissions

5. **SessionTimeout** (`/components/SessionTimeout.tsx`)
   - Idle session detection
   - Automatic logout warnings
   - Session extension capabilities

## User Roles and Permissions

### Role Hierarchy
1. **Sales** - Basic CRM operations
2. **Marketing** - Enhanced analytics and reporting
3. **Tech Support** - Technical operations and system management
4. **Admin** - Full system access

### Permission Matrix

| Permission | Sales | Marketing | Tech Support | Admin |
|------------|-------|-----------|--------------|-------|
| view_companies | ✅ | ✅ | ✅ | ✅ |
| create_companies | ✅ | ✅ | ❌ | ✅ |
| edit_companies | ✅ | ✅ | ✅ | ✅ |
| delete_companies | ❌ | ❌ | ❌ | ✅ |
| view_opportunities | ✅ | ✅ | ✅ | ✅ |
| create_opportunities | ✅ | ✅ | ❌ | ✅ |
| edit_opportunities | ✅ | ✅ | ❌ | ✅ |
| view_analytics | ❌ | ✅ | ❌ | ✅ |
| export_data | ❌ | ✅ | ❌ | ✅ |
| manage_users | ❌ | ❌ | ❌ | ✅ |
| view_audit_logs | ❌ | ❌ | ❌ | ✅ |

## Usage Examples

### 1. Protected Routes

```tsx
import ProtectedRoute from '../components/ProtectedRoute';

// Protect entire route
<Route
  path="/admin"
  element={
    <ProtectedRoute requiredRole="Admin">
      <AdminPanel />
    </ProtectedRoute>
  }
/>

// Protect with specific permission
<Route
  path="/analytics"
  element={
    <ProtectedRoute requiredPermission="view_analytics">
      <Analytics />
    </ProtectedRoute>
  }
/>

// Protect with module access
<Route
  path="/companies"
  element={
    <ProtectedRoute requiredModule="companies">
      <Companies />
    </ProtectedRoute>
  }
/>
```

### 2. Permission-Based UI Controls

```tsx
import PermissionWrapper from '../components/PermissionWrapper';

// Show button only if user has permission
<PermissionWrapper permission="create_companies">
  <Button onClick={handleCreateCompany}>
    Add Company
  </Button>
</PermissionWrapper>

// Role-based content
<PermissionWrapper role={['Admin', 'Marketing']}>
  <AdvancedFeatures />
</PermissionWrapper>

// Multiple conditions (all must be true)
<PermissionWrapper
  permission="export_data"
  role="Marketing"
  requireAll={true}
>
  <ExportButton />
</PermissionWrapper>
```

### 3. Using Permission Hooks

```tsx
import { usePermissions } from '../hooks/usePermissions';

function CompanyList() {
  const permissions = usePermissions();

  return (
    <div>
      {permissions.companies.canCreate() && (
        <Button onClick={handleCreate}>Add Company</Button>
      )}

      {permissions.isAdmin() && (
        <AdminOnlyFeature />
      )}

      {permissions.canExportData() && (
        <ExportButton />
      )}
    </div>
  );
}
```

### 4. Authentication Context

```tsx
import { useAuth } from '../contexts/AuthContext';

function UserProfile() {
  const { user, logout, hasPermission, hasRole } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  if (hasRole('Admin')) {
    return <AdminDashboard />;
  }

  return (
    <div>
      <h1>Welcome, {user?.first_name}</h1>
      <p>Role: {user?.role}</p>

      {hasPermission('view_analytics') && (
        <AnalyticsWidget />
      )}

      <Button onClick={handleLogout}>Logout</Button>
    </div>
  );
}
```

## API Integration

### Backend Endpoints Required

The frontend expects these authentication endpoints:

```
POST /api/v1/auth/login/
Body: { username, password, remember_me? }
Response: { access, refresh, user }

POST /api/v1/auth/refresh/
Body: { refresh }
Response: { access }

POST /api/v1/auth/logout/
Body: { refresh }
Response: 204 No Content

GET /api/v1/auth/me/
Response: User object
```

### JWT Token Structure

Access tokens should include:
```json
{
  "token_type": "access",
  "exp": 1640995200,
  "iat": 1640908800,
  "jti": "uuid",
  "user_id": "user_uuid",
  "username": "username",
  "role": "Sales"
}
```

## Security Features

### Token Management
- Access tokens stored in memory or sessionStorage
- Refresh tokens in httpOnly cookies (recommended) or localStorage
- Automatic token refresh before expiration
- Secure token clearing on logout

### Session Security
- Configurable session timeout (default: 30 minutes)
- Activity-based session extension
- Warning dialogs before auto-logout
- Multi-tab session synchronization

### Permission Enforcement
- Frontend permissions for UI/UX only
- All security enforcement must happen on backend
- Permissions cached with user data
- Regular permission validation

## Configuration

### Environment Variables

```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_SESSION_TIMEOUT=30
REACT_APP_SESSION_WARNING=5
```

### Customizing Permissions

Update `/utils/permissions.ts` to modify role permissions:

```typescript
export const ROLE_PERMISSIONS = {
  Sales: [
    'view_companies',
    'create_companies',
    // ... more permissions
  ],
  // ... other roles
};
```

## Testing

### Unit Tests

Test authentication flows:
```typescript
// Test login
it('should login user successfully', async () => {
  const { result } = renderHook(() => useAuth());
  await act(async () => {
    await result.current.login({ username: 'test', password: 'pass' });
  });
  expect(result.current.isAuthenticated).toBe(true);
});

// Test permissions
it('should check permissions correctly', () => {
  const user = { role: 'Sales', permissions: [] };
  expect(hasPermission(user, 'view_companies')).toBe(true);
  expect(hasPermission(user, 'delete_companies')).toBe(false);
});
```

### Integration Tests

Test protected routes and permission flows:
```typescript
it('should redirect to login when not authenticated', () => {
  render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>
  );
  expect(screen.getByText('BMAsia CRM Login')).toBeInTheDocument();
});
```

## Troubleshooting

### Common Issues

1. **Token Refresh Loops**
   - Check backend token expiration times
   - Verify refresh token endpoint responses

2. **Permission Denied Errors**
   - Verify user role assignments
   - Check permission definitions
   - Ensure backend permissions match frontend

3. **Session Timeout Issues**
   - Adjust timeout configuration
   - Check activity detection events
   - Verify localStorage/sessionStorage access

### Debug Mode

Enable debug logging:
```typescript
// In development
if (process.env.NODE_ENV === 'development') {
  console.log('Auth state:', authState);
  console.log('User permissions:', getUserPermissions(user));
}
```

## Migration Guide

### From Basic Auth to JWT

1. Update API calls to use new endpoints
2. Replace token storage with new service
3. Update permission checks throughout app
4. Add protected routes to sensitive pages
5. Test all authentication flows

### Deployment Checklist

- [ ] Update environment variables
- [ ] Configure secure token storage
- [ ] Test permission matrix
- [ ] Verify session timeout behavior
- [ ] Test logout functionality
- [ ] Validate protected routes
- [ ] Check mobile responsiveness

## Support

For issues or questions:
1. Check this documentation
2. Review permission utility functions
3. Test with different user roles
4. Validate backend API responses