import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import MarkPaidDialog, { bangkokToday, describeMarkPaidResult, earliestPaymentDate } from './MarkPaidDialog';
import ApiService from '../services/api';

jest.mock('../services/api', () => ({
  __esModule: true,
  default: { markInvoicePaid: jest.fn() },
}));

const api = ApiService as unknown as { markInvoicePaid: jest.Mock };

const invoice: any = {
  id: 'inv-1',
  invoice_number: 'INV-TEST-0001',
  company_name: 'Lotus Bay Hotel',
  total_amount: 108000,
  currency: 'THB',
  status: 'Sent',
  issue_date: '2026-11-01',
};

const result = {
  message: 'Invoice marked as paid',
  receipt_number: 'REC-TH-2026-0001',
  paid_date: '2026-11-10',
  receipt_email_status: 'not_requested',
};

const openDialog = (onRecorded = jest.fn()) => {
  render(<MarkPaidDialog open invoice={invoice} onClose={jest.fn()} onRecorded={onRecorded} />);
  return onRecorded;
};

beforeEach(() => {
  api.markInvoicePaid.mockReset();
});

test('shows the amount in the invoice currency and says what each button does', () => {
  openDialog();
  expect(screen.getByText(/THB 108,000/)).toBeInTheDocument();
  expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  expect(screen.getByText(/also emails the receipt to the/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Record without sending' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Record and email receipt' })).toBeInTheDocument();
  expect(screen.getByLabelText(/Payment date/)).toHaveValue(bangkokToday());
});

test('"Record without sending" asks the server not to email', async () => {
  api.markInvoicePaid.mockResolvedValue(result);
  const onRecorded = openDialog();
  fireEvent.change(screen.getByLabelText(/Payment date/), { target: { value: '2026-11-10' } });
  fireEvent.change(screen.getByLabelText('Payment reference'), { target: { value: 'BANK-REF-1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Record without sending' }));

  await waitFor(() => expect(onRecorded).toHaveBeenCalledWith(result));
  expect(api.markInvoicePaid).toHaveBeenCalledWith('inv-1', {
    paid_date: '2026-11-10',
    send_receipt: false,
    payment_method: undefined,
    transaction_id: 'BANK-REF-1',
    notes: undefined,
  });
});

test('"Record and email receipt" asks the server to email', async () => {
  api.markInvoicePaid.mockResolvedValue({ ...result, receipt_email_status: 'sent' });
  const onRecorded = openDialog();
  fireEvent.click(screen.getByRole('button', { name: 'Record and email receipt' }));
  await waitFor(() => expect(onRecorded).toHaveBeenCalled());
  expect(api.markInvoicePaid.mock.calls[0][1].send_receipt).toBe(true);
});

test('a double click records the payment once', async () => {
  let resolve: (value: any) => void = () => {};
  api.markInvoicePaid.mockReturnValue(new Promise((r) => { resolve = r; }));
  openDialog();
  const button = screen.getByRole('button', { name: 'Record and email receipt' });
  fireEvent.click(button);
  fireEvent.click(button);
  fireEvent.click(screen.getByRole('button', { name: 'Record without sending' }));
  expect(api.markInvoicePaid).toHaveBeenCalledTimes(1);
  expect(button).toBeDisabled();
  resolve(result);
  await waitFor(() => expect(button).not.toBeDisabled());
});

test('an invoice that is already paid shows its receipt and that nothing was sent', async () => {
  api.markInvoicePaid.mockRejectedValue({
    response: {
      status: 409,
      data: { error: 'This invoice is already marked as paid.', code: 'already_paid', receipt_number: 'REC-TH-2026-0001' },
    },
  });
  const onRecorded = openDialog();
  fireEvent.click(screen.getByRole('button', { name: 'Record and email receipt' }));
  expect(await screen.findByText(/already marked as paid\. \(receipt REC-TH-2026-0001\) Nothing was changed or sent\./))
    .toBeInTheDocument();
  expect(onRecorded).not.toHaveBeenCalled();
});

test('a future payment date cannot be recorded', () => {
  openDialog();
  fireEvent.change(screen.getByLabelText(/Payment date/), { target: { value: '2999-01-01' } });
  expect(screen.getByText('The payment date cannot be in the future (Bangkok date).')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Record without sending' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Record and email receipt' })).toBeDisabled();
});

test('describeMarkPaidResult says whether an email went out', () => {
  expect(describeMarkPaidResult(result)).toBe('Payment recorded. Receipt REC-TH-2026-0001. No email was sent.');
  expect(describeMarkPaidResult({ ...result, receipt_email_status: 'sent' }))
    .toBe('Payment recorded. Receipt REC-TH-2026-0001. The receipt was emailed to the customer.');
  expect(describeMarkPaidResult({ ...result, receipt_email_status: 'failed: No recipients found' }))
    .toMatch(/receipt email failed/);
});

test('"today" is the Bangkok date, which the server checks against', () => {
  // 23:30 in Bangkok on 18 Nov is already 00:30 on 19 Nov in Hong Kong.
  expect(bangkokToday(new Date('2026-11-18T16:30:00Z'))).toBe('2026-11-18');
  expect(bangkokToday(new Date('2026-12-31T17:30:00Z'))).toBe('2027-01-01');
});

test('the earliest payment date is a year before the issue date, and never before 2000', () => {
  expect(earliestPaymentDate('2026-11-01')).toBe('2025-10-31');
  expect(earliestPaymentDate('2000-03-01')).toBe('2000-01-01');
  expect(earliestPaymentDate(undefined)).toBe('2000-01-01');
});

test('a payment date before that cannot be recorded', () => {
  openDialog();
  fireEvent.change(screen.getByLabelText(/Payment date/), { target: { value: '2025-10-30' } });
  expect(screen.getByText('The payment date cannot be before 2025-10-31.')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Record without sending' })).toBeDisabled();
});

test('after a 409 the page is told to reload the invoice', async () => {
  api.markInvoicePaid.mockRejectedValue({ response: { status: 409, data: { error: 'Already paid.' } } });
  const onConflict = jest.fn();
  render(<MarkPaidDialog open invoice={invoice} onClose={jest.fn()} onRecorded={jest.fn()} onConflict={onConflict} />);
  fireEvent.click(screen.getByRole('button', { name: 'Record without sending' }));
  await waitFor(() => expect(onConflict).toHaveBeenCalledTimes(1));
});

test('a paid invoice without a receipt only gets its receipt, keeping its own payment date', async () => {
  api.markInvoicePaid.mockResolvedValue({ ...result, receipt_only: true, paid_date: '2026-11-02' });
  const onRecorded = jest.fn();
  render(
    <MarkPaidDialog open invoice={{ ...invoice, status: 'Paid', paid_date: '2026-11-02', receipt_number: null }}
      onClose={jest.fn()} onRecorded={onRecorded} />,
  );
  expect(screen.getByRole('dialog', { name: 'Issue receipt' })).toBeInTheDocument();
  expect(screen.getByText(/already marked paid but has no receipt number/)).toBeInTheDocument();
  expect(screen.getByLabelText(/Payment date/)).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Record without sending' }));
  await waitFor(() => expect(onRecorded).toHaveBeenCalled());
  expect(api.markInvoicePaid.mock.calls[0][1]).toMatchObject({ paid_date: undefined, send_receipt: false });
  expect(describeMarkPaidResult({ ...result, receipt_only: true })).toBe(
    'Receipt issued. Receipt REC-TH-2026-0001. No email was sent.');
});
