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
  });

  const [zones, setZones] = useState<ZoneFormData[]>([
    { name: '', platform: 'soundtrack', tempId: generateTempId() }
  ]);
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
    });

    // For edit mode, zones will be managed separately (not in this form for now)
    setZones([{ name: '', platform: 'soundtrack', tempId: generateTempId() }]);
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
    });
    setZones([{ name: '', platform: 'soundtrack', tempId: generateTempId() }]);
    setAttachments([]);
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