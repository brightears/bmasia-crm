import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Divider,
  Alert,
  CircularProgress,
  GridLegacy as Grid,
  InputAdornment,
  Chip,
} from '@mui/material';
import {
  Add,
  Delete,
  AttachMoney,
  Percent,
  Calculate,
  Business,
  Person,
  Assignment,
  CloudUpload,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV2';
import { Quote, QuoteLineItem, Company, Contact, Opportunity } from '../types';
import ApiService from '../services/api';

interface QuoteFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (quote: Quote) => void;
  quote?: Quote | null;
  mode: 'create' | 'edit';
  companies: Company[];
  contacts: Contact[];
  opportunities: Opportunity[];
}

const QuoteForm: React.FC<QuoteFormProps> = ({
  open,
  onClose,
  onSave,
  quote,
  mode,
  companies,
  contacts,
  opportunities
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    quote_number: '',
    company: '',
    contact: '',
    opportunity: '',
    status: 'Draft' as Quote['status'],
    valid_from: new Date(),
    valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days from now
    terms_conditions: 'Payment is due within 30 days of acceptance. All prices are in USD. This quote is valid for the specified period.',
    notes: '',
    currency: 'USD',
  });

  const [lineItems, setLineItems] = useState<QuoteLineItem[]>([
    {
      product_service: 'Soundtrack Essential (Serviced)',
      description: 'Monthly subscription for background music service with professional curation',
      quantity: 1,
      unit_price: 50.00,
      discount_percentage: 0,
      tax_rate: 7.5,
      line_total: 50.00,
    }
  ]);

  const [filteredContacts, setFilteredContacts] = useState<Contact[]>([]);
  const [attachments, setAttachments] = useState<File[]>([]);

  useEffect(() => {
    if (open) {
      if (mode === 'edit' && quote) {
        setFormData({
          quote_number: quote.quote_number,
          company: quote.company,
          contact: quote.contact || '',
          opportunity: quote.opportunity || '',
          status: quote.status,
          valid_from: new Date(quote.valid_from),
          valid_until: new Date(quote.valid_until),
          terms_conditions: quote.terms_conditions || '',
          notes: quote.notes || '',
          currency: quote.currency,
        });
        setLineItems(quote.line_items || []);
      } else {
        // Generate quote number for new quotes
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const random = String(Math.floor(Math.random() * 1000)).padStart(3, '0');
        const quoteNumber = `Q-${year}-${month}${day}-${random}`;

        setFormData(prev => ({
          ...prev,
          quote_number: quoteNumber,
        }));
      }
    }
  }, [open, mode, quote]);

  useEffect(() => {
    if (formData.company) {
      const companyContacts = contacts.filter(contact => contact.company === formData.company);
      setFilteredContacts(companyContacts);

      // Clear contact if it's not from the selected company
      if (formData.contact && !companyContacts.find(c => c.id === formData.contact)) {
        setFormData(prev => ({ ...prev, contact: '' }));
      }
    } else {
      setFilteredContacts([]);
      setFormData(prev => ({ ...prev, contact: '' }));
    }
  }, [formData.company, contacts]);

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const addLineItem = () => {
    setLineItems(prev => [...prev, {
      product_service: '',
      description: '',
      quantity: 1,
      unit_price: 0,
      discount_percentage: 0,
      tax_rate: 7.5,
      line_total: 0,
    }]);
  };

  const removeLineItem = (index: number) => {
    if (lineItems.length > 1) {
      setLineItems(prev => prev.filter((_, i) => i !== index));
    }
  };

  const updateLineItem = (index: number, field: keyof QuoteLineItem, value: any) => {
    setLineItems(prev => {
      const newItems = [...prev];
      newItems[index] = { ...newItems[index], [field]: value };

      // Recalculate line total when quantity, unit_price, or discount_percentage changes
      if (field === 'quantity' || field === 'unit_price' || field === 'discount_percentage') {
        const item = newItems[index];
        const subtotal = item.quantity * item.unit_price;
        const discountAmount = subtotal * (item.discount_percentage / 100);
        const afterDiscount = subtotal - discountAmount;
        newItems[index].line_total = afterDiscount;
      }

      return newItems;
    });
  };

  const calculateTotals = () => {
    const subtotal = lineItems.reduce((sum, item) => {
      const itemSubtotal = item.quantity * item.unit_price;
      const discountAmount = itemSubtotal * (item.discount_percentage / 100);
      return sum + (itemSubtotal - discountAmount);
    }, 0);

    const totalTaxAmount = lineItems.reduce((sum, item) => {
      const itemSubtotal = item.quantity * item.unit_price;
      const discountAmount = itemSubtotal * (item.discount_percentage / 100);
      const afterDiscount = itemSubtotal - discountAmount;
      const taxAmount = afterDiscount * (item.tax_rate / 100);
      return sum + taxAmount;
    }, 0);

    const totalDiscountAmount = lineItems.reduce((sum, item) => {
      const itemSubtotal = item.quantity * item.unit_price;
      const discountAmount = itemSubtotal * (item.discount_percentage / 100);
      return sum + discountAmount;
    }, 0);

    const total = subtotal + totalTaxAmount;

    return {
      subtotal,
      taxAmount: totalTaxAmount,
      discountAmount: totalDiscountAmount,
      total
    };
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setAttachments(prev => [...prev, ...Array.from(event.target.files!)]);
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setError('');

      const totals = calculateTotals();

      const quoteData: Partial<Quote> = {
        quote_number: formData.quote_number,
        company: formData.company,
        contact: formData.contact || undefined,
        opportunity: formData.opportunity || undefined,
        status: formData.status,
        valid_from: formData.valid_from.toISOString().split('T')[0],
        valid_until: formData.valid_until.toISOString().split('T')[0],
        subtotal: totals.subtotal,
        tax_amount: totals.taxAmount,
        discount_amount: totals.discountAmount,
        total_value: totals.total,
        currency: formData.currency,
        terms_conditions: formData.terms_conditions,
        notes: formData.notes,
        line_items: lineItems,
      };

      let savedQuote: Quote;

      if (mode === 'edit' && quote) {
        savedQuote = await ApiService.updateQuote(quote.id, quoteData);
      } else {
        savedQuote = await ApiService.createQuote(quoteData);
      }

      // Upload attachments if any
      if (attachments.length > 0 && savedQuote.id) {
        for (const file of attachments) {
          try {
            await ApiService.addQuoteAttachment(savedQuote.id, file);
          } catch (err) {
            console.error('Failed to upload attachment:', err);
          }
        }
      }

      onSave(savedQuote);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save quote');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setFormData({
      quote_number: '',
      company: '',
      contact: '',
      opportunity: '',
      status: 'Draft',
      valid_from: new Date(),
      valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
      terms_conditions: 'Payment is due within 30 days of acceptance. All prices are in USD. This quote is valid for the specified period.',
      notes: '',
      currency: 'USD',
    });
    setLineItems([{
      product_service: 'Soundtrack Essential (Serviced)',
      description: 'Monthly subscription for background music service with professional curation',
      quantity: 1,
      unit_price: 50.00,
      discount_percentage: 0,
      tax_rate: 7.5,
      line_total: 50.00,
    }]);
    setAttachments([]);
    setError('');
    onClose();
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: formData.currency,
      minimumFractionDigits: 2,
    }).format(value);
  };

  const totals = calculateTotals();

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Dialog open={open} onClose={handleClose} maxWidth="xl" fullWidth>
        <DialogTitle>
          {mode === 'create' ? 'Create New Quote' : 'Edit Quote'}
        </DialogTitle>
        <DialogContent sx={{ pb: 1 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Grid container spacing={3}>
            {/* Basic Information */}
            <Grid item xs={12}>
              <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
                <Assignment sx={{ mr: 1 }} />
                Quote Information
              </Typography>
            </Grid>

            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Quote Number"
                value={formData.quote_number}
                onChange={(e) => handleInputChange('quote_number', e.target.value)}
                disabled
                required
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControl fullWidth required>
                <InputLabel>Company</InputLabel>
                <Select
                  value={formData.company}
                  onChange={(e) => handleInputChange('company', e.target.value)}
                  label="Company"
                >
                  {companies.map((company) => (
                    <MenuItem key={company.id} value={company.id}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Business sx={{ mr: 1, fontSize: 16 }} />
                        {company.name}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Contact</InputLabel>
                <Select
                  value={formData.contact}
                  onChange={(e) => handleInputChange('contact', e.target.value)}
                  label="Contact"
                  disabled={!formData.company}
                >
                  {filteredContacts.map((contact) => (
                    <MenuItem key={contact.id} value={contact.id}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Person sx={{ mr: 1, fontSize: 16 }} />
                        {contact.name} - {contact.title}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Opportunity</InputLabel>
                <Select
                  value={formData.opportunity}
                  onChange={(e) => handleInputChange('opportunity', e.target.value)}
                  label="Opportunity"
                >
                  {opportunities
                    .filter(opp => !formData.company || opp.company === formData.company)
                    .map((opportunity) => (
                      <MenuItem key={opportunity.id} value={opportunity.id}>
                        {opportunity.name}
                      </MenuItem>
                    ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select
                  value={formData.status}
                  onChange={(e) => handleInputChange('status', e.target.value)}
                  label="Status"
                >
                  <MenuItem value="Draft">Draft</MenuItem>
                  <MenuItem value="Sent">Sent</MenuItem>
                  <MenuItem value="Accepted">Accepted</MenuItem>
                  <MenuItem value="Rejected">Rejected</MenuItem>
                  <MenuItem value="Expired">Expired</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={3}>
              <DatePicker
                label="Valid From"
                value={formData.valid_from}
                onChange={(date) => handleInputChange('valid_from', date)}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    required: true,
                  },
                }}
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <DatePicker
                label="Valid Until"
                value={formData.valid_until}
                onChange={(date) => handleInputChange('valid_until', date)}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    required: true,
                  },
                }}
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Currency</InputLabel>
                <Select
                  value={formData.currency}
                  onChange={(e) => handleInputChange('currency', e.target.value)}
                  label="Currency"
                >
                  <MenuItem value="USD">USD</MenuItem>
                  <MenuItem value="THB">THB</MenuItem>
                  <MenuItem value="EUR">EUR</MenuItem>
                  <MenuItem value="GBP">GBP</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Line Items */}
            <Grid item xs={12}>
              <Box sx={{ mt: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center' }}>
                    <Calculate sx={{ mr: 1 }} />
                    Line Items
                  </Typography>
                  <Button
                    variant="outlined"
                    startIcon={<Add />}
                    onClick={addLineItem}
                    size="small"
                  >
                    Add Line Item
                  </Button>
                </Box>

                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Product/Service</TableCell>
                        <TableCell>Description</TableCell>
                        <TableCell width="80px">Qty</TableCell>
                        <TableCell width="120px">Unit Price</TableCell>
                        <TableCell width="100px">Discount %</TableCell>
                        <TableCell width="100px">Tax %</TableCell>
                        <TableCell width="120px">Line Total</TableCell>
                        <TableCell width="50px">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {lineItems.map((item, index) => (
                        <TableRow key={index}>
                          <TableCell>
                            <TextField
                              fullWidth
                              size="small"
                              value={item.product_service}
                              onChange={(e) => updateLineItem(index, 'product_service', e.target.value)}
                              placeholder="Product/Service name"
                            />
                          </TableCell>
                          <TableCell>
                            <TextField
                              fullWidth
                              size="small"
                              multiline
                              rows={2}
                              value={item.description}
                              onChange={(e) => updateLineItem(index, 'description', e.target.value)}
                              placeholder="Description"
                            />
                          </TableCell>
                          <TableCell>
                            <TextField
                              size="small"
                              type="number"
                              value={item.quantity}
                              onChange={(e) => updateLineItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                              inputProps={{ min: 0, step: 1 }}
                            />
                          </TableCell>
                          <TableCell>
                            <TextField
                              size="small"
                              type="number"
                              value={item.unit_price}
                              onChange={(e) => updateLineItem(index, 'unit_price', parseFloat(e.target.value) || 0)}
                              inputProps={{ min: 0, step: 0.01 }}
                              InputProps={{
                                startAdornment: <InputAdornment position="start"><AttachMoney sx={{ fontSize: 14 }} /></InputAdornment>,
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <TextField
                              size="small"
                              type="number"
                              value={item.discount_percentage}
                              onChange={(e) => updateLineItem(index, 'discount_percentage', parseFloat(e.target.value) || 0)}
                              inputProps={{ min: 0, max: 100, step: 0.1 }}
                              InputProps={{
                                endAdornment: <InputAdornment position="end"><Percent sx={{ fontSize: 14 }} /></InputAdornment>,
                              }}
                              sx={{
                                minWidth: '90px',
                                '& input': {
                                  textAlign: 'center',
                                  paddingRight: '8px',
                                  color: 'text.primary',
                                  fontWeight: 500,
                                },
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <TextField
                              size="small"
                              type="number"
                              value={item.tax_rate}
                              onChange={(e) => updateLineItem(index, 'tax_rate', parseFloat(e.target.value) || 0)}
                              inputProps={{ min: 0, max: 100, step: 0.1 }}
                              InputProps={{
                                endAdornment: <InputAdornment position="end"><Percent sx={{ fontSize: 14 }} /></InputAdornment>,
                              }}
                              sx={{
                                minWidth: '90px',
                                '& input': {
                                  textAlign: 'center',
                                  paddingRight: '8px',
                                  color: 'text.primary',
                                  fontWeight: 500,
                                },
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight="medium">
                              {formatCurrency(item.line_total)}
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

                {/* Totals */}
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                  <Paper sx={{ p: 2, minWidth: 300 }}>
                    <Grid container spacing={1}>
                      <Grid item xs={6}>
                        <Typography variant="body2">Subtotal:</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" align="right">
                          {formatCurrency(totals.subtotal)}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2">Discount:</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" align="right" color="error.main">
                          -{formatCurrency(totals.discountAmount)}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2">Tax:</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" align="right">
                          {formatCurrency(totals.taxAmount)}
                        </Typography>
                      </Grid>
                      <Divider sx={{ width: '100%', my: 1 }} />
                      <Grid item xs={6}>
                        <Typography variant="h6">Total:</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="h6" align="right">
                          {formatCurrency(totals.total)}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Paper>
                </Box>
              </Box>
            </Grid>

            {/* Terms and Notes */}
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Terms & Conditions"
                value={formData.terms_conditions}
                onChange={(e) => handleInputChange('terms_conditions', e.target.value)}
                multiline
                rows={4}
                placeholder="Enter terms and conditions..."
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Notes"
                value={formData.notes}
                onChange={(e) => handleInputChange('notes', e.target.value)}
                multiline
                rows={4}
                placeholder="Internal notes..."
              />
            </Grid>

            {/* Attachments */}
            <Grid item xs={12}>
              <Box>
                <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
                  <CloudUpload sx={{ mr: 1 }} />
                  Attachments
                </Typography>

                <input
                  accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"
                  style={{ display: 'none' }}
                  id="attachment-upload"
                  type="file"
                  multiple
                  onChange={handleFileUpload}
                />
                <label htmlFor="attachment-upload">
                  <Button variant="outlined" component="span" startIcon={<CloudUpload />}>
                    Upload Files
                  </Button>
                </label>

                {attachments.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    {attachments.map((file, index) => (
                      <Chip
                        key={index}
                        label={`${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`}
                        onDelete={() => removeAttachment(index)}
                        sx={{ mr: 1, mb: 1 }}
                      />
                    ))}
                  </Box>
                )}
              </Box>
            </Grid>
          </Grid>
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={loading || !formData.company || lineItems.length === 0}
            startIcon={loading ? <CircularProgress size={16} /> : null}
          >
            {loading ? 'Saving...' : mode === 'create' ? 'Create Quote' : 'Update Quote'}
          </Button>
        </DialogActions>
      </Dialog>
    </LocalizationProvider>
  );
};

export default QuoteForm;