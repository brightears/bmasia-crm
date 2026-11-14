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

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

/**
 * One search box for the whole CRM. Uses the existing list endpoints with their `search`
 * parameter (read-only), five results per record type. Opens with Ctrl+K / ⌘K.
 */
const GlobalSearch: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const requestId = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const runSearch = useCallback(async (q: string) => {
    const id = ++requestId.current;
    setLoading(true);
    const params = { search: q, page_size: PER_GROUP };
    const [companies, contacts, contracts, quotes, invoices] = await Promise.allSettled([
      ApiService.getCompanies(params),
      ApiService.getContacts(params),
      ApiService.getContracts(params),
      ApiService.getQuotes(params),
      ApiService.getInvoices(params),
    ]);
    if (id !== requestId.current) return; // a newer search has started

    const list: SearchResult[] = [];
    const rows = <T,>(r: PromiseSettledResult<{ results?: T[] }>): T[] =>
      r.status === 'fulfilled' ? (r.value.results || []).slice(0, PER_GROUP) : [];

    rows<any>(companies).forEach((c) =>
      list.push({
        key: `company-${c.id}`,
        group: 'Companies',
        icon: <BusinessOutlined />,
        title: c.name,
        detail: [c.city, c.country].filter(Boolean).join(', '),
        to: `/companies/${c.id}`,
      })
    );
    rows<any>(contacts).forEach((c) =>
      list.push({
        key: `contact-${c.id}`,
        group: 'Contacts',
        icon: <PersonOutline />,
        title: c.name,
        detail: [c.title, c.company_name].filter(Boolean).join(' · '),
        // Contacts have no page of their own yet: open their company.
        to: `/companies/${c.company}`,
      })
    );
    rows<any>(contracts).forEach((c) =>
      list.push({
        key: `contract-${c.id}`,
        group: 'Contracts',
        icon: <HistoryEduOutlined />,
        title: c.contract_number,
        detail: [c.company_name, c.status, formatMoney(c.value, c.currency)].filter(Boolean).join(' · '),
        to: `/contracts/${c.id}`,
      })
    );
    rows<any>(quotes).forEach((q) =>
      list.push({
        key: `quote-${q.id}`,
        group: 'Quotes',
        icon: <RequestQuoteOutlined />,
        title: q.quote_number,
        detail: [q.company_name, q.status].filter(Boolean).join(' · '),
        to: `/quotes/${q.id}`,
      })
    );
    rows<any>(invoices).forEach((inv) =>
      list.push({
        key: `invoice-${inv.id}`,
        group: 'Invoices',
        icon: <ReceiptLongOutlined />,
        title: inv.invoice_number,
        detail: [inv.company_name, inv.status, formatMoney(inv.total_amount, inv.currency)].filter(Boolean).join(' · '),
        // Invoices have no page of their own: open the contract, or else the company.
        to: inv.contract ? `/contracts/${inv.contract}` : `/companies/${inv.company}`,
      })
    );

    setResults(list);
    setActive(0);
    setLoading(false);
  }, []);

  // Debounced search while typing
  useEffect(() => {
    const q = query.trim();
    if (q.length < MIN_CHARS) {
      requestId.current++;
      setResults([]);
      setLoading(false);
      return;
    }
    const t = setTimeout(() => runSearch(q), 250);
    return () => clearTimeout(t);
  }, [query, runSearch]);

  const close = () => {
    setOpen(false);
    setQuery('');
    setResults([]);
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
    } else if (e.key === 'Enter' && results[active]) {
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
              number.
            </Typography>
          ) : !loading && results.length === 0 ? (
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
        </Box>
      </Dialog>
    </>
  );
};

export default GlobalSearch;
