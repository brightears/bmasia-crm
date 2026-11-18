import React, { useMemo, useState } from 'react';
import { Alert, Box, Button, Checkbox, FormControlLabel, MenuItem, TextField, Typography } from '@mui/material';
import type { ChangeProposal, PatchValue } from '../../services/reviewApi';
import PlainText from './PlainText';
import { REQUIRED_FIELDS, displayValue, fieldLabel, fieldRule, validateValue } from './reviewModel';

interface EditFormProps {
  proposal: ChangeProposal;
  /** Fields the allowlist lets this kind change; null when unknown (then every proposed field). */
  editable: string[] | null;
  busy: boolean;
  /** Server-side errors from the last attempt, by field. */
  serverErrors?: Record<string, string>;
  onSubmit: (edits: Record<string, PatchValue>, dropFields: string[]) => void;
  onCancel: () => void;
}

/**
 * Edit then accept: change or drop the proposed values. Only fields in the proposal can be edited
 * (the API refuses anything else), and only those the allowlist still permits.
 */
const EditForm: React.FC<EditFormProps> = ({ proposal: p, editable, busy, serverErrors = {}, onSubmit, onCancel }) => {
  const keys = Object.keys(p.patch || {});
  const original = useMemo(
    () => Object.fromEntries(keys.map((k) => [k, displayValue(p.patch[k])])) as Record<string, string>,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [p.id, p.seen_version],
  );
  const notAllowed = keys.filter((k) => editable && !editable.includes(k));
  const [values, setValues] = useState<Record<string, string>>(original);
  const [dropped, setDropped] = useState<string[]>(notAllowed);
  const [submitted, setSubmitted] = useState(false);
  const required = REQUIRED_FIELDS[p.kind] || [];

  const errors: Record<string, string> = {};
  keys.forEach((k) => {
    if (dropped.includes(k)) return;
    const message = validateValue(p.target_collection, k, values[k] ?? '');
    if (message) errors[k] = message;
    else if (required.includes(k) && !(values[k] || '').trim()) errors[k] = 'Required.';
  });
  const edits: Record<string, PatchValue> = {};
  keys.forEach((k) => {
    if (!dropped.includes(k) && values[k] !== original[k]) edits[k] = values[k];
  });
  const remaining = keys.filter((k) => !dropped.includes(k));
  const nothingChanged = Object.keys(edits).length === 0 && dropped.length === 0;
  const nothingLeft = remaining.length === 0;
  const blocked = Object.keys(errors).length > 0 || nothingChanged || nothingLeft;

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitted(true);
    if (blocked || busy) return;
    onSubmit(edits, dropped);
  };

  return (
    <Box
      component="form"
      onSubmit={submit}
      noValidate
      aria-label="Edit the suggestion"
      sx={{ display: 'grid', gap: 2 }}
    >
      {keys.map((k) => {
        const rule = fieldRule(p.target_collection, k);
        const isDropped = dropped.includes(k);
        const locked = notAllowed.includes(k);
        const error =
          (submitted || values[k] !== original[k]) && !isDropped ? errors[k] || serverErrors[k] : serverErrors[k];
        const helper = locked
          ? 'No longer allowed to be changed by a suggestion, so it is dropped.'
          : error || rule.hint || (rule.maxLength ? `Up to ${rule.maxLength} characters.` : undefined);
        const currentValue = displayValue(p.current_values?.[k]);
        return (
          <Box key={k} sx={{ opacity: isDropped ? 0.55 : 1 }}>
            {rule.kind === 'choice' ? (
              <TextField
                select
                fullWidth
                size="small"
                label={fieldLabel(k)}
                value={values[k] ?? ''}
                disabled={isDropped || busy}
                error={Boolean(error)}
                helperText={helper}
                onChange={(e) => setValues((v) => ({ ...v, [k]: e.target.value }))}
              >
                <MenuItem value="">
                  <em>Empty</em>
                </MenuItem>
                {(rule.choices || []).map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </TextField>
            ) : (
              <TextField
                fullWidth
                size="small"
                label={fieldLabel(k)}
                value={values[k] ?? ''}
                multiline={rule.multiline}
                minRows={rule.multiline ? 3 : undefined}
                maxRows={rule.multiline ? 12 : undefined}
                disabled={isDropped || busy}
                error={Boolean(error)}
                helperText={helper}
                inputProps={{ spellCheck: rule.kind ? false : undefined }}
                onChange={(e) => setValues((v) => ({ ...v, [k]: e.target.value }))}
              />
            )}
            <Box
              sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}
            >
              {p.kind === 'field_update' ? (
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 0 }}>
                  Now: {currentValue ? <PlainText value={currentValue} clampAt={120} /> : <em>empty</em>}
                </Typography>
              ) : (
                <span />
              )}
              <FormControlLabel
                sx={{ mr: 0 }}
                control={
                  <Checkbox
                    size="small"
                    checked={isDropped}
                    disabled={busy || locked || required.includes(k)}
                    onChange={(e) => setDropped((d) => (e.target.checked ? [...d, k] : d.filter((x) => x !== k)))}
                  />
                }
                label={<Typography variant="caption">{required.includes(k) ? 'Required' : 'Leave out'}</Typography>}
              />
            </Box>
          </Box>
        );
      })}
      {submitted && nothingChanged && (
        <Alert severity="info" variant="outlined">
          Nothing was changed. Use Accept to take the suggestion as it is, or change a value.
        </Alert>
      )}
      {submitted && nothingLeft && (
        <Alert severity="warning" variant="outlined">
          Every field is left out, so nothing would be applied. Reject the suggestion instead.
        </Alert>
      )}
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <Button type="submit" variant="contained" disabled={busy}>
          {busy ? 'Saving…' : 'Accept with edits'}
        </Button>
        <Button onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </Box>
    </Box>
  );
};

export default EditForm;
