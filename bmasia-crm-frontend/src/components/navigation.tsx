import React from 'react';
import {
  TodayOutlined,
  SpaceDashboardOutlined,
  BusinessOutlined,
  PeopleAltOutlined,
  TrendingUp,
  RequestQuoteOutlined,
  HistoryEduOutlined,
  TaskAltOutlined,
  MarkEmailReadOutlined,
  TrackChangesOutlined,
  ReceiptLongOutlined,
  ShowChartOutlined,
  CallReceivedOutlined,
  CallMadeOutlined,
  AssessmentOutlined,
  WaterfallChartOutlined,
  AccountBalanceOutlined,
  EventRepeatOutlined,
  SupportAgentOutlined,
  SpeakerGroupOutlined,
  RouterOutlined,
  MenuBookOutlined,
  CampaignOutlined,
  AutoFixHighOutlined,
  AutoModeOutlined,
  DraftsOutlined,
  GroupsOutlined,
  ManageAccountsOutlined,
  ArticleOutlined,
  CalendarMonthOutlined,
} from '@mui/icons-material';

export interface NavItem {
  text: string;
  path: string;
  icon: React.ReactNode;
  badge?: number;
  /** Older name, kept for the breadcrumb tooltip and search later. */
  formerly?: string;
}

export interface NavGroup {
  id: string;
  title?: string;
  items: NavItem[];
}

/**
 * Menu structure in plain business words. Only labels and grouping change; every item
 * still opens the same page as before.
 */
export const buildNavGroups = (aiDraftsPendingCount: number): NavGroup[] => [
  {
    id: 'home',
    items: [
      { text: 'Today', icon: <TodayOutlined />, path: '/today' },
      { text: 'Dashboard', icon: <SpaceDashboardOutlined />, path: '/dashboard' },
    ],
  },
  {
    id: 'customers',
    title: 'Customers',
    items: [
      { text: 'Companies', icon: <BusinessOutlined />, path: '/companies' },
      { text: 'Contacts', icon: <PeopleAltOutlined />, path: '/contacts' },
    ],
  },
  {
    id: 'sales',
    title: 'Sales',
    items: [
      { text: 'Opportunities', icon: <TrendingUp />, path: '/opportunities' },
      { text: 'Quotes', icon: <RequestQuoteOutlined />, path: '/quotes' },
      { text: 'Contracts', icon: <HistoryEduOutlined />, path: '/contracts' },
      { text: 'Tasks', icon: <TaskAltOutlined />, path: '/tasks' },
      {
        text: 'AI email drafts',
        icon: <MarkEmailReadOutlined />,
        path: '/ai-drafts',
        badge: aiDraftsPendingCount > 0 ? aiDraftsPendingCount : undefined,
        formerly: 'AI Drafts',
      },
      { text: 'Sales targets', icon: <TrackChangesOutlined />, path: '/targets', formerly: 'Performance' },
    ],
  },
  {
    id: 'finance',
    title: 'Billing & finance',
    items: [
      { text: 'Invoices', icon: <ReceiptLongOutlined />, path: '/invoices' },
      { text: 'Revenue', icon: <ShowChartOutlined />, path: '/revenue' },
      { text: 'Receivables', icon: <CallReceivedOutlined />, path: '/finance/ar', formerly: 'AR Aging' },
      { text: 'Payables', icon: <CallMadeOutlined />, path: '/finance/ap', formerly: 'AP Aging' },
      { text: 'Profit & loss', icon: <AssessmentOutlined />, path: '/finance/pl' },
      { text: 'Cash flow', icon: <WaterfallChartOutlined />, path: '/finance/cash-flow' },
      { text: 'Balance sheet', icon: <AccountBalanceOutlined />, path: '/finance/balance-sheet' },
      {
        text: 'Revenue recognition',
        icon: <EventRepeatOutlined />,
        path: '/finance/revenue-accrual',
        formerly: 'Revenue Accrual',
      },
    ],
  },
  {
    id: 'support',
    title: 'Support',
    items: [
      { text: 'Tickets', icon: <SupportAgentOutlined />, path: '/tickets' },
      { text: 'Music zones', icon: <SpeakerGroupOutlined />, path: '/zones', formerly: 'Zones' },
      { text: 'Site tech details', icon: <RouterOutlined />, path: '/tech-details', formerly: 'Client Tech Details' },
      { text: 'Help articles', icon: <MenuBookOutlined />, path: '/knowledge-base', formerly: 'Knowledge Base' },
    ],
  },
  {
    id: 'marketing',
    title: 'Marketing',
    items: [
      { text: 'Campaigns', icon: <CampaignOutlined />, path: '/campaigns' },
      { text: 'Prospecting sequences', icon: <AutoFixHighOutlined />, path: '/prospect-sequences', formerly: 'Sequences' },
      { text: 'Email automations', icon: <AutoModeOutlined />, path: '/email-automations' },
      { text: 'Email templates', icon: <DraftsOutlined />, path: '/email-templates' },
      { text: 'Segments', icon: <GroupsOutlined />, path: '/segments' },
    ],
  },
  {
    id: 'admin',
    title: 'Admin',
    items: [
      { text: 'Users', icon: <ManageAccountsOutlined />, path: '/users' },
      { text: 'Contract templates', icon: <ArticleOutlined />, path: '/contract-templates' },
      { text: 'Seasonal email dates', icon: <CalendarMonthOutlined />, path: '/settings', formerly: 'Settings' },
    ],
  },
];

