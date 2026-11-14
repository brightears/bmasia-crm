import React from 'react';
import { Box } from '@mui/material';
import { product } from '../../theme';

type ProductKey = 'beatbreeze' | 'soundtrack' | 'mixed' | string | null | undefined;

const LABELS: Record<string, string> = {
  beatbreeze: 'Beat Breeze',
  soundtrack: 'Soundtrack',
};

const Pill: React.FC<{ kind: 'beatbreeze' | 'soundtrack' }> = ({ kind }) => (
  <Box
    component="span"
    sx={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 0.75,
      height: 22,
      px: 1,
      borderRadius: '6px',
      fontSize: '0.75rem',
      fontWeight: 600,
      whiteSpace: 'nowrap',
      bgcolor: product[kind].bg,
      color: product[kind].fg,
    }}
  >
    <Box component="span" sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: product[kind].fg }} />
    {LABELS[kind]}
  </Box>
);

/** Shows which BMAsia product a customer uses, in that product's colour. */
const ProductChip: React.FC<{ value: ProductKey }> = ({ value }) => {
  if (value === 'beatbreeze' || value === 'soundtrack') return <Pill kind={value} />;
  if (value === 'mixed') {
    return (
      <Box component="span" sx={{ display: 'inline-flex', gap: 0.5, flexWrap: 'wrap' }}>
        <Pill kind="soundtrack" />
        <Pill kind="beatbreeze" />
      </Box>
    );
  }
  return null;
};

export default ProductChip;
