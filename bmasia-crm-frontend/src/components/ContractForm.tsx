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
  Autocomplete,
  Box,
  Typography,
  Alert,
  CircularProgress,
  Chip,
  FormControlLabel,
  Switch,
  InputAdornment,
  Divider,
  IconButton,
  Stack,
  Paper,
} from '@mui/material';
import {
  AttachFile,
  Close,
  Delete,
  CalendarToday,
  LocationOn as LocationOnIcon,
  MusicNote as MusicNoteIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Contract, Company, ApiResponse } from '../types';
import ApiService from '../services/api';

interface ContractFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (contract: Contract) => void;
  contract: Contract | null;
  mode: 'create' | 'edit';
}

interface ZoneFormData {
  id?: string;
  name: string;
  platform: 'soundtrack' | 'beatbreeze';
  status?: string;
  tempId?: string;
}

const contractStatuses = [
  'Draft',
  'Sent',
  'Signed',
  'Active',
  'Expired',
  'Terminated',
  'Renewed'
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

// Helper function for generating temporary IDs
const generateTempId = () => `temp-${Date.now()}-${Math.random()}`;

const ContractForm: React.FC<ContractFormProps> = ({
  open,
  onClose,
  onSave,
  contract,
  mode,
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
    status: 'Draft' as 'Draft' | 'Sent' | 'Signed' | 'Active' | 'Expired' | 'Terminated' | 'Renewed',
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
    bmasia_signatory_name: '',
    bmasia_signatory_title: '',
    custom_terms: '',
    // Contract Content Management fields
    preamble_template: '',
    preamble_custom: '',
    payment_template: '',
    payment_custom: '',
    activation_template: '',
    activation_custom: '',
    show_zone_pricing_detail: true,
    price_per_zone: '',
    bmasia_contact_name: '',
    bmasia_contact_email: '',
    bmasia_contact_title: '',
    customer_contact_name: '',
    customer_contact_email: '',
    customer_contact_title: '',
  });

  const [zones, setZones] = useState<ZoneFormData[]>([
    { name: '', platform: 'soundtrack', tempId: generateTempId() }
  ]);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [masterContracts, setMasterContracts] = useState<Contract[]>([]);

  // Contract Content Management state
  const [contractTemplates, setContractTemplates] = useState<any[]>([]);
  const [servicePackageItems, setServicePackageItems] = useState<any[]>([]);
  const [selectedServiceItems, setSelectedServiceItems] = useState<any[]>([]);
  const [customServiceItems, setCustomServiceItems] = useState<Array<{ name: string; description: string }>>([]);
  const [customizePreamble, setCustomizePreamble] = useState(false);
  const [customizePayment, setCustomizePayment] = useState(false);
  const [customizeActivation, setCustomizeActivation] = useState(false);

  useEffect(() => {
    if (open) {
      loadCompanies();
      loadMasterContracts();
      loadContractTemplates();
      loadServicePackageItems();
      if (mode === 'edit' && contract) {
        populateForm(contract);
      } else {
        resetForm();
      }
    }
  }, [open, mode, contract]);

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
      const response = await ApiService.getContractTemplates({ page_size: 1000 });
      setContractTemplates(response.results || []);
    } catch (err) {
      console.error('Failed to load contract templates:', err);
    }
  };

  const loadServicePackageItems = async () => {
    try {
      const items = await ApiService.getServicePackageItems();
      setServicePackageItems(items);
    } catch (err) {
      console.error('Failed to load service package items:', err);
    }
  };


  const populateForm = (contract: Contract) => {
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
      bmasia_signatory_name: contract.bmasia_signatory_name || '',
      bmasia_signatory_title: contract.bmasia_signatory_title || '',
      custom_terms: contract.custom_terms || '',
      // Contract Content Management fields
      preamble_template: contract.preamble_template || '',
      preamble_custom: contract.preamble_custom || '',
      payment_template: contract.payment_template || '',
      payment_custom: contract.payment_custom || '',
      activation_template: contract.activation_template || '',
      activation_custom: contract.activation_custom || '',
      show_zone_pricing_detail: contract.show_zone_pricing_detail ?? true,
      price_per_zone: contract.price_per_zone?.toString() || '',
      bmasia_contact_name: contract.bmasia_contact_name || '',
      bmasia_contact_email: contract.bmasia_contact_email || '',
      bmasia_contact_title: contract.bmasia_contact_title || '',
      customer_contact_name: contract.customer_contact_name || '',
      customer_contact_email: contract.customer_contact_email || '',
      customer_contact_title: contract.customer_contact_title || '',
    });

    // Set customize flags
    setCustomizePreamble(!!contract.preamble_custom);
    setCustomizePayment(!!contract.payment_custom);
    setCustomizeActivation(!!contract.activation_custom);

    // Set service items
    if (contract.service_items && contract.service_items.length > 0) {
      const selectedItems = servicePackageItems.filter(item =>
        contract.service_items?.includes(item.id)
      );
      setSelectedServiceItems(selectedItems);
    }

    // Set custom service items
    if (contract.custom_service_items) {
      setCustomServiceItems(contract.custom_service_items);
    }

    // For edit mode, zones will be managed separately (not in this form for now)
    setZones([{ name: '', platform: 'soundtrack', tempId: generateTempId() }]);
  };

  const resetForm = () => {
    setFormData({
      company: '',
      contract_number: '',
      contract_type: 'Annual' as 'Annual' | 'Monthly' | 'One-time' | 'Custom',
      contract_category: 'standard' as 'standard' | 'corporate_master' | 'participation',
      status: 'Draft' as 'Draft' | 'Sent' | 'Signed' | 'Active' | 'Expired' | 'Terminated' | 'Renewed',
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
      bmasia_signatory_name: '',
      bmasia_signatory_title: '',
      custom_terms: '',
      // Contract Content Management fields
      preamble_template: '',
      preamble_custom: '',
      payment_template: '',
      payment_custom: '',
      activation_template: '',
      activation_custom: '',
      show_zone_pricing_detail: true,
      price_per_zone: '',
      bmasia_contact_name: '',
      bmasia_contact_email: '',
      bmasia_contact_title: '',
      customer_contact_name: '',
      customer_contact_email: '',
      customer_contact_title: '',
    });
    setZones([{ name: '', platform: 'soundtrack', tempId: generateTempId() }]);
    setAttachments([]);
    setSelectedServiceItems([]);
    setCustomServiceItems([]);
    setCustomizePreamble(false);
    setCustomizePayment(false);
    setCustomizeActivation(false);
    setError('');
    setShowErrors(false);
  };

  const handleCompanyChange = (company: Company | null) => {
    setFormData(prev => ({
      ...prev,
      company: company?.id || '',
    }));
  };

  const handleZoneChange = (index: number, field: keyof ZoneFormData, value: any) => {
    const newZones = [...zones];
    newZones[index] = { ...newZones[index], [field]: value };
    setZones(newZones);
  };

  const addZone = () => {
    setZones([...zones, { name: '', platform: 'soundtrack', tempId: generateTempId() }]);
  };

  const removeZone = (index: number) => {
    if (zones.length > 1) {
      setZones(zones.filter((_, i) => i !== index));
    }
  };

  const handleStartDateChange = (date: Date | null) => {
    setFormData(prev => ({
      ...prev,
      start_date: date,
      end_date: date && prev.contract_type === 'Annual' ?
        new Date(date.getFullYear() + 1, date.getMonth(), date.getDate()) :
        prev.end_date,
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

  const calculateEndDate = (startDate: Date | null, type: string) => {
    if (!startDate) return null;

    const date = new Date(startDate);
    switch (type) {
      case 'Annual':
        date.setFullYear(date.getFullYear() + 1);
        break;
      case 'Monthly':
        date.setMonth(date.getMonth() + 1);
        break;
      default:
        return null;
    }
    return date;
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

      if (formData.contract_category === 'participation' && !formData.master_contract) {
        setError('Please select a master contract for participation agreements');
        return;
      }

      if (!formData.start_date || !formData.end_date) {
        setError('Please select start and end dates');
        return;
      }

      if (!formData.value || parseFloat(formData.value) <= 0) {
        setError('Please enter a valid contract value');
        return;
      }

      const contractData = {
        ...formData,
        value: parseFloat(formData.value),
        discount_percentage: parseFloat(formData.discount_percentage) || 0,
        start_date: formData.start_date.toISOString().split('T')[0],
        end_date: formData.end_date.toISOString().split('T')[0],
        price_per_zone: formData.price_per_zone ? parseFloat(formData.price_per_zone) : undefined,
        service_items: selectedServiceItems.map(item => item.id),
        custom_service_items: customServiceItems.length > 0 ? customServiceItems : undefined,
      };

      let savedContract: Contract;
      if (mode === 'create') {
        savedContract = await ApiService.createContract(contractData);
      } else {
        savedContract = await ApiService.updateContract(contract!.id, contractData);
      }

      // Add zones to contract (only if zones have names)
      const validZones = zones.filter(z => z.name.trim());
      if (validZones.length > 0 && savedContract.id) {
        try {
          await ApiService.addZonesToContract(
            savedContract.id,
            validZones.map(z => ({
              name: z.name.trim(),
              platform: z.platform
            }))
          );
        } catch (zoneErr) {
          console.error('Failed to add zones:', zoneErr);
          // Don't fail the entire operation if zones fail
        }
      }

      onSave(savedContract);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to save contract');
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
        maxWidth="md"
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
                        const type = e.target.value;
                        setFormData(prev => ({
                          ...prev,
                          contract_type: type as any,
                          end_date: calculateEndDate(prev.start_date, type),
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

                <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                  <FormControl fullWidth>
                    <InputLabel>Contract Category</InputLabel>
                    <Select
                      value={formData.contract_category}
                      onChange={(e) => setFormData(prev => ({ ...prev, contract_category: e.target.value as any }))}
                      label="Contract Category"
                    >
                      <MenuItem value="standard">Standard Contract</MenuItem>
                      <MenuItem value="corporate_master">Corporate Master Agreement</MenuItem>
                      <MenuItem value="participation">Participation Agreement</MenuItem>
                    </Select>
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
              </Box>
            </Box>

            <Divider />

            {/* Signatories */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Signatories
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
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

                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    fullWidth
                    label="BMAsia Signatory Name"
                    value={formData.bmasia_signatory_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, bmasia_signatory_name: e.target.value }))}
                    placeholder="e.g., Norbert Platzer"
                  />
                  <TextField
                    fullWidth
                    label="BMAsia Signatory Title"
                    value={formData.bmasia_signatory_title}
                    onChange={(e) => setFormData(prev => ({ ...prev, bmasia_signatory_title: e.target.value }))}
                    placeholder="e.g., Managing Director"
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

                <DatePicker
                  label="End Date *"
                  value={formData.end_date}
                  onChange={(date) => setFormData(prev => ({ ...prev, end_date: date }))}
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

            {/* Financial Information */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Financial Terms
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    label="Contract Value *"
                    type="number"
                    value={formData.value}
                    onChange={(e) => setFormData(prev => ({ ...prev, value: e.target.value }))}
                    fullWidth
                  />

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
                </Box>

                <Box sx={{ display: 'flex', gap: 2 }}>
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

                  <TextField
                    label="Discount %"
                    type="number"
                    value={formData.discount_percentage}
                    onChange={(e) => setFormData(prev => ({ ...prev, discount_percentage: e.target.value }))}
                    sx={{ minWidth: 120 }}
                    inputProps={{ min: 0, max: 100 }}
                  />
                </Box>
              </Box>
            </Box>

            <Divider />

            {/* Contract Content Section */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Contract Content
              </Typography>

              {/* Template Selectors */}
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {/* Preamble Template */}
                <Box>
                  <FormControl fullWidth>
                    <InputLabel>Preamble Template</InputLabel>
                    <Select
                      value={formData.preamble_template}
                      onChange={(e) => setFormData(prev => ({ ...prev, preamble_template: e.target.value }))}
                      label="Preamble Template"
                    >
                      <MenuItem value="">
                        <em>None</em>
                      </MenuItem>
                      {contractTemplates
                        .filter(t => t.template_type === 'preamble' && t.is_active)
                        .map(template => (
                          <MenuItem key={template.id} value={template.id}>
                            {template.name} {template.is_default && '(Default)'}
                          </MenuItem>
                        ))}
                    </Select>
                  </FormControl>

                  <FormControlLabel
                    control={
                      <Switch
                        checked={customizePreamble}
                        onChange={(e) => setCustomizePreamble(e.target.checked)}
                      />
                    }
                    label="Customize preamble text"
                    sx={{ mt: 1 }}
                  />

                  {customizePreamble && (
                    <TextField
                      fullWidth
                      multiline
                      rows={4}
                      label="Custom Preamble Text"
                      value={formData.preamble_custom}
                      onChange={(e) => setFormData(prev => ({ ...prev, preamble_custom: e.target.value }))}
                      placeholder="Enter custom preamble text..."
                      sx={{ mt: 1 }}
                    />
                  )}
                </Box>

                {/* Payment Template */}
                <Box>
                  <FormControl fullWidth>
                    <InputLabel>Payment Terms Template</InputLabel>
                    <Select
                      value={formData.payment_template}
                      onChange={(e) => setFormData(prev => ({ ...prev, payment_template: e.target.value }))}
                      label="Payment Terms Template"
                    >
                      <MenuItem value="">
                        <em>None</em>
                      </MenuItem>
                      {contractTemplates
                        .filter(t => ['payment_thailand', 'payment_international'].includes(t.template_type) && t.is_active)
                        .map(template => (
                          <MenuItem key={template.id} value={template.id}>
                            {template.name} {template.is_default && '(Default)'}
                          </MenuItem>
                        ))}
                    </Select>
                  </FormControl>

                  <FormControlLabel
                    control={
                      <Switch
                        checked={customizePayment}
                        onChange={(e) => setCustomizePayment(e.target.checked)}
                      />
                    }
                    label="Customize payment terms"
                    sx={{ mt: 1 }}
                  />

                  {customizePayment && (
                    <TextField
                      fullWidth
                      multiline
                      rows={4}
                      label="Custom Payment Terms"
                      value={formData.payment_custom}
                      onChange={(e) => setFormData(prev => ({ ...prev, payment_custom: e.target.value }))}
                      placeholder="Enter custom payment terms..."
                      sx={{ mt: 1 }}
                    />
                  )}
                </Box>

                {/* Activation Template */}
                <Box>
                  <FormControl fullWidth>
                    <InputLabel>Activation Terms Template</InputLabel>
                    <Select
                      value={formData.activation_template}
                      onChange={(e) => setFormData(prev => ({ ...prev, activation_template: e.target.value }))}
                      label="Activation Terms Template"
                    >
                      <MenuItem value="">
                        <em>None</em>
                      </MenuItem>
                      {contractTemplates
                        .filter(t => t.template_type === 'activation' && t.is_active)
                        .map(template => (
                          <MenuItem key={template.id} value={template.id}>
                            {template.name} {template.is_default && '(Default)'}
                          </MenuItem>
                        ))}
                    </Select>
                  </FormControl>

                  <FormControlLabel
                    control={
                      <Switch
                        checked={customizeActivation}
                        onChange={(e) => setCustomizeActivation(e.target.checked)}
                      />
                    }
                    label="Customize activation terms"
                    sx={{ mt: 1 }}
                  />

                  {customizeActivation && (
                    <TextField
                      fullWidth
                      multiline
                      rows={4}
                      label="Custom Activation Terms"
                      value={formData.activation_custom}
                      onChange={(e) => setFormData(prev => ({ ...prev, activation_custom: e.target.value }))}
                      placeholder="Enter custom activation terms..."
                      sx={{ mt: 1 }}
                    />
                  )}
                </Box>
              </Box>

              {/* Service Package Items */}
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Service Package
                </Typography>

                <Autocomplete
                  multiple
                  options={servicePackageItems}
                  getOptionLabel={(option) => option.name}
                  value={selectedServiceItems}
                  onChange={(_, newValue) => setSelectedServiceItems(newValue)}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Select Service Items"
                      placeholder="Choose service package items"
                    />
                  )}
                  renderTags={(value, getTagProps) =>
                    value.map((option, index) => (
                      <Chip
                        label={option.name}
                        {...getTagProps({ index })}
                        color={option.is_standard ? 'primary' : 'default'}
                      />
                    ))
                  }
                />

                {/* Custom Service Items */}
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Custom Service Items (optional)
                  </Typography>

                  {customServiceItems.map((item, index) => (
                    <Paper key={index} sx={{ p: 2, mb: 1 }}>
                      <Box sx={{ display: 'flex', gap: 2, alignItems: 'start' }}>
                        <TextField
                          fullWidth
                          size="small"
                          label="Item Name"
                          value={item.name}
                          onChange={(e) => {
                            const newItems = [...customServiceItems];
                            newItems[index].name = e.target.value;
                            setCustomServiceItems(newItems);
                          }}
                        />
                        <TextField
                          fullWidth
                          size="small"
                          label="Description"
                          value={item.description}
                          onChange={(e) => {
                            const newItems = [...customServiceItems];
                            newItems[index].description = e.target.value;
                            setCustomServiceItems(newItems);
                          }}
                        />
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => {
                            setCustomServiceItems(customServiceItems.filter((_, i) => i !== index));
                          }}
                        >
                          <Delete />
                        </IconButton>
                      </Box>
                    </Paper>
                  ))}

                  <Button
                    startIcon={<AddIcon />}
                    onClick={() => setCustomServiceItems([...customServiceItems, { name: '', description: '' }])}
                    variant="outlined"
                    size="small"
                    sx={{ mt: 1 }}
                  >
                    Add Custom Service Item
                  </Button>
                </Box>
              </Box>

              {/* Zone Pricing */}
              <Box sx={{ mt: 3 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.show_zone_pricing_detail}
                      onChange={(e) => setFormData(prev => ({ ...prev, show_zone_pricing_detail: e.target.checked }))}
                    />
                  }
                  label="Show Zone Pricing Detail"
                />

                {formData.show_zone_pricing_detail && (
                  <TextField
                    label="Price Per Zone"
                    type="number"
                    value={formData.price_per_zone}
                    onChange={(e) => setFormData(prev => ({ ...prev, price_per_zone: e.target.value }))}
                    fullWidth
                    sx={{ mt: 1 }}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          {formData.currency === 'THB' ? '฿' : formData.currency === 'EUR' ? '€' : formData.currency === 'GBP' ? '£' : '$'}
                        </InputAdornment>
                      ),
                    }}
                  />
                )}
              </Box>

              {/* Contact Information */}
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Contact Information
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
            </Box>

            <Divider />

            {/* Zone Management Section */}
            <Box sx={{ mt: 4, mb: 3 }}>
              <Divider sx={{ mb: 3 }} />

              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <LocationOnIcon sx={{ color: '#FFA500' }} />
                  Music Zones
                </Typography>
                <Chip
                  label={`${zones.length} zone${zones.length !== 1 ? 's' : ''}`}
                  color="primary"
                  size="small"
                  sx={{ bgcolor: '#FFA500' }}
                />
              </Box>

              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Specify the music zones covered by this contract. Tech Support will add technical details later.
              </Typography>

              {zones.map((zone, index) => (
                <Paper
                  key={zone.tempId || zone.id || index}
                  elevation={2}
                  sx={{ p: 2, mb: 2, border: '1px solid #e0e0e0' }}
                >
                  <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    <Box sx={{ flex: 1 }}>
                      <TextField
                        fullWidth
                        size="small"
                        label="Zone Name"
                        value={zone.name}
                        onChange={(e) => handleZoneChange(index, 'name', e.target.value)}
                        placeholder="e.g., Pool Bar, Lobby, All Day Dining"
                        required
                        error={!zone.name && showErrors}
                        helperText={!zone.name && showErrors ? 'Zone name required' : ''}
                      />
                    </Box>

                    <Box sx={{ minWidth: 200 }}>
                      <FormControl fullWidth size="small" required>
                        <InputLabel>Platform</InputLabel>
                        <Select
                          value={zone.platform}
                          onChange={(e) => handleZoneChange(index, 'platform', e.target.value)}
                          label="Platform"
                        >
                          <MenuItem value="soundtrack">
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <MusicNoteIcon fontSize="small" />
                              Soundtrack Your Brand
                            </Box>
                          </MenuItem>
                          <MenuItem value="beatbreeze">
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <MusicNoteIcon fontSize="small" />
                              Beat Breeze
                            </Box>
                          </MenuItem>
                        </Select>
                      </FormControl>
                    </Box>

                    <Box sx={{ minWidth: 100 }}>
                      <Chip
                        label="Pending"
                        size="small"
                        color="warning"
                        sx={{ width: '100%' }}
                      />
                    </Box>

                    <IconButton
                      onClick={() => removeZone(index)}
                      color="error"
                      disabled={zones.length === 1}
                      size="small"
                    >
                      <Delete />
                    </IconButton>
                  </Box>
                </Paper>
              ))}

              <Button
                startIcon={<AddIcon />}
                onClick={addZone}
                variant="outlined"
                sx={{
                  mt: 1,
                  borderColor: '#FFA500',
                  color: '#FFA500',
                  '&:hover': { borderColor: '#FF8C00', bgcolor: 'rgba(255, 165, 0, 0.04)' }
                }}
              >
                Add Another Zone
              </Button>
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