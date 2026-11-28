/**
 * Which role may open which page: the one table the router guards, the side menu, the
 * global search and every permission helper read from. Keyed by the server's role values
 * (`User.role` choices in crm_app/models.py). The server still decides what data it returns;
 * this table only decides what the screens offer.
 *
 * To add a page: give its route a `requiredModule` in App.tsx and, if it is in the menu,
 * map its menu path in MENU_PATH_MODULE. A menu path that is not mapped shows for Admin only.
 */

export const SERVER_ROLES = ['Admin', 'Sales', 'Finance', 'Tech', 'Music'] as const;
export type ServerRole = (typeof SERVER_ROLES)[number];

/** Any signed-in user, including one whose account has no role yet. */
export const ANYONE = 'anyone' as const;

type Audience = typeof ANYONE | readonly ServerRole[];

const EVERY_ROLE: readonly ServerRole[] = SERVER_ROLES;
const ADMIN: readonly ServerRole[] = ['Admin'];
const FINANCE: readonly ServerRole[] = ['Admin', 'Finance'];
const SALES: readonly ServerRole[] = ['Admin', 'Sales'];
const COMMERCIAL: readonly ServerRole[] = ['Admin', 'Sales', 'Finance'];
const SUPPORT: readonly ServerRole[] = ['Admin', 'Sales', 'Tech', 'Music'];

/** Page modules, as used by `<ProtectedRoute requiredModule=…>` and the search sources. */
export const MODULE_ROLES = {
  today: ANYONE,
  profile: ANYONE,
  dashboard: EVERY_ROLE,
  companies: EVERY_ROLE,
  contacts: EVERY_ROLE,
  contracts: EVERY_ROLE,
  tasks: EVERY_ROLE,
  opportunities: COMMERCIAL, // also AI email drafts
  quotes: COMMERCIAL,
  targets: COMMERCIAL,
  invoices: COMMERCIAL,
  'finance-reports': FINANCE, // revenue, receivables, payables, P&L, cash flow, balance sheet, revenue recognition
  'prospect-sequences': SALES,
  campaigns: SALES, // also email templates and segments
  'email-automations': ADMIN,
  tickets: SUPPORT, // also help articles, music zones and site tech details
  'contract-templates': SALES,
  'seasonal-dates': ADMIN,
  users: ADMIN,
  // The Review page: every real role may open it; the server's reviewer list decides who can act
  // (everyone else sees it read-only, with no count).
  review: EVERY_ROLE,
};

export type PageModule = keyof typeof MODULE_ROLES;
// Every entry must be an audience (checked at compile time).
const _modulesAreAudiences: Record<PageModule, Audience> = MODULE_ROLES;
void _modulesAreAudiences;

/** Actions inside a page that only some of the page's roles may use. */
export const ACTION_ROLES = {
  /** Mark as paid, issue a receipt, export to QuickBooks. */
  'invoice-money': FINANCE,
};

export type PageAction = keyof typeof ACTION_ROLES;

/** The module behind each side-menu entry (and so behind each page offered in search). */
export const MENU_PATH_MODULE: Record<string, PageModule> = {
  '/today': 'today',
  '/review': 'review',
  '/dashboard': 'dashboard',
  '/companies': 'companies',
  '/contacts': 'contacts',
  '/opportunities': 'opportunities',
  '/quotes': 'quotes',
  '/contracts': 'contracts',
  '/renewals': 'contracts',
  '/tasks': 'tasks',
  '/ai-drafts': 'opportunities',
  '/research-leads': 'prospect-sequences',
  '/targets': 'targets',
  '/invoices': 'invoices',
  '/revenue': 'finance-reports',
  '/finance/ar': 'finance-reports',
  '/finance/ap': 'finance-reports',
  '/finance/pl': 'finance-reports',
  '/finance/cash-flow': 'finance-reports',
  '/finance/balance-sheet': 'finance-reports',
  '/finance/revenue-accrual': 'finance-reports',
  '/tickets': 'tickets',
  '/zones': 'tickets',
  '/tech-details': 'tickets',
  '/knowledge-base': 'tickets',
  '/campaigns': 'campaigns',
  '/prospect-sequences': 'prospect-sequences',
  '/email-automations': 'email-automations',
  '/email-templates': 'campaigns',
  '/segments': 'campaigns',
  '/users': 'users',
  '/contract-templates': 'contract-templates',
  '/settings': 'seasonal-dates',
};

interface RoleHolder {
  role?: string | null;
  is_active?: boolean;
}

export const isServerRole = (role: unknown): role is ServerRole =>
  typeof role === 'string' && (SERVER_ROLES as readonly string[]).includes(role);

/** True when the signed-in account has none of the server's roles (blank or unknown). */
export const hasNoRole = (user: RoleHolder | null | undefined): boolean => !!user && !isServerRole(user.role);

const admits = (audience: Audience, user: RoleHolder | null | undefined): boolean => {
  if (!user || user.is_active === false) return false;
  if (audience === ANYONE) return true;
  return isServerRole(user.role) && audience.includes(user.role);
};

export const canOpenModule = (user: RoleHolder | null | undefined, module: string): boolean =>
  Object.prototype.hasOwnProperty.call(MODULE_ROLES, module)
    ? admits(MODULE_ROLES[module as PageModule], user)
    : false;

export const canDo = (user: RoleHolder | null | undefined, action: PageAction): boolean =>
  admits(ACTION_ROLES[action], user);

/** Whether a side-menu entry shows; an unmapped path shows for Admin only. */
export const canSeeMenuPath = (user: RoleHolder | null | undefined, path: string): boolean => {
  const module = MENU_PATH_MODULE[path];
  return module ? canOpenModule(user, module) : admits(ADMIN, user);
};

/** The modules a role may open, for tests and for the role overview. */
export const modulesFor = (role: string | null | undefined): PageModule[] =>
  (Object.keys(MODULE_ROLES) as PageModule[]).filter((m) => canOpenModule({ role, is_active: true }, m));
