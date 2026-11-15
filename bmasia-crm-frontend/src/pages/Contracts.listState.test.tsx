import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import Contracts from './Contracts';
import ApiService from '../services/api';

jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('../services/api', () => {
  const getContracts = jest.fn();
  return {
    __esModule: true,
    default: new Proxy({ getContracts } as any, {
      get: (target, key) => (key in target ? target[key] : () => new Promise(() => {})),
    }),
  };
});

const getContracts = (ApiService as any).getContracts as jest.Mock;

let lastLocation: any = null;
const Where: React.FC = () => {
  lastLocation = useLocation();
  return null;
};

const contract = {
  id: 'k-1',
  contract_number: 'TH-TEST-0001',
  company: 'co-1',
  company_name: 'Fixture Resort',
  contract_type: 'Annual',
  status: 'Sent',
  start_date: '2026-01-01',
  end_date: '2026-12-31',
  value: 1000,
  currency: 'THB',
  auto_renew: false,
};

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Where />
      <Routes>
        <Route path="/contracts" element={<Contracts />} />
        <Route path="/contracts/:id" element={<div>contract page</div>} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  getContracts.mockReset();
  getContracts.mockResolvedValue({ results: [contract], count: 60 });
});

it('reads search, filters, sort and page from the address', async () => {
  renderAt('/contracts?q=fixture&status=Sent&type=Annual&sort=end_date&page=2&size=50');
  await waitFor(() => expect(getContracts).toHaveBeenCalled());
  expect(getContracts).toHaveBeenLastCalledWith({
    page: 2,
    page_size: 50,
    ordering: 'end_date',
    search: 'fixture',
    status: 'Sent',
    contract_type: 'Annual',
  });
});

it('typing a search updates the address and goes back to page 1', async () => {
  renderAt('/contracts?status=Sent&page=3');
  fireEvent.change(await screen.findByPlaceholderText(/search by contract number/i), { target: { value: 'lumen' } });
  await waitFor(() => expect(lastLocation.search).toContain('q=lumen'));
  expect(lastLocation.search).toContain('status=Sent');
  expect(lastLocation.search).not.toContain('page=');
});

it('opening a contract passes the list view along for the way back', async () => {
  renderAt('/contracts?status=Sent&page=2');
  fireEvent.click(await screen.findByText('TH-TEST-0001'));
  await waitFor(() => expect(lastLocation.pathname).toBe('/contracts/k-1'));
  expect(lastLocation.state).toEqual({ listSearch: 'status=Sent&page=2' });
});
