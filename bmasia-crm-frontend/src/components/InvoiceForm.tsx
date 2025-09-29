import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Divider,
  Switch,
  FormControlLabel,
  Alert,
  GridLegacy as Grid,
  InputAdornment,
} from '@mui/material';
import {
  Add,
  Delete,
  Calculate,
  Receipt,
  Save,
  Close,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV2';
import { Invoice, InvoiceLineItem, Company, Contract } from '../types';
import ApiService from '../services/api';

interface InvoiceFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (invoice: Invoice) => void;
  invoice: Invoice | null;
  mode: 'create' | 'edit';
  companies: Company[];
  contracts: Contract[];
}

const paymentTermsOptions = [
  { value: 'Net 15', label: 'Net 15 days' },
  { value: 'Net 30', label: 'Net 30 days' },
  { value: 'Net 45', label: 'Net 45 days' },
  { value: 'Net 60', label: 'Net 60 days' },
  { value: 'Due on Receipt', label: 'Due on Receipt' },
  { value: 'Custom', label: 'Custom' },
];

const defaultLineItem: InvoiceLineItem = {
  description: '',
  quantity: 1,
  unit_price: 0,
  tax_rate: 0,
  total: 0,
};

const InvoiceForm: React.FC<InvoiceFormProps> = ({
  open,
  onClose,
  onSave,
  invoice,
  mode,
  companies,
  contracts,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Form fields
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [companyId, setCompanyId] = useState('');
  const [contractId, setContractId] = useState('');
  const [issueDate, setIssueDate] = useState<Date | null>(new Date());
  const [dueDate, setDueDate] = useState<Date | null>(null);
  const [paymentTerms, setPaymentTerms] = useState('Net 30');
  const [notes, setNotes] = useState('');
  const [lineItems, setLineItems] = useState<InvoiceLineItem[]>([defaultLineItem]);
  const [discountAmount, setDiscountAmount] = useState(0);
  const [sendEmail, setSendEmail] = useState(false);

  // Filtered contracts based on selected company
  const [filteredContracts, setFilteredContracts] = useState<Contract[]>([]);

  useEffect(() => {
    if (open) {
      if (mode === 'create') {
        resetForm();
        generateInvoiceNumber();
      } else if (invoice) {
        populateForm(invoice);
      }
    }
  }, [open, mode, invoice]);

  useEffect(() => {
    // Filter contracts by selected company
    if (companyId) {
      const filtered = contracts.filter(contract => contract.company === companyId);
      setFilteredContracts(filtered);

      // Reset contract selection if current contract doesn't belong to selected company
      if (contractId && !filtered.find(c => c.id === contractId)) {
        setContractId('');
      }
    } else {
      setFilteredContracts([]);
      setContractId('');
    }
  }, [companyId, contracts, contractId]);

  useEffect(() => {
    // Calculate due date based on payment terms
    if (issueDate && paymentTerms !== 'Custom') {
      const days = paymentTerms === 'Due on Receipt' ? 0 : parseInt(paymentTerms.replace('Net ', ''));
      const newDueDate = new Date(issueDate);
      newDueDate.setDate(newDueDate.getDate() + days);
      setDueDate(newDueDate);
    }
  }, [issueDate, paymentTerms]);

  const resetForm = () => {
    setInvoiceNumber('');
    setCompanyId('');
    setContractId('');
    setIssueDate(new Date());
    setDueDate(null);
    setPaymentTerms('Net 30');
    setNotes('');
    setLineItems([defaultLineItem]);
    setDiscountAmount(0);
    setSendEmail(false);
    setError('');
  };

  const populateForm = (invoice: Invoice) => {
    setInvoiceNumber(invoice.invoice_number);
    setCompanyId(invoice.company);
    setContractId(invoice.contract);
    setIssueDate(new Date(invoice.issue_date));
    setDueDate(invoice.due_date ? new Date(invoice.due_date) : null);
    setPaymentTerms(invoice.payment_terms || 'Net 30');
    setNotes(invoice.notes || '');
    setLineItems(invoice.line_items.length > 0 ? invoice.line_items : [defaultLineItem]);
    setDiscountAmount(invoice.discount_amount || 0);
    setSendEmail(false);
    setError('');
  };

  const generateInvoiceNumber = async () => {
    try {
      // Generate a simple invoice number based on current date
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0');
      setInvoiceNumber(`INV-${year}${month}${day}-${random}`);
    } catch (err) {
      console.error('Failed to generate invoice number:', err);
    }
  };

  const handleLineItemChange = (index: number, field: keyof InvoiceLineItem, value: any) => {
    const updatedItems = [...lineItems];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: value,
    };

    // Calculate total for the line item
    if (field === 'quantity' || field === 'unit_price' || field === 'tax_rate') {
      const item = updatedItems[index];
      const subtotal = item.quantity * item.unit_price;
      const taxAmount = subtotal * (item.tax_rate / 100);
      item.total = subtotal + taxAmount;
    }

    setLineItems(updatedItems);
  };

  const addLineItem = () => {
    setLineItems([...lineItems, { ...defaultLineItem }]);
  };

  const removeLineItem = (index: number) => {
    if (lineItems.length > 1) {
      const updatedItems = lineItems.filter((_, i) => i !== index);
      setLineItems(updatedItems);
    }
  };

  const calculateTotals = () => {
    const subtotal = lineItems.reduce((sum, item) => sum + (item.quantity * item.unit_price), 0);
    const taxAmount = lineItems.reduce((sum, item) => sum + (item.quantity * item.unit_price * item.tax_rate / 100), 0);
    const total = subtotal + taxAmount - discountAmount;

    return {
      subtotal,
      taxAmount,
      total: Math.max(0, total), // Ensure total is not negative
    };
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setError('');

      // Validation
      if (!invoiceNumber.trim()) {
        setError('Invoice number is required');
        return;
      }
      if (!companyId) {
        setError('Company is required');
        return;
      }
      if (!contractId) {
        setError('Contract is required');
        return;
      }
      if (!issueDate) {
        setError('Issue date is required');
        return;
      }
      if (!dueDate) {
        setError('Due date is required');
        return;
      }
      if (lineItems.length === 0 || lineItems.every(item => !item.description.trim())) {
        setError('At least one line item is required');
        return;
      }

      const totals = calculateTotals();

      const invoiceData = {
        invoice_number: invoiceNumber,
        company: companyId,
        contract: contractId,
        issue_date: issueDate.toISOString().split('T')[0],
        due_date: dueDate.toISOString().split('T')[0],
        payment_terms: paymentTerms,
        notes,
        line_items: lineItems.filter(item => item.description.trim()),
        amount: totals.subtotal,
        tax_amount: totals.taxAmount,
        discount_amount: discountAmount,
        total_amount: totals.total,
        currency: 'USD',
        status: 'Draft' as const,
      };

      let savedInvoice: Invoice;
      if (mode === 'create') {
        savedInvoice = await ApiService.createInvoice(invoiceData);
      } else {
        savedInvoice = await ApiService.updateInvoice(invoice!.id, invoiceData);
      }

      // Send email if requested
      if (sendEmail && savedInvoice.id) {
        try {
          await ApiService.sendInvoice(savedInvoice.id);
        } catch (emailError) {
          console.error('Failed to send invoice email:', emailError);
          // Don't fail the entire operation if email fails
        }
      }

      onSave(savedInvoice);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to save invoice');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const totals = calculateTotals();

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
            {mode === 'create' ? 'Create New Invoice' : 'Edit Invoice'}
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
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            {/* Header Information */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Invoice Information
              </Typography>
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Invoice Number"
                    value={invoiceNumber}
                    onChange={(e) => setInvoiceNumber(e.target.value)}
                    required
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <FormControl fullWidth required>
                    <InputLabel>Company</InputLabel>
                    <Select
                      value={companyId}
                      onChange={(e) => setCompanyId(e.target.value)}
                      label="Company"
                    >
                      {companies.map((company) => (
                        <MenuItem key={company.id} value={company.id}>
                          {company.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FormControl fullWidth required>
                    <InputLabel>Contract</InputLabel>
                    <Select
                      value={contractId}
                      onChange={(e) => setContractId(e.target.value)}
                      label="Contract"
                      disabled={!companyId}
                    >
                      {filteredContracts.map((contract) => (
                        <MenuItem key={contract.id} value={contract.id}>
                          {contract.contract_number} - {formatCurrency(contract.value)}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FormControl fullWidth>
                    <InputLabel>Payment Terms</InputLabel>
                    <Select
                      value={paymentTerms}
                      onChange={(e) => setPaymentTerms(e.target.value)}
                      label="Payment Terms"
                    >
                      {paymentTermsOptions.map((option) => (
                        <MenuItem key={option.value} value={option.value}>
                          {option.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={6}>
                  <DatePicker
                    label="Issue Date"
                    value={issueDate}
                    onChange={setIssueDate}
                    slotProps={{
                      textField: {
                        fullWidth: true,
                        required: true,
                      },
                    }}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <DatePicker
                    label="Due Date"
                    value={dueDate}
                    onChange={setDueDate}
                    slotProps={{
                      textField: {
                        fullWidth: true,
                        required: true,
                      },
                    }}
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Line Items */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                  Line Items
                </Typography>
                <Button
                  variant="outlined"
                  startIcon={<Add />}
                  onClick={addLineItem}
                  size="small"
                >
                  Add Item
                </Button>
              </Box>

              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Description</TableCell>
                      <TableCell width="100">Quantity</TableCell>
                      <TableCell width="120">Unit Price</TableCell>
                      <TableCell width="100">Tax Rate (%)</TableCell>
                      <TableCell width="120">Total</TableCell>
                      <TableCell width="60">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {lineItems.map((item, index) => (
                      <TableRow key={index}>
                        <TableCell>
                          <TextField
                            fullWidth
                            size="small"
                            value={item.description}
                            onChange={(e) => handleLineItemChange(index, 'description', e.target.value)}
                            placeholder="Enter description..."
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            value={item.quantity}
                            onChange={(e) => handleLineItemChange(index, 'quantity', parseFloat(e.target.value) || 0)}
                            inputProps={{ min: 0, step: 0.01 }}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            value={item.unit_price}
                            onChange={(e) => handleLineItemChange(index, 'unit_price', parseFloat(e.target.value) || 0)}
                            inputProps={{ min: 0, step: 0.01 }}
                            InputProps={{
                              startAdornment: <InputAdornment position="start">$</InputAdornment>,
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            value={item.tax_rate}
                            onChange={(e) => handleLineItemChange(index, 'tax_rate', parseFloat(e.target.value) || 0)}
                            inputProps={{ min: 0, max: 100, step: 0.1 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight="medium">
                            {formatCurrency(item.total)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <IconButton
                            size="small"
                            onClick={() => removeLineItem(index)}
                            disabled={lineItems.length === 1}
                            color="error"
                          >
                            <Delete fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>

            {/* Totals */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Invoice Totals
              </Typography>
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Discount Amount"
                    type="number"
                    value={discountAmount}
                    onChange={(e) => setDiscountAmount(parseFloat(e.target.value) || 0)}
                    inputProps={{ min: 0, step: 0.01 }}
                    InputProps={{
                      startAdornment: <InputAdornment position="start">$</InputAdornment>,
                    }}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <Box sx={{ mt: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">Subtotal:</Typography>
                      <Typography variant="body2">{formatCurrency(totals.subtotal)}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">Tax:</Typography>
                      <Typography variant="body2">{formatCurrency(totals.taxAmount)}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">Discount:</Typography>
                      <Typography variant="body2" color="error">
                        -{formatCurrency(discountAmount)}
                      </Typography>
                    </Box>
                    <Divider sx={{ my: 1 }} />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="h6">Total:</Typography>
                      <Typography variant="h6" color="primary">
                        {formatCurrency(totals.total)}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>
              </Grid>
            </Paper>

            {/* Notes and Options */}
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Additional Information
              </Typography>
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    multiline
                    rows={3}
                    placeholder="Additional notes or terms..."
                  />
                </Grid>
                <Grid item xs={12}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={sendEmail}
                        onChange={(e) => setSendEmail(e.target.checked)}
                      />
                    }
                    label="Send invoice via email after saving"
                  />
                </Grid>
              </Grid>
            </Paper>
          </Box>
        </LocalizationProvider>
      </DialogContent>

      <DialogActions sx={{ p: 3, pt: 0 }}>
        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading}
          startIcon={loading ? <Calculate /> : <Save />}
        >
          {loading ? 'Saving...' : mode === 'create' ? 'Create Invoice' : 'Update Invoice'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default InvoiceForm;