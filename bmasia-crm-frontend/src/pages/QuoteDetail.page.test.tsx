import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import QuoteDetailPage from './QuoteDetail';
import ApiService from '../services/api';

jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('../services/authService', () => ({ __esModule: true, default: { getCurrentUser: () => null, isAuthenticated: () => true } }));
jest.mock('../services/api', () => {
  const calls: Record<string, jest.Mock> = {
    getQuote: jest.fn(),
    convertQuoteToContract: jest.fn(),
    previewQuotePDF: jest.fn(),
  };
  return {
    __esModule: true,
    default: new Proxy(calls as any, {
      get: (target, key) => (key in target ? target[key] : () => new Promise(() => {})),
    }),
  };
});

const api = ApiService as any;
const quote = {
  id: 'q-1',
  quote_number: 'TH-QT-TEST',
  company: 'co-1',
  company_name: 'Fixture Resort',
  status: 'Accepted',
  currency: 'THB',
  subtotal: 1000,
  discount_amount: 0,
  tax_amount: 0,
  total_value: 1000,
  line_items: [],
  attachments: [],
  activities: [],
  valid_from: '2026-11-01',
  valid_until: '2026-12-01',
  created_at: '2026-11-01T00:00:00Z',
};

let lastLocation: any = null;
const Where: React.FC = () => {
  lastLocation = useLocation();
  return null;
};

const renderAt = (entry: any) =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Where />
      <Routes>
        <Route path="/quotes/:id" element={<QuoteDetailPage />} />
        <Route path="/contracts" element={<div>contracts page</div>} />
        <Route path="/invoices" element={<div>invoices page</div>} />
        <Route path="/quotes" element={<div>quotes list</div>} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  api.getQuote.mockResolvedValue(quote);
  api.convertQuoteToContract.mockResolvedValue({});
  api.previewQuotePDF.mockResolvedValue(new Blob(['%PDF']));
});

it('Convert to Contract opens the contract form pre-filled and writes nothing', async () => {
  const confirm = jest.spyOn(window, 'confirm');
  renderAt('/quotes/q-1');
  fireEvent.click(await screen.findByRole('button', { name: /convert to contract/i }));
  await waitFor(() => expect(lastLocation.pathname).toBe('/contracts'));
  expect(lastLocation.search).toBe('?new=true&company=co-1&quote=q-1');
  expect(api.convertQuoteToContract).not.toHaveBeenCalled();
  expect(confirm).not.toHaveBeenCalled();
  confirm.mockRestore();
});

it('Create Invoice opens the invoice form pre-filled from the quote', async () => {
  renderAt('/quotes/q-1');
  fireEvent.click(await screen.findByRole('button', { name: /create invoice/i }));
  await waitFor(() => expect(lastLocation.pathname).toBe('/invoices'));
  expect(lastLocation.search).toBe('?new=true&company=co-1&quote=q-1');
});

it('Preview opens the PDF preview', async () => {
  const open = jest.spyOn(window, 'open').mockImplementation(() => null);
  (window.URL as any).createObjectURL = jest.fn(() => 'blob:preview');
  renderAt('/quotes/q-1');
  fireEvent.click(await screen.findByRole('button', { name: /^preview$/i }));
  await waitFor(() => expect(open).toHaveBeenCalledWith('blob:preview', '_blank'));
  expect(api.previewQuotePDF).toHaveBeenCalledWith('q-1');
  open.mockRestore();
});

it('the breadcrumb returns to the list view passed along, or the plain list', async () => {
  renderAt({ pathname: '/quotes/q-1', state: { listSearch: 'status=Accepted&page=2' } });
  const crumb = await screen.findByRole('link', { name: 'Quotes' });
  expect(crumb.getAttribute('href')).toBe('/quotes?status=Accepted&page=2');
});

it('Create Invoice is only offered on accepted quotes', async () => {
  api.getQuote.mockResolvedValue({ ...quote, status: 'Sent' });
  renderAt('/quotes/q-1');
  await screen.findByRole('button', { name: /accept/i });
  expect(screen.queryByRole('button', { name: /create invoice/i })).toBeNull();
  expect(screen.getByRole('button', { name: /^preview$/i })).toBeInTheDocument();
});
