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
  InputAdornment,
  IconButton,
} from '@mui/material';
import { Save, Cancel, Visibility, VisibilityOff } from '@mui/icons-material';
import { User, UserRole, USER_ROLE_LABELS, UserCreateData, UserUpdateData } from '../types';
import ApiService from '../services/api';

interface UserFormProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (message: string) => void;
  user: User | null;
}

interface UserFormData {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  confirm_password: string;
  role: UserRole;
  phone: string;
  department: string;
  is_active: boolean;
}

const UserForm: React.FC<UserFormProps> = ({
  open,
  onClose,
  onSuccess,
  user,
}) => {
  const [formData, setFormData] = useState<UserFormData>({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    confirm_password: '',
    role: 'Sales',
    phone: '',
    department: '',
    is_active: true,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  useEffect(() => {
    if (user) {
      setFormData({
        username: user.username || '',
        email: user.email || '',
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        password: '',
        confirm_password: '',
        role: user.role as UserRole || 'Sales',
        phone: user.phone || '',
        department: user.department || '',
        is_active: user.is_active !== undefined ? user.is_active : true,
      });
    } else {
      // Reset form for new user
      setFormData({
        username: '',
        email: '',
        first_name: '',
        last_name: '',
        password: '',
        confirm_password: '',
        role: 'Sales',
        phone: '',
        department: '',
        is_active: true,
      });
    }
    setError('');
    setErrors({});
  }, [user, open]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    // Username validation (required for new users, disabled for edit)
    if (!user && !formData.username.trim()) {
      newErrors.username = 'Username is required';
    } else if (!user && formData.username.length < 3) {
      newErrors.username = 'Username must be at least 3 characters';
    } else if (!user && !/^[a-zA-Z0-9_]+$/.test(formData.username)) {
      newErrors.username = 'Username can only contain letters, numbers, and underscores';
    }

    // Email validation
    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(formData.email)) {
        newErrors.email = 'Please enter a valid email address';
      }
    }

    // Password validation (required for new users, optional for edit)
    if (!user) {
      // Creating new user - password required
      if (!formData.password) {
        newErrors.password = 'Password is required';
      } else if (formData.password.length < 8) {
        newErrors.password = 'Password must be at least 8 characters';
      }

      if (!formData.confirm_password) {
        newErrors.confirm_password = 'Please confirm password';
      } else if (formData.password !== formData.confirm_password) {
        newErrors.confirm_password = 'Passwords do not match';
      }
    } else {
      // Editing user - password optional, but if provided must be valid
      if (formData.password) {
        if (formData.password.length < 8) {
          newErrors.password = 'Password must be at least 8 characters';
        }
        if (formData.password !== formData.confirm_password) {
          newErrors.confirm_password = 'Passwords do not match';
        }
      }
    }

    // Phone validation (optional)
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
      if (user) {
        // Update existing user
        const updateData: UserUpdateData = {
          email: formData.email,
          first_name: formData.first_name,
          last_name: formData.last_name,
          role: formData.role,
          phone: formData.phone || undefined,
          department: formData.department || undefined,
          is_active: formData.is_active,
        };

        // Only include password if it was entered
        if (formData.password) {
          updateData.password = formData.password;
        }

        await ApiService.updateUser(user.id, updateData);
        onSuccess('User updated successfully');
      } else {
        // Create new user
        const createData: UserCreateData = {
          username: formData.username,
          email: formData.email,
          password: formData.password,
          first_name: formData.first_name,
          last_name: formData.last_name,
          role: formData.role,
          phone: formData.phone || undefined,
          department: formData.department || undefined,
          is_active: formData.is_active,
        };

        await ApiService.createUser(createData);
        onSuccess('User created successfully');
      }
    } catch (err: any) {
      console.error('User save error:', err);
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
          setError('Please check the form for errors');
        } else {
          setError(err.response.data.message || 'Failed to save user');
        }
      } else {
        setError('Failed to save user. Please try again.');
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

  const handleFieldChange = (field: keyof UserFormData, value: any) => {
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
          {user ? 'Edit User' : 'New User'}
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
              label="Username"
              value={formData.username}
              onChange={(e) => handleFieldChange('username', e.target.value)}
              error={!!errors.username}
              helperText={errors.username || (user ? 'Username cannot be changed' : 'Unique identifier for login')}
              required={!user}
              disabled={!!user}
              size="medium"
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="First Name"
              value={formData.first_name}
              onChange={(e) => handleFieldChange('first_name', e.target.value)}
              error={!!errors.first_name}
              helperText={errors.first_name}
              size="medium"
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
              size="medium"
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={formData.email}
              onChange={(e) => handleFieldChange('email', e.target.value)}
              error={!!errors.email}
              helperText={errors.email}
              required
              size="medium"
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Password Section */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              {user ? 'Change Password (Optional)' : 'Password'}
            </Typography>
            {user && (
              <Typography variant="caption" color="text.secondary">
                Leave blank to keep current password
              </Typography>
            )}
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={(e) => handleFieldChange('password', e.target.value)}
              error={!!errors.password}
              helperText={errors.password || 'Minimum 8 characters'}
              required={!user}
              size="medium"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                    >
                      {showPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Confirm Password"
              type={showConfirmPassword ? 'text' : 'password'}
              value={formData.confirm_password}
              onChange={(e) => handleFieldChange('confirm_password', e.target.value)}
              error={!!errors.confirm_password}
              helperText={errors.confirm_password}
              required={!user}
              size="medium"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      edge="end"
                    >
                      {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Role & Department */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Role & Department
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth error={!!errors.role} size="medium">
              <InputLabel>Role *</InputLabel>
              <Select
                value={formData.role}
                onChange={(e) => handleFieldChange('role', e.target.value)}
                label="Role *"
                required
              >
                <MenuItem value="Sales">{USER_ROLE_LABELS.Sales}</MenuItem>
                <MenuItem value="Finance">{USER_ROLE_LABELS.Finance}</MenuItem>
                <MenuItem value="Tech">{USER_ROLE_LABELS.Tech}</MenuItem>
                <MenuItem value="Music">{USER_ROLE_LABELS.Music}</MenuItem>
                <MenuItem value="Admin">{USER_ROLE_LABELS.Admin}</MenuItem>
              </Select>
            </FormControl>
            {errors.role && (
              <Typography variant="caption" color="error" sx={{ mt: 0.5, display: 'block' }}>
                {errors.role}
              </Typography>
            )}
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Department"
              value={formData.department}
              onChange={(e) => handleFieldChange('department', e.target.value)}
              error={!!errors.department}
              helperText={errors.department}
              placeholder="e.g., Sales, IT, Operations"
              size="medium"
            />
          </Grid>

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Contact Information */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Contact Information
            </Typography>
          </Grid>

          <Grid item xs={12}>
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

          <Divider sx={{ width: '100%', my: 2 }} />

          {/* Settings */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
              Settings
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ pt: 1 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.is_active}
                    onChange={(e) => handleFieldChange('is_active', e.target.checked)}
                    color="success"
                  />
                }
                label={
                  <Box>
                    <Typography variant="body2">Active</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Inactive users cannot log in to the system
                    </Typography>
                  </Box>
                }
              />
            </Box>
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
          sx={{
            bgcolor: '#FFA500',
            '&:hover': {
              bgcolor: '#FF8C00',
            },
          }}
        >
          {loading ? 'Saving...' : (user ? 'Update User' : 'Create User')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default UserForm;
