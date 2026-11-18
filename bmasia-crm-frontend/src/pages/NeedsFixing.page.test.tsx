import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import NeedsFixing from './NeedsFixing';
import { downloadDataQualityCsv, getDataQualityCheck, getDataQualitySummary } from '../services/dataQuality';

jest.mock('../services/authService', () => ({ __esModule: true, default: {}, authApi: {} }));
jest.mock('../services/dataQuality', () => {
  const actual = jest.requireActual('../services/dataQuality');
  return {
    ...actual,
    getDataQualitySummary: jest.fn(),
    getDataQualityCheck: jest.fn(),
    downloadDataQualityCsv: jest.fn(),
  };
});
jest.mock('../services/api', () => ({
  __esModule: true,
  default: {
    getCompaniesSimple: () =>
      Promise.resolve([
        { id: '11111111-1111-1111-1111-111111111111', name: 'Lumen Bay Resort & Spa', billing_entity: '' },
      ]),
    getUsers: () => Promise.resolve({ results: [{ id: '22222222-2222-2222-2222-222222222222', first_name: 'Sam', last_name: 'Seller' }] }),
  },
}));

const summary = jest.mocked(getDataQualitySummary);
const checkPage = jest.mocked(getDataQualityCheck);
const download = jest.mocked(downloadDataQualityCsv);

const checks = [
  { key: 'contract_active_past_end', title: 'Active contracts past their end date', why: 'The term is over.', severity: 'high' as const, record_type: 'contract' as const, count: 2, rows: [] },
  { key: 'invoice_overdue', title: 'Overdue invoices', why: 'Money is late.', severity: 'high' as const, record_type: 'invoice' as const, count: 0, rows: [] },
  { key: 'company_lookalike_names', title: 'Companies that may be duplicates', why: 'Split history.', severity: 'low' as const, record_type: 'company' as const, count: 1, rows: [] },
];

const contractRows = [
  {
    id: 'c-1',
    record_type: 'contract' as const,
    label: 'TH-CT26001',
    company_id: '11111111-1111-1111-1111-111111111111',
    company_name: 'Lumen Bay Resort & Spa',
    fact: 'Ended 23 days ago (27 Oct 2026); no renewal recorded',
    owner_id: '22222222-2222-2222-2222-222222222222',
    owner_name: 'Sam Seller',
    date: '2026-10-27',
    amount: '108000.00',
    currency: 'THB',
    link: '/contracts/c-1',
    related: [],
  },
  {
    id: 'c-2',
    record_type: 'contract' as const,
    label: 'HK-CT26002',
    company_id: null,
    company_name: null,
    fact: 'Ended yesterday (18 Nov 2026); renewal HK-CT26090 is Sent',
    owner_id: null,
    owner_name: null,
    date: '2026-11-18',
    amount: '4450.00',
    currency: 'USD',
    link: '/contracts/c-2',
    related: [],
  },
];

const page = (key: string, rows: any[], count = rows.length) => {
  const meta = checks.find((c) => c.key === key)!;
  return { ...meta, today: '2026-11-19', page: 1, page_size: 25, count, rows };
};

let location: any;
const Where: React.FC = () => {
  location = useLocation();
  return null;
};

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Where />
      <Routes>
        <Route path="/needs-fixing/:key?" element={<NeedsFixing />} />
        <Route path="/contracts/:id" element={<div>contract page</div>} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  summary.mockReset();
  checkPage.mockReset();
  download.mockReset();
  summary.mockResolvedValue({ today: '2026-11-19', generated_at: '', checks, total: 3, clear: 1 });
});

