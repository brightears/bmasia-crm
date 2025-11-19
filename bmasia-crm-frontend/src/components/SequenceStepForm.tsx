import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  GridLegacy as Grid,
  FormControlLabel,
  Switch,
  Typography,
  Alert,
  CircularProgress,
  Autocomplete,
} from '@mui/material';
import {
  Save,
  Cancel,
} from '@mui/icons-material';
import { SequenceStep, EmailTemplate } from '../types';
import ApiService from '../services/api';

interface SequenceStepFormProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  sequenceId: string;
  step?: SequenceStep;
  existingSteps: SequenceStep[];
}

interface FormData {
  step_number: number;
  name: string;
  email_template: string;
  delay_days: number;
  is_active: boolean;
}

const SequenceStepForm: React.FC<SequenceStepFormProps> = ({
  open,
  onClose,
  onSuccess,
  sequenceId,
  step,
  existingSteps,
}) => {
  const [formData, setFormData] = useState<FormData>({
    step_number: 1,
    name: '',
    email_template: '',
    delay_days: 0,
    is_active: true,
  });

  const [emailTemplates, setEmailTemplates] = useState<EmailTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Load email templates on mount
  useEffect(() => {
    if (open) {
      loadEmailTemplates();
    }
  }, [open]);

  // Set form data when step changes
  useEffect(() => {
    if (step) {
      setFormData({
        step_number: step.step_number || 1,
        name: step.name || '',
        email_template: step.email_template || '',
        delay_days: step.delay_days || 0,
        is_active: step.is_active ?? true,
      });

      // Find and set the selected template
      const template = emailTemplates.find((t) => t.id === step.email_template);
      setSelectedTemplate(template || null);
    } else {
      // Calculate next step number for new steps
      const maxStepNumber = existingSteps.reduce((max, s) => Math.max(max, s.step_number), 0);
      setFormData({
        step_number: maxStepNumber + 1,
        name: '',
        email_template: '',
        delay_days: 0,
        is_active: true,
      });
      setSelectedTemplate(null);
    }
    setError('');
    setErrors({});
  }, [step, existingSteps, open, emailTemplates]);

  const loadEmailTemplates = async () => {
    try {
      setLoadingTemplates(true);
      const response = await ApiService.getEmailTemplates({ is_active: true });
      setEmailTemplates(response.results || []);
    } catch (err: any) {
      console.error('Failed to load email templates:', err);
      setError('Failed to load email templates');
    } finally {
      setLoadingTemplates(false);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Step name is required';
    } else if (formData.name.length > 200) {
      newErrors.name = 'Step name must be 200 characters or less';
    }

    if (!formData.email_template) {
      newErrors.email_template = 'Email template is required';
    }

    if (formData.step_number < 1) {
      newErrors.step_number = 'Step number must be at least 1';
    } else if (!step) {
      // Only validate uniqueness for new steps
      const isDuplicate = existingSteps.some((s) => s.step_number === formData.step_number);
      if (isDuplicate) {
        newErrors.step_number = 'Step number already exists. Please choose a different number.';
      }
    }

    if (formData.delay_days < 0) {
      newErrors.delay_days = 'Delay days must be 0 or greater';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    setLoading(true);
    setError('');

    try {
      const submitData = {
        sequence: sequenceId,
        step_number: formData.step_number,
        name: formData.name,
        email_template: formData.email_template,
        delay_days: formData.delay_days,
        is_active: formData.is_active,
      };

      if (step) {
        await ApiService.updateSequenceStep(step.id, submitData);
      } else {
        await ApiService.createSequenceStep(submitData);
      }

      onSuccess();
    } catch (err: any) {
      console.error('Step save error:', err);
      if (err.response?.data) {
        if (typeof err.response.data === 'object') {
          const fieldErrors: Record<string, string> = {};
          Object.keys(err.response.data).forEach((field) => {
            if (Array.isArray(err.response.data[field])) {
              fieldErrors[field] = err.response.data[field][0];
            } else {
              fieldErrors[field] = err.response.data[field];
            }
          });
          setErrors(fieldErrors);
        } else {
          setError(err.response.data.message || 'Failed to save step');
        }
      } else {
        setError('Failed to save step. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  const handleFieldChange = (field: keyof FormData, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));

    if (errors[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: '',
      }));
    }
  };

  const handleTemplateChange = (_event: any, newValue: EmailTemplate | null) => {
    setSelectedTemplate(newValue);
    if (newValue) {
      handleFieldChange('email_template', newValue.id);
    } else {
      handleFieldChange('email_template', '');
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Typography variant="h6">
          {step ? 'Edit Step' : 'Add Step'}
        </Typography>
      </DialogTitle>

      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {loadingTemplates && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <CircularProgress size={16} sx={{ mr: 1 }} />
            Loading email templates...
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Step Number"
              type="number"
              value={formData.step_number}
              onChange={(e) => handleFieldChange('step_number', parseInt(e.target.value) || 1)}
              error={!!errors.step_number}
              helperText={errors.step_number || 'Order in sequence (1, 2, 3, ...)'}
              required
              size="medium"
              inputProps={{ min: 1 }}
              disabled={!!step} // Read-only when editing
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Step Name"
              value={formData.name}
              onChange={(e) => handleFieldChange('name', e.target.value)}
              error={!!errors.name}
              helperText={errors.name || "e.g., 'Welcome Email', 'Day 3 Tips'"}
              required
              size="medium"
              inputProps={{ maxLength: 200 }}
            />
          </Grid>

          <Grid item xs={12}>
            <Autocomplete
              options={emailTemplates}
              value={selectedTemplate}
              onChange={handleTemplateChange}
              getOptionLabel={(option) => option.name}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Email Template"
                  error={!!errors.email_template}
                  helperText={errors.email_template || 'Select the email template to send for this step'}
                  required
                  size="medium"
                />
              )}
              loading={loadingTemplates}
              disabled={loadingTemplates}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Delay (days)"
              type="number"
              value={formData.delay_days}
              onChange={(e) => handleFieldChange('delay_days', parseInt(e.target.value) || 0)}
              error={!!errors.delay_days}
              helperText={errors.delay_days || 'Days to wait after previous step (0 for immediate)'}
              required
              size="medium"
              inputProps={{ min: 0 }}
            />
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.is_active}
                  onChange={(e) => handleFieldChange('is_active', e.target.checked)}
                  color="primary"
                />
              }
              label="Active"
            />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', ml: 4 }}>
              Inactive steps are skipped during execution
            </Typography>
          </Grid>

          {formData.step_number === 1 && (
            <Grid item xs={12}>
              <Alert severity="info">
                Step 1 will be sent {formData.delay_days === 0 ? 'immediately' : `${formData.delay_days} day${formData.delay_days !== 1 ? 's' : ''} after`} enrollment.
              </Alert>
            </Grid>
          )}

          {formData.step_number > 1 && (
            <Grid item xs={12}>
              <Alert severity="info">
                This step will be sent {formData.delay_days === 0 ? 'immediately' : `${formData.delay_days} day${formData.delay_days !== 1 ? 's' : ''}`} after the previous step.
              </Alert>
            </Grid>
          )}
        </Grid>
      </DialogContent>

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button onClick={handleClose} disabled={loading} startIcon={<Cancel />}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading || loadingTemplates}
          startIcon={loading ? <CircularProgress size={20} /> : <Save />}
          sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
        >
          {loading ? 'Saving...' : step ? 'Update Step' : 'Add Step'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SequenceStepForm;
