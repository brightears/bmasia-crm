import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  ButtonBase,
  CircularProgress,
  Dialog,
  IconButton,
  InputAdornment,
  InputBase,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Search,
  BusinessOutlined,
  PersonOutline,
  HistoryEduOutlined,
  RequestQuoteOutlined,
  ReceiptLongOutlined,
  Close,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import ApiService from '../services/api';
import { formatMoney } from '../theme';
import { buildNavGroups, filterNavForRole } from './navigation';
import { useAuth } from '../contexts/AuthContext';
import { canAccessModule } from '../utils/permissions';

// Menu pages the user's menu shows, searchable by their current name and by the name they had
// before the redesign.
const pagesFor = (role?: string | null) =>
  filterNavForRole(buildNavGroups(0), role).flatMap((g) =>
    g.items.map((item) => ({ ...item, groupTitle: g.title || 'Home' }))
  );

const matchPages = (q: string, role?: string | null): SearchResult[] => {
  const needle = q.toLowerCase();
  return pagesFor(role).filter(
    (p) => p.text.toLowerCase().includes(needle) || (p.formerly || '').toLowerCase().includes(needle)
  )
    .slice(0, PER_GROUP)
    .map((p) => ({
      key: `page-${p.path}`,
      group: 'Pages',
      icon: p.icon,
      title: p.text,
      detail: p.formerly ? `${p.groupTitle} · formerly “${p.formerly}”` : p.groupTitle,
      to: p.path,
    }));
};

interface SearchResult {
  key: string;
  group: string;
  icon: React.ReactNode;
  title: string;
  detail: string;
  to: string;
}

const MIN_CHARS = 2;
const PER_GROUP = 5;

// Record types searched, each with the page-access module that guards its page.
interface Source {
  module: string;
  group: string;
  fetch: (params: any) => Promise<any>;
  toResult: (row: any) => SearchResult;
}

const SOURCES: Source[] = [
  {
    module: 'companies',
    group: 'Companies',
    fetch: (p) => ApiService.getCompanies(p),
    toResult: (c) => ({
      key: `company-${c.id}`,
      group: 'Companies',
      icon: <BusinessOutlined />,
      title: c.name,
      detail: [c.city, c.country].filter(Boolean).join(', '),
      to: `/companies/${c.id}`,
    }),
  },
  {
    module: 'contacts',
    group: 'Contacts',
    fetch: (p) => ApiService.getContacts(p),
    toResult: (c) => ({
      key: `contact-${c.id}`,
      group: 'Contacts',
      icon: <PersonOutline />,
      title: c.name,
      detail: [c.title, c.company_name].filter(Boolean).join(' · '),
      // Contacts have no page of their own yet: open their company.
      to: `/companies/${c.company}`,
    }),
  },
  {
    module: 'contracts',
    group: 'Contracts',
    fetch: (p) => ApiService.getContracts(p),
    toResult: (c) => ({
      key: `contract-${c.id}`,
      group: 'Contracts',
      icon: <HistoryEduOutlined />,
      title: c.contract_number,
      detail: [c.company_name, c.status, formatMoney(c.value, c.currency)].filter(Boolean).join(' · '),
      to: `/contracts/${c.id}`,
    }),
  },
  {
    module: 'quotes',
    group: 'Quotes',
    fetch: (p) => ApiService.getQuotes(p),
    toResult: (q) => ({
      key: `quote-${q.id}`,
      group: 'Quotes',
      icon: <RequestQuoteOutlined />,
      title: q.quote_number,
      detail: [q.company_name, q.status].filter(Boolean).join(' · '),
      to: `/quotes/${q.id}`,
    }),
  },
  {
    module: 'invoices',
    group: 'Invoices',
    fetch: (p) => ApiService.getInvoices(p),
    toResult: (inv) => ({
      key: `invoice-${inv.id}`,
      group: 'Invoices',
      icon: <ReceiptLongOutlined />,
      title: inv.invoice_number,
      detail: [inv.company_name, inv.status, formatMoney(inv.total_amount, inv.currency)].filter(Boolean).join(' · '),
      // Invoices have no page of their own: open the contract, or else the company.
      to: inv.contract ? `/contracts/${inv.contract}` : `/companies/${inv.company}`,
    }),
  },
];

const GROUP_ORDER = ['Pages', ...SOURCES.map((src) => src.group)];

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

