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
  Divider,
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
  industry: string;
  country: string;
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
  soundtrack_account_id: string;
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

const CompanyForm: React.FC<CompanyFormProps> = ({
  open,
  onClose,
  onSave,
  company,
}) => {
  const [formData, setFormData] = useState<CompanyFormData>({
    name: '',
    industry: '',
    country: '',
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
    soundtrack_account_id: '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (company) {
      setFormData({
        name: company.name || '',
        industry: company.industry || '',
        country: company.country || '',
        city: company.city || '',
        website: company.website || '',
        phone: '', // Phone not in Company type, will need to be added
        email: '', // Email not in Company type, will need to be added
        address_line1: company.address_line1 || '',
        address_line2: company.address_line2 || '',
        state: company.state || '',
        postal_code: company.postal_code || '',
        notes: company.notes || '',
        is_active: company.is_active !== undefined ? company.is_active : true,
        soundtrack_account_id: '', // Will need to be added to Company type
      });
    } else {
      // Reset form for new company
      setFormData({
        name: '',
        industry: '',
        country: '',
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
        soundtrack_account_id: '',
      });
    }
    setError('');
    setErrors({});
  }, [company, open]);

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
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth error={!!errors.industry}>
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
            <FormControl fullWidth error={!!errors.country}>
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
            <TextField
              fullWidth
              label="City"
              value={formData.city}
              onChange={(e) => handleFieldChange('city', e.target.value)}
              error={!!errors.city}
              helperText={errors.city}
              placeholder="e.g., Bangkok, Singapore"
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

          {/* Address Information */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
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
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Address Line 2"
              value={formData.address_line2}
              onChange={(e) => handleFieldChange('address_line2', e.target.value)}
              placeholder="Apartment, suite, unit, building, floor"
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