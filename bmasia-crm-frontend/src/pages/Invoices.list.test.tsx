import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import Invoices from './Invoices';
import ApiService from '../services/api';

jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('../services/authService', () => ({ __esModule: true, default: { getCurrentUser: () => null, isAuthenticated: () => true } }));
jest.mock('../components/InvoiceForm', () => ({
  __esModule: true,
  default: (p: any) => (p.open ? <div role="dialog" aria-label="invoice form">{`company=${p.initialCompanyId} contract=${p.initialContractId}`}</div> : null),
}));
jest.mock('../components/InvoiceDetail', () => ({
  __esModule: true,
  default: (p: any) => (p.open ? <div role="dialog" aria-label="invoice detail">{p.invoice?.invoice_number}</div> : null),
}));
jest.mock('../services/api', () => {
  const calls: Record<string, any> = {
    getInvoices: jest.fn(),
    getCompaniesSimple: () => Promise.resolve([{ id: 'a1b2c3d4-0000-0000-0000-000000000001', name: 'Fixture Resort' }]),
    getContracts: () => Promise.resolve({ results: [], count: 0 }),
  };
  return {
    __esModule: true,
    default: new Proxy(calls, {
      get: (target, key) => (key in target ? target[key as string] : () => new Promise(() => {})),
    }),
  };
});

const api = ApiService as any;
const CO = 'a1b2c3d4-0000-0000-0000-000000000001';
const invoice = (over: any = {}) => ({
  id: 'i-1',
  invoice_number: 'INV-TEST-1',
  company: CO,
  company_name: 'Fixture Resort',
  total_amount: 108000,
  currency: 'THB',
  issue_date: '2026-11-01',
  due_date: '2026-12-01',
  status: 'Draft',
  is_overdue: false,
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
        <Route path="/invoices" element={<Invoices />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  api.getInvoices.mockReset();
  api.getInvoices.mockResolvedValue({ results: [invoice()], count: 60 });
});

it('reads search, filters, sort and page from the address', async () => {
  renderAt(`/invoices?q=fixture&status=Sent&company=${CO}&payment=Cash&sort=due_date&page=2&size=50`);
  await waitFor(() => expect(api.getInvoices).toHaveBeenCalled());
  expect(api.getInvoices).toHaveBeenLastCalledWith({
    page: 2,
    page_size: 50,
    search: 'fixture',
    status: 'Sent',
    company: CO,
    payment_method: 'Cash',
    ordering: 'due_date',
  });
});

it('unknown values in the address fall back to the defaults and are not sent', async () => {
  renderAt('/invoices?status=Bogus&company=nope&payment=Gold&sort=secret&size=0');
  await waitFor(() => expect(api.getInvoices).toHaveBeenCalled());
  expect(api.getInvoices).toHaveBeenLastCalledWith({
    page: 1,
    page_size: 25,
    search: undefined,
    status: undefined,
    company: undefined,
    payment_method: undefined,
    ordering: '-issue_date',
  });
});

it('typing a search updates the address and goes back to page 1', async () => {
  renderAt('/invoices?status=Sent&page=3');
  fireEvent.change(await screen.findByPlaceholderText(/search by invoice number/i), { target: { value: 'inv-1' } });
  await waitFor(() => expect(lastLocation.search).toContain('q=inv-1'));
  expect(lastLocation.search).toContain('status=Sent');
  expect(lastLocation.search).not.toContain('page=');
});

it('amounts show in their own currency', async () => {
  api.getInvoices.mockResolvedValue({
    results: [invoice(), invoice({ id: 'i-2', invoice_number: 'INV-TEST-2', total_amount: 580, currency: 'USD' })],
    count: 2,
  });
  renderAt('/invoices');
  expect(await screen.findByText('THB 108,000')).toBeInTheDocument();
  expect(screen.getByText('USD 580')).toBeInTheDocument();
});

it.each([
  ['Draft', {}, ['View Details', 'Edit', 'Download PDF', 'Send via Email', 'Mark as Sent', 'Delete']],
  ['Sent', {}, ['View Details', 'Edit', 'Download PDF', 'Mark as Paid', 'Delete']],
  ['Overdue', { is_overdue: true, days_overdue: 5 }, ['View Details', 'Edit', 'Download PDF', 'Mark as Paid', 'Delete']],
  ['Paid', { receipt_number: 'R-1' }, ['View Details', 'Edit', 'Download PDF', 'Download Receipt', 'Delete']],
])('the actions menu for a %s invoice is unchanged', async (status, extra, labels) => {
  api.getInvoices.mockResolvedValue({ results: [invoice({ status, ...(extra as any) })], count: 1 });
  renderAt('/invoices');
  fireEvent.click(await screen.findByRole('button', { name: /more actions for invoice INV-TEST-1/i }));
  const menu = await screen.findByRole('menu');
  expect(within(menu).getAllByRole('menuitem').map((m) => m.textContent)).toEqual(labels);
});

it('a row opens the invoice detail', async () => {
  renderAt('/invoices');
  fireEvent.click(await screen.findByText('INV-TEST-1'));
  expect(await screen.findByRole('dialog', { name: 'invoice detail' })).toHaveTextContent('INV-TEST-1');
});

it('?new=true from a contract opens the form pre-filled and keeps the list view', async () => {
  renderAt(`/invoices?status=Sent&new=true&company=${CO}&contract=k-1`);
  expect(await screen.findByRole('dialog', { name: 'invoice form' })).toHaveTextContent(`company=${CO} contract=k-1`);
  await waitFor(() => expect(lastLocation.search).toBe('?status=Sent'));
});

it('an overdue invoice says how many days', async () => {
  api.getInvoices.mockResolvedValue({ results: [invoice({ status: 'Overdue', is_overdue: true, days_overdue: 12 })], count: 1 });
  renderAt('/invoices');
  expect(await screen.findByText('12 days overdue')).toBeInTheDocument();
});
