import React from 'react';
import { Box, Typography } from '@mui/material';

interface DetailFieldProps {
  label: string;
  children?: React.ReactNode;
  /** Shown when there is no value. */
  empty?: string;
}

/** A label above its value, used in record summaries. Empty values show a quiet dash. */
const DetailField: React.FC<DetailFieldProps> = ({ label, children, empty = '—' }) => {
  const hasValue = children !== undefined && children !== null && children !== '';
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 0.25 }}>
        {label}
      </Typography>
      <Typography
        variant="body1"
        component="div"
        sx={{ overflowWrap: 'anywhere', color: hasValue ? 'text.primary' : 'text.disabled' }}
      >
        {hasValue ? children : empty}
      </Typography>
    </Box>
  );
};

export default DetailField;
