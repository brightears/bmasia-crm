import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  GridLegacy as Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Box,
  Typography,
  Alert,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Paper,
  Tooltip,
  FormHelperText,
} from '@mui/material';
import {
  Save,
  Cancel,
  ExpandMore,
  ContentCopy,
  Code,
} from '@mui/icons-material';
import { EmailTemplate } from '../types';
import ApiService from '../services/api';

interface EmailTemplateFormProps {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  template: EmailTemplate | null;
}

interface FormData {
  name: string;
  template_type: string;
  language: 'en' | 'th';
  department: string;
  subject: string;
  body_text: string;
  body_html: string;
  notes: string;
  is_active: boolean;
}

const TEMPLATE_TYPES = [
  { value: 'renewal_30_days', label: 'Renewal 30 Days' },
  { value: 'renewal_14_days', label: 'Renewal 14 Days' },
  { value: 'renewal_7_days', label: 'Renewal 7 Days' },
  { value: 'renewal_urgent', label: 'Renewal Urgent' },
  { value: 'invoice_new', label: 'Invoice New' },
  { value: 'payment_reminder_7_days', label: 'Payment Reminder 7 Days' },
  { value: 'payment_reminder_14_days', label: 'Payment Reminder 14 Days' },
  { value: 'payment_overdue', label: 'Payment Overdue' },
  { value: 'quarterly_checkin', label: 'Quarterly Check-in' },
  { value: 'seasonal_christmas', label: 'Seasonal Christmas' },
  { value: 'seasonal_newyear', label: 'Seasonal New Year' },
  { value: 'seasonal_songkran', label: 'Seasonal Songkran' },
  { value: 'seasonal_ramadan', label: 'Seasonal Ramadan' },
  { value: 'zone_offline_48h', label: 'Zone Offline 48h' },
  { value: 'zone_offline_7d', label: 'Zone Offline 7d' },
  { value: 'welcome', label: 'Welcome' },
  { value: 'contract_signed', label: 'Contract Signed' },
  { value: 'quote_send', label: 'Quote Send' },
  { value: 'contract_send', label: 'Contract Send' },
  { value: 'invoice_send', label: 'Invoice Send' },
  { value: 'renewal_manual', label: 'Renewal Manual' },
];

// Predefined variables for each template type
const TEMPLATE_VARIABLES: Record<string, string[]> = {
  renewal_30_days: ['{{company_name}}', '{{contract_number}}', '{{end_date}}', '{{contact_name}}'],
  renewal_14_days: ['{{company_name}}', '{{contract_number}}', '{{end_date}}', '{{contact_name}}'],
  renewal_7_days: ['{{company_name}}', '{{contract_number}}', '{{end_date}}', '{{contact_name}}'],
  renewal_urgent: ['{{company_name}}', '{{contract_number}}', '{{end_date}}', '{{contact_name}}'],
  invoice_new: ['{{company_name}}', '{{invoice_number}}', '{{amount}}', '{{due_date}}', '{{contact_name}}'],
  payment_reminder_7_days: ['{{company_name}}', '{{invoice_number}}', '{{amount}}', '{{due_date}}', '{{contact_name}}'],
  payment_reminder_14_days: ['{{company_name}}', '{{invoice_number}}', '{{amount}}', '{{due_date}}', '{{contact_name}}'],
  payment_overdue: ['{{company_name}}', '{{invoice_number}}', '{{amount}}', '{{days_overdue}}', '{{contact_name}}'],
  quarterly_checkin: ['{{company_name}}', '{{contact_name}}', '{{quarter}}'],
  seasonal_christmas: ['{{company_name}}', '{{contact_name}}'],
  seasonal_newyear: ['{{company_name}}', '{{contact_name}}'],
  seasonal_songkran: ['{{company_name}}', '{{contact_name}}'],
  seasonal_ramadan: ['{{company_name}}', '{{contact_name}}'],
  zone_offline_48h: ['{{company_name}}', '{{zone_name}}', '{{offline_duration}}', '{{contact_name}}'],
  zone_offline_7d: ['{{company_name}}', '{{zone_name}}', '{{offline_duration}}', '{{contact_name}}'],
  welcome: ['{{company_name}}', '{{contact_name}}'],
  contract_signed: ['{{company_name}}', '{{contract_number}}', '{{contact_name}}'],
  quote_send: ['{{company_name}}', '{{quote_number}}', '{{amount}}', '{{contact_name}}'],
  contract_send: ['{{company_name}}', '{{contract_number}}', '{{contact_name}}'],
  invoice_send: ['{{company_name}}', '{{invoice_number}}', '{{amount}}', '{{contact_name}}'],
  renewal_manual: ['{{company_name}}', '{{contract_number}}', '{{end_date}}', '{{contact_name}}'],
};

