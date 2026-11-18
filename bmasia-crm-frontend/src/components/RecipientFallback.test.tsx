import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RecipientFallback, { noRecipientMessage, sendErrorMessage } from './RecipientFallback';
import InvoiceDetail from './InvoiceDetail';
import QuoteDetail from './QuoteDetail';
import ApiService from '../services/api';

jest.mock('../services/api', () => {
  const calls: Record<string, any> = {
    getEmailLogs: () => Promise.resolve([]),
    getCompany: jest.fn(),
    sendInvoice: jest.fn(),
    sendInvoiceEmail: jest.fn(),
    getQuote: jest.fn(),
    sendQuote: jest.fn(),
  };
  return {
    __esModule: true,
    default: new Proxy(calls, {
      get: (target, key) => (key in target ? target[key as string] : () => new Promise(() => {})),
    }),
  };
});

const api = ApiService as any;
const MESSAGE = 'No contact of Lotus Bay Hotel is set to receive invoice emails. '
  + 'Choose the recipients, or switch the email setting on for a contact.';
const serverError = (error: string) => ({ response: { data: { error } } });

const contacts = [
  { id: 'c-1', name: 'Kim Accounts', email: 'kim@lotusbay.example.com', contact_type: 'Billing',
    receives_invoice_emails: false },
  { id: 'c-2', name: 'Pat Front', email: 'pat@lotusbay.example.com', contact_type: 'Other',
    receives_invoice_emails: false },
];

beforeEach(() => {
  api.getCompany.mockReset();
  api.getCompany.mockResolvedValue({ contacts: [] });
  api.sendInvoice.mockReset();
  api.sendInvoiceEmail.mockReset();
});

test('the server message is recognised only when no contact is set to receive the email', () => {
  expect(noRecipientMessage(serverError(MESSAGE))).toBe(MESSAGE);
  expect(noRecipientMessage(serverError('Failed to generate PDF'))).toBeNull();
  expect(noRecipientMessage(new Error('Network Error'))).toBeNull();
  expect(sendErrorMessage(serverError('SMTP refused'), 'Failed to send invoice')).toBe('SMTP refused');
  expect(sendErrorMessage(new Error('x'), 'Failed to send invoice')).toBe('Failed to send invoice');
});

test('the notice shows the message, links to the contacts and lets the user pick recipients', async () => {
  api.getCompany.mockResolvedValue({ contacts });
  api.sendInvoiceEmail.mockResolvedValue(undefined);
  const onSent = jest.fn();
  render(
    <RecipientFallback
      open message={MESSAGE} documentType="invoice" documentId="inv-1" documentNumber="INV-TEST-0001"
      companyId="co-1" companyName="Lotus Bay Hotel" onClose={jest.fn()}
      onSendEmail={(data) => api.sendInvoiceEmail('inv-1', data)} onSent={onSent}
    />,
  );
  expect(screen.getByText(MESSAGE)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Open Lotus Bay Hotel's contacts/ })).toHaveAttribute(
    'href', '/companies/co-1');

  fireEvent.click(screen.getByRole('button', { name: 'Choose recipients' }));
  await waitFor(() => expect(api.getCompany).toHaveBeenCalledWith('co-1'));
  fireEvent.click(await screen.findByRole('button', { name: /Send/ }));
  await waitFor(() => expect(api.sendInvoiceEmail).toHaveBeenCalled());
  const [, data] = api.sendInvoiceEmail.mock.calls[0];
  expect(data.recipients).toEqual(['kim@lotusbay.example.com']);
  await waitFor(() => expect(onSent).toHaveBeenCalled());
});

test('an invoice send that finds nobody opens the notice instead of a generic failure', async () => {
  api.sendInvoice.mockRejectedValue(serverError(MESSAGE));
  const invoice: any = {
    id: 'inv-1', invoice_number: 'INV-TEST-0001', company: 'co-1', company_name: 'Lotus Bay Hotel',
    contract_number: null, status: 'Draft', issue_date: '2026-11-01', due_date: '2026-12-01', amount: 100,
    tax_amount: 0, discount_amount: 0, total_amount: 100, currency: 'THB', line_items: [],
    is_overdue: false, days_overdue: 0,
  };
  render(<InvoiceDetail open invoice={invoice} onClose={jest.fn()} onInvoiceUpdate={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: /Send via Email/i }));
  expect(await screen.findByText(MESSAGE)).toBeInTheDocument();
  expect(screen.queryByText('Failed to send invoice')).not.toBeInTheDocument();
});

test('the quote Send button without a dialog opens the same notice', async () => {
  const quoteMessage = 'No contact of Lotus Bay Hotel is set to receive quote emails. '
    + 'Choose the recipients, or switch the email setting on for a contact.';
  const quote: any = {
    id: 'q-1', quote_number: 'Q-TEST-0001', company: 'co-1', company_name: 'Lotus Bay Hotel', status: 'Draft',
    currency: 'THB', subtotal: 100, tax_amount: 0, discount_amount: 0, total_value: 100, line_items: [],
    activities: [], valid_from: '2026-11-01', valid_until: '2026-12-01',
  };
  api.getQuote.mockResolvedValue(quote);
  api.sendQuote.mockRejectedValue(serverError(quoteMessage));
  render(
    <MemoryRouter><QuoteDetail open quote={quote} onClose={jest.fn()} onQuoteUpdate={jest.fn()} /></MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole('button', { name: /Send Quote/i }));
  expect(await screen.findByText(quoteMessage)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Open Lotus Bay Hotel's contacts/ })).toHaveAttribute(
    'href', '/companies/co-1');
  expect(screen.queryByText('Failed to send quote')).not.toBeInTheDocument();
});
