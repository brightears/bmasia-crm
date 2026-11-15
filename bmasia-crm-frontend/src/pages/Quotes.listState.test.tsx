import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import Quotes from './Quotes';
import ApiService from '../services/api';

jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('../services/api', () => {
  const getQuotes = jest.fn();
  const getCompaniesSimple = () => Promise.resolve([]);
  return {
    __esModule: true,
    default: new Proxy({ getQuotes, getCompaniesSimple } as any, {
      get: (target, key) => (key in target ? target[key] : () => new Promise(() => {})),
    }),
  };
});

const getQuotes = (ApiService as any).getQuotes as jest.Mock;

let lastLocation: any = null;
const Where: React.FC = () => {
  lastLocation = useLocation();
  return null;
};

const quote = {
  id: 'q-1',
  quote_number: 'Q-TEST-0001',
  company: 'co-1',
  company_name: 'Fixture Resort',
  status: 'Sent',
  total_value: 1000,
  currency: 'THB',
  valid_until: '2026-12-31',
  created_at: '2026-11-01T00:00:00Z',
};

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Where />
      <Routes>
        <Route path="/quotes" element={<Quotes />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  getQuotes.mockReset();
  getQuotes.mockResolvedValue({ results: [quote], count: 60 });
});

it('reads search, status, sort and page from the address', async () => {
  renderAt('/quotes?q=fixture&status=Sent&sort=valid_until&page=2&size=50');
  await waitFor(() => expect(getQuotes).toHaveBeenCalled());
  expect(getQuotes).toHaveBeenLastCalledWith({
    page: 2,
    page_size: 50,
    ordering: 'valid_until',
    search: 'fixture',
    status: 'Sent',
  });
});

it('typing a search updates the address and goes back to page 1', async () => {
  renderAt('/quotes?status=Sent&page=3');
  fireEvent.change(await screen.findByPlaceholderText(/search by quote number/i), { target: { value: 'lumen' } });
  await waitFor(() => expect(lastLocation.search).toContain('q=lumen'));
  expect(lastLocation.search).toContain('status=Sent');
  expect(lastLocation.search).not.toContain('page=');
});
