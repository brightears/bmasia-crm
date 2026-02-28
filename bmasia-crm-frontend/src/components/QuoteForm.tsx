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
  Percent,
  Calculate,
  Business,
  Person,
  Assignment,
  CloudUpload,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Quote, QuoteLineItem, Company, Contact, Opportunity } from '../types';
import ApiService from '../services/api';

// Product options for dropdown
const PRODUCT_OPTIONS = [
  {
    code: 'soundtrack_essential',
    name: 'Soundtrack Your Brand',
    description: `• 100+ million tracks
• Personalized music design and support services
• Custom API solutions
• AI-powered content management`,
    thailandOnly: false,
  },
  {
    code: 'beat_breeze',
    name: 'Beat Breeze',
    description: `• 100,000+ tracks
• Public performance licenses included
• Personalized music design
• Dedicated technical support services`,
    thailandOnly: false,
  },
  {
    code: 'mini_pc',
    name: 'Windows Mini PC',
    description: 'Windows Mini PC',
    thailandOnly: true,
  },
  {
    code: 'soundtrack_player',
    name: 'Soundtrack Player',
    description: `• Includes a 1-year warranty
• Shipping costs covered
• Customs fees to be paid by the receiver`,
    thailandOnly: false,
  },
  {
    code: 'custom',
    name: 'Custom (Manual Entry)',
    description: '',
    thailandOnly: false,
  },
];

