import React, { useState, useEffect, useRef } from 'react';
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
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
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

// Entity-specific default payment terms text (same as contract PDFs)
const PAYMENT_TERMS_DEFAULTS: Record<string, string> = {
  'Thailand': "by bank transfer on a net received, paid in full basis, with no offset to BMA's TMB-Thanachart Bank, Bangkok, Thailand due immediately on invoicing to activate the music subscription. All outbound and inbound bank transfer fees are borne by the Client in remitting payments as invoiced less Withholding Tax required by Thai Law.",
  'default': "by bank transfer on a net received, paid in full basis, with no offset to BMA's HSBC Bank, Hong Kong due immediately as invoiced to activate the music subscription. All Bank transfer fees, and all taxes are borne by the Client in remitting payments as invoiced.",
};

const getDefaultPaymentTermsText = (country: string): string => {
  return PAYMENT_TERMS_DEFAULTS[country] || PAYMENT_TERMS_DEFAULTS['default'];
};

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
  const dialogContentRef = useRef<HTMLDivElement>(null);

  // Form fields
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [companyId, setCompanyId] = useState('');
  const [contractId, setContractId] = useState('');
  const [issueDate, setIssueDate] = useState<Date | null>(new Date());
  const [dueDate, setDueDate] = useState<Date | null>(null);
  const [paymentTerms, setPaymentTerms] = useState('Net 30');
  const [paymentTermsText, setPaymentTermsText] = useState('');
  const [notes, setNotes] = useState('');
  const [lineItems, setLineItems] = useState<InvoiceLineItem[]>([defaultLineItem]);
  const [discountAmount, setDiscountAmount] = useState(0);
  const [sendEmail, setSendEmail] = useState(false);
  const [currency, setCurrency] = useState<string>('USD');
  const [servicePeriodStart, setServicePeriodStart] = useState<Date | null>(null);
  const [servicePeriodEnd, setServicePeriodEnd] = useState<Date | null>(null);

  // Filtered contracts based on selected company
  const [filteredContracts, setFilteredContracts] = useState<Contract[]>([]);

  // Track company country for smart VAT/currency (same pattern as QuoteForm)
  const [selectedCompanyCountry, setSelectedCompanyCountry] = useState('');

  // Track which unit price field is focused (show raw number when editing)
  const [focusedPriceIndex, setFocusedPriceIndex] = useState<number | null>(null);

  // Helper function to get currency symbol
  const getCurrencySymbol = (currencyCode: string): string => {
    const symbols: Record<string, string> = {
      'USD': '$',
      'THB': '฿',
      'EUR': '€',
      'GBP': '£',
    };
    return symbols[currencyCode] || '$';
  };

  // Determine tax label based on company country (same as QuoteForm)
  const getTaxLabel = (): string => {
    const selectedCompany = companies.find(c => c.id === companyId);
    if (selectedCompany) {
      if (selectedCompanyCountry === 'Thailand' ||
          selectedCompany.billing_entity?.includes('Thailand')) {
        return 'VAT:';
      }
    }
    return 'Tax:';
  };

  // Get smart tax rate based on company country
  const getSmartTaxRate = (): number => {
    return selectedCompanyCountry === 'Thailand' ? 7 : 0;
  };

  // Scroll to top when error appears so user can see it
  useEffect(() => {
    if (error && dialogContentRef.current) {
      dialogContentRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [error]);

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
    setPaymentTermsText('');
    setNotes('');
    setLineItems([defaultLineItem]);
    setDiscountAmount(0);
    setSendEmail(false);
    setCurrency('USD');
    setServicePeriodStart(null);
    setServicePeriodEnd(null);
    setSelectedCompanyCountry('');
    setError('');
  };

  const populateForm = (invoice: Invoice) => {
    setInvoiceNumber(invoice.invoice_number);
    setCompanyId(invoice.company || '');
    setContractId(invoice.contract || '');
    setIssueDate(new Date(invoice.issue_date));
    setDueDate(invoice.due_date ? new Date(invoice.due_date) : null);
    setPaymentTerms(invoice.payment_terms || 'Net 30');
    setPaymentTermsText(invoice.payment_terms_text || '');
    setNotes(invoice.notes || '');
    setLineItems(invoice.line_items?.length > 0
      ? invoice.line_items.map(item => ({
          ...item,
          total: item.total || item.line_total || (item.quantity * item.unit_price * (1 + item.tax_rate / 100)),
        }))
      : [defaultLineItem]);
    setDiscountAmount(invoice.discount_amount || 0);
    setCurrency(invoice.currency || 'USD');
    setServicePeriodStart(invoice.service_period_start ? new Date(invoice.service_period_start) : null);
    setServicePeriodEnd(invoice.service_period_end ? new Date(invoice.service_period_end) : null);
    setSendEmail(false);
    setError('');

    // Set company country for smart VAT logic
    const editCompany = companies.find(c => c.id === invoice.company);
    if (editCompany) {
      setSelectedCompanyCountry(editCompany.country || '');
    }
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

  // Handle company selection with smart currency default
  const handleCompanyChange = (newCompanyId: string) => {
    setCompanyId(newCompanyId);

    const selectedCompany = companies.find(c => c.id === newCompanyId);
    if (selectedCompany) {
      const country = selectedCompany.country || '';
      setSelectedCompanyCountry(country);

      // Smart currency default based on country (same as QuoteForm)
      const smartCurrency = country === 'Thailand' ? 'THB' : 'USD';
      setCurrency(smartCurrency);

      // Auto-fill payment terms text from entity defaults
      setPaymentTermsText(getDefaultPaymentTermsText(country));

      // Update existing line items' tax rates to match new country
      const smartTaxRate = country === 'Thailand' ? 7 : 0;
      setLineItems(prev => prev.map(item => ({
        ...item,
        tax_rate: smartTaxRate,
        total: item.quantity * item.unit_price * (1 + smartTaxRate / 100),
      })));
    }
  };

  // Handle contract selection with auto-fill
  const handleContractChange = (newContractId: string) => {
    setContractId(newContractId);

    if (!newContractId) return;

    const selectedContract = filteredContracts.find(c => c.id === newContractId);
    if (selectedContract) {
      // Auto-fill currency from contract
      setCurrency(selectedContract.currency);

      // Auto-fill payment terms from contract
      if (selectedContract.payment_terms) {
        const matchedTerms = paymentTermsOptions.find(opt => opt.value === selectedContract.payment_terms);
        setPaymentTerms(matchedTerms ? matchedTerms.value : 'Net 30');
      }

      // Auto-fill first line item from contract (with zone details)
      const smartTaxRate = getSmartTaxRate();
      const billingDesc = selectedContract.billing_frequency || 'Service';
      const contractValue = parseFloat(String(selectedContract.value)) || 0;

      // Build description with zone details
      const activeZones = selectedContract.contract_zones?.filter(z => z.is_active) || [];
      const soundtrackZones = activeZones.filter(z => z.zone_platform === 'soundtrack');
      const beatBreezeZones = activeZones.filter(z => z.zone_platform === 'beatbreeze');

      const zoneCount = activeZones.length || 1;
      const perZonePrice = Math.round((contractValue / zoneCount) * 100) / 100;

      if (soundtrackZones.length > 0 && beatBreezeZones.length > 0) {
        // Mixed contract: create separate line items per service type
        setLineItems([
          {
            description: `Soundtrack Your Brand\n${soundtrackZones.map(z => z.zone_name).join(', ')}`,
            quantity: soundtrackZones.length,
            unit_price: perZonePrice,
            tax_rate: smartTaxRate,
            total: soundtrackZones.length * perZonePrice * (1 + smartTaxRate / 100),
          },
          {
            description: `Beat Breeze\n${beatBreezeZones.map(z => z.zone_name).join(', ')}`,
            quantity: beatBreezeZones.length,
            unit_price: perZonePrice,
            tax_rate: smartTaxRate,
            total: beatBreezeZones.length * perZonePrice * (1 + smartTaxRate / 100),
          },
        ]);
      } else {
        // Single service: one line item
        let description = `${selectedContract.contract_number} - ${billingDesc} Subscription`;
        if (activeZones.length > 0) {
          const serviceName = soundtrackZones.length > 0 ? 'Soundtrack' : 'Beat Breeze';
          description += `\n${serviceName}: ${activeZones.map(z => z.zone_name).join(', ')}`;
        }
        setLineItems([{
          description,
          quantity: zoneCount,
          unit_price: perZonePrice,
          tax_rate: smartTaxRate,
          total: contractValue * (1 + smartTaxRate / 100),
        }]);
      }

      // Auto-fill service period from contract dates
      if (selectedContract.start_date) {
        setServicePeriodStart(new Date(selectedContract.start_date));
      }
      if (selectedContract.end_date) {
        setServicePeriodEnd(new Date(selectedContract.end_date));
      }
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
    // Smart tax rate default based on company country (same as QuoteForm)
    const smartTaxRate = getSmartTaxRate();
    setLineItems([...lineItems, { ...defaultLineItem, tax_rate: smartTaxRate }]);
  };

  const removeLineItem = (index: number) => {
    if (lineItems.length > 1) {
      const updatedItems = lineItems.filter((_, i) => i !== index);
      setLineItems(updatedItems);
    }
  };

  const calculateTotals = () => {
    const subtotal = lineItems.reduce((sum, item) => sum + (Number(item.quantity) * Number(item.unit_price)), 0);
    const taxAmount = lineItems.reduce((sum, item) => sum + (Number(item.quantity) * Number(item.unit_price) * Number(item.tax_rate) / 100), 0);
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
        contract: contractId || null,
        issue_date: issueDate.toISOString().split('T')[0],
        due_date: dueDate.toISOString().split('T')[0],
        service_period_start: servicePeriodStart ? servicePeriodStart.toISOString().split('T')[0] : null,
        service_period_end: servicePeriodEnd ? servicePeriodEnd.toISOString().split('T')[0] : null,
        payment_terms: paymentTerms,
        payment_terms_text: paymentTermsText,
        notes,
        line_items: lineItems.filter(item => item.description.trim()),
        amount: Math.round(totals.subtotal * 100) / 100,
        tax_amount: Math.round(totals.taxAmount * 100) / 100,
        discount_amount: Math.round(discountAmount * 100) / 100,
        total_amount: Math.round(totals.total * 100) / 100,
        currency: currency,
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
      console.error('Invoice save error:', err.response?.data || err.message);
      // Parse DRF field-level errors (e.g. {"company": ["This field is required."]})
      const data = err.response?.data;
      if (data && typeof data === 'object' && !data.message) {
        const messages = Object.entries(data)
          .map(([field, errors]) => `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}`)
          .join('; ');
        setError(messages || 'Failed to save invoice');
      } else {
        setError(data?.message || data?.detail || 'Failed to save invoice');
      }
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number, currencyCode: string = currency): string => {
    // Map currency to locale
    const localeMap: Record<string, string> = {
      'USD': 'en-US',
      'THB': 'th-TH',
      'EUR': 'de-DE',
      'GBP': 'en-GB',
    };

    return new Intl.NumberFormat(localeMap[currencyCode] || 'en-US', {
      style: 'currency',
      currency: currencyCode,
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
      scroll="paper"
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

      <DialogContent ref={dialogContentRef}>
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
                      onChange={(e) => handleCompanyChange(e.target.value)}
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
                  <FormControl fullWidth>
                    <InputLabel>Contract (Optional)</InputLabel>
                    <Select
                      value={contractId}
                      onChange={(e) => handleContractChange(e.target.value)}
                      label="Contract (Optional)"
                      disabled={!companyId}
                    >
                      <MenuItem value="">
                        <em>No Contract (Standalone Invoice)</em>
                      </MenuItem>
                      {filteredContracts.map((contract) => (
                        <MenuItem key={contract.id} value={contract.id}>
                          {contract.contract_number} - {formatCurrency(contract.value, contract.currency)}
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
                <Grid item xs={12} md={6}>
                  <DatePicker
                    label="Service Period Start"
                    value={servicePeriodStart}
                    onChange={setServicePeriodStart}
                    slotProps={{
                      textField: {
                        fullWidth: true,
                        helperText: 'Optional — auto-filled from contract',
                      },
                      field: { clearable: true },
                    }}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <DatePicker
                    label="Service Period End"
                    value={servicePeriodEnd}
                    onChange={setServicePeriodEnd}
                    slotProps={{
                      textField: {
                        fullWidth: true,
                        helperText: 'Optional — auto-filled from contract',
                      },
                      field: { clearable: true },
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
                      <TableCell width="90">Qty</TableCell>
                      <TableCell width="160">Unit Price</TableCell>
                      <TableCell width="90">{getTaxLabel().replace(':', '')} (%)</TableCell>
                      <TableCell width="150">Total</TableCell>
                      <TableCell width="50">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {lineItems.map((item, index) => (
                      <TableRow key={index}>
                        <TableCell>
                          <TextField
                            fullWidth
                            size="small"
                            multiline
                            minRows={1}
                            maxRows={3}
                            value={item.description}
                            onChange={(e) => handleLineItemChange(index, 'description', e.target.value)}
                            placeholder="Enter description..."
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            value={Math.round(item.quantity)}
                            onChange={(e) => handleLineItemChange(index, 'quantity', parseInt(e.target.value) || 0)}
                            inputProps={{ min: 0, step: 1 }}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="text"
                            value={focusedPriceIndex === index
                              ? item.unit_price
                              : new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(item.unit_price)
                            }
                            onChange={(e) => {
                              const cleaned = e.target.value.replace(/[^0-9.]/g, '');
                              handleLineItemChange(index, 'unit_price', parseFloat(cleaned) || 0);
                            }}
                            onFocus={() => setFocusedPriceIndex(index)}
                            onBlur={() => setFocusedPriceIndex(null)}
                            InputProps={{
                              startAdornment: <InputAdornment position="start">{getCurrencySymbol(currency)}</InputAdornment>,
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            value={Math.round(item.tax_rate)}
                            onChange={(e) => handleLineItemChange(index, 'tax_rate', parseInt(e.target.value) || 0)}
                            inputProps={{ min: 0, max: 100, step: 1 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight="medium">
                            {formatCurrency(item.total, currency)}
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
                      startAdornment: <InputAdornment position="start">{getCurrencySymbol(currency)}</InputAdornment>,
                    }}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <Box sx={{ mt: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">Subtotal:</Typography>
                      <Typography variant="body2">{formatCurrency(totals.subtotal, currency)}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">{getTaxLabel()}</Typography>
                      <Typography variant="body2">{formatCurrency(totals.taxAmount, currency)}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">Discount:</Typography>
                      <Typography variant="body2" color="error">
                        -{formatCurrency(discountAmount, currency)}
                      </Typography>
                    </Box>
                    <Divider sx={{ my: 1 }} />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="h6">Total:</Typography>
                      <Typography variant="h6" color="primary">
                        {formatCurrency(totals.total, currency)}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>
              </Grid>
            </Paper>

            {/* Payment Terms Text + Notes */}
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Payment Terms & Notes
              </Typography>
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Payment Terms (shown on PDF)"
                    value={paymentTermsText}
                    onChange={(e) => setPaymentTermsText(e.target.value)}
                    multiline
                    rows={3}
                    placeholder="Auto-filled from company defaults. Override with custom terms if needed..."
                    helperText="Optional — leave blank to use default bank transfer instructions on PDF."
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    multiline
                    rows={3}
                    placeholder="Additional notes..."
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
