import React, { useCallback, useEffect, useState } from 'react';
import DOMPurify from 'dompurify';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Paper,
  Snackbar,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { AutoAwesome, Insights, Search, Send } from '@mui/icons-material';
import ApiService from '../services/api';
import { ChurnInsightReport, WinBackCandidate, WinBackStatus, WinBackSummary } from '../types';

type TabKey = 'review' | 'new' | 'sent' | 'closed' | 'insights';

const TAB_STATUSES: Record<Exclude<TabKey, 'insights'>, WinBackStatus[]> = {
  review: ['pending_review'],
  new: ['identified', 'needs_contact'],
  sent: ['sent', 'replied'],
  closed: ['won_back', 'lost', 'skipped'],
};

const PRODUCTS = [
  { value: 'beatbreeze', label: 'Beat Breeze' },
  { value: 'soundtrack', label: 'Soundtrack Your Brand' },
  { value: 'all', label: 'All products' },
];

const STATUS_COLOR: Record<WinBackStatus, 'default' | 'warning' | 'info' | 'success' | 'error' | 'primary'> = {
  identified: 'default',
  needs_contact: 'error',
  pending_review: 'warning',
  sent: 'info',
  replied: 'primary',
  won_back: 'success',
  lost: 'default',
  skipped: 'default',
};

function errorText(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: { error?: string; detail?: string } } })?.response?.data;
  return data?.error || data?.detail || fallback;
}

