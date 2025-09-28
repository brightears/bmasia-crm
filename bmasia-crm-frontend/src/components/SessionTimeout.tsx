import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  LinearProgress,
  Box,
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';

interface SessionTimeoutProps {
  warningTime?: number; // Warning time before logout (in minutes)
  timeoutTime?: number; // Total session timeout (in minutes)
}

/**
 * Session Timeout Component
 * Warns users before automatic logout and handles idle timeouts
 */
const SessionTimeout: React.FC<SessionTimeoutProps> = ({
  warningTime = 5, // 5 minutes warning
  timeoutTime = 30, // 30 minutes total timeout
}) => {
  const { logout, isAuthenticated, user } = useAuth();
  const [showWarning, setShowWarning] = useState(false);
  const [remainingTime, setRemainingTime] = useState(warningTime * 60);
  const [lastActivity, setLastActivity] = useState(Date.now());

  // Reset activity timer
  const resetActivityTimer = useCallback(() => {
    setLastActivity(Date.now());
    setShowWarning(false);
  }, []);

  // Handle user activity
  const handleUserActivity = useCallback(() => {
    resetActivityTimer();
  }, [resetActivityTimer]);

  // Extend session
  const extendSession = useCallback(() => {
    resetActivityTimer();
  }, [resetActivityTimer]);

  // Force logout
  const handleTimeout = useCallback(async () => {
    await logout();
  }, [logout]);

  // Monitor user activity
  useEffect(() => {
    if (!isAuthenticated || !user) return;

    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];

    events.forEach(event => {
      document.addEventListener(event, handleUserActivity, true);
    });

    return () => {
      events.forEach(event => {
        document.removeEventListener(event, handleUserActivity, true);
      });
    };
  }, [isAuthenticated, user, handleUserActivity]);

  // Session timeout logic
  useEffect(() => {
    if (!isAuthenticated || !user) return;

    const checkSession = () => {
      const now = Date.now();
      const timeSinceLastActivity = (now - lastActivity) / 1000 / 60; // in minutes

      if (timeSinceLastActivity >= timeoutTime) {
        // Auto logout
        handleTimeout();
      } else if (timeSinceLastActivity >= (timeoutTime - warningTime)) {
        // Show warning
        setShowWarning(true);
        const remaining = (timeoutTime - timeSinceLastActivity) * 60; // in seconds
        setRemainingTime(Math.max(0, remaining));
      }
    };

    const interval = setInterval(checkSession, 1000); // Check every second

    return () => clearInterval(interval);
  }, [isAuthenticated, user, lastActivity, timeoutTime, warningTime, handleTimeout]);

  // Countdown timer for warning dialog
  useEffect(() => {
    if (!showWarning) return;

    const countdown = setInterval(() => {
      setRemainingTime(prev => {
        const newTime = prev - 1;
        if (newTime <= 0) {
          handleTimeout();
          return 0;
        }
        return newTime;
      });
    }, 1000);

    return () => clearInterval(countdown);
  }, [showWarning, handleTimeout]);

  // Format time display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progressValue = (remainingTime / (warningTime * 60)) * 100;

  if (!isAuthenticated || !user) return null;

  return (
    <Dialog
      open={showWarning}
      disableEscapeKeyDown
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { borderTop: '4px solid', borderColor: 'warning.main' }
      }}
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          ⚠️ Session Timeout Warning
        </Box>
      </DialogTitle>

      <DialogContent>
        <Typography variant="body1" gutterBottom>
          Your session will expire in <strong>{formatTime(remainingTime)}</strong> due to inactivity.
        </Typography>

        <Typography variant="body2" color="text.secondary" gutterBottom>
          You will be automatically logged out to protect your account security.
        </Typography>

        <Box sx={{ mt: 2, mb: 1 }}>
          <LinearProgress
            variant="determinate"
            value={progressValue}
            color="warning"
            sx={{ height: 8, borderRadius: 4 }}
          />
        </Box>

        <Typography variant="caption" color="text.secondary">
          Time remaining: {formatTime(remainingTime)}
        </Typography>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button
          onClick={handleTimeout}
          color="secondary"
          variant="outlined"
        >
          Logout Now
        </Button>
        <Button
          onClick={extendSession}
          color="primary"
          variant="contained"
          autoFocus
        >
          Stay Logged In
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SessionTimeout;