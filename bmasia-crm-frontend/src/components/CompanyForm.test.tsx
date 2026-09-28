import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CompanyForm from './CompanyForm';
import ApiService from '../services/api';
import { Company } from '../types';

jest.mock('../services/api', () => ({
  __esModule: true,
  default: {
    getCompanies: jest.fn(),
    updateCompany: jest.fn(),
    createCompany: jest.fn(),
  },
}));

const joali: Company = {
  id: 'company-joali',
  name: 'Joali Being',
  legal_entity_name: 'JOALI BEING BODUFUSHI',
  country: 'Maldives',
  industry: 'Hotels',
  billing_entity: 'BMAsia Limited',
  location_count: 1,
  music_zone_count: 1,
  avg_zones_per_location: 1,
  total_contract_value: 0,
  is_active: true,
  contacts: [],
  subscription_plans: [],
  active_subscription_plans: [],
  subscription_summary: '',
  opportunities_count: 0,
  active_contracts_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

beforeEach(() => {
  jest.clearAllMocks();
  (ApiService.getCompanies as jest.Mock).mockResolvedValue({ results: [] });
});

test('keeps Maldives visible and preserves the accepted empty optional parent', async () => {
  (ApiService.updateCompany as jest.Mock).mockResolvedValue(joali);
  render(<CompanyForm open company={joali} onClose={jest.fn()} onSave={jest.fn()} />);

  await waitFor(() => expect(ApiService.getCompanies).toHaveBeenCalled());
  expect(screen.getByText('Maldives')).toBeTruthy();

  fireEvent.click(screen.getByRole('button', { name: /update company/i }));
  await waitFor(() => expect(ApiService.updateCompany).toHaveBeenCalledWith(
    'company-joali',
    expect.objectContaining({ country: 'Maldives', parent_company: '' }),
  ));
});

test('keeps an existing country that is outside the curated menu visible', async () => {
  const legacyCountryCompany = { ...joali, country: 'Réunion' };
  render(<CompanyForm open company={legacyCountryCompany} onClose={jest.fn()} onSave={jest.fn()} />);

  await waitFor(() => expect(ApiService.getCompanies).toHaveBeenCalled());
  expect(screen.getByText('Réunion')).toBeTruthy();
});

test('allows unrelated edits to preserve legacy blank country and industry', async () => {
  const legacyCompany = { ...joali, country: '', industry: '' };
  (ApiService.updateCompany as jest.Mock).mockResolvedValue(legacyCompany);
  render(<CompanyForm open company={legacyCompany} onClose={jest.fn()} onSave={jest.fn()} />);

  await waitFor(() => expect(ApiService.getCompanies).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: /update company/i }));

  await waitFor(() => expect(ApiService.updateCompany).toHaveBeenCalledWith(
    'company-joali',
    expect.objectContaining({ country: '', industry: '' }),
  ));
});

test('still requires country and industry for a new company', async () => {
  render(<CompanyForm open company={null} onClose={jest.fn()} onSave={jest.fn()} />);

  await waitFor(() => expect(ApiService.getCompanies).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: /create company/i }));

  expect(await screen.findByText('Country is required')).toBeTruthy();
  expect(screen.getByText('Industry is required')).toBeTruthy();
  expect(ApiService.createCompany).not.toHaveBeenCalled();
});

test('shows server-wide and parent-company validation errors instead of a generic failure', async () => {
  (ApiService.updateCompany as jest.Mock).mockRejectedValue({
    response: {
      data: {
        detail: 'Company could not be updated.',
        parent_company: ['Select a valid corporate parent.'],
      },
    },
  });
  render(<CompanyForm open company={joali} onClose={jest.fn()} onSave={jest.fn()} />);

  await waitFor(() => expect(ApiService.getCompanies).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: /update company/i }));

  expect(await screen.findByText('Company could not be updated.')).toBeTruthy();
  expect(screen.getByText('Select a valid corporate parent.')).toBeTruthy();
});

test('does not render an HTML error response as the save error', async () => {
  (ApiService.updateCompany as jest.Mock).mockRejectedValue({
    response: { data: '<!doctype html><html><body>upstream failure</body></html>' },
  });
  render(<CompanyForm open company={joali} onClose={jest.fn()} onSave={jest.fn()} />);

  await waitFor(() => expect(ApiService.getCompanies).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: /update company/i }));

  expect(await screen.findByText('Unable to save company. The server returned an unexpected response.')).toBeTruthy();
  expect(screen.queryByText(/upstream failure/i)).toBeNull();
});
