import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import InvoiceForm from './InvoiceForm';
import ApiService from '../services/api';

jest.mock('react-quill-new', () => ({ __esModule: true, default: () => null }));
jest.mock('../services/api', () => {
  const calls: Record<string, any> = {
    updateInvoice: jest.fn(),
    getNextInvoiceNumber: () => Promise.resolve('INV-HK-2026-0009'),
  };
  return {
    __esModule: true,
    default: new Proxy(calls, {
      get: (target, key) => (key in target ? target[key as string] : () => new Promise(() => {})),
    }),
  };
});

const api = ApiService as any;
const company: any = { id: 'co-1', name: 'Status Test Resort', billing_entity: 'BMAsia Limited', country: 'Hong Kong' };

const paidInvoice: any = {
  id: 'inv-1',
  invoice_number: 'INV-HK-2026-0001',
  company: 'co-1',
  company_name: 'Status Test Resort',
  contract: null,
  status: 'Paid',
  receipt_number: 'REC-HK-2026-0001',
  paid_date: '2026-11-10',
  issue_date: '2026-11-01',
  due_date: '2026-12-01',
  amount: 100,
  tax_amount: 0,
  discount_amount: 0,
  total_amount: 100,
  currency: 'USD',
  billing_entity: '',
  payment_terms: 'Net 30',
  line_items: [{ description: 'Music service', product_service: 'Music service', quantity: 1, unit_price: 100,
    tax_rate: 0, total: 100 }],
};

beforeEach(() => {
  api.updateInvoice.mockReset();
});

test('saving an edit sends no status, so a paid invoice stays paid', async () => {
  api.updateInvoice.mockResolvedValue({ ...paidInvoice });
  const onSave = jest.fn();
  render(
    <InvoiceForm open mode="edit" invoice={paidInvoice} companies={[company]} contracts={[]}
      onClose={jest.fn()} onSave={onSave} />,
  );
  fireEvent.click(await screen.findByRole('button', { name: 'Update Invoice' }));
  await waitFor(() => expect(api.updateInvoice).toHaveBeenCalled());
  const [id, payload] = api.updateInvoice.mock.calls[0];
  expect(id).toBe('inv-1');
  expect(payload).not.toHaveProperty('status');
});
