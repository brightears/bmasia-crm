import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Divider,
  IconButton,
  Alert,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  GridLegacy as Grid,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Timeline,
  TimelineItem,
  TimelineOppositeContent,
  TimelineSeparator,
  TimelineDot,
  TimelineConnector,
  TimelineContent,
} from '@mui/lab';
import {
  Close,
  Send,
  GetApp,
  Visibility,
  Payment,
  Receipt,
  Business,
  Schedule,
  Add,
  History,
  Description,
  CheckCircle,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Invoice } from '../types';
import ApiService from '../services/api';

interface InvoiceDetailProps {
  open: boolean;
  onClose: () => void;
  invoice: Invoice | null;
  onInvoiceUpdate: () => void;
}

const paymentMethods = [
  { value: 'Cash', label: 'Cash' },
  { value: 'Check', label: 'Check' },
  { value: 'Credit Card', label: 'Credit Card' },
  { value: 'Bank Transfer', label: 'Bank Transfer' },
  { value: 'Online Payment', label: 'Online Payment' },
  { value: 'Other', label: 'Other' },
];

const InvoiceDetail: React.FC<InvoiceDetailProps> = ({
  open,
  onClose,
  invoice,
  onInvoiceUpdate,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Payment form
  const [paymentDialogOpen, setPaymentDialogOpen] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState(0);
  const [paymentMethod, setPaymentMethod] = useState('');
  const [paymentDate, setPaymentDate] = useState<Date | null>(new Date());
  const [transactionId, setTransactionId] = useState('');
  const [paymentNotes, setPaymentNotes] = useState('');

  useEffect(() => {
    if (invoice && paymentDialogOpen) {
      // Set default payment amount to remaining amount
      setPaymentAmount(invoice.remaining_amount || invoice.total_amount);
    }
  }, [invoice, paymentDialogOpen]);

  const handleSendInvoice = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      await ApiService.sendInvoice(invoice.id);
      setSuccess('Invoice sent successfully');
      onInvoiceUpdate();
    } catch (err) {
      setError('Failed to send invoice');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkPaid = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      await ApiService.markInvoicePaid(invoice.id);
      setSuccess('Invoice marked as paid');
      onInvoiceUpdate();
    } catch (err) {
      setError('Failed to mark invoice as paid');
    } finally {
      setLoading(false);
    }
  };

  const handlePreviewPDF = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      const blob = await ApiService.downloadInvoicePDF(invoice.id);
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (err) {
      setError('Failed to preview PDF');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      const blob = await ApiService.downloadInvoicePDF(invoice.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Invoice_${invoice.invoice_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download PDF');
    } finally {
      setLoading(false);
    }
  };

  const handleAddPayment = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      setError('');

      if (!paymentAmount || paymentAmount <= 0) {
        setError('Payment amount must be greater than 0');
        return;
      }

      if (!paymentMethod) {
        setError('Payment method is required');
        return;
      }

      if (!paymentDate) {
        setError('Payment date is required');
        return;
      }

      await ApiService.addInvoicePayment(invoice.id, {
        amount: paymentAmount,
        payment_method: paymentMethod,
        payment_date: paymentDate.toISOString().split('T')[0],
        transaction_id: transactionId,
        notes: paymentNotes,
      });

      setSuccess('Payment added successfully');
      setPaymentDialogOpen(false);
      resetPaymentForm();
      onInvoiceUpdate();
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to add payment');
    } finally {
      setLoading(false);
    }
  };

  const resetPaymentForm = () => {
    setPaymentAmount(0);
    setPaymentMethod('');
    setPaymentDate(new Date());
    setTransactionId('');
    setPaymentNotes('');
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: string): string => {
    const colors: { [key: string]: string } = {
      'Draft': '#9e9e9e',
      'Sent': '#2196f3',
      'Paid': '#4caf50',
      'Overdue': '#f44336',
      'Cancelled': '#f44336',
      'Refunded': '#9c27b0',
    };
    return colors[status] || '#2196f3';
  };


  if (!invoice) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      scroll="body"
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Receipt sx={{ mr: 1 }} />
          <Typography variant="h6">
            Invoice Details - {invoice.invoice_number}
          </Typography>
        </Box>
        <IconButton onClick={onClose} size="small">
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <Box sx={{ mt: 2 }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                {error}
              </Alert>
            )}

            {success && (
              <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
                {success}
              </Alert>
            )}

            {/* Invoice Header */}
            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid item xs={12} md={8}>
                <Card>
                  <CardContent>
                    <Typography variant="h5" gutterBottom>
                      {invoice.invoice_number}
                    </Typography>
                    <List dense>
                      <ListItem>
                        <ListItemIcon>
                          <Business />
                        </ListItemIcon>
                        <ListItemText
                          primary="Company"
                          secondary={invoice.company_name}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemIcon>
                          <Description />
                        </ListItemIcon>
                        <ListItemText
                          primary="Contract"
                          secondary={invoice.contract_number}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemIcon>
                          <Schedule />
                        </ListItemIcon>
                        <ListItemText
                          primary="Issue Date"
                          secondary={formatDate(invoice.issue_date)}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemIcon>
                          <Schedule />
                        </ListItemIcon>
                        <ListItemText
                          primary="Due Date"
                          secondary={
                            <Box>
                              {formatDate(invoice.due_date)}
                              {invoice.is_overdue && (
                                <Typography variant="caption" color="error" display="block">
                                  {invoice.days_overdue} days overdue
                                </Typography>
                              )}
                            </Box>
                          }
                        />
                      </ListItem>
                    </List>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <Typography variant="h6">Status</Typography>
                      <Box sx={{ ml: 'auto' }}>
                        <Chip
                          label={invoice.status}
                          sx={{
                            backgroundColor: getStatusColor(invoice.status),
                            color: 'white',
                            fontWeight: 600
                          }}
                        />
                      </Box>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">Subtotal:</Typography>
                      <Typography variant="body2">{formatCurrency(invoice.amount)}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">Tax:</Typography>
                      <Typography variant="body2">{formatCurrency(invoice.tax_amount)}</Typography>
                    </Box>
                    {invoice.discount_amount > 0 && (
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="body2">Discount:</Typography>
                        <Typography variant="body2" color="error">
                          -{formatCurrency(invoice.discount_amount)}
                        </Typography>
                      </Box>
                    )}
                    <Divider sx={{ my: 1 }} />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                      <Typography variant="h6">Total:</Typography>
                      <Typography variant="h6" color="primary">
                        {formatCurrency(invoice.total_amount)}
                      </Typography>
                    </Box>
                    {invoice.remaining_amount > 0 && (
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body1" fontWeight="medium">Remaining:</Typography>
                        <Typography variant="body1" fontWeight="medium" color="warning.main">
                          {formatCurrency(invoice.remaining_amount)}
                        </Typography>
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            {/* Line Items */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Line Items
              </Typography>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Description</TableCell>
                      <TableCell align="right">Quantity</TableCell>
                      <TableCell align="right">Unit Price</TableCell>
                      <TableCell align="right">Tax Rate</TableCell>
                      <TableCell align="right">Total</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {invoice.line_items.map((item, index) => (
                      <TableRow key={index}>
                        <TableCell>{item.description}</TableCell>
                        <TableCell align="right">{item.quantity}</TableCell>
                        <TableCell align="right">{formatCurrency(item.unit_price)}</TableCell>
                        <TableCell align="right">{item.tax_rate}%</TableCell>
                        <TableCell align="right">{formatCurrency(item.total)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>

            {/* Payment History */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                  Payment History
                </Typography>
                {invoice.status !== 'Paid' && invoice.remaining_amount > 0 && (
                  <Button
                    variant="outlined"
                    startIcon={<Add />}
                    onClick={() => setPaymentDialogOpen(true)}
                    size="small"
                  >
                    Add Payment
                  </Button>
                )}
              </Box>

              {invoice.payments && invoice.payments.length > 0 ? (
                <Timeline>
                  {invoice.payments.map((payment, index) => (
                    <TimelineItem key={payment.id}>
                      <TimelineOppositeContent sx={{ m: 'auto 0' }} variant="body2" color="text.secondary">
                        {formatDate(payment.payment_date)}
                      </TimelineOppositeContent>
                      <TimelineSeparator>
                        <TimelineDot color="primary">
                          <Payment />
                        </TimelineDot>
                        {index < invoice.payments.length - 1 && <TimelineConnector />}
                      </TimelineSeparator>
                      <TimelineContent sx={{ py: '12px', px: 2 }}>
                        <Typography variant="h6" component="span">
                          {formatCurrency(payment.amount)}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {payment.payment_method}
                          {payment.transaction_id && ` - ${payment.transaction_id}`}
                        </Typography>
                        {payment.notes && (
                          <Typography variant="body2" color="text.secondary">
                            {payment.notes}
                          </Typography>
                        )}
                        <Typography variant="caption" color="text.secondary" display="block">
                          Added by {payment.created_by_name}
                        </Typography>
                      </TimelineContent>
                    </TimelineItem>
                  ))}
                </Timeline>
              ) : (
                <Box sx={{ py: 4, textAlign: 'center' }}>
                  <History sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                  <Typography variant="h6" color="text.secondary">
                    No payments recorded
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Add a payment to track payment history
                  </Typography>
                </Box>
              )}
            </Paper>

            {/* Notes */}
            {invoice.notes && (
              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Notes
                </Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {invoice.notes}
                </Typography>
              </Paper>
            )}
          </Box>
        </LocalizationProvider>
      </DialogContent>

      <DialogActions sx={{ p: 3, pt: 0 }}>
        <Button onClick={onClose}>
          Close
        </Button>
        <Button
          onClick={handlePreviewPDF}
          variant="outlined"
          startIcon={<Visibility />}
          disabled={loading}
        >
          Preview
        </Button>
        <Button
          onClick={handleDownloadPDF}
          variant="outlined"
          startIcon={<GetApp />}
          disabled={loading}
        >
          Download PDF
        </Button>
        <Button
          onClick={handleSendInvoice}
          variant="outlined"
          startIcon={<Send />}
          disabled={loading}
        >
          Send Invoice
        </Button>
        {invoice && (invoice.status === 'Sent' || invoice.status === 'Overdue') && (
          <Button
            onClick={handleMarkPaid}
            variant="contained"
            color="success"
            startIcon={<CheckCircle />}
            disabled={loading}
          >
            Mark as Paid
          </Button>
        )}
      </DialogActions>

      {/* Add Payment Dialog */}
      <Dialog
        open={paymentDialogOpen}
        onClose={() => setPaymentDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add Payment</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Payment Amount"
                  type="number"
                  value={paymentAmount}
                  onChange={(e) => setPaymentAmount(parseFloat(e.target.value) || 0)}
                  inputProps={{ min: 0, step: 0.01 }}
                  InputProps={{
                    startAdornment: <Typography sx={{ mr: 1 }}>$</Typography>,
                  }}
                  required
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth required>
                  <InputLabel>Payment Method</InputLabel>
                  <Select
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    label="Payment Method"
                  >
                    {paymentMethods.map((method) => (
                      <MenuItem key={method.value} value={method.value}>
                        {method.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <DatePicker
                  label="Payment Date"
                  value={paymentDate}
                  onChange={setPaymentDate}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      required: true,
                    },
                  }}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Transaction ID"
                  value={transactionId}
                  onChange={(e) => setTransactionId(e.target.value)}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Notes"
                  value={paymentNotes}
                  onChange={(e) => setPaymentNotes(e.target.value)}
                  multiline
                  rows={3}
                />
              </Grid>
            </Grid>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPaymentDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleAddPayment}
            variant="contained"
            disabled={loading || !paymentAmount || !paymentMethod}
          >
            Add Payment
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  );
};

export default InvoiceDetail;