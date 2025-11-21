import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  GridLegacy as Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Autocomplete,
  IconButton,
  InputAdornment,
  Alert,
  CircularProgress,
  Divider,
} from '@mui/material';
import { Save, Cancel, Visibility, VisibilityOff, ArrowBack } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { Equipment, EquipmentType, Company } from '../types';
import ApiService from '../services/api';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV3';

interface EquipmentFormProps {
  equipment?: Equipment | null;
  mode: 'create' | 'edit';
}

interface FormData {
  equipment_type: string;
  company: string;
  serial_number: string;
  model_name: string;
  manufacturer: string;
  status: 'active' | 'inactive' | 'maintenance' | 'retired';
  remote_username: string;
  remote_password: string;
  ip_address: string;
  mac_address: string;
  setup_details: string;
  notes: string;
  installed_date: Date | null;
  warranty_expiry: Date | null;
}

const EquipmentForm: React.FC<EquipmentFormProps> = ({ equipment, mode }) => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({
    equipment_type: '',
    company: '',
    serial_number: '',
    model_name: '',
    manufacturer: '',
    status: 'active',
    remote_username: '',
    remote_password: '',
    ip_address: '',
    mac_address: '',
    setup_details: '',
    notes: '',
    installed_date: null,
    warranty_expiry: null,
  });

  const [equipmentTypes, setEquipmentTypes] = useState<EquipmentType[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (equipment && mode === 'edit') {
      setFormData({
        equipment_type: equipment.equipment_type || '',
        company: equipment.company || '',
        serial_number: equipment.serial_number || '',
        model_name: equipment.model_name || '',
        manufacturer: equipment.manufacturer || '',
        status: equipment.status || 'active',
        remote_username: equipment.remote_username || '',
        remote_password: equipment.remote_password || '',
        ip_address: equipment.ip_address || '',
        mac_address: equipment.mac_address || '',
        setup_details: equipment.setup_details || '',
        notes: equipment.notes || '',
        installed_date: equipment.installed_date ? new Date(equipment.installed_date) : null,
        warranty_expiry: equipment.warranty_expiry ? new Date(equipment.warranty_expiry) : null,
      });
    }
  }, [equipment, mode]);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const [typesResponse, companiesResponse] = await Promise.all([
        ApiService.getEquipmentTypes(),
        ApiService.getCompanies({ is_active: true }),
      ]);
      setEquipmentTypes(typesResponse);
      setCompanies(companiesResponse.results || companiesResponse);
    } catch (err: any) {
      console.error('Load data error:', err);
      setError('Failed to load form data');
    } finally {
      setLoading(false);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.equipment_type) {
      newErrors.equipment_type = 'Equipment type is required';
    }
    if (!formData.company) {
      newErrors.company = 'Company is required';
    }
    if (!formData.serial_number?.trim()) {
      newErrors.serial_number = 'Serial number is required';
    }
    if (!formData.model_name?.trim()) {
      newErrors.model_name = 'Model name is required';
    }
    if (!formData.manufacturer?.trim()) {
      newErrors.manufacturer = 'Manufacturer is required';
    }

    // IP address validation (if provided)
    if (formData.ip_address && formData.ip_address.trim()) {
      const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
      if (!ipRegex.test(formData.ip_address)) {
        newErrors.ip_address = 'Invalid IP address format';
      }
    }

    // MAC address validation (if provided)
    if (formData.mac_address && formData.mac_address.trim()) {
      const macRegex = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/;
      if (!macRegex.test(formData.mac_address)) {
        newErrors.mac_address = 'Invalid MAC address format (e.g., 00:11:22:33:44:55)';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    setSubmitting(true);
    setError('');

    try {
      const submitData = {
        equipment_type: formData.equipment_type,
        company: formData.company,
        serial_number: formData.serial_number,
        model_name: formData.model_name,
        manufacturer: formData.manufacturer,
        status: formData.status,
        remote_username: formData.remote_username || '',
        remote_password: formData.remote_password || '',
        ip_address: formData.ip_address || '',
        mac_address: formData.mac_address || '',
        setup_details: formData.setup_details || '',
        notes: formData.notes || '',
        installed_date: formData.installed_date ? formData.installed_date.toISOString().split('T')[0] : null,
        warranty_expiry: formData.warranty_expiry ? formData.warranty_expiry.toISOString().split('T')[0] : null,
      };

      if (mode === 'edit' && equipment?.id) {
        await ApiService.updateEquipment(equipment.id, submitData);
      } else {
        await ApiService.createEquipment(submitData);
      }

      navigate('/equipment');
    } catch (err: any) {
      console.error('Submit error:', err);
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
          setError(err.response.data.message || 'Failed to save equipment');
        }
      } else {
        setError('Failed to save equipment. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleFieldChange = (field: keyof FormData, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: '' }));
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/equipment')} sx={{ mb: 2 }}>
          Back to Equipment
        </Button>

        <Typography variant="h4" component="h1" gutterBottom>
          {mode === 'edit' ? 'Edit Equipment' : 'New Equipment'}
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        <Paper sx={{ p: 3 }}>
          <Grid container spacing={3}>
            {/* Basic Information */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Basic Information
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth error={!!errors.equipment_type} required>
                <InputLabel>Equipment Type</InputLabel>
                <Select
                  value={formData.equipment_type}
                  onChange={(e) => handleFieldChange('equipment_type', e.target.value)}
                  label="Equipment Type *"
                >
                  {equipmentTypes.map((type) => (
                    <MenuItem key={type.id} value={type.id}>
                      {type.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              {errors.equipment_type && (
                <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                  {errors.equipment_type}
                </Typography>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              <Autocomplete
                options={companies}
                getOptionLabel={(option) => option.name}
                value={companies.find((c) => c.id === formData.company) || null}
                onChange={(e, newValue) => handleFieldChange('company', newValue?.id || '')}
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

            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select
                  value={formData.status}
                  onChange={(e) => handleFieldChange('status', e.target.value)}
                  label="Status"
                >
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="inactive">Inactive</MenuItem>
                  <MenuItem value="maintenance">Maintenance</MenuItem>
                  <MenuItem value="retired">Retired</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12}>
              <Divider />
            </Grid>

            {/* Hardware Details */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Hardware Details
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Serial Number"
                value={formData.serial_number}
                onChange={(e) => handleFieldChange('serial_number', e.target.value)}
                error={!!errors.serial_number}
                helperText={errors.serial_number}
                required
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Model Name"
                value={formData.model_name}
                onChange={(e) => handleFieldChange('model_name', e.target.value)}
                error={!!errors.model_name}
                helperText={errors.model_name}
                required
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Manufacturer"
                value={formData.manufacturer}
                onChange={(e) => handleFieldChange('manufacturer', e.target.value)}
                error={!!errors.manufacturer}
                helperText={errors.manufacturer}
                required
              />
            </Grid>

            <Grid item xs={12}>
              <Divider />
            </Grid>

            {/* Network Configuration */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Network Configuration
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="IP Address"
                value={formData.ip_address}
                onChange={(e) => handleFieldChange('ip_address', e.target.value)}
                error={!!errors.ip_address}
                helperText={errors.ip_address || 'e.g., 192.168.1.100'}
                placeholder="192.168.1.100"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="MAC Address"
                value={formData.mac_address}
                onChange={(e) => handleFieldChange('mac_address', e.target.value)}
                error={!!errors.mac_address}
                helperText={errors.mac_address || 'e.g., 00:11:22:33:44:55'}
                placeholder="00:11:22:33:44:55"
              />
            </Grid>

            <Grid item xs={12}>
              <Divider />
            </Grid>

            {/* Remote Access */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Remote Access Credentials
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Remote Username"
                value={formData.remote_username}
                onChange={(e) => handleFieldChange('remote_username', e.target.value)}
                placeholder="admin"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Remote Password"
                type={showPassword ? 'text' : 'password'}
                value={formData.remote_password}
                onChange={(e) => handleFieldChange('remote_password', e.target.value)}
                placeholder="Enter password"
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton onClick={() => setShowPassword(!showPassword)} edge="end" size="small">
                        {showPassword ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>

            <Grid item xs={12}>
              <Divider />
            </Grid>

            {/* Notes */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Additional Information
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={4}
                label="Setup Details"
                value={formData.setup_details}
                onChange={(e) => handleFieldChange('setup_details', e.target.value)}
                placeholder="Configuration details, installation notes, special settings..."
                helperText="Technical setup and configuration information"
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Notes"
                value={formData.notes}
                onChange={(e) => handleFieldChange('notes', e.target.value)}
                placeholder="General notes and comments..."
              />
            </Grid>

            <Grid item xs={12}>
              <Divider />
            </Grid>

            {/* Dates */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Important Dates
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <DatePicker
                label="Installed Date"
                value={formData.installed_date}
                onChange={(date) => handleFieldChange('installed_date', date)}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    helperText: 'When the equipment was installed',
                  },
                }}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <DatePicker
                label="Warranty Expiry"
                value={formData.warranty_expiry}
                onChange={(date) => handleFieldChange('warranty_expiry', date)}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    helperText: 'When the warranty expires',
                  },
                }}
              />
            </Grid>
          </Grid>

          {/* Actions */}
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 4 }}>
            <Button
              variant="outlined"
              startIcon={<Cancel />}
              onClick={() => navigate('/equipment')}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              startIcon={submitting ? <CircularProgress size={20} /> : <Save />}
              onClick={handleSubmit}
              disabled={submitting}
              sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
            >
              {submitting ? 'Saving...' : mode === 'edit' ? 'Update Equipment' : 'Create Equipment'}
            </Button>
          </Box>
        </Paper>
      </Box>
    </LocalizationProvider>
  );
};

export default EquipmentForm;
