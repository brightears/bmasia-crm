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
