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
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  Save,
  Cancel,
} from '@mui/icons-material';
import { EmailSequence } from '../types';
import ApiService from '../services/api';

interface SequenceFormProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  sequence?: EmailSequence | null;
}

interface FormData {
  name: string;
  description: string;
  status: 'active' | 'paused' | 'archived';
}

const SequenceForm: React.FC<SequenceFormProps> = ({
  open,
  onClose,
  onSuccess,
  sequence,
}) => {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    status: 'paused',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (sequence) {
      setFormData({
        name: sequence.name || '',
        description: sequence.description || '',
        status: sequence.status || 'paused',
      });
    } else {
      setFormData({
        name: '',
        description: '',
        status: 'paused',
      });
    }
    setError('');
    setErrors({});
  }, [sequence, open]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Sequence name is required';
    } else if (formData.name.length > 200) {
      newErrors.name = 'Sequence name must be 200 characters or less';
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
        description: formData.description || undefined,
      };

      if (sequence) {
        await ApiService.updateEmailSequence(sequence.id, submitData);
      } else {
        await ApiService.createEmailSequence(submitData);
      }

      onSuccess();
    } catch (err: any) {
      console.error('Sequence save error:', err);
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
          setError(err.response.data.message || 'Failed to save sequence');
        }
      } else {
        setError('Failed to save sequence. Please try again.');
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

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Typography variant="h6">
          {sequence ? 'Edit Email Sequence' : 'New Email Sequence'}
        </Typography>
      </DialogTitle>

      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Sequence Name"
              value={formData.name}
              onChange={(e) => handleFieldChange('name', e.target.value)}
              error={!!errors.name}
              helperText={errors.name || 'Maximum 200 characters'}
              required
              size="medium"
              inputProps={{ maxLength: 200 }}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Description"
              value={formData.description}
              onChange={(e) => handleFieldChange('description', e.target.value)}
              error={!!errors.description}
              helperText={errors.description || 'Optional: Describe the purpose of this sequence'}
              multiline
              rows={4}
              size="medium"
            />
          </Grid>

          <Grid item xs={12}>
            <FormControl fullWidth size="medium">
              <InputLabel>Status</InputLabel>
              <Select
                value={formData.status}
                onChange={(e) => handleFieldChange('status', e.target.value as 'active' | 'paused' | 'archived')}
                label="Status"
              >
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="paused">Paused</MenuItem>
                <MenuItem value="archived">Archived</MenuItem>
              </Select>
            </FormControl>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Active sequences will send emails to enrolled contacts. Paused sequences will not send emails.
            </Typography>
          </Grid>

          {!sequence && (
            <Grid item xs={12}>
              <Alert severity="info">
                After creating the sequence, you can add email steps in Phase 2.
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
          disabled={loading}
          startIcon={loading ? <CircularProgress size={20} /> : <Save />}
          sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
        >
          {loading ? 'Saving...' : sequence ? 'Update Sequence' : 'Create Sequence'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SequenceForm;
