import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';
import ApiService from '../services/api';

jest.mock('../services/authService', () => ({ __esModule: true, default: {} }));
jest.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: { first_name: 'Alex' } }) }));
jest.mock('../services/api', () => {
  const calls: Record<string, any> = { getDashboardStats: jest.fn(), getMyTasks: () => Promise.resolve([]) };
  return {
    __esModule: true,
    default: new Proxy(calls, { get: (t, k) => (k in t ? t[k as string] : () => new Promise(() => {})) }),
  };
});

const api = ApiService as any;
const oldResponse = {
  total_companies: 3, active_opportunities: 4, opportunities_value: 50000, active_contracts: 2, contracts_value: 110160,
  overdue_tasks: 0, overdue_invoices: 2, pending_renewals: 2, contacted_count: 1, quotation_count: 1, contract_count: 1,
  won_count: 1, lost_count: 0, monthly_revenue: 110160, monthly_new_opportunities: 1, monthly_closed_deals: 0,
  win_rate: 100, previous_month_revenue: 0, previous_win_rate: 0, total_overdue_amount: 50700, pending_renewal_value: 110160,
  pipeline_stages: {}, revenue_trend: [], new_revenue: 110160, renewal_revenue: 0, churned_revenue: 0, churned_count: 0,
  net_revenue: 110160,
};
const newResponse = {
  ...oldResponse,
  net_revenue_by_currency: [{ currency: 'THB', total: '108000.00' }, { currency: 'USD', total: '2160.00' }],
  monthly_revenue_by_currency: [{ currency: 'THB', total: '108000.00' }, { currency: 'USD', total: '2160.00' }],
  previous_month_revenue_by_currency: [],
  total_overdue_amount_by_currency: [{ currency: 'THB', total: '50000.00' }, { currency: 'USD', total: '700.00' }],
  pending_renewal_value_by_currency: [{ currency: 'THB', total: '108000.00' }, { currency: 'USD', total: '2160.00' }],
  new_revenue_by_currency: [{ currency: 'THB', total: '108000.00' }, { currency: 'USD', total: '2160.00' }],
  renewal_revenue_by_currency: [],
  churned_revenue_by_currency: [],
  contracts_value_by_currency: [],
};

const card = async (title: string) => (await screen.findByText(title)).closest('.MuiPaper-root') as HTMLElement;

it('older backend: shows the single totals as today', async () => {
  api.getDashboardStats.mockResolvedValue(oldResponse);
  render(<MemoryRouter><Dashboard /></MemoryRouter>);
  expect(within(await card('Overdue Invoices')).getByText('USD 50,700')).toBeInTheDocument();
});

it('newer backend: one line per currency, never added together', async () => {
  api.getDashboardStats.mockResolvedValue(newResponse);
  render(<MemoryRouter><Dashboard /></MemoryRouter>);
  const overdue = await card('Overdue Invoices');
  expect(within(overdue).getByText('USD 700')).toBeInTheDocument();
  expect(within(overdue).getByText('THB 50,000')).toBeInTheDocument();
  expect(within(overdue).queryByText(/50,700/)).toBeNull();
  const net = await card('Net Revenue This Month');
  expect(within(net).getByText('USD 2,160')).toBeInTheDocument();
  expect(within(net).queryByText(/110,160/)).toBeNull();
});