// Terms & Conditions options for dropdown
const TERMS_OPTIONS = [
  {
    code: '30_days',
    label: 'Payment due within 30 days',
    text: 'Payment is due within 30 days of acceptance. This quote is valid for the specified period.',
  },
  {
    code: 'upon_receipt',
    label: 'Payment due upon receipt',
    text: 'Payment is due immediately upon receiving invoice and before activating subscription. All payments are to be paid on a net received basis. This quote is valid for the specified period.',
  },
  {
    code: 'custom',
    label: 'Custom (Manual Entry)',
    text: '',
  },
];

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
    quote_type: 'new' as 'new' | 'renewal' | 'addon',
    contract_duration_months: 12,
    status: 'Draft' as Quote['status'],
    valid_from: new Date(),
    valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days from now
    terms_conditions: TERMS_OPTIONS.find(t => t.code === '30_days')?.text || 'Payment is due within 30 days of acceptance. This quote is valid for the specified period.',
    notes: '',
    currency: 'USD',
  });

  const defaultProduct = PRODUCT_OPTIONS.find(p => p.code === 'soundtrack_essential');
  const [lineItems, setLineItems] = useState<QuoteLineItem[]>([
    {
      product_service: defaultProduct?.name || 'Soundtrack Essential (Serviced)',
      description: defaultProduct?.description || '',
      quantity: 1,
      unit_price: 50.00,
      discount_percentage: 0,
      tax_rate: 7,
      line_total: 50.00,
    }
  ]);

  const [filteredContacts, setFilteredContacts] = useState<Contact[]>([]);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [selectedCompanyCountry, setSelectedCompanyCountry] = useState<string>('');
  const [selectedTermsOption, setSelectedTermsOption] = useState<string>('30_days');
  const [isCustomDuration, setIsCustomDuration] = useState(false);

  const DURATION_PRESETS = [
    { label: '6 months', months: 6 },
    { label: '1 year', months: 12 },
    { label: '2 years', months: 24 },
    { label: '3 years', months: 36 },
  ];

  useEffect(() => {
    if (open) {
      if (mode === 'edit' && quote) {
        setFormData({
          quote_number: quote.quote_number,
          company: quote.company,
          contact: quote.contact || '',
          opportunity: quote.opportunity || '',
          quote_type: quote.quote_type || 'new',
          contract_duration_months: quote.contract_duration_months || 12,
          status: quote.status,
          valid_from: new Date(quote.valid_from),
          valid_until: new Date(quote.valid_until),
          terms_conditions: quote.terms_conditions || '',
          notes: quote.notes || '',
          currency: quote.currency,
        });
        setLineItems(quote.line_items || []);

        // Detect if duration matches a preset
        const dur = quote.contract_duration_months || 12;
        const isPreset = [6, 12, 24, 36].includes(dur);
        setIsCustomDuration(!isPreset);

        // Detect terms option from existing text
        const existingTerms = quote.terms_conditions || '';
        const matchedTerms = TERMS_OPTIONS.find(opt => opt.text === existingTerms);
        setSelectedTermsOption(matchedTerms ? matchedTerms.code : 'custom');

        // Set company country for Mini PC visibility
        const editCompany = companies.find(c => c.id === quote.company);
        if (editCompany) {
          setSelectedCompanyCountry(editCompany.country || '');
        }
      } else {
        // Generate quote number for new quotes
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const random = String(Math.floor(Math.random() * 1000)).padStart(3, '0');
        const quoteNumber = `Q-${year}-${month}${day}-${random}`;

        // Pre-fill company and opportunity from query params (via quote prop)
        const prefillCompany = quote?.company || '';
        const prefillOpportunity = quote?.opportunity || '';

        setFormData(prev => ({
          ...prev,
          quote_number: quoteNumber,
          company: prefillCompany,
          opportunity: prefillOpportunity,
          contract_duration_months: 12,
        }));
        setIsCustomDuration(false);

        // Set company country for Mini PC visibility
        if (prefillCompany) {
          const prefillComp = companies.find(c => c.id === prefillCompany);
          if (prefillComp) {
            setSelectedCompanyCountry(prefillComp.country || '');
          }
        }
      }
    }
  }, [open, mode, quote, companies]);

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
    // Handle company selection with smart defaults
    if (field === 'company') {
      const selectedCompany = companies.find(c => c.id === value);
      if (selectedCompany) {
        const country = selectedCompany.country || '';
        setSelectedCompanyCountry(country);

        // Smart currency default based on country
        const smartCurrency = country === 'Thailand' ? 'THB' : 'USD';

        setFormData(prev => ({
          ...prev,
          company: value,
          currency: smartCurrency
        }));
        return;
      }
    }

    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const addLineItem = () => {
    // Smart tax rate default based on company country
    const smartTaxRate = selectedCompanyCountry === 'Thailand' ? 7 : 0;

    setLineItems(prev => [...prev, {
      product_service: '',
      description: '',
      quantity: 1,
      unit_price: 0,
      discount_percentage: 0,
      tax_rate: smartTaxRate,
      line_total: 0,
    }]);
  };

  const removeLineItem = (index: number) => {
    if (lineItems.length > 1) {
      setLineItems(prev => prev.filter((_, i) => i !== index));
    }
  };

  const updateLineItem = (index: number, field: keyof QuoteLineItem | 'product_code', value: any) => {
    setLineItems(prev => {
      const newItems = [...prev];

      // Handle product selection from dropdown
      if (field === 'product_code') {
        const product = PRODUCT_OPTIONS.find(p => p.code === value);
        if (product && product.code !== 'custom') {
          newItems[index] = {
            ...newItems[index],
            product_service: product.name,
            description: product.description,
          };
        }
        return newItems;
      }

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

  // Get available products based on company country (Mini PC = Thailand only)
  const getAvailableProducts = () => {
    return PRODUCT_OPTIONS.filter(product =>
      !product.thailandOnly || selectedCompanyCountry === 'Thailand'
    );
  };

  // Handle terms option change
  const handleTermsChange = (optionCode: string) => {
    setSelectedTermsOption(optionCode);
    const option = TERMS_OPTIONS.find(t => t.code === optionCode);
    if (option && option.code !== 'custom') {
      setFormData(prev => ({ ...prev, terms_conditions: option.text }));
    }
  };

  const calculateTotals = () => {
    // Helper function to round to 2 decimal places to avoid floating-point precision errors
    const roundTo2Decimals = (value: number): number => {
      return Math.round(value * 100) / 100;
    };

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
      subtotal: roundTo2Decimals(subtotal),
      taxAmount: roundTo2Decimals(totalTaxAmount),
      discountAmount: roundTo2Decimals(totalDiscountAmount),
      total: roundTo2Decimals(total)
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

      // Strip read-only fields from line items before sending
      const cleanLineItems = lineItems.map(item => ({
        product_service: item.product_service,
        description: item.description,
        quantity: item.quantity,
        unit_price: item.unit_price,
        discount_percentage: item.discount_percentage,
        tax_rate: item.tax_rate,
      }));

      const quoteData: Partial<Quote> = {
        quote_number: formData.quote_number,
        company: formData.company,
        contact: formData.contact || undefined,
        opportunity: formData.opportunity || undefined,
        quote_type: formData.quote_type,
        contract_duration_months: formData.contract_duration_months,
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
        line_items: cleanLineItems as any,
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
    const defaultTerms = TERMS_OPTIONS.find(t => t.code === '30_days')?.text || '';

    setFormData({
      quote_number: '',
      company: '',
      contact: '',
      opportunity: '',
      quote_type: 'new' as 'new' | 'renewal' | 'addon',
      contract_duration_months: 12,
      status: 'Draft',
      valid_from: new Date(),
      valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
      terms_conditions: defaultTerms,
      notes: '',
      currency: 'USD',
    });
    setIsCustomDuration(false);
    setLineItems([{
      product_service: defaultProduct?.name || 'Soundtrack Essential (Serviced)',
      description: defaultProduct?.description || '',
      quantity: 1,
      unit_price: 50.00,
      discount_percentage: 0,
      tax_rate: 7,
      line_total: 50.00,
    }]);
    setAttachments([]);
    setSelectedTermsOption('30_days');
    setSelectedCompanyCountry('');
    setError('');
    onClose();
  };

  const getCurrencySymbol = (currency: string): string => {
    const symbols: { [key: string]: string } = {
      'USD': '$',
      'THB': '฿',
      'EUR': '€',
      'GBP': '£'
    };
    return symbols[currency] || currency;
  };

  const formatCurrency = (value: number): string => {
    // Currency locale mapping for proper symbol display
    const currencyLocaleMap: { [key: string]: string } = {
      'USD': 'en-US',
      'THB': 'th-TH',
      'EUR': 'de-DE',
      'GBP': 'en-GB'
    };

    return new Intl.NumberFormat(currencyLocaleMap[formData.currency] || 'en-US', {
      style: 'currency',
      currency: formData.currency,
      minimumFractionDigits: 2,
    }).format(value);
  };

  const totals = calculateTotals();

  // Determine tax label based on company country or billing entity
  const getTaxLabel = (): string => {
    const selectedCompany = companies.find(c => c.id === formData.company);
    if (selectedCompany) {
      // Check if Thailand or if billing entity is Thailand
      if (selectedCompanyCountry === 'Thailand' ||
          selectedCompany.billing_entity?.includes('Thailand')) {
        return 'VAT:';
      }
    }
    return 'Tax:';
  };

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
                <InputLabel>Quote Type *</InputLabel>
                <Select
                  value={formData.quote_type}
                  onChange={(e) => {
                    const newType = e.target.value;
                    setFormData(prev => ({
                      ...prev,
                      quote_type: newType as 'new' | 'renewal' | 'addon',
                      opportunity: newType === 'renewal' ? '' : prev.opportunity,
                    }));
                  }}
                  label="Quote Type *"
                >
                  <MenuItem value="new">New Business</MenuItem>
                  <MenuItem value="renewal">Renewal</MenuItem>
                  <MenuItem value="addon">Add-on</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {formData.quote_type !== 'renewal' && (
              <Grid item xs={12} md={3}>
                <FormControl fullWidth>
                  <InputLabel>Opportunity</InputLabel>
                  <Select
                    value={formData.opportunity}
                    onChange={(e) => handleInputChange('opportunity', e.target.value)}
                    label="Opportunity"
                  >
                    <MenuItem value="">
                      <em>Auto-create new</em>
                    </MenuItem>
                    {opportunities
                      .filter(opp => !formData.company || opp.company === formData.company)
                      .map((opportunity) => (
                        <MenuItem key={opportunity.id} value={opportunity.id}>
                          {opportunity.name}
                        </MenuItem>
                      ))}
                  </Select>
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, ml: 1.5 }}>
                    Leave empty to auto-create an opportunity
                  </Typography>
                </FormControl>
              </Grid>
            )}

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
              <FormControl fullWidth>
                <InputLabel>Contract Duration</InputLabel>
                <Select
                  value={isCustomDuration ? 'custom' : String(formData.contract_duration_months)}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === 'custom') {
                      setIsCustomDuration(true);
                    } else {
                      setIsCustomDuration(false);
                      setFormData(prev => ({ ...prev, contract_duration_months: Number(val) }));
                    }
                  }}
                  label="Contract Duration"
                >
                  {DURATION_PRESETS.map(p => (
                    <MenuItem key={p.months} value={String(p.months)}>{p.label}</MenuItem>
                  ))}
                  <MenuItem value="custom">Custom</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {isCustomDuration && (
              <Grid item xs={12} md={3}>
                <TextField
                  fullWidth
                  label="Duration (months)"
                  type="number"
                  value={formData.contract_duration_months}
                  onChange={(e) => {
                    const val = Math.max(1, parseInt(e.target.value) || 1);
                    setFormData(prev => ({ ...prev, contract_duration_months: val }));
                  }}
                  inputProps={{ min: 1, max: 120 }}
                />
              </Grid>
            )}

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
                          <TableCell sx={{ minWidth: 200 }}>
                            <FormControl fullWidth size="small">
                              <Select
                                value={
                                  PRODUCT_OPTIONS.find(p => p.name === item.product_service)?.code || 'custom'
                                }
                                onChange={(e) => {
                                  const code = e.target.value;
                                  updateLineItem(index, 'product_code', code);
                                  // If custom is selected, clear the product_service to let user type
                                  if (code === 'custom') {
                                    updateLineItem(index, 'product_service', '');
                                  }
                                }}
                                displayEmpty
                              >
                                {getAvailableProducts().map((product) => (
                                  <MenuItem key={product.code} value={product.code}>
                                    {product.name}
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                            {/* Show text field for custom entry */}
                            {!PRODUCT_OPTIONS.find(p => p.name === item.product_service) && (
                              <TextField
                                fullWidth
                                size="small"
                                value={item.product_service}
                                onChange={(e) => updateLineItem(index, 'product_service', e.target.value)}
                                placeholder="Enter product/service name"
                                sx={{ mt: 1 }}
                              />
                            )}
                          </TableCell>
                          <TableCell>
                            <TextField
                              fullWidth
                              size="small"
                              multiline
                              rows={2}
                              value={item.description}
                              onChange={(e) => updateLineItem(index, 'description', e.target.value)}
                              placeholder="Description (auto-filled from product selection)"
                            />
                          </TableCell>
                          <TableCell>
                            <TextField
                              size="small"
                              type="number"
                              value={item.quantity}
                              onChange={(e) => updateLineItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                              inputProps={{ min: 0, step: 1 }}
                              sx={{
                                '& input::-webkit-outer-spin-button, & input::-webkit-inner-spin-button': {
                                  WebkitAppearance: 'none', margin: 0
                                },
                                '& input[type=number]': { MozAppearance: 'textfield' }
                              }}
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
                                startAdornment: (
                                  <InputAdornment position="start">
                                    <Typography variant="body2" sx={{ fontSize: 14, fontWeight: 500 }}>
                                      {getCurrencySymbol(formData.currency)}
                                    </Typography>
                                  </InputAdornment>
                                ),
                              }}
                              sx={{
                                '& input::-webkit-outer-spin-button, & input::-webkit-inner-spin-button': {
                                  WebkitAppearance: 'none', margin: 0
                                },
                                '& input[type=number]': { MozAppearance: 'textfield' }
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
                                '& input::-webkit-outer-spin-button, & input::-webkit-inner-spin-button': {
                                  WebkitAppearance: 'none', margin: 0
                                },
                                '& input[type=number]': { MozAppearance: 'textfield' }
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <TextField
                              size="small"
                              type="number"
                              value={item.tax_rate}
                              onChange={(e) => updateLineItem(index, 'tax_rate', parseInt(e.target.value) || 0)}
                              inputProps={{ min: 0, max: 100, step: 1 }}
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
                                '& input[type=number]': {
                                  MozAppearance: 'textfield',
                                },
                                '& input[type=number]::-webkit-outer-spin-button': {
                                  WebkitAppearance: 'none',
                                  margin: 0,
                                },
                                '& input[type=number]::-webkit-inner-spin-button': {
                                  WebkitAppearance: 'none',
                                  margin: 0,
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
                        <Typography variant="body2">{getTaxLabel()}</Typography>
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
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Terms & Conditions</InputLabel>
                <Select
                  value={selectedTermsOption}
                  onChange={(e) => handleTermsChange(e.target.value)}
                  label="Terms & Conditions"
                >
                  {TERMS_OPTIONS.map((option) => (
                    <MenuItem key={option.code} value={option.code}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                fullWidth
                label={selectedTermsOption === 'custom' ? 'Custom Terms' : 'Terms Preview'}
                value={formData.terms_conditions}
                onChange={(e) => handleInputChange('terms_conditions', e.target.value)}
                multiline
                rows={3}
                placeholder="Enter custom terms and conditions..."
                disabled={selectedTermsOption !== 'custom'}
                InputProps={{
                  readOnly: selectedTermsOption !== 'custom',
                }}
                sx={{
                  '& .MuiInputBase-input.Mui-disabled': {
                    WebkitTextFillColor: 'rgba(0, 0, 0, 0.6)',
                  },
                }}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Notes (shown on PDF)"
                value={formData.notes}
                onChange={(e) => handleInputChange('notes', e.target.value)}
                multiline
                rows={4}
                placeholder="e.g., Zone added prorated on top of existing zones..."
                helperText="Optional — visible to the client on the quote PDF"
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