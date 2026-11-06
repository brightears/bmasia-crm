import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  GridLegacy as Grid,
  IconButton,
  InputLabel,
  Menu,
  MenuItem,
  Paper,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import { Add, Delete } from '@mui/icons-material';
import {
  AddendumAddress,
  AddendumChange,
  Contract,
  ContractAddendum,
  ContractAddendumInput,
} from '../types';
import ApiService from '../services/api';

interface ContractAddendumFormProps {
  open: boolean;
  contract: Contract;
  addendum?: ContractAddendum | null;
  onClose: () => void;
  onSaved: (addendum: ContractAddendum) => void;
}

const CHANGE_LABELS: Record<AddendumChange['type'], string> = {
  zone_add: 'Add a zone',
  zone_remove: 'Remove a zone',
  dates: 'Change contract dates',
  party: 'Change client name or address',
  clause: 'Add or replace a clause',
  bank_details: 'Add our bank details',
};

const ADDRESS_FIELDS: { key: keyof AddendumAddress; label: string }[] = [
  { key: 'address_line1', label: 'Address line 1' },
  { key: 'address_line2', label: 'Address line 2' },
  { key: 'city', label: 'City' },
  { key: 'state', label: 'State / province' },
  { key: 'postal_code', label: 'Postal code' },
  { key: 'country', label: 'Country' },
];

const today = () => new Date().toISOString().slice(0, 10);

const blankChange = (type: AddendumChange['type']): AddendumChange => {
  switch (type) {
    case 'zone_add':
      return { type, name: '', platform: 'soundtrack', price: '', annual_price: '' };
    case 'zone_remove':
      return { type, service_location_id: '', credit: '0' };
    case 'dates':
      return { type, start_date: '', end_date: '' };
    case 'party':
      return { type, legal_name: '', address: null };
    case 'clause':
      return { type, action: 'add', clause_ref: '', text: '' };
    default:
      return { type: 'bank_details', text: '' };
  }
};

/** Strip the CRM-filled display fields and empty optionals before sending. */
const toPayload = (change: AddendumChange): AddendumChange => {
  switch (change.type) {
    case 'zone_add':
      return { ...change, annual_price: change.annual_price || null, start_date: change.start_date || undefined };
    case 'zone_remove':
      return { type: change.type, service_location_id: change.service_location_id, credit: change.credit };
    case 'dates':
      return { type: change.type, start_date: change.start_date || null, end_date: change.end_date || null };
    case 'party':
      return { type: change.type, legal_name: change.legal_name || null, address: change.address || null };
    case 'bank_details':
      return { type: change.type, text: change.text || '' };
    default:
      return change;
  }
};

const apiError = (err: any): { message: string; perChange: Record<string, string> } => {
  const data = err?.response?.data || {};
  return {
    message: data.error || data.detail || 'Could not save the addendum.',
    perChange: data.details?.changes || {},
  };
};

