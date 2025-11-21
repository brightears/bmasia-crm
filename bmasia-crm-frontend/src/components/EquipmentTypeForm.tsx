import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Autocomplete,
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material';
import { Save, Cancel } from '@mui/icons-material';
import * as Icons from '@mui/icons-material';
import { EquipmentType } from '../types';
import ApiService from '../services/api';

interface EquipmentTypeFormProps {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  equipmentType: EquipmentType | null;
}

interface EquipmentTypeFormData {
  name: string;
  description: string;
  icon: string;
}

// Predefined icon options with Material-UI icon names
const ICON_OPTIONS = [
  'computer',
  'laptop',
  'tablet',
  'phone_android',
  'speaker',
  'router',
  'print',
  'tv',
  'headphones',
  'camera',
  'watch',
  'keyboard',
  'mouse',
  'devices',
  'memory',
  'settings_input_component',
];

// Helper function to render Material-UI icon by name
const renderIcon = (iconName: string) => {
  // Convert icon name to PascalCase (e.g., 'phone_android' -> 'PhoneAndroid')
  const pascalCase = iconName
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join('');

  const IconComponent = (Icons as any)[pascalCase];
  return IconComponent ? <IconComponent /> : <Icons.DevicesOther />;
};

const EquipmentTypeForm: React.FC<EquipmentTypeFormProps> = ({
  open,
  onClose,
  onSave,
  equipmentType,
}) => {
  const [formData, setFormData] = useState<EquipmentTypeFormData>({
    name: '',
    description: '',
    icon: '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (equipmentType) {
      setFormData({
        name: equipmentType.name || '',
        description: equipmentType.description || '',
        icon: equipmentType.icon || '',
      });
    } else {
      // Reset form for new equipment type
      setFormData({
        name: '',
        description: '',
        icon: '',
      });
    }
    setError('');
    setErrors({});
  }, [equipmentType, open]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    } else if (formData.name.length > 100) {
      newErrors.name = 'Name must be 100 characters or less';
    }

    if (!formData.icon) {
      newErrors.icon = 'Icon is required';
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
        name: formData.name.trim(),
        description: formData.description.trim(),
        icon: formData.icon,
      };

      if (equipmentType) {
        await ApiService.updateEquipmentType(equipmentType.id, submitData);
      } else {
        await ApiService.createEquipmentType(submitData);
      }

      onSave();
    } catch (err: any) {
      console.error('Failed to save equipment type:', err);

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
          setError(
            `Validation error: ${Object.values(fieldErrors).join(', ')}`
          );
        } else {
          const errorMsg =
            err.response.data.message ||
            err.response.data ||
            'Failed to save equipment type';
          setError(errorMsg);
        }
      } else {
        setError('Failed to save equipment type. Please try again.');
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

  const handleFieldChange = (field: keyof EquipmentTypeFormData, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));

    // Clear field error when user starts typing
    if (errors[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: '',
      }));
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Typography variant="h6">
          {equipmentType ? 'Edit Equipment Type' : 'New Equipment Type'}
        </Typography>
      </DialogTitle>

      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Name */}
          <TextField
            fullWidth
            label="Name"
            value={formData.name}
            onChange={(e) => handleFieldChange('name', e.target.value)}
            error={!!errors.name}
            helperText={errors.name || 'Max 100 characters, must be unique'}
            required
            inputProps={{ maxLength: 100 }}
          />

          {/* Description */}
          <TextField
            fullWidth
            label="Description"
            value={formData.description}
            onChange={(e) => handleFieldChange('description', e.target.value)}
            multiline
            rows={4}
            placeholder="Optional description of this equipment type..."
          />

          {/* Icon */}
          <Box>
            <Autocomplete
              options={ICON_OPTIONS}
              value={formData.icon || null}
              onChange={(_, newValue) => handleFieldChange('icon', newValue || '')}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Icon"
                  required
                  error={!!errors.icon}
                  helperText={errors.icon || 'Select an icon to represent this equipment type'}
                />
              )}
              renderOption={(props, option) => (
                <li {...props}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {renderIcon(option)}
                    <Typography>{option}</Typography>
                  </Box>
                </li>
              )}
            />

            {/* Icon Preview */}
            {formData.icon && (
              <Box
                sx={{
                  mt: 2,
                  p: 2,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  bgcolor: '#f5f5f5',
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  Preview:
                </Typography>
                <Box sx={{ color: '#FFA500', display: 'flex', alignItems: 'center' }}>
                  {renderIcon(formData.icon)}
                </Box>
                <Typography variant="body2">{formData.icon}</Typography>
              </Box>
            )}
          </Box>
        </Box>
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
          sx={{
            bgcolor: '#FFA500',
            '&:hover': { bgcolor: '#FF8C00' },
          }}
        >
          {loading
            ? 'Saving...'
            : equipmentType
            ? 'Update Type'
            : 'Create Type'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EquipmentTypeForm;
