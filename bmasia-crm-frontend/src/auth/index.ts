/**
 * BMAsia CRM Authentication System
 * Central export file for all authentication-related utilities
 */

// Core Authentication
export { AuthProvider, useAuth } from '../contexts/AuthContext';
export { default as AuthService } from '../services/authService';

// Components
export { default as ProtectedRoute } from '../components/ProtectedRoute';
export { default as PermissionWrapper } from '../components/PermissionWrapper';
export { default as SessionTimeout } from '../components/SessionTimeout';

// Hooks
export { usePermissions, useRoleBasedContent, useBusinessPermissions } from '../hooks/usePermissions';

// Utilities
export {
  hasPermission,
  hasRole,
  hasMinimumRole,
  canAccessModule,
  canPerformAction,
  getUserPermissions,
  getAccessibleMenuItems,
  canViewSensitiveData,
  canPerformBulkOperations,
  canExportData,
  ROLE_HIERARCHY,
  ROLE_PERMISSIONS,
} from '../utils/permissions';

// Types
export type {
  AuthContextType,
  AuthState,
  AuthResponse,
  RefreshTokenResponse,
  JWTPayload,
  LoginCredentials,
  User,
} from '../types';