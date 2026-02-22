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
  Autocomplete,
  Box,
  Typography,
  Alert,
  CircularProgress,
  FormControlLabel,
  Switch,
  InputAdornment,
  Divider,
  IconButton,
  Stack,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  AttachFile,
  Close,
  Delete,
  CalendarToday,
  LocationOn as LocationOnIcon,
  Add as AddIcon,
  Calculate,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Contract, Company, ApiResponse, ContractTemplate, ContractLineItem, Quote } from '../types';
import ApiService from '../services/api';

interface ContractFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (contract: Contract) => void;
  contract: Contract | null;
  mode: 'create' | 'edit';
  initialCompanyId?: string;
  initialQuoteId?: string;
}

interface ServiceLocationEntry {
  location_name: string;
  platform: 'soundtrack' | 'beatbreeze';
  tempId: string;
}

const contractStatuses = [
  'Draft',
  'Sent',
  'Active',
  'Renewed',
  'Expired',
  'Cancelled'
];

const contractTypes = [
  'Annual',
  'Monthly',
  'One-time',
  'Custom'
];

const billingFrequencies = [
  'Monthly',
  'Quarterly',
  'Semi-annually',
  'Annually',
  'One-time'
];

const currencies = [
  'USD',
  'THB',
  'EUR',
  'GBP'
];

const paymentTermsOptions = [
  'Net 15',
  'Net 30',
  'Net 45',
  'Net 60',
  'Due on Receipt',
  'COD',
  'Prepaid'
];

// Product options (same as QuoteForm)
const PRODUCT_OPTIONS = [
  {
    code: 'soundtrack_essential',
    name: 'Soundtrack Your Brand',
    description: `• 100+ million tracks
• Personalized music design and support services
• Custom API solutions
• AI-powered content management`,
    thailandOnly: false,
    platform: 'soundtrack' as 'soundtrack' | 'beatbreeze',
  },
  {
    code: 'beat_breeze',
    name: 'Beat Breeze',
    description: `• 100,000+ tracks
• Public performance licenses included
• Personalized music design
• Dedicated technical support services`,
    thailandOnly: false,
    platform: 'beatbreeze' as 'soundtrack' | 'beatbreeze',
  },
  {
    code: 'mini_pc',
    name: 'Windows Mini PC',
    description: 'Windows Mini PC',
    thailandOnly: true,
    platform: null,
  },
  {
    code: 'soundtrack_player',
    name: 'Soundtrack Player',
    description: `• Includes a 1-year warranty
• Shipping costs covered
• Customs fees to be paid by the receiver`,
    thailandOnly: false,
    platform: null,
  },
  {
    code: 'custom',
    name: 'Custom',
    description: '',
    thailandOnly: false,
    platform: null,
  },
];

// Helper function for generating temporary IDs
const generateTempId = () => `temp-${Date.now()}-${Math.random()}`;

