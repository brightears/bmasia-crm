import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ContractForm from './ContractForm';
import ApiService from '../services/api';
import { Contract } from '../types';

jest.mock('../services/api', () => ({
  __esModule: true,
  default: {
    getCompaniesSimple: jest.fn(),
    getMasterAgreements: jest.fn(),
    getContractTemplates: jest.fn(),
    getQuotes: jest.fn(),
    getQuote: jest.fn(),
    updateContract: jest.fn(),
    createContract: jest.fn(),
    uploadContractDocument: jest.fn(),
  },
}));

const company = { id: 'company-1', name: 'Fixture Hotel', country: 'Singapore', billing_entity: 'BMAsia Limited' };

// A contract whose service-location rows are not backed by any music line item (imported or back-filled).
const contract = {
  id: 'contract-1',
  company: 'company-1',
  company_name: 'Fixture Hotel',
  contract_number: 'TEST-0001',
  contract_type: 'Annual',
  status: 'Active',
  start_date: '2026-01-01',
  end_date: '2026-12-31',
  value: 900,
  discount_percentage: 0,
  tax_rate: 0,
  currency: 'USD',
  line_items: [],
  service_locations: [
    { id: 'row-a', location_name: 'Lobby', platform: 'soundtrack', sort_order: 0 },
    { id: 'row-b', location_name: 'Pool', platform: 'custom', custom_service_name: 'Beat Breeze', sort_order: 1 },
  ],
  contract_zones: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
} as unknown as Contract;

beforeEach(() => {
  jest.clearAllMocks();
  (ApiService.getCompaniesSimple as jest.Mock).mockResolvedValue([company]);
  (ApiService.getMasterAgreements as jest.Mock).mockResolvedValue([]);
  (ApiService.getContractTemplates as jest.Mock).mockResolvedValue({ results: [] });
  (ApiService.getQuotes as jest.Mock).mockResolvedValue({ results: [] });
  (ApiService.updateContract as jest.Mock).mockResolvedValue(contract);
});

test('opening and saving a contract without music line items leaves its service locations alone', async () => {
  render(<ContractForm open mode="edit" contract={contract} onClose={jest.fn()} onSave={jest.fn()} />);

  await waitFor(() => expect(ApiService.getCompaniesSimple).toHaveBeenCalled());
  expect(screen.getByDisplayValue('Lobby')).toBeTruthy();
  expect(screen.getByDisplayValue('Pool')).toBeTruthy();

  fireEvent.click(screen.getByRole('button', { name: /update contract/i }));
  await waitFor(() => expect(ApiService.updateContract).toHaveBeenCalled());

  const payload = (ApiService.updateContract as jest.Mock).mock.calls[0][1];
  expect(payload).not.toHaveProperty('service_locations');
  expect(payload).not.toHaveProperty('replace_service_locations');
  expect(payload).not.toHaveProperty('remove_service_location_ids');
});

test('renaming a saved location sends the full list by id and removes nothing', async () => {
  render(<ContractForm open mode="edit" contract={contract} onClose={jest.fn()} onSave={jest.fn()} />);
  await waitFor(() => expect(ApiService.getCompaniesSimple).toHaveBeenCalled());

  fireEvent.change(screen.getByDisplayValue('Lobby'), { target: { value: 'Front desk' } });
  fireEvent.click(screen.getByRole('button', { name: /update contract/i }));
  await waitFor(() => expect(ApiService.updateContract).toHaveBeenCalled());

  const payload = (ApiService.updateContract as jest.Mock).mock.calls[0][1];
  expect(payload.replace_service_locations).toBe(true);
  expect(payload.remove_service_location_ids).toEqual([]);
  expect(payload.service_locations).toEqual([
    { id: 'row-a', location_name: 'Front desk', platform: 'soundtrack', sort_order: 0 },
    { id: 'row-b', location_name: 'Pool', platform: 'custom', sort_order: 1, custom_service_name: 'Beat Breeze' },
  ]);
});
