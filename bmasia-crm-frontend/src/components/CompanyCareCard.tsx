import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { SupportAgent } from '@mui/icons-material';
import { CareTouch, CareTouchOutcome, Company } from '../types';
import ApiService from '../services/api';
import { SectionCard, EmptyState } from './ui';
import { formatDate, humanize } from '../theme';

const OUTCOME_COLOR: Record<CareTouchOutcome, 'default' | 'success' | 'info' | 'warning' | 'error'> = {
  none: 'default',
  all_good: 'success',
  request: 'info',
  issue: 'warning',
  handed_off: 'info',
  bounced: 'error',
  unsubscribe_request: 'warning',
};

interface CompanyCareCardProps {
  company: Company;
}

/**
 * Client care: the care summary and the latest care touches for one company.
 * Read-only. Both are written by Cara through its own endpoints, not on the website.
 */
const CompanyCareCard: React.FC<CompanyCareCardProps> = ({ company }) => {
  const [touches, setTouches] = useState<CareTouch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    ApiService.getCompanyCareTouches(company.id)
      .then((rows) => {
        if (!cancelled) setTouches(rows);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load care touches.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [company.id]);

  const summary = (company.care_summary || '').trim();

  return (
    <SectionCard title="Client care" subtitle="Written by Cara; read-only here">
      <Box sx={{ display: 'grid', gap: 2 }}>
        <Box>
          <Typography variant="overline" color="text.secondary">
            Care summary
          </Typography>
          {summary ? (
            <>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {company.care_summary}
              </Typography>
              {company.care_summary_updated_at && (
                <Typography variant="caption" color="text.secondary">
                  Updated {formatDate(company.care_summary_updated_at)}
                  {company.care_summary_updated_by ? ` by ${company.care_summary_updated_by}` : ''}
                </Typography>
              )}
            </>
          ) : (
            <Typography variant="body2" color="text.secondary">
              No care summary yet.
            </Typography>
          )}
        </Box>

        <Box>
          <Typography variant="overline" color="text.secondary">
            Latest touches
          </Typography>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
              <CircularProgress size={24} />
            </Box>
          ) : error ? (
            <Alert severity="warning">{error}</Alert>
          ) : touches.length === 0 ? (
            <EmptyState compact icon={<SupportAgent />} title="No care touches recorded yet" />
          ) : (
            <TableContainer>
              <Table size="small" aria-label="Latest care touches">
                <TableHead>
                  <TableRow>
                    <TableCell>Date</TableCell>
                    <TableCell>Kind</TableCell>
                    <TableCell>Outcome</TableCell>
                    <TableCell>Summary</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {touches.map((touch) => (
                    <TableRow key={touch.id}>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDate(touch.occurred_at)}</TableCell>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{humanize(touch.kind)}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={humanize(touch.outcome)}
                          color={OUTCOME_COLOR[touch.outcome] || 'default'}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>{touch.summary || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      </Box>
    </SectionCard>
  );
};

export default CompanyCareCard;
