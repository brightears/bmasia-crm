import React from 'react';
import { Box, Chip, Link, Tooltip, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { MarkEmailReadOutlined, EditNoteOutlined, ReportGmailerrorredOutlined, OpenInNew } from '@mui/icons-material';
import type { ChangeProposal, EvidenceState } from '../../services/reviewApi';
import PlainText from './PlainText';
import { TextChecks } from './ChangePreview';
import { EVIDENCE_HELP, EVIDENCE_LABEL, SOURCE_LABEL, VIA_LABEL, describeLink, formatDateTime } from './reviewModel';

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

/**
 * The source link with its destination printed next to it (the part that names the owner in bold).
 * An unusual address is never a link: it is shown as text with the reason.
 */
export const SourceLink: React.FC<{ url: string }> = ({ url }) => {
  const info = describeLink(url);
  if (!info) return null;
  if (!info.href) {
    return (
      <Box component="span" sx={{ display: 'block', mt: 0.25 }} data-testid="source-link-refused">
        <PlainText value={url} clampAt={120} sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }} />{' '}
        <Box component="span" sx={{ color: 'warning.main', fontWeight: 600 }}>
          Link not shown: unusual address ({info.refused}).
        </Box>
      </Box>
    );
  }
  return (
    <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
      <Link
        href={info.href}
        target="_blank"
        rel="noopener noreferrer"
        underline="hover"
        sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.25 }}
      >
        {info.label} <OpenInNew sx={{ fontSize: 13 }} />
      </Link>
      <Box component="span" data-testid="source-host" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
        {info.prefix}
        <Box component="strong" sx={{ color: 'text.primary' }}>
          {info.registrable}
        </Box>
      </Box>
    </Box>
  );
};

/** The quotation the suggestion rests on, where it came from, and how far it was checked. */
const EvidenceBlock: React.FC<{ proposal: ChangeProposal; compact?: boolean }> = ({ proposal: p, compact = false }) => {
  const facts: React.ReactNode[] = [];
  if (p.evidence_source_system) {
    facts.push(`stated source: ${SOURCE_LABEL[p.evidence_source_system] || p.evidence_source_system}`);
  }
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
        <>
          <Box
            component="blockquote"
            data-testid="evidence-quote"
            sx={(theme) => ({
              m: 0,
              p: compact ? 1 : 1.5,
              borderLeft: 3,
              borderColor:
                p.evidence === 'verified_captured'
                  ? 'success.main'
                  : p.evidence === 'unverified'
                    ? 'warning.main'
                    : 'divider',
              bgcolor: alpha(theme.palette.text.primary, theme.palette.mode === 'dark' ? 0.06 : 0.03),
              borderRadius: '0 6px 6px 0',
              fontSize: compact ? '0.875rem' : '0.9375rem',
            })}
          >
            <PlainText value={p.evidence_quote} clampAt={compact ? 300 : 600} />
          </Box>
          <TextChecks value={p.evidence_quote} only={['invisible', 'direction', 'lookalike']} />
        </>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
          No quote was given.
        </Typography>
      )}
      {!compact && (facts.length > 0 || p.evidence_source_url || p.evidence_source_ref) && (
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.75 }}>
          {facts.map((fact, i) => (
            <React.Fragment key={i}>
              {i > 0 && ' · '}
              {fact}
            </React.Fragment>
          ))}
          {p.evidence_source_url && (
            <Box component="span" sx={{ display: 'block', mt: 0.25 }}>
              <SourceLink url={p.evidence_source_url} />
            </Box>
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