/**
 * One search box for the whole CRM. Uses the existing list endpoints with their `search`
 * parameter (read-only), five results per record type. Opens with Ctrl+K / ⌘K.
 */
const GlobalSearch: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const navigate = useNavigate();
  const { user } = useAuth();
  const role = user?.role;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  // Results per group, in arrival order; shown in the fixed GROUP_ORDER.
  const [groupRows, setGroupRows] = useState<Record<string, SearchResult[]>>({});
  const [failedGroups, setFailedGroups] = useState<string[]>([]);
  const [pending, setPending] = useState(0);
  const [searchedCount, setSearchedCount] = useState(0);
  // The query the shown results belong to (Enter is ignored while they belong to an older one).
  const [resultsFor, setResultsFor] = useState('');
  const loading = pending > 0;
  const allFailed = !loading && failedGroups.length > 0 && failedGroups.length === searchedCount;
  const results = useMemo(() => GROUP_ORDER.flatMap((g) => groupRows[g] || []), [groupRows]);
  const [active, setActive] = useState(0);
  const requestId = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Inside a rich-text editor Ctrl/⌘K means "add link": leave it to the editor.
      const target = e.target as HTMLElement | null;
      if (target && (target.isContentEditable || target.closest?.('.ql-editor, [contenteditable="true"]'))) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const runSearch = useCallback(
    (q: string) => {
      const id = ++requestId.current;
      const params = { search: q, page_size: PER_GROUP };
      // Only record types whose pages this user may open are searched.
      const allowed = SOURCES.filter((src) => canAccessModule(user, src.module));
      const pages = matchPages(q, role);

      setResultsFor(q);
      setActive(0);
      setFailedGroups([]);
      setGroupRows({ Pages: pages });
      setPending(allowed.length);
      setSearchedCount(allowed.length);
      if (allowed.length === 0) return;

      // Each type is shown as soon as it arrives; one slow type does not hold back the rest.
      allowed.forEach((src) => {
        src
          .fetch(params)
          .then((res: any) => {
            if (id !== requestId.current) return; // a newer search has started
            const rows = (res?.results || []).slice(0, PER_GROUP).map(src.toResult);
            setGroupRows((prev) => ({ ...prev, [src.group]: rows }));
          })
          .catch(() => {
            if (id !== requestId.current) return;
            setFailedGroups((prev) => [...prev, src.group]);
          })
          .finally(() => {
            if (id !== requestId.current) return;
            setPending((n) => n - 1);
          });
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [user, role]
  );

  // Debounced search while typing
  useEffect(() => {
    const q = query.trim();
    if (q.length < MIN_CHARS) {
      requestId.current++;
      setGroupRows({});
      setFailedGroups([]);
      setPending(0);
      setResultsFor('');
      return;
    }
    const t = setTimeout(() => runSearch(q), 250);
    return () => clearTimeout(t);
  }, [query, runSearch]);

  const close = () => {
    setOpen(false);
    setQuery('');
    requestId.current++;
    setGroupRows({});
    setFailedGroups([]);
    setPending(0);
    setResultsFor('');
  };

  const go = (r: SearchResult) => {
    close();
    navigate(r.to);
  };

  const onInputKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter' && results[active] && resultsFor === query.trim()) {
      e.preventDefault();
      go(results[active]);
    }
  };

  const grouped = useMemo(() => {
    const groups: { name: string; items: { r: SearchResult; index: number }[] }[] = [];
    results.forEach((r, index) => {
      let g = groups.find((x) => x.name === r.group);
      if (!g) {
        g = { name: r.group, items: [] };
        groups.push(g);
      }
      g.items.push({ r, index });
    });
    return groups;
  }, [results]);

  const q = query.trim();

  return (
    <>
      {/* Trigger in the top bar */}
      {isMobile ? (
        <IconButton aria-label="Search" onClick={() => setOpen(true)}>
          <Search fontSize="small" />
        </IconButton>
      ) : (
        <ButtonBase
          onClick={() => setOpen(true)}
          aria-label="Search the CRM"
          sx={{
            width: { sm: 260, md: 340, lg: 420 },
            height: 38,
            px: 1.5,
            gap: 1,
            justifyContent: 'flex-start',
            borderRadius: 2,
            border: 1,
            borderColor: 'divider',
            bgcolor: 'background.default',
            color: 'text.secondary',
            '&:hover': { borderColor: 'text.secondary' },
          }}
        >
          <Search fontSize="small" />
          <Typography sx={{ fontSize: '0.875rem', flex: 1, textAlign: 'left' }} noWrap>
            Search companies, contacts, contracts…
          </Typography>
          <Box
            component="kbd"
            sx={{
              fontFamily: 'inherit',
              fontSize: '0.75rem',
              px: 0.75,
              py: '1px',
              borderRadius: 1,
              border: 1,
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            {isMac ? '⌘K' : 'Ctrl K'}
          </Box>
        </ButtonBase>
      )}

      <Dialog
        open={open}
        onClose={close}
        fullWidth
        maxWidth="sm"
        fullScreen={isMobile}
        PaperProps={{ sx: { alignSelf: { sm: 'flex-start' }, mt: { sm: 10 } } }}
        // Put the cursor in the search box as soon as the dialog has opened.
        TransitionProps={{ onEntered: () => inputRef.current?.focus() }}
        aria-label="Search the CRM"
      >
        <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1, borderBottom: 1, borderColor: 'divider' }}>
          <InputBase
            autoFocus
            inputRef={inputRef}
            fullWidth
            placeholder="Search by name or number"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKey}
            inputProps={{ 'aria-label': 'Search by name or number', role: 'combobox', 'aria-expanded': results.length > 0 }}
            startAdornment={
              <InputAdornment position="start">
                <Search sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            }
            endAdornment={loading ? <CircularProgress size={18} /> : null}
            sx={{ fontSize: '1rem', py: 1 }}
          />
          <IconButton aria-label="Close search" onClick={close} sx={{ ml: 1 }}>
            <Close fontSize="small" />
          </IconButton>
        </Box>

        <Box sx={{ maxHeight: { sm: '60vh' }, overflowY: 'auto' }}>
          {q.length < MIN_CHARS ? (
            <Typography color="text.secondary" sx={{ p: 3, fontSize: '0.875rem' }}>
              Type at least two letters. Finds companies, contacts, contracts, quotes and invoices by name or
              number, and pages of the CRM by their current or former name.
            </Typography>
          ) : !loading && results.length === 0 && allFailed ? (
            <Typography color="error" sx={{ p: 3, fontSize: '0.875rem' }} role="alert">
              Search failed. Check your connection and try again.
            </Typography>
          ) : !loading && results.length === 0 && failedGroups.length === 0 ? (
            <Typography color="text.secondary" sx={{ p: 3, fontSize: '0.875rem' }}>
              Nothing found for “{q}”.
            </Typography>
          ) : (
            <List dense disablePadding role="listbox">
              {grouped.map((g) => (
                <li key={g.name}>
                  <ul style={{ padding: 0 }}>
                    <ListSubheader sx={{ lineHeight: '32px', fontSize: '0.75rem', fontWeight: 600, bgcolor: 'background.paper' }}>
                      {g.name}
                    </ListSubheader>
                    {g.items.map(({ r, index }) => (
                      <ListItemButton
                        key={r.key}
                        role="option"
                        aria-selected={index === active}
                        selected={index === active}
                        onMouseEnter={() => setActive(index)}
                        onClick={() => go(r)}
                        sx={{ mx: 1, borderRadius: 1.5 }}
                      >
                        <ListItemIcon sx={{ minWidth: 36, color: 'text.secondary', '& svg': { fontSize: 20 } }}>
                          {r.icon}
                        </ListItemIcon>
                        <ListItemText
                          primary={r.title}
                          secondary={r.detail}
                          primaryTypographyProps={{ fontWeight: 600, fontSize: '0.875rem', noWrap: true }}
                          secondaryTypographyProps={{ fontSize: '0.8125rem', noWrap: true }}
                        />
                      </ListItemButton>
                    ))}
                  </ul>
                </li>
              ))}
            </List>
          )}
          {q.length >= MIN_CHARS && failedGroups.length > 0 && !allFailed && (
            <Typography color="error" sx={{ px: 3, py: 1.5, fontSize: '0.8125rem' }} role="status">
              Could not search {failedGroups.map((g) => g.toLowerCase()).join(', ')}.
            </Typography>
          )}
        </Box>
      </Dialog>
    </>
  );
};

export default GlobalSearch;
