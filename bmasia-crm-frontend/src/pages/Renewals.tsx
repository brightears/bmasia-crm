import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  ButtonBase,
  Chip,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  LinearProgress,
  Link,
  MenuItem,
  Paper,
  Select,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  ChevronLeft,
  ChevronRight,
  AutorenewOutlined,
  FileDownloadOutlined,
  Refresh,
  Search,
  WarningAmberRounded,
} from '@mui/icons-material';
import { Link as RouterLink } from 'react-router-dom';
import { EmptyState, PageHeader, ProductChip } from '../components/ui';
import { useListState } from '../hooks/useListState';
import { useListSearchBox } from '../hooks/useListSearchBox';
import { formatDate, formatMoney, visuallyHidden } from '../theme';
import {
  EntityKey,
  getRenewals,
  RenewalRow,
  RenewalsResponse,
  RenewalStateKey,
} from '../services/renewals';
import {
  CurrencySummary,
  filterRows,
  parseStates,
  PRODUCT_FILTERS,
  ProductFilter,
  relativeDays,
  rowsToCsv,
  SORT_VALUES,
  sortRows,
  STATE_ORDER,
  summarize,
} from '../utils/renewalsView';

type ChipColor = 'default' | 'primary' | 'info' | 'success' | 'warning' | 'error';

/** Colour of each renewal state, in the app's status language (display only). */
export const STATE_TONE: Record<RenewalStateKey, ChipColor> = {
  not_started: 'default',
  drafted: 'info',
  sent: 'info',
  signed: 'success',
  invoiced: 'success',
  paid: 'success',
  renewed_unlinked: 'warning',
  auto_renews: 'primary',
  lapsed: 'error',
  lost: 'error',
};

const ENTITY_LABEL: Record<string, string> = {
  '': 'Both entities',
  th: 'Thailand',
  hk: 'Hong Kong',
};
const ENTITY_FULL: Record<string, string> = {
  th: 'BMAsia (Thailand) Co., Ltd.',
  hk: 'BMAsia Limited (Hong Kong)',
};
const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_LONG = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const PRODUCT_KEY: Record<string, 'soundtrack' | 'beatbreeze' | undefined> = {
  Soundtrack: 'soundtrack',
  'Beat Breeze': 'beatbreeze',
};

const isYear = (v: string | number) => /^\d{4}$/.test(String(v)) && Number(v) >= 2000 && Number(v) <= 2100;
const isMonth = (v: string | number) => /^\d{1,2}$/.test(String(v)) && Number(v) >= 1 && Number(v) <= 12;

const DEFAULTS = {
  view: '',
  year: '',
  month: '',
  entity: '',
  state: '',
  attention: '',
  product: '',
  q: '',
  sort: '',
};

// ---------------------------------------------------------------------------
// Small pieces
// ---------------------------------------------------------------------------

const StateChip: React.FC<{ row: RenewalRow }> = ({ row }) => (
  <Chip size="small" label={row.renewal.label} color={STATE_TONE[row.renewal.state]} sx={{ maxWidth: '100%' }} />
);

const AttentionNote: React.FC<{ row: RenewalRow }> = ({ row }) =>
  row.renewal.attention ? (
    <Typography
      variant="caption"
      component="div"
      sx={{ color: 'error.main', display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5, lineHeight: 1.3 }}
    >
      <WarningAmberRounded sx={{ fontSize: 14 }} aria-hidden />
      {row.renewal.attention_label}
    </Typography>
  ) : null;

const RecordLink: React.FC<{ to: string; children: React.ReactNode; strong?: boolean; label?: string }> = ({
  to,
  children,
  strong,
  label,
}) => (
  <Link
    component={RouterLink}
    to={to}
    underline="hover"
    color="inherit"
    aria-label={label}
    sx={{ fontWeight: strong ? 600 : 500, overflowWrap: 'anywhere' }}
  >
    {children}
  </Link>
);

