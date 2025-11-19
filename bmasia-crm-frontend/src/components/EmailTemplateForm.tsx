import React, { useState, useEffect, useRef } from 'react';
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
import ReactQuill from 'react-quill-new';
import 'react-quill-new/dist/quill.snow.css';
import { EmailTemplate, TemplateVariable } from '../types';
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

// Quill editor configuration
const quillModules = {
  toolbar: [
    [{ 'header': [1, 2, 3, false] }],
    ['bold', 'italic', 'underline', 'strike'],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
    [{ 'color': [] }, { 'background': [] }],
    ['link'],
    ['clean']
  ],
};

// Predefined variables for each template type (matches backend structure)
const TEMPLATE_VARIABLES: Record<string, TemplateVariable[]> = {
  // Common variables included in all templates
  common: [
    { name: 'company_name', description: 'Company name' },
    { name: 'contact_name', description: 'Contact person name' },
    { name: 'current_year', description: 'Current year' },
    { name: 'unsubscribe_url', description: 'Unsubscribe link' },
  ],
  // Renewal templates
  renewal_30_days: [
    { name: 'contract_number', description: 'Contract number' },
    { name: 'end_date', description: 'Contract end date' },
    { name: 'days_until_expiry', description: 'Days until contract expires' },
    { name: 'monthly_value', description: 'Monthly contract value' },
  ],
  renewal_14_days: [
    { name: 'contract_number', description: 'Contract number' },
    { name: 'end_date', description: 'Contract end date' },
    { name: 'days_until_expiry', description: 'Days until contract expires' },
    { name: 'monthly_value', description: 'Monthly contract value' },
  ],
  renewal_7_days: [
    { name: 'contract_number', description: 'Contract number' },
    { name: 'end_date', description: 'Contract end date' },
    { name: 'days_until_expiry', description: 'Days until contract expires' },
    { name: 'monthly_value', description: 'Monthly contract value' },
  ],
  renewal_urgent: [
    { name: 'contract_number', description: 'Contract number' },
    { name: 'end_date', description: 'Contract end date' },
    { name: 'days_until_expiry', description: 'Days until contract expires' },
    { name: 'monthly_value', description: 'Monthly contract value' },
  ],
  // Invoice templates
  invoice_new: [
    { name: 'invoice_number', description: 'Invoice number' },
    { name: 'due_date', description: 'Payment due date' },
    { name: 'total_amount', description: 'Total invoice amount' },
    { name: 'payment_url', description: 'Payment link' },
  ],
  payment_reminder_7_days: [
    { name: 'invoice_number', description: 'Invoice number' },
    { name: 'due_date', description: 'Payment due date' },
    { name: 'total_amount', description: 'Total invoice amount' },
    { name: 'payment_url', description: 'Payment link' },
    { name: 'days_overdue', description: 'Days payment is overdue' },
  ],
  payment_reminder_14_days: [
    { name: 'invoice_number', description: 'Invoice number' },
    { name: 'due_date', description: 'Payment due date' },
    { name: 'total_amount', description: 'Total invoice amount' },
    { name: 'payment_url', description: 'Payment link' },
    { name: 'days_overdue', description: 'Days payment is overdue' },
  ],
  payment_overdue: [
    { name: 'invoice_number', description: 'Invoice number' },
    { name: 'due_date', description: 'Payment due date' },
    { name: 'total_amount', description: 'Total invoice amount' },
    { name: 'payment_url', description: 'Payment link' },
    { name: 'days_overdue', description: 'Days payment is overdue' },
  ],
  // Zone offline templates
  zone_offline_48h: [
    { name: 'zone_name', description: 'Zone name' },
    { name: 'offline_duration', description: 'How long zone has been offline' },
    { name: 'support_email', description: 'Support contact email' },
  ],
  zone_offline_7d: [
    { name: 'zone_name', description: 'Zone name' },
    { name: 'offline_duration', description: 'How long zone has been offline' },
    { name: 'support_email', description: 'Support contact email' },
  ],
  // Quarterly checkin
  quarterly_checkin: [
    { name: 'quarter', description: 'Current quarter (Q1, Q2, Q3, Q4)' },
  ],
  // Seasonal templates
  seasonal_christmas: [],
  seasonal_newyear: [],
  seasonal_songkran: [],
  seasonal_ramadan: [],
  // General templates
  welcome: [
    { name: 'login_url', description: 'Login URL' },
  ],
  contract_signed: [
    { name: 'contract_number', description: 'Contract number' },
    { name: 'start_date', description: 'Contract start date' },
  ],
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
    body_html: '',
    notes: '',
    is_active: true,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [advancedExpanded, setAdvancedExpanded] = useState(false);

  const quillRef = useRef<ReactQuill>(null);

  useEffect(() => {
    if (template) {
      setFormData({
        name: template.name || '',
        template_type: template.template_type || '',
        language: template.language || 'en',
        department: template.department || '',
        subject: template.subject || '',
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

    // Validate body_html is not empty
    if (!formData.body_html || !formData.body_html.trim()) {
      newErrors.body_html = 'Email body is required';
    } else {
      // Check for actual content (not just empty Quill tags like <p><br></p>)
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = formData.body_html;
      const textContent = tempDiv.textContent || '';

      if (!textContent.trim()) {
        newErrors.body_html = 'Email body cannot be empty';
      }
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

  const handleInsertVariable = (variable: string) => {
    if (quillRef.current) {
      const editor = quillRef.current.getEditor();
      const selection = editor.getSelection();
      const index = selection ? selection.index : editor.getLength();
      editor.insertText(index, variable);
      // Move cursor after inserted variable
      editor.setSelection(index + variable.length, 0);
    }
  };

  // Get available variables - prioritize backend data if available
  const availableVariables: TemplateVariable[] = React.useMemo(() => {
    // If editing existing template with variable_list from backend, use that
    if (template?.variable_list && template.variable_list.length > 0) {
      return template.variable_list as TemplateVariable[];
    }

    // Otherwise, combine common variables with template-specific ones
    if (formData.template_type) {
      const common = TEMPLATE_VARIABLES.common || [];
      const specific = TEMPLATE_VARIABLES[formData.template_type] || [];
      return [...common, ...specific];
    }

    return [];
  }, [template, formData.template_type]);

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

          {/* Email Body - Rich Text Editor */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600, mt: 2 }}>
              Email Body
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                Compose your email message using the formatting toolbar. Template variables like {'{{company_name}}'} can be inserted using the buttons below. A plain text version will be automatically generated.
              </Typography>
              <Box sx={{
                mt: 1,
                '& .ql-container': {
                  minHeight: '300px',
                  backgroundColor: 'white',
                  borderBottomLeftRadius: '4px',
                  borderBottomRightRadius: '4px',
                },
                '& .ql-editor': {
                  minHeight: '300px',
                  fontSize: '14px',
                  fontFamily: 'inherit',
                },
                '& .ql-toolbar': {
                  backgroundColor: '#f5f5f5',
                  borderTopLeftRadius: '4px',
                  borderTopRightRadius: '4px',
                },
                '& .ql-toolbar .ql-stroke': {
                  stroke: '#424242',
                },
                '& .ql-toolbar .ql-fill': {
                  fill: '#424242',
                },
                '& .ql-toolbar button:hover .ql-stroke': {
                  stroke: '#FFA500',
                },
                '& .ql-toolbar button:hover .ql-fill': {
                  fill: '#FFA500',
                },
                '& .ql-toolbar button.ql-active .ql-stroke': {
                  stroke: '#FFA500',
                },
                '& .ql-toolbar button.ql-active .ql-fill': {
                  fill: '#FFA500',
                },
              }}>
                <ReactQuill
                  ref={quillRef}
                  theme="snow"
                  value={formData.body_html || ''}
                  onChange={(value) => handleFieldChange('body_html', value)}
                  modules={quillModules}
                  placeholder="Compose your email message..."
                />
              </Box>
              {errors.body_html && (
                <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                  {errors.body_html}
                </Typography>
              )}
            </Box>
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
                  Click "Insert" to add a variable at the cursor position in your email body, or click the variable to copy it.
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {availableVariables.map((variable) => {
                    const varString = `{{${variable.name}}}`;
                    return (
                      <Box key={variable.name} sx={{ display: 'flex', gap: 0.5 }}>
                        <Tooltip title={`${variable.description} - Click to copy`}>
                          <Chip
                            label={varString}
                            size="small"
                            onClick={() => handleCopyVariable(varString)}
                            icon={<ContentCopy />}
                            sx={{ cursor: 'pointer' }}
                          />
                        </Tooltip>
                        <Tooltip title={`Insert ${variable.description.toLowerCase()} at cursor`}>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleInsertVariable(varString)}
                            sx={{
                              minWidth: 'auto',
                              px: 1,
                              fontSize: '0.7rem',
                              borderColor: '#FFA500',
                              color: '#FFA500',
                              '&:hover': {
                                backgroundColor: 'rgba(255, 165, 0, 0.1)',
                                borderColor: '#FF8C00',
                              }
                            }}
                          >
                            Insert
                          </Button>
                        </Tooltip>
                      </Box>
                    );
                  })}
                </Box>
              </Paper>
            </Grid>
          )}

          {/* Additional Options */}
          <Grid item xs={12}>
            <Accordion
              expanded={advancedExpanded}
              onChange={(e, isExpanded) => setAdvancedExpanded(isExpanded)}
            >
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="subtitle1" fontWeight={600}>
                  Additional Options
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={2}>
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
