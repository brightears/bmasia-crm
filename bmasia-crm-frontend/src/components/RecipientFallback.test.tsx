import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RecipientFallback, { noRecipientMessage, pickableContacts } from './RecipientFallback';
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
const MESSAGE = 'No contact of Lotus Bay Hotel is set to receive invoice emails.';
const refusal = (message = MESSAGE, kind = 'invoice') => ({
  response: { status: 422, data: { code: 'no_recipient', kind, company_id: 'co-1', message } },
});
const serverError = (status: number, error: string) => ({ response: { status, data: { error } } });

const contacts = [
  { id: 'c-1', name: 'Kim Accounts', email: 'kim@lotusbay.example.com', contact_type: 'Billing',
    is_active: true, receives_invoice_emails: false },
  { id: 'c-2', name: 'Pat Front', email: 'pat@lotusbay.example.com', contact_type: 'Other',
    is_active: true, receives_invoice_emails: false },
  { id: 'c-3', name: 'Gone Person', email: 'gone@lotusbay.example.com', contact_type: 'Billing',
    is_active: false, receives_invoice_emails: false },
  { id: 'c-4', name: 'No Address', email: '', contact_type: 'Other', is_active: true },
];

const invoice: any = {
  id: 'inv-1', invoice_number: 'INV-TEST-0001', company: 'co-1', company_name: 'Lotus Bay Hotel',
  contract_number: null, status: 'Draft', issue_date: '2026-11-01', due_date: '2026-12-01', amount: 100,
  tax_amount: 0, discount_amount: 0, total_amount: 100, currency: 'THB', line_items: [],
  is_overdue: false, days_overdue: 0,
};

beforeEach(() => {
  api.getCompany.mockReset();
  api.getCompany.mockResolvedValue({ contacts: [] });
  api.sendInvoice.mockReset();
  api.sendInvoiceEmail.mockReset();
});

const renderNotice = (onSent = jest.fn()) => render(
  <RecipientFallback
    open message={MESSAGE} documentType="invoice" documentId="inv-1" documentNumber="INV-TEST-0001"
    companyId="co-1" companyName="Lotus Bay Hotel" onClose={jest.fn()}
    onSendEmail={(data) => api.sendInvoiceEmail('inv-1', data)} onSent={onSent}
  />,
);

test('the notice is recognised by its code, never by its text', () => {
  expect(noRecipientMessage(refusal())).toBe(MESSAGE);
  // The same words without the code (for example a generic 500) are not the notice.
  expect(noRecipientMessage(serverError(500, MESSAGE))).toBeNull();
  expect(noRecipientMessage({ response: { status: 422, data: { code: 'other', message: MESSAGE } } })).toBeNull();
  expect(noRecipientMessage({ response: { status: 500, data: { code: 'no_recipient', message: MESSAGE } } }))
    .toBeNull();
  expect(noRecipientMessage(new Error('Network Error'))).toBeNull();
});

test('the picker offers active contacts with an address only', () => {
  expect(pickableContacts(contacts as any).map(c => c.id)).toEqual(['c-1', 'c-2']);
});

test('the notice links to the contacts and the picker sends the standard email to the picked contacts', async () => {
  api.getCompany.mockResolvedValue({ contacts });
  api.sendInvoiceEmail.mockResolvedValue(undefined);
  const onSent = jest.fn();
  renderNotice(onSent);
  expect(screen.getByText(MESSAGE)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Open Lotus Bay Hotel's contacts/ })).toHaveAttribute(
    'href', '/companies/co-1');

  fireEvent.click(screen.getByRole('button', { name: 'Choose recipients' }));
  await waitFor(() => expect(api.getCompany).toHaveBeenCalledWith('co-1'));
  expect(await screen.findByText(/The standard invoice email is sent/)).toBeInTheDocument();
  expect(screen.queryByLabelText(/Subject/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/Message/)).not.toBeInTheDocument();
  expect(screen.getByText(/Kim Accounts \(kim@/)).toBeInTheDocument();
  expect(screen.queryByText(/Gone Person/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Send Email/ }));
  await waitFor(() => expect(api.sendInvoiceEmail).toHaveBeenCalledTimes(1));
  const [, data] = api.sendInvoiceEmail.mock.calls[0];
  expect(data).toEqual({ recipients: ['kim@lotusbay.example.com'], cc: [] });  // no subject or body keys
  await waitFor(() => expect(onSent).toHaveBeenCalled());
});

