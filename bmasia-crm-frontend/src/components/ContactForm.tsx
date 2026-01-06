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
  Autocomplete,
  Typography,
  Alert,
  CircularProgress,
  Divider,
} from '@mui/material';
import { Save, Cancel } from '@mui/icons-material';
import { Contact, Company } from '../types';
import ApiService from '../services/api';

interface ContactFormProps {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  contact: Contact | null;
  companies: Company[];
}

interface ContactFormData {
  first_name: string;
  last_name: string;
  title: string;
  company: string;
  email: string;
  phone: string;
  mobile: string;
  department: string;
  status: 'Active' | 'Inactive';
  is_decision_maker: boolean;
  linkedin_url: string;
  notes: string;
  preferred_contact_method: 'Email' | 'Phone' | 'Mobile' | 'LinkedIn' | '';
  // Granular email preferences
  receives_renewal_emails: boolean;
  receives_seasonal_emails: boolean;
  receives_payment_emails: boolean;
  receives_quarterly_emails: boolean;
  receives_soundtrack_alerts: boolean;
}

const ContactForm: React.FC<ContactFormProps> = ({
  open,
  onClose,
  onSave,
  contact,
  companies,
}) => {
  const [formData, setFormData] = useState<ContactFormData>({
    first_name: '',
    last_name: '',
    title: '',
    company: '',
    email: '',
    phone: '',
    mobile: '',
    department: '',
    status: 'Active',
    is_decision_maker: false,
    linkedin_url: '',
    notes: '',
    preferred_contact_method: '',
    // Email preferences default to true
    receives_renewal_emails: true,
    receives_seasonal_emails: true,
    receives_payment_emails: true,
    receives_quarterly_emails: true,
    receives_soundtrack_alerts: false,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (contact) {
      // Split name into first and last for editing
      const nameParts = contact.name ? contact.name.split(' ') : ['', ''];
      const firstName = nameParts[0] || '';
      const lastName = nameParts.slice(1).join(' ') || '';

      setFormData({
        first_name: firstName,
        last_name: lastName,
        title: contact.title || '',
        company: contact.company || '',
        email: contact.email || '',
        phone: contact.phone || '',
        mobile: '', // Mobile field not in backend yet
        department: contact.department || '',
        status: contact.is_active ? 'Active' : 'Inactive',
        is_decision_maker: contact.contact_type === 'Decision Maker',
        linkedin_url: contact.linkedin_url || '',
        notes: contact.notes || '',
        preferred_contact_method: '', // Not in backend yet
        // Email preferences (default to true if undefined)
        receives_renewal_emails: contact.receives_renewal_emails ?? true,
        receives_seasonal_emails: contact.receives_seasonal_emails ?? true,
        receives_payment_emails: contact.receives_payment_emails ?? true,
        receives_quarterly_emails: contact.receives_quarterly_emails ?? true,
        receives_soundtrack_alerts: contact.receives_soundtrack_alerts ?? false,
      });
    } else {
      // Reset form for new contact
      setFormData({
        first_name: '',
        last_name: '',
        title: '',
        company: '',
        email: '',
        phone: '',
        mobile: '',
        department: '',
        status: 'Active',
        is_decision_maker: false,
        linkedin_url: '',
        notes: '',
        preferred_contact_method: '',
        // Email preferences default to true for new contacts
        receives_renewal_emails: true,
        receives_seasonal_emails: true,
        receives_payment_emails: true,
        receives_quarterly_emails: true,
        receives_soundtrack_alerts: false,
      });
    }
    setError('');
    setErrors({});
  }, [contact, open]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.first_name.trim()) {
      newErrors.first_name = 'First name is required';
    }

    if (!formData.last_name.trim()) {
      newErrors.last_name = 'Last name is required';
    }

    if (!formData.company) {
      newErrors.company = 'Company is required';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(formData.email)) {
        newErrors.email = 'Please enter a valid email address';
      }
    }

    if (formData.phone && formData.phone.trim()) {
      const phoneRegex = /^[+]?[0-9\s-()]+$/;
      if (!phoneRegex.test(formData.phone)) {
        newErrors.phone = 'Please enter a valid phone number';
      }
    }

    if (formData.mobile && formData.mobile.trim()) {
      const phoneRegex = /^[+]?[0-9\s-()]+$/;
      if (!phoneRegex.test(formData.mobile)) {
        newErrors.mobile = 'Please enter a valid mobile number';
      }
    }

    if (formData.linkedin_url && formData.linkedin_url.trim()) {
      const linkedinRegex = /^https?:\/\/(www\.)?linkedin\.com\/in\/[a-zA-Z0-9-]+\/?$/;
      if (!linkedinRegex.test(formData.linkedin_url)) {
        newErrors.linkedin_url = 'Please enter a valid LinkedIn profile URL';
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
      // Map frontend form data to backend API format
      // Note: mobile and preferred_contact_method are not in the Django model yet
      const contactType: 'Primary' | 'Technical' | 'Billing' | 'Decision Maker' | 'Other' =
        formData.is_decision_maker ? 'Decision Maker' : 'Other';

      const submitData: Partial<Contact> = {
        name: `${formData.first_name} ${formData.last_name}`.trim(),
        email: formData.email,
        phone: formData.phone || '',
        title: formData.title || '',
        department: formData.department || '',
        company: formData.company,
        contact_type: contactType,
        is_primary: false, // Default to non-primary
        is_active: formData.status === 'Active',
        linkedin_url: formData.linkedin_url || '',
        notes: formData.notes || '',
        // Granular email preferences
        receives_renewal_emails: formData.receives_renewal_emails,
        receives_seasonal_emails: formData.receives_seasonal_emails,
        receives_payment_emails: formData.receives_payment_emails,
        receives_quarterly_emails: formData.receives_quarterly_emails,
        receives_soundtrack_alerts: formData.receives_soundtrack_alerts,
      };

      console.log('=== Contact Form Submit ===');
      console.log('Form Data:', JSON.stringify(formData, null, 2));
      console.log('Submit Data (mapped for API):', JSON.stringify(submitData, null, 2));
      console.log('Contact ID:', contact?.id || 'NEW');

      if (contact) {
        await ApiService.updateContact(contact.id, submitData);
      } else {
        await ApiService.createContact(submitData);
      }

      console.log('Contact save successful!');
      onSave();
    } catch (err: any) {
      console.error('=== Contact Save ERROR ===');
      console.error('Full error object:', err);
      console.error('Error message:', err.message);
      console.error('Error response:', err.response);

      if (err.response) {
        console.error('Response status:', err.response.status);
        console.error('Response data:', JSON.stringify(err.response.data, null, 2));
        console.error('Response headers:', err.response.headers);
      }

      if (err.response?.data) {
        if (typeof err.response.data === 'object') {
          const fieldErrors: Record<string, string> = {};
          Object.keys(err.response.data).forEach(field => {
            if (Array.isArray(err.response.data[field])) {
              fieldErrors[field] = err.response.data[field][0];
            } else {
              fieldErrors[field] = err.response.data[field];
            }
          });
          console.error('Parsed field errors:', fieldErrors);
          setErrors(fieldErrors);
          setError(`Validation error: ${JSON.stringify(fieldErrors)}`);
        } else {
          const errorMsg = err.response.data.message || err.response.data || 'Failed to save contact';
          setError(errorMsg);
        }
      } else {
        setError('Failed to save contact. Please check the console for details.');
      }
      console.error('============================');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  const handleFieldChange = (field: keyof ContactFormData, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));

    // Clear field error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: '',
      }));
    }
  };

  const selectedCompany = companies.find(c => c.id === formData.company);

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { minHeight: '80vh' }
      }}
    >
      <DialogTitle>
        <Typography variant="h6">
          {contact ? 'Edit Contact' : 'New Contact'}
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

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="First Name"
              value={formData.first_name}
              onChange={(e) => handleFieldChange('first_name', e.target.value)}
              error={!!errors.first_name}
              helperText={errors.first_name}
              required
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Last Name"
              value={formData.last_name}
              onChange={(e) => handleFieldChange('last_name', e.target.value)}
              error={!!errors.last_name}
              helperText={errors.last_name}
              required
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Title/Position"
              value={formData.title}
              onChange={(e) => handleFieldChange('title', e.target.value)}
              placeholder="e.g., Marketing Manager"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Department"
              value={formData.department}
              onChange={(e) => handleFieldChange('department', e.target.value)}
              placeholder="e.g., Marketing, IT, Operations"
            />
          </Grid>

          <Grid item xs={12}>
            <Autocomplete
              options={companies}
              getOptionLabel={(option) => option.name}
              value={selectedCompany || null}
              onChange={(_, newValue) => handleFieldChange('company', newValue?.id || '')}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Company"
                  required
                  error={!!errors.company}
                  helperText={errors.company}
                />
              )}
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Contact Information */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Contact Information
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={formData.email}
              onChange={(e) => handleFieldChange('email', e.target.value)}
              error={!!errors.email}
              helperText={errors.email}
              required
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Preferred Contact Method</InputLabel>
              <Select
                value={formData.preferred_contact_method}
                onChange={(e) => handleFieldChange('preferred_contact_method', e.target.value)}
                label="Preferred Contact Method"
              >
                <MenuItem value="">Not specified</MenuItem>
                <MenuItem value="Email">Email</MenuItem>
                <MenuItem value="Phone">Phone</MenuItem>
                <MenuItem value="Mobile">Mobile</MenuItem>
                <MenuItem value="LinkedIn">LinkedIn</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Phone"
              value={formData.phone}
              onChange={(e) => handleFieldChange('phone', e.target.value)}
              error={!!errors.phone}
              helperText={errors.phone}
              placeholder="+1 (555) 123-4567"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Mobile Phone"
              value={formData.mobile}
              onChange={(e) => handleFieldChange('mobile', e.target.value)}
              error={!!errors.mobile}
              helperText={errors.mobile}
              placeholder="+1 (555) 987-6543"
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="LinkedIn URL"
              value={formData.linkedin_url}
              onChange={(e) => handleFieldChange('linkedin_url', e.target.value)}
              error={!!errors.linkedin_url}
              helperText={errors.linkedin_url}
              placeholder="https://linkedin.com/in/username"
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Settings */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Settings
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={formData.status}
                onChange={(e) => handleFieldChange('status', e.target.value)}
                label="Status"
              >
                <MenuItem value="Active">Active</MenuItem>
                <MenuItem value="Inactive">Inactive</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6}>
            <Box sx={{ pt: 2 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.is_decision_maker}
                    onChange={(e) => handleFieldChange('is_decision_maker', e.target.checked)}
                  />
                }
                label="Decision Maker"
              />
            </Box>
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Email Preferences */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Email Preferences
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Control which automated emails this contact receives
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.receives_renewal_emails}
                  onChange={(e) => handleFieldChange('receives_renewal_emails', e.target.checked)}
                />
              }
              label="Contract Renewal Reminders"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.receives_payment_emails}
                  onChange={(e) => handleFieldChange('receives_payment_emails', e.target.checked)}
                />
              }
              label="Payment Reminders"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.receives_quarterly_emails}
                  onChange={(e) => handleFieldChange('receives_quarterly_emails', e.target.checked)}
                />
              }
              label="Quarterly Check-ins"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.receives_seasonal_emails}
                  onChange={(e) => handleFieldChange('receives_seasonal_emails', e.target.checked)}
                />
              }
              label="Seasonal Campaigns"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.receives_soundtrack_alerts}
                  onChange={(e) => handleFieldChange('receives_soundtrack_alerts', e.target.checked)}
                />
              }
              label="Soundtrack Offline Alerts"
            />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: -0.5 }}>
              Receive alerts when music zones go offline (for IT/Technical contacts)
            </Typography>
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Notes */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Notes
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Notes"
              multiline
              rows={4}
              value={formData.notes}
              onChange={(e) => handleFieldChange('notes', e.target.value)}
              placeholder="Additional notes about this contact..."
            />
          </Grid>
        </Grid>
      </DialogContent>

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button
          onClick={handleClose}
          disabled={loading}
          startIcon={<Cancel />}
        >
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={20} /> : <Save />}
        >
          {loading ? 'Saving...' : (contact ? 'Update Contact' : 'Create Contact')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ContactForm;