it('shows each record with the fact that triggered it and links to the record', async () => {
  checkPage.mockResolvedValue(page('contract_active_past_end', contractRows));
  renderAt('/needs-fixing/contract_active_past_end');
  const record = await screen.findByRole('link', { name: 'TH-CT26001' });
  expect(record).toHaveAttribute('href', '/contracts/c-1');
  const row = screen.getByRole('row', { name: /TH-CT26001/ });
  expect(within(row).getAllByText('Ended 23 days ago (27 Oct 2026); no renewal recorded').length).toBeGreaterThan(0);
  expect(within(row).getByRole('link', { name: 'Lumen Bay Resort & Spa' })).toHaveAttribute(
    'href',
    '/companies/11111111-1111-1111-1111-111111111111'
  );
  expect(within(row).getByText('Sam Seller')).toBeInTheDocument();
  expect(within(row).getByText('THB 108,000')).toBeInTheDocument();
  expect(screen.getByText('USD 4,450')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Active contracts past their end date' })).toBeInTheDocument();
  expect(screen.getByText('2 contracts')).toBeInTheDocument();
  expect(checkPage).toHaveBeenCalledWith('contract_active_past_end', { page: 1, pageSize: 25, company: undefined, owner: undefined });
  fireEvent.click(within(screen.getByRole('row', { name: /HK-CT26002/ })).getAllByText(/Ended yesterday/)[0]);
  await waitFor(() => expect(location.pathname).toBe('/contracts/c-2'));
});

it('opens the first check with records when none is chosen', async () => {
  checkPage.mockResolvedValue(page('contract_active_past_end', contractRows));
  renderAt('/needs-fixing');
  await waitFor(() => expect(location.pathname).toBe('/needs-fixing/contract_active_past_end'));
  expect(await screen.findByRole('link', { name: 'TH-CT26001' })).toBeInTheDocument();
});

it('reads page and filters from the address and passes them to the server', async () => {
  checkPage.mockResolvedValue(page('contract_active_past_end', contractRows, 60));
  renderAt('/needs-fixing/contract_active_past_end?page=2&owner=none&company=11111111-1111-1111-1111-111111111111');
  await screen.findByRole('link', { name: 'TH-CT26001' });
  expect(checkPage).toHaveBeenCalledWith('contract_active_past_end', {
    page: 2,
    pageSize: 25,
    company: '11111111-1111-1111-1111-111111111111',
    owner: 'none',
  });
  expect(screen.getByText(/matching the filters/)).toBeInTheDocument();
});

it('downloads the CSV for the current check and filters', async () => {
  checkPage.mockResolvedValue(page('contract_active_past_end', contractRows));
  download.mockResolvedValue(undefined);
  renderAt('/needs-fixing/contract_active_past_end?owner=none');
  fireEvent.click(await screen.findByRole('button', { name: 'Download CSV' }));
  await waitFor(() => expect(download).toHaveBeenCalledWith('contract_active_past_end', { company: undefined, owner: 'none' }));
});

it('shows related records and an empty state', async () => {
  checkPage.mockResolvedValueOnce(
    page('company_lookalike_names', [
      {
        ...contractRows[0],
        id: 'co-1',
        record_type: 'company',
        label: 'Lumen Bay Co., Ltd.',
        fact: '2 records with the same name: Lumen Bay Co., Ltd.; lumen-bay',
        link: '/companies/co-1',
        amount: null,
        currency: null,
        owner_name: null,
        related: [{ label: 'lumen-bay', link: '/companies/co-2' }],
      },
    ])
  );
  renderAt('/needs-fixing/company_lookalike_names');
  expect(await screen.findByRole('link', { name: 'lumen-bay' })).toHaveAttribute('href', '/companies/co-2');

  checkPage.mockResolvedValueOnce(page('invoice_overdue', [], 0));
  fireEvent.click(screen.getByRole('link', { name: /Overdue invoices/ }));
  expect(await screen.findByText('Nothing to fix here')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Download CSV' })).toBeDisabled();
});

it('says when a check does not exist', async () => {
  checkPage.mockRejectedValue({ response: { status: 404 } });
  renderAt('/needs-fixing/no_such_check');
  expect(await screen.findByText(/This check does not exist/)).toBeInTheDocument();
});

it('shows a load error with a retry', async () => {
  checkPage.mockRejectedValueOnce(new Error('Network Error'));
  checkPage.mockResolvedValueOnce(page('contract_active_past_end', contractRows));
  renderAt('/needs-fixing/contract_active_past_end');
  expect(await screen.findByText(/Could not load this check: Network Error/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByRole('link', { name: 'TH-CT26001' })).toBeInTheDocument();
});

it("never shows the previous check's title while the next one loads", async () => {
  checkPage.mockResolvedValueOnce(page('contract_active_past_end', contractRows));
  renderAt('/needs-fixing/contract_active_past_end');
  await screen.findByRole('link', { name: 'TH-CT26001' });
  checkPage.mockReturnValueOnce(new Promise(() => {}));
  fireEvent.click(screen.getByRole('link', { name: /Companies that may be duplicates/ }));
  expect(await screen.findByRole('heading', { name: 'Companies that may be duplicates' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Active contracts past their end date' })).toBeNull();
  expect(screen.queryByText('2 contracts')).toBeNull();
});

it('moves a page past the end to the last page', async () => {
  checkPage.mockImplementation((key: string, opts: any) =>
    Promise.resolve({ ...page('contract_active_past_end', opts.page === 1 ? contractRows : [], 2), page: opts.page })
  );
  renderAt('/needs-fixing/contract_active_past_end?page=4');
  await waitFor(() => expect(location.search).toBe(''));
  expect(await screen.findByRole('link', { name: 'TH-CT26001' })).toBeInTheDocument();
});

it('ignores a company or owner in the address that is not an id', async () => {
  checkPage.mockResolvedValue(page('contract_active_past_end', contractRows));
  renderAt('/needs-fixing/contract_active_past_end?company=123&owner=someone');
  await screen.findByRole('link', { name: 'TH-CT26001' });
  expect(checkPage).toHaveBeenLastCalledWith('contract_active_past_end', {
    page: 1,
    pageSize: 25,
    company: undefined,
    owner: undefined,
  });
});
