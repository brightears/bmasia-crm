import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import Opportunities from './Opportunities';
import ApiService from '../services/api';

jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('../services/api', () => {
  const getOpportunities = jest.fn();
  const getUsers = () => Promise.resolve({ results: [], count: 0 });
  return {
    __esModule: true,
    default: new Proxy({ getOpportunities, getUsers } as any, {
      get: (target, key) => (key in target ? target[key] : () => new Promise(() => {})),
    }),
  };
});

const getOpportunities = (ApiService as any).getOpportunities as jest.Mock;

const opp = (i: number, stage = 'Contacted', value = '1000.00') => ({
  id: `o-${i}`,
  name: `Fixture deal ${i}`,
  company: 'co-1',
  company_name: 'Fixture Resort',
  stage,
  expected_value: value,
  weighted_value: '100.00',
  probability: 10,
  service_type: 'soundtrack',
  is_active: true,
  created_at: '2026-11-01T00:00:00Z',
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
        <Route path="/opportunities" element={<Opportunities />} />
        <Route path="/opportunities/:id" element={<div>opportunity page</div>} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  getOpportunities.mockReset();
  getOpportunities.mockImplementation((params: any) =>
    Promise.resolve(
      params.page_size === 1000
        ? { results: Array.from({ length: 30 }, (_, i) => opp(i)), count: 30 }
        : { results: [opp(1), opp(2)], count: 30 }
    )
  );
});

it('the pipeline loads its own list (up to 1000) with the same filters, so totals cover more than the table page', async () => {
  renderAt('/opportunities?q=fixture&stage=Contacted&page=2');
  await waitFor(() => expect(getOpportunities).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('tab', { name: /pipeline/i }));
  await waitFor(() => expect(getOpportunities).toHaveBeenCalledTimes(2));
  expect(getOpportunities).toHaveBeenLastCalledWith({
    page: 1,
    page_size: 1000,
    ordering: '-created_at',
    company__billing_entity: 'BMAsia Limited',
    search: 'fixture',
    stage: 'Contacted',
  });
  // 30 deals of 1,000 each, not the table page's 2
  expect(await screen.findByText('USD 30,000')).toBeInTheDocument();
  expect(screen.queryByText(/the board shows the first/i)).toBeNull();
});

it('says so on the board when the server has more than the limit', async () => {
  getOpportunities.mockImplementation((params: any) =>
    Promise.resolve(
      params.page_size === 1000
        ? { results: Array.from({ length: 3 }, (_, i) => opp(i)), count: 1200 }
        : { results: [opp(1)], count: 1200 }
    )
  );
  renderAt('/opportunities');
  await waitFor(() => expect(getOpportunities).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('tab', { name: /pipeline/i }));
  expect(await screen.findByText(/the board shows the first 3 of 1,200 matching opportunities/i)).toBeInTheDocument();
});

it('opening an opportunity passes the list view along for the breadcrumb', async () => {
  renderAt('/opportunities?stage=Contacted&page=2');
  fireEvent.click(await screen.findByText('Fixture deal 1'));
  await waitFor(() => expect(lastLocation.pathname).toBe('/opportunities/o-1'));
  expect(lastLocation.state).toEqual({ listSearch: 'stage=Contacted&page=2' });
});
