import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  InputAdornment,
  MenuItem,
  Popover,
  Skeleton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  AssignmentOutlined,
  CalendarMonthOutlined,
  ChatBubbleOutline,
  CheckCircleOutline,
  ConfirmationNumberOutlined,
  DeleteOutline,
  DescriptionOutlined,
  EditOutlined,
  ExpandLess,
  ExpandMore,
  GroupsOutlined,
  History,
  HistoryEduOutlined,
  MailOutline,
  PaidOutlined,
  PersonAddAlt1Outlined,
  PhoneOutlined,
  ReceiptLongOutlined,
  RequestQuoteOutlined,
  Search,
  SmartToyOutlined,
  StickyNote2Outlined,
  SyncAlt,
  TaskAlt,
  TrendingUp,
  VolunteerActivismOutlined,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import ApiService from '../../services/api';
import { EmptyState } from '../ui';
import { formatDate, product, status as statusTokens, ink, brand, dark as darkTokens } from '../../theme';
import {
  TimelineCategory,
  TimelineEvent,
  TimelineFacetActor,
  TimelineLink,
  TimelineRecordType,
  changeSentence,
  eventExactTime,
  eventSummary,
  groupByDay,
  hasMore,
  linkHref,
  relativeTime,
} from './timelineModel';

export interface CompanyTimelineProps {
  companyId: string;
  /** Only the events of one record (e.g. on the contract page). */
  record?: { type: TimelineRecordType; id: string };
  pageSize?: number;
  /** Search box, date range, type chips and person filter. Default: shown. */
  showFilters?: boolean;
  /** Open a contact (contacts have no page of their own). */
  onOpenContact?: (contactId: string) => void;
  /** Bump to reload from the top, e.g. after something was added. */
  refreshKey?: number;
  /** Accessible name of the feed. */
  label?: string;
}

const CATEGORY_LABELS: Record<TimelineCategory, string> = {
  note: 'Notes',
  task: 'Tasks',
  email: 'Emails',
  care: 'Client care',
  quote: 'Quotes',
  contract: 'Contracts',
  invoice: 'Invoices',
  opportunity: 'Opportunities',
  ticket: 'Support',
  change: 'Field changes',
};

type Tone = { fg: string; bg: string; solid: string };

/** One colour per kind of event; tinted circle with a dark (light mode) or light (dark mode) icon. */
const TONES: Record<TimelineCategory, Tone> = {
  note: { fg: ink[700], bg: ink[100], solid: ink[400] },
  task: { fg: statusTokens.info.text, bg: statusTokens.info.bg, solid: statusTokens.info.main },
  email: { fg: brand.amberText, bg: brand.amberTint, solid: brand.amber },
  care: { fg: product.beatbreeze.fg, bg: product.beatbreeze.bg, solid: product.beatbreeze.solid },
  quote: { fg: product.soundtrack.fg, bg: product.soundtrack.bg, solid: product.soundtrack.solid },
  contract: { fg: statusTokens.success.text, bg: statusTokens.success.bg, solid: statusTokens.success.main },
  invoice: { fg: statusTokens.warning.text, bg: statusTokens.warning.bg, solid: statusTokens.warning.main },
  opportunity: { fg: '#3B4AA0', bg: '#E9ECFA', solid: '#7C8BE0' },
  ticket: { fg: statusTokens.error.text, bg: statusTokens.error.bg, solid: statusTokens.error.main },
  change: { fg: statusTokens.neutral.text, bg: statusTokens.neutral.bg, solid: ink[400] },
};

const DARK_FG: Record<TimelineCategory, string> = {
  note: '#C9D3DC',
  task: '#8DB9F0',
  email: brand.amber,
  care: product.beatbreeze.solid,
  quote: product.soundtrack.solid,
  contract: '#7FD3A8',
  invoice: '#F5C46E',
  opportunity: '#A9B4F2',
  ticket: '#F59A8F',
  change: darkTokens.textSecondary,
};

const ACTIVITY_ICONS: Record<string, React.ReactElement> = {
  Call: <PhoneOutlined />,
  Meeting: <GroupsOutlined />,
  Email: <MailOutline />,
};

