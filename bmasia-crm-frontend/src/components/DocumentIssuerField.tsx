import React from 'react';
import { MenuItem, TextField } from '@mui/material';
import { DOCUMENT_BILLING_ENTITIES, effectiveBillingEntity } from '../utils/documentTailoring';

interface Props {
  value: string;
  companyEntity?: string;
  onChange: (value: string) => void;
}

/** Document-local issuer selection never changes the customer record or currency. */
const DocumentIssuerField: React.FC<Props> = ({ value, companyEntity, onChange }) => {
  const effective = effectiveBillingEntity(value, companyEntity);
  return (
    <TextField
      select
      fullWidth
      label="Issued by (this document)"
      value={value}
      onChange={event => onChange(event.target.value)}
      helperText={`Issuer: ${effective || 'select an entity; company has no default'}. Independent of currency and customer country; does not change the company record.`}
    >
      <MenuItem value="">Use company billing entity</MenuItem>
      {DOCUMENT_BILLING_ENTITIES.map(entity => (
        <MenuItem key={entity} value={entity}>{entity}</MenuItem>
      ))}
    </TextField>
  );
};

export default DocumentIssuerField;
