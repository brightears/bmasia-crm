import { User } from '../types';

/**
 * Role-based access control utilities
 */

// Define role hierarchy (higher index = more permissions)
export const ROLE_HIERARCHY = ['Sales', 'Marketing', 'Tech Support', 'Admin'] as const;

// Define permissions for each role
export const ROLE_PERMISSIONS = {
  Sales: [
    'view_companies',
    'create_companies',
    'edit_companies',
    'view_contacts',
    'create_contacts',
    'edit_contacts',
    'view_opportunities',
    'create_opportunities',
    'edit_opportunities',
    'view_tasks',
    'create_tasks',
    'edit_own_tasks',
    'view_contracts',
    'view_invoices',
    'view_quotes',
    'create_quotes',
    'edit_quotes',
    'view_targets',
    'create_targets',
    'edit_targets',
    'view_own_notes',
    'create_notes',
    'edit_own_notes',
  ],
  Marketing: [
    'view_companies',
    'create_companies',
    'edit_companies',
    'view_contacts',
    'create_contacts',
    'edit_contacts',
    'view_opportunities',
    'create_opportunities',
    'edit_opportunities',
    'view_tasks',
    'create_tasks',
    'edit_own_tasks',
    'view_contracts',
    'view_invoices',
    'view_quotes',
    'create_quotes',
    'edit_quotes',
    'view_targets',
    'create_targets',
    'edit_targets',
    'view_all_notes',
    'create_notes',
    'edit_own_notes',
    'view_analytics',
    'export_data',
  ],
  'Tech Support': [
    'view_companies',
    'edit_companies',
    'view_contacts',
    'edit_contacts',
    'view_opportunities',
    'view_tasks',
    'create_tasks',
    'edit_all_tasks',
    'view_contracts',
    'edit_contracts',
    'view_invoices',
    'edit_invoices',
    'view_all_notes',
    'create_notes',
    'edit_all_notes',
    'manage_technical_settings',
  ],
  Admin: [
    // Admins have all permissions
    'view_companies',
    'create_companies',
    'edit_companies',
    'delete_companies',
    'view_contacts',
    'create_contacts',
    'edit_contacts',
    'delete_contacts',
    'view_opportunities',
    'create_opportunities',
    'edit_opportunities',
    'delete_opportunities',
    'view_tasks',
    'create_tasks',
    'edit_all_tasks',
    'delete_tasks',
    'view_contracts',
    'create_contracts',
    'edit_contracts',
    'delete_contracts',
    'view_invoices',
    'create_invoices',
    'edit_invoices',
    'delete_invoices',
    'view_quotes',
    'create_quotes',
    'edit_quotes',
    'delete_quotes',
    'view_targets',
    'create_targets',
    'edit_targets',
    'delete_targets',
    'view_all_notes',
    'create_notes',
    'edit_all_notes',
    'delete_notes',
    'view_analytics',
    'export_data',
    'manage_users',
    'manage_system_settings',
    'view_audit_logs',
    'manage_technical_settings',
  ],
} as const;

/**
 * Check if user has specific permission
 */
export const hasPermission = (user: User | null, permission: string): boolean => {
  if (!user || !user.is_active) return false;

  // Check explicit permissions array if available
  if (user.permissions && user.permissions.includes(permission)) {
    return true;
  }

  // Check role-based permissions
  const rolePermissions = ROLE_PERMISSIONS[user.role as keyof typeof ROLE_PERMISSIONS];
  return rolePermissions ? rolePermissions.includes(permission as any) : false;
};

/**
 * Check if user has any of the specified roles
 */
export const hasRole = (user: User | null, roles: string | string[]): boolean => {
  if (!user || !user.is_active) return false;

  const roleArray = Array.isArray(roles) ? roles : [roles];
  return roleArray.includes(user.role);
};

/**
 * Check if user has role with equal or higher level
 */
export const hasMinimumRole = (user: User | null, minimumRole: string): boolean => {
  if (!user || !user.is_active) return false;

  const userRoleIndex = ROLE_HIERARCHY.indexOf(user.role as any);
  const minimumRoleIndex = ROLE_HIERARCHY.indexOf(minimumRole as any);

  return userRoleIndex !== -1 && minimumRoleIndex !== -1 && userRoleIndex >= minimumRoleIndex;
};

/**
 * Get all permissions for a user's role
 */
export const getUserPermissions = (user: User | null): string[] => {
  if (!user || !user.is_active) return [];

  const rolePermissions = ROLE_PERMISSIONS[user.role as keyof typeof ROLE_PERMISSIONS] || [];
  const explicitPermissions = user.permissions || [];

  // Combine role permissions with explicit permissions
  const combinedPermissions: string[] = [...rolePermissions, ...explicitPermissions];
  return combinedPermissions.filter((permission, index) =>
    combinedPermissions.indexOf(permission) === index
  );
};

/**
 * Check if user can access a specific module/page
 */
export const canAccessModule = (user: User | null, module: string): boolean => {
  if (!user || !user.is_active) return false;

  const modulePermissions = {
    dashboard: 'view_companies', // Basic permission
    companies: 'view_companies',
    contacts: 'view_contacts',
    opportunities: 'view_opportunities',
    tasks: 'view_tasks',
    contracts: 'view_contracts',
    invoices: 'view_invoices',
    quotes: 'view_quotes',
    targets: 'view_targets',
    analytics: 'view_analytics',
    users: 'manage_users',
    settings: 'manage_system_settings',
    audit: 'view_audit_logs',
  };

  const requiredPermission = modulePermissions[module as keyof typeof modulePermissions];
  return requiredPermission ? hasPermission(user, requiredPermission) : false;
};

/**
 * Check if user can perform CRUD operations on an entity
 */
export const canPerformAction = (
  user: User | null,
  entity: string,
  action: 'create' | 'read' | 'update' | 'delete',
  isOwner?: boolean
): boolean => {
  if (!user || !user.is_active) return false;

  // Map entity and action to permission
  const permission = `${action === 'read' ? 'view' : action === 'update' ? 'edit' : action}_${entity}`;

  // For owned resources, check if user can edit their own items
  if (isOwner && action === 'update') {
    const ownPermission = `edit_own_${entity}`;
    return hasPermission(user, ownPermission) || hasPermission(user, permission);
  }

  return hasPermission(user, permission);
};

/**
 * Filter menu items based on user permissions
 */
export const getAccessibleMenuItems = (user: User | null) => {
  if (!user) return [];

  const allMenuItems = [
    { id: 'dashboard', label: 'Dashboard', path: '/dashboard' },
    { id: 'companies', label: 'Companies', path: '/companies' },
    { id: 'opportunities', label: 'Opportunities', path: '/opportunities' },
    { id: 'tasks', label: 'Tasks', path: '/tasks' },
    { id: 'contracts', label: 'Contracts', path: '/contracts' },
    { id: 'invoices', label: 'Invoices', path: '/invoices' },
    { id: 'analytics', label: 'Analytics', path: '/analytics' },
    { id: 'users', label: 'Users', path: '/users' },
    { id: 'settings', label: 'Settings', path: '/settings' },
    { id: 'audit', label: 'Audit Logs', path: '/audit' },
  ];

  return allMenuItems.filter(item => canAccessModule(user, item.id));
};

/**
 * Department-specific permissions
 */
export const getDepartmentPermissions = (department: string): string[] => {
  const departmentPerms = {
    Sales: ['view_sales_analytics', 'manage_sales_pipeline'],
    Marketing: ['view_marketing_analytics', 'manage_campaigns'],
    'Tech Support': ['manage_technical_issues', 'view_system_logs'],
    Finance: ['view_financial_reports', 'manage_billing'],
  };

  return departmentPerms[department as keyof typeof departmentPerms] || [];
};

/**
 * Check if user can view sensitive information
 */
export const canViewSensitiveData = (user: User | null): boolean => {
  return hasMinimumRole(user, 'Marketing');
};

/**
 * Check if user can perform bulk operations
 */
export const canPerformBulkOperations = (user: User | null): boolean => {
  return hasMinimumRole(user, 'Tech Support');
};

/**
 * Check if user can export data
 */
export const canExportData = (user: User | null): boolean => {
  return hasPermission(user, 'export_data');
};