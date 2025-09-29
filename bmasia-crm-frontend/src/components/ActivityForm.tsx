import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Autocomplete,
  CircularProgress,
  Alert,
  IconButton,
  FormControlLabel,
  Checkbox,
  InputAdornment,
} from '@mui/material';
import {
  Close as CloseIcon,
  Phone as PhoneIcon,
  Email as EmailIcon,
  Groups as GroupsIcon,
  Slideshow as SlideshowIcon,
  Description as ProposalIcon,
  FollowUp as FollowUpIcon,
  RequestQuote as QuoteIcon,
  Assignment as ContractIcon,
  MoreHoriz as OtherIcon,
  AccessTime as DurationIcon,
} from '@mui/icons-material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV2';
import { OpportunityActivity, Contact, Opportunity, User } from '../types';
import ApiService from '../services/api';

interface ActivityFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (activity: OpportunityActivity) => void;
  opportunity?: Opportunity | null;
  contact?: Contact | null;
  activity?: OpportunityActivity | null;
  mode: 'create' | 'edit';
}

const activityTypes = [
  { value: 'Call', label: 'Call', icon: PhoneIcon, color: '#2196f3' },
  { value: 'Email', label: 'Email', icon: EmailIcon, color: '#ff9800' },
  { value: 'Meeting', label: 'Meeting', icon: GroupsIcon, color: '#4caf50' },
  { value: 'Demo', label: 'Demo', icon: SlideshowIcon, color: '#9c27b0' },
  { value: 'Proposal', label: 'Proposal', icon: ProposalIcon, color: '#f44336' },
  { value: 'Follow-up', label: 'Follow-up', icon: FollowUpIcon, color: '#ff5722' },
  { value: 'Quote', label: 'Quote', icon: QuoteIcon, color: '#607d8b' },
  { value: 'Contract', label: 'Contract', icon: ContractIcon, color: '#795548' },
  { value: 'Other', label: 'Other', icon: OtherIcon, color: '#9e9e9e' },
];

