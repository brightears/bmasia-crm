import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import GlobalSearch from './GlobalSearch';
import ApiService from '../services/api';

let mockUser: any = { id: 'x', role: 'Admin', is_active: true, permissions: [] };
jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
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
  mockUser = { id: 'x', role: 'Admin', is_active: true, permissions: [] };
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

const openAndType = async (text: string) => {
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const input = await screen.findByRole('combobox');
  fireEvent.change(input, { target: { value: text } });
  return input;
};

it('only searches record types whose pages the user may open', async () => {
  mockUser = { id: 'x', role: 'Tech Support', is_active: true, permissions: [] };
  renderSearch();
  await openAndType('fixture');
  await screen.findByText('TH-TEST-0001');
  expect(api.getQuotes).not.toHaveBeenCalled(); // Tech Support cannot open quote pages
  expect(api.getContracts).toHaveBeenCalled();
});

it('shows each type as it arrives instead of waiting for the slowest', async () => {
  api.getContracts.mockReturnValue(new Promise(() => {})); // never answers
  renderSearch();
  await openAndType('fixture');
  expect(await screen.findByText('Fixture Resort')).toBeInTheDocument();
  expect(screen.getByText('Pat Example')).toBeInTheDocument();
});

it('says that search failed when every type failed, not "Nothing found"', async () => {
  for (const k of ['getCompanies', 'getContacts', 'getContracts', 'getQuotes', 'getInvoices']) {
    api[k].mockRejectedValue(new Error('offline'));
  }
  renderSearch();
  await openAndType('fixture');
  expect(await screen.findByText(/search failed/i)).toBeInTheDocument();
  expect(screen.queryByText(/nothing found/i)).not.toBeInTheDocument();
});

it('names the types that could not be searched when only some failed', async () => {
  renderSearch();
  await openAndType('fixture');
  expect(await screen.findByText('Could not search quotes.')).toBeInTheDocument();
});

it('ignores Enter while the results still belong to the previous text', async () => {
  renderSearch();
  const input = await openAndType('fixture');
  await screen.findByText('TH-TEST-0001');
  fireEvent.change(input, { target: { value: 'fixture resort' } });
  fireEvent.keyDown(input, { key: 'Enter' }); // within the 250 ms wait
  expect(screen.getByTestId('where')).toHaveTextContent('/today');
});

it('leaves Ctrl/Cmd+K to rich-text editors', async () => {
  const editor = document.createElement('div');
  editor.className = 'ql-editor';
  editor.setAttribute('contenteditable', 'true');
  document.body.appendChild(editor);
  renderSearch();
  fireEvent.keyDown(editor, { key: 'k', metaKey: true });
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  editor.remove();
});

it('does not offer pages the role menu hides', async () => {
  mockUser = { id: 'x', role: 'Sales', is_active: true, permissions: [] };
  renderSearch();
  await openAndType('balance');
  await waitFor(() => expect(api.getCompanies).toHaveBeenCalled());
  expect(screen.queryByText('Balance sheet')).not.toBeInTheDocument();
});