const ValueChange: React.FC<{ row: RenewalRow }> = ({ row }) => {
  const s = row.renewal.successor;
  if (!s) return <Typography variant="body2" color="text.secondary">—</Typography>;
  const change = row.renewal.value_change;
  const perYear = row.renewal.value_change_basis === 'per_year';
  return (
    <Box sx={{ textAlign: 'right' }}>
      <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
        {formatMoney(s.value, s.currency)}
      </Typography>
      {change === null ? (
        s.currency !== row.currency ? (
          <Typography variant="caption" color="text.secondary">other currency</Typography>
        ) : null
      ) : (
        <Typography
          variant="caption"
          sx={{
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
            color: change > 0 ? 'success.main' : change < 0 ? 'error.main' : 'text.secondary',
          }}
        >
          {change === 0
            ? 'no change'
            : `${change > 0 ? '+' : '−'}${formatMoney(Math.abs(change), row.currency)}${perYear ? ' / yr' : ''}`}
        </Typography>
      )}
    </Box>
  );
};

const SuccessorCell: React.FC<{ row: RenewalRow }> = ({ row }) => {
  const s = row.renewal.successor;
  const others = row.renewal.other_linked.length;
  if (!s) {
    return (
      <Typography variant="body2" color="text.secondary">
        {others ? `${others} linked, none live` : '—'}
      </Typography>
    );
  }
  return (
    <Box>
      <RecordLink to={`/contracts/${s.contract_id}`} label={`Renewal contract ${s.contract_number}`}>
        {s.contract_number}
      </RecordLink>
      <Typography variant="caption" color="text.secondary" component="div" sx={{ lineHeight: 1.3 }}>
        {s.status}
        {s.start_date ? ` from ${formatDate(s.start_date)}` : ''}
        {others ? ` · +${others} more` : ''}
        {s.other_company ? ' · other company record' : ''}
      </Typography>
    </Box>
  );
};

const ZonesText: React.FC<{ row: RenewalRow }> = ({ row }) => {
  if (!row.zones) return <>no zones</>;
  const text = `${row.zones} zone${row.zones === 1 ? '' : 's'}`;
  if (row.zones_source === 'contracted_zone_count') {
    return (
      <Tooltip title="The contract has no service-location rows; this is the company's zone count from the funnel.">
        <span>{text}*</span>
      </Tooltip>
    );
  }
  return <>{text}</>;
};

// ---------------------------------------------------------------------------
// Month strip
// ---------------------------------------------------------------------------

interface StripProps {
  data: RenewalsResponse | null;
  year: number;
  month: number;
  openView: boolean;
  today: Date;
  onMonth: (m: number) => void;
  onOpen: () => void;
  onYear: (y: number) => void;
}

