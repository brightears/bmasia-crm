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
  GridLegacy as Grid,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Close,
  Send,
  GetApp,
  Visibility,
  Payment,
  Receipt,
  Business,
  Schedule,
  Description,
  CheckCircle,
  Cancel,
  Email,
} from '@mui/icons-material';
import { Invoice, EmailLogEntry, Contact } from '../types';
import ApiService, { MarkInvoicePaidResult } from '../services/api';
import RecipientFallback, { noRecipientMessage } from './RecipientFallback';
import EmailSendDialog, { EmailSendData } from './EmailSendDialog';
import MarkPaidDialog, { describeMarkPaidResult } from './MarkPaidDialog';
import { formatDate as formatDisplayDate, formatMoney } from '../theme';
import { useAuth } from '../contexts/AuthContext';
import { canDo } from '../utils/access';

interface InvoiceDetailProps {
  open: boolean;
  onClose: () => void;
  invoice: Invoice | null;
  onInvoiceUpdate: () => void;
}

const InvoiceDetail: React.FC<InvoiceDetailProps> = ({
  open,
  onClose,
  invoice,
  onInvoiceUpdate,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [sendFallback, setSendFallback] = useState<string | null>(null);
  const [emailLogs, setEmailLogs] = useState<EmailLogEntry[]>([]);

  // Receipt email
  const [receiptEmailDialogOpen, setReceiptEmailDialogOpen] = useState(false);
  const [companyContacts, setCompanyContacts] = useState<Contact[]>([]);

  // Record payment ("Mark as Paid"): the dialog asks whether to email the receipt.
  const [markPaidOpen, setMarkPaidOpen] = useState(false);
  // Recording payments is for Finance and Admin (role table in utils/access.ts).
  const canRecordPayment = canDo(useAuth().user, 'invoice-money');

  useEffect(() => {
    if (open && invoice) {
      ApiService.getEmailLogs({ invoice: invoice.id })
        .then(setEmailLogs)
        .catch(() => setEmailLogs([]));
      // Load company contacts for receipt email dialog
      if (invoice.company) {
        ApiService.getCompany(invoice.company)
          .then((company: any) => setCompanyContacts(company.contacts || []))
          .catch(() => setCompanyContacts([]));
      }
    }
  }, [open, invoice]);

  const handleSendInvoice = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      const response = await ApiService.sendInvoice(invoice.id);
      const details = response?.email_details;
      if (details && details.length > 0) {
        const recipientList = details.map((d: any) => d.to_email).join(', ');
        setSuccess(`Invoice sent to ${recipientList}`);
      } else {
        setSuccess('Invoice sent successfully');
      }
      onInvoiceUpdate();
      // Reload email logs after send
      ApiService.getEmailLogs({ invoice: invoice.id })
        .then(setEmailLogs)
        .catch(() => {});
    } catch (err) {
      const noRecipient = noRecipientMessage(err);
      if (noRecipient) {
        setSendFallback(noRecipient);
      } else {
        setError('Failed to send invoice');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsSent = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      await ApiService.updateInvoice(invoice.id, { status: 'Sent' });
      setSuccess('Invoice marked as sent');
      onInvoiceUpdate();
    } catch (err: any) {
      const data = err?.response?.data;
      const reason = Array.isArray(data?.status) ? data.status.join(' ') : data?.status || data?.error;
      setError(typeof reason === 'string' && reason ? reason : 'Failed to update invoice status');
    } finally {
      setLoading(false);
    }
  };

  const handlePaymentRecorded = (result: MarkInvoicePaidResult) => {
    if (!invoice) return;
    setMarkPaidOpen(false);
    setSuccess(describeMarkPaidResult(result));
    onInvoiceUpdate();
    // Reload email logs to show a receipt email, if one was sent
    ApiService.getEmailLogs({ invoice: invoice.id })
      .then(setEmailLogs)
      .catch(() => {});
  };

  const handlePreviewPDF = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      const blob = await ApiService.previewInvoicePDF(invoice.id);
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

  const handleDownloadReceipt = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      const blob = await ApiService.downloadReceiptPDF(invoice.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Receipt_Tax_Invoice_${invoice.receipt_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download receipt PDF');
    } finally {
      setLoading(false);
    }
  };

  const handlePreviewReceipt = async () => {
    if (!invoice) return;

    try {
      setLoading(true);
      const blob = await ApiService.downloadReceiptPDF(invoice.id);
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (err) {
      setError('Failed to preview receipt PDF');
    } finally {
      setLoading(false);
    }
  };

  const handleSendReceipt = async (data: EmailSendData) => {
    if (!invoice) return;
    await ApiService.sendReceiptEmail(invoice.id, data);
    // Reload email logs after send
    ApiService.getEmailLogs({ invoice: invoice.id })
      .then(setEmailLogs)
      .catch(() => {});
    onInvoiceUpdate();
  };

  // Amounts use the invoice's own currency (was always shown in dollars).
  const formatCurrency = (value: number): string => formatMoney(value, invoice?.currency || 'USD');

  const formatDate = (dateString: string): string => formatDisplayDate(dateString);

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
                    {invoice.receipt_number && (
                      <ListItem>
                        <ListItemIcon>
                          <Receipt />
                        </ListItemIcon>
                        <ListItemText
                          primary="Receipt No."
                          secondary={invoice.receipt_number}
                        />
                      </ListItem>
                    )}
                    {invoice.status === 'Paid' && invoice.paid_date && (
                      <ListItem>
                        <ListItemIcon>
                          <Payment />
                        </ListItemIcon>
                        <ListItemText
                          primary="Paid Date"
                          secondary={formatDate(invoice.paid_date)}
                        />
                      </ListItem>
                    )}
                    {invoice.status === 'Paid' && (
                      <ListItem>
                        <ListItemIcon>
                          <Payment />
                        </ListItemIcon>
                        <ListItemText
                          primary="Payment Method"
                          secondary={invoice.payment_method || '-'}
                        />
                      </ListItem>
                    )}
                    {invoice.status === 'Paid' && invoice.transaction_id && (
                      <ListItem>
                        <ListItemIcon>
                          <Payment />
                        </ListItemIcon>
                        <ListItemText
                          primary="Payment Reference"
                          secondary={invoice.transaction_id}
                        />
                      </ListItem>
                    )}
                    {invoice.status === 'Paid' && invoice.receipt_number && (
                      <ListItem>
                        <ListItemIcon>
                          <Email />
                        </ListItemIcon>
                        <ListItemText
                          primary="Receipt Email"
                          secondary={
                            <Chip
                              label={invoice.receipt_sent ? 'Sent' : 'Not Sent'}
                              color={invoice.receipt_sent ? 'success' : 'default'}
                              variant="outlined"
                              size="small"
                            />
                          }
                        />
                      </ListItem>
                    )}
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

          {/* Email History */}
          <Paper sx={{ p: 2, mt: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Email fontSize="small" />
              Email History
            </Typography>
            {emailLogs.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No emails sent for this invoice yet
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {emailLogs.map((log) => (
                  <Box key={log.id} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, p: 1.5, borderRadius: 1, bgcolor: 'grey.50' }}>
                    <Box sx={{ mt: 0.5 }}>
                      {log.status === 'sent' && <CheckCircle color="success" fontSize="small" />}
                      {log.status === 'opened' && <Visibility color="info" fontSize="small" />}
                      {log.status === 'failed' && <Cancel color="error" fontSize="small" />}
                      {log.status === 'pending' && <Schedule color="disabled" fontSize="small" />}
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Typography variant="body2" fontWeight="medium">
                          {log.email_type_display}
                        </Typography>
                        <Chip
                          label={log.status_display}
                          size="small"
                          color={log.status === 'sent' ? 'success' : log.status === 'opened' ? 'info' : log.status === 'failed' ? 'error' : 'default'}
                          variant="outlined"
                        />
                        {log.opened_at && (
                          <Chip label={`Opened ${new Date(log.opened_at).toLocaleString()}`} size="small" color="info" />
                        )}
                      </Box>
                      <Typography variant="body2" color="text.secondary" noWrap>
                        To: {log.to_email}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" noWrap>
                        From: {log.from_email}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {log.sent_at ? new Date(log.sent_at).toLocaleString() : log.created_at ? new Date(log.created_at).toLocaleString() : ''}
                      </Typography>
                      {log.status === 'failed' && log.error_message && (
                        <Typography variant="caption" color="error" display="block">
                          Error: {log.error_message}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                ))}
              </Box>
            )}
          </Paper>
        </Box>
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
        {invoice && invoice.status === 'Draft' && (
          <Button
            onClick={handleSendInvoice}
            variant="contained"
            color="primary"
            startIcon={<Send />}
            disabled={loading}
          >
            Send via Email
          </Button>
        )}
        {invoice && invoice.status === 'Draft' && (
          <Button
            onClick={handleMarkAsSent}
            variant="outlined"
            startIcon={<CheckCircle />}
            disabled={loading}
          >
            Mark as Sent
          </Button>
        )}
        {canRecordPayment && invoice && (invoice.status === 'Sent' || invoice.status === 'Overdue') && (
          <Button
            onClick={() => setMarkPaidOpen(true)}
            variant="contained"
            color="success"
            startIcon={<CheckCircle />}
            disabled={loading}
          >
            Mark as Paid
          </Button>
        )}
        {canRecordPayment && invoice && invoice.status === 'Paid' && !invoice.receipt_number && (
          <Button
            onClick={() => setMarkPaidOpen(true)}
            variant="contained"
            color="success"
            startIcon={<Receipt />}
            disabled={loading}
          >
            Issue Receipt
          </Button>
        )}
        {invoice && invoice.status === 'Paid' && invoice.receipt_number && (
          <>
            <Button
              onClick={handlePreviewReceipt}
              variant="outlined"
              startIcon={<Receipt />}
              disabled={loading}
              sx={{ borderColor: '#4CAF50', color: '#4CAF50' }}
            >
              Preview Receipt
            </Button>
            <Button
              onClick={handleDownloadReceipt}
              variant="outlined"
              startIcon={<GetApp />}
              disabled={loading}
              sx={{ borderColor: '#4CAF50', color: '#4CAF50' }}
            >
              Download Receipt
            </Button>
            <Button
              onClick={() => setReceiptEmailDialogOpen(true)}
              variant="contained"
              startIcon={<Send />}
              disabled={loading}
              sx={{ bgcolor: '#4CAF50', '&:hover': { bgcolor: '#388E3C' } }}
            >
              {invoice.receipt_sent ? 'Resend Receipt' : 'Send Receipt'}
            </Button>
          </>
        )}
      </DialogActions>

      <MarkPaidDialog
        open={markPaidOpen}
        invoice={invoice}
        onClose={() => setMarkPaidOpen(false)}
        onRecorded={handlePaymentRecorded}
        onConflict={onInvoiceUpdate}
      />

      {/* Receipt Email Dialog */}
      {invoice && invoice.status === 'Paid' && invoice.receipt_number && (
        <EmailSendDialog
          open={receiptEmailDialogOpen}
          onClose={() => setReceiptEmailDialogOpen(false)}
          documentType="receipt"
          documentId={invoice.id}
          documentNumber={invoice.receipt_number}
          companyName={invoice.company_name || ''}
          contacts={companyContacts}
          onSendSuccess={() => {
            setReceiptEmailDialogOpen(false);
            setSuccess('Receipt email sent successfully');
            onInvoiceUpdate();
            ApiService.getEmailLogs({ invoice: invoice.id })
              .then(setEmailLogs)
              .catch(() => {});
          }}
          onSendEmail={handleSendReceipt}
          documentDetails={{
            currency: invoice.currency,
            totalValue: invoice.total_amount,
          }}
        />
      )}
      {invoice && sendFallback && (
        <RecipientFallback
          open
          message={sendFallback}
          documentType="invoice"
          documentId={invoice.id}
          documentNumber={invoice.invoice_number}
          companyId={invoice.company}
          companyName={invoice.company_name}
          onClose={() => setSendFallback(null)}
          onSendEmail={(data) => ApiService.sendInvoiceEmail(invoice.id, data)}
          onSent={() => {
            setSendFallback(null);
            setSuccess('Invoice sent');
            onInvoiceUpdate();
            ApiService.getEmailLogs({ invoice: invoice.id }).then(setEmailLogs).catch(() => {});
          }}
        />
      )}
    </Dialog>
  );
};

export default InvoiceDetail;
