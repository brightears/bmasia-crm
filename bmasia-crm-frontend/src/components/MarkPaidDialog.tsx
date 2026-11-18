import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import { Invoice } from '../types';
import ApiService, { MarkInvoicePaidResult } from '../services/api';
import { formatMoney } from '../theme';

export const PAYMENT_METHODS = ['Bank Transfer', 'Cash', 'Check', 'Credit Card', 'Online Payment', 'Other'];

/**
 * Today as YYYY-MM-DD on Bangkok's calendar, the date the server checks against
 * (the browser's own date can already be tomorrow, for example in Hong Kong after midnight).
 */
export const bangkokToday = (now: Date = new Date()): string =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Bangkok', year: 'numeric', month: '2-digit', day: '2-digit' })
    .format(now);

/**
 * The earliest payment date the server accepts: a year (366 days) before the invoice was
 * issued, and never before 2000 (crm_app/services/invoice_payments.py).
 */
export const earliestPaymentDate = (issueDate?: string | null): string => {
  const floor = '2000-01-01';
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(issueDate || '');
  if (!m) return floor;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) - 366));
  const iso = d.toISOString().slice(0, 10);
  return iso > floor ? iso : floor;
};

/** One line for the page after a payment is recorded. */
export const describeMarkPaidResult = (result: MarkInvoicePaidResult): string => {
  const receipt = result.receipt_number ? ` Receipt ${result.receipt_number}.` : '';
  const done = result.receipt_only ? 'Receipt issued.' : 'Payment recorded.';
  if (result.receipt_email_status === 'sent') {
    return `${done}${receipt} The receipt was emailed to the customer.`;
  }
  if (result.receipt_email_refusal?.code === 'no_recipient') {
    const reason = result.receipt_email_refusal.message.replace(/\.$/, '');
    return `${done}${receipt} The receipt was not emailed: ${reason}. Use Send Receipt to choose the recipients.`;
  }
  if (result.receipt_email_status?.startsWith('failed')) {
    return `${done}${receipt} The receipt email failed; use Send Receipt to try again.`;
  }
  return `${done}${receipt} No email was sent.`;
};

interface MarkPaidDialogProps {
  open: boolean;
  invoice: Invoice | null;
  onClose: () => void;
  onRecorded: (result: MarkInvoicePaidResult) => void;
  /** Called after a 409 (already paid elsewhere), so the page can reload the invoice. */
  onConflict?: () => void;
}

const MarkPaidDialog: React.FC<MarkPaidDialogProps> = ({ open, invoice, onClose, onRecorded, onConflict }) => {
  const [paidDate, setPaidDate] = useState(bangkokToday());
  const [paymentMethod, setPaymentMethod] = useState('');
  const [transactionId, setTransactionId] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const inFlight = useRef(false); // a second click before the re-render must not post again

  useEffect(() => {
    if (open) {
      setPaidDate(invoice?.paid_date || bangkokToday());
      setPaymentMethod(invoice?.payment_method || '');
      setTransactionId('');
      setNotes('');
      setError('');
    }
  }, [open, invoice]);

  if (!invoice) return null;

  // Paid already (set by another route) but without a receipt: this only issues the receipt.
  const receiptOnly = invoice.status === 'Paid' && !invoice.receipt_number;
  const keepsOwnDate = receiptOnly && Boolean(invoice.paid_date);
  const today = bangkokToday();
  const earliest = earliestPaymentDate(invoice.issue_date);
  const dateProblem = keepsOwnDate
    ? ''
    : !paidDate
      ? 'Enter the date the payment arrived.'
      : paidDate > today
        ? 'The payment date cannot be in the future (Bangkok date).'
        : paidDate < earliest
          ? `The payment date cannot be before ${earliest}.`
          : '';

  const record = async (sendReceipt: boolean) => {
    if (inFlight.current || dateProblem) return;
    inFlight.current = true;
    setSubmitting(true);
    setError('');
    try {
      const result = await ApiService.markInvoicePaid(invoice.id, {
        paid_date: keepsOwnDate ? undefined : paidDate,
        send_receipt: sendReceipt,
        payment_method: paymentMethod || undefined,
        transaction_id: transactionId.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onRecorded(result);
    } catch (err: any) {
      const data = err?.response?.data;
      if (err?.response?.status === 409) {
        const receipt = data?.receipt_number ? ` (receipt ${data.receipt_number})` : '';
        setError(`${data?.error || 'This invoice is already marked as paid.'}${receipt} Nothing was changed or sent.`);
        onConflict?.();
      } else if (data && typeof data === 'object' && !data.error) {
        setError(Object.values(data).flat().join(' ') || 'The payment could not be recorded.');
      } else {
        setError(data?.error || 'The payment could not be recorded.');
      }
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  };

  const close = () => {
    if (!submitting) onClose();
  };

  return (
    <Dialog open={open} onClose={close} maxWidth="sm" fullWidth aria-labelledby="mark-paid-title">
      <DialogTitle id="mark-paid-title">{receiptOnly ? 'Issue receipt' : 'Record payment'}</DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="body2">
            {invoice.invoice_number} · {invoice.company_name} · {formatMoney(invoice.total_amount, invoice.currency)}
          </Typography>

          {error && <Alert severity="error">{error}</Alert>}

          <TextField
            label="Payment date"
            type="date"
            value={paidDate}
            onChange={(e) => setPaidDate(e.target.value)}
            inputProps={{ max: today, min: earliest }}
            InputLabelProps={{ shrink: true }}
            disabled={keepsOwnDate}
            error={Boolean(dateProblem)}
            helperText={dateProblem || (keepsOwnDate
              ? 'The invoice keeps the payment date it already has.'
              : 'The date the money arrived (bank date).')}
            required
            fullWidth
          />
          <FormControl fullWidth>
            <InputLabel id="mark-paid-method-label">Payment method</InputLabel>
            <Select
              labelId="mark-paid-method-label"
              label="Payment method"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as string)}
            >
              <MenuItem value="">Not stated</MenuItem>
              {PAYMENT_METHODS.map((method) => (
                <MenuItem key={method} value={method}>{method}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Payment reference"
            value={transactionId}
            onChange={(e) => setTransactionId(e.target.value)}
            inputProps={{ maxLength: 100 }}
            fullWidth
          />
          <TextField
            label="Internal note"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            helperText="Kept in the history, not printed on the invoice."
            inputProps={{ maxLength: 2000 }}
            multiline
            rows={2}
            fullWidth
          />

          <Alert severity="info">
            {receiptOnly
              ? 'This invoice is already marked paid but has no receipt number. This gives it one; the status stays Paid.'
              : 'Recording the payment marks the invoice Paid and gives it a receipt number.'}
            {' '}<strong>Record and email receipt</strong> also emails the receipt to the
            customer&apos;s billing contacts. <strong>Record without sending</strong> sends nothing;
            you can send the receipt later.
          </Alert>
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={close} disabled={submitting}>Cancel</Button>
        <Button variant="outlined" onClick={() => record(false)} disabled={submitting || Boolean(dateProblem)}>
          Record without sending
        </Button>
        <Button variant="contained" onClick={() => record(true)} disabled={submitting || Boolean(dateProblem)}>
          Record and email receipt
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default MarkPaidDialog;
