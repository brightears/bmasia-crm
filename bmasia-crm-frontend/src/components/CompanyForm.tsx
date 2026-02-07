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
  Checkbox,
  Box,
  Typography,
  Alert,
  CircularProgress,
  Divider,
  Autocomplete,
} from '@mui/material';
import { Save, Cancel } from '@mui/icons-material';
import { Company } from '../types';
import ApiService from '../services/api';

interface CompanyFormProps {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  company: Company | null;
}

interface CompanyFormData {
  name: string;
  legal_entity_name: string;
  industry: string;
  country: string;
  billing_entity: string;
  city: string;
  website: string;
  phone: string;
  email: string;
  address_line1: string;
  address_line2: string;
  state: string;
  postal_code: string;
  notes: string;
  it_notes: string;
  is_active: boolean;
  seasonal_emails_enabled: boolean;
  soundtrack_offline_alerts_enabled: boolean;
  soundtrack_account_id: string;
  is_corporate_parent: boolean;
  parent_company: string;
}

// BMAsia's target industries - must match backend Company.INDUSTRY_CHOICES exactly
// Format: { value: database_value, label: display_name }
const INDUSTRIES = [
  { value: 'Hotels', label: 'Hotels & Resorts' },
  { value: 'Restaurants', label: 'Restaurants' },
  { value: 'Bars', label: 'Bars & Nightlife' },
  { value: 'Quick Service Restaurants', label: 'Quick Service Restaurants' },
  { value: 'Retail Fashion', label: 'Retail Fashion' },
  { value: 'Retail Food', label: 'Retail Food' },
  { value: 'Malls', label: 'Shopping Malls' },
  { value: 'Offices', label: 'Offices & Corporate' },
  { value: 'Hospitals', label: 'Hospitals & Medical' },
  { value: 'Spas', label: 'Spas & Wellness' },
  { value: 'Fun Parks', label: 'Fun Parks & Entertainment' },
  { value: 'Cafes', label: 'Cafes & Coffee Shops' },
  { value: 'Gyms', label: 'Gyms & Fitness Centers' },
  { value: 'Salons', label: 'Salons & Beauty' },
  { value: 'Banks', label: 'Banks & Financial' },
  { value: 'Other', label: 'Other' },
];

// Common countries for BMAsia's operations
const COUNTRIES = [
  'Thailand',
  'Singapore',
  'Malaysia',
  'Indonesia',
  'Philippines',
  'Vietnam',
  'Cambodia',
  'Laos',
  'Myanmar',
  'Brunei',
  'United States',
  'United Kingdom',
  'Australia',
  'New Zealand',
  'Japan',
  'South Korea',
  'China',
  'Hong Kong',
  'India',
  'Other',
];

// Billing entities for BMAsia
const BILLING_ENTITIES = [
  { value: 'BMAsia Limited', label: 'BMAsia Limited (Hong Kong)' },
  { value: 'BMAsia (Thailand) Co., Ltd.', label: 'BMAsia (Thailand) Co., Ltd.' },
];

