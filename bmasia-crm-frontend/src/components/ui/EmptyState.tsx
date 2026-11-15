import React from 'react';
import { Box, Typography } from '@mui/material';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  compact?: boolean;
}

/** What a list or tab shows when there is nothing in it: what is missing and what to do next. */
const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, description, action, compact }) => (
  <Box
    sx={{
      textAlign: 'center',
      py: compact ? 3 : 6,
      px: 2,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 1,
    }}
  >
    {icon && (
      <Box
        sx={{
          width: 48,
          height: 48,
          borderRadius: '50%',
          display: 'grid',
          placeItems: 'center',
          bgcolor: 'action.selected',
          color: 'primary.main',
          mb: 1,
          '& svg': { fontSize: 24 },
        }}
      >
        {icon}
      </Box>
    )}
    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
      {title}
    </Typography>
    {description && (
      <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 420 }}>
        {description}
      </Typography>
    )}
    {action && <Box sx={{ mt: 1.5 }}>{action}</Box>}
  </Box>
);

export default EmptyState;