const ActivityForm: React.FC<ActivityFormProps> = ({
  open,
  onClose,
  onSave,
  opportunity,
  contact,
  activity,
  mode,
}) => {
  const [formData, setFormData] = useState<Partial<OpportunityActivity>>({
    activity_type: 'Call',
    subject: '',
    description: '',
    duration_minutes: undefined,
    date: new Date().toISOString(),
    completed: false,
    next_action_date: undefined,
  });

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [opportunitiesLoading, setOpportunitiesLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [nextActionRequired, setNextActionRequired] = useState(false);

  useEffect(() => {
    if (open) {
      if (!opportunity) {
        loadOpportunities();
      }

      if (mode === 'edit' && activity) {
        setFormData({
          ...activity,
          date: activity.date,
          next_action_date: activity.next_action_date,
        });
        setNextActionRequired(!!activity.next_action_date);
      } else {
        const initialData: Partial<OpportunityActivity> = {
          activity_type: 'Call',
          subject: '',
          description: '',
          duration_minutes: undefined,
          date: new Date().toISOString(),
          completed: false,
          next_action_date: undefined,
        };

        if (opportunity) {
          initialData.opportunity = opportunity.id;
        }
        if (contact) {
          initialData.contact = contact.id;
        }

        setFormData(initialData);
        setNextActionRequired(false);
      }

      setError('');
      setErrors({});
    }
  }, [open, activity, mode, opportunity, contact]);

  useEffect(() => {
    if (opportunity && open) {
      loadContactsForOpportunity(opportunity.id);
    }
  }, [opportunity, open]);

  const loadOpportunities = async () => {
    try {
      setOpportunitiesLoading(true);
      const response = await ApiService.getOpportunities({ page_size: 100 });
      setOpportunities(response.results);
    } catch (err) {
      console.error('Failed to load opportunities:', err);
    } finally {
      setOpportunitiesLoading(false);
    }
  };

  const loadContactsForOpportunity = async (opportunityId: string) => {
    try {
      setContactsLoading(true);
      const selectedOpportunity = opportunities.find(o => o.id === opportunityId) || opportunity;
      if (selectedOpportunity) {
        const response = await ApiService.getContacts({ company: selectedOpportunity.company });
        setContacts(response.results);
      }
    } catch (err) {
      console.error('Failed to load contacts:', err);
    } finally {
      setContactsLoading(false);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.activity_type) {
      newErrors.activity_type = 'Activity type is required';
    }

    if (!formData.subject?.trim()) {
      newErrors.subject = 'Subject is required';
    }

    if (!formData.opportunity) {
      newErrors.opportunity = 'Opportunity is required';
    }

    if (!formData.date) {
      newErrors.date = 'Date is required';
    }

    if (formData.duration_minutes !== undefined && formData.duration_minutes < 0) {
      newErrors.duration_minutes = 'Duration cannot be negative';
    }

    if (nextActionRequired && !formData.next_action_date) {
      newErrors.next_action_date = 'Follow-up date is required when next action is needed';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (field: keyof OpportunityActivity, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));

    // Clear error for this field when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const handleOpportunityChange = (opportunityId: string) => {
    handleInputChange('opportunity', opportunityId);
    loadContactsForOpportunity(opportunityId);
    // Clear contact selection when opportunity changes
    setFormData(prev => ({ ...prev, contact: undefined }));
  };

  const handleNextActionChange = (checked: boolean) => {
    setNextActionRequired(checked);
    if (!checked) {
      handleInputChange('next_action_date', undefined);
    }
  };

  const handleSubmit = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      setLoading(true);
      setError('');

      const submitData = {
        ...formData,
        next_action_date: nextActionRequired ? formData.next_action_date : undefined,
      };

      let result: OpportunityActivity;
      if (mode === 'edit' && activity?.id) {
        result = await ApiService.updateOpportunityActivity(activity.id, submitData);
      } else {
        result = await ApiService.createOpportunityActivity(submitData);
      }

      onSave(result);
      onClose();
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail ||
                          err.response?.data?.message ||
                          'Failed to save activity';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const getActivityIcon = (activityType: string) => {
    const type = activityTypes.find(t => t.value === activityType);
    if (!type) return OtherIcon;
    return type.icon;
  };

  const getActivityColor = (activityType: string) => {
    const type = activityTypes.find(t => t.value === activityType);
    return type?.color || '#9e9e9e';
  };

  const shouldShowDuration = () => {
    return ['Call', 'Meeting', 'Demo'].includes(formData.activity_type || '');
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
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              {formData.activity_type && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    backgroundColor: getActivityColor(formData.activity_type),
                    color: 'white',
                    mr: 2,
                  }}
                >
                  {React.createElement(getActivityIcon(formData.activity_type), { fontSize: 'small' })}
                </Box>
              )}
              <Typography variant="h6">
                {mode === 'edit' ? 'Edit Activity' : 'Log New Activity'}
              </Typography>
            </Box>
            <IconButton onClick={onClose} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent dividers sx={{ p: 3 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <Grid container spacing={3}>
            {/* Activity Type and Subject */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary">
                Activity Details
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth error={!!errors.activity_type}>
                <InputLabel>Activity Type *</InputLabel>
                <Select
                  value={formData.activity_type || ''}
                  onChange={(e) => handleInputChange('activity_type', e.target.value)}
                  label="Activity Type *"
                >
                  {activityTypes.map((type) => (
                    <MenuItem key={type.value} value={type.value}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 20,
                            height: 20,
                            borderRadius: '50%',
                            backgroundColor: type.color,
                            color: 'white',
                            mr: 1,
                          }}
                        >
                          <type.icon sx={{ fontSize: 12 }} />
                        </Box>
                        {type.label}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
                {errors.activity_type && (
                  <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                    {errors.activity_type}
                  </Typography>
                )}
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Subject/Title *"
                value={formData.subject || ''}
                onChange={(e) => handleInputChange('subject', e.target.value)}
                error={!!errors.subject}
                helperText={errors.subject}
                placeholder="Brief description of the activity"
              />
            </Grid>

            {/* Opportunity and Contact */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary" sx={{ mt: 2 }}>
                Related Records
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              {opportunity ? (
                <TextField
                  fullWidth
                  label="Opportunity"
                  value={opportunity.name}
                  disabled
                  helperText="Opportunity is pre-selected"
                />
              ) : (
                <Autocomplete
                  options={opportunities}
                  getOptionLabel={(option) => `${option.name} - ${option.company_name}`}
                  loading={opportunitiesLoading}
                  value={opportunities.find(o => o.id === formData.opportunity) || null}
                  onChange={(event, newValue) => {
                    handleOpportunityChange(newValue?.id || '');
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Opportunity *"
                      error={!!errors.opportunity}
                      helperText={errors.opportunity}
                      InputProps={{
                        ...params.InputProps,
                        endAdornment: (
                          <React.Fragment>
                            {opportunitiesLoading ? <CircularProgress color="inherit" size={20} /> : null}
                            {params.InputProps.endAdornment}
                          </React.Fragment>
                        ),
                      }}
                    />
                  )}
                />
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              <Autocomplete
                options={contacts}
                getOptionLabel={(option) => `${option.name} (${option.title || 'No title'})`}
                loading={contactsLoading}
                value={contacts.find(c => c.id === formData.contact) || null}
                onChange={(event, newValue) => {
                  handleInputChange('contact', newValue?.id || undefined);
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Contact"
                    helperText="Optional - specify if activity was with a specific contact"
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <React.Fragment>
                          {contactsLoading ? <CircularProgress color="inherit" size={20} /> : null}
                          {params.InputProps.endAdornment}
                        </React.Fragment>
                      ),
                    }}
                  />
                )}
              />
            </Grid>

            {/* Date and Duration */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary" sx={{ mt: 2 }}>
                Timing
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <DateTimePicker
                label="Date & Time *"
                value={formData.date ? new Date(formData.date) : null}
                onChange={(newValue) => {
                  handleInputChange('date', newValue ? newValue.toISOString() : new Date().toISOString());
                }}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    error: !!errors.date,
                    helperText: errors.date,
                  },
                }}
              />
            </Grid>

            {shouldShowDuration() && (
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Duration (minutes)"
                  type="number"
                  value={formData.duration_minutes || ''}
                  onChange={(e) => handleInputChange('duration_minutes', parseInt(e.target.value) || undefined)}
                  error={!!errors.duration_minutes}
                  helperText={errors.duration_minutes || 'How long did this activity take?'}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <DurationIcon />
                      </InputAdornment>
                    ),
                  }}
                />
              </Grid>
            )}

            {/* Description */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary" sx={{ mt: 2 }}>
                Activity Notes
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={4}
                label="Description/Notes"
                value={formData.description || ''}
                onChange={(e) => handleInputChange('description', e.target.value)}
                placeholder="Detailed notes about the activity, outcomes, key points discussed..."
              />
            </Grid>

            {/* Next Actions */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary" sx={{ mt: 2 }}>
                Follow-up Actions
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={nextActionRequired}
                    onChange={(e) => handleNextActionChange(e.target.checked)}
                    color="primary"
                  />
                }
                label="Next action required"
              />
            </Grid>

            {nextActionRequired && (
              <Grid item xs={12} sm={6}>
                <DatePicker
                  label="Follow-up Date *"
                  value={formData.next_action_date ? new Date(formData.next_action_date) : null}
                  onChange={(newValue) => {
                    handleInputChange('next_action_date', newValue ? newValue.toISOString().split('T')[0] : undefined);
                  }}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      error: !!errors.next_action_date,
                      helperText: errors.next_action_date || 'When should the follow-up happen?',
                    },
                  }}
                />
              </Grid>
            )}

            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={formData.completed || false}
                    onChange={(e) => handleInputChange('completed', e.target.checked)}
                    color="primary"
                  />
                }
                label="Mark as completed"
              />
            </Grid>
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
            {loading ? 'Saving...' : (mode === 'edit' ? 'Update Activity' : 'Log Activity')}
          </Button>
        </DialogActions>
      </Dialog>
    </LocalizationProvider>
  );
};

export default ActivityForm;