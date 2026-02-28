import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  GridLegacy as Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Typography,
  Autocomplete,
  CircularProgress,
  Alert,
  IconButton,
} from '@mui/material';
import {
  Close as CloseIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Opportunity, Company, User, OpportunityActivity } from '../types';
import ApiService from '../services/api';
import ActivityForm from './ActivityForm';
import ActivityTimeline from './ActivityTimeline';
import { formatCurrency as formatCurrencyFn } from '../constants/entities';

interface OpportunityFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (opportunity: Opportunity) => void;
  opportunity?: Opportunity | null;
  mode: 'create' | 'edit';
}

const stageOptions = [
  { value: 'Contacted', label: 'Contacted', color: '#2196f3' },
  { value: 'Quotation Sent', label: 'Quotation Sent', color: '#ff9800' },
  { value: 'Contract Sent', label: 'Contract Sent', color: '#9c27b0' },
  { value: 'Won', label: 'Won', color: '#4caf50' },
  { value: 'Lost', label: 'Lost', color: '#f44336' },
];

const leadSourceOptions = [
  'Website Inquiry',
  'Referral',
  'Cold Call',
  'Email Campaign',
  'Social Media',
  'Trade Show',
  'Partner',
  'Direct Mail',
  'Webinar',
  'Other',
];

const contactMethodOptions = [
  'Phone',
  'Email',
  'In-person Meeting',
  'Video Call',
  'Chat',
  'Social Media',
  'Other',
];

