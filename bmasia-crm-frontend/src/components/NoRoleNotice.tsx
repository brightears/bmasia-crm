import React from 'react';
import { Alert, AlertTitle } from '@mui/material';

/** Shown to an account that has none of the server's roles (blank or unknown). */
const NoRoleNotice: React.FC<{ compact?: boolean }> = ({ compact }) => (
  <Alert severity="info" sx={{ mb: compact ? 2 : 0, mt: compact ? 0 : 2 }} data-testid={compact ? "no-role-banner" : "no-role-notice"}>
    <AlertTitle>Your account has no role yet</AlertTitle>
    Ask an administrator to give you a role. Until then you can use Today and My profile.
  </Alert>
);

export default NoRoleNotice;