const ContractForm: React.FC<ContractFormProps> = ({
  open,
  onClose,
  onSave,
  contract,
  mode,
  initialCompanyId,
  initialQuoteId,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showErrors, setShowErrors] = useState(false);
  const [companies, setCompanies] = useState<Company[]>([]);

  // Form state
  const [formData, setFormData] = useState({
    company: '',
    contract_number: '',
    contract_type: 'Annual' as 'Annual' | 'Monthly' | 'One-time' | 'Custom',
    contract_category: 'standard' as 'standard' | 'corporate_master' | 'participation',
    status: 'Draft' as 'Draft' | 'Sent' | 'Active' | 'Renewed' | 'Expired' | 'Cancelled',
    start_date: null as Date | null,
    end_date: null as Date | null,
    value: '',
    currency: 'USD',
    auto_renew: false,
    renewal_period_months: 12,
    send_renewal_reminders: true,
    payment_terms: 'Net 30',
    billing_frequency: 'Monthly',
    discount_percentage: '',
    notes: '',
    master_contract: '',
    customer_signatory_name: '',
    customer_signatory_title: '',
    bmasia_signatory_name: 'Chris Andrews',
    bmasia_signatory_title: 'Director',
    custom_terms: '',
    bmasia_contact_name: '',
    bmasia_contact_email: '',
    bmasia_contact_title: '',
    customer_contact_name: '',
    customer_contact_email: '',
    customer_contact_title: '',
  });

  const [serviceLocations, setServiceLocations] = useState<ServiceLocationEntry[]>([]);
  const [locationsTrimmedWarning, setLocationsTrimmedWarning] = useState('');
  const isFormInitialized = useRef(false);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [masterContracts, setMasterContracts] = useState<Contract[]>([]);
  const [additionalSignatories, setAdditionalSignatories] = useState<Array<{ name: string; title: string }>>([]);
  const [contractTemplates, setContractTemplates] = useState<ContractTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');

  // Line Items and Quote state
  const defaultContractLineItem: ContractLineItem = {
    product_service: '',
    description: '',
    quantity: 1,
    unit_price: 0,
    discount_percentage: 0,
    tax_rate: formData.currency === 'THB' ? 7 : 0,
    line_total: 0,
  };
  const [lineItems, setLineItems] = useState<ContractLineItem[]>([defaultContractLineItem]);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState<string>('');
  const [selectedCompanyCountry, setSelectedCompanyCountry] = useState<string>('');
  const [focusedPriceIndex, setFocusedPriceIndex] = useState<number | null>(null);
  const [durationMonths, setDurationMonths] = useState<number>(12);
  const [isCustomContractDuration, setIsCustomContractDuration] = useState(false);

  const CONTRACT_DURATION_PRESETS = [
    { label: '6 months', months: 6 },
    { label: '1 year', months: 12 },
    { label: '2 years', months: 24 },
    { label: '3 years', months: 36 },
  ];

  useEffect(() => {
    if (open) {
      loadCompanies();
      loadMasterContracts();
      loadContractTemplates();
      if (mode === 'edit' && contract) {
        populateForm(contract);
      } else {
        resetForm();
      }
    }
  }, [open, mode, contract]);

  // Pre-fill from query params (e.g., "Convert to Contract" from QuoteDetail)
  useEffect(() => {
    if (open && mode === 'create' && initialCompanyId && companies.length > 0) {
      const company = companies.find(c => c.id === initialCompanyId);
      if (company) {
        handleCompanyChange(company).then(() => {
          if (initialQuoteId) {
            // Wait for quotes to load, then auto-select
            setTimeout(() => handleQuoteChange(initialQuoteId), 500);
          }
        });
      }
    }
  }, [open, mode, initialCompanyId, initialQuoteId, companies]);

  const loadCompanies = async () => {
    try {
      const response: ApiResponse<Company> = await ApiService.getCompanies({
        page_size: 1000,
      });
      setCompanies(response.results);
    } catch (err) {
      console.error('Failed to load companies:', err);
    }
  };

  const loadMasterContracts = async () => {
    try {
      const contracts = await ApiService.getMasterAgreements();
      setMasterContracts(contracts);
    } catch (err) {
      console.error('Failed to load master contracts:', err);
    }
  };

  const loadContractTemplates = async () => {
    try {
      // Load all templates (including inactive) so edit mode shows the assigned template
      const response = await ApiService.getContractTemplates({});
      setContractTemplates(response.results || []);
    } catch (err) {
      console.error('Failed to load contract templates:', err);
    }
  };

  const populateForm = (contract: Contract) => {
    isFormInitialized.current = false;
    setFormData({
      company: contract.company,
      contract_number: contract.contract_number,
      contract_type: contract.contract_type,
      contract_category: contract.contract_category || 'standard',
      status: contract.status,
      start_date: contract.start_date ? new Date(contract.start_date) : null,
      end_date: contract.end_date ? new Date(contract.end_date) : null,
      value: contract.value.toString(),
      currency: contract.currency,
      auto_renew: contract.auto_renew,
      renewal_period_months: contract.renewal_period_months,
      send_renewal_reminders: contract.send_renewal_reminders ?? true,
      payment_terms: contract.payment_terms || 'Net 30',
      billing_frequency: contract.billing_frequency,
      discount_percentage: contract.discount_percentage.toString(),
      notes: contract.notes || '',
      master_contract: contract.master_contract || '',
      customer_signatory_name: contract.customer_signatory_name || '',
      customer_signatory_title: contract.customer_signatory_title || '',
      bmasia_signatory_name: contract.bmasia_signatory_name || 'Chris Andrews',
      bmasia_signatory_title: contract.bmasia_signatory_title || 'Director',
      custom_terms: contract.custom_terms || '',
      bmasia_contact_name: contract.bmasia_contact_name || '',
      bmasia_contact_email: contract.bmasia_contact_email || '',
      bmasia_contact_title: contract.bmasia_contact_title || '',
      customer_contact_name: contract.customer_contact_name || '',
      customer_contact_email: contract.customer_contact_email || '',
      customer_contact_title: contract.customer_contact_title || '',
    });

    // Derive duration from existing start/end dates
    if (contract.start_date && contract.end_date) {
      const start = new Date(contract.start_date);
      const end = new Date(contract.end_date);
      let months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
      if (end.getDate() >= start.getDate()) months += 0; // no adjustment needed
      const isPreset = [6, 12, 24, 36].includes(months);
      setDurationMonths(months || 12);
      setIsCustomContractDuration(!isPreset);
    } else {
      setDurationMonths(12);
      setIsCustomContractDuration(false);
    }

    // Load additional signatories
    setAdditionalSignatories(contract.additional_customer_signatories || []);

    // Load selected template
    setSelectedTemplate(contract.preamble_template || '');

    // Prepare line items
    let contractLineItems: ContractLineItem[];
    if (contract.line_items && contract.line_items.length > 0) {
      contractLineItems = contract.line_items.map(item => ({
        ...item,
        line_total: item.line_total || 0,
      }));
    } else {
      const smartTaxRate = contract.currency === 'THB' ? 7 : 0;
      contractLineItems = [{ ...defaultContractLineItem, tax_rate: smartTaxRate }];
    }

    // Load quote selection
    setSelectedQuoteId(contract.quote || '');

    // Set company country for product filtering
    const editCompany = companies.find(c => c.id === contract.company);
    if (editCompany) {
      setSelectedCompanyCountry(editCompany.country || '');
    }

    // Load service locations from DB, then sync platforms against line items
    let dbLocations: ServiceLocationEntry[] = [];
    if (contract.service_locations && contract.service_locations.length > 0) {
      dbLocations = contract.service_locations.map(loc => ({
        location_name: loc.location_name,
        platform: loc.platform,
        tempId: generateTempId(),
      }));
    } else if (contract.contract_zones && contract.contract_zones.length > 0) {
      const activeZones = contract.contract_zones.filter(cz => cz.is_active);
      dbLocations = activeZones.map(cz => ({
        location_name: cz.zone_name || '',
        platform: (cz.zone_platform || 'soundtrack') as 'soundtrack' | 'beatbreeze',
        tempId: generateTempId(),
      }));
    }

    // Sync locations against line items to fix stale platform assignments
    const { locations: syncedLocations } = syncLocationsFromLineItems(contractLineItems, dbLocations);
    setServiceLocations(syncedLocations);
    setLineItems(contractLineItems);

    // Allow sync to run after initial form population
    setTimeout(() => { isFormInitialized.current = true; }, 0);
  };

  const resetForm = () => {
    isFormInitialized.current = false;
    setFormData({
      company: '',
      contract_number: '',
      contract_type: 'Annual' as 'Annual' | 'Monthly' | 'One-time' | 'Custom',
      contract_category: 'standard' as 'standard' | 'corporate_master' | 'participation',
      status: 'Draft' as 'Draft' | 'Sent' | 'Active' | 'Renewed' | 'Expired' | 'Cancelled',
      start_date: null,
      end_date: null,
      value: '',
      currency: 'USD',
      auto_renew: false,
      renewal_period_months: 12,
      send_renewal_reminders: true,
      payment_terms: 'Net 30',
      billing_frequency: 'Monthly',
      discount_percentage: '',
      notes: '',
      master_contract: '',
      customer_signatory_name: '',
      customer_signatory_title: '',
      bmasia_signatory_name: 'Chris Andrews',
      bmasia_signatory_title: 'Director',
      custom_terms: '',
      bmasia_contact_name: '',
      bmasia_contact_email: '',
      bmasia_contact_title: '',
      customer_contact_name: '',
      customer_contact_email: '',
      customer_contact_title: '',
    });
    setServiceLocations([]);
    setAttachments([]);
    setAdditionalSignatories([]);
    setSelectedTemplate('');
    setLineItems([defaultContractLineItem]);
    setQuotes([]);
    setSelectedQuoteId('');
    setSelectedCompanyCountry('');
    setError('');
    setShowErrors(false);
    setLocationsTrimmedWarning('');
    setDurationMonths(12);
    setIsCustomContractDuration(false);

    // Allow sync to run after form reset
    setTimeout(() => { isFormInitialized.current = true; }, 0);
  };

  const handleCompanyChange = async (company: Company | null) => {
    setFormData(prev => ({
      ...prev,
      company: company?.id || '',
      currency: company?.country === 'Thailand' ? 'THB' : 'USD',
    }));

    // Set company country for product filtering and tax rates
    const country = company?.country || '';
    setSelectedCompanyCountry(country);

    // Load accepted quotes for this company
    if (company?.id) {
      try {
        const response = await ApiService.getQuotes({
          company: company.id,
          status: 'Accepted',
        });
        setQuotes(response.results || []);
      } catch (err) {
        console.error('Failed to load quotes:', err);
        setQuotes([]);
      }
    } else {
      setQuotes([]);
      setSelectedQuoteId('');
    }

    // Update line items tax rates based on country
    const smartTaxRate = country === 'Thailand' ? 7 : 0;
    setLineItems(prev => prev.map(item => ({
      ...item,
      tax_rate: smartTaxRate,
    })));
  };

  const calculateEndDateFromMonths = (startDate: Date | null, months: number) => {
    if (!startDate || months <= 0) return null;
    const date = new Date(startDate);
    date.setMonth(date.getMonth() + months);
    return date;
  };

  const handleStartDateChange = (date: Date | null) => {
    setFormData(prev => ({
      ...prev,
      start_date: date,
      end_date: date && !isCustomContractDuration
        ? calculateEndDateFromMonths(date, durationMonths)
        : prev.end_date,
    }));
  };

  const handleDurationChange = (months: number) => {
    setDurationMonths(months);
    setIsCustomContractDuration(false);
    setFormData(prev => ({
      ...prev,
      end_date: prev.start_date
        ? calculateEndDateFromMonths(prev.start_date, months)
        : prev.end_date,
    }));
  };

  const handleFileAttachment = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      const newFiles = Array.from(event.target.files);
      setAttachments(prev => [...prev, ...newFiles]);
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  // Helper to get currency symbol
  const getCurrencySymbol = (currencyCode: string): string => {
    const symbols: Record<string, string> = {
      'USD': '$',
      'THB': '฿',
      'EUR': '€',
      'GBP': '£',
    };
    return symbols[currencyCode] || '$';
  };

  // Available products based on company country
  const getAvailableProducts = () => {
    return PRODUCT_OPTIONS.filter(product =>
      !product.thailandOnly || selectedCompanyCountry === 'Thailand'
    );
  };

  // Line item handlers
  const addLineItem = () => {
    const smartTaxRate = formData.currency === 'THB' ? 7 : 0;
    setLineItems(prev => [...prev, { ...defaultContractLineItem, tax_rate: smartTaxRate }]);
  };

  const removeLineItem = (index: number) => {
    if (lineItems.length > 1) {
      setLineItems(prev => prev.filter((_, i) => i !== index));
    }
  };

  const updateLineItem = (index: number, field: keyof ContractLineItem | 'product_code', value: any) => {
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

      // Recalculate line total when quantity, unit_price, or tax_rate changes
      if (field === 'quantity' || field === 'unit_price' || field === 'tax_rate') {
        const item = newItems[index];
        newItems[index].line_total = item.quantity * item.unit_price;
      }

      return newItems;
    });
  };

  // Calculate totals from line items
  const calculateLineItemTotals = () => {
    return lineItems.reduce((sum, item) => sum + (item.quantity * item.unit_price), 0);
  };

  // Service location handler (only location_name is editable — platform is derived from line items)
  const updateServiceLocation = (tempId: string, field: keyof Omit<ServiceLocationEntry, 'tempId'>, value: string) => {
    setServiceLocations(prev => prev.map(loc =>
      loc.tempId === tempId ? { ...loc, [field]: value } : loc
    ));
  };

  // Sync service locations from music line items
  const syncLocationsFromLineItems = (
    currentLineItems: ContractLineItem[],
    currentLocations: ServiceLocationEntry[]
  ): { locations: ServiceLocationEntry[]; droppedNamedCount: number } => {
    const requiredCounts: Record<string, number> = { soundtrack: 0, beatbreeze: 0 };

    currentLineItems.forEach(item => {
      const product = PRODUCT_OPTIONS.find(p => p.name === item.product_service);
      const platform = product?.platform;
      if (platform) {
        requiredCounts[platform] += Math.max(0, Math.round(item.quantity));
      }
    });

    const result: ServiceLocationEntry[] = [];
    let droppedNamedCount = 0;

    for (const platform of ['soundtrack', 'beatbreeze'] as const) {
      const existing = currentLocations.filter(loc => loc.platform === platform);
      const required = requiredCounts[platform];

      if (existing.length <= required) {
        // Keep all existing, add blank rows to fill the gap
        result.push(...existing);
        for (let i = 0; i < required - existing.length; i++) {
          result.push({ location_name: '', platform, tempId: generateTempId() });
        }
      } else {
        // Need to remove some — prefer removing blank/unnamed ones first
        const named = existing.filter(loc => loc.location_name.trim() !== '');
        const unnamed = existing.filter(loc => loc.location_name.trim() === '');

        if (named.length <= required) {
          result.push(...named);
          result.push(...unnamed.slice(0, required - named.length));
        } else {
          // Even named ones exceed required — keep first N
          result.push(...named.slice(0, required));
          droppedNamedCount += named.length - required;
        }
      }
    }

    return { locations: result, droppedNamedCount };
  };

  // Auto-sync service locations when line items change (after form is initialized)
  useEffect(() => {
    if (!isFormInitialized.current) return;
    const { locations, droppedNamedCount } = syncLocationsFromLineItems(lineItems, serviceLocations);
    setServiceLocations(locations);
    if (droppedNamedCount > 0) {
      setLocationsTrimmedWarning(`${droppedNamedCount} named location(s) removed due to quantity decrease`);
    } else {
      setLocationsTrimmedWarning('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lineItems]);

  // Handle quote selection and auto-fill
  const handleQuoteChange = async (quoteId: string) => {
    setSelectedQuoteId(quoteId);

    if (!quoteId) return;

    const selectedQuote = quotes.find(q => q.id === quoteId);
    if (selectedQuote) {
      // Auto-populate line items from quote
      if (selectedQuote.line_items && selectedQuote.line_items.length > 0) {
        const smartTaxRate = formData.currency === 'THB' ? 7 : 0;
        setLineItems(selectedQuote.line_items.map(item => {
          // Fold quote discount into final unit price (contracts show agreed price)
          const finalUnitPrice = item.unit_price * (1 - (item.discount_percentage || 0) / 100);
          return {
            product_service: item.product_service,
            description: item.description,
            quantity: item.quantity,
            unit_price: Math.round(finalUnitPrice * 100) / 100,
            discount_percentage: 0,
            tax_rate: smartTaxRate,
            line_total: item.quantity * Math.round(finalUnitPrice * 100) / 100,
          };
        }));
        // Service locations will auto-sync via useEffect on lineItems
      }

      // Auto-fill currency from quote
      setFormData(prev => ({
        ...prev,
        currency: selectedQuote.currency,
      }));

      // Transfer contract duration from quote
      if (selectedQuote.contract_duration_months) {
        const dur = selectedQuote.contract_duration_months;
        setDurationMonths(dur);
        const isPreset = [6, 12, 24, 36].includes(dur);
        setIsCustomContractDuration(!isPreset);
        // Auto-calculate end_date if start_date is set
        setFormData(prev => ({
          ...prev,
          end_date: prev.start_date
            ? calculateEndDateFromMonths(prev.start_date, dur)
            : prev.end_date,
        }));
      }

      // Auto-fill payment terms if quote has terms
      if (selectedQuote.terms_conditions) {
        const termsText = selectedQuote.terms_conditions.toLowerCase();
        if (termsText.includes('30 days')) {
          setFormData(prev => ({ ...prev, payment_terms: 'Net 30' }));
        } else if (termsText.includes('15 days')) {
          setFormData(prev => ({ ...prev, payment_terms: 'Net 15' }));
        } else if (termsText.includes('45 days')) {
          setFormData(prev => ({ ...prev, payment_terms: 'Net 45' }));
        } else if (termsText.includes('60 days')) {
          setFormData(prev => ({ ...prev, payment_terms: 'Net 60' }));
        }
      }
    }
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setError('');
      setShowErrors(true);

      // Validation
      if (!formData.company) {
        setError('Please select a company');
        return;
      }

      if (!selectedTemplate && mode === 'create') {
        setError('Please select a contract template');
        return;
      }

      if (formData.contract_category === 'participation' && !formData.master_contract) {
        setError('Please select a master contract for participation agreements');
        return;
      }

      if (!formData.start_date || !formData.end_date) {
        setError('Please select start and end dates');
        return;
      }

      // Validate service locations have names
      const emptyLocations = serviceLocations.filter(loc => !loc.location_name.trim());
      if (emptyLocations.length > 0) {
        setError(`Please fill in all ${emptyLocations.length} service location name(s)`);
        return;
      }

      // Auto-calculate value from line items if they exist
      const validLineItems = lineItems.filter(item => item.product_service || item.description);
      const calculatedValue = validLineItems.length > 0
        ? calculateLineItemTotals()
        : parseFloat(formData.value);

      if (!calculatedValue || calculatedValue <= 0) {
        setError('Please add line items with pricing');
        return;
      }

      const contractData = {
        ...formData,
        value: calculatedValue,
        discount_percentage: parseFloat(formData.discount_percentage) || 0,
        start_date: formData.start_date.toISOString().split('T')[0],
        end_date: formData.end_date.toISOString().split('T')[0],
        additional_customer_signatories: additionalSignatories.length > 0 ? additionalSignatories : [],
        preamble_template: selectedTemplate || undefined,
        quote: selectedQuoteId || null,
        line_items: lineItems.filter(item => item.product_service || item.description).map(item => ({
          product_service: item.product_service,
          description: item.description,
          quantity: item.quantity,
          unit_price: item.unit_price,
          discount_percentage: 0,
          tax_rate: item.tax_rate,
        })),
        service_locations: serviceLocations
          .filter(loc => loc.location_name.trim())
          .map((loc, index) => ({
            location_name: loc.location_name.trim(),
            platform: loc.platform,
            sort_order: index,
          })),
      };

      let savedContract: Contract;
      if (mode === 'create') {
        savedContract = await ApiService.createContract(contractData);
      } else {
        savedContract = await ApiService.updateContract(contract!.id, contractData);
      }

      // Upload attachments
      if (attachments.length > 0 && savedContract.id) {
        for (const file of attachments) {
          try {
            const formDataUpload = new FormData();
            formDataUpload.append('file', file);
            formDataUpload.append('contract', savedContract.id);
            formDataUpload.append('title', file.name.replace(/\.[^/.]+$/, ''));
            formDataUpload.append('document_type', 'other');
            formDataUpload.append('is_official', 'false');
            formDataUpload.append('is_signed', 'false');
            await ApiService.uploadContractDocument(savedContract.id, formDataUpload);
          } catch (uploadErr) {
            console.error('Failed to upload document:', uploadErr);
          }
        }
      }

      onSave(savedContract);
      onClose();
    } catch (err: any) {
      // Parse DRF field-level errors (e.g., { field_name: ['error'] })
      const data = err.response?.data;
      if (data && typeof data === 'object' && !data.detail) {
        const messages = Object.entries(data)
          .map(([field, errors]) => `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}`)
          .join('; ');
        setError(messages || 'Failed to save contract');
      } else {
        setError(data?.detail || err.message || 'Failed to save contract');
      }
    } finally {
      setLoading(false);
    }
  };

  const selectedCompany = companies.find(c => c.id === formData.company);

  // Filter companies based on contract category
  const filteredCompanies = formData.contract_category === 'corporate_master'
    ? companies.filter(c => c.is_corporate_parent)
    : companies;

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="lg"
        fullWidth
        scroll="paper"
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography variant="h6">
              {mode === 'create' ? 'Create New Contract' : 'Edit Contract'}
            </Typography>
            <IconButton onClick={onClose}>
              <Close />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent dividers>
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Basic Information */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Basic Information
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <Autocomplete
                    fullWidth
                    options={filteredCompanies}
                    getOptionLabel={(option) => option.name}
                    value={selectedCompany || null}
                    onChange={(_, value) => handleCompanyChange(value)}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Company *"
                        placeholder="Select a company"
                        helperText={formData.contract_category === 'corporate_master' ? 'Only corporate HQ companies shown' : ''}
                      />
                    )}
                  />

                  <TextField
                    label="Contract Number"
                    value={formData.contract_number}
                    onChange={(e) => setFormData(prev => ({ ...prev, contract_number: e.target.value }))}
                    placeholder={mode === 'create' ? 'Auto-generated' : ''}
                    InputProps={{
                      readOnly: mode === 'create',
                    }}
                    sx={{ minWidth: 200 }}
                  />
                </Box>

                <Box sx={{ display: 'flex', gap: 2 }}>
                  <FormControl fullWidth>
                    <InputLabel>Contract Type</InputLabel>
                    <Select
                      value={formData.contract_type}
                      onChange={(e) => {
                        setFormData(prev => ({
                          ...prev,
                          contract_type: e.target.value as any,
                        }));
                      }}
                      label="Contract Type"
                    >
                      {contractTypes.map(type => (
                        <MenuItem key={type} value={type}>{type}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  <FormControl fullWidth>
                    <InputLabel>Status</InputLabel>
                    <Select
                      value={formData.status}
                      onChange={(e) => setFormData(prev => ({ ...prev, status: e.target.value as any }))}
                      label="Status"
                    >
                      {contractStatuses.map(status => (
                        <MenuItem key={status} value={status}>{status}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Box>

                {/* Contract Template Selection */}
                <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                  <FormControl fullWidth>
                    <InputLabel>Contract Template *</InputLabel>
                    <Select
                      value={selectedTemplate}
                      onChange={(e) => {
                        const templateId = e.target.value;
                        setSelectedTemplate(templateId);
                        // Update contract_category based on template's pdf_format
                        const template = contractTemplates.find(t => t.id === templateId);
                        if (template?.pdf_format) {
                          setFormData(prev => ({ ...prev, contract_category: template.pdf_format as any }));
                        } else {
                          setFormData(prev => ({ ...prev, contract_category: 'standard' as any }));
                        }
                      }}
                      label="Contract Template *"
                    >
                      <MenuItem value="">
                        <em>Select a template</em>
                      </MenuItem>
                      {contractTemplates.map((template) => (
                        <MenuItem key={template.id} value={template.id} disabled={!template.is_active && mode === 'create'}>
                          {template.name}
                          {!template.is_active && (
                            <Typography component="span" variant="caption" sx={{ ml: 1, color: 'warning.main' }}>
                              (inactive)
                            </Typography>
                          )}
                          {template.pdf_format !== 'standard' && (
                            <Typography component="span" variant="caption" sx={{ ml: 1, color: 'text.secondary' }}>
                              ({template.pdf_format_display || template.pdf_format})
                            </Typography>
                          )}
                        </MenuItem>
                      ))}
                    </Select>
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, ml: 1.5 }}>
                      Template determines contract structure and PDF format
                    </Typography>
                  </FormControl>
                </Box>

                {formData.contract_category === 'participation' && (
                  <Box sx={{ mt: 2 }}>
                    <Autocomplete
                      fullWidth
                      options={masterContracts}
                      getOptionLabel={(option) => `${option.contract_number} - ${option.company_name}`}
                      value={masterContracts.find(c => c.id === formData.master_contract) || null}
                      onChange={(_, value) => setFormData(prev => ({ ...prev, master_contract: value?.id || '' }))}
                      renderInput={(params) => (
                        <TextField
                          {...params}
                          label="Master Contract *"
                          placeholder="Select master agreement"
                          error={showErrors && !formData.master_contract}
                          helperText={showErrors && !formData.master_contract ? 'Required for participation agreements' : ''}
                        />
                      )}
                    />
                  </Box>
                )}

                {formData.contract_category === 'corporate_master' && (
                  <Box sx={{ mt: 2 }}>
                    <TextField
                      fullWidth
                      label="Custom Terms"
                      multiline
                      rows={4}
                      value={formData.custom_terms}
                      onChange={(e) => setFormData(prev => ({ ...prev, custom_terms: e.target.value }))}
                      placeholder="Enter custom contract terms for this master agreement..."
                      helperText="Specific terms that apply to all participation agreements under this master contract"
                    />
                  </Box>
                )}

                {/* Source Quote Dropdown */}
                {quotes.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <FormControl fullWidth>
                      <InputLabel>Source Quote (Optional)</InputLabel>
                      <Select
                        value={selectedQuoteId}
                        onChange={(e) => handleQuoteChange(e.target.value)}
                        label="Source Quote (Optional)"
                      >
                        <MenuItem value="">
                          <em>None</em>
                        </MenuItem>
                        {quotes.map((quote) => (
                          <MenuItem key={quote.id} value={quote.id}>
                            {quote.quote_number} - {getCurrencySymbol(quote.currency)}{quote.total_value.toLocaleString()}
                            {quote.contact_name && ` (${quote.contact_name})`}
                          </MenuItem>
                        ))}
                      </Select>
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, ml: 1.5 }}>
                        Auto-fill line items, currency, and payment terms from accepted quote
                      </Typography>
                    </FormControl>
                  </Box>
                )}
              </Box>
            </Box>

            <Divider />

            {/* Signatories */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Signatories
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {/* Customer Signatories */}
                <Typography variant="subtitle2" color="text.secondary">
                  Customer Signatories
                </Typography>

                {/* Primary Customer Signatory */}
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    fullWidth
                    label="Customer Signatory Name"
                    value={formData.customer_signatory_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, customer_signatory_name: e.target.value }))}
                    placeholder="e.g., John Smith"
                  />
                  <TextField
                    fullWidth
                    label="Customer Signatory Title"
                    value={formData.customer_signatory_title}
                    onChange={(e) => setFormData(prev => ({ ...prev, customer_signatory_title: e.target.value }))}
                    placeholder="e.g., General Manager"
                  />
                </Box>

                {/* Additional Customer Signatories */}
                {additionalSignatories.map((signatory, index) => (
                  <Box key={index} sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    <TextField
                      fullWidth
                      label={`Additional Signatory ${index + 1} Name`}
                      value={signatory.name}
                      onChange={(e) => {
                        const updated = [...additionalSignatories];
                        updated[index] = { ...updated[index], name: e.target.value };
                        setAdditionalSignatories(updated);
                      }}
                      placeholder="e.g., Jane Doe"
                    />
                    <TextField
                      fullWidth
                      label={`Additional Signatory ${index + 1} Title`}
                      value={signatory.title}
                      onChange={(e) => {
                        const updated = [...additionalSignatories];
                        updated[index] = { ...updated[index], title: e.target.value };
                        setAdditionalSignatories(updated);
                      }}
                      placeholder="e.g., Director"
                    />
                    <IconButton
                      onClick={() => {
                        setAdditionalSignatories(additionalSignatories.filter((_, i) => i !== index));
                      }}
                      color="error"
                      size="small"
                    >
                      <Delete />
                    </IconButton>
                  </Box>
                ))}

                {/* Add Additional Signatory Button */}
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={() => setAdditionalSignatories([...additionalSignatories, { name: '', title: '' }])}
                  sx={{ alignSelf: 'flex-start' }}
                >
                  Add Customer Signatory
                </Button>

                {/* BMAsia Signatory */}
                <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 1 }}>
                  BMAsia Signatory
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    fullWidth
                    label="BMAsia Signatory Name"
                    value={formData.bmasia_signatory_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, bmasia_signatory_name: e.target.value }))}
                    placeholder="Chris Andrews"
                  />
                  <TextField
                    fullWidth
                    label="BMAsia Signatory Title"
                    value={formData.bmasia_signatory_title}
                    onChange={(e) => setFormData(prev => ({ ...prev, bmasia_signatory_title: e.target.value }))}
                    placeholder="Director"
                  />
                </Box>
              </Box>
            </Box>

            <Divider />

            {/* Dates and Duration */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Contract Period
              </Typography>

              <Box sx={{ display: 'flex', gap: 2 }}>
                <DatePicker
                  label="Start Date *"
                  value={formData.start_date}
                  onChange={handleStartDateChange}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      InputProps: {
                        startAdornment: (
                          <InputAdornment position="start">
                            <CalendarToday />
                          </InputAdornment>
                        ),
                      },
                    },
                  }}
                />

                <FormControl sx={{ minWidth: 160 }}>
                  <InputLabel>Duration</InputLabel>
                  <Select
                    value={isCustomContractDuration ? 'custom' : String(durationMonths)}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === 'custom') {
                        setIsCustomContractDuration(true);
                      } else {
                        handleDurationChange(Number(val));
                      }
                    }}
                    label="Duration"
                  >
                    {CONTRACT_DURATION_PRESETS.map(p => (
                      <MenuItem key={p.months} value={String(p.months)}>{p.label}</MenuItem>
                    ))}
                    <MenuItem value="custom">Custom</MenuItem>
                  </Select>
                </FormControl>

                {isCustomContractDuration && (
                  <TextField
                    label="Months"
                    type="number"
                    value={durationMonths}
                    onChange={(e) => {
                      const val = Math.max(1, parseInt(e.target.value) || 1);
                      setDurationMonths(val);
                      setFormData(prev => ({
                        ...prev,
                        end_date: prev.start_date
                          ? calculateEndDateFromMonths(prev.start_date, val)
                          : prev.end_date,
                      }));
                    }}
                    inputProps={{ min: 1, max: 120 }}
                    sx={{ width: 120 }}
                  />
                )}

                <DatePicker
                  label="End Date *"
                  value={formData.end_date}
                  onChange={(date) => {
                    setFormData(prev => ({ ...prev, end_date: date }));
                    setIsCustomContractDuration(true);
                  }}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      InputProps: {
                        startAdornment: (
                          <InputAdornment position="start">
                            <CalendarToday />
                          </InputAdornment>
                        ),
                      },
                    },
                  }}
                />
              </Box>

              <Box sx={{ mt: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.auto_renew}
                      onChange={(e) => setFormData(prev => ({ ...prev, auto_renew: e.target.checked }))}
                    />
                  }
                  label="Auto-renew contract"
                />

                {formData.auto_renew && (
                  <TextField
                    label="Renewal Period (months)"
                    type="number"
                    value={formData.renewal_period_months}
                    onChange={(e) => setFormData(prev => ({
                      ...prev,
                      renewal_period_months: parseInt(e.target.value) || 12
                    }))}
                    sx={{ ml: 2, width: 200 }}
                  />
                )}
              </Box>

              <Box sx={{ mt: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.send_renewal_reminders !== false}
                      onChange={(e) => setFormData(prev => ({ ...prev, send_renewal_reminders: e.target.checked }))}
                    />
                  }
                  label="Send automatic renewal reminders"
                />
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', ml: 6 }}>
                  Uncheck for multi-year contracts to prevent premature renewal emails
                </Typography>
              </Box>
            </Box>

            <Divider />

            {/* Payment & Billing */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Payment &amp; Billing
              </Typography>

              <Box sx={{ display: 'flex', gap: 2 }}>
                <FormControl sx={{ minWidth: 120 }}>
                  <InputLabel>Currency</InputLabel>
                  <Select
                    value={formData.currency}
                    onChange={(e) => setFormData(prev => ({ ...prev, currency: e.target.value }))}
                    label="Currency"
                  >
                    {currencies.map(currency => (
                      <MenuItem key={currency} value={currency}>{currency}</MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <FormControl fullWidth>
                  <InputLabel>Payment Terms</InputLabel>
                  <Select
                    value={formData.payment_terms}
                    onChange={(e) => setFormData(prev => ({ ...prev, payment_terms: e.target.value }))}
                    label="Payment Terms"
                  >
                    {paymentTermsOptions.map(terms => (
                      <MenuItem key={terms} value={terms}>{terms}</MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <FormControl fullWidth>
                  <InputLabel>Billing Frequency</InputLabel>
                  <Select
                    value={formData.billing_frequency}
                    onChange={(e) => setFormData(prev => ({ ...prev, billing_frequency: e.target.value }))}
                    label="Billing Frequency"
                  >
                    {billingFrequencies.map(freq => (
                      <MenuItem key={freq} value={freq}>{freq}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
            </Box>

            <Divider />

            {/* Line Items */}
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center' }}>
                  <Calculate sx={{ mr: 1 }} />
                  Line Items
                </Typography>
                <Button
                  variant="outlined"
                  startIcon={<AddIcon />}
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
                      <TableCell width="160px">Unit Price</TableCell>
                      <TableCell width="100px">Tax %</TableCell>
                      <TableCell width="150px">Line Total</TableCell>
                      <TableCell width="50px">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {lineItems.map((item, index) => (
                      <TableRow key={index}>
                        <TableCell sx={{ minWidth: 180 }}>
                          <FormControl fullWidth size="small">
                            <Select
                              value={
                                PRODUCT_OPTIONS.find(p => p.name === item.product_service)?.code || 'custom'
                              }
                              onChange={(e) => {
                                const code = e.target.value;
                                updateLineItem(index, 'product_code', code);
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
                            placeholder="Description"
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            value={Math.round(item.quantity)}
                            onChange={(e) => updateLineItem(index, 'quantity', parseInt(e.target.value) || 0)}
                            inputProps={{ min: 0, step: 1 }}
                            sx={{
                              '& input::-webkit-outer-spin-button, & input::-webkit-inner-spin-button': {
                                WebkitAppearance: 'none',
                                margin: 0
                              },
                              '& input[type=number]': {
                                MozAppearance: 'textfield'
                              }
                            }}
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
                              updateLineItem(index, 'unit_price', parseFloat(cleaned) || 0);
                            }}
                            onFocus={() => setFocusedPriceIndex(index)}
                            onBlur={() => setFocusedPriceIndex(null)}
                            InputProps={{
                              startAdornment: <InputAdornment position="start">{getCurrencySymbol(formData.currency)}</InputAdornment>,
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            value={Math.round(item.tax_rate)}
                            onChange={(e) => updateLineItem(index, 'tax_rate', parseInt(e.target.value) || 0)}
                            inputProps={{ min: 0, max: 100, step: 1 }}
                            InputProps={{
                              endAdornment: <InputAdornment position="end">%</InputAdornment>,
                            }}
                            sx={{
                              minWidth: '90px',
                              '& input::-webkit-outer-spin-button, & input::-webkit-inner-spin-button': {
                                WebkitAppearance: 'none',
                                margin: 0
                              },
                              '& input[type=number]': {
                                MozAppearance: 'textfield'
                              }
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight="medium">
                            {getCurrencySymbol(formData.currency)}{(item.line_total || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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

              {/* Line Items Summary with VAT */}
              {lineItems.length > 0 && (() => {
                const subtotal = calculateLineItemTotals();
                const taxRate = formData.currency === 'THB' ? 7 : 0;
                const vatAmount = subtotal * (taxRate / 100);
                const total = subtotal + vatAmount;
                const sym = getCurrencySymbol(formData.currency);
                const fmt = (v: number) => v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

                return (
                  <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                    <Paper variant="outlined" sx={{ p: 2, minWidth: 300 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="body2" color="text.secondary">Subtotal:</Typography>
                        <Typography variant="body2">{sym}{fmt(subtotal)}</Typography>
                      </Box>
                      {taxRate > 0 && (
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2" color="text.secondary">VAT ({taxRate}%):</Typography>
                          <Typography variant="body2">{sym}{fmt(vatAmount)}</Typography>
                        </Box>
                      )}
                      <Divider sx={{ my: 1 }} />
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" fontWeight="bold">Total{taxRate > 0 ? ' (incl. VAT)' : ''}:</Typography>
                        <Typography variant="body2" fontWeight="bold" color="primary">
                          {sym}{fmt(total)}
                        </Typography>
                      </Box>
                    </Paper>
                  </Box>
                );
              })()}
            </Box>

            <Divider />

            {/* Service Locations (auto-derived from music line items) */}
            <Box>
              <Box sx={{ mb: 1 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center' }}>
                  <LocationOnIcon sx={{ mr: 1, color: '#FFA500' }} />
                  Service Locations
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Auto-generated from music line items above. Adjust line item quantities to add or remove locations.
              </Typography>

              {locationsTrimmedWarning && (
                <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setLocationsTrimmedWarning('')}>
                  {locationsTrimmedWarning}
                </Alert>
              )}

              {serviceLocations.length === 0 ? (
                <Typography variant="body2" color="text.disabled" sx={{ py: 2, textAlign: 'center' }}>
                  Add a music service line item (Soundtrack Your Brand or Beat Breeze) to generate service locations.
                </Typography>
              ) : (
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell width="60px">#</TableCell>
                        <TableCell>Location Name</TableCell>
                        <TableCell width="220px">Platform</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {serviceLocations.map((loc, index) => (
                        <TableRow key={loc.tempId}>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">{index + 1}</Typography>
                          </TableCell>
                          <TableCell>
                            <TextField
                              fullWidth
                              size="small"
                              value={loc.location_name}
                              onChange={(e) => updateServiceLocation(loc.tempId, 'location_name', e.target.value)}
                              placeholder="e.g., Bangkok HQ - Lobby"
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {loc.platform === 'soundtrack' ? 'Soundtrack Your Brand' : 'Beat Breeze'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>

            <Divider />

            {/* Contact Information */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Contract Contacts
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    fullWidth
                    label="BMAsia Contact Name"
                    value={formData.bmasia_contact_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, bmasia_contact_name: e.target.value }))}
                  />
                  <TextField
                    fullWidth
                    label="BMAsia Contact Email"
                    type="email"
                    value={formData.bmasia_contact_email}
                    onChange={(e) => setFormData(prev => ({ ...prev, bmasia_contact_email: e.target.value }))}
                  />
                  <TextField
                    fullWidth
                    label="BMAsia Contact Title"
                    value={formData.bmasia_contact_title}
                    onChange={(e) => setFormData(prev => ({ ...prev, bmasia_contact_title: e.target.value }))}
                  />
                </Box>

                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    fullWidth
                    label="Customer Contact Name"
                    value={formData.customer_contact_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, customer_contact_name: e.target.value }))}
                  />
                  <TextField
                    fullWidth
                    label="Customer Contact Email"
                    type="email"
                    value={formData.customer_contact_email}
                    onChange={(e) => setFormData(prev => ({ ...prev, customer_contact_email: e.target.value }))}
                  />
                  <TextField
                    fullWidth
                    label="Customer Contact Title"
                    value={formData.customer_contact_title}
                    onChange={(e) => setFormData(prev => ({ ...prev, customer_contact_title: e.target.value }))}
                  />
                </Box>
              </Box>
            </Box>

            <Divider />

            {/* File Attachments */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Contract Documents
              </Typography>

              <input
                accept=".pdf,.doc,.docx"
                style={{ display: 'none' }}
                id="file-upload"
                type="file"
                multiple
                onChange={handleFileAttachment}
              />
              <label htmlFor="file-upload">
                <Button
                  variant="outlined"
                  component="span"
                  startIcon={<AttachFile />}
                  sx={{ mb: 2 }}
                >
                  Attach Contract Documents
                </Button>
              </label>

              {attachments.length > 0 && (
                <Stack spacing={1}>
                  {attachments.map((file, index) => (
                    <Box
                      key={index}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        p: 1,
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: 1,
                      }}
                    >
                      <Typography variant="body2">{file.name}</Typography>
                      <IconButton
                        size="small"
                        onClick={() => removeAttachment(index)}
                      >
                        <Delete />
                      </IconButton>
                    </Box>
                  ))}
                </Stack>
              )}
            </Box>

            {/* Notes */}
            <TextField
              label="Notes"
              value={formData.notes}
              onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
              multiline
              rows={3}
              placeholder="Additional contract terms, conditions, or notes..."
            />
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} /> : null}
          >
            {loading ? 'Saving...' : (mode === 'create' ? 'Create Contract' : 'Update Contract')}
          </Button>
        </DialogActions>
      </Dialog>
    </LocalizationProvider>
  );
};

export default ContractForm;