const MonthStrip: React.FC<StripProps> = ({ data, year, month, openView, today, onMonth, onOpen, onYear }) => {
  const months = data && data.year === year ? data.months : null;
  const cell = (selected: boolean) => ({
    flex: '1 0 64px',
    minWidth: 64,
    px: 1,
    py: 1,
    borderRadius: 2,
    flexDirection: 'column' as const,
    alignItems: 'flex-start',
    border: 1,
    borderColor: selected ? 'primary.main' : 'divider',
    bgcolor: (t: any) => (selected ? alpha(t.palette.primary.main, t.palette.mode === 'dark' ? 0.16 : 0.12) : 'background.paper'),
    '&:hover': { borderColor: 'primary.main' },
    '&.Mui-focusVisible': { outline: 2, outlineColor: 'primary.dark', outlineStyle: 'solid', outlineOffset: 2 },
  });
  return (
    <Box component="nav" aria-label="Months" sx={{ display: 'flex', alignItems: 'stretch', gap: 1, mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
        <IconButton size="small" aria-label={`Previous year, ${year - 1}`} onClick={() => onYear(year - 1)}>
          <ChevronLeft />
        </IconButton>
        <Typography sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }} aria-live="polite">
          {year}
        </Typography>
        <IconButton size="small" aria-label={`Next year, ${year + 1}`} onClick={() => onYear(year + 1)}>
          <ChevronRight />
        </IconButton>
      </Box>
      <Box sx={{ display: 'flex', gap: 0.75, overflowX: 'auto', flex: 1, pb: 0.5 }}>
        <ButtonBase onClick={onOpen} aria-pressed={openView} sx={{ ...cell(openView), flex: '1 0 84px' }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary' }}>
            All open
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 700 }}>
            {openView && data ? data.count : '·'}
          </Typography>
        </ButtonBase>
        {Array.from({ length: 12 }).map((_, i) => {
          const m = months ? months[i] : null;
          const selected = !openView && month === i + 1;
          const isNow = year === today.getFullYear() && i === today.getMonth();
          return (
            <ButtonBase
              key={i}
              onClick={() => onMonth(i + 1)}
              aria-current={selected ? 'page' : undefined}
              aria-label={`${MONTH_LONG[i]} ${year}${m ? `: ${m.count} ending, ${m.attention} need attention` : ''}`}
              sx={cell(selected)}
            >
              <Typography
                variant="caption"
                sx={{ fontWeight: 600, color: isNow ? 'primary.dark' : 'text.secondary', display: 'flex', gap: 0.5 }}
              >
                {MONTH_SHORT[i]}
                {isNow && (
                  <Box component="span" sx={{ fontWeight: 500 }}>
                    · now
                  </Box>
                )}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, width: '100%' }}>
                <Typography variant="body2" sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                  {m ? m.count : <Skeleton width={18} />}
                </Typography>
                {m && m.attention > 0 && (
                  <Box
                    component="span"
                    title={`${m.attention} need attention`}
                    sx={{
                      ml: 'auto',
                      minWidth: 18,
                      height: 18,
                      px: 0.5,
                      borderRadius: 9,
                      bgcolor: 'error.main',
                      color: 'error.contrastText',
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      display: 'grid',
                      placeItems: 'center',
                    }}
                  >
                    {m.attention}
                  </Box>
                )}
              </Box>
            </ButtonBase>
          );
        })}
      </Box>
    </Box>
  );
};

// ---------------------------------------------------------------------------
// Summary strip
// ---------------------------------------------------------------------------

const Figure: React.FC<{ label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: string }> = ({
  label,
  value,
  sub,
  tone,
}) => (
  <Box sx={{ minWidth: 0 }}>
    <Typography variant="caption" color="text.secondary" component="div" sx={{ fontWeight: 600 }}>
      {label}
    </Typography>
    <Typography sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: tone, fontSize: '1rem' }}>
      {value}
    </Typography>
    {sub && (
      <Typography variant="caption" color="text.secondary" component="div" sx={{ fontVariantNumeric: 'tabular-nums' }}>
        {sub}
      </Typography>
    )}
  </Box>
);

