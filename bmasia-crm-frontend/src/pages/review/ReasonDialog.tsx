import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from '@mui/material';
import { hasInvisible } from './reviewModel';

/** Same limit as the API's DECISION_NOTE_MAX. */
const REASON_MAX = 1000;

interface ReasonDialogProps {
  open: boolean;
  title: string;
  intro?: React.ReactNode;
  label: string;
  confirmLabel: string;
  confirmColor?: 'error' | 'primary';
  quickPicks?: string[];
  /** Text the field starts with (e.g. the reason for keeping another suggestion). */
  initialText?: string;
  busy: boolean;
  onConfirm: (reason: string) => void;
  onClose: () => void;
}

/** Asks for the required reason (reject, bulk reject) or note (reopen). Nothing is sent without one. */
const ReasonDialog: React.FC<ReasonDialogProps> = ({
  open,
  title,
  intro,
  label,
  confirmLabel,
  confirmColor = 'primary',
  quickPicks = [],
  initialText,
  busy,
  onConfirm,
  onClose,
}) => {
  const [text, setText] = useState('');
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (open) {
      setText(initialText || '');
      setTouched(false);
    }
  }, [open, initialText]);

  const trimmed = text.trim();
  const error = !trimmed
    ? 'Required.'
    : trimmed.length > REASON_MAX
      ? `At most ${REASON_MAX} characters.`
      : hasInvisible(trimmed.replace(/\n/g, ''))
        ? 'Remove control or invisible characters.'
        : null;

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setTouched(true);
    if (error || busy) return;
    onConfirm(trimmed);
  };

  return (
    <Dialog
      open={open}
      onClose={busy ? undefined : onClose}
      fullWidth
      maxWidth="sm"
      aria-labelledby="reason-dialog-title"
    >
      <form onSubmit={submit} noValidate>
        <DialogTitle id="reason-dialog-title">{title}</DialogTitle>
        <DialogContent>
          {intro && (
            <Typography variant="body2" color="text.secondary" component="div" sx={{ mb: 2 }}>
              {intro}
            </Typography>
          )}
          {quickPicks.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }} role="group" aria-label="Common reasons">
              {quickPicks.map((pick) => (
                <Chip
                  key={pick}
                  label={pick}
                  clickable
                  variant={trimmed === pick ? 'filled' : 'outlined'}
                  color={trimmed === pick ? 'primary' : 'default'}
                  onClick={() => setText(pick)}
                  disabled={busy}
                />
              ))}
            </Box>
          )}
          <TextField
            autoFocus
            fullWidth
            multiline
            minRows={2}
            label={label}
            value={text}
            onChange={(e) => setText(e.target.value)}
            error={touched && Boolean(error)}
            helperText={touched && error ? error : 'Plain text. Shown in the history of the suggestion.'}
            disabled={busy}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" color={confirmColor} disabled={busy}>
            {busy ? 'Sending…' : confirmLabel}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default ReasonDialog;