const OpportunityForm: React.FC<OpportunityFormProps> = ({
  open,
  onClose,
  onSave,
  opportunity,
  mode,
}) => {
  const [formData, setFormData] = useState<Partial<Opportunity>>({
    name: '',
    stage: 'Contacted',
    expected_value: 0,
    probability: 10,
    lead_source: '',
    contact_method: '',
    notes: '',
    competitors: '',
    pain_points: '',
    expected_close_date: undefined,
    follow_up_date: undefined,
    service_type: null,
  });

  const [companies, setCompanies] = useState<Company[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [companiesLoading, setCompaniesLoading] = useState(false);
  const [usersLoading, setUsersLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [activityFormOpen, setActivityFormOpen] = useState(false);
  const [recentActivities, setRecentActivities] = useState<OpportunityActivity[]>([]);

  useEffect(() => {
    if (open) {
      loadCompanies();
      loadUsers();
      
      if (mode === 'edit' && opportunity) {
        setFormData({
          ...opportunity,
          expected_close_date: opportunity.expected_close_date || undefined,
          follow_up_date: opportunity.follow_up_date || undefined,
          service_type: opportunity.service_type || null,
        });
        loadRecentActivities(opportunity.id);
      } else {
        setFormData({
          name: '',
          stage: 'Contacted',
          expected_value: 0,
          probability: 10,
          lead_source: '',
          contact_method: '',
          notes: '',
          competitors: '',
          pain_points: '',
          expected_close_date: undefined,
          follow_up_date: undefined,
          service_type: null,
        });
      }
      setError('');
      setErrors({});
    }
  }, [open, opportunity, mode]);

  const loadCompanies = async () => {
    try {
      setCompaniesLoading(true);
      const response = await ApiService.getCompanies({ page_size: 1000, ordering: 'name' });
      setCompanies(response.results);
    } catch (err) {
      console.error('Failed to load companies:', err);
    } finally {
      setCompaniesLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      setUsersLoading(true);
      const response = await ApiService.getUsers({ page_size: 100 });
      setUsers(response.results);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setUsersLoading(false);
    }
  };

  const loadRecentActivities = async (opportunityId: string) => {
    try {
      const activities = await ApiService.getActivitiesByOpportunity(opportunityId);
      setRecentActivities(activities.slice(0, 3)); // Show only 3 most recent
    } catch (err) {
      console.error('Failed to load recent activities:', err);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name?.trim()) {
      newErrors.name = 'Opportunity name is required';
    }

    if (!formData.company) {
      newErrors.company = 'Company is required';
    }

    if (!formData.owner) {
      newErrors.owner = 'Owner is required';
    }

    if (mode === 'create' && !formData.service_type) {
      newErrors.service_type = 'Service type is required';
    }

    if (formData.probability !== undefined && (formData.probability < 0 || formData.probability > 100)) {
      newErrors.probability = 'Probability must be between 0 and 100';
    }

    if (formData.expected_value !== undefined && formData.expected_value < 0) {
      newErrors.expected_value = 'Expected value cannot be negative';
    }

    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0) {
      // Scroll to first error field so user can see it
      const firstErrorField = Object.keys(newErrors)[0];
      const el = document.querySelector(`[name="${firstErrorField}"], [data-field="${firstErrorField}"]`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (field: keyof Opportunity, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear error for this field when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const handleProbabilityChange = (event: Event, value: number | number[]) => {
    handleInputChange('probability', value as number);
  };

  const handleSubmit = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      setLoading(true);
      setError('');

      let result: Opportunity;
      if (mode === 'edit' && opportunity?.id) {
        result = await ApiService.updateOpportunity(opportunity.id, formData);
      } else {
        result = await ApiService.createOpportunity(formData);
      }

      onSave(result);
      onClose();
    } catch (err: any) {
      const data = err.response?.data;
      let errorMessage = 'Failed to save opportunity';
      if (data) {
        if (typeof data === 'string') {
          errorMessage = data;
        } else if (data.detail) {
          errorMessage = data.detail;
        } else if (typeof data === 'object') {
          // DRF validation errors: { field: ["error"] }
          const fieldErrors = Object.entries(data)
            .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
            .join('; ');
          errorMessage = fieldErrors || errorMessage;
        }
      }
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number): string => {
    // Find the selected company for currency
    const selectedCompany = companies.find(c => c.id === formData.company);
    const entityForCurrency = selectedCompany?.billing_entity;
    return formatCurrencyFn(value, entityForCurrency);
  };

  const getSelectedStage = () => {
    return stageOptions.find(stage => stage.value === formData.stage);
  };

  const handleActivityCreated = (activity: OpportunityActivity) => {
    // Refresh recent activities if we're editing an opportunity
    if (mode === 'edit' && opportunity) {
      loadRecentActivities(opportunity.id);
    }
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Dialog 
        open={open} 
        onClose={onClose} 
        maxWidth="md" 
        fullWidth
        PaperProps={{
          sx: { height: '90vh' }
        }}
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">
              {mode === 'edit' ? 'Edit Opportunity' : 'Create New Opportunity'}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              {mode === 'edit' && opportunity && (
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={() => setActivityFormOpen(true)}
                >
                  Log Activity
                </Button>
              )}
              <IconButton onClick={onClose} size="small">
                <CloseIcon />
              </IconButton>
            </Box>
          </Box>
        </DialogTitle>
        
        <DialogContent dividers sx={{ p: 3 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <Grid container spacing={3}>
            {/* Basic Information */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary">
                Basic Information
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Autocomplete
                options={companies}
                getOptionLabel={(option) => option.name}
                loading={companiesLoading}
                value={companies.find(c => c.id === formData.company) || null}
                onChange={(event, newValue) => {
                  handleInputChange('company', newValue?.id || '');
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Company *"
                    error={!!errors.company}
                    helperText={errors.company}
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <React.Fragment>
                          {companiesLoading ? <CircularProgress color="inherit" size={20} /> : null}
                          {params.InputProps.endAdornment}
                        </React.Fragment>
                      ),
                    }}
                  />
                )}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Opportunity Name *"
                value={formData.name || ''}
                onChange={(e) => handleInputChange('name', e.target.value)}
                error={!!errors.name}
                helperText={errors.name}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth required>
                <InputLabel>Service</InputLabel>
                <Select
                  value={formData.service_type || ''}
                  onChange={(e) => handleInputChange('service_type', e.target.value || null)}
                  label="Service"
                  error={!!errors.service_type}
                >
                  <MenuItem value="soundtrack">Soundtrack</MenuItem>
                  <MenuItem value="beatbreeze">Beat Breeze</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Stage</InputLabel>
                <Select
                  value={formData.stage || 'Contacted'}
                  onChange={(e) => handleInputChange('stage', e.target.value)}
                  label="Stage"
                >
                  {stageOptions.map((stage) => (
                    <MenuItem key={stage.value} value={stage.value}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Box
                          sx={{
                            width: 12,
                            height: 12,
                            borderRadius: '50%',
                            backgroundColor: stage.color,
                            mr: 1,
                          }}
                        />
                        {stage.label}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Autocomplete
                options={users}
                getOptionLabel={(option) => `${option.first_name} ${option.last_name} (${option.role})`}
                loading={usersLoading}
                value={users.find(u => u.id === formData.owner) || null}
                onChange={(event, newValue) => {
                  handleInputChange('owner', newValue?.id || '');
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Owner *"
                    error={!!errors.owner}
                    helperText={errors.owner}
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <React.Fragment>
                          {usersLoading ? <CircularProgress color="inherit" size={20} /> : null}
                          {params.InputProps.endAdornment}
                        </React.Fragment>
                      ),
                    }}
                  />
                )}
              />
            </Grid>

            {/* Financial Information */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary" sx={{ mt: 2 }}>
                Financial Details
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Expected Value"
                type="number"
                value={formData.expected_value || 0}
                onChange={(e) => handleInputChange('expected_value', parseFloat(e.target.value) || 0)}
                error={!!errors.expected_value}
                helperText={errors.expected_value || `Weighted Value: ${formatCurrency((formData.expected_value || 0) * (formData.probability || 0) / 100)}`}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <Box>
                <Typography gutterBottom>
                  Probability: {formData.probability || 0}%
                </Typography>
                <Slider
                  value={formData.probability || 0}
                  onChange={handleProbabilityChange}
                  valueLabelDisplay="auto"
                  step={5}
                  marks
                  min={0}
                  max={100}
                  valueLabelFormat={(value) => `${value}%`}
                  sx={{
                    '& .MuiSlider-track': {
                      backgroundColor: getSelectedStage()?.color || '#2196f3',
                    },
                    '& .MuiSlider-thumb': {
                      backgroundColor: getSelectedStage()?.color || '#2196f3',
                    },
                  }}
                />
              </Box>
            </Grid>

            {/* Contact Information */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary" sx={{ mt: 2 }}>
                Contact & Source
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Autocomplete
                freeSolo
                options={leadSourceOptions}
                value={formData.lead_source || ''}
                onChange={(event, newValue) => {
                  handleInputChange('lead_source', newValue || '');
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Lead Source"
                  />
                )}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <Autocomplete
                freeSolo
                options={contactMethodOptions}
                value={formData.contact_method || ''}
                onChange={(event, newValue) => {
                  handleInputChange('contact_method', newValue || '');
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Contact Method"
                  />
                )}
              />
            </Grid>

            {/* Dates */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary" sx={{ mt: 2 }}>
                Important Dates
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <DatePicker
                label="Expected Close Date"
                value={formData.expected_close_date ? new Date(formData.expected_close_date) : null}
                onChange={(newValue) => {
                  handleInputChange('expected_close_date', newValue ? newValue.toISOString().split('T')[0] : null);
                }}
                slotProps={{
                  textField: {
                    fullWidth: true,
                  },
                }}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <DatePicker
                label="Follow-up Date"
                value={formData.follow_up_date ? new Date(formData.follow_up_date) : null}
                onChange={(newValue) => {
                  handleInputChange('follow_up_date', newValue ? newValue.toISOString().split('T')[0] : null);
                }}
                slotProps={{
                  textField: {
                    fullWidth: true,
                  },
                }}
              />
            </Grid>

            {/* Additional Information */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary" sx={{ mt: 2 }}>
                Additional Details
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Notes"
                value={formData.notes || ''}
                onChange={(e) => handleInputChange('notes', e.target.value)}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                multiline
                rows={2}
                label="Competitors"
                value={formData.competitors || ''}
                onChange={(e) => handleInputChange('competitors', e.target.value)}
                placeholder="List known competitors..."
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                multiline
                rows={2}
                label="Pain Points"
                value={formData.pain_points || ''}
                onChange={(e) => handleInputChange('pain_points', e.target.value)}
                placeholder="Customer challenges to address..."
              />
            </Grid>

            {/* Recent Activities Section */}
            {mode === 'edit' && opportunity && recentActivities.length > 0 && (
              <>
                <Grid item xs={12}>
                  <Typography variant="h6" gutterBottom color="primary" sx={{ mt: 2 }}>
                    Recent Activities
                  </Typography>
                </Grid>
                <Grid item xs={12}>
                  <ActivityTimeline
                    activities={recentActivities}
                    compact={true}
                    showFilters={false}
                    onEditActivity={(activity) => {
                      // Could open activity form in edit mode
                      console.log('Edit activity:', activity);
                    }}
                  />
                </Grid>
              </>
            )}
          </Grid>
        </DialogContent>
        
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button 
            onClick={handleSubmit}
            variant="contained"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} /> : null}
          >
            {loading ? 'Saving...' : (mode === 'edit' ? 'Update' : 'Create')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Activity Form Dialog */}
      <ActivityForm
        open={activityFormOpen}
        onClose={() => setActivityFormOpen(false)}
        onSave={handleActivityCreated}
        opportunity={opportunity}
        mode="create"
      />
    </LocalizationProvider>
  );
};

export default OpportunityForm;