function money(c: WinBackCandidate): string {
  if (!c.annual_value) return '';
  return `${c.currency} ${Number(c.annual_value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

const safeHtml = (html: string) =>
  DOMPurify.sanitize(html, { ALLOWED_TAGS: ['p', 'br', 'strong', 'b', 'em', 'i', 'ul', 'ol', 'li'], ALLOWED_ATTR: [] });

const WinBack: React.FC = () => {
  const [tab, setTab] = useState<TabKey>('review');
  const [product, setProduct] = useState('beatbreeze');
  const [windowDays, setWindowDays] = useState(183);
  const [rows, setRows] = useState<WinBackCandidate[]>([]);
  const [summary, setSummary] = useState<WinBackSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null);

  const [draftFor, setDraftFor] = useState<WinBackCandidate | null>(null);
  const [offer, setOffer] = useState('');
  const [instructions, setInstructions] = useState('');

  const [reviewFor, setReviewFor] = useState<WinBackCandidate | null>(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');

  const [feedbackFor, setFeedbackFor] = useState<WinBackCandidate | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackSource, setFeedbackSource] = useState('call');

  const [reports, setReports] = useState<ChurnInsightReport[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s] = await Promise.all([ApiService.getWinBackSummary()]);
      setSummary(s);
      if (tab === 'insights') {
        const data = await ApiService.getChurnInsights();
        setReports(Array.isArray(data) ? data : data.results || []);
      } else {
        const data = await ApiService.getWinBackCandidates({
          status: TAB_STATUSES[tab].join(','),
          product: product === 'all' ? undefined : product,
          page_size: 200,
        });
        setRows(data.results || []);
      }
    } catch (err) {
      setToast({ text: errorText(err, 'Could not load win-back data'), error: true });
    } finally {
      setLoading(false);
    }
  }, [tab, product]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try {
      await fn();
      if (ok) setToast({ text: ok });
      await load();
      return true;
    } catch (err) {
      setToast({ text: errorText(err, 'Something went wrong'), error: true });
      return false;
    } finally {
      setBusy(false);
    }
  };

  const scan = () =>
    run(async () => {
      const r = await ApiService.scanWinBack({ product, window_days: windowDays });
      setToast({ text: `${r.created} new, ${r.already_listed} already listed` });
      setTab('new');
    }, '');

  const openDraft = (c: WinBackCandidate) => {
    setDraftFor(c);
    setOffer(c.offer || summary?.default_offer || '');
    setInstructions('');
  };

  const doDraft = async () => {
    if (!draftFor) return;
    setBusy(true);
    try {
      const updated = await ApiService.draftWinBack(draftFor.id, { offer, instructions });
      setDraftFor(null);
      openReview(updated);
      await load();
    } catch (err) {
      setToast({ text: errorText(err, 'Claude could not draft this email'), error: true });
    } finally {
      setBusy(false);
    }
  };

  const openReview = (c: WinBackCandidate) => {
    setReviewFor(c);
    setSubject(c.draft_subject);
    setBody(c.draft_body_html);
  };

  const send = async () => {
    if (!reviewFor) return;
    const done = await run(
      () => ApiService.approveWinBack(reviewFor.id, { subject, body_html: body }),
      `Sent to ${reviewFor.contact_email}`,
    );
    if (done) setReviewFor(null);
  };

  const saveFeedback = async () => {
    if (!feedbackFor) return;
    const done = await run(
      () => ApiService.recordWinBackFeedback(feedbackFor.id, { text: feedbackText, source: feedbackSource }),
      'Feedback saved and classified',
    );
    if (done) {
      setFeedbackFor(null);
      setFeedbackText('');
    }
  };

  const generateInsights = () =>
    run(() => ApiService.generateChurnInsights({ product, window_days: windowDays }), 'Insights ready');

  const latest = reports[0];

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Typography variant="h5" gutterBottom>
        Win-back
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2, maxWidth: 760 }}>
        Customers whose contract ended or was cancelled, with nothing live since. Claude drafts a personal email
        for each one; nothing is sent until you approve it. Replies are picked up by the reply checker and Claude
        sorts out why they left.
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
          <TextField select size="small" label="Product" value={product} onChange={(e) => setProduct(e.target.value)}
            sx={{ minWidth: 200 }}>
            {PRODUCTS.map((p) => <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>)}
          </TextField>
          <TextField select size="small" label="Left in the last" value={windowDays}
            onChange={(e) => setWindowDays(Number(e.target.value))} sx={{ minWidth: 160 }}>
            <MenuItem value={90}>3 months</MenuItem>
            <MenuItem value={183}>6 months</MenuItem>
            <MenuItem value={365}>12 months</MenuItem>
          </TextField>
          <Button variant="contained" startIcon={<Search />} onClick={scan} disabled={busy}>
            Find customers who left
          </Button>
          {summary?.default_offer && (
            <Chip label={`Default offer: ${summary.default_offer}`} variant="outlined" sx={{ maxWidth: '100%' }} />
          )}
        </Stack>
      </Paper>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" sx={{ mb: 2 }}>
        <Tab value="review" label={`To review${summary?.pending_review ? ` (${summary.pending_review})` : ''}`} />
        <Tab value="new" label="Found" />
        <Tab value="sent" label="Sent and replies" />
        <Tab value="closed" label="Closed" />
        <Tab value="insights" icon={<Insights fontSize="small" />} iconPosition="start" label="Why they left" />
      </Tabs>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
      ) : tab === 'insights' ? (
        <Paper sx={{ p: 2 }}>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
            <Button variant="contained" startIcon={<AutoAwesome />} onClick={generateInsights} disabled={busy}>
              Analyse and write a plan
            </Button>
            {busy && <CircularProgress size={20} />}
          </Stack>
          {summary && Object.keys(summary.by_reason).length > 0 && (
            <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap', gap: 1 }}>
              {Object.entries(summary.by_reason).sort((a, b) => b[1] - a[1]).map(([reason, n]) => (
                <Chip key={reason} label={`${reason.replace('_', ' ')}: ${n}`} size="small" />
              ))}
            </Stack>
          )}
          {latest ? (
            <Box>
              <Typography variant="caption" color="text.secondary">
                {new Date(latest.created_at).toLocaleString()} · {latest.candidate_count} customers ·{' '}
                {latest.feedback_count} answers · {latest.product || 'all products'}
              </Typography>
              <Typography sx={{ my: 2 }}>{latest.summary}</Typography>
              <Typography component="div" sx={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6 }}>
                {latest.plan_markdown}
              </Typography>
            </Box>
          ) : (
            <Alert severity="info">No analysis yet. Find churned customers first, then run the analysis.</Alert>
          )}
        </Paper>
      ) : rows.length === 0 ? (
        <Alert severity="info">Nothing here. Use "Find customers who left" to scan the CRM.</Alert>
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Customer</TableCell>
                <TableCell>Product</TableCell>
                <TableCell>Left on</TableCell>
                <TableCell align="right">Zones</TableCell>
                <TableCell align="right">Last value</TableCell>
                <TableCell>Contact</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Why they left</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>{c.company_name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {[c.company_industry, c.company_country, c.contract_number].filter(Boolean).join(' · ')}
                    </Typography>
                  </TableCell>
                  <TableCell>{c.product_display}</TableCell>
                  <TableCell>{c.churned_on}</TableCell>
                  <TableCell align="right">{c.zones}</TableCell>
                  <TableCell align="right">{money(c)}</TableCell>
                  <TableCell>
                    {c.contact_email ? (
                      <>
                        <Typography variant="body2">{c.contact_name}</Typography>
                        <Typography variant="caption" color="text.secondary">{c.contact_email}</Typography>
                      </>
                    ) : (
                      <Typography variant="caption" color="error">No emailable contact</Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={c.status_display} color={STATUS_COLOR[c.status]} />
                  </TableCell>
                  <TableCell sx={{ maxWidth: 220 }}>
                    {c.churn_reason !== 'unknown' && (
                      <Typography variant="body2">{c.churn_reason_display}</Typography>
                    )}
                    {c.churn_reason_detail && (
                      <Typography variant="caption" color="text.secondary">{c.churn_reason_detail}</Typography>
                    )}
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    {c.status === 'identified' && (
                      <Button size="small" startIcon={<AutoAwesome />} onClick={() => openDraft(c)}>Draft</Button>
                    )}
                    {c.status === 'pending_review' && (
                      <Button size="small" variant="contained" onClick={() => openReview(c)}>Review</Button>
                    )}
                    {(c.status === 'sent' || c.status === 'replied') && (
                      <>
                        <Button size="small" onClick={() => { setFeedbackFor(c); setFeedbackText(''); }}>
                          Add feedback
                        </Button>
                        <Button size="small" color="success" disabled={busy}
                          onClick={() => run(() => ApiService.setWinBackOutcome(c.id, { outcome: 'won_back' }), 'Marked won back')}>
                          Won
                        </Button>
                        <Button size="small" color="inherit" disabled={busy}
                          onClick={() => run(() => ApiService.setWinBackOutcome(c.id, { outcome: 'lost' }), 'Marked lost')}>
                          Lost
                        </Button>
                      </>
                    )}
                    {['identified', 'needs_contact', 'pending_review'].includes(c.status) && (
                      <Button size="small" color="inherit" disabled={busy}
                        onClick={() => run(() => ApiService.skipWinBack(c.id), 'Skipped')}>
                        Skip
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Ask Claude for a draft */}
      <Dialog open={!!draftFor} onClose={() => !busy && setDraftFor(null)} fullWidth maxWidth="sm">
        <DialogTitle>Draft a win-back email to {draftFor?.company_name}</DialogTitle>
        <DialogContent>
          <TextField label="Offer" value={offer} onChange={(e) => setOffer(e.target.value)} fullWidth
            margin="normal" helperText="Claude makes exactly this offer." />
          <TextField label="Anything else Claude should know (optional)" value={instructions}
            onChange={(e) => setInstructions(e.target.value)} fullWidth multiline minRows={2} margin="normal"
            placeholder="e.g. They renovated in June; the GM changed." />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDraftFor(null)} disabled={busy}>Cancel</Button>
          <Button variant="contained" onClick={doDraft} disabled={busy}
            startIcon={busy ? <CircularProgress size={16} /> : <AutoAwesome />}>
            Draft with Claude
          </Button>
        </DialogActions>
      </Dialog>

      {/* Review and send */}
      <Dialog open={!!reviewFor} onClose={() => !busy && setReviewFor(null)} fullWidth maxWidth="md">
        <DialogTitle>Review before sending</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 1 }}>
            To <strong>{reviewFor?.contact_name}</strong> &lt;{reviewFor?.contact_email}&gt; at {reviewFor?.company_name}
          </Typography>
          {reviewFor?.personalisation_notes && (
            <Alert severity="info" sx={{ mb: 2 }}>{reviewFor.personalisation_notes}</Alert>
          )}
          {reviewFor?.send_error && <Alert severity="error" sx={{ mb: 2 }}>{reviewFor.send_error}</Alert>}
          <TextField label="Subject" value={subject} onChange={(e) => setSubject(e.target.value)} fullWidth
            margin="dense" />
          <TextField label="Body (HTML)" value={body} onChange={(e) => setBody(e.target.value)} fullWidth multiline
            minRows={8} margin="dense" sx={{ fontFamily: 'monospace' }} />
          <Typography variant="overline" color="text.secondary">Preview</Typography>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Box dangerouslySetInnerHTML={{ __html: safeHtml(body) }} sx={{ '& p': { mt: 0 } }} />
          </Paper>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => reviewFor && openDraft(reviewFor)} disabled={busy}>Redraft</Button>
          <Box sx={{ flex: 1 }} />
          <Button onClick={() => setReviewFor(null)} disabled={busy}>Close</Button>
          <Button variant="contained" onClick={send} disabled={busy || !subject.trim() || !body.trim()}
            startIcon={busy ? <CircularProgress size={16} /> : <Send />}>
            Approve and send
          </Button>
        </DialogActions>
      </Dialog>

      {/* Feedback from a call or forwarded reply */}
      <Dialog open={!!feedbackFor} onClose={() => !busy && setFeedbackFor(null)} fullWidth maxWidth="sm">
        <DialogTitle>What did {feedbackFor?.company_name} say?</DialogTitle>
        <DialogContent>
          <TextField select label="Source" value={feedbackSource} onChange={(e) => setFeedbackSource(e.target.value)}
            margin="normal" size="small">
            <MenuItem value="call">Call</MenuItem>
            <MenuItem value="email_reply">Email reply</MenuItem>
            <MenuItem value="manual">Other</MenuItem>
          </TextField>
          <TextField label="Their words or your notes" value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)} fullWidth multiline minRows={4} margin="normal" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFeedbackFor(null)} disabled={busy}>Cancel</Button>
          <Button variant="contained" onClick={saveFeedback} disabled={busy || !feedbackText.trim()}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={5000} onClose={() => setToast(null)}>
        <Alert severity={toast?.error ? 'error' : 'success'} onClose={() => setToast(null)}>
          {toast?.text}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default WinBack;