test('a failed picker send shows the fixed message, not the server text', async () => {
  api.getCompany.mockResolvedValue({ contacts });
  api.sendInvoiceEmail.mockRejectedValue(serverError(500, 'Failed to send invoice: 535 smtp.internal.example'));
  renderNotice();
  fireEvent.click(screen.getByRole('button', { name: 'Choose recipients' }));
  fireEvent.click(await screen.findByRole('button', { name: /Send Email/ }));
  expect(await screen.findByText('Failed to send invoice')).toBeInTheDocument();
  expect(screen.queryByText(/smtp.internal/)).not.toBeInTheDocument();
});

test('with no active contact the notice says so and offers no empty picker', async () => {
  api.getCompany.mockResolvedValue({ contacts: [contacts[2]] });
  renderNotice();
  fireEvent.click(screen.getByRole('button', { name: 'Choose recipients' }));
  expect(await screen.findByText(/no active contact with an email address/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Send Email/ })).not.toBeInTheDocument();
});

test('an invoice send that finds nobody opens the notice instead of a generic failure', async () => {
  api.sendInvoice.mockRejectedValue(refusal());
  render(<InvoiceDetail open invoice={invoice} onClose={jest.fn()} onInvoiceUpdate={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: /Send via Email/i }));
  expect(await screen.findByText(MESSAGE)).toBeInTheDocument();
  expect(screen.queryByText('Failed to send invoice')).not.toBeInTheDocument();
});

test('any other failed invoice send shows the fixed message, not the server text', async () => {
  api.sendInvoice.mockRejectedValue(serverError(500, 'Failed to generate PDF: /srv/app/secret_path.py line 42'));
  render(<InvoiceDetail open invoice={invoice} onClose={jest.fn()} onInvoiceUpdate={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: /Send via Email/i }));
  expect(await screen.findByText('Failed to send invoice')).toBeInTheDocument();
  expect(screen.queryByText(/secret_path/)).not.toBeInTheDocument();
});

test('the quote Send button without a dialog opens the same notice', async () => {
  const quoteMessage = 'No contact of Lotus Bay Hotel is set to receive quote emails.';
  const quote: any = {
    id: 'q-1', quote_number: 'Q-TEST-0001', company: 'co-1', company_name: 'Lotus Bay Hotel', status: 'Draft',
    currency: 'THB', subtotal: 100, tax_amount: 0, discount_amount: 0, total_value: 100, line_items: [],
    activities: [], valid_from: '2026-11-01', valid_until: '2026-12-01',
  };
  api.getQuote.mockResolvedValue(quote);
  api.sendQuote.mockRejectedValue(refusal(quoteMessage, 'quote'));
  render(
    <MemoryRouter><QuoteDetail open quote={quote} onClose={jest.fn()} onQuoteUpdate={jest.fn()} /></MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole('button', { name: /Send Quote/i }));
  expect(await screen.findByText(quoteMessage)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Open Lotus Bay Hotel's contacts/ })).toHaveAttribute(
    'href', '/companies/co-1');
  expect(screen.queryByText('Failed to send quote')).not.toBeInTheDocument();
});

test('any other failed quote send shows the fixed message', async () => {
  const quote: any = {
    id: 'q-2', quote_number: 'Q-TEST-0002', company: 'co-1', company_name: 'Lotus Bay Hotel', status: 'Draft',
    currency: 'THB', subtotal: 100, tax_amount: 0, discount_amount: 0, total_value: 100, line_items: [],
    activities: [], valid_from: '2026-11-01', valid_until: '2026-12-01',
  };
  api.getQuote.mockResolvedValue(quote);
  api.sendQuote.mockRejectedValue(serverError(500, 'Failed to send quote to any recipients. Errors: 550 x'));
  render(
    <MemoryRouter><QuoteDetail open quote={quote} onClose={jest.fn()} onQuoteUpdate={jest.fn()} /></MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole('button', { name: /Send Quote/i }));
  expect(await screen.findByText('Failed to send quote')).toBeInTheDocument();
  expect(screen.queryByText(/Errors: 550/)).not.toBeInTheDocument();
});
