import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Link,
  MenuItem,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { CheckCircle, Cancel, TravelExploreOutlined } from '@mui/icons-material';
import { Link as RouterLink } from 'react-router-dom';
import { ResearchLead } from '../types';
import ApiService from '../services/api';
import { logApiError } from '../utils/logApiError';

type LeadStatus = ResearchLead['status'] | '';

const STATUS_TABS: { value: LeadStatus; label: string }[] = [
  { value: 'new', label: 'To review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: '', label: 'All' },
];

const REJECT_REASONS = [
  'Too small',
  'Wrong segment',
  'Already a client or in talks',
  'Not real or out of date',
  'Outside our markets',
  'Other',
];

function scoreColor(score: number): 'success' | 'warning' | 'default' {
  if (score >= 75) return 'success';
  if (score >= 50) return 'warning';
  return 'default';
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

const ResearchLeads: React.FC = () => {
  const [status, setStatus] = useState<LeadStatus>('new');
  const [leads, setLeads] = useState<ResearchLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [products, setProducts] = useState<Record<string, ResearchLead['suggested_product']>>({});
  const [rejecting, setRejecting] = useState<ResearchLead | null>(null);
  const [rejectReason, setRejectReason] = useState(REJECT_REASONS[0]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { page_size: 100 };
      if (status) params.status = status;
      const data = await ApiService.getResearchLeads(params);
      setLeads(Array.isArray(data) ? data : data.results);
    } catch (err) {
      logApiError('Failed to load research leads', err);
      setError('Could not load research leads.');
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  const approve = async (lead: ResearchLead) => {
    setBusyId(lead.id);
    try {
      const product = products[lead.id] || lead.suggested_product;
      const result = await ApiService.approveResearchLead(lead.id, { service_type: product });
      setToast(
        result.sequence_enrollment_requested
          ? `${lead.venue_name} added. Its first outreach email will wait in AI email drafts for your approval.`
          : `${lead.venue_name} added with a task to find the decision maker (no public email was found).`
      );
      await load();
    } catch (err) {
      logApiError('Approve research lead failed', err);
      setToast('Could not approve this lead.');
    } finally {
      setBusyId(null);
    }
  };

  const confirmReject = async () => {
    if (!rejecting) return;
    setBusyId(rejecting.id);
    try {
      await ApiService.rejectResearchLead(rejecting.id, rejectReason);
      setToast(`${rejecting.venue_name} rejected.`);
      setRejecting(null);
      await load();
    } catch (err) {
      logApiError('Reject research lead failed', err);
      setToast('Could not reject this lead.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1 }}>
        <TravelExploreOutlined color="primary" />
        <Typography variant="h5">AI lead research</Typography>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2, maxWidth: 820 }}>
        Each week Claude searches the news for hotel openings, retail launches and QSR expansions in our markets.
        Approving a lead creates the company and an opportunity. If a public business email was found, the lead
        enters your prospect sequences, and every email still waits in AI email drafts for your approval.
      </Typography>

      <Tabs value={status} onChange={(_, v) => setStatus(v)} sx={{ mb: 2 }}>
        {STATUS_TABS.map((t) => (
          <Tab key={t.label} value={t.value} label={t.label} />
        ))}
      </Tabs>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </Box>
      ) : leads.length === 0 ? (
        <Alert severity="info">
          {status === 'new' ? 'No leads waiting for review.' : 'No leads here yet.'}
        </Alert>
      ) : (
        <Stack spacing={2}>
          {leads.map((lead) => (
            <Card key={lead.id} variant="outlined">
              <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
                  <Typography variant="h6" sx={{ mr: 1 }}>{lead.venue_name}</Typography>
                  <Chip size="small" label={`Fit ${lead.score}`} color={scoreColor(lead.score)} />
                  <Chip size="small" label={lead.segment_display} variant="outlined" />
                  <Chip size="small" label={[lead.city, lead.country].filter(Boolean).join(', ')} variant="outlined" />
                  {lead.opening_timeframe && <Chip size="small" label={lead.opening_timeframe} variant="outlined" />}
                  {lead.estimated_zones && <Chip size="small" label={`~${lead.estimated_zones} zones`} variant="outlined" />}
                  {lead.status !== 'new' && (
                    <Chip size="small" label={lead.status} color={lead.status === 'approved' ? 'success' : 'default'} />
                  )}
                </Stack>
                {lead.brand_or_group && (
                  <Typography variant="body2" color="text.secondary">{lead.brand_or_group}</Typography>
                )}
                <Typography variant="body1" sx={{ mt: 1 }}>{lead.signal}</Typography>
                {lead.fit_reason && (
                  <Typography variant="body2" sx={{ mt: 1 }}><strong>Why it fits:</strong> {lead.fit_reason}</Typography>
                )}
                {lead.personal_hook && (
                  <Typography variant="body2" sx={{ mt: 0.5 }}><strong>Opening hook:</strong> {lead.personal_hook}</Typography>
                )}
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  <strong>Contact:</strong>{' '}
                  {[lead.decision_maker_name, lead.decision_maker_title].filter(Boolean).join(', ') || 'No named decision maker'}
                  {' · '}
                  {lead.contact_email || 'no public email'}
                </Typography>
                {lead.matched_company_name && lead.status === 'new' && (
                  <Alert severity="info" sx={{ mt: 1 }}>
                    Matches existing company {lead.matched_company_name}; approving adds an opportunity there.
                  </Alert>
                )}
                <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                  {lead.source_urls.map((url) => (
                    <Link key={url} href={url} target="_blank" rel="noopener noreferrer" variant="body2">
                      {hostname(url)}
                    </Link>
                  ))}
                  {lead.website && (
                    <Link href={lead.website} target="_blank" rel="noopener noreferrer" variant="body2">Website</Link>
                  )}
                </Stack>
                {lead.status === 'approved' && lead.opportunity && (
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    Opportunity:{' '}
                    <Link component={RouterLink} to={`/opportunities?highlight=${lead.opportunity}`}>
                      {lead.opportunity_name}
                    </Link>
                    {lead.reviewed_by_name ? ` · approved by ${lead.reviewed_by_name}` : ''}
                  </Typography>
                )}
                {lead.status === 'rejected' && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Rejected{lead.rejection_reason ? `: ${lead.rejection_reason}` : ''}
                    {lead.reviewed_by_name ? ` · by ${lead.reviewed_by_name}` : ''}
                  </Typography>
                )}
              </CardContent>
              {lead.status === 'new' && (
                <CardActions sx={{ px: 2, pb: 2, gap: 1, flexWrap: 'wrap' }}>
                  <TextField
                    select
                    size="small"
                    label="Product"
                    value={products[lead.id] || lead.suggested_product}
                    onChange={(e) =>
                      setProducts((p) => ({ ...p, [lead.id]: e.target.value as ResearchLead['suggested_product'] }))
                    }
                    sx={{ minWidth: 160 }}
                  >
                    <MenuItem value="beatbreeze">Beat Breeze</MenuItem>
                    <MenuItem value="soundtrack">Soundtrack</MenuItem>
                  </TextField>
                  <Button
                    variant="contained"
                    startIcon={<CheckCircle />}
                    disabled={busyId === lead.id}
                    onClick={() => approve(lead)}
                  >
                    Approve
                  </Button>
                  <Button
                    color="inherit"
                    startIcon={<Cancel />}
                    disabled={busyId === lead.id}
                    onClick={() => {
                      setRejectReason(REJECT_REASONS[0]);
                      setRejecting(lead);
                    }}
                  >
                    Reject
                  </Button>
                </CardActions>
              )}
            </Card>
          ))}
        </Stack>
      )}

      <Dialog open={Boolean(rejecting)} onClose={() => setRejecting(null)} fullWidth maxWidth="xs">
        <DialogTitle>Reject {rejecting?.venue_name}?</DialogTitle>
        <DialogContent>
          <TextField
            select
            fullWidth
            label="Reason"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            sx={{ mt: 1 }}
          >
            {REJECT_REASONS.map((r) => (
              <MenuItem key={r} value={r}>{r}</MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejecting(null)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={confirmReject} disabled={busyId === rejecting?.id}>
            Reject
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={Boolean(toast)} autoHideDuration={6000} onClose={() => setToast(null)} message={toast || ''} />
    </Box>
  );
};

export default ResearchLeads;
