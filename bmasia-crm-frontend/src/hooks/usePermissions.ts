import { useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
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
} from '../utils/permissions';

/**
 * Custom hook for permission-based logic
 */
export const usePermissions = () => {
  const { user } = useAuth();

  const permissions = useMemo(() => ({
    // Core permission checks
    hasPermission: (permission: string) => hasPermission(user, permission),
    hasRole: (roles: string | string[]) => hasRole(user, roles),
    hasMinimumRole: (role: string) => hasMinimumRole(user, role),
    canAccessModule: (module: string) => canAccessModule(user, module),
    canPerformAction: (
      entity: string,
      action: 'create' | 'read' | 'update' | 'delete',
      isOwner?: boolean
    ) => canPerformAction(user, entity, action, isOwner),

    // Convenience methods
    canViewSensitiveData: () => canViewSensitiveData(user),
    canPerformBulkOperations: () => canPerformBulkOperations(user),
    canExportData: () => canExportData(user),

    // Get user data
    getUserPermissions: () => getUserPermissions(user),
    getAccessibleMenuItems: () => getAccessibleMenuItems(user),

    // Role-specific checks
    isSales: () => hasRole(user, 'Sales'),
    isMarketing: () => hasRole(user, 'Marketing'),
    isTechSupport: () => hasRole(user, 'Tech Support'),
    isAdmin: () => hasRole(user, 'Admin'),

    // Module access checks
    canAccessDashboard: () => canAccessModule(user, 'dashboard'),
    canAccessCompanies: () => canAccessModule(user, 'companies'),
    canAccessOpportunities: () => canAccessModule(user, 'opportunities'),
    canAccessTasks: () => canAccessModule(user, 'tasks'),
    canAccessContracts: () => canAccessModule(user, 'contracts'),
    canAccessInvoices: () => canAccessModule(user, 'invoices'),
    canAccessAnalytics: () => canAccessModule(user, 'analytics'),
    canAccessUsers: () => canAccessModule(user, 'users'),
    canAccessSettings: () => canAccessModule(user, 'settings'),
    canAccessAudit: () => canAccessModule(user, 'audit'),

    // Entity-specific CRUD operations
    companies: {
      canView: () => hasPermission(user, 'view_companies'),
      canCreate: () => hasPermission(user, 'create_companies'),
      canEdit: () => hasPermission(user, 'edit_companies'),
      canDelete: () => hasPermission(user, 'delete_companies'),
    },
    contacts: {
      canView: () => hasPermission(user, 'view_contacts'),
      canCreate: () => hasPermission(user, 'create_contacts'),
      canEdit: () => hasPermission(user, 'edit_contacts'),
      canDelete: () => hasPermission(user, 'delete_contacts'),
    },
    opportunities: {
      canView: () => hasPermission(user, 'view_opportunities'),
      canCreate: () => hasPermission(user, 'create_opportunities'),
      canEdit: () => hasPermission(user, 'edit_opportunities'),
      canDelete: () => hasPermission(user, 'delete_opportunities'),
    },
    tasks: {
      canView: () => hasPermission(user, 'view_tasks'),
      canCreate: () => hasPermission(user, 'create_tasks'),
      canEditOwn: () => hasPermission(user, 'edit_own_tasks'),
      canEditAll: () => hasPermission(user, 'edit_all_tasks'),
      canDelete: () => hasPermission(user, 'delete_tasks'),
    },
    contracts: {
      canView: () => hasPermission(user, 'view_contracts'),
      canCreate: () => hasPermission(user, 'create_contracts'),
      canEdit: () => hasPermission(user, 'edit_contracts'),
      canDelete: () => hasPermission(user, 'delete_contracts'),
    },
    invoices: {
      canView: () => hasPermission(user, 'view_invoices'),
      canCreate: () => hasPermission(user, 'create_invoices'),
      canEdit: () => hasPermission(user, 'edit_invoices'),
      canDelete: () => hasPermission(user, 'delete_invoices'),
    },
    notes: {
      canViewAll: () => hasPermission(user, 'view_all_notes'),
      canViewOwn: () => hasPermission(user, 'view_own_notes'),
      canCreate: () => hasPermission(user, 'create_notes'),
      canEditOwn: () => hasPermission(user, 'edit_own_notes'),
      canEditAll: () => hasPermission(user, 'edit_all_notes'),
      canDelete: () => hasPermission(user, 'delete_notes'),
    },
  }), [user]);

  return permissions;
};

/**
 * Hook for role-based conditional rendering
 */
export const useRoleBasedContent = () => {
  const { user } = useAuth();

  const getContentByRole = useMemo(() => ({
    forSales: <T,>(content: T): T | null => hasRole(user, 'Sales') ? content : null,
    forMarketing: <T,>(content: T): T | null => hasRole(user, 'Marketing') ? content : null,
    forTechSupport: <T,>(content: T): T | null => hasRole(user, 'Tech Support') ? content : null,
    forAdmin: <T,>(content: T): T | null => hasRole(user, 'Admin') ? content : null,
    forMinimumRole: <T,>(content: T, minRole: string): T | null =>
      hasMinimumRole(user, minRole) ? content : null,
  }), [user]);

  return getContentByRole;
};

/**
 * Hook to check if user can perform specific business operations
 */
export const useBusinessPermissions = () => {
  const { user } = useAuth();

  return useMemo(() => ({
    // Sales operations
    canManageSalesPipeline: () => hasPermission(user, 'manage_sales_pipeline') || hasRole(user, ['Sales', 'Admin']),
    canAdvanceOpportunityStage: () => hasPermission(user, 'edit_opportunities'),
    canCreateQuotes: () => hasPermission(user, 'create_opportunities') && hasMinimumRole(user, 'Sales'),

    // Marketing operations
    canViewAnalytics: () => hasPermission(user, 'view_analytics'),
    canManageCampaigns: () => hasPermission(user, 'manage_campaigns') || hasRole(user, ['Marketing', 'Admin']),

    // Technical operations
    canManageTechnicalSettings: () => hasPermission(user, 'manage_technical_settings'),
    canViewSystemLogs: () => hasPermission(user, 'view_system_logs') || hasRole(user, ['Tech Support', 'Admin']),

    // Financial operations
    canViewFinancialReports: () => hasPermission(user, 'view_financial_reports') || hasMinimumRole(user, 'Marketing'),
    canManageBilling: () => hasPermission(user, 'manage_billing') || hasRole(user, ['Tech Support', 'Admin']),

    // Administrative operations
    canManageUsers: () => hasPermission(user, 'manage_users'),
    canManageSystemSettings: () => hasPermission(user, 'manage_system_settings'),
    canViewAuditLogs: () => hasPermission(user, 'view_audit_logs'),

    // Data operations
    canExportAllData: () => canExportData(user),
    canPerformBulkOperations: () => canPerformBulkOperations(user),
    canViewSensitiveInfo: () => canViewSensitiveData(user),
  }), [user]);
};