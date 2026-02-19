import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
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
  Alert,
  CircularProgress,
  Divider,
  Breadcrumbs,
  Link,
} from '@mui/material';
import { Save, Cancel, ArrowBack, Business } from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { Company } from '../types';
import ApiService from '../services/api';

interface CompanyFormData {
  name: string;
  legal_entity_name: string;
  tax_id: string;
  branch: string;
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
  is_active: boolean;
  seasonal_emails_enabled: boolean;
  soundtrack_account_id: string;
}

// Common industries for BMAsia's target market
const INDUSTRIES = [
  'Hospitality & Tourism',
  'Retail',
  'Restaurant & Food Service',
  'Healthcare',
  'Fitness & Wellness',
  'Corporate Offices',
  'Education',
  'Real Estate',
  'Entertainment',
  'Transportation',
  'Manufacturing',
  'Technology',
  'Financial Services',
  'Government',
  'Non-profit',
  'Other',
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

const CompanyEdit: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [company, setCompany] = useState<Company | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [formData, setFormData] = useState<CompanyFormData>({
    name: '',
    legal_entity_name: '',
    tax_id: '',
    branch: '',
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
    is_active: true,
    seasonal_emails_enabled: true,
    soundtrack_account_id: '',
  });

  useEffect(() => {
    if (id) {
      loadCompany();
    }
  }, [id]);

  const loadCompany = async () => {
    if (!id) return;

    try {
      setLoading(true);
      const companyData = await ApiService.getCompany(id);
      setCompany(companyData);

      setFormData({
        name: companyData.name || '',
        legal_entity_name: companyData.legal_entity_name || '',
        tax_id: companyData.tax_id || '',
        branch: companyData.branch || '',
        industry: companyData.industry || '',
        country: companyData.country || '',
        billing_entity: companyData.billing_entity || 'BMAsia Limited',
        city: companyData.city || '',
        website: companyData.website || '',
        phone: companyData.phone || '',
        email: companyData.email || '',
        address_line1: companyData.address_line1 || '',
        address_line2: companyData.address_line2 || '',
        state: companyData.state || '',
        postal_code: companyData.postal_code || '',
        notes: companyData.notes || '',
        is_active: companyData.is_active !== undefined ? companyData.is_active : true,
        seasonal_emails_enabled: companyData.seasonal_emails_enabled !== undefined ? companyData.seasonal_emails_enabled : true,
        soundtrack_account_id: companyData.soundtrack_account_id || '',
      });
    } catch (err: any) {
      console.error('Company load error:', err);
      setError('Failed to load company details');
    } finally {
      setLoading(false);
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
    if (!validateForm() || !id) return;

    setSaving(true);
    setError('');

    try {
      const submitData = {
        ...formData,
        billing_entity: formData.billing_entity,
        legal_entity_name: formData.legal_entity_name || undefined,
        tax_id: formData.tax_id || undefined,
        branch: formData.branch || undefined,
        website: formData.website || undefined,
        phone: formData.phone || undefined,
        email: formData.email || undefined,
        address_line2: formData.address_line2 || undefined,
        state: formData.state || undefined,
        postal_code: formData.postal_code || undefined,
        notes: formData.notes || undefined,
        soundtrack_account_id: formData.soundtrack_account_id || undefined,
      };

      await ApiService.updateCompany(id, submitData);
      navigate(`/companies/${id}`);
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
          setError(err.response.data.message || 'Failed to update company');
        }
      } else {
        setError('Failed to update company. Please try again.');
      }
    } finally {
      setSaving(false);
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

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  if (error && !company) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button variant="contained" onClick={() => navigate('/companies')}>
          Back to Companies
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Breadcrumbs aria-label="breadcrumb" sx={{ mb: 2 }}>
          <Link
            underline="hover"
            color="inherit"
            onClick={() => navigate('/companies')}
            sx={{ cursor: 'pointer' }}
          >
            Companies
          </Link>
          <Link
            underline="hover"
            color="inherit"
            onClick={() => navigate(`/companies/${id}`)}
            sx={{ cursor: 'pointer' }}
          >
            {company?.name || 'Company'}
          </Link>
          <Typography color="text.primary">Edit</Typography>
        </Breadcrumbs>

        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Button
            startIcon={<ArrowBack />}
            onClick={() => navigate(`/companies/${id}`)}
            sx={{ mr: 2 }}
          >
            Back to Details
          </Button>
          <Box>
            <Typography variant="h4" component="h1" sx={{ display: 'flex', alignItems: 'center' }}>
              <Business sx={{ mr: 1 }} />
              Edit {company?.name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Update company information and settings
            </Typography>
          </Box>
        </Box>
      </Box>

      <Paper sx={{ p: 3 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* Basic Information */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
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
              name="legal_entity_name"
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
                  <MenuItem key={industry} value={industry}>
                    {industry}
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
              label="Tax ID"
              value={formData.tax_id || ''}
              onChange={(e) => handleFieldChange('tax_id', e.target.value)}
              helperText="Tax Identification Number (required for Thai tax invoices)"
              size="medium"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Branch"
              value={formData.branch || ''}
              onChange={(e) => handleFieldChange('branch', e.target.value)}
              helperText="e.g., Head Office, Branch 00001"
              placeholder="e.g., Branch 00001"
              size="medium"
            />
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
              size="medium"
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Contact Information */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
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
              size="medium"
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
              size="medium"
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Address Information */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
              Address Information
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Address Line 1"
              value={formData.address_line1}
              onChange={(e) => handleFieldChange('address_line1', e.target.value)}
              placeholder="Street address, building number"
              size="medium"
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Address Line 2"
              value={formData.address_line2}
              onChange={(e) => handleFieldChange('address_line2', e.target.value)}
              placeholder="Apartment, suite, unit, building, floor"
              size="medium"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="City"
              value={formData.city}
              onChange={(e) => handleFieldChange('city', e.target.value)}
              error={!!errors.city}
              helperText={errors.city}
              placeholder="e.g., Bangkok, Singapore"
              size="medium"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="State/Province"
              value={formData.state}
              onChange={(e) => handleFieldChange('state', e.target.value)}
              placeholder="e.g., Bangkok, Selangor"
              size="medium"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Postal Code"
              value={formData.postal_code}
              onChange={(e) => handleFieldChange('postal_code', e.target.value)}
              placeholder="e.g., 10110, 50450"
              size="medium"
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Integration & Settings */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
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
              size="medium"
            />
          </Grid>

          <Grid item xs={12} sm={4}>
            <Box sx={{ pt: 2 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.is_active}
                    onChange={(e) => handleFieldChange('is_active', e.target.checked)}
                    size="medium"
                  />
                }
                label="Active Company"
              />
            </Box>
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Communication Preferences */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
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

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Additional Notes */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
              Additional Notes
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
              placeholder="Additional notes about this company..."
              size="medium"
            />
          </Grid>
        </Grid>

        {/* Action Buttons */}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mt: 4, pt: 3, borderTop: '1px solid', borderColor: 'divider' }}>
          <Button
            variant="outlined"
            startIcon={<Cancel />}
            onClick={() => navigate(`/companies/${id}`)}
            disabled={saving}
            size="large"
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            startIcon={saving ? <CircularProgress size={20} /> : <Save />}
            onClick={handleSubmit}
            disabled={saving}
            size="large"
          >
            {saving ? 'Updating...' : 'Update Company'}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
};

export default CompanyEdit;