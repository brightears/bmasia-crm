import React from 'react';
import { Box, Paper, SxProps, Theme, Typography } from '@mui/material';

interface SectionCardProps {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  /** Remove the inner padding, e.g. when the card holds a table. */
  disablePadding?: boolean;
  sx?: SxProps<Theme>;
}

/** A white panel with an optional title row. The building block for record and dashboard pages. */
const SectionCard: React.FC<SectionCardProps> = ({ title, subtitle, action, children, disablePadding, sx }) => (
  <Paper component="section" sx={{ overflow: 'hidden', ...((sx as object) || {}) }}>
    {(title || action) && (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
          px: 2.5,
          pt: 2,
          pb: disablePadding ? 2 : 0,
          borderBottom: disablePadding ? 1 : 0,
          borderColor: 'divider',
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          {title && (
            <Typography variant="h6" component="h2">
              {title}
            </Typography>
          )}
          {subtitle && (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        {action}
      </Box>
    )}
    <Box sx={disablePadding ? undefined : { p: 2.5 }}>{children}</Box>
  </Paper>
);

export default SectionCard;
