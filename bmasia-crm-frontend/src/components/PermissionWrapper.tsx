import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { hasPermission, hasRole, canAccessModule } from '../utils/permissions';

interface PermissionWrapperProps {
  children: React.ReactNode;
  permission?: string;
  role?: string | string[];
  module?: string;
  fallback?: React.ReactNode;
  requireAll?: boolean; // If true, all conditions must be met
}

/**
 * Permission Wrapper Component
 * Conditionally renders children based on user permissions
 */
const PermissionWrapper: React.FC<PermissionWrapperProps> = ({
  children,
  permission,
  role,
  module,
  fallback = null,
  requireAll = false,
}) => {
  const { user } = useAuth();

  const checks = [];

  // Check module access
  if (module) {
    checks.push(canAccessModule(user, module));
  }

  // Check specific permission
  if (permission) {
    checks.push(hasPermission(user, permission));
  }

  // Check role requirement
  if (role) {
    checks.push(hasRole(user, role));
  }

  // If no checks specified, allow access
  if (checks.length === 0) {
    return <>{children}</>;
  }

  // Evaluate checks based on requireAll flag
  const hasAccess = requireAll ? checks.every(Boolean) : checks.some(Boolean);

  return hasAccess ? <>{children}</> : <>{fallback}</>;
};

export default PermissionWrapper;