const iconFor = (event: TimelineEvent): React.ReactElement => {
  switch (event.type) {
    case 'note':
      return ACTIVITY_ICONS[event.extra?.note_type] || <StickyNote2Outlined />;
    case 'task_completed':
      return <TaskAlt />;
    case 'task_comment':
    case 'ticket_comment':
      return <ChatBubbleOutline />;
    case 'task_created':
      return <AssignmentOutlined />;
    case 'contract_signed':
      return <HistoryEduOutlined />;
    case 'contract_status':
    case 'opportunity_stage':
      return <SyncAlt />;
    case 'invoice_paid':
      return <PaidOutlined />;
    case 'ticket_resolved':
    case 'ticket_closed':
      return <CheckCircleOutline />;
    case 'record_created':
      return <PersonAddAlt1Outlined />;
    case 'record_deleted':
      return <DeleteOutline />;
    case 'opportunity_activity':
      return ACTIVITY_ICONS[event.extra?.activity_type] || <TrendingUp />;
    default:
      break;
  }
  switch (event.category) {
    case 'email':
      return <MailOutline />;
    case 'care':
      return <VolunteerActivismOutlined />;
    case 'quote':
      return <RequestQuoteOutlined />;
    case 'contract':
      return <DescriptionOutlined />;
    case 'invoice':
      return <ReceiptLongOutlined />;
    case 'opportunity':
      return <TrendingUp />;
    case 'ticket':
      return <ConfirmationNumberOutlined />;
    case 'change':
      return <EditOutlined />;
    default:
      return <StickyNote2Outlined />;
  }
};

