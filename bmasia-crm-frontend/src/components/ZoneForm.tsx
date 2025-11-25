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
  Alert,
  CircularProgress,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
} from '@mui/material';
import { Save, Cancel, ArrowBack, Add } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { Zone, Company, Device, DEVICE_TYPE_LABELS } from '../types';
import ApiService from '../services/api';

interface ZoneFormProps {
  zone?: Zone | null;
  mode: 'create' | 'edit';
}

interface FormData {
  company: string;
  name: string;
  platform: 'soundtrack' | 'beatbreeze';
  status: 'online' | 'offline' | 'no_device' | 'expired' | 'pending';
  soundtrack_zone_id: string;
  device?: string;
  device_name: string;
  notes: string;
}

const ZoneForm: React.FC<ZoneFormProps> = ({ zone, mode }) => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({
    company: '',
    name: '',
    platform: 'soundtrack',
    status: 'pending',
    soundtrack_zone_id: '',
    device: undefined,
    device_name: '',
    notes: '',
  });

  const [companies, setCompanies] = useState<Company[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showNewDeviceDialog, setShowNewDeviceDialog] = useState(false);
  const [newDevice, setNewDevice] = useState({ name: '', device_type: 'pc' as const, model_info: '', notes: '' });

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (zone && mode === 'edit') {
      setFormData({
        company: zone.company || '',
        name: zone.name || '',
        platform: zone.platform || 'soundtrack',
        status: zone.status || 'pending',
        soundtrack_zone_id: zone.soundtrack_zone_id || '',
        device: zone.device || undefined,
        device_name: zone.device_name || '',
        notes: zone.notes || '',
      });
    }
  }, [zone, mode]);

  useEffect(() => {
    if (formData.company) {
      loadDevicesForCompany(formData.company);
    } else {
      setDevices([]);
    }
  }, [formData.company]);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const companiesResponse = await ApiService.getCompanies({ is_active: true });
      setCompanies(companiesResponse.results || companiesResponse);
    } catch (err: any) {
      console.error('Load data error:', err);
      setError('Failed to load form data');
    } finally {
      setLoading(false);
    }
  };

  const loadDevicesForCompany = async (companyId: string) => {
    setLoadingDevices(true);
    try {
      const data = await ApiService.getDevicesByCompany(companyId);
      setDevices(data);
    } catch (error) {
      console.error('Failed to load devices:', error);
    } finally {
      setLoadingDevices(false);
    }
  };

  const handleCreateDevice = async () => {
    if (!formData.company || !newDevice.name) return;

    try {
      const created = await ApiService.createDevice({
        company: formData.company,
        ...newDevice
      });
      setDevices([...devices, created]);
      setFormData({ ...formData, device: created.id });
      setShowNewDeviceDialog(false);
      setNewDevice({ name: '', device_type: 'pc', model_info: '', notes: '' });
    } catch (error) {
      console.error('Failed to create device:', error);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.company) {
      newErrors.company = 'Company is required';
    }
    if (!formData.name?.trim()) {
      newErrors.name = 'Zone name is required';
    }
    if (formData.name && formData.name.length > 100) {
      newErrors.name = 'Zone name must be 100 characters or less';
    }
    if (!formData.platform) {
      newErrors.platform = 'Platform is required';
    }
    if (!formData.status) {
      newErrors.status = 'Status is required';
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
        company: formData.company,
        name: formData.name,
        platform: formData.platform,
        status: formData.status,
        soundtrack_zone_id: formData.soundtrack_zone_id || '',
        device: formData.device || undefined,
        device_name: formData.device_name || '',
        notes: formData.notes || '',
      };

      if (mode === 'edit' && zone?.id) {
        await ApiService.updateZone(zone.id, submitData);
      } else {
        await ApiService.createZone(submitData);
      }

      navigate('/zones');
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
          setError(err.response.data.message || 'Failed to save zone');
        }
      } else {
        setError('Failed to save zone. Please try again.');
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
    <Box>
      <Button startIcon={<ArrowBack />} onClick={() => navigate('/zones')} sx={{ mb: 2 }}>
        Back to Zones
      </Button>

      <Typography variant="h4" component="h1" gutterBottom>
        {mode === 'edit' ? 'Edit Zone' : 'New Zone'}
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

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Zone Name"
              value={formData.name}
              onChange={(e) => handleFieldChange('name', e.target.value)}
              error={!!errors.name}
              helperText={errors.name || 'e.g., Pool Bar, Main Restaurant, Lobby'}
              required
              inputProps={{ maxLength: 100 }}
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth error={!!errors.platform} required>
              <InputLabel>Platform</InputLabel>
              <Select
                value={formData.platform}
                onChange={(e) => handleFieldChange('platform', e.target.value)}
                label="Platform *"
              >
                <MenuItem value="soundtrack">Soundtrack</MenuItem>
                <MenuItem value="beatbreeze">Beat Breeze</MenuItem>
              </Select>
            </FormControl>
            {errors.platform && (
              <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                {errors.platform}
              </Typography>
            )}
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth error={!!errors.status} required>
              <InputLabel>Status</InputLabel>
              <Select
                value={formData.status}
                onChange={(e) => handleFieldChange('status', e.target.value)}
                label="Status *"
              >
                <MenuItem value="online">Online</MenuItem>
                <MenuItem value="offline">Offline</MenuItem>
                <MenuItem value="no_device">No Device</MenuItem>
                <MenuItem value="expired">Expired</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
              </Select>
            </FormControl>
            {errors.status && (
              <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                {errors.status}
              </Typography>
            )}
          </Grid>

          <Grid item xs={12}>
            <Divider />
          </Grid>

          {/* Platform-Specific Information */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
              Platform Details
            </Typography>
          </Grid>

          {formData.platform === 'soundtrack' && (
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Soundtrack Zone ID"
                value={formData.soundtrack_zone_id}
                onChange={(e) => handleFieldChange('soundtrack_zone_id', e.target.value)}
                error={!!errors.soundtrack_zone_id}
                helperText={errors.soundtrack_zone_id || 'Optional: ID from Soundtrack Your Brand platform'}
                placeholder="e.g., 12345"
              />
            </Grid>
          )}

          <Grid item xs={12} sm={6}>
            <TextField
              select
              fullWidth
              label="Device (Optional)"
              value={formData.device || ''}
              onChange={(e) => handleFieldChange('device', e.target.value || undefined)}
              disabled={!formData.company || loadingDevices}
              helperText="Physical device running this zone"
            >
              <MenuItem value="">
                <em>No device assigned</em>
              </MenuItem>
              {devices.map((device) => (
                <MenuItem key={device.id} value={device.id}>
                  {device.name} ({DEVICE_TYPE_LABELS[device.device_type]})
                  {device.zone_count ? ` - ${device.zone_count} zone(s)` : ''}
                </MenuItem>
              ))}
              <Divider />
              <MenuItem
                onClick={(e) => {
                  e.preventDefault();
                  setShowNewDeviceDialog(true);
                }}
                sx={{ color: 'primary.main' }}
              >
                <Add sx={{ mr: 1 }} /> Create New Device
              </MenuItem>
            </TextField>
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Device Name (Legacy)"
              value={formData.device_name}
              onChange={(e) => handleFieldChange('device_name', e.target.value)}
              error={!!errors.device_name}
              helperText={errors.device_name || 'Optional: Free-form device identifier (legacy field)'}
              placeholder="e.g., iPad 1, Music Player A"
            />
          </Grid>

          <Grid item xs={12}>
            <Divider />
          </Grid>

          {/* Additional Information */}
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
              label="Notes"
              value={formData.notes}
              onChange={(e) => handleFieldChange('notes', e.target.value)}
              placeholder="Additional notes about this zone..."
              helperText="Optional: Configuration details, special requirements, etc."
            />
          </Grid>
        </Grid>

        {/* Actions */}
        <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 4 }}>
          <Button
            variant="outlined"
            startIcon={<Cancel />}
            onClick={() => navigate('/zones')}
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
            {submitting ? 'Saving...' : mode === 'edit' ? 'Update Zone' : 'Create Zone'}
          </Button>
        </Box>
      </Paper>

      {/* New Device Dialog */}
      <Dialog open={showNewDeviceDialog} onClose={() => setShowNewDeviceDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Device</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              fullWidth
              required
              label="Device Name"
              value={newDevice.name}
              onChange={(e) => setNewDevice({ ...newDevice, name: e.target.value })}
              placeholder="e.g., Lobby PC, Restaurant Tablet"
            />
            <TextField
              select
              fullWidth
              label="Device Type"
              value={newDevice.device_type}
              onChange={(e) => setNewDevice({ ...newDevice, device_type: e.target.value as any })}
            >
              <MenuItem value="pc">PC / Computer</MenuItem>
              <MenuItem value="tablet">Tablet</MenuItem>
              <MenuItem value="music_player">Music Player Box</MenuItem>
              <MenuItem value="other">Other</MenuItem>
            </TextField>
            <TextField
              fullWidth
              label="Model Info (Optional)"
              value={newDevice.model_info}
              onChange={(e) => setNewDevice({ ...newDevice, model_info: e.target.value })}
              placeholder="Model name, serial number, etc."
            />
            <TextField
              fullWidth
              multiline
              rows={2}
              label="Notes (Optional)"
              value={newDevice.notes}
              onChange={(e) => setNewDevice({ ...newDevice, notes: e.target.value })}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowNewDeviceDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateDevice}
            disabled={!newDevice.name}
            sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
          >
            Create Device
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ZoneForm;
