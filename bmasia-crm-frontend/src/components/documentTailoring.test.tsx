import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import InvoiceForm from './InvoiceForm';
import ContractForm from './ContractForm';
import ApiService from '../services/api';
import { Company, Contract, Invoice } from '../types';

jest.mock('../services/api', () => ({
  __esModule: true,
  default: {
    getCompaniesSimple: jest.fn(),
    getMasterAgreements: jest.fn(),
    getContractTemplates: jest.fn(),
    getNextInvoiceNumber: jest.fn(),
    updateInvoice: jest.fn(),
    updateContract: jest.fn(),
    createContract: jest.fn(),
  },
}));

const companies = [{
  id: 'hk-customer', name: 'Hong Kong Test Customer', country: 'Hong Kong', billing_entity: 'BMAsia Limited',
}] as Company[];

beforeEach(() => {
  jest.clearAllMocks();
  (ApiService.getCompaniesSimple as jest.Mock).mockResolvedValue(companies);
  (ApiService.getMasterAgreements as jest.Mock).mockResolvedValue([]);
  (ApiService.getContractTemplates as jest.Mock).mockResolvedValue({ results: [] });
  (ApiService.getNextInvoiceNumber as jest.Mock).mockResolvedValue('INV-TH-TEST');
});

async function selectIssuer(entity: string) {
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Issued by (this document)' }));
  fireEvent.click(await screen.findByRole('option', { name: entity }));
}

test('invoice can use Thailand issuer in USD for a Hong Kong customer and retains tailored payment text', async () => {
  const invoice = {
    id: 'inv-1', invoice_number: 'INV-TEST', company: 'hk-customer', contract: null,
    issue_date: '2026-09-09', due_date: '2026-10-09', currency: 'USD', billing_entity: '',
    payment_terms: 'Net 30', payment_terms_text: 'Agreed custom payment instructions.',
    line_items: [{ product_service: 'Beat Breeze', description: 'Lobby', quantity: 1, unit_price: 260, tax_rate: 0, total: 260 }],
  } as Invoice;
  (ApiService.updateInvoice as jest.Mock).mockResolvedValue(invoice);
  render(<InvoiceForm open onClose={jest.fn()} onSave={jest.fn()} invoice={invoice} mode="edit" companies={companies} contracts={[]} />);
  await selectIssuer('BMAsia (Thailand) Co., Ltd.');
  expect(screen.getByRole('combobox', { name: 'Currency' }).textContent).toBe('USD');
  expect((screen.getByRole('textbox', { name: 'Payment Terms (shown on PDF)' }) as HTMLInputElement).value).toBe('Agreed custom payment instructions.');
  fireEvent.click(screen.getByRole('button', { name: /update invoice/i }));
  await waitFor(() => expect(ApiService.updateInvoice).toHaveBeenCalledWith('inv-1', expect.objectContaining({
    company: 'hk-customer', billing_entity: 'BMAsia (Thailand) Co., Ltd.', currency: 'USD',
    payment_terms_text: 'Agreed custom payment instructions.',
  })));
});

test('contract exposes all tailoring fields without requiring a named template and preserves saved wording', async () => {
  const contract = {
    id: 'contract-1', company: 'hk-customer', contract_number: 'CT-TEST', contract_type: 'Annual',
    status: 'Draft', start_date: '2026-10-01', end_date: '2027-09-30', value: 260, currency: 'USD',
    auto_renew: false, renewal_period_months: 12, billing_frequency: 'Annually', discount_percentage: 0,
    preamble_custom: 'Agreed preamble.', payment_custom: 'Agreed payment wording.', activation_custom: 'Agreed activation wording.',
    payment_schedule: '50% deposit, 50% on activation.', custom_terms: 'An agreed additional provision.',
    custom_service_items: [{ name: 'Remote onboarding', description: 'Agreed onboarding provision.' }],
    line_items: [{ product_service: 'Custom service', description: 'Onboarding', quantity: 1, unit_price: 260, tax_rate: 0, line_total: 260 }],
    service_locations: [{ id: 'loc-1', location_name: 'Lobby', platform: 'custom', custom_service_name: 'Custom service' }],
  } as unknown as Contract;
  (ApiService.updateContract as jest.Mock).mockResolvedValue(contract);
  render(<ContractForm open onClose={jest.fn()} onSave={jest.fn()} contract={contract} mode="edit" />);
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Contract starting point' }).textContent).toContain('BMAsia standard'));
  await selectIssuer('BMAsia (Thailand) Co., Ltd.');
  fireEvent.change(screen.getByRole('textbox', { name: 'Additional agreed terms (optional)' }), { target: { value: 'Revised agreed provision.' } });
  fireEvent.click(screen.getByRole('button', { name: /update contract/i }));
  await waitFor(() => expect(ApiService.updateContract).toHaveBeenCalledWith('contract-1', expect.objectContaining({
    preamble_template: null, billing_entity: 'BMAsia (Thailand) Co., Ltd.', currency: 'USD',
    preamble_custom: 'Agreed preamble.', payment_custom: 'Agreed payment wording.',
    activation_custom: 'Agreed activation wording.', payment_schedule: '50% deposit, 50% on activation.',
    custom_terms: 'Revised agreed provision.',
    custom_service_items: [{ name: 'Remote onboarding', description: 'Agreed onboarding provision.' }],
  })));
  expect((ApiService.updateContract as jest.Mock).mock.calls[0][1]).not.toHaveProperty('line_items');
});