const EmailTemplateForm: React.FC<EmailTemplateFormProps> = ({
  open,
  onClose,
  onSave,
  template,
}) => {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    template_type: '',
    language: 'en',
    department: '',
    subject: '',
    body_text: '',
    body_html: '',
    notes: '',
    is_active: true,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [advancedExpanded, setAdvancedExpanded] = useState(false);

  useEffect(() => {
    if (template) {
      setFormData({
        name: template.name || '',
        template_type: template.template_type || '',
        language: template.language || 'en',
        department: template.department || '',
        subject: template.subject || '',
        body_text: template.body_text || '',
        body_html: template.body_html || '',
        notes: template.notes || '',
        is_active: template.is_active !== undefined ? template.is_active : true,
      });
    } else {
      setFormData({
        name: '',
        template_type: '',
        language: 'en',
        department: '',
        subject: '',
        body_text: '',
        body_html: '',
        notes: '',
        is_active: true,
      });
    }
    setError('');
    setErrors({});
    setAdvancedExpanded(false);
  }, [template, open]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Template name is required';
    }

    if (!formData.template_type) {
      newErrors.template_type = 'Template type is required';
    }

    if (!formData.subject.trim()) {
      newErrors.subject = 'Subject is required';
    }

    if (!formData.body_text.trim()) {
      newErrors.body_text = 'Body text is required';
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
        ...formData,
        department: formData.department || undefined,
        body_html: formData.body_html || undefined,
        notes: formData.notes || undefined,
      };

      if (template) {
        await ApiService.updateEmailTemplate(template.id, submitData);
      } else {
        await ApiService.createEmailTemplate(submitData);
      }

      onSave();
    } catch (err: any) {
      console.error('Template save error:', err);
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
          setError(err.response.data.message || 'Failed to save template');
        }
      } else {
        setError('Failed to save template. Please try again.');
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

  const handleCopyVariable = (variable: string) => {
    navigator.clipboard.writeText(variable);
  };

  const availableVariables = formData.template_type
    ? TEMPLATE_VARIABLES[formData.template_type] || []
    : [];

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Typography variant="h6">
          {template ? 'Edit Email Template' : 'New Email Template'}
        </Typography>
      </DialogTitle>

      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* Basic Information */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Basic Information
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Template Name"
              value={formData.name}
              onChange={(e) => handleFieldChange('name', e.target.value)}
              error={!!errors.name}
              helperText={errors.name}
              required
              size="medium"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth error={!!errors.template_type} size="medium">
              <InputLabel>Template Type *</InputLabel>
              <Select
                value={formData.template_type}
                onChange={(e) => handleFieldChange('template_type', e.target.value)}
                label="Template Type *"
                required
              >
                {TEMPLATE_TYPES.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {errors.template_type && (
              <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                {errors.template_type}
              </Typography>
            )}
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth size="medium">
              <InputLabel>Language *</InputLabel>
              <Select
                value={formData.language}
                onChange={(e) => handleFieldChange('language', e.target.value as 'en' | 'th')}
                label="Language *"
                required
              >
                <MenuItem value="en">English</MenuItem>
                <MenuItem value="th">Thai</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Department</InputLabel>
              <Select
                value={formData.department || ''}
                onChange={(e) => handleFieldChange('department', e.target.value)}
                label="Department"
              >
                <MenuItem value="">
                  <em>None</em>
                </MenuItem>
                <MenuItem value="Sales">Sales</MenuItem>
                <MenuItem value="Finance">Finance</MenuItem>
                <MenuItem value="Tech">Tech Support</MenuItem>
                <MenuItem value="Music">Music Design</MenuItem>
                <MenuItem value="Admin">Admin</MenuItem>
              </Select>
              <FormHelperText>Optional: for organizational purposes</FormHelperText>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6}>
            <Box sx={{ pt: 2 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.is_active}
                    onChange={(e) => handleFieldChange('is_active', e.target.checked)}
                  />
                }
                label="Active"
              />
            </Box>
          </Grid>

          {/* Email Content */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600, mt: 2 }}>
              Email Content
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Subject"
              value={formData.subject}
              onChange={(e) => handleFieldChange('subject', e.target.value)}
              error={!!errors.subject}
              helperText={errors.subject}
              required
              placeholder="e.g., Your contract is expiring soon"
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Body (Text)"
              multiline
              rows={10}
              value={formData.body_text}
              onChange={(e) => handleFieldChange('body_text', e.target.value)}
              error={!!errors.body_text}
              helperText={errors.body_text || 'Plain text email body (required)'}
              required
              placeholder="Enter email body text. Use variables like {{company_name}}, {{contact_name}}, etc."
            />
          </Grid>

          {/* Variable Guide */}
          {availableVariables.length > 0 && (
            <Grid item xs={12}>
              <Paper sx={{ p: 2, backgroundColor: '#f5f5f5' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Code sx={{ mr: 1, fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={600}>
                    Available Variables
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  Click to copy a variable, then paste it into your subject or body
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {availableVariables.map((variable) => (
                    <Tooltip key={variable} title="Click to copy">
                      <Chip
                        label={variable}
                        size="small"
                        onClick={() => handleCopyVariable(variable)}
                        icon={<ContentCopy />}
                        sx={{ cursor: 'pointer' }}
                      />
                    </Tooltip>
                  ))}
                </Box>
              </Paper>
            </Grid>
          )}

          {/* Advanced Section */}
          <Grid item xs={12}>
            <Accordion
              expanded={advancedExpanded}
              onChange={(e, isExpanded) => setAdvancedExpanded(isExpanded)}
            >
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="subtitle1" fontWeight={600}>
                  Advanced Options
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Body (HTML)"
                      multiline
                      rows={10}
                      value={formData.body_html}
                      onChange={(e) => handleFieldChange('body_html', e.target.value)}
                      helperText="Optional: HTML version for rich email clients"
                      placeholder="<html><body>...</body></html>"
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Notes"
                      multiline
                      rows={3}
                      value={formData.notes}
                      onChange={(e) => handleFieldChange('notes', e.target.value)}
                      placeholder="Internal notes about this template..."
                    />
                  </Grid>
                </Grid>
              </AccordionDetails>
            </Accordion>
          </Grid>
        </Grid>
      </DialogContent>

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button onClick={handleClose} disabled={loading} startIcon={<Cancel />}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={20} /> : <Save />}
          sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
        >
          {loading ? 'Saving...' : template ? 'Update Template' : 'Create Template'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EmailTemplateForm;
