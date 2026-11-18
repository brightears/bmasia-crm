import React from 'react';
import { Box, Chip, Link, Tooltip, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { MarkEmailReadOutlined, EditNoteOutlined, ReportGmailerrorredOutlined, OpenInNew } from '@mui/icons-material';
import type { ChangeProposal, EvidenceState } from '../../services/reviewApi';
import PlainText from './PlainText';
import { EVIDENCE_HELP, EVIDENCE_LABEL, SOURCE_LABEL, VIA_LABEL, formatDateTime, safeHttpUrl } from './reviewModel';

export const EvidenceBadge: React.FC<{ state: EvidenceState }> = ({ state }) => {
  const label = EVIDENCE_LABEL[state] || EVIDENCE_LABEL.unverified;
  const help = EVIDENCE_HELP[state] || EVIDENCE_HELP.unverified;
  if (state === 'verified_captured') {
    return (
      <Tooltip title={help}>
        <Chip size="small" color="success" icon={<MarkEmailReadOutlined />} label={label} data-evidence={state} />
      </Tooltip>
    );
  }
  if (state === 'verified_agent_recorded') {
    return (
      <Tooltip title={help}>
        <Chip size="small" variant="outlined" icon={<EditNoteOutlined />} label={label} data-evidence={state} />
      </Tooltip>
    );
  }
  return (
    <Tooltip title={help}>
      <Chip
        size="small"
        color="warning"
        icon={<ReportGmailerrorredOutlined />}
        label={label}
        data-evidence="unverified"
      />
    </Tooltip>
  );
};

/** The quotation the suggestion rests on, where it came from, and how far it was checked. */
const EvidenceBlock: React.FC<{ proposal: ChangeProposal }> = ({ proposal: p }) => {
  const url = safeHttpUrl(p.evidence_source_url);
  const facts: React.ReactNode[] = [];
  if (p.evidence_source_system) facts.push(SOURCE_LABEL[p.evidence_source_system] || p.evidence_source_system);
  if (p.evidence_recorded_by) {
    facts.push(
      <>
        recorded by <PlainText value={p.evidence_recorded_by} />
        {p.evidence_recorded_via ? ` via ${VIA_LABEL[p.evidence_recorded_via] || p.evidence_recorded_via}` : ''}
      </>,
    );
  }
  if (p.evidence_occurred_at) facts.push(`source dated ${formatDateTime(p.evidence_occurred_at)}`);

  return (
    <Box component="section" aria-label="Evidence">
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 1 }}>
        <Typography variant="overline" color="text.secondary" sx={{ lineHeight: 1.6 }}>
          Evidence
        </Typography>
        <EvidenceBadge state={p.evidence} />
      </Box>
      {p.evidence_quote ? (
        <Box
          component="blockquote"
          data-testid="evidence-quote"
          sx={(theme) => ({
            m: 0,
            p: 1.5,
            borderLeft: 3,
            borderColor:
              p.evidence === 'verified_captured'
                ? 'success.main'
                : p.evidence === 'unverified'
                  ? 'warning.main'
                  : 'divider',
            bgcolor: alpha(theme.palette.text.primary, theme.palette.mode === 'dark' ? 0.06 : 0.03),
            borderRadius: '0 6px 6px 0',
            fontSize: '0.9375rem',
          })}
        >
          <PlainText value={p.evidence_quote} multiline clampAt={600} />
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
          No quote was given.
        </Typography>
      )}
      {(facts.length > 0 || url || p.evidence_source_ref) && (
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.75 }}>
          {facts.map((fact, i) => (
            <React.Fragment key={i}>
              {i > 0 && ' · '}
              {fact}
            </React.Fragment>
          ))}
          {url && (
            <>
              {facts.length > 0 && ' · '}
              <Link
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                underline="hover"
                sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.25 }}
              >
                Open source <OpenInNew sx={{ fontSize: 13 }} />
              </Link>
            </>
          )}
          {p.evidence_source_ref && (
            <Box component="span" sx={{ display: 'block', mt: 0.25 }}>
              Reference:{' '}
              <PlainText value={p.evidence_source_ref} sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }} />
            </Box>
          )}
        </Typography>
      )}
    </Box>
  );
};

export default EvidenceBlock;
