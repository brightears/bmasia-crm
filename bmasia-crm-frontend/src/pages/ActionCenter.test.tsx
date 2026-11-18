import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ActionCenter, { recordPath } from './ActionCenter';
import ApiService from '../services/api';

jest.mock('../services/authService', () => ({ __esModule: true, default: {}, authApi: {} }));
jest.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: { first_name: 'Alex' } }) }));
jest.mock('../components/NeedsFixingCard', () => ({ __esModule: true, default: () => <div>needs fixing card</div> }));
jest.mock('../services/api', () => ({ __esModule: true, default: { getActionCenterItems: jest.fn() } }));

const api = ApiService as any;

const item = (type: string, id: string, title: string, extra: any = {}) => ({
  id,
  type,
  urgency: 'overdue',
  title,
  subtitle: 'Lumen Bay Resort & Spa',
  contact_name: null,
  contact_email: null,
  contact_phone: null,
  time_context: '2 days overdue',
  priority: 'Medium',
  amount: null,
  currency: null,
  link_url: `/${type}s`,
  link_id: id,
  meta: {},
  ...extra,
});

it('maps every row type to the record itself', () => {
  expect(recordPath({ type: 'contract', link_id: 'c1', link_url: '/contracts' })).toBe('/contracts/c1');
  expect(recordPath({ type: 'opportunity', link_id: 'o1', link_url: '/opportunities' })).toBe('/opportunities/o1');
  expect(recordPath({ type: 'task', link_id: 't1', link_url: '/tasks' })).toBe('/tasks/t1');
  expect(recordPath({ type: 'invoice', link_id: 'i1', link_url: '/invoices' })).toBe('/invoices?open=i1');
  expect(recordPath({ type: 'task', link_id: '', link_url: '/tasks' })).toBe('/tasks');
});

it('renders rows as links to their records, amounts in the shared format, and the card', async () => {
  api.getActionCenterItems.mockResolvedValue({
    items: [
      item('task', 't1', 'Call back the GM'),
      item('invoice', 'i1', 'Invoice TH-IV26001', { amount: 108000, currency: 'THB' }),
      item('contract', 'c1', 'Contract TH-CT26001', { urgency: 'upcoming', meta: { auto_renew: false } }),
    ],
    summary: { overdue_count: 2, today_count: 0, upcoming_count: 1, expiring_count: 1 },
  });
  render(
    <MemoryRouter>
      <ActionCenter />
    </MemoryRouter>
  );
  expect(await screen.findByRole('link', { name: /Call back the GM/ })).toHaveAttribute('href', '/tasks/t1');
  expect(screen.getByRole('link', { name: /Invoice TH-IV26001/ })).toHaveAttribute('href', '/invoices?open=i1');
  expect(screen.getByRole('link', { name: /Contract TH-CT26001/ })).toHaveAttribute('href', '/contracts/c1');
  expect(screen.getByText('THB 108,000')).toBeInTheDocument();
  expect(screen.getByText('needs fixing card')).toBeInTheDocument();
});

it('keeps the card when Today itself fails to load', async () => {
  api.getActionCenterItems.mockRejectedValue(new Error('Network Error'));
  render(
    <MemoryRouter>
      <ActionCenter />
    </MemoryRouter>
  );
  expect(await screen.findByText(/Could not load today's items/)).toBeInTheDocument();
  expect(screen.getByText('needs fixing card')).toBeInTheDocument();
});
