import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import Renewals from './Renewals';
import { getRenewals } from '../services/renewals';

jest.mock('../services/renewals', () => ({ __esModule: true, getRenewals: jest.fn() }));
const api = getRenewals as jest.Mock;

const STATES = [
  ['not_started', 'Not started', 'open'],
  ['drafted', 'Renewal drafted', 'open'],
  ['sent', 'Sent', 'open'],
  ['signed', 'Signed / active', 'renewed'],
  ['invoiced', 'Invoiced', 'renewed'],
  ['paid', 'Paid', 'renewed'],
  ['renewed_unlinked', 'Renewed, not linked', 'renewed'],
  ['auto_renews', 'Auto-renews', 'auto'],
  ['lapsed', 'Expired, not renewed', 'lost'],
  ['lost', 'Cancelled / lost', 'lost'],
].map(([key, label, group]) => ({ key, label, group }));

const row = (n: number, over: any = {}) => ({
  contract_id: `00000000-0000-0000-0000-00000000000${n}`,
  company_id: `10000000-0000-0000-0000-00000000000${n}`,
  contract_number: `HK-CT9900${n}`,
  corporate_group: `Fixture Hotel ${n}`,
  company: `Fixture Hotel ${n}`,
  country: 'Thailand',
  end_date: '2026-11-20',
  zones: 3,
  zones_source: 'service_locations',
  value: 1200,
  currency: 'USD',
  product: 'Soundtrack',
  lifecycle_type: '',
  status: 'Active',
  auto_renew: false,
  billing_frequency: 'Annual',
  property_name: '',
  contract_type: 'Annual',
  start_date: '2025-11-21',
  term_months: 12,
  entity: 'hk',
  owner: null,
  owner_source: null,
  days_from_end: -2,
  ...over,
  renewal: {
    state: 'not_started',
    label: 'Not started',
    group: 'open',
    reason: 'no_renewal',
    attention: null,
    attention_label: null,
    successor: null,
    other_linked: [],
    value_change: null,
    value_change_basis: null,
    ...(over.renewal || {}),
  },
});

const response = (over: any = {}) => ({
  as_of: '2026-11-18',
  view: 'month',
  year: 2026,
  month: 11,
  month_label: 'November 2026',
  entity: '',
  window: { start: '2026-11-01', end: '2026-11-30' },
  states: STATES,
  attention_reasons: [],
  months: Array.from({ length: 12 }, (_, i) => ({
    year: 2026, month: i + 1, label: '', count: i === 10 ? 2 : 0, attention: i === 10 ? 1 : 0,
    open: 0, renewed: 0, auto: 0, lost: 0,
  })),
  count: 2,
  rows: [
    row(1, {
      renewal: {
        state: 'not_started', label: 'Not started', group: 'open',
        attention: 'ending_soon_nothing_sent', attention_label: 'Ends within 30 days, no renewal sent',
      },
    }),
    row(2, {
      currency: 'THB',
      value: 108000,
      renewal: {
        state: 'paid', label: 'Paid', group: 'renewed', value_change: 12000, value_change_basis: 'term',
        successor: {
          contract_id: '20000000-0000-0000-0000-000000000002', contract_number: 'TH-CT99102', status: 'Active',
          start_date: '2026-11-21', end_date: '2027-11-20', term_months: 12, value: 120000, currency: 'THB',
          signed_date: null, sent_date: null, invoice_state: 'paid', other_company: false,
        },
      },
    }),
  ],
  ...over,
});

let lastLocation: any = null;
const Where: React.FC = () => {
  lastLocation = useLocation();
  return null;
};
const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Where />
      <Routes>
        <Route path="/renewals" element={<Renewals />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  api.mockReset();
});

it('shows the month, its rows with links, states and per-currency totals', async () => {
  api.mockResolvedValue(response());
  renderAt('/renewals?year=2026&month=11');
  expect(await screen.findByText('Fixture Hotel 1')).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith({ view: 'month', year: 2026, month: 11, entity: '' });

  const table = screen.getByRole('table', { name: /November 2026/ });
  const rows = within(table).getAllByRole('row');
  expect(within(rows[1]).getByRole('link', { name: 'Fixture Hotel 1' })).toHaveAttribute(
    'href', '/companies/10000000-0000-0000-0000-000000000001');
  expect(within(rows[1]).getByText('Ends within 30 days, no renewal sent')).toBeInTheDocument();
  expect(within(rows[2]).getByRole('link', { name: 'Renewal contract TH-CT99102' })).toHaveAttribute(
    'href', '/contracts/20000000-0000-0000-0000-000000000002');
  expect(within(rows[2]).getByText('+THB 12,000')).toBeInTheDocument();

  expect(screen.getByRole('region', { name: 'THB totals' })).toHaveTextContent('THB 108,000');
  expect(screen.getByRole('region', { name: 'USD totals' })).toHaveTextContent('USD 1,200');
  expect(screen.getByRole('region', { name: 'THB totals' })).toHaveTextContent('100%');
});

it('keeps filters and sort in the address and filters the rows', async () => {
  api.mockResolvedValue(response());
  renderAt('/renewals?year=2026&month=11');
  await screen.findByText('Fixture Hotel 1');

  fireEvent.click(screen.getByRole('button', { name: 'Paid (1)' }));
  await waitFor(() => expect(lastLocation.search).toContain('state=paid'));
  expect(screen.queryByText('Fixture Hotel 1')).not.toBeInTheDocument();
  expect(screen.getByText('1 of 2 terms')).toBeInTheDocument();

  fireEvent.click(screen.getByText('Current value'));
  await waitFor(() => expect(lastLocation.search).toContain('sort=value'));
});

it('opens a month from the strip and the all-open view', async () => {
  api.mockResolvedValue(response());
  renderAt('/renewals?year=2026&month=11');
  await screen.findByText('Fixture Hotel 1');
  fireEvent.click(screen.getByRole('button', { name: /^December 2026/ }));
  await waitFor(() => expect(api).toHaveBeenLastCalledWith({ view: 'month', year: 2026, month: 12, entity: '' }));
  fireEvent.click(screen.getByRole('button', { name: /All open/ }));
  await waitFor(() => expect(lastLocation.search).toContain('view=open'));
  expect(api).toHaveBeenLastCalledWith(expect.objectContaining({ view: 'open', year: 2026 }));
});

it('says so when nothing ends in the month', async () => {
  api.mockResolvedValue(response({ month: 3, month_label: 'March 2026', rows: [], count: 0 }));
  renderAt('/renewals?year=2026&month=3');
  expect(await screen.findByText('Nothing ends in this month')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Export CSV/ })).toBeDisabled();
});

it('shows an error with a way to try again', async () => {
  api.mockRejectedValueOnce(new Error('boom')).mockResolvedValue(response());
  renderAt('/renewals?year=2026&month=11');
  expect(await screen.findByText('The renewals could not be loaded.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Try again/ }));
  expect(await screen.findByText('Fixture Hotel 1')).toBeInTheDocument();
});

it('ignores unknown values in the address', async () => {
  api.mockResolvedValue(response());
  renderAt('/renewals?year=20x6&month=13&entity=sg&sort=bogus');
  await screen.findByText('Fixture Hotel 1');
  const now = new Date();
  expect(api).toHaveBeenCalledWith({ view: 'month', year: now.getFullYear(), month: now.getMonth() + 1, entity: '' });
});