const toIsoDay = (d: Date | null): string | undefined => {
  if (!d || Number.isNaN(d.getTime())) return undefined;
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

const useDebounced = <T,>(value: T, ms: number): T => {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
};

/** The company's activity feed: every note, email, task, quote, contract, ticket and change, newest first. */
const CompanyTimeline: React.FC<CompanyTimelineProps> = ({
  companyId,
  record,
  pageSize = 25,
  showFilters = true,
  onOpenContact,
  refreshKey = 0,
  label = 'Activity',
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [more, setMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [moreError, setMoreError] = useState('');
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [actors, setActors] = useState<TimelineFacetActor[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [retry, setRetry] = useState(0);

  const [types, setTypes] = useState<TimelineCategory[]>([]);
  const [searchText, setSearchText] = useState('');
  const search = useDebounced(searchText, 300);
  const [dateFrom, setDateFrom] = useState<Date | null>(null);
  const [dateTo, setDateTo] = useState<Date | null>(null);
  const [actor, setActor] = useState('');
  const [dateAnchor, setDateAnchor] = useState<HTMLElement | null>(null);
  const [draftFrom, setDraftFrom] = useState<Date | null>(null);
  const [draftTo, setDraftTo] = useState<Date | null>(null);

  const request = useRef(0);
  const recordType = record?.type;
  const recordId = record?.id;
  const typesKey = types.join(',');
  const from = toIsoDay(dateFrom);
  const to = toIsoDay(dateTo);

  const baseQuery = useMemo(
    () => ({
      types: typesKey ? (typesKey.split(',') as TimelineCategory[]) : undefined,
      from,
      to,
      actor: actor || undefined,
      q: search || undefined,
      record: recordType && recordId ? { type: recordType, id: recordId } : undefined,
      page_size: pageSize,
    }),
    [typesKey, from, to, actor, search, recordType, recordId, pageSize]
  );

  useEffect(() => {
    const id = ++request.current;
    setLoading(true);
    setError('');
    setMoreError('');
    ApiService.getCompanyTimeline(companyId, { ...baseQuery, facets: showFilters })
      .then((page) => {
        if (id !== request.current) return;
        setEvents(page.results);
        setCursor(page.next_cursor);
        setMore(page.has_more);
        if (page.facets) {
          setCounts(page.facets.types);
          setActors(page.facets.actors);
        }
      })
      .catch(() => {
        if (id !== request.current) return;
        setEvents([]);
        setMore(false);
        setError('Could not load the activity.');
      })
      .finally(() => {
        if (id === request.current) setLoading(false);
      });
  }, [companyId, baseQuery, showFilters, refreshKey, retry]);

  const loadMore = useCallback(() => {
    if (!cursor || loadingMore) return;
    const id = request.current;
    setLoadingMore(true);
    setMoreError('');
    ApiService.getCompanyTimeline(companyId, { ...baseQuery, cursor })
      .then((page) => {
        if (id !== request.current) return;
        setEvents((current) => {
          const seen = new Set(current.map((e) => e.id));
          return [...current, ...page.results.filter((e) => !seen.has(e.id))];
        });
        setCursor(page.next_cursor);
        setMore(page.has_more);
      })
      .catch(() => {
        if (id === request.current) setMoreError('Could not load more activity.');
      })
      .finally(() => setLoadingMore(false));
  }, [companyId, baseQuery, cursor, loadingMore]);

  const toggleType = (key: TimelineCategory) =>
    setTypes((current) => (current.includes(key) ? current.filter((t) => t !== key) : [...current, key]));

  const toggleExpanded = (id: string) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const expandable = events.filter(hasMore);
  const allExpanded = expandable.length > 0 && expandable.every((e) => expanded.has(e.id));
  const filtersActive = types.length > 0 || Boolean(search) || Boolean(from) || Boolean(to) || Boolean(actor);

  const clearFilters = () => {
    setTypes([]);
    setSearchText('');
    setDateFrom(null);
    setDateTo(null);
    setActor('');
  };

  const dateLabel =
    from || to
      ? `${from ? formatDate(from) : 'Any time'} – ${to ? formatDate(to) : 'today'}`
      : 'Any date';

  const tone = (category: TimelineCategory) => {
    const t = TONES[category] || TONES.note;
    return isDark ? { fg: DARK_FG[category], bg: alpha(t.solid, 0.18) } : { fg: t.fg, bg: t.bg };
  };

  const groups = groupByDay(events);
  const chipKeys = (Object.keys(CATEGORY_LABELS) as TimelineCategory[]).filter(
    (key) => types.includes(key) || (counts[key] || 0) > 0
  );

  const renderLink = (link: TimelineLink) => {
    if (record && link.type === record.type && link.id === record.id) return null;
    const href = linkHref(link);
    const key = `${link.type}-${link.id}`;
    const common = {
      size: 'small' as const,
      variant: 'outlined' as const,
      label: link.label,
      sx: { maxWidth: 220, height: 24, '& .MuiChip-label': { px: 1 } },
    };
    if (href) {
      return <Chip key={key} {...common} clickable component={RouterLink} to={href} aria-label={`Open ${link.type} ${link.label}`} />;
    }
    if (link.type === 'contact' && onOpenContact) {
      return <Chip key={key} {...common} clickable onClick={() => onOpenContact(link.id)} aria-label={`Open contact ${link.label}`} />;
    }
    return <Chip key={key} {...common} />;
  };

  const renderEvent = (event: TimelineEvent, isLast: boolean) => {
    const t = tone(event.category);
    const open = expanded.has(event.id);
    const canExpand = hasMore(event);
    const summary = eventSummary(event);
    const detailId = `timeline-detail-${event.id.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
    const links = event.links.map(renderLink).filter(Boolean);
    return (
      <Box component="li" key={event.id} sx={{ display: 'flex', gap: 1.5, position: 'relative', pb: isLast ? 0 : 2 }}>
        {/* rail: icon and the line down to the next event */}
        <Box sx={{ position: 'relative', flex: '0 0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Box
            aria-hidden
            sx={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              display: 'grid',
              placeItems: 'center',
              bgcolor: t.bg,
              color: t.fg,
              '& svg': { fontSize: 18 },
            }}
          >
            {iconFor(event)}
          </Box>
          {!isLast && <Box aria-hidden sx={{ flex: 1, width: '1px', bgcolor: 'divider', mt: 0.5, mb: -2 }} />}
        </Box>

        <Box sx={{ flex: 1, minWidth: 0, pt: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
            <Typography
              component="h4"
              sx={{ fontSize: '0.875rem', fontWeight: 600, lineHeight: 1.45, flex: '1 1 240px', minWidth: 0, overflowWrap: 'anywhere' }}
            >
              {event.title}
            </Typography>
            <Tooltip title={eventExactTime(event)} placement="top" arrow>
              <Typography
                component="time"
                dateTime={event.precision === 'date' && event.date ? event.date : event.occurred_at}
                tabIndex={0}
                variant="caption"
                color="text.secondary"
                sx={{ whiteSpace: 'nowrap', lineHeight: '21px', borderRadius: 0.5, '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' } }}
              >
                {event.precision === 'date' ? 'Date only' : relativeTime(event.occurred_at)}
              </Typography>
            </Tooltip>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap', mt: 0.25 }}>
            {event.actor && (
              <Typography variant="body2" color="text.secondary" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                {event.actor.kind === 'agent' && <SmartToyOutlined sx={{ fontSize: 14 }} aria-hidden />}
                {event.actor.name}
                {event.actor.kind === 'agent' && (
                  <Box component="span" sx={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
                    (agent)
                  </Box>
                )}
              </Typography>
            )}
            {event.actor && summary && (
              <Typography variant="body2" color="text.secondary" aria-hidden>
                ·
              </Typography>
            )}
            {summary && (
              <Typography variant="body2" color="text.secondary" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                {summary}
              </Typography>
            )}
            {links.length > 0 && <Box sx={{ display: 'inline-flex', gap: 0.5, flexWrap: 'wrap' }}>{links}</Box>}
          </Box>

          {event.changes.length === 0 && event.detail && (
            <Typography
              id={detailId}
              variant="body2"
              sx={{
                mt: 0.75,
                whiteSpace: 'pre-line',
                overflowWrap: 'anywhere',
                color: 'text.primary',
                ...(canExpand && !open
                  ? { display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }
                  : {}),
              }}
            >
              {event.detail}
            </Typography>
          )}
          {canExpand && (
            <Button
              size="small"
              onClick={() => toggleExpanded(event.id)}
              aria-expanded={open}
              aria-controls={detailId}
              endIcon={open ? <ExpandLess /> : <ExpandMore />}
              sx={{ mt: 0.25, ml: -1, px: 1, minHeight: 28, color: 'text.secondary', fontWeight: 500 }}
            >
              {event.changes.length
                ? open
                  ? 'Hide changes'
                  : `Show ${event.changes.length} change${event.changes.length > 1 ? 's' : ''}`
                : open
                ? 'Show less'
                : 'Show more'}
            </Button>
          )}
          {event.changes.length > 0 && (
            <Collapse in={open} unmountOnExit>
              <Box
                id={detailId}
                sx={{
                  mt: 0.5,
                  p: 1.5,
                  borderRadius: 1,
                  bgcolor: isDark ? 'rgba(255,255,255,0.04)' : ink[25],
                  border: 1,
                  borderColor: 'divider',
                }}
              >
                <Box component="ul" sx={{ m: 0, pl: 2.5, display: 'grid', gap: 0.5 }}>
                  {event.changes.map((change) => (
                    <Typography component="li" variant="body2" key={change.field} sx={{ overflowWrap: 'anywhere' }}>
                      {changeSentence(change)}
                    </Typography>
                  ))}
                </Box>
              </Box>
            </Collapse>
          )}
        </Box>
      </Box>
    );
  };

  return (
    <Box>
      {showFilters && (
        <Box sx={{ mb: 2.5, display: 'grid', gap: 1.5 }}>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            <TextField
              size="small"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Search activity"
              inputProps={{ 'aria-label': 'Search activity' }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ flex: '1 1 220px', minWidth: 0 }}
            />
            <Button
              variant="outlined"
              color={from || to ? 'primary' : 'inherit'}
              startIcon={<CalendarMonthOutlined />}
              onClick={(e) => {
                setDraftFrom(dateFrom);
                setDraftTo(dateTo);
                setDateAnchor(e.currentTarget);
              }}
              aria-haspopup="dialog"
              sx={{ whiteSpace: 'nowrap', borderColor: 'divider' }}
            >
              {dateLabel}
            </Button>
            {actors.length > 0 && (
              <TextField
                select
                size="small"
                value={actor}
                onChange={(e) => setActor(e.target.value)}
                label="Person"
                sx={{ minWidth: 150 }}
              >
                <MenuItem value="">Anyone</MenuItem>
                {actors.map((a) => (
                  <MenuItem key={a.id || a.name} value={a.id || ''}>
                    {a.name} ({a.count})
                  </MenuItem>
                ))}
              </TextField>
            )}
          </Box>

          <Box role="group" aria-label="Filter by type" sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', alignItems: 'center' }}>
            <Chip
              label="All"
              size="small"
              clickable
              onClick={() => setTypes([])}
              color={types.length === 0 ? 'primary' : 'default'}
              variant={types.length === 0 ? 'filled' : 'outlined'}
              aria-pressed={types.length === 0}
            />
            {chipKeys.map((key) => {
              const selected = types.includes(key);
              const t = tone(key);
              return (
                <Chip
                  key={key}
                  size="small"
                  clickable
                  onClick={() => toggleType(key)}
                  aria-pressed={selected}
                  variant={selected ? 'filled' : 'outlined'}
                  label={
                    <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
                      <Box component="span" aria-hidden sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: t.fg }} />
                      {CATEGORY_LABELS[key]}
                      <Box component="span" sx={{ fontVariantNumeric: 'tabular-nums', opacity: 0.75 }}>
                        {counts[key] || 0}
                      </Box>
                    </Box>
                  }
                  sx={selected ? { bgcolor: t.bg, color: t.fg, borderColor: t.fg, '&:hover': { bgcolor: t.bg } } : undefined}
                />
              );
            })}
            <Box sx={{ flex: 1 }} />
            {filtersActive && (
              <Button size="small" onClick={clearFilters} sx={{ color: 'text.secondary' }}>
                Clear filters
              </Button>
            )}
            {expandable.length > 0 && (
              <Button
                size="small"
                onClick={() => setExpanded(allExpanded ? new Set() : new Set(expandable.map((e) => e.id)))}
                sx={{ color: 'text.secondary' }}
              >
                {allExpanded ? 'Collapse all' : 'Expand all'}
              </Button>
            )}
          </Box>

          <Popover
            open={Boolean(dateAnchor)}
            anchorEl={dateAnchor}
            onClose={() => setDateAnchor(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
            slotProps={{ paper: { sx: { p: 2, mt: 1, width: 300, maxWidth: 'calc(100vw - 32px)' }, role: 'dialog', 'aria-label': 'Date range' } as any }}
          >
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <Stack spacing={2}>
                <Typography variant="subtitle2">Show activity between</Typography>
                <DatePicker
                  label="From"
                  value={draftFrom}
                  onChange={(v) => setDraftFrom(v as Date | null)}
                  format="d MMM yyyy"
                  maxDate={draftTo || undefined}
                  slotProps={{ textField: { size: 'small', fullWidth: true } }}
                />
                <DatePicker
                  label="To"
                  value={draftTo}
                  onChange={(v) => setDraftTo(v as Date | null)}
                  format="d MMM yyyy"
                  minDate={draftFrom || undefined}
                  slotProps={{ textField: { size: 'small', fullWidth: true } }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                  <Button
                    onClick={() => {
                      setDateFrom(null);
                      setDateTo(null);
                      setDateAnchor(null);
                    }}
                    sx={{ color: 'text.secondary' }}
                  >
                    Any date
                  </Button>
                  <Button
                    variant="contained"
                    onClick={() => {
                      setDateFrom(draftFrom);
                      setDateTo(draftTo);
                      setDateAnchor(null);
                    }}
                  >
                    Apply
                  </Button>
                </Box>
              </Stack>
            </LocalizationProvider>
          </Popover>
        </Box>
      )}

      {loading ? (
        <Box aria-busy="true" aria-label="Loading activity" sx={{ display: 'grid', gap: 2.5 }}>
          {[0, 1, 2, 3].map((i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1.5 }}>
              <Skeleton variant="circular" width={32} height={32} />
              <Box sx={{ flex: 1 }}>
                <Skeleton width={i % 2 ? '55%' : '70%'} height={20} />
                <Skeleton width="35%" height={18} />
              </Box>
            </Box>
          ))}
        </Box>
      ) : error ? (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => setRetry((n) => n + 1)}>
              Try again
            </Button>
          }
        >
          {error}
        </Alert>
      ) : events.length === 0 ? (
        <EmptyState
          compact
          icon={<History />}
          title={filtersActive ? 'Nothing matches these filters' : 'No activity yet'}
          description={
            filtersActive
              ? 'Try another type, date range or search.'
              : record
              ? 'Emails, tasks, invoices and changes for this record will appear here.'
              : 'Notes, emails, tasks, quotes, contracts, tickets and changes for this company will appear here.'
          }
          action={
            filtersActive ? (
              <Button variant="outlined" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Box component="section" aria-label={label}>
          {groups.map((group, gi) => (
            <Box key={group.day} sx={{ mb: gi === groups.length - 1 ? 0 : 3 }}>
              <Typography
                component="h3"
                variant="overline"
                color="text.secondary"
                sx={{ display: 'block', mb: 1.5, letterSpacing: '0.06em', lineHeight: 1.6 }}
              >
                {group.label}
              </Typography>
              <Box component="ol" sx={{ listStyle: 'none', m: 0, p: 0 }} aria-label={`${label}, ${group.label}`}>
                {group.events.map((event, i) => renderEvent(event, i === group.events.length - 1))}
              </Box>
            </Box>
          ))}

          {moreError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {moreError}
            </Alert>
          )}
          {more && (
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
              <Button
                variant="outlined"
                onClick={loadMore}
                disabled={loadingMore}
                startIcon={loadingMore ? <CircularProgress size={16} /> : undefined}
                sx={{ minWidth: 160 }}
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </Button>
            </Box>
          )}
          {!more && events.length > pageSize && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 3, textAlign: 'center' }}>
              That is everything.
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
};

export default CompanyTimeline;

export type { TimelineRecordType };
