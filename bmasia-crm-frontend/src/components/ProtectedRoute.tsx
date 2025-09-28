import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Box, Typography, Paper } from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import { hasPermission, hasRole, canAccessModule } from '../utils/permissions';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermission?: string;
  requiredRole?: string | string[];
  requiredModule?: string;
  fallback?: React.ReactNode;
}

/**
 * Protected Route Component
 * Handles authentication and authorization for routes
 */
const ProtectedRoute = ({
  children,
  requiredPermission,
  requiredRole,
  requiredModule,
  fallback,
}: ProtectedRouteProps): React.ReactElement => {
  const { isAuthenticated, user, loading } = useAuth();
  const location = useLocation();

  // Show loading while checking authentication
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <Typography>Loading...</Typography>
      </Box>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check module access
  if (requiredModule && !canAccessModule(user, requiredModule)) {
    return (fallback || <UnauthorizedAccess />) as React.ReactElement;
  }

  // Check specific permission
  if (requiredPermission && !hasPermission(user, requiredPermission)) {
    return (fallback || <UnauthorizedAccess />) as React.ReactElement;
  }

  // Check role requirement
  if (requiredRole && !hasRole(user, requiredRole)) {
    return (fallback || <UnauthorizedAccess />) as React.ReactElement;
  }

  return <>{children}</> as React.ReactElement;
};

/**
 * Unauthorized Access Component
 */
const UnauthorizedAccess = () => (
  <Box
    display="flex"
    justifyContent="center"
    alignItems="center"
    minHeight="400px"
    p={3}
  >
    <Paper elevation={3} sx={{ p: 4, textAlign: 'center', maxWidth: 500 }}>
      <Typography variant="h5" color="error" gutterBottom>
        Access Denied
      </Typography>
      <Typography variant="body1" color="text.secondary">
        You don't have permission to access this resource.
        Please contact your administrator if you believe this is an error.
      </Typography>
    </Paper>
  </Box>
);

export default ProtectedRoute;