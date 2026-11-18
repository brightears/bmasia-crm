import { User } from '../types';
import {
  ACTION_ROLES,
  MENU_PATH_MODULE,
  MODULE_ROLES,
  PageAction,
  SERVER_ROLES,
  canDo,
  canOpenModule,
  isServerRole,
} from './access';

/**
 * Role helpers for the screens. Every answer here comes from the one role table in
 * `./access` (keyed by the server's role values), so the router, the menu, the search
 * and these helpers cannot disagree. The server decides what data it returns.
 */

/** Server roles, Admin last (kept for callers that list roles). */
export const ROLE_HIERARCHY = ['Sales', 'Finance', 'Tech', 'Music', 'Admin'] as const;

const VERBS = ['view', 'create', 'edit', 'edit_own', 'edit_all', 'delete'];

/**
 * `view_<module>` (and create/edit/delete) follow whether the role may open that module;
 * a named page action (e.g. `invoice-money`) follows ACTION_ROLES; anything else is Admin only.
 */
export const hasPermission = (user: User | null, permission: string): boolean => {
  if (!user || !user.is_active) return false;
  if (Object.prototype.hasOwnProperty.call(ACTION_ROLES, permission)) {
    return canDo(user, permission as PageAction);
  }
  for (const verb of VERBS) {
    const prefix = `${verb}_`;
    if (permission.startsWith(prefix)) {
      const module = permission.slice(prefix.length);
      if (Object.prototype.hasOwnProperty.call(MODULE_ROLES, module)) return canOpenModule(user, module);
    }
  }
  return user.role === 'Admin';
};

/** Every `view_<module>` and page action the user's role has, derived from the table. */
const permissionsForRole = (role: string): string[] => {
  const probe = { role, is_active: true };
  return [
    ...Object.keys(MODULE_ROLES).filter((m) => canOpenModule(probe, m)).map((m) => `view_${m}`),
    ...(Object.keys(ACTION_ROLES) as PageAction[]).filter((a) => canDo(probe, a)),
  ];
};

export const ROLE_PERMISSIONS: Record<string, string[]> = Object.fromEntries(
  SERVER_ROLES.map((role) => [role, permissionsForRole(role)])
);

export const hasRole = (user: User | null, roles: string | string[]): boolean => {
  if (!user || !user.is_active) return false;
  const roleArray = Array.isArray(roles) ? roles : [roles];
  return roleArray.includes(user.role);
};

/** Admin is above every other role; the other roles are side by side, not ranked. */
export const hasMinimumRole = (user: User | null, minimumRole: string): boolean => {
  if (!user || !user.is_active || !isServerRole(user.role)) return false;
  if (user.role === 'Admin') return true;
  return minimumRole !== 'Admin' && user.role === minimumRole;
};

export const getUserPermissions = (user: User | null): string[] =>
  user && user.is_active ? permissionsForRole(user.role) : [];

/** Whether the user may open a page module (the same check the router guard uses). */
export const canAccessModule = (user: User | null, module: string): boolean => canOpenModule(user, module);

export const canPerformAction = (
  user: User | null,
  entity: string,
  action: 'create' | 'read' | 'update' | 'delete',
  isOwner?: boolean
): boolean => {
  const verb = action === 'read' ? 'view' : action === 'update' ? 'edit' : action;
  if (isOwner && action === 'update') return hasPermission(user, `edit_own_${entity}`);
  return hasPermission(user, `${verb}_${entity}`);
};

/** Menu pages (path and module) the user may open. */
export const getAccessibleMenuItems = (user: User | null) =>
  Object.entries(MENU_PATH_MODULE)
    .filter(([, module]) => canOpenModule(user, module))
    .map(([path, module]) => ({ id: module, path }));

export const canViewSensitiveData = (user: User | null): boolean => canDo(user, 'invoice-money');

export const canPerformBulkOperations = (user: User | null): boolean => hasRole(user, 'Admin');

export const canExportData = (user: User | null): boolean => hasRole(user, ['Admin', 'Finance']);
