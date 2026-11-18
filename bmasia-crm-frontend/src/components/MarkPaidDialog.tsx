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

/** Today as YYYY-MM-DD in the user's own time zone (toISOString would give the UTC date). */
export const localToday = (now: Date = new Date()): string => {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
};

/** One line for the page after a payment is recorded. */
export const describeMarkPaidResult = (result: MarkInvoicePaidResult): string => {
  const receipt = result.receipt_number ? ` Receipt ${result.receipt_number}.` : '';
  if (result.receipt_email_status === 'sent') {
    return `Payment recorded.${receipt} The receipt was emailed to the customer.`;
  }
  if (result.receipt_email_status?.startsWith('failed')) {
    return `Payment recorded.${receipt} The receipt email failed; use Send Receipt to try again.`;
  }
  return `Payment recorded.${receipt} No email was sent.`;
};

interface MarkPaidDialogProps {
  open: boolean;
  invoice: Invoice | null;
  onClose: () => void;
  onRecorded: (result: MarkInvoicePaidResult) => void;
}

const MarkPaidDialog: React.FC<MarkPaidDialogProps> = ({ open, invoice, onClose, onRecorded }) => {
  const [paidDate, setPaidDate] = useState(localToday());
  const [paymentMethod, setPaymentMethod] = useState('');
  const [transactionId, setTransactionId] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const inFlight = useRef(false); // a second click before the re-render must not post again

  useEffect(() => {
    if (open) {
      setPaidDate(localToday());
      setPaymentMethod(invoice?.payment_method || '');
      setTransactionId('');
      setNotes('');
      setError('');
    }
  }, [open, invoice]);

  if (!invoice) return null;

  const today = localToday();
  const dateProblem = !paidDate
    ? 'Enter the date the payment arrived.'
    : paidDate > today
      ? 'The payment date cannot be in the future.'
      : '';

  const record = async (sendReceipt: boolean) => {
    if (inFlight.current || dateProblem) return;
    inFlight.current = true;
    setSubmitting(true);
    setError('');
    try {
      const result = await ApiService.markInvoicePaid(invoice.id, {
        paid_date: paidDate,
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
      <DialogTitle id="mark-paid-title">Record payment</DialogTitle>
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
            inputProps={{ max: today }}
            InputLabelProps={{ shrink: true }}
            error={Boolean(dateProblem)}
            helperText={dateProblem || 'The date the money arrived (bank date).'}
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
            Recording the payment marks the invoice Paid and gives it a receipt number.
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
