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
import { Contract, Company, ApiResponse, Zone, PreviewZone, ContractTemplate } from '../types';
import ApiService from '../services/api';
import EnhancedZonePicker from './EnhancedZonePicker';

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
    status: 'Active' as 'Active' | 'Renewed' | 'Expired' | 'Cancelled',
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
    show_zone_pricing_detail: true,
    price_per_zone: '',
    bmasia_contact_name: '',
    bmasia_contact_email: '',
    bmasia_contact_title: '',
    customer_contact_name: '',
    customer_contact_email: '',
    customer_contact_title: '',
  });

  const [selectedZones, setSelectedZones] = useState<Zone[]>([]);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [masterContracts, setMasterContracts] = useState<Contract[]>([]);
  const [additionalSignatories, setAdditionalSignatories] = useState<Array<{ name: string; title: string }>>([]);
  const [contractTemplates, setContractTemplates] = useState<ContractTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');

  // Soundtrack Account ID preview state
  const [soundtrackAccountId, setSoundtrackAccountId] = useState('');
  const [previewZones, setPreviewZones] = useState<PreviewZone[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');

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
      const response = await ApiService.getContractTemplates({ is_active: true });
      setContractTemplates(response.results || []);
    } catch (err) {
      console.error('Failed to load contract templates:', err);
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
      show_zone_pricing_detail: contract.show_zone_pricing_detail ?? true,
      price_per_zone: contract.price_per_zone?.toString() || '',
      bmasia_contact_name: contract.bmasia_contact_name || '',
      bmasia_contact_email: contract.bmasia_contact_email || '',
      bmasia_contact_title: contract.bmasia_contact_title || '',
      customer_contact_name: contract.customer_contact_name || '',
      customer_contact_email: contract.customer_contact_email || '',
      customer_contact_title: contract.customer_contact_title || '',
    });

    // Load additional signatories
    setAdditionalSignatories(contract.additional_customer_signatories || []);

    // Load selected template
    setSelectedTemplate(contract.preamble_template || '');

    // Load existing contract zones in edit mode
    if (contract.id) {
      loadContractZones(contract.id, contract.company);
    }
  };

  const loadContractZones = async (contractId: string, companyId: string) => {
    try {
      // Get all zones for the company
      const companyZones = await ApiService.getZonesByCompany(companyId);

      // Get contract's linked zones
      const contractZones = await ApiService.getContractZones(contractId);
      const activeZoneIds = contractZones
        .filter((cz: any) => cz.is_active)
        .map((cz: any) => cz.zone);

      // Filter to get the Zone objects that are linked to this contract
      const linkedZones = companyZones.filter((z: Zone) => activeZoneIds.includes(z.id));
      setSelectedZones(linkedZones);
    } catch (err) {
      console.error('Failed to load contract zones:', err);
      setSelectedZones([]);
    }
  };

  const resetForm = () => {
    setFormData({
      company: '',
      contract_number: '',
      contract_type: 'Annual' as 'Annual' | 'Monthly' | 'One-time' | 'Custom',
      contract_category: 'standard' as 'standard' | 'corporate_master' | 'participation',
      status: 'Active' as 'Active' | 'Renewed' | 'Expired' | 'Cancelled',
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
      show_zone_pricing_detail: true,
      price_per_zone: '',
      bmasia_contact_name: '',
      bmasia_contact_email: '',
      bmasia_contact_title: '',
      customer_contact_name: '',
      customer_contact_email: '',
      customer_contact_title: '',
    });
    setSelectedZones([]);
    setAttachments([]);
    setAdditionalSignatories([]);
    setSelectedTemplate('');
    setError('');
    setShowErrors(false);
  };

  const handleCompanyChange = (company: Company | null) => {
    setFormData(prev => ({
      ...prev,
      company: company?.id || '',
    }));
    // Clear selected zones when company changes (zones are company-specific)
    setSelectedZones([]);
    // Load company's Soundtrack Account ID
    setSoundtrackAccountId(company?.soundtrack_account_id || '');
    setPreviewZones([]);
    setPreviewError('');
  };

  // Load Soundtrack zones preview when account ID changes
  useEffect(() => {
    const loadPreviewZones = async () => {
      if (!soundtrackAccountId || soundtrackAccountId.length < 5) {
        setPreviewZones([]);
        return;
      }

      setPreviewLoading(true);
      setPreviewError('');
      try {
        const zones = await ApiService.previewSoundtrackZones(soundtrackAccountId);
        setPreviewZones(zones);
      } catch (err: any) {
        setPreviewError(err.message || 'Failed to fetch zones. Check Account ID.');
        setPreviewZones([]);
      } finally {
        setPreviewLoading(false);
      }
    };

    // Debounce the API call
    const timer = setTimeout(() => {
      loadPreviewZones();
    }, 500);

    return () => clearTimeout(timer);
  }, [soundtrackAccountId]);

  const handleAccountIdChange = (accountId: string) => {
    setSoundtrackAccountId(accountId);
    setFormData(prev => ({ ...prev, soundtrack_account_id: accountId }));
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

      if (!selectedTemplate) {
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
        additional_customer_signatories: additionalSignatories.length > 0 ? additionalSignatories : [],
        preamble_template: selectedTemplate || undefined,
      };

      let savedContract: Contract;
      if (mode === 'create') {
        savedContract = await ApiService.createContract(contractData);
      } else {
        savedContract = await ApiService.updateContract(contract!.id, contractData);
      }

      // Update contract zones (link selected existing zones by ID)
      if (savedContract.id) {
        try {
          const zoneIds = selectedZones.map(z => z.id);
          await ApiService.updateContractZones(savedContract.id, zoneIds);
        } catch (zoneErr) {
          console.error('Failed to update zones:', zoneErr);
          // Don't fail the entire operation if zones fail
        }
      }

      // Upload attachments
      if (attachments.length > 0 && savedContract.id) {
        for (const file of attachments) {
          try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('contract', savedContract.id);
            formData.append('title', file.name.replace(/\.[^/.]+$/, '')); // Remove extension for title
            formData.append('document_type', 'other');
            formData.append('is_official', 'false');
            formData.append('is_signed', 'false');
            await ApiService.uploadContractDocument(savedContract.id, formData);
          } catch (uploadErr) {
            console.error('Failed to upload document:', uploadErr);
            // Don't fail the entire operation if document upload fails
          }
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
                        <MenuItem key={template.id} value={template.id}>
                          {template.name}
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
                    helperText={
                      formData.currency === 'THB'
                        ? 'Enter base price (excluding VAT). System will add 7% VAT automatically.'
                        : 'Enter contract value'
                    }
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          {formData.currency === 'THB' ? '฿' : formData.currency === 'EUR' ? '€' : formData.currency === 'GBP' ? '£' : '$'}
                        </InputAdornment>
                      ),
                    }}
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

                {/* Tax calculation display for THB contracts */}
                {formData.currency === 'THB' && formData.value && parseFloat(formData.value) > 0 && (
                  <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50' }}>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Tax Calculation (7% VAT)
                    </Typography>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2" color="text.secondary">Base Value:</Typography>
                      <Typography variant="body2">฿{parseFloat(formData.value).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2" color="text.secondary">VAT (7%):</Typography>
                      <Typography variant="body2">฿{(parseFloat(formData.value) * 0.07).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</Typography>
                    </Box>
                    <Divider sx={{ my: 1 }} />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2" fontWeight="bold">Total (incl. VAT):</Typography>
                      <Typography variant="body2" fontWeight="bold" color="primary">
                        ฿{(parseFloat(formData.value) * 1.07).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </Typography>
                    </Box>
                  </Paper>
                )}

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

            {/* Zone Pricing */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Zone Pricing
              </Typography>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.show_zone_pricing_detail}
                    onChange={(e) => setFormData(prev => ({ ...prev, show_zone_pricing_detail: e.target.checked }))}
                  />
                }
                label="Show Zone Pricing Detail on Contract"
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

            {/* Soundtrack Account Configuration */}
            <Box>
              <Typography variant="h6" gutterBottom>
                Soundtrack Account Configuration
              </Typography>
              <TextField
                fullWidth
                size="small"
                label="Soundtrack Account ID"
                value={soundtrackAccountId}
                onChange={(e) => handleAccountIdChange(e.target.value)}
                helperText="Enter Soundtrack account ID to fetch available zones"
                InputProps={{
                  endAdornment: previewLoading ? (
                    <InputAdornment position="end">
                      <CircularProgress size={20} />
                    </InputAdornment>
                  ) : previewZones.length > 0 ? (
                    <InputAdornment position="end">
                      <Chip size="small" label={`${previewZones.length} zones`} color="success" />
                    </InputAdornment>
                  ) : null
                }}
              />
              {previewError && (
                <Alert severity="error" sx={{ mt: 1 }}>{previewError}</Alert>
              )}
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
                  label={`${selectedZones.length} zone${selectedZones.length !== 1 ? 's' : ''} selected`}
                  color="primary"
                  size="small"
                  sx={{ bgcolor: '#FFA500' }}
                />
              </Box>

              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Soundtrack zones are auto-selected for new contracts. Beat Breeze zones can be added manually.
              </Typography>

              <EnhancedZonePicker
                companyId={formData.company || null}
                soundtrackAccountId={soundtrackAccountId}
                previewZones={previewZones}
                selectedZones={selectedZones}
                onChange={setSelectedZones}
                disabled={!formData.company}
                mode={mode}
                contractId={contract?.id}
              />
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