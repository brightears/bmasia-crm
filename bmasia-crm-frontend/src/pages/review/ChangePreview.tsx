import React from 'react';
import { Box, Chip, Table, TableBody, TableCell, TableHead, TableRow, Tooltip, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { WarningAmberOutlined, SwapHorizOutlined, SpaceBarOutlined } from '@mui/icons-material';
import type { ChangeProposal } from '../../services/reviewApi';
import PlainText from './PlainText';
import { ValueWarning, displayValue, fieldLabel, fieldWarnings, formatDateTime, textWarnings } from './reviewModel';

export const Empty: React.FC = () => (
  <Typography component="span" variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
    empty
  </Typography>
);

const CHIP: Record<ValueWarning, { label: string; help: string; warn: boolean }> = {
  lookalike: {
    label: 'Look-alike letters',
    help: 'Letters from different alphabets that look alike (for example a Latin a next to a Cyrillic one). The value may not be what it seems.',
    warn: true,
  },
  direction: {
    label: 'Mixed writing directions',
    help: 'Right-to-left and left-to-right text in one value. It is shown in its own direction, but the order of its parts on screen can differ from how it is stored.',
    warn: false,
  },
  server_mixed: {
    label: 'Mixed scripts (flagged by the server)',
    help: 'The server flagged this value for mixing scripts. Read it carefully.',
    warn: true,
  },
  invisible: {
    label: 'Hidden characters',
    help: 'Contains invisible, direction-changing or tag characters, shown as U+ markers.',
    warn: true,
  },
  spaces: {
    label: 'Contains unusual spaces',
    help: 'Contains a non-breaking or other unusual space, a run of spaces, or a space at the start or end. Markers show where.',
    warn: false,
  },
};

const Chips: React.FC<{ warnings: ValueWarning[] }> = ({ warnings }) =>
  warnings.length ? (
    <Box component="span" sx={{ display: 'inline-flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
      {warnings.map((w) => (
        <Tooltip key={w} title={CHIP[w].help}>
          <Chip
            size="small"
            color={CHIP[w].warn ? 'warning' : 'default'}
            variant={CHIP[w].warn ? 'filled' : 'outlined'}
            icon={
              w === 'direction' ? (
                <SwapHorizOutlined />
              ) : w === 'spaces' ? (
                <SpaceBarOutlined />
              ) : (
                <WarningAmberOutlined />
              )
            }
            label={CHIP[w].label}
            data-warning={w}
          />
        </Tooltip>
      ))}
    </Box>
  ) : null;

export const ValueWarnings: React.FC<{ proposal: ChangeProposal; field: string; value: string }> = ({
  proposal,
  field,
  value,
}) => (
  <Box>
    <Chips warnings={fieldWarnings(proposal, field, value)} />
  </Box>
);

/** Chips for a name or quote shown next to a decision (proposer, company, evidence). */
export const TextChecks: React.FC<{ value: string; only?: ValueWarning[] }> = ({ value, only }) => {
  const warnings = textWarnings(value).filter((w) => !only || only.includes(w));
  return <Chips warnings={warnings} />;
};

const Proposed: React.FC<{ value: string; testId?: string }> = ({ value, testId }) => (
  <Box
    data-testid={testId}
    sx={(theme) => ({
      display: 'inline-block',
      maxWidth: '100%',
      px: 0.75,
      py: 0.25,
      borderRadius: 1,
      bgcolor: alpha(theme.palette.success.main, theme.palette.mode === 'dark' ? 0.22 : 0.1),
      color: 'text.primary',
      fontWeight: 600,
    })}
  >
    {value ? <PlainText value={value} edges /> : <Empty />}
  </Box>
);

interface ChangePreviewProps {
  proposal: ChangeProposal;
  /** Name of a linked contact (task `related_contact`), when known. */
  relatedName?: string;
  /** The backend re-reads current values whenever the record changes (PR 67), so "Now" is true. */
  valuesFollowTarget?: boolean;
}

/** What would change: before → after for updates, the new record's fields, or the note text to add. */
const ChangePreview: React.FC<ChangePreviewProps> = ({ proposal: p, relatedName, valuesFollowTarget = false }) => {
  const entries = Object.entries(p.patch || {});
  const asOf = p.target_changed_at
    ? `again on ${formatDateTime(p.target_changed_at)}`
    : `when the suggestion was made, ${formatDateTime(p.created_at)}`;
  const isNow = Boolean(p.target_changed_at) || valuesFollowTarget;

  if (p.kind === 'note') {
    const text = displayValue(p.patch?.notes);
    const existing = displayValue(p.current_values?.notes);
    return (
      <Box>
        <Typography variant="overline" color="text.secondary">
          Text to add to the notes
        </Typography>
        <Box
          data-testid="note-text"
          sx={(theme) => ({
            p: 1.5,
            borderRadius: 1,
            borderLeft: 3,
            borderColor: 'success.main',
            bgcolor: alpha(theme.palette.success.main, theme.palette.mode === 'dark' ? 0.16 : 0.07),
          })}
        >
          <PlainText value={text} clampAt={1200} edges />
        </Box>
        <ValueWarnings proposal={p} field="notes" value={text} />
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
          Added below the existing notes, which stay as they are.
          {existing ? ` Existing notes, as read ${asOf}:` : ' There are no notes yet.'}
        </Typography>
        {existing && (
          <Box sx={{ mt: 0.5, color: 'text.secondary', fontSize: '0.875rem' }}>
            <PlainText value={existing} clampAt={240} />
          </Box>
        )}
      </Box>
    );
  }

  if (p.kind === 'new_contact' || p.kind === 'task') {
    return (
      <Box>
        <Typography variant="overline" color="text.secondary">
          {p.kind === 'task' ? 'New task with' : 'New contact with'}
        </Typography>
        <Table size="small" aria-label="Fields to be created" sx={{ tableLayout: 'fixed', width: '100%' }}>
          <TableBody>
            {entries.map(([key, value]) => {
              const text = displayValue(value);
              const linkedName = key === 'related_contact' && text ? relatedName : undefined;
              return (
                <TableRow key={key}>
                  <TableCell
                    component="th"
                    scope="row"
                    sx={{ width: { xs: '38%', sm: '30%' }, color: 'text.secondary', verticalAlign: 'top' }}
                  >
                    {fieldLabel(key)}
                  </TableCell>
                  <TableCell sx={{ verticalAlign: 'top' }}>
                    <Proposed value={text} />
                    {linkedName && (
                      <Typography variant="caption" color="text.secondary" component="div">
                        <PlainText value={linkedName} />
                      </Typography>
                    )}
                    <ValueWarnings proposal={p} field={key} value={text} />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Box>
    );
  }

  return (
    <Box>
      <Table size="small" aria-label="Before and after" sx={{ tableLayout: 'fixed', width: '100%' }}>
        <TableHead>
          <TableRow>
            <TableCell sx={{ width: { xs: '28%', sm: '24%' } }}>Field</TableCell>
            <TableCell sx={{ width: { xs: '36%', sm: '38%' } }} data-testid="before-header">
              {p.status !== 'proposed' ? 'Before' : isNow ? 'Now' : 'When suggested'}
            </TableCell>
            <TableCell sx={{ width: { xs: '36%', sm: '38%' } }}>
              {p.status === 'edited' ? 'Applied' : 'Suggested'}
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {entries.map(([key, value]) => {
            const before = displayValue(p.current_values?.[key]);
            const after = displayValue(value);
            return (
              <TableRow key={key} data-testid={`change-row-${key}`}>
                <TableCell component="th" scope="row" sx={{ color: 'text.secondary', verticalAlign: 'top' }}>
                  {fieldLabel(key)}
                </TableCell>
                <TableCell sx={{ verticalAlign: 'top' }}>
                  {before ? (
                    <Box
                      component="span"
                      data-testid={`before-${key}`}
                      sx={{ color: 'text.secondary', textDecoration: 'line-through', textDecorationThickness: '1px' }}
                    >
                      <PlainText value={before} edges />
                    </Box>
                  ) : (
                    <Empty />
                  )}
                  <Chips warnings={textWarnings(before).filter((w) => w === 'spaces' || w === 'invisible')} />
                </TableCell>
                <TableCell sx={{ verticalAlign: 'top' }}>
                  <Proposed value={after} testId={`after-${key}`} />
                  <ValueWarnings proposal={p} field={key} value={after} />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.75 }} data-testid="values-as-of">
        {p.status === 'proposed' && valuesFollowTarget && !p.target_changed_at
          ? 'Current values: the server re-reads them whenever the record changes.'
          : `${p.status === 'proposed' ? 'Current' : 'Earlier'} values as read ${asOf}.`}
        {p.status === 'proposed' && !isNow ? ' The record may have changed since; accepting checks it again.' : ''}
      </Typography>
    </Box>
  );
};

export default ChangePreview;
