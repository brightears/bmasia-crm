import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import MarkPaidDialog, { describeMarkPaidResult, localToday } from './MarkPaidDialog';
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
  expect(screen.getByLabelText(/Payment date/)).toHaveValue(localToday());
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
  expect(screen.getByText('The payment date cannot be in the future.')).toBeInTheDocument();
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

test('localToday uses the local calendar date', () => {
  expect(localToday(new Date(2026, 0, 1, 0, 30))).toBe('2026-01-01');
});
