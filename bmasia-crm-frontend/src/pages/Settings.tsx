import React from 'react';
import {
  Container,
  Paper,
  Typography,
  Box,
  Button,
} from '@mui/material';
import AutoModeIcon from '@mui/icons-material/AutoMode';
import { useNavigate } from 'react-router-dom';

const Settings: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        System Settings
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Box display="flex" alignItems="center" gap={2}>
          <AutoModeIcon sx={{ color: '#FFA500', fontSize: 32 }} />
          <Box>
            <Typography variant="h6">Email Automation</Typography>
            <Typography variant="body2" color="text.secondary">
              Email automation has been moved to Marketing & Campaigns → Email Automations
            </Typography>
            <Button
              variant="text"
              color="primary"
              onClick={() => navigate('/email-automations')}
              sx={{ mt: 1, p: 0 }}
            >
              Go to Email Automations →
            </Button>
          </Box>
        </Box>
      </Paper>

      {/* Future: Add other system settings sections here */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          General Settings
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Additional system settings will be available here in future updates.
        </Typography>
      </Paper>
    </Container>
  );
};

export default Settings;
