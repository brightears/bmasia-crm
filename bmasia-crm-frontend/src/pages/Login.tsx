import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  CssBaseline,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import { useAuth } from '../contexts/AuthContext';
import { getDailyQuote } from '../constants/quotes';
import { brand } from '../theme';

const Login: React.FC = () => {
  const { login, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [credentials, setCredentials] = useState({
    username: '',
    password: '',
    remember_me: true,
  });
  const [error, setError] = useState('');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setCredentials({
      ...credentials,
      [name]: type === 'checkbox' ? checked : value,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      await login(credentials);

      // Get the intended destination from location state, or default to /dashboard
      const from = (location.state as any)?.from?.pathname || '/dashboard';
      console.log('Login successful, navigating to:', from);

      // Navigate to the intended destination
      navigate(from, { replace: true });
    } catch (err: any) {
      console.error('Login component error:', err);
      // Get error message from the thrown Error object
      setError(err.message || 'Login failed. Please check your credentials.');
    }
  };

  const quote = getDailyQuote();

  return (
    <Box component="main" sx={{ minHeight: '100vh', display: 'flex', bgcolor: 'background.default' }}>
      <CssBaseline />
      {/* Brand panel (hidden on phones) */}
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flex: '0 0 44%',
          maxWidth: 620,
          flexDirection: 'column',
          justifyContent: 'space-between',
          p: 6,
          color: '#E8EDF2',
          background: `radial-gradient(120% 80% at 0% 100%, ${alpha(brand.amber, 0.28)} 0%, rgba(239,166,52,0) 55%), ${brand.navy}`,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box component="img" src="/bmasia-mark.png" alt="" sx={{ width: 40, height: 40 }} />
          <Typography sx={{ fontWeight: 600, fontSize: '1.125rem', letterSpacing: '-0.01em' }}>BMAsia</Typography>
        </Box>
        <Box>
          <Typography sx={{ fontSize: '2rem', fontWeight: 700, lineHeight: 1.2, letterSpacing: '-0.02em', mb: 2, maxWidth: 440 }}>
            Every customer, contract and renewal in one place.
          </Typography>
          <Typography sx={{ color: '#9AA6B2', maxWidth: 420 }}>
            The BMAsia CRM for sales, support and finance.
          </Typography>
        </Box>
        <Box sx={{ borderLeft: `2px solid ${brand.amber}`, pl: 2, maxWidth: 440 }}>
          <Typography sx={{ fontStyle: 'italic', color: '#C9D3DC' }}>&ldquo;{quote.text}&rdquo;</Typography>
          <Typography sx={{ color: '#9AA6B2', fontSize: '0.8125rem', mt: 0.5 }}>{quote.author}</Typography>
        </Box>
      </Box>

      {/* Sign-in form */}
      <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 2, sm: 4 } }}>
        <Box sx={{ width: '100%', maxWidth: 380 }}>
          <Box component="img" src="/bmasia-logo.png" alt="BMAsia" sx={{ height: 40, display: 'block', mb: 4 }} />
          <Typography component="h1" variant="h4" sx={{ mb: 0.5 }}>
            Sign in
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            Use your BMAsia CRM username and password.
          </Typography>
          <Box component="form" onSubmit={handleSubmit} sx={{ width: '100%' }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            <TextField
              margin="normal"
              required
              fullWidth
              size="medium"
              id="username"
              label="Username"
              name="username"
              autoComplete="username"
              autoFocus
              value={credentials.username}
              onChange={handleChange}
            />
            <TextField
              margin="normal"
              required
              fullWidth
              size="medium"
              name="password"
              label="Password"
              type="password"
              id="password"
              autoComplete="current-password"
              value={credentials.password}
              onChange={handleChange}
            />
            <FormControlLabel
              control={
                <Checkbox
                  name="remember_me"
                  checked={credentials.remember_me}
                  onChange={handleChange}
                  color="primary"
                />
              }
              label="Remember me"
              sx={{ mt: 1 }}
            />
            <Button
              type="submit"
              fullWidth
              size="large"
              variant="contained"
              sx={{ mt: 2, mb: 2 }}
              disabled={loading}
            >
              {loading ? 'Signing In...' : 'Sign In'}
            </Button>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default Login;