const CompanyForm: React.FC<CompanyFormProps> = ({
  open,
  onClose,
  onSave,
  company,
}) => {
  const [formData, setFormData] = useState<CompanyFormData>({
    name: '',
    legal_entity_name: '',
    industry: '',
    country: '',
    billing_entity: 'BMAsia Limited',
    city: '',
    website: '',
    phone: '',
    email: '',
    address_line1: '',
    address_line2: '',
    state: '',
    postal_code: '',
    notes: '',
    it_notes: '',
    is_active: true,
    seasonal_emails_enabled: true,
    soundtrack_offline_alerts_enabled: true,
    soundtrack_account_id: '',
    is_corporate_parent: false,
    parent_company: '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [corporateParents, setCorporateParents] = useState<Company[]>([]);

  useEffect(() => {
    if (open) {
      loadCorporateParents();
    }
    if (company) {
      setFormData({
        name: company.name || '',
        legal_entity_name: company.legal_entity_name || '',
        industry: company.industry || '',
        country: company.country || '',
        billing_entity: company.billing_entity || 'BMAsia Limited',
        city: company.city || '',
        website: company.website || '',
        phone: company.phone || '',
        email: company.email || '',
        address_line1: company.address_line1 || '',
        address_line2: company.address_line2 || '',
        state: company.state || '',
        postal_code: company.postal_code || '',
        notes: company.notes || '',
        it_notes: company.it_notes || '',
        is_active: company.is_active !== undefined ? company.is_active : true,
        seasonal_emails_enabled: company.seasonal_emails_enabled !== undefined ? company.seasonal_emails_enabled : true,
        soundtrack_offline_alerts_enabled: company.soundtrack_offline_alerts_enabled !== undefined ? company.soundtrack_offline_alerts_enabled : true,
        soundtrack_account_id: company.soundtrack_account_id || '',
        is_corporate_parent: company.is_corporate_parent || false,
        parent_company: company.parent_company || '',
      });
    } else {
      // Reset form for new company
      setFormData({
        name: '',
        legal_entity_name: '',
        industry: '',
        country: '',
        billing_entity: 'BMAsia Limited',
        city: '',
        website: '',
        phone: '',
        email: '',
        address_line1: '',
        address_line2: '',
        state: '',
        postal_code: '',
        notes: '',
        it_notes: '',
        is_active: true,
        seasonal_emails_enabled: true,
        soundtrack_offline_alerts_enabled: true,
        soundtrack_account_id: '',
        is_corporate_parent: false,
        parent_company: '',
      });
    }
    setError('');
    setErrors({});
  }, [company, open]);

  const loadCorporateParents = async () => {
    try {
      const response = await ApiService.getCompanies({
        is_corporate_parent: true,
        page_size: 1000,
      });
      setCorporateParents(response.results);
    } catch (err) {
      console.error('Failed to load corporate parents:', err);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Company name is required';
    }

    if (!formData.industry) {
      newErrors.industry = 'Industry is required';
    }

    if (!formData.country) {
      newErrors.country = 'Country is required';
    }

    if (formData.website && formData.website.trim()) {
      const urlRegex = /^https?:\/\/.+/;
      if (!urlRegex.test(formData.website)) {
        newErrors.website = 'Please enter a valid website URL (including http:// or https://)';
      }
    }

    if (formData.email && formData.email.trim()) {
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
        billing_entity: formData.billing_entity,
        legal_entity_name: formData.legal_entity_name || undefined,
        website: formData.website || undefined,
        phone: formData.phone || undefined,
        email: formData.email || undefined,
        address_line2: formData.address_line2 || undefined,
        state: formData.state || undefined,
        postal_code: formData.postal_code || undefined,
        notes: formData.notes || undefined,
        soundtrack_account_id: formData.soundtrack_account_id || undefined,
      };

      if (company) {
        await ApiService.updateCompany(company.id, submitData);
      } else {
        await ApiService.createCompany(submitData);
      }

      // Call onSave callback after successful save (this will close the form and refresh the list)
      onSave();
    } catch (err: any) {
      console.error('Company save error:', err);
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
          setErrors(fieldErrors);
        } else {
          setError(err.response.data.message || 'Failed to save company');
        }
      } else {
        setError('Failed to save company. Please try again.');
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

  const handleFieldChange = (field: keyof CompanyFormData, value: any) => {
    // Single atomic state update with smart defaults
    setFormData(prev => {
      const updates: Partial<CompanyFormData> = { [field]: value };

      // Smart default: auto-select billing entity based on country
      if (field === 'country') {
        if (value === 'Thailand' || value === 'Hong Kong') {
          updates.billing_entity = 'BMAsia (Thailand) Co., Ltd.';
        } else if (value) {
          updates.billing_entity = 'BMAsia Limited';
        }
      }

      return { ...prev, ...updates };
    });

    // Clear field error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: '',
      }));
    }
  };

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
          {company ? 'Edit Company' : 'New Company'}
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
              label="Company Name"
              value={formData.name}
              onChange={(e) => handleFieldChange('name', e.target.value)}
              error={!!errors.name}
              helperText={errors.name}
              required
              size="medium"
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Legal Entity Name"
              value={formData.legal_entity_name}
              onChange={(e) => handleFieldChange('legal_entity_name', e.target.value)}
              helperText="Registered company name if different from display name (optional)"
              error={!!errors.legal_entity_name}
              size="medium"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth error={!!errors.industry} size="medium">
              <InputLabel>Industry *</InputLabel>
              <Select
                value={formData.industry}
                onChange={(e) => handleFieldChange('industry', e.target.value)}
                label="Industry *"
                required
              >
                {INDUSTRIES.map((industry) => (
                  <MenuItem key={industry.value} value={industry.value}>
                    {industry.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {errors.industry && (
              <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                {errors.industry}
              </Typography>
            )}
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth error={!!errors.country} size="medium">
              <InputLabel>Country *</InputLabel>
              <Select
                value={formData.country}
                onChange={(e) => handleFieldChange('country', e.target.value)}
                label="Country *"
                required
              >
                {COUNTRIES.map((country) => (
                  <MenuItem key={country} value={country}>
                    {country}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {errors.country && (
              <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                {errors.country}
              </Typography>
            )}
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth size="medium">
              <InputLabel>Billing Entity</InputLabel>
              <Select
                value={formData.billing_entity}
                onChange={(e) => handleFieldChange('billing_entity', e.target.value)}
                label="Billing Entity"
              >
                {BILLING_ENTITIES.map((entity) => (
                  <MenuItem key={entity.value} value={entity.value}>
                    {entity.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Legal entity for billing and invoicing
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Website"
              value={formData.website}
              onChange={(e) => handleFieldChange('website', e.target.value)}
              error={!!errors.website}
              helperText={errors.website}
              placeholder="https://www.company.com"
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Corporate Structure */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Corporate Structure
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.is_corporate_parent}
                  onChange={(e) => handleFieldChange('is_corporate_parent', e.target.checked)}
                />
              }
              label="This is a Corporate HQ"
            />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              Enable if this company is a corporate headquarters with subsidiary locations
            </Typography>
          </Grid>

          {!formData.is_corporate_parent && (
            <Grid item xs={12}>
              <Autocomplete
                fullWidth
                options={corporateParents}
                getOptionLabel={(option) => option.name}
                value={corporateParents.find(c => c.id === formData.parent_company) || null}
                onChange={(_, value) => handleFieldChange('parent_company', value?.id || '')}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Parent Company"
                    placeholder="Select parent company (optional)"
                    helperText="Link this subsidiary to its corporate headquarters"
                  />
                )}
              />
            </Grid>
          )}

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
              label="Phone Number"
              value={formData.phone}
              onChange={(e) => handleFieldChange('phone', e.target.value)}
              error={!!errors.phone}
              helperText={errors.phone}
              placeholder="+66 2 123 4567"
            />
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
              placeholder="info@company.com"
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Company Address */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Company Address
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Address Line 1"
              value={formData.address_line1}
              onChange={(e) => handleFieldChange('address_line1', e.target.value)}
              placeholder="Street address, building number"
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Address Line 2"
              value={formData.address_line2}
              onChange={(e) => handleFieldChange('address_line2', e.target.value)}
              placeholder="Apartment, suite, unit, floor"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="City"
              value={formData.city}
              onChange={(e) => handleFieldChange('city', e.target.value)}
              placeholder="e.g., Bangkok, Singapore"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="State/Province"
              value={formData.state}
              onChange={(e) => handleFieldChange('state', e.target.value)}
              placeholder="e.g., Bangkok, Selangor"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Postal Code"
              value={formData.postal_code}
              onChange={(e) => handleFieldChange('postal_code', e.target.value)}
              placeholder="e.g., 10110, 50450"
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Integration & Settings */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Integration & Settings
            </Typography>
          </Grid>

          <Grid item xs={12} sm={8}>
            <TextField
              fullWidth
              label="Soundtrack Account ID"
              value={formData.soundtrack_account_id}
              onChange={(e) => handleFieldChange('soundtrack_account_id', e.target.value)}
              placeholder="Soundtrack Your Brand account identifier"
              helperText="Used for integration with Soundtrack Your Brand API"
            />
          </Grid>

          <Grid item xs={12} sm={4}>
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

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Communication Preferences */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Communication Preferences
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={formData.seasonal_emails_enabled ?? true}
                  onChange={(e) => handleFieldChange('seasonal_emails_enabled', e.target.checked)}
                  color="primary"
                />
              }
              label="Receive seasonal email campaigns (Christmas, CNY, Songkran, etc.)"
            />
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={formData.soundtrack_offline_alerts_enabled ?? true}
                  onChange={(e) => handleFieldChange('soundtrack_offline_alerts_enabled', e.target.checked)}
                  color="primary"
                />
              }
              label="Soundtrack Offline Alerts"
            />
            <Typography variant="caption" color="text.secondary" sx={{ ml: 4, mb: 2, display: 'block' }}>
              Send email alerts to opted-in contacts when music zones go offline
            </Typography>
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Additional Notes */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Additional Notes
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="IT Notes"
              multiline
              rows={4}
              value={formData.it_notes}
              onChange={(e) => handleFieldChange('it_notes', e.target.value)}
              placeholder="IT-related notes: remote access details, contact preferences, configurations..."
              helperText="General IT notes for this company"
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Notes"
              multiline
              rows={4}
              value={formData.notes}
              onChange={(e) => handleFieldChange('notes', e.target.value)}
              placeholder="Additional notes about this company..."
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
          {loading ? 'Saving...' : (company ? 'Update Company' : 'Create Company')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CompanyForm;