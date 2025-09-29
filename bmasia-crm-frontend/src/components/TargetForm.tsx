import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  GridLegacy as Grid,
  Box,
  Typography,
  Switch,
  FormControlLabel,
  Chip,
  InputAdornment,
  Alert,
  SelectChangeEvent,
} from '@mui/material';
// Temporarily removed date picker due to compatibility issues
// import { DatePicker } from '@mui/x-date-pickers/DatePicker';
// import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
// import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { SalesTarget, User } from '../types';
import { useAuth } from '../contexts/AuthContext';

interface TargetFormProps {
  open: boolean;
  target?: SalesTarget | null;
  onSave: (target: SalesTarget) => void;
  onClose: () => void;
}

const TargetForm: React.FC<TargetFormProps> = ({
  open,
  target,
  onSave,
  onClose
}) => {
  const { user } = useAuth();
  const [formData, setFormData] = useState({
    name: '',
    period_type: 'Monthly' as 'Monthly' | 'Quarterly' | 'Yearly',
    period_start: new Date().toISOString().split('T')[0],
    period_end: new Date().toISOString().split('T')[0],
    target_type: 'Revenue' as 'Revenue' | 'Units' | 'Customers' | 'Contracts',
    target_value: '',
    stretch_target: '',
    currency: 'USD',
    unit_type: '',
    team_target: false,
    team_name: '',
    assigned_to: user?.id || '',
    notes: '',
    justification: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [mockUsers] = useState<User[]>([
    {
      id: '1',
      username: 'john.doe',
      email: 'john@bmasia.com',
      first_name: 'John',
      last_name: 'Doe',
      role: 'Sales',
      is_active: true,
      date_joined: '2024-01-01T00:00:00Z',
    },
    {
      id: '2',
      username: 'jane.smith',
      email: 'jane@bmasia.com',
      first_name: 'Jane',
      last_name: 'Smith',
      role: 'Sales',
      is_active: true,
      date_joined: '2024-01-01T00:00:00Z',
    },
  ]);

  useEffect(() => {
    if (target) {
      setFormData({
        name: target.name,
        period_type: target.period_type,
        period_start: target.period_start.split('T')[0],
        period_end: target.period_end.split('T')[0],
        target_type: target.target_type,
        target_value: target.target_value.toString(),
        stretch_target: target.stretch_target?.toString() || '',
        currency: target.currency,
        unit_type: target.unit_type || '',
        team_target: target.team_target,
        team_name: target.team_name || '',
        assigned_to: target.assigned_to || '',
        notes: target.notes || '',
        justification: target.justification || '',
      });
    } else {
      resetForm();
    }
  }, [target, user?.id]);

  const resetForm = () => {
    const now = new Date();
    const endDate = new Date(now);
    endDate.setMonth(endDate.getMonth() + 1);

    setFormData({
      name: '',
      period_type: 'Monthly',
      period_start: now.toISOString().split('T')[0],
      period_end: endDate.toISOString().split('T')[0],
      target_type: 'Revenue',
      target_value: '',
      stretch_target: '',
      currency: 'USD',
      unit_type: '',
      team_target: false,
      team_name: '',
      assigned_to: user?.id || '',
      notes: '',
      justification: '',
    });
    setErrors({});
  };

  const handleChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));

    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }

    // Auto-adjust period end based on period type and start date
    if (field === 'period_type' || field === 'period_start') {
      const startDate = field === 'period_start' ? value : formData.period_start;
      const periodType = field === 'period_type' ? value : formData.period_type;

      if (startDate) {
        const endDate = new Date(startDate);
        switch (periodType) {
          case 'Monthly':
            endDate.setMonth(endDate.getMonth() + 1);
            endDate.setDate(endDate.getDate() - 1);
            break;
          case 'Quarterly':
            endDate.setMonth(endDate.getMonth() + 3);
            endDate.setDate(endDate.getDate() - 1);
            break;
          case 'Yearly':
            endDate.setFullYear(endDate.getFullYear() + 1);
            endDate.setDate(endDate.getDate() - 1);
            break;
        }
        setFormData(prev => ({ ...prev, period_end: endDate.toISOString().split('T')[0] }));
      }
    }

    // Auto-generate name based on inputs
    if (['period_type', 'target_type', 'team_target'].includes(field)) {
      const periodType = field === 'period_type' ? value : formData.period_type;
      const targetType = field === 'target_type' ? value : formData.target_type;
      const isTeam = field === 'team_target' ? value : formData.team_target;

      const startDate = new Date(formData.period_start);
      const period = formData.period_start ? `${periodType} ${startDate.getFullYear()}` : periodType;
      const prefix = isTeam ? 'Team' : 'Individual';
      const name = `${prefix} ${targetType} Target - ${period}`;

      setFormData(prev => ({ ...prev, name }));
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Target name is required';
    }

    if (!formData.target_value || parseFloat(formData.target_value) <= 0) {
      newErrors.target_value = 'Target value must be greater than 0';
    }

    if (formData.stretch_target && parseFloat(formData.stretch_target) <= parseFloat(formData.target_value)) {
      newErrors.stretch_target = 'Stretch target must be greater than target value';
    }

    if (formData.target_type !== 'Revenue' && !formData.unit_type.trim()) {
      newErrors.unit_type = 'Unit type is required for non-revenue targets';
    }

    if (formData.team_target && !formData.team_name.trim()) {
      newErrors.team_name = 'Team name is required for team targets';
    }

    if (!formData.team_target && !formData.assigned_to) {
      newErrors.assigned_to = 'Please select a user for individual targets';
    }

    if (new Date(formData.period_end) <= new Date(formData.period_start)) {
      newErrors.period_end = 'End date must be after start date';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (!validateForm()) return;

    const targetValue = parseFloat(formData.target_value);
    const stretchTarget = formData.stretch_target ? parseFloat(formData.stretch_target) : undefined;

    const savedTarget: SalesTarget = {
      id: target?.id || '',
      name: formData.name,
      period_type: formData.period_type,
      period_start: new Date(formData.period_start).toISOString(),
      period_end: new Date(formData.period_end).toISOString(),
      target_type: formData.target_type,
      target_value: targetValue,
      stretch_target: stretchTarget,
      currency: formData.currency,
      unit_type: formData.unit_type || undefined,
      assigned_to: formData.team_target ? undefined : formData.assigned_to,
      assigned_to_name: formData.team_target ? undefined : mockUsers.find(u => u.id === formData.assigned_to)?.first_name + ' ' + mockUsers.find(u => u.id === formData.assigned_to)?.last_name,
      team_target: formData.team_target,
      team_name: formData.team_target ? formData.team_name : undefined,
      status: target?.status || 'Active',
      current_value: target?.current_value || 0,
      achievement_percentage: target?.achievement_percentage || 0,
      stretch_achievement_percentage: target?.stretch_achievement_percentage,
      is_on_track: target?.is_on_track || false,
      forecasted_value: target?.forecasted_value || 0,
      forecasted_achievement: target?.forecasted_achievement || 0,
      risk_level: target?.risk_level || 'Medium',
      notes: formData.notes,
      justification: formData.justification,
      created_by: target?.created_by || user?.id || '',
      created_by_name: target?.created_by_name || (user?.first_name + ' ' + user?.last_name) || '',
      created_at: target?.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
      days_remaining: Math.ceil((new Date(formData.period_end).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)),
      days_total: Math.ceil((new Date(formData.period_end).getTime() - new Date(formData.period_start).getTime()) / (1000 * 60 * 60 * 24)),
      expected_daily_progress: targetValue / Math.ceil((new Date(formData.period_end).getTime() - new Date(formData.period_start).getTime()) / (1000 * 60 * 60 * 24)),
      actual_daily_progress: target?.actual_daily_progress || 0,
      variance_from_plan: target?.variance_from_plan || 0,
    };

    onSave(savedTarget);
  };

  const getCurrencySymbol = (currency: string) => {
    switch (currency) {
      case 'USD': return '$';
      case 'THB': return '฿';
      case 'EUR': return '€';
      default: return '$';
    }
  };

  const getUnitLabel = (targetType: string) => {
    switch (targetType) {
      case 'Revenue': return 'Amount';
      case 'Units': return 'Quantity';
      case 'Customers': return 'Count';
      case 'Contracts': return 'Count';
      default: return 'Value';
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {target ? 'Edit Sales Target' : 'Create Sales Target'}
      </DialogTitle>
      <DialogContent>
        <Grid container spacing={3} sx={{ mt: 1 }}>
          {/* Basic Information */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Basic Information
            </Typography>
          </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Target Name"
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                error={!!errors.name}
                helperText={errors.name}
              />
            </Grid>

            <Grid item xs={12} sm={4}>
              <FormControl fullWidth error={!!errors.period_type}>
                <InputLabel>Period Type</InputLabel>
                <Select
                  value={formData.period_type}
                  onChange={(e: SelectChangeEvent) => handleChange('period_type', e.target.value)}
                  label="Period Type"
                >
                  <MenuItem value="Monthly">Monthly</MenuItem>
                  <MenuItem value="Quarterly">Quarterly</MenuItem>
                  <MenuItem value="Yearly">Yearly</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Start Date"
                type="date"
                value={formData.period_start}
                onChange={(e) => handleChange('period_start', e.target.value)}
                error={!!errors.period_start}
                helperText={errors.period_start}
                InputLabelProps={{
                  shrink: true,
                }}
              />
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="End Date"
                type="date"
                value={formData.period_end}
                onChange={(e) => handleChange('period_end', e.target.value)}
                error={!!errors.period_end}
                helperText={errors.period_end}
                InputLabelProps={{
                  shrink: true,
                }}
              />
            </Grid>

            {/* Target Configuration */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Target Configuration
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Target Type</InputLabel>
                <Select
                  value={formData.target_type}
                  onChange={(e: SelectChangeEvent) => handleChange('target_type', e.target.value)}
                  label="Target Type"
                >
                  <MenuItem value="Revenue">Revenue</MenuItem>
                  <MenuItem value="Units">Units</MenuItem>
                  <MenuItem value="Customers">New Customers</MenuItem>
                  <MenuItem value="Contracts">Contracts</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {formData.target_type !== 'Revenue' && (
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Unit Type"
                  value={formData.unit_type}
                  onChange={(e) => handleChange('unit_type', e.target.value)}
                  error={!!errors.unit_type}
                  helperText={errors.unit_type || 'e.g., licenses, subscriptions, devices'}
                  placeholder="e.g., licenses, subscriptions"
                />
              </Grid>
            )}

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label={getUnitLabel(formData.target_type)}
                value={formData.target_value}
                onChange={(e) => handleChange('target_value', e.target.value)}
                error={!!errors.target_value}
                helperText={errors.target_value}
                type="number"
                InputProps={{
                  startAdornment: formData.target_type === 'Revenue' ? (
                    <InputAdornment position="start">
                      {getCurrencySymbol(formData.currency)}
                    </InputAdornment>
                  ) : undefined,
                }}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label={`Stretch ${getUnitLabel(formData.target_type)} (Optional)`}
                value={formData.stretch_target}
                onChange={(e) => handleChange('stretch_target', e.target.value)}
                error={!!errors.stretch_target}
                helperText={errors.stretch_target || 'Ambitious goal beyond the main target'}
                type="number"
                InputProps={{
                  startAdornment: formData.target_type === 'Revenue' ? (
                    <InputAdornment position="start">
                      {getCurrencySymbol(formData.currency)}
                    </InputAdornment>
                  ) : undefined,
                }}
              />
            </Grid>

            {formData.target_type === 'Revenue' && (
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel>Currency</InputLabel>
                  <Select
                    value={formData.currency}
                    onChange={(e: SelectChangeEvent) => handleChange('currency', e.target.value)}
                    label="Currency"
                  >
                    <MenuItem value="USD">USD ($)</MenuItem>
                    <MenuItem value="THB">THB (฿)</MenuItem>
                    <MenuItem value="EUR">EUR (€)</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            )}

            {/* Assignment */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Assignment
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.team_target}
                    onChange={(e) => handleChange('team_target', e.target.checked)}
                  />
                }
                label="Team Target"
              />
            </Grid>

            {formData.team_target ? (
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Team Name"
                  value={formData.team_name}
                  onChange={(e) => handleChange('team_name', e.target.value)}
                  error={!!errors.team_name}
                  helperText={errors.team_name}
                  placeholder="e.g., Sales Team A, APAC Sales"
                />
              </Grid>
            ) : (
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth error={!!errors.assigned_to}>
                  <InputLabel>Assigned To</InputLabel>
                  <Select
                    value={formData.assigned_to}
                    onChange={(e: SelectChangeEvent) => handleChange('assigned_to', e.target.value)}
                    label="Assigned To"
                  >
                    {mockUsers.map((user) => (
                      <MenuItem key={user.id} value={user.id}>
                        {user.first_name} {user.last_name} ({user.role})
                      </MenuItem>
                    ))}
                  </Select>
                  {errors.assigned_to && (
                    <Typography variant="caption" color="error">
                      {errors.assigned_to}
                    </Typography>
                  )}
                </FormControl>
              </Grid>
            )}

            {/* Additional Information */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Additional Information
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Justification"
                value={formData.justification}
                onChange={(e) => handleChange('justification', e.target.value)}
                multiline
                rows={3}
                placeholder="Why is this target appropriate? What factors support this goal?"
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Notes"
                value={formData.notes}
                onChange={(e) => handleChange('notes', e.target.value)}
                multiline
                rows={2}
                placeholder="Additional notes or comments..."
              />
            </Grid>

            {/* Target Preview */}
            <Grid item xs={12}>
              <Alert severity="info">
                <Typography variant="body2">
                  <strong>Target Preview:</strong> {formData.name}
                  <br />
                  Period: {new Date(formData.period_start).toLocaleDateString()} - {new Date(formData.period_end).toLocaleDateString()}
                  <br />
                  Goal: {formData.target_type === 'Revenue' && getCurrencySymbol(formData.currency)}{parseFloat(formData.target_value || '0').toLocaleString()}
                  {formData.target_type !== 'Revenue' && ` ${formData.unit_type}`}
                  {formData.stretch_target && (
                    <> (Stretch: {formData.target_type === 'Revenue' && getCurrencySymbol(formData.currency)}{parseFloat(formData.stretch_target).toLocaleString()}{formData.target_type !== 'Revenue' && ` ${formData.unit_type}`})</>
                  )}
                </Typography>
              </Alert>
            </Grid>
          </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSubmit} variant="contained">
          {target ? 'Update' : 'Create'} Target
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TargetForm;