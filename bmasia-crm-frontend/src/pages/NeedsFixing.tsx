import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  Link,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Assignment,
  Business,
  CheckCircleOutline,
  Description,
  FileDownloadOutlined,
  Person,
  Receipt,
  RequestQuote,
} from '@mui/icons-material';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import { EmptyState, PageHeader } from '../components/ui';
import ApiService from '../services/api';
import {
  DataQualityCheckPage,
  DataQualityRecordType,
  DataQualitySummary,
  downloadDataQualityCsv,
  getDataQualityCheck,
  getDataQualitySummary,
  SEVERITY_LABEL,
  SEVERITY_TONE,
} from '../services/dataQuality';
import { formatMoney } from '../theme/format';
import useListState from '../hooks/useListState';

const PAGE_SIZES = [25, 50, 100];

const RECORD_ICON: Record<DataQualityRecordType, React.ReactNode> = {
  contract: <Description />,
  company: <Business />,
  contact: <Person />,
  quote: <RequestQuote />,
  invoice: <Receipt />,
  task: <Assignment />,
};

const RECORD_NOUN: Record<DataQualityRecordType, [string, string]> = {
  contract: ['contract', 'contracts'],
  company: ['company', 'companies'],
  contact: ['contact', 'contacts'],
  quote: ['quote', 'quotes'],
  invoice: ['invoice', 'invoices'],
  task: ['task', 'tasks'],
};

// Company and user ids are UUIDs; anything else in the address falls back to "any".
const isUuid = (v: string | number) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(v));

const IDENTIFIER_TYPES: DataQualityRecordType[] = ['contract', 'quote', 'invoice'];

const countLabel = (n: number, type: DataQualityRecordType) =>
  `${n.toLocaleString('en-US')} ${RECORD_NOUN[type][n === 1 ? 0 : 1]}`;

const errorText = (err: any) => err?.response?.data?.detail || err?.message || 'Something went wrong';

/**
 * "Needs fixing": one data-quality check at a time, with the fact that put each record on the
 * list and a link straight to the record. Read-only. The check, page and filters live in the
 * address (/needs-fixing/:key?page=2&company=…&owner=…), so any view can be shared as a link.
 */
