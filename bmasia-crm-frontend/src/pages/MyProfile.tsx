import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Stack,
  Chip,
  IconButton,
  InputAdornment,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Snackbar,
  Link,
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
  Person,
  Lock,
  Email,
  CheckCircle,
  Warning,
  Save,
  Clear,
  Send,
  Info,
} from '@mui/icons-material';
import { GridLegacy as Grid } from '@mui/material';
import { User, UserRole, USER_ROLE_LABELS, USER_ROLE_COLORS, PasswordChangeData, SmtpSettingsData } from '../types';
import ApiService from '../services/api';
const MyProfile: React.FC = () => {

  // Profile state
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileData, setProfileData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    department: '',
  });

  // Password state
  const [passwordData, setPasswordData] = useState<PasswordChangeData>({
    old_password: '',
    new_password: '',
  });
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordErrors, setPasswordErrors] = useState<string[]>([]);

  // SMTP state
  const [smtpData, setSmtpData] = useState<SmtpSettingsData>({
    smtp_email: '',
    smtp_password: '',
  });
  const [showSmtpPassword, setShowSmtpPassword] = useState(false);
  const [smtpSaving, setSmtpSaving] = useState(false);
  const [smtpTesting, setSmtpTesting] = useState(false);
  const [smtpClearDialogOpen, setSmtpClearDialogOpen] = useState(false);

  // Snackbar state
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error' | 'info' | 'warning'>('success');

  // Error state
  const [error, setError] = useState('');

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      setError('');
      const profile = await ApiService.getMyProfile();
      setUser(profile);
      setProfileData({
        first_name: profile.first_name || '',
        last_name: profile.last_name || '',
        email: profile.email || '',
        phone: profile.phone || '',
        department: profile.department || '',
      });
      setSmtpData({
        smtp_email: profile.smtp_email || '',
        smtp_password: '', // Never pre-fill password
      });
    } catch (err: any) {
      console.error('Load profile error:', err);
      setError(`Failed to load profile: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleProfileChange = (field: string) => (event: React.ChangeEvent<HTMLInputElement>) => {
    setProfileData({ ...profileData, [field]: event.target.value });
  };

  const handleProfileSave = async () => {
    try {
      setProfileSaving(true);
      setError('');
      const updatedUser = await ApiService.updateMyProfile(profileData);
      setUser(updatedUser);
      showSnackbar('Profile updated successfully', 'success');
    } catch (err: any) {
      console.error('Save profile error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      setError(`Failed to update profile: ${errorMsg}`);
      showSnackbar(`Failed to update profile: ${errorMsg}`, 'error');
    } finally {
      setProfileSaving(false);
    }
  };

  const validatePassword = (): boolean => {
    const errors: string[] = [];

    if (!passwordData.old_password) {
      errors.push('Current password is required');
    }

    if (!passwordData.new_password) {
      errors.push('New password is required');
    } else if (passwordData.new_password.length < 8) {
      errors.push('New password must be at least 8 characters');
    }

    if (passwordData.new_password !== confirmPassword) {
      errors.push('New passwords do not match');
    }

    if (passwordData.old_password === passwordData.new_password) {
      errors.push('New password must be different from current password');
    }

    setPasswordErrors(errors);
    return errors.length === 0;
  };

  const handlePasswordChange = async () => {
    if (!validatePassword()) {
      return;
    }

    try {
      setPasswordSaving(true);
      setError('');
      setPasswordErrors([]);
      const response = await ApiService.changePassword(passwordData);
      showSnackbar(response.message || 'Password changed successfully', 'success');
      // Clear password fields
      setPasswordData({ old_password: '', new_password: '' });
      setConfirmPassword('');
    } catch (err: any) {
      console.error('Change password error:', err);
      const errorMsg = err.response?.data?.detail || err.response?.data?.error || err.message || 'Unknown error';
      setPasswordErrors([errorMsg]);
      showSnackbar(`Failed to change password: ${errorMsg}`, 'error');
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleSmtpChange = (field: keyof SmtpSettingsData) => (event: React.ChangeEvent<HTMLInputElement>) => {
    setSmtpData({ ...smtpData, [field]: event.target.value });
  };

  const handleSmtpSave = async () => {
    if (!smtpData.smtp_email || !smtpData.smtp_password) {
      showSnackbar('Please provide both SMTP email and password', 'warning');
      return;
    }

    try {
      setSmtpSaving(true);
      setError('');
      const response = await ApiService.updateSmtpSettings(smtpData);
      showSnackbar(response.message || 'SMTP settings saved successfully', 'success');
      // Reload profile to get updated smtp_configured status
      await loadProfile();
      // Clear password field for security
      setSmtpData({ ...smtpData, smtp_password: '' });
    } catch (err: any) {
      console.error('Save SMTP error:', err);
      const errorMsg = err.response?.data?.detail || err.response?.data?.error || err.message || 'Unknown error';
      setError(`Failed to save SMTP settings: ${errorMsg}`);
      showSnackbar(`Failed to save SMTP settings: ${errorMsg}`, 'error');
    } finally {
      setSmtpSaving(false);
    }
  };

  const handleSmtpTest = async () => {
    try {
      setSmtpTesting(true);
      setError('');
      const response = await ApiService.testSmtpConnection();
      if (response.success) {
        showSnackbar(response.message || 'SMTP connection successful!', 'success');
      } else {
        showSnackbar(response.error || response.message || 'SMTP connection failed', 'error');
      }
    } catch (err: any) {
      console.error('Test SMTP error:', err);
      const errorMsg = err.response?.data?.error || err.response?.data?.detail || err.message || 'Unknown error';
      showSnackbar(`SMTP test failed: ${errorMsg}`, 'error');
    } finally {
      setSmtpTesting(false);
    }
  };

  const handleSmtpClear = async () => {
    try {
      setSmtpSaving(true);
      setError('');
      const response = await ApiService.clearSmtpSettings();
      showSnackbar(response.message || 'SMTP settings cleared successfully', 'success');
      setSmtpData({ smtp_email: '', smtp_password: '' });
      setSmtpClearDialogOpen(false);
      // Reload profile to get updated smtp_configured status
      await loadProfile();
    } catch (err: any) {
      console.error('Clear SMTP error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      showSnackbar(`Failed to clear SMTP settings: ${errorMsg}`, 'error');
    } finally {
      setSmtpSaving(false);
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error' | 'info' | 'warning') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  };

  const handleSnackbarClose = () => {
    setSnackbarOpen(false);
  };

  const getRoleColor = (role: UserRole): string => {
    return USER_ROLE_COLORS[role] || '#757575';
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!user) {
    return (
      <Box>
        <Alert severity="error">Failed to load profile. Please try refreshing the page.</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          My Profile
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Stack spacing={3}>
        {/* Profile Information Card */}
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
              <Person sx={{ fontSize: 32, color: '#FFA500', mr: 2 }} />
              <Typography variant="h6" component="h2">
                Profile Information
              </Typography>
            </Box>

            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="First Name"
                  value={profileData.first_name}
                  onChange={handleProfileChange('first_name')}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Last Name"
                  value={profileData.last_name}
                  onChange={handleProfileChange('last_name')}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Email"
                  type="email"
                  value={profileData.email}
                  onChange={handleProfileChange('email')}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Phone"
                  value={profileData.phone}
                  onChange={handleProfileChange('phone')}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Department"
                  value={profileData.department}
                  onChange={handleProfileChange('department')}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Username"
                  value={user.username}
                  disabled
                  helperText="Username cannot be changed"
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                    Role
                  </Typography>
                  <Chip
                    label={USER_ROLE_LABELS[user.role as UserRole] || user.role}
                    sx={{
                      backgroundColor: getRoleColor(user.role as UserRole),
                      color: 'white',
                      fontWeight: 'bold',
                    }}
                  />
                </Box>
              </Grid>
              <Grid item xs={12} md={6}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                    Member Since
                  </Typography>
                  <Typography variant="body1">
                    {new Date(user.date_joined).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </Typography>
                </Box>
              </Grid>
              {user.last_login && (
                <Grid item xs={12} md={6}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                      Last Login
                    </Typography>
                    <Typography variant="body1">
                      {new Date(user.last_login).toLocaleString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </Typography>
                  </Box>
                </Grid>
              )}
            </Grid>

            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                startIcon={profileSaving ? <CircularProgress size={16} /> : <Save />}
                onClick={handleProfileSave}
                disabled={profileSaving}
                sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
              >
                {profileSaving ? 'Saving...' : 'Save Profile'}
              </Button>
            </Box>
          </CardContent>
        </Card>

        {/* Change Password Card */}
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
              <Lock sx={{ fontSize: 32, color: '#FFA500', mr: 2 }} />
              <Typography variant="h6" component="h2">
                Change Password
              </Typography>
            </Box>

            {passwordErrors.length > 0 && (
              <Alert severity="error" sx={{ mb: 2 }}>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {passwordErrors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </Alert>
            )}

            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Current Password"
                  type={showOldPassword ? 'text' : 'password'}
                  value={passwordData.old_password}
                  onChange={(e) => setPasswordData({ ...passwordData, old_password: e.target.value })}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => setShowOldPassword(!showOldPassword)}
                          edge="end"
                        >
                          {showOldPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
              </Grid>
              <Grid item xs={12} md={6}></Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="New Password"
                  type={showNewPassword ? 'text' : 'password'}
                  value={passwordData.new_password}
                  onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                  helperText="Minimum 8 characters"
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => setShowNewPassword(!showNewPassword)}
                          edge="end"
                        >
                          {showNewPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Confirm New Password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  helperText="Must match new password"
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
            </Grid>

            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                startIcon={passwordSaving ? <CircularProgress size={16} /> : <Lock />}
                onClick={handlePasswordChange}
                disabled={passwordSaving}
                sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
              >
                {passwordSaving ? 'Changing...' : 'Change Password'}
              </Button>
            </Box>
          </CardContent>
        </Card>

        {/* SMTP Configuration Card */}
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Email sx={{ fontSize: 32, color: '#FFA500', mr: 2 }} />
              <Typography variant="h6" component="h2">
                SMTP Email Configuration
              </Typography>
              {user.smtp_configured ? (
                <Chip
                  icon={<CheckCircle />}
                  label="Configured"
                  color="success"
                  size="small"
                  sx={{ ml: 2 }}
                />
              ) : (
                <Chip
                  icon={<Warning />}
                  label="Not Configured"
                  color="warning"
                  size="small"
                  sx={{ ml: 2 }}
                />
              )}
            </Box>

            <Alert severity="info" icon={<Info />} sx={{ mb: 3 }}>
              <Typography variant="body2" fontWeight="bold" gutterBottom>
                Configure your Gmail SMTP to send emails from your own account
              </Typography>
              <Typography variant="body2" component="div">
                <strong>For Gmail users:</strong>
                <ol style={{ margin: '8px 0', paddingLeft: 20 }}>
                  <li>Use your Gmail address (e.g., yourname@bmasiamusic.com)</li>
                  <li>Create an App Password (not your regular Gmail password)</li>
                  <li>
                    Follow{' '}
                    <Link
                      href="https://support.google.com/accounts/answer/185833"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Google's App Password guide
                    </Link>
                  </li>
                </ol>
                Emails will be sent from your account and replies will come to your inbox.
              </Typography>
            </Alert>

            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="SMTP Email Address"
                  type="email"
                  value={smtpData.smtp_email}
                  onChange={handleSmtpChange('smtp_email')}
                  placeholder="yourname@bmasiamusic.com"
                  helperText={user.smtp_email ? `Current: ${user.smtp_email}` : 'Your email address for sending'}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="SMTP Password"
                  type={showSmtpPassword ? 'text' : 'password'}
                  value={smtpData.smtp_password}
                  onChange={handleSmtpChange('smtp_password')}
                  placeholder="Gmail App Password"
                  helperText="Use Gmail App Password (16 characters, no spaces)"
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => setShowSmtpPassword(!showSmtpPassword)}
                          edge="end"
                        >
                          {showSmtpPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
              </Grid>
            </Grid>

            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
              <Box sx={{ display: 'flex', gap: 1 }}>
                {user.smtp_configured && (
                  <>
                    <Button
                      variant="outlined"
                      startIcon={smtpTesting ? <CircularProgress size={16} /> : <Send />}
                      onClick={handleSmtpTest}
                      disabled={smtpTesting || smtpSaving}
                      sx={{
                        borderColor: '#FFA500',
                        color: '#FFA500',
                        '&:hover': { borderColor: '#FF8C00', backgroundColor: 'rgba(255, 165, 0, 0.04)' },
                      }}
                    >
                      {smtpTesting ? 'Testing...' : 'Test Connection'}
                    </Button>
                    <Button
                      variant="outlined"
                      color="error"
                      startIcon={<Clear />}
                      onClick={() => setSmtpClearDialogOpen(true)}
                      disabled={smtpSaving}
                    >
                      Clear Settings
                    </Button>
                  </>
                )}
              </Box>
              <Button
                variant="contained"
                startIcon={smtpSaving ? <CircularProgress size={16} /> : <Save />}
                onClick={handleSmtpSave}
                disabled={smtpSaving}
                sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
              >
                {smtpSaving ? 'Saving...' : 'Save SMTP Settings'}
              </Button>
            </Box>
          </CardContent>
        </Card>
      </Stack>

      {/* Clear SMTP Confirmation Dialog */}
      <Dialog
        open={smtpClearDialogOpen}
        onClose={() => setSmtpClearDialogOpen(false)}
        aria-labelledby="smtp-clear-dialog-title"
        aria-describedby="smtp-clear-dialog-description"
      >
        <DialogTitle id="smtp-clear-dialog-title">
          Clear SMTP Settings?
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="smtp-clear-dialog-description">
            Are you sure you want to clear your SMTP configuration?
            You will no longer be able to send emails from your own account until you reconfigure these settings.
            The system will fall back to default email senders.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setSmtpClearDialogOpen(false)}
            disabled={smtpSaving}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSmtpClear}
            color="error"
            variant="contained"
            disabled={smtpSaving}
            startIcon={smtpSaving ? <CircularProgress size={16} /> : <Clear />}
          >
            {smtpSaving ? 'Clearing...' : 'Clear Settings'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleSnackbarClose} severity={snackbarSeverity} sx={{ width: '100%' }}>
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default MyProfile;
