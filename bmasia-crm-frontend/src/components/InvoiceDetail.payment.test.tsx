import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import InvoiceDetail from './InvoiceDetail';
import ApiService from '../services/api';

let mockRole = 'Admin';
jest.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 'u-1', role: mockRole, is_active: true } }) }));

jest.mock('../services/api', () => {
  const calls: Record<string, any> = {
    getEmailLogs: () => Promise.resolve([]),
    getCompany: () => Promise.resolve({ contacts: [] }),
    markInvoicePaid: jest.fn(),
  };
  return {
    __esModule: true,
    default: new Proxy(calls, {
      get: (target, key) => (key in target ? target[key as string] : () => new Promise(() => {})),
    }),
  };
});

const api = ApiService as any;

const invoice = (over: any = {}): any => ({
  id: 'inv-1',
  invoice_number: 'INV-TEST-0001',
  company: 'co-1',
  company_name: 'Lotus Bay Hotel',
  contract_number: 'TH-CT26001',
  status: 'Sent',
  issue_date: '2026-11-01',
  due_date: '2026-12-01',
  amount: 108000,
  tax_amount: 0,
  discount_amount: 0,
  total_amount: 108000,
  currency: 'THB',
  line_items: [],
  is_overdue: false,
  days_overdue: 0,
  ...over,
});

test('the broken "Add Payment" button and empty payment history are gone', () => {
  render(<InvoiceDetail open invoice={invoice()} onClose={jest.fn()} onInvoiceUpdate={jest.fn()} />);
  expect(screen.queryByRole('button', { name: /Add Payment/i })).not.toBeInTheDocument();
  expect(screen.queryByText('Payment History')).not.toBeInTheDocument();
  expect(screen.getAllByText('THB 108,000').length).toBeGreaterThan(0);
});

test('"Mark as Paid" opens the record-payment dialog instead of posting at once', async () => {
  const onInvoiceUpdate = jest.fn();
  api.markInvoicePaid.mockResolvedValue({
    message: 'Invoice marked as paid', receipt_number: 'REC-TH-2026-0001',
    paid_date: '2026-11-10', receipt_email_status: 'not_requested',
  });
  render(<InvoiceDetail open invoice={invoice()} onClose={jest.fn()} onInvoiceUpdate={onInvoiceUpdate} />);

  fireEvent.click(screen.getByRole('button', { name: 'Mark as Paid' }));
  expect(api.markInvoicePaid).not.toHaveBeenCalled();
  expect(screen.getByRole('dialog', { name: 'Record payment' })).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Record without sending' }));
  await waitFor(() => expect(onInvoiceUpdate).toHaveBeenCalled());
  expect(api.markInvoicePaid.mock.calls[0][1].send_receipt).toBe(false);
  expect(await screen.findByText('Payment recorded. Receipt REC-TH-2026-0001. No email was sent.')).toBeInTheDocument();
});

test('a paid invoice shows its payment reference', () => {
  render(
    <InvoiceDetail
      open
      invoice={invoice({ status: 'Paid', paid_date: '2026-11-10', receipt_number: 'REC-TH-2026-0001',
        payment_method: 'Bank Transfer', transaction_id: 'BANK-REF-1' })}
      onClose={jest.fn()}
      onInvoiceUpdate={jest.fn()}
    />,
  );
  expect(screen.getByText('BANK-REF-1')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Mark as Paid' })).not.toBeInTheDocument();
});

test('a paid invoice without a receipt offers "Issue Receipt"', () => {
  render(
    <InvoiceDetail open invoice={invoice({ status: 'Paid', paid_date: '2026-11-10', receipt_number: null })}
      onClose={jest.fn()} onInvoiceUpdate={jest.fn()} />,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Issue Receipt' }));
  expect(screen.getByRole('dialog', { name: 'Issue receipt' })).toBeInTheDocument();
});

test('Sales sees the invoice but not "Mark as Paid" or "Issue Receipt"', () => {
  mockRole = 'Sales';
  const { unmount } = render(<InvoiceDetail open invoice={invoice()} onClose={jest.fn()} onInvoiceUpdate={jest.fn()} />);
  expect(screen.getAllByText('THB 108,000').length).toBeGreaterThan(0);
  expect(screen.queryByRole('button', { name: 'Mark as Paid' })).not.toBeInTheDocument();
  unmount();
  render(
    <InvoiceDetail open invoice={invoice({ status: 'Paid', paid_date: '2026-11-10', receipt_number: null })}
      onClose={jest.fn()} onInvoiceUpdate={jest.fn()} />,
  );
  expect(screen.queryByRole('button', { name: 'Issue Receipt' })).not.toBeInTheDocument();
  mockRole = 'Admin';
});