/** True when `pathname` is this item's page or one of its sub-pages (e.g. a record). */
export const isActivePath = (itemPath: string, pathname: string): boolean =>
  pathname === itemPath || pathname.startsWith(`${itemPath}/`);

/** The menu group and item for the current page, used for the top bar location. */
export const findNavLocation = (
  groups: NavGroup[],
  pathname: string
): { group?: NavGroup; item?: NavItem } => {
  let best: { group?: NavGroup; item?: NavItem } = {};
  groups.forEach((group) =>
    group.items.forEach((item) => {
      if (isActivePath(item.path, pathname) && (!best.item || item.path.length > best.item.path.length)) {
        best = { group, item };
      }
    })
  );
  return best;
};

/**
 * Which menu entries each role sees. Display only: hidden pages still open from a link,
 * and nothing here changes what the server allows. Paths not listed for a role are hidden;
 * `'*'` means everything. Unknown or missing roles see everything.
 */
const SALES_FINANCE_HIDDEN = [
  '/revenue',
  '/finance/ar',
  '/finance/ap',
  '/finance/pl',
  '/finance/cash-flow',
  '/finance/balance-sheet',
  '/finance/revenue-accrual',
];

export const MENU_BY_ROLE: Record<string, { groups: string[] | '*'; hidePaths?: string[] }> = {
  Admin: { groups: '*' },
  // Sales: everything except the finance reports and the admin pages. Invoices stay visible.
  Sales: { groups: ['home', 'customers', 'sales', 'finance', 'support', 'marketing'], hidePaths: SALES_FINANCE_HIDDEN },
  Marketing: { groups: ['home', 'customers', 'sales', 'finance', 'support', 'marketing'], hidePaths: SALES_FINANCE_HIDDEN },
  // Finance: customers, sales documents and all of billing & finance.
  Finance: { groups: ['home', 'customers', 'sales', 'finance'] },
  // Tech support and music design: customers, support, and contracts/tasks from Sales.
  Tech: { groups: ['home', 'customers', 'sales', 'support'], hidePaths: ['/opportunities', '/quotes', '/ai-drafts', '/targets'] },
  'Tech Support': { groups: ['home', 'customers', 'sales', 'support'], hidePaths: ['/opportunities', '/quotes', '/ai-drafts', '/targets'] },
  Music: { groups: ['home', 'customers', 'sales', 'support'], hidePaths: ['/opportunities', '/quotes', '/ai-drafts', '/targets'] },
};

export const filterNavForRole = (groups: NavGroup[], role?: string | null): NavGroup[] => {
  const rule = role ? MENU_BY_ROLE[role] : undefined;
  if (!rule || rule.groups === '*') return groups;
  const allowed = rule.groups;
  const hidden = new Set(rule.hidePaths || []);
  return groups
    .filter((g) => allowed.includes(g.id))
    .map((g) => ({ ...g, items: g.items.filter((i) => !hidden.has(i.path)) }))
    .filter((g) => g.items.length > 0);
};
