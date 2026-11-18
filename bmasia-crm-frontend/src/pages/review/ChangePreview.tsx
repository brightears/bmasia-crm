import React from 'react';
import { Box, Chip, Table, TableBody, TableCell, TableHead, TableRow, Tooltip, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { WarningAmberOutlined } from '@mui/icons-material';
import type { ChangeProposal } from '../../services/reviewApi';
import PlainText from './PlainText';
import { displayValue, fieldLabel, fieldWarnings, formatDateTime } from './reviewModel';

const Empty: React.FC = () => (
  <Typography component="span" variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
    empty
  </Typography>
);

export const ValueWarnings: React.FC<{ proposal: ChangeProposal; field: string; value: string }> = ({
  proposal,
  field,
  value,
}) => {
  const warnings = fieldWarnings(proposal, field, value);
  if (!warnings.length) return null;
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
      {warnings.includes('mixed_script') && (
        <Tooltip title={'Letters from different alphabets that look alike (for example a Latin a and a Cyrillic \u0430). The value may not be what it seems.'}>
          <Chip size="small" color="warning" icon={<WarningAmberOutlined />} label="Mixed alphabets" />
        </Tooltip>
      )}
      {warnings.includes('invisible') && (
        <Tooltip title="Contains invisible or direction-changing characters, shown as U+ markers.">
          <Chip size="small" color="warning" icon={<WarningAmberOutlined />} label="Hidden characters" />
        </Tooltip>
      )}
    </Box>
  );
};

const Proposed: React.FC<{ value: string; multiline?: boolean; testId?: string }> = ({ value, multiline, testId }) => (
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
    {value ? <PlainText value={value} multiline={multiline} /> : <Empty />}
  </Box>
);

interface ChangePreviewProps {
  proposal: ChangeProposal;
  /** Names for linked contacts, by id. */
  contactNames?: Record<string, string>;
}

/** What would change: before → after for updates, the new record's fields, or the note text to add. */
const ChangePreview: React.FC<ChangePreviewProps> = ({ proposal: p, contactNames = {} }) => {
  const entries = Object.entries(p.patch || {});
  const asOf = p.target_changed_at
    ? `again on ${formatDateTime(p.target_changed_at)}`
    : `when the suggestion was made, ${formatDateTime(p.created_at)}`;

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
          <PlainText value={text} multiline clampAt={1200} />
        </Box>
        <ValueWarnings proposal={p} field="notes" value={text} />
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
          Added below the existing notes, which stay as they are.
          {existing ? ` Existing notes, as read ${asOf}:` : ' There are no notes yet.'}
        </Typography>
        {existing && (
          <Box sx={{ mt: 0.5, color: 'text.secondary', fontSize: '0.875rem' }}>
            <PlainText value={existing} multiline clampAt={240} />
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
              const linkedName = key === 'related_contact' && text ? contactNames[text] : undefined;
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
                    <Proposed
                      value={linkedName ? `${linkedName} (${text})` : text}
                      multiline={key === 'notes' || key === 'description'}
                    />
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
            <TableCell sx={{ width: { xs: '36%', sm: '38%' } }}>{p.status === 'proposed' ? 'Now' : 'Before'}</TableCell>
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
                      <PlainText value={before} />
                    </Box>
                  ) : (
                    <Empty />
                  )}
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
        {p.status === 'proposed' ? 'Current' : 'Earlier'} values as read {asOf}.
      </Typography>
    </Box>
  );
};

export default ChangePreview;