const SummaryStrip: React.FC<{ summaries: CurrencySummary[]; filtered: boolean }> = ({ summaries, filtered }) => {
  if (!summaries.length) return null;
  return (
    <Box sx={{ display: 'grid', gap: 1.5, mb: 2, gridTemplateColumns: { xs: '1fr', lg: summaries.length > 1 ? '1fr 1fr' : '1fr' } }}>
      {summaries.map((s) => (
        <Paper key={s.currency} component="section" aria-label={`${s.currency} totals`} sx={{ p: 2 }}>
          <Typography variant="overline" sx={{ lineHeight: 1, color: 'text.secondary', fontWeight: 700 }}>
            {s.currency}
            {filtered ? ' · rows shown' : ''}
          </Typography>
          <Box
            sx={{
              display: 'grid',
              gap: 2,
              mt: 1,
              gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(5, minmax(0, 1fr))' },
            }}
          >
            <Figure label="Terms ending" value={s.terms} sub={formatMoney(s.value, s.currency)} />
            <Figure
              label="Renewed"
              value={s.renewed}
              sub={formatMoney(s.renewedValue, s.currency)}
              tone="success.main"
            />
            <Figure
              label="At risk"
              value={formatMoney(s.atRiskValue, s.currency)}
              sub={`${s.open} not yet renewed`}
              tone={s.atRiskValue > 0 ? 'warning.dark' : undefined}
            />
            <Figure
              label="Lost"
              value={formatMoney(s.lostValue, s.currency)}
              sub={`${s.lost} cancelled or expired`}
              tone={s.lostValue > 0 ? 'error.main' : undefined}
            />
            <Tooltip title="Renewed terms ÷ terms ending, leaving out terms that renew automatically.">
              <Box>
                <Figure
                  label="Renewal rate"
                  value={s.rate === null ? '—' : `${Math.round(s.rate * 100)}%`}
                  sub={s.auto ? `${s.auto} auto-renew` : undefined}
                />
              </Box>
            </Tooltip>
          </Box>
        </Paper>
      ))}
    </Box>
  );
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type Column = {
  key: string;
  label: string;
  align?: 'right';
  hide?: object;
  width?: number | string;
};

const COLUMNS: Column[] = [
  { key: 'company', label: 'Customer' },
  { key: 'contract', label: 'Contract', width: 150 },
  { key: 'product', label: 'Product', width: 120, hide: { display: { xs: 'none', lg: 'table-cell' } } },
  { key: 'end', label: 'Term ends', width: 118 },
  { key: 'value', label: 'Current value', align: 'right', width: 120 },
  { key: 'state', label: 'Renewal', width: 180 },
  { key: 'renewal', label: 'Renewal contract', width: 150 },
  { key: 'change', label: 'New value', align: 'right', width: 130, hide: { display: { xs: 'none', md: 'table-cell' } } },
  { key: 'owner', label: 'Owner', width: 120, hide: { display: { xs: 'none', xl: 'table-cell' } } },
];

const Renewals: React.FC = () => {
  const theme = useTheme();
  const narrow = useMediaQuery(theme.breakpoints.down('md'));
  const today = useMemo(() => new Date(), []);

  const list = useListState(DEFAULTS, {
    view: ['', 'open'],
    year: isYear,
    month: isMonth,
    entity: ['', 'th', 'hk'],
    state: (v) => parseStates(String(v)).length > 0,
    attention: ['', '1'],
    product: PRODUCT_FILTERS,
    sort: SORT_VALUES,
  });
  const v = list.values;
  const openView = v.view === 'open';
  const year = v.year ? Number(v.year) : today.getFullYear();
  const month = v.month ? Number(v.month) : today.getMonth() + 1;
  const entity = v.entity as '' | EntityKey;
  const states = useMemo(() => parseStates(String(v.state)), [v.state]);

  const update = useCallback(
    (changes: Partial<Record<keyof typeof DEFAULTS, string>>) => {
      Object.entries(changes).forEach(([key, value]) => list.set(key as keyof typeof DEFAULTS, value ?? ''));
    },
    // list.set is stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );
  const searchBox = useListSearchBox(String(v.q), (text) => update({ q: text }));

  const [data, setData] = useState<RenewalsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const requestId = useRef(0);

  useEffect(() => {
    const id = ++requestId.current;
    setLoading(true);
    setError('');
    getRenewals({ view: openView ? 'open' : 'month', year, month, entity })
      .then((result) => {
        if (id === requestId.current) setData(result);
      })
      .catch(() => {
        if (id === requestId.current) setError('The renewals could not be loaded.');
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false);
      });
  }, [openView, year, month, entity, reload]);

  // Rows of the response that matches the current choice (older responses are not shown as current).
  const current =
    data &&
    data.view === (openView ? 'open' : 'month') &&
    data.year === year &&
    (openView || data.month === month) &&
    data.entity === entity
      ? data
      : null;
  const allRows = useMemo(() => current?.rows ?? [], [current]);
  const filters = {
    states,
    attentionOnly: v.attention === '1',
    product: v.product as ProductFilter,
    search: String(v.q),
  };
  const anyFilter = Boolean(filters.states.length || filters.attentionOnly || filters.product || filters.search);
  const visible = useMemo(
    () => sortRows(filterRows(allRows, filters), String(v.sort)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [allRows, v.state, v.attention, v.product, v.q, v.sort]
  );
  const summaries = useMemo(() => summarize(visible), [visible]);

  const stateCounts = useMemo(() => {
    const counts: Partial<Record<RenewalStateKey, number>> = {};
    allRows.forEach((r) => {
      counts[r.renewal.state] = (counts[r.renewal.state] || 0) + 1;
    });
    return counts;
  }, [allRows]);
  const attentionCount = allRows.filter((r) => r.renewal.attention).length;
  const stateLabel = (key: RenewalStateKey) => current?.states.find((s) => s.key === key)?.label ?? key;

  const toggleState = (key: RenewalStateKey) => {
    const next = states.includes(key) ? states.filter((s) => s !== key) : [...states, key];
    update({ state: STATE_ORDER.filter((s) => next.includes(s)).join(',') });
  };

  const clearFilters = () => {
    update({ state: '', attention: '', product: '', q: '' });
  };

  const onSort = (key: string) => {
    const sort = String(v.sort);
    update({ sort: sort === key ? `-${key}` : sort === `-${key}` ? '' : key });
  };

  const viewTitle = openView
    ? `All open renewals${current ? `, ${formatDate(current.window.start)} – ${formatDate(current.window.end)}` : ''}`
    : `${MONTH_LONG[month - 1]} ${year}`;

  const exportCsv = () => {
    const csv = rowsToCsv(visible);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `renewals-${openView ? 'open' : `${year}-${String(month).padStart(2, '0')}`}${entity ? `-${entity}` : ''}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  const emptyText = openView
    ? { title: 'No open renewals', description: 'Every term in this window is renewed, lost or renews automatically.' }
    : {
        title: 'Nothing ends in this month',
        description: `No contract term ends in ${MONTH_LONG[month - 1]} ${year}${entity ? ` for ${ENTITY_FULL[entity]}` : ''}.`,
      };

  // ----- table and cards -----
  const renderEmpty = () =>
    anyFilter && allRows.length > 0 ? (
      <EmptyState
        icon={<Search />}
        title="No rows match these filters"
        description="Try a different search or clear the filters."
        action={
          <Button variant="outlined" onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    ) : (
      <EmptyState icon={<AutorenewOutlined />} title={emptyText.title} description={emptyText.description} />
    );

  const rowAccent = (row: RenewalRow) =>
    row.renewal.attention ? { boxShadow: `inset 3px 0 0 ${theme.palette.error.main}` } : undefined;

  const table = (
    <TableContainer sx={{ maxHeight: 'calc(100vh - 120px)', borderRadius: 0 }}>
      <Table stickyHeader size="small" aria-label={`Renewals, ${viewTitle}`} sx={{ tableLayout: 'auto' }}>
        <TableHead>
          <TableRow>
            {COLUMNS.map((col) => {
              const sort = String(v.sort);
              const active = sort === col.key || sort === `-${col.key}`;
              return (
                <TableCell
                  key={col.key}
                  align={col.align}
                  sortDirection={active ? (sort.startsWith('-') ? 'desc' : 'asc') : false}
                  sx={{ width: col.width, whiteSpace: 'nowrap', ...(col.hide || {}) }}
                >
                  <TableSortLabel
                    active={active}
                    direction={active && sort.startsWith('-') ? 'desc' : 'asc'}
                    onClick={() => onSort(col.key)}
                  >
                    {col.label}
                    {active && (
                      <Box component="span" sx={visuallyHidden}>
                        {sort.startsWith('-') ? 'sorted descending' : 'sorted ascending'}
                      </Box>
                    )}
                  </TableSortLabel>
                </TableCell>
              );
            })}
          </TableRow>
        </TableHead>
        <TableBody>
          {loading && !current ? (
            Array.from({ length: 8 }).map((_, i) => (
              <TableRow key={`s-${i}`}>
                {COLUMNS.map((col) => (
                  <TableCell key={col.key} sx={col.hide}>
                    <Skeleton width="70%" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : visible.length === 0 ? (
            <TableRow>
              <TableCell colSpan={COLUMNS.length}>{renderEmpty()}</TableCell>
            </TableRow>
          ) : (
            visible.map((row) => (
              <TableRow key={row.contract_id} hover sx={{ verticalAlign: 'top', ...rowAccent(row) }}>
                <TableCell>
                  <RecordLink to={`/companies/${row.company_id}`} strong>
                    {row.company}
                  </RecordLink>
                  <Typography variant="caption" color="text.secondary" component="div" sx={{ lineHeight: 1.3 }}>
                    {[row.corporate_group !== row.company ? row.corporate_group : '', row.country]
                      .filter(Boolean)
                      .join(' · ')}
                  </Typography>
                </TableCell>
                <TableCell>
                  <RecordLink to={`/contracts/${row.contract_id}`} label={`Contract ${row.contract_number}`}>
                    {row.contract_number}
                  </RecordLink>
                  <Typography variant="caption" color="text.secondary" component="div" sx={{ lineHeight: 1.3 }}>
                    {[row.property_name, row.status !== 'Active' ? row.status : ''].filter(Boolean).join(' · ')}
                    {row.lifecycle_type === 'addon' ? ' · add-on' : ''}
                  </Typography>
                </TableCell>
                <TableCell sx={COLUMNS[2].hide}>
                  {PRODUCT_KEY[row.product] ? (
                    <ProductChip value={PRODUCT_KEY[row.product]} />
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      {row.product}
                    </Typography>
                  )}
                  <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.25 }}>
                    <ZonesText row={row} />
                  </Typography>
                </TableCell>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>
                  <Typography variant="body2">{formatDate(row.end_date)}</Typography>
                  <Typography
                    variant="caption"
                    component="div"
                    sx={{ color: row.days_from_end !== null && row.days_from_end > 0 ? 'text.primary' : 'text.secondary' }}
                  >
                    {relativeDays(row.days_from_end)}
                  </Typography>
                </TableCell>
                <TableCell align="right" sx={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                  <Typography variant="body2">{formatMoney(row.value, row.currency)}</Typography>
                  {row.term_months && row.term_months !== 12 ? (
                    <Typography variant="caption" color="text.secondary">
                      {row.term_months} months
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell>
                  <StateChip row={row} />
                  <AttentionNote row={row} />
                </TableCell>
                <TableCell>
                  <SuccessorCell row={row} />
                </TableCell>
                <TableCell align="right" sx={COLUMNS[7].hide}>
                  <ValueChange row={row} />
                </TableCell>
                <TableCell sx={COLUMNS[8].hide}>
                  <Typography variant="body2" color={row.owner ? 'text.primary' : 'text.secondary'}>
                    {row.owner || '—'}
                  </Typography>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );

  const cards = (
    <Box component="ul" aria-label={`Renewals, ${viewTitle}`} sx={{ listStyle: 'none', m: 0, p: 0 }}>
      {loading && !current
        ? Array.from({ length: 5 }).map((_, i) => (
            <Box component="li" key={i} sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
              <Skeleton width="60%" />
              <Skeleton width="40%" />
            </Box>
          ))
        : visible.length === 0
        ? <Box component="li">{renderEmpty()}</Box>
        : visible.map((row) => (
            <Box
              component="li"
              key={row.contract_id}
              sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider', ...rowAccent(row) }}
            >
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box sx={{ minWidth: 0 }}>
                  <RecordLink to={`/companies/${row.company_id}`} strong>
                    {row.company}
                  </RecordLink>
                  <Typography variant="caption" color="text.secondary" component="div">
                    <RecordLink to={`/contracts/${row.contract_id}`} label={`Contract ${row.contract_number}`}>
                      {row.contract_number}
                    </RecordLink>
                    {row.property_name ? ` · ${row.property_name}` : ''} · {row.product} · <ZonesText row={row} />
                  </Typography>
                </Box>
                <StateChip row={row} />
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.75, gap: 1 }}>
                <Typography variant="body2">
                  Ends {formatDate(row.end_date)}{' '}
                  <Box component="span" sx={{ color: 'text.secondary' }}>
                    ({relativeDays(row.days_from_end)})
                  </Box>
                </Typography>
                <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
                  {formatMoney(row.value, row.currency)}
                </Typography>
              </Box>
              <AttentionNote row={row} />
              {row.renewal.successor && (
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.75, gap: 1 }}>
                  <SuccessorCell row={row} />
                  <ValueChange row={row} />
                </Box>
              )}
            </Box>
          ))}
    </Box>
  );

  return (
    <Box>
      <PageHeader
        title="Renewals"
        subtitle="Every contract term that ends in a month, and where its renewal stands. Read-only: open a record to change it."
        actions={
          <Button
            variant="outlined"
            startIcon={<FileDownloadOutlined />}
            onClick={exportCsv}
            disabled={!current || visible.length === 0}
          >
            Export CSV
          </Button>
        }
      />

      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1.5, mb: 2 }}>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={entity}
          onChange={(_, value) => value !== null && update({ entity: value })}
          aria-label="Billing entity"
        >
          {(['', 'th', 'hk'] as const).map((key) => (
            <ToggleButton key={key || 'all'} value={key} sx={{ px: 1.5, textTransform: 'none' }}>
              <Tooltip title={key ? ENTITY_FULL[key] : 'Both billing entities; totals stay per currency'}>
                <span>{ENTITY_LABEL[key]}</span>
              </Tooltip>
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        <Typography variant="body2" color="text.secondary" sx={{ ml: { sm: 'auto' } }}>
          {current ? `${viewTitle} · data as of ${formatDate(current.as_of)}` : viewTitle}
        </Typography>
      </Box>

      <MonthStrip
        data={data}
        year={year}
        month={month}
        openView={openView}
        today={today}
        onMonth={(m) => update({ view: '', month: String(m), year: String(year) })}
        onOpen={() => update({ view: 'open', year: String(year) })}
        onYear={(y) => update({ year: String(y) })}
      />

      {error && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          action={
            <Button color="inherit" size="small" startIcon={<Refresh />} onClick={() => setReload((n) => n + 1)}>
              Try again
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {current && <SummaryStrip summaries={summaries} filtered={anyFilter} />}

      <Paper sx={{ overflow: 'hidden' }}>
        {loading && <LinearProgress aria-label="Loading renewals" sx={{ height: 2 }} />}
        <Box
          sx={{ p: 2, display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap', borderBottom: 1, borderColor: 'divider' }}
        >
          <TextField
            size="small"
            sx={{ flex: '1 1 240px', maxWidth: { md: 360 } }}
            inputProps={{ 'aria-label': 'Search renewals' }}
            placeholder="Search customer or contract number"
            value={searchBox.value}
            onChange={(e) => searchBox.onChange(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel id="renewals-product">Product</InputLabel>
            <Select
              labelId="renewals-product"
              label="Product"
              value={String(v.product)}
              onChange={(e) => update({ product: e.target.value })}
            >
              {PRODUCT_FILTERS.map((p) => (
                <MenuItem key={p || 'all'} value={p}>
                  {p || 'All products'}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {anyFilter && (
            <Button size="small" onClick={clearFilters}>
              Clear filters
            </Button>
          )}
          <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }} aria-live="polite">
            {current ? `${visible.length} of ${allRows.length} terms` : ''}
          </Typography>
          <Box
            role="group"
            aria-label="Filter by renewal state"
            sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', width: '100%' }}
          >
            <Chip
              size="small"
              icon={<WarningAmberRounded />}
              label={`Needs attention (${attentionCount})`}
              color={filters.attentionOnly ? 'error' : 'default'}
              variant={filters.attentionOnly ? 'filled' : 'outlined'}
              onClick={() => update({ attention: filters.attentionOnly ? '' : '1' })}
              aria-pressed={filters.attentionOnly}
            />
            {STATE_ORDER.filter((key) => stateCounts[key] || states.includes(key)).map((key) => {
              const on = states.includes(key);
              return (
                <Chip
                  key={key}
                  size="small"
                  label={`${stateLabel(key)} (${stateCounts[key] || 0})`}
                  color={on ? STATE_TONE[key] : 'default'}
                  variant={on ? 'filled' : 'outlined'}
                  onClick={() => toggleState(key)}
                  aria-pressed={on}
                />
              );
            })}
          </Box>
        </Box>
        {narrow ? cards : table}
      </Paper>
      <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1.5 }}>
        A term is listed in the month its end date falls in. Draft contracts are not terms. The renewal state comes from
        the contracts linked as its renewal and their invoices. * zone count from the company's funnel figure.
      </Typography>
    </Box>
  );
};

export default Renewals;