const ContractAddendumForm: React.FC<ContractAddendumFormProps> = ({
  open, contract, addendum, onClose, onSaved,
}) => {
  const [effectiveDate, setEffectiveDate] = useState(today());
  const [changes, setChanges] = useState<AddendumChange[]>([]);
  const [signatories, setSignatories] = useState({
    customer_signatory_name: '', customer_signatory_title: '',
    bmasia_signatory_name: '', bmasia_signatory_title: '',
  });
  const [notes, setNotes] = useState('');
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [changeErrors, setChangeErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) return;
    setEffectiveDate(addendum?.effective_date || today());
    setChanges(addendum ? addendum.changes.map((change) => ({ ...change })) : []);
    setSignatories({
      customer_signatory_name: addendum?.customer_signatory_name || '',
      customer_signatory_title: addendum?.customer_signatory_title || '',
      bmasia_signatory_name: addendum?.bmasia_signatory_name || '',
      bmasia_signatory_title: addendum?.bmasia_signatory_title || '',
    });
    setNotes(addendum?.notes || '');
    setError('');
    setChangeErrors({});
  }, [open, addendum]);

  const usedSingles = new Set(changes.filter((c) => ['dates', 'party', 'bank_details'].includes(c.type)).map((c) => c.type));
  const zones = contract.service_locations || [];

  const updateChange = (index: number, patch: Partial<AddendumChange>) => {
    setChanges((current) => current.map((change, i) => (i === index ? ({ ...change, ...patch } as AddendumChange) : change)));
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setChangeErrors({});
    const payload: ContractAddendumInput = {
      effective_date: effectiveDate,
      changes: changes.map(toPayload),
      ...signatories,
      notes,
    };
    try {
      const saved = addendum
        ? await ApiService.updateContractAddendum(addendum.id, payload, addendum.version)
        : await ApiService.createContractAddendum(contract.id, payload);
      onSaved(saved);
    } catch (err: any) {
      const parsed = apiError(err);
      setError(parsed.message);
      setChangeErrors(parsed.perChange);
    } finally {
      setSaving(false);
    }
  };

  const renderChange = (change: AddendumChange, index: number) => {
    switch (change.type) {
      case 'zone_add':
        return (
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label="Zone name" value={change.name}
                onChange={(e) => updateChange(index, { name: e.target.value })} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Service</InputLabel>
                <Select label="Service" value={change.platform}
                  onChange={(e) => updateChange(index, { platform: e.target.value as any })}>
                  <MenuItem value="soundtrack">Soundtrack Your Brand</MenuItem>
                  <MenuItem value="beatbreeze">Beat Breeze</MenuItem>
                  <MenuItem value="custom">Custom</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            {change.platform === 'custom' && (
              <Grid item xs={12}>
                <TextField fullWidth size="small" label="Custom service name" value={change.custom_service_name || ''}
                  onChange={(e) => updateChange(index, { custom_service_name: e.target.value })} />
              </Grid>
            )}
            <Grid item xs={12} sm={4}>
              <TextField fullWidth size="small" type="number" label={`Amount charged (${contract.currency})`}
                value={change.price} helperText="Added to the contract value when signed"
                onChange={(e) => updateChange(index, { price: e.target.value })} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField fullWidth size="small" type="number" label="Yearly rate (optional)"
                value={change.annual_price || ''} helperText="Printed as the per-zone yearly price"
                onChange={(e) => updateChange(index, { annual_price: e.target.value })} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField fullWidth size="small" type="date" label="Zone starts" InputLabelProps={{ shrink: true }}
                value={change.start_date || ''} helperText="Blank uses the effective date"
                onChange={(e) => updateChange(index, { start_date: e.target.value })} />
            </Grid>
          </Grid>
        );
      case 'zone_remove':
        return (
          <Grid container spacing={2}>
            <Grid item xs={12} sm={8}>
              <FormControl fullWidth size="small">
                <InputLabel>Zone to remove</InputLabel>
                <Select label="Zone to remove" value={change.service_location_id}
                  onChange={(e) => updateChange(index, { service_location_id: e.target.value as string })}>
                  {zones.map((zone) => (
                    <MenuItem key={zone.id} value={zone.id}>
                      {zone.location_name}{zone.price ? ` (${contract.currency} ${zone.price})` : ''}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField fullWidth size="small" type="number" label={`Credit (${contract.currency})`}
                value={change.credit} helperText="Deducted from the contract value"
                onChange={(e) => updateChange(index, { credit: e.target.value })} />
            </Grid>
          </Grid>
        );
      case 'dates':
        return (
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" type="date" label="New start date" InputLabelProps={{ shrink: true }}
                value={change.start_date || ''} helperText={`Now ${contract.start_date || 'not set'}`}
                onChange={(e) => updateChange(index, { start_date: e.target.value })} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" type="date" label="New end date" InputLabelProps={{ shrink: true }}
                value={change.end_date || ''} helperText={`Now ${contract.end_date || 'not set'}`}
                onChange={(e) => updateChange(index, { end_date: e.target.value })} />
            </Grid>
          </Grid>
        );
      case 'party':
        return (
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField fullWidth size="small" label="New legal name (blank keeps the current one)"
                value={change.legal_name || ''}
                onChange={(e) => updateChange(index, { legal_name: e.target.value })} />
            </Grid>
            {ADDRESS_FIELDS.map(({ key, label }) => (
              <Grid item xs={12} sm={6} key={key}>
                <TextField fullWidth size="small" label={`New ${label.toLowerCase()}`}
                  value={change.address?.[key] || ''}
                  onChange={(e) => updateChange(index, { address: { ...(change.address || {}), [key]: e.target.value } })} />
              </Grid>
            ))}
            <Grid item xs={12}>
              <Typography variant="caption" color="text.secondary">
                Filling any address field replaces the whole address. Applied to the company when the addendum is signed.
              </Typography>
            </Grid>
          </Grid>
        );
      case 'clause':
        return (
          <Grid container spacing={2}>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small">
                <InputLabel>Clause</InputLabel>
                <Select label="Clause" value={change.action}
                  onChange={(e) => updateChange(index, { action: e.target.value as 'add' | 'replace' })}>
                  <MenuItem value="add">Add a new clause</MenuItem>
                  <MenuItem value="replace">Replace an existing clause</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={8}>
              <TextField fullWidth size="small" value={change.clause_ref || ''}
                label={change.action === 'replace' ? 'Clause being replaced, e.g. Clause 5 Payment' : 'Heading (optional)'}
                onChange={(e) => updateChange(index, { clause_ref: e.target.value })} />
            </Grid>
            <Grid item xs={12}>
              <TextField fullWidth multiline minRows={3} size="small" label="Clause text" value={change.text}
                onChange={(e) => updateChange(index, { text: e.target.value })} />
            </Grid>
          </Grid>
        );
      default:
        return (
          <Box>
            <TextField fullWidth multiline minRows={2} size="small" label="Intro text (optional)" value={change.text || ''}
              placeholder="All payments under the Agreement shall be made by bank transfer to:"
              onChange={(e) => updateChange(index, { text: e.target.value })} />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              {change.account
                ? `${change.beneficiary}, ${change.bank}, SWIFT ${change.swift}, account ${change.account}`
                : 'The CRM fills in the bank details of the issuing BMAsia entity when you save.'}
            </Typography>
          </Box>
        );
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {addendum ? `Edit ${addendum.addendum_number}` : `New addendum to ${contract.contract_number}`}
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Enter only what changes. The parties and all other terms come from {contract.contract_number}.
          Nothing on the contract changes until the addendum is marked Signed.
        </Typography>
        <TextField size="small" type="date" label="Effective date" InputLabelProps={{ shrink: true }}
          value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} sx={{ mb: 2 }} />

        {changes.map((change, index) => (
          <Paper key={index} variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
              <Typography variant="subtitle2">{CHANGE_LABELS[change.type]}</Typography>
              <IconButton size="small" aria-label="Remove this change"
                onClick={() => setChanges((current) => current.filter((_, i) => i !== index))}>
                <Delete fontSize="small" />
              </IconButton>
            </Box>
            {changeErrors[String(index)] && (
              <Alert severity="error" sx={{ mb: 1.5 }}>{changeErrors[String(index)]}</Alert>
            )}
            {renderChange(change, index)}
          </Paper>
        ))}

        <Button startIcon={<Add />} variant="outlined" onClick={(e) => setMenuAnchor(e.currentTarget)}>
          Add change
        </Button>
        <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={() => setMenuAnchor(null)}>
          {(Object.keys(CHANGE_LABELS) as AddendumChange['type'][]).map((type) => (
            <MenuItem key={type} disabled={usedSingles.has(type) || (type === 'zone_remove' && zones.length === 0)}
              onClick={() => { setChanges((current) => [...current, blankChange(type)]); setMenuAnchor(null); }}>
              {CHANGE_LABELS[type]}
            </MenuItem>
          ))}
        </Menu>

        <Divider sx={{ my: 3 }} />
        <Typography variant="subtitle2" sx={{ mb: 1 }}>Signatories (blank uses the contract's)</Typography>
        <Grid container spacing={2}>
          {([
            ['customer_signatory_name', 'Client signatory'],
            ['customer_signatory_title', 'Client signatory title'],
            ['bmasia_signatory_name', 'BMAsia signatory'],
            ['bmasia_signatory_title', 'BMAsia signatory title'],
          ] as const).map(([key, label]) => (
            <Grid item xs={12} sm={6} key={key}>
              <TextField fullWidth size="small" label={label} value={signatories[key]}
                onChange={(e) => setSignatories((current) => ({ ...current, [key]: e.target.value }))} />
            </Grid>
          ))}
          <Grid item xs={12}>
            <TextField fullWidth multiline minRows={2} size="small" label="Internal notes (not printed)"
              value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>Cancel</Button>
        <Button variant="contained" onClick={handleSave} disabled={saving || changes.length === 0}>
          {saving ? 'Saving…' : addendum ? 'Save changes' : 'Create draft addendum'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ContractAddendumForm;