const NeedsFixing: React.FC = () => {
  const { key } = useParams<{ key?: string }>();
  const navigate = useNavigate();
  const theme = useTheme();
  const narrow = useMediaQuery(theme.breakpoints.down('md'));

  const [summary, setSummary] = useState<DataQualitySummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [data, setData] = useState<DataQualityCheckPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<{ id: string; name: string }[]>([]);
  const [users, setUsers] = useState<{ id: string; name: string }[]>([]);

  const list = useListState(
    { page: 0, size: 25, company: '', owner: '' },
    {
      size: PAGE_SIZES,
      company: (v) => isUuid(v),
      owner: (v) => v === 'none' || isUuid(v),
    }
  );
  const { page, size, company, owner } = list.values;

  const loadSummary = useCallback(async () => {
    setSummaryError(null);
    try {
      setSummary(await getDataQualitySummary(0));
    } catch (err) {
      setSummaryError(errorText(err));
    }
  }, []);

  useEffect(() => {
    loadSummary();
    ApiService.getCompaniesSimple()
      .then((rows) => setCompanies(rows.map((c) => ({ id: String(c.id), name: c.name }))))
      .catch(() => setCompanies([]));
    ApiService.getUsers({ page_size: 200 })
      .then((res) =>
        setUsers(
          (res.results || []).map((u: any) => ({
            id: String(u.id),
            name: [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username,
          }))
        )
      )
      .catch(() => setUsers([]));
  }, [loadSummary]);

  // No check chosen: open the first one that has records (the server lists the most severe first).
  useEffect(() => {
    if (!key && summary) {
      const first = summary.checks.find((c) => c.count > 0) || summary.checks[0];
      if (first) navigate(`/needs-fixing/${first.key}`, { replace: true });
    }
  }, [key, summary, navigate]);

  const loadPage = useCallback(async () => {
    if (!key) return;
    setLoading(true);
    setError(null);
    try {
      setData(
        await getDataQualityCheck(key, {
          page: page + 1,
          pageSize: size,
          company: company || undefined,
          owner: owner || undefined,
        })
      );
    } catch (err: any) {
      setData(null);
      setError(err?.response?.status === 404 ? 'not-found' : errorText(err));
    } finally {
      setLoading(false);
    }
  }, [key, page, size, company, owner]);

  useEffect(() => {
    loadPage();
  }, [loadPage]);

  // A page past the end (records were fixed since the link was made) moves to the last page.
  useEffect(() => {
    if (data && data.key === key && data.count > 0 && data.rows.length === 0 && page > 0) {
      const last = Math.max(0, Math.ceil(data.count / size) - 1);
      // Only ever move once: if the count and the rows disagree (a record fixed between the
      // two queries), the last page itself can come back empty, and must not be set again.
      if (page !== last) list.set('page', last);
    }
  }, [data, key, page, size, list]);

  const checkHref = (k: string) => {
    const params = new URLSearchParams();
    if (company) params.set('company', String(company));
    if (owner) params.set('owner', String(owner));
    const qs = params.toString();
    return `/needs-fixing/${k}${qs ? `?${qs}` : ''}`;
  };

  const current = useMemo(() => summary?.checks.find((c) => c.key === key), [summary, key]);
  const selectedCompany = companies.find((c) => c.id === company) || null;

  const handleDownload = async () => {
    if (!key) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadDataQualityCsv(key, { company: company || undefined, owner: owner || undefined });
    } catch (err) {
      setDownloadError(errorText(err));
    } finally {
      setDownloading(false);
    }
  };

  const checkPicker = narrow ? (
    <TextField
      select
      fullWidth
      size="small"
      label="Check"
      value={key && summary?.checks.some((c) => c.key === key) ? key : ''}
      onChange={(e) => navigate(checkHref(e.target.value))}
      sx={{ mb: 2 }}
    >
      {(summary?.checks || []).map((c) => (
        <MenuItem key={c.key} value={c.key}>
          {c.title} ({c.count.toLocaleString('en-US')})
        </MenuItem>
      ))}
    </TextField>
  ) : (
    <Paper component="nav" aria-label="Checks" sx={{ overflow: 'hidden', alignSelf: 'start' }}>
      <Typography variant="overline" color="text.secondary" sx={{ display: 'block', px: 2, pt: 1.5 }}>
        Checks
      </Typography>
      {!summary && !summaryError && (
        <Box sx={{ px: 2, pb: 2 }}>
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} height={36} />
          ))}
        </Box>
      )}
      {summaryError && (
        <Alert severity="error" sx={{ m: 2 }} action={<Button color="inherit" size="small" onClick={loadSummary}>Try again</Button>}>
          {summaryError}
        </Alert>
      )}
      <List dense disablePadding>
        {(summary?.checks || []).map((c) => {
          const tone = SEVERITY_TONE[c.severity];
          return (
            <ListItemButton
              key={c.key}
              component={RouterLink}
              to={checkHref(c.key)}
              selected={c.key === key}
              aria-current={c.key === key ? 'page' : undefined}
              sx={{ gap: 1.25, py: 1, alignItems: 'flex-start' }}
            >
              <Box
                aria-hidden
                sx={{
                  mt: 0.9,
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  flexShrink: 0,
                  bgcolor: c.count === 0 ? 'success.main' : tone === 'default' ? 'text.secondary' : `${tone}.main`,
                }}
              />
              <ListItemText
                primary={c.title}
                primaryTypographyProps={{ fontSize: '0.8125rem', fontWeight: c.key === key ? 600 : 400 }}
                sx={{ my: 0, color: c.count === 0 ? 'text.secondary' : 'text.primary' }}
              />
              <Typography
                variant="body2"
                sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: c.count === 0 ? 'text.disabled' : 'text.primary' }}
              >
                {c.count.toLocaleString('en-US')}
              </Typography>
            </ListItemButton>
          );
        })}
      </List>
    </Paper>
  );

  // While another check loads, show its own title from the summary, never the previous check's.
  const pageData = data && data.key === key ? data : null;
  const header = pageData || current;
  const severity = header?.severity;

  return (
    <Box>
      <PageHeader
        breadcrumbs={[{ label: 'Today', to: '/today' }, { label: 'Needs fixing' }]}
        title="Needs fixing"
        subtitle="Records that are wrong or about to be missed. This page only reads; nothing here changes data."
      />

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: '300px minmax(0, 1fr)' },
          gap: { xs: 0, md: 3 },
          alignItems: 'start',
        }}
      >
        {checkPicker}

        <Paper component="section" aria-labelledby="check-title" sx={{ overflow: 'hidden', minWidth: 0 }}>
          {error === 'not-found' ? (
            <Box sx={{ p: 2.5 }}>
              <Alert severity="warning">
                This check does not exist. <Link component={RouterLink} to="/needs-fixing">Show all checks</Link>
              </Alert>
            </Box>
          ) : (
            <>
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: { xs: 'column', sm: 'row' },
                  alignItems: { xs: 'stretch', sm: 'flex-start' },
                  justifyContent: 'space-between',
                  gap: 2,
                  px: 2.5,
                  pt: 2,
                  pb: 2,
                  borderBottom: 1,
                  borderColor: 'divider',
                }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Typography variant="h6" component="h2" id="check-title">
                      {header ? header.title : <Skeleton width={260} />}
                    </Typography>
                    {severity && (
                      <Chip
                        size="small"
                        label={`${SEVERITY_LABEL[severity]} priority`}
                        color={SEVERITY_TONE[severity]}
                        variant={SEVERITY_TONE[severity] === 'default' ? 'outlined' : 'filled'}
                      />
                    )}
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {header ? header.why : <Skeleton width={360} />}
                  </Typography>
                  {pageData && (
                    <Typography variant="body2" sx={{ mt: 0.75, fontWeight: 600 }}>
                      {countLabel(pageData.count, pageData.record_type)}
                      {(company || owner) && ' matching the filters'}
                    </Typography>
                  )}
                </Box>
                <Button
                  variant="outlined"
                  startIcon={<FileDownloadOutlined />}
                  onClick={handleDownload}
                  disabled={!data || data.count === 0 || downloading}
                  sx={{ flexShrink: 0, alignSelf: { xs: 'flex-start', sm: 'auto' } }}
                >
                  {downloading ? 'Preparing…' : 'Download CSV'}
                </Button>
              </Box>

              <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', px: 2.5, py: 1.5, borderBottom: 1, borderColor: 'divider' }}>
                <Autocomplete
                  size="small"
                  options={companies}
                  value={selectedCompany}
                  getOptionLabel={(o) => o.name}
                  isOptionEqualToValue={(o, v) => o.id === v.id}
                  onChange={(_, v) => {
                    list.set('company', v ? v.id : '');
                    list.set('page', 0);
                  }}
                  renderInput={(params) => (
                    <TextField {...params} label="Company" placeholder="Any company" InputLabelProps={{ ...params.InputLabelProps, shrink: true }} />
                  )}
                  sx={{ flex: '1 1 240px', maxWidth: { sm: 360 } }}
                />
                <TextField
                  select
                  size="small"
                  label="Owner"
                  value={owner || ''}
                  onChange={(e) => {
                    list.set('owner', e.target.value);
                    list.set('page', 0);
                  }}
                  sx={{ flex: '1 1 180px', maxWidth: { sm: 240 } }}
                  SelectProps={{ displayEmpty: true }}
                  InputLabelProps={{ shrink: true }}
                >
                  <MenuItem value="">Anyone</MenuItem>
                  <MenuItem value="none">No owner recorded</MenuItem>
                  {users.map((u) => (
                    <MenuItem key={u.id} value={u.id}>
                      {u.name}
                    </MenuItem>
                  ))}
                </TextField>
              </Box>

              {downloadError && (
                <Alert severity="error" sx={{ mx: 2.5, mt: 2 }} onClose={() => setDownloadError(null)}>
                  Could not download the CSV: {downloadError}
                </Alert>
              )}

              {error && (
                <Box sx={{ p: 2.5 }}>
                  <Alert
                    severity="error"
                    action={
                      <Button color="inherit" size="small" onClick={loadPage}>
                        Try again
                      </Button>
                    }
                  >
                    Could not load this check: {error}
                  </Alert>
                </Box>
              )}

              {!error && data && data.count === 0 && !loading && (
                <EmptyState
                  icon={<CheckCircleOutline />}
                  title={company || owner ? 'Nothing matches these filters' : 'Nothing to fix here'}
                  description={
                    company || owner
                      ? 'Clear the company or owner filter to see every record of this check.'
                      : 'Every record passes this check today.'
                  }
                />
              )}

              {!error && (loading || !data || data.count > 0) && (
                <>
                  <TableContainer>
                    <Table size="small" aria-labelledby="check-title">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ minWidth: { sm: 150 } }}>Record</TableCell>
                          <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>Company</TableCell>
                          <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>What needs fixing</TableCell>
                          <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' } }}>Owner</TableCell>
                          <TableCell align="right" sx={{ display: { xs: 'none', lg: 'table-cell' } }}>
                            Value
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {(loading || !data) &&
                          [0, 1, 2, 3, 4, 5].map((i) => (
                            <TableRow key={`s${i}`}>
                              <TableCell colSpan={5}>
                                <Skeleton height={28} />
                              </TableCell>
                            </TableRow>
                          ))}
                        {!loading &&
                          data &&
                          data.rows.map((r) => (
                            <TableRow
                              key={`${r.record_type}-${r.id}-${r.label}`}
                              hover
                              onClick={(e) => {
                                if ((e.target as HTMLElement).closest('a')) return;
                                navigate(r.link);
                              }}
                              sx={{ cursor: 'pointer', verticalAlign: 'top' }}
                            >
                              <TableCell sx={{ minWidth: 0 }}>
                                <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
                                  <Box
                                    aria-hidden
                                    sx={{ color: 'text.secondary', display: 'flex', mt: '1px', '& svg': { fontSize: 18 } }}
                                  >
                                    {RECORD_ICON[r.record_type]}
                                  </Box>
                                  <Box sx={{ minWidth: 0 }}>
                                    <Link
                                      component={RouterLink}
                                      to={r.link}
                                      underline="hover"
                                      sx={{
                                        fontWeight: 600,
                                        fontSize: '0.8125rem',
                                        // Document numbers stay on one line; names and titles wrap.
                                        ...(IDENTIFIER_TYPES.includes(r.record_type)
                                          ? { whiteSpace: 'nowrap' }
                                          : { overflowWrap: 'break-word' }),
                                      }}
                                    >
                                      {r.label}
                                    </Link>
                                    {r.company_name && r.record_type !== 'company' && (
                                      <Typography
                                        variant="caption"
                                        color="text.secondary"
                                        sx={{ display: { xs: 'block', md: 'none' }, overflowWrap: 'anywhere' }}
                                      >
                                        {r.company_name}
                                      </Typography>
                                    )}
                                    <Typography
                                      variant="caption"
                                      sx={{ display: { xs: 'block', sm: 'none' }, color: 'text.primary', mt: 0.25 }}
                                    >
                                      {r.fact}
                                    </Typography>
                                  </Box>
                                </Box>
                              </TableCell>
                              <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                                {r.company_id && r.record_type !== 'company' ? (
                                  <Link
                                    component={RouterLink}
                                    to={`/companies/${r.company_id}`}
                                    underline="hover"
                                    color="text.primary"
                                    sx={{ fontSize: '0.8125rem' }}
                                  >
                                    {r.company_name}
                                  </Link>
                                ) : (
                                  '—'
                                )}
                              </TableCell>
                              <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>
                                <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>
                                  {r.fact}
                                </Typography>
                                {r.related.length > 0 && (
                                  <Typography variant="caption" color="text.secondary">
                                    Also:{' '}
                                    {r.related.map((x, i) => (
                                      <React.Fragment key={x.link}>
                                        {i > 0 && ', '}
                                        <Link component={RouterLink} to={x.link} underline="hover">
                                          {x.label}
                                        </Link>
                                      </React.Fragment>
                                    ))}
                                  </Typography>
                                )}
                              </TableCell>
                              <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' }, whiteSpace: 'nowrap' }}>
                                {r.owner_name || (
                                  <Typography component="span" variant="body2" color="text.secondary">
                                    —
                                  </Typography>
                                )}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{ display: { xs: 'none', lg: 'table-cell' }, whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}
                              >
                                {r.amount && r.currency ? formatMoney(r.amount, r.currency) : '—'}
                              </TableCell>
                            </TableRow>
                          ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                  {data && data.count > 0 && (
                    <TablePagination
                      component="div"
                      count={data.count}
                      page={Math.min(page, Math.max(0, Math.ceil(data.count / size) - 1))}
                      onPageChange={(_, p) => list.set('page', p)}
                      rowsPerPage={size}
                      rowsPerPageOptions={PAGE_SIZES}
                      onRowsPerPageChange={(e) => {
                        list.set('size', parseInt(e.target.value, 10));
                        list.set('page', 0);
                      }}
                      labelRowsPerPage={narrow ? 'Rows' : 'Rows per page'}
                    />
                  )}
                </>
              )}
            </>
          )}
        </Paper>
      </Box>
    </Box>
  );
};

export default NeedsFixing;
