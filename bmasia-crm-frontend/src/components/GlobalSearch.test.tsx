import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import GlobalSearch from './GlobalSearch';
import ApiService from '../services/api';

let mockRole = 'Admin';
jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { role: mockRole } }),
}));

jest.mock('../services/api', () => ({
  __esModule: true,
  default: {
    getCompanies: jest.fn(),
    getContacts: jest.fn(),
    getContracts: jest.fn(),
    getQuotes: jest.fn(),
    getInvoices: jest.fn(),
  },
}));

const api = ApiService as unknown as Record<string, jest.Mock>;

const Where: React.FC = () => <div data-testid="where">{useLocation().pathname}</div>;

const renderSearch = () =>
  render(
    <MemoryRouter initialEntries={['/today']}>
      <GlobalSearch />
      <Routes>
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  jest.clearAllMocks();
  api.getCompanies.mockResolvedValue({ results: [{ id: 'co-1', name: 'Fixture Resort', city: 'Phuket', country: 'Thailand' }] });
  api.getContacts.mockResolvedValue({ results: [{ id: 'ct-1', name: 'Pat Example', title: 'GM', company: 'co-1', company_name: 'Fixture Resort' }] });
  api.getContracts.mockResolvedValue({
    results: [{ id: 'k-1', contract_number: 'TH-TEST-0001', company_name: 'Fixture Resort', status: 'Active', value: 108000, currency: 'THB' }],
  });
  // One failing source must not hide the others.
  api.getQuotes.mockRejectedValue(new Error('forbidden'));
  api.getInvoices.mockResolvedValue({ results: [] });
});

it('opens with Ctrl+K, searches every record type read-only and groups the results', async () => {
  renderSearch();
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const input = await screen.findByRole('combobox');
  fireEvent.change(input, { target: { value: 'fixture' } });

  expect(await screen.findByText('TH-TEST-0001')).toBeInTheDocument();
  expect(screen.getByText('Companies')).toBeInTheDocument();
  expect(screen.getByText('Contacts')).toBeInTheDocument();
  expect(screen.getByText('Fixture Resort · Active · THB 108,000')).toBeInTheDocument();
  expect(screen.queryByText('Quotes')).not.toBeInTheDocument();
  expect(api.getCompanies).toHaveBeenCalledWith({ search: 'fixture', page_size: 5 });
});

it('does not search for a single letter', async () => {
  renderSearch();
  fireEvent.keyDown(window, { key: 'k', metaKey: true });
  fireEvent.change(await screen.findByRole('combobox'), { target: { value: 'f' } });
  await new Promise((r) => setTimeout(r, 300));
  expect(api.getCompanies).not.toHaveBeenCalled();
});

it('opens the highlighted result with the keyboard', async () => {
  renderSearch();
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const input = await screen.findByRole('combobox');
  fireEvent.change(input, { target: { value: 'fixture' } });
  await screen.findByText('TH-TEST-0001');

  // Results: company, contact, contract. Move down twice to the contract.
  fireEvent.keyDown(input, { key: 'ArrowDown' });
  fireEvent.keyDown(input, { key: 'ArrowDown' });
  fireEvent.keyDown(input, { key: 'Enter' });

  await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/contracts/k-1'));
});

it('finds menu pages by their former name', async () => {
  api.getCompanies.mockResolvedValue({ results: [] });
  api.getContacts.mockResolvedValue({ results: [] });
  api.getContracts.mockResolvedValue({ results: [] });
  renderSearch();
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const input = await screen.findByRole('combobox');
  fireEvent.change(input, { target: { value: 'knowledge' } });

  expect(await screen.findByText('Help articles')).toBeInTheDocument();
  expect(screen.getByText('Support · formerly “Knowledge Base”')).toBeInTheDocument();
  fireEvent.keyDown(input, { key: 'Enter' });
  await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/knowledge-base'));
});

it('does not offer pages the role menu hides', async () => {
  mockRole = 'Sales';
  api.getCompanies.mockResolvedValue({ results: [] });
  api.getContacts.mockResolvedValue({ results: [] });
  api.getContracts.mockResolvedValue({ results: [] });
  renderSearch();
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  fireEvent.change(await screen.findByRole('combobox'), { target: { value: 'balance' } });
  await waitFor(() => expect(api.getCompanies).toHaveBeenCalled());
  expect(screen.queryByText('Balance sheet')).not.toBeInTheDocument();
  mockRole = 'Admin';
});
