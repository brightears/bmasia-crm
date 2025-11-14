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
} from '@mui/material';
import {
  AttachFile,
  Close,
  Delete,
  CalendarToday,
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

interface Zone {
  id: string;
  name: string;
  location: string;
  status: string;
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

const ContractForm: React.FC<ContractFormProps> = ({
  open,
  onClose,
  onSave,
  contract,
  mode,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [companies, setCompanies] = useState<Company[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loadingZones, setLoadingZones] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    company: '',
    contract_number: '',
    contract_type: 'Annual' as 'Annual' | 'Monthly' | 'One-time' | 'Custom',
    status: 'Draft' as 'Draft' | 'Sent' | 'Signed' | 'Active' | 'Expired' | 'Terminated' | 'Renewed',
    start_date: null as Date | null,
    end_date: null as Date | null,
    value: '',
    currency: 'USD',
    auto_renew: false,
    renewal_period_months: 12,
    payment_terms: 'Net 30',
    billing_frequency: 'Monthly',
    discount_percentage: '',
    notes: '',
    zones: [] as string[],
  });

  const [attachments, setAttachments] = useState<File[]>([]);

  useEffect(() => {
    if (open) {
      loadCompanies();
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

  const loadCompanyZones = async (companyId: string) => {
    try {
      setLoadingZones(true);
      // This would need to be implemented in the API
      // const zones = await ApiService.getCompanyZones(companyId);
      // setZones(zones);
      // For now, we'll use placeholder data
      setZones([]);
    } catch (err) {
      console.error('Failed to load zones:', err);
    } finally {
      setLoadingZones(false);
    }
  };

  const populateForm = (contract: Contract) => {
    setFormData({
      company: contract.company,
      contract_number: contract.contract_number,
      contract_type: contract.contract_type,
      status: contract.status,
      start_date: contract.start_date ? new Date(contract.start_date) : null,
      end_date: contract.end_date ? new Date(contract.end_date) : null,
      value: contract.value.toString(),
      currency: contract.currency,
      auto_renew: contract.auto_renew,
      renewal_period_months: contract.renewal_period_months,
      payment_terms: contract.payment_terms || 'Net 30',
      billing_frequency: contract.billing_frequency,
      discount_percentage: contract.discount_percentage.toString(),
      notes: contract.notes || '',
      zones: [], // Would need to load from API
    });

    if (contract.company) {
      loadCompanyZones(contract.company);
    }
  };

  const resetForm = () => {
    setFormData({
      company: '',
      contract_number: '',
      contract_type: 'Annual' as 'Annual' | 'Monthly' | 'One-time' | 'Custom',
      status: 'Draft' as 'Draft' | 'Sent' | 'Signed' | 'Active' | 'Expired' | 'Terminated' | 'Renewed',
      start_date: null,
      end_date: null,
      value: '',
      currency: 'USD',
      auto_renew: false,
      renewal_period_months: 12,
      payment_terms: 'Net 30',
      billing_frequency: 'Monthly',
      discount_percentage: '',
      notes: '',
      zones: [],
    });
    setZones([]);
    setAttachments([]);
    setError('');
  };

  const handleCompanyChange = (company: Company | null) => {
    setFormData(prev => ({
      ...prev,
      company: company?.id || '',
      zones: [], // Reset zones when company changes
    }));

    if (company) {
      loadCompanyZones(company.id);
    } else {
      setZones([]);
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

      // Validation
      if (!formData.company) {
        setError('Please select a company');
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
      };

      let savedContract: Contract;
      if (mode === 'create') {
        savedContract = await ApiService.createContract(contractData);
      } else {
        savedContract = await ApiService.updateContract(contract!.id, contractData);
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
                    options={companies}
                    getOptionLabel={(option) => option.name}
                    value={selectedCompany || null}
                    onChange={(_, value) => handleCompanyChange(value)}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Company *"
                        placeholder="Select a company"
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

            {/* Zones Selection */}
            {selectedCompany && (
              <>
                <Divider />
                <Box>
                  <Typography variant="h6" gutterBottom>
                    Zones (Optional)
                  </Typography>

                  {loadingZones ? (
                    <CircularProgress size={20} />
                  ) : zones.length > 0 ? (
                    <Autocomplete
                      multiple
                      options={zones}
                      getOptionLabel={(option) => `${option.name} - ${option.location}`}
                      value={zones.filter(zone => formData.zones.includes(zone.id))}
                      onChange={(_, values) => {
                        setFormData(prev => ({
                          ...prev,
                          zones: values.map(v => v.id),
                        }));
                      }}
                      renderTags={(value, getTagProps) =>
                        value.map((option, index) => (
                          <Chip
                            label={option.name}
                            {...getTagProps({ index })}
                            key={option.id}
                          />
                        ))
                      }
                      renderInput={(params) => (
                        <TextField
                          {...params}
                          placeholder="Select zones"
                          helperText="Select the zones covered by this contract"
                        />
                      )}
                    />
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      No zones available for this company
                    </Typography>
                  )}
                </Box>
              </>
            )}

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