import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  IconButton,
  InputAdornment,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Menu,
  ListItemIcon,
  ListItemText,
  Divider,
  useTheme,
  useMediaQuery,
  Skeleton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Visibility,
  Delete,
  Send,
  GetApp,
  MoreVert,
  RequestQuote,
  Business,
  Schedule,
  FileCopy,
  CheckCircle,
  Cancel,
  Warning,
  Assignment,
  Sort,
} from '@mui/icons-material';
import { useSearchParams } from 'react-router-dom';
import { Quote, ApiResponse, Company, Contact, Opportunity } from '../types';
import ApiService, { EmailSendData } from '../services/api';
import QuoteForm from '../components/QuoteForm';
import QuoteDetail from '../components/QuoteDetail';
import EmailSendDialog from '../components/EmailSendDialog';
import { formatDate as formatDisplayDate, formatMoney, statusTone, visuallyHidden } from '../theme';
import { PageHeader, EmptyState } from '../components/ui';
import { useListState, optionValues, idFromList } from '../hooks/useListState';
import { useListSearchBox } from '../hooks/useListSearchBox';

const statusOptions = [
  { value: '', label: 'All Status' },
  { value: 'Draft', label: 'Draft', color: '#9e9e9e', icon: <Edit fontSize="small" /> },
  { value: 'Sent', label: 'Sent', color: '#2196f3', icon: <Send fontSize="small" /> },
  { value: 'Accepted', label: 'Accepted', color: '#4caf50', icon: <CheckCircle fontSize="small" /> },
  { value: 'Rejected', label: 'Rejected', color: '#f44336', icon: <Cancel fontSize="small" /> },
  { value: 'Expired', label: 'Expired', color: '#ff9800', icon: <Warning fontSize="small" /> },
];

const sortOptions = [
  { value: '-created_at', label: 'Newest First' },
  { value: 'created_at', label: 'Oldest First' },
  { value: 'valid_until', label: 'Expiring Soonest' },
  { value: '-total_value', label: 'Highest Value' },
  { value: 'quote_number', label: 'Quote Number' },
  { value: 'company__name', label: 'Company' },
];

const Quotes: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [searchParams, setSearchParams] = useSearchParams();

  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  // Search, filters, sort and page live in the address, so Back returns to the same view.
  const list = useListState(
    { q: '', status: '', company: '', sort: '-created_at', page: 0, size: 25 },
    { status: optionValues(statusOptions), company: idFromList(companies), sort: optionValues(sortOptions) },
    companies.length
  );
  const [search, setSearch] = list.bind('q');
  const [page, setPage] = list.bind('page');
  const [rowsPerPage, setRowsPerPage] = list.bind('size');
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [statusFilter, setStatusFilter] = list.bind('status');
  const [companyFilter, setCompanyFilter] = list.bind('company');
  const [sortBy, setSortBy] = list.bind('sort');
  // The box's own text, written to the address shortly after typing stops.
  const searchBox = useListSearchBox(search, (text) => {
    setSearch(text);
    setPage(0);
  });

  // Form state
  const [formOpen, setFormOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedQuote, setSelectedQuote] = useState<Quote | null>(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');

  // Action menu
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [actionMenuQuote, setActionMenuQuote] = useState<Quote | null>(null);

  // Convert to contract dialog
  const [convertDialogOpen, setConvertDialogOpen] = useState(false);
  const [convertingQuote, setConvertingQuote] = useState<Quote | null>(null);

  // Email dialog state
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [emailQuote, setEmailQuote] = useState<Quote | null>(null);
  const [emailContacts, setEmailContacts] = useState<Contact[]>([]);

  // Handle query params for opening create dialog (from dashboard or OpportunityDetail)
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      const opportunityId = searchParams.get('opportunity') || '';
      const companyId = searchParams.get('company') || '';

      // Pre-fill a partial quote with opportunity and company from query params
      if (opportunityId || companyId) {
        setSelectedQuote({
          opportunity: opportunityId,
          company: companyId,
        } as any);
      } else {
        setSelectedQuote(null);
      }
      setFormMode('create');
      setFormOpen(true);
      // Clear query params to avoid re-opening on refresh
      searchParams.delete('new');
      searchParams.delete('opportunity');
      searchParams.delete('company');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // Open the edit form for ?edit=<quote id> (the Edit button on a quote's own page links here,
  // because quotes are edited in this page's form).
  useEffect(() => {
    const editId = searchParams.get('edit');
    if (!editId) return;
    searchParams.delete('edit');
    setSearchParams(searchParams, { replace: true });
    ApiService.getQuote(editId)
      .then((q) => {
        setSelectedQuote(q);
        setFormMode('edit');
        setFormOpen(true);
      })
      .catch((err) => {
        console.error('Could not open quote for editing:', err);
        setError('Could not open that quote for editing.');
      });
  }, [searchParams, setSearchParams]);

  const loadQuotes = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
        ordering: sortBy,
      };

      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (companyFilter) params.company = companyFilter;

      const response: ApiResponse<Quote> = await ApiService.getQuotes(params);
      setQuotes(response.results);
      setTotalCount(response.count);
    } catch (err: any) {
      setError('Failed to load quotes');
      console.error('Quotes error:', err);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, statusFilter, companyFilter, sortBy]);

  const loadCompanies = async () => {
    try {
      const companies = await ApiService.getCompaniesSimple();
      setCompanies(companies as any[]);
    } catch (err) {
      console.error('Failed to load companies:', err);
    }
  };

  const loadContacts = async () => {
    try {
      const response = await ApiService.getContacts({ page_size: 500 });
      setContacts(response.results);
    } catch (err) {
      console.error('Failed to load contacts:', err);
    }
  };

  const loadOpportunities = async () => {
    try {
      const response = await ApiService.getOpportunities({ page_size: 100 });
      setOpportunities(response.results);
    } catch (err) {
      console.error('Failed to load opportunities:', err);
    }
  };

  useEffect(() => {
    loadQuotes();
  }, [loadQuotes]);

  useEffect(() => {
    loadCompanies();
    loadContacts();
    loadOpportunities();
  }, []);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    searchBox.onChange(event.target.value);
  };

  const handleSortChange = (event: any) => {
    setSortBy(event.target.value);
    setPage(0);
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleCreateQuote = () => {
    setSelectedQuote(null);
    setFormMode('create');
    setFormOpen(true);
  };

  const handleEditQuote = (quote: Quote) => {
    setSelectedQuote(quote);
    setFormMode('edit');
    setFormOpen(true);
    setActionMenuAnchor(null);
  };

  const handleViewQuote = (quote: Quote) => {
    setSelectedQuote(quote);
    setDetailOpen(true);
    setActionMenuAnchor(null);
  };

  const handleDeleteQuote = async (quote: Quote) => {
    if (window.confirm(`Are you sure you want to delete quote ${quote.quote_number}?`)) {
      try {
        await ApiService.deleteQuote(quote.id);
        setSuccess('Quote deleted successfully');
        loadQuotes();
      } catch (err) {
        setError('Failed to delete quote');
      }
    }
    setActionMenuAnchor(null);
  };

  const handleSendQuote = async (quote: Quote) => {
    try {
      // Fetch full quote details with company contacts
      const fullQuote = await ApiService.getQuote(quote.id);
      const company = await ApiService.getCompany(fullQuote.company);

      setEmailQuote(fullQuote);
      setEmailContacts(company.contacts || []);
      setEmailDialogOpen(true);
      setActionMenuAnchor(null);
    } catch (err) {
      setError('Failed to load quote details');
      console.error('Error loading quote details:', err);
    }
  };

  const handleEmailSend = async (data: EmailSendData) => {
    if (!emailQuote) return;

    await ApiService.sendQuoteEmail(emailQuote.id, data);
  };

  const handleEmailSuccess = () => {
    setSuccess('Quote email sent successfully');
    loadQuotes();
    // Auto-dismiss success message after 4 seconds
    setTimeout(() => setSuccess(''), 4000);
  };

  const handleDownloadPDF = async (quote: Quote) => {
    try {
      const blob = await ApiService.downloadQuotePDF(quote.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Quote_${quote.quote_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download PDF');
    }
    setActionMenuAnchor(null);
  };

  const handleDuplicateQuote = async (quote: Quote) => {
    try {
      const duplicatedQuote = await ApiService.duplicateQuote(quote.id);
      setSuccess('Quote duplicated successfully');
      loadQuotes();
    } catch (err) {
      setError('Failed to duplicate quote');
    }
    setActionMenuAnchor(null);
  };

  const handleConvertToContract = (quote: Quote) => {
    setConvertingQuote(quote);
    setConvertDialogOpen(true);
    setActionMenuAnchor(null);
  };

  const handleConvertConfirm = async () => {
    if (!convertingQuote) return;

    try {
      await ApiService.convertQuoteToContract(convertingQuote.id);
      setSuccess('Quote converted to contract successfully');
      setConvertDialogOpen(false);
      setConvertingQuote(null);
      loadQuotes();
    } catch (err) {
      setError('Failed to convert quote to contract');
    }
  };

  const handleQuoteSave = (quote: Quote) => {
    setQuotes(prev => {
      const existing = prev.find(q => q.id === quote.id);
      if (existing) {
        return prev.map(q => q.id === quote.id ? quote : q);
      } else {
        return [quote, ...prev];
      }
    });

    if (formMode === 'create') {
      setTotalCount(prev => prev + 1);
    }
  };

  const handleActionMenuOpen = (event: React.MouseEvent<HTMLElement>, quote: Quote) => {
    setActionMenuAnchor(event.currentTarget);
    setActionMenuQuote(quote);
  };

  const handleActionMenuClose = () => {
    setActionMenuAnchor(null);
    setActionMenuQuote(null);
  };

  const formatCurrency = (value: number, currency: string = 'USD'): string => {
    return formatMoney(value, currency);
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '-';
    return formatDisplayDate(dateString);
  };


  return (
    <Box>
      <PageHeader
        title="Quotes"
        subtitle="Price offers sent to customers. Accepted quotes can be turned into contracts."
        actions={
          <Button variant="contained" startIcon={<Add />} onClick={handleCreateQuote}>
            New Quote
          </Button>
        }
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Filters and table in one card */}
      <Paper sx={{ overflow: 'hidden' }}>
        <Box sx={{ p: 2, display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap', borderBottom: 1, borderColor: 'divider' }}>
          <TextField
            sx={{ flex: '1 1 240px', maxWidth: { md: 380 } }}
            inputProps={{ 'aria-label': 'Search quotes' }}
            placeholder="Search by quote number or company"
            value={searchBox.value}
            onChange={handleSearchChange}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
              label="Status"
            >
              {statusOptions.map((status) => (
                <MenuItem key={status.value} value={status.value}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {status.value && status.icon && (
                      <Box sx={{ mr: 1, display: 'flex', color: statusTone(status.value) === 'default' ? 'text.secondary' : `${statusTone(status.value)}.main` }}>
                        {status.icon}
                      </Box>
                    )}
                    {status.label}
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Company</InputLabel>
            <Select
              value={companyFilter}
              onChange={(e) => { setCompanyFilter(e.target.value); setPage(0); }}
              label="Company"
            >
              <MenuItem value="">All Companies</MenuItem>
              {companies.map((company) => (
                <MenuItem key={company.id} value={company.id}>
                  {company.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <Select
              value={sortBy}
              onChange={handleSortChange}
              startAdornment={<Sort sx={{ mr: 0.5, ml: -0.5, color: 'text.secondary', fontSize: 20 }} />}
              sx={{ '& .MuiSelect-select': { display: 'flex', alignItems: 'center' } }}
            >
              {sortOptions.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

      <TableContainer sx={{ borderRadius: 0 }}>
        <Table aria-label="Quotes">
          <TableHead>
            <TableRow>
              <TableCell>Quote</TableCell>
              <TableCell>Company</TableCell>
              <TableCell align="right">Total</TableCell>
              <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>Valid until</TableCell>
              <TableCell>Status</TableCell>
              <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' } }}>Created</TableCell>
              <TableCell align="right"><Box component="span" sx={visuallyHidden}>Actions</Box></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={`skeleton-${i}`}>
                  {Array.from({ length: 7 }).map((__, j) => (
                    <TableCell key={j} sx={j === 3 ? { display: { xs: 'none', sm: 'table-cell' } } : j === 5 ? { display: { xs: 'none', lg: 'table-cell' } } : undefined}>
                      <Skeleton width={j === 6 ? 24 : '70%'} />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : quotes.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7}>
                  <EmptyState
                    icon={<RequestQuote />}
                    title={search || statusFilter || companyFilter ? 'No quotes match these filters' : 'No quotes yet'}
                    description={search || statusFilter || companyFilter ? 'Try a different search or clear the filters.' : 'Create the first quote for a customer.'}
                  />
                </TableCell>
              </TableRow>
            ) : (
              quotes.map((quote) => (
                <TableRow key={quote.id} hover sx={{ cursor: 'pointer' }} onClick={() => handleViewQuote(quote)}>
                  <TableCell>
                    <Typography sx={{ fontWeight: 600, fontSize: '0.875rem', whiteSpace: 'nowrap' }}>
                      {quote.quote_number}
                    </Typography>
                    {quote.contact_name && (
                      <Typography variant="body2" color="text.secondary" noWrap>
                        {quote.contact_name}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ maxWidth: 260 }}>
                    <Typography variant="body2" sx={{ fontWeight: 500 }} noWrap>
                      {quote.company_name}
                    </Typography>
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {formatCurrency(quote.total_value, quote.currency)}
                  </TableCell>
                  <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' }, whiteSpace: 'nowrap' }}>
                    <Typography
                      variant="body2"
                      sx={{ color: quote.is_expired ? 'error.main' : 'text.primary', fontWeight: quote.is_expired ? 600 : 400 }}
                    >
                      {formatDate(quote.valid_until)}
                      {quote.is_expired && ' · expired'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip label={quote.status} size="small" color={statusTone(quote.status)} />
                  </TableCell>
                  <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' }, whiteSpace: 'nowrap' }}>
                    {formatDate(quote.created_at)}
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      aria-label={`Actions for ${quote.quote_number}`}
                      onClick={(e) => { e.stopPropagation(); handleActionMenuOpen(e, quote); }}
                    >
                      <MoreVert fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        rowsPerPageOptions={[10, 25, 50, 100]}
        component="div"
        count={totalCount}
        rowsPerPage={rowsPerPage}
        page={page}
        onPageChange={handleChangePage}
        onRowsPerPageChange={handleChangeRowsPerPage}
      />
      </Paper>

      {/* Action Menu */}
      <Menu
        anchorEl={actionMenuAnchor}
        open={Boolean(actionMenuAnchor)}
        onClose={handleActionMenuClose}
      >
        <MenuItem onClick={() => handleViewQuote(actionMenuQuote!)}>
          <ListItemIcon>
            <Visibility fontSize="small" />
          </ListItemIcon>
          <ListItemText>View Details</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleEditQuote(actionMenuQuote!)}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleDownloadPDF(actionMenuQuote!)}>
          <ListItemIcon>
            <GetApp fontSize="small" />
          </ListItemIcon>
          <ListItemText>Download PDF</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleSendQuote(actionMenuQuote!)}>
          <ListItemIcon>
            <Send fontSize="small" />
          </ListItemIcon>
          <ListItemText>Send Quote</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleDuplicateQuote(actionMenuQuote!)}>
          <ListItemIcon>
            <FileCopy fontSize="small" />
          </ListItemIcon>
          <ListItemText>Duplicate</ListItemText>
        </MenuItem>
        {actionMenuQuote?.status === 'Accepted' && (
          <MenuItem onClick={() => handleConvertToContract(actionMenuQuote!)}>
            <ListItemIcon>
              <Assignment fontSize="small" />
            </ListItemIcon>
            <ListItemText>Convert to Contract</ListItemText>
          </MenuItem>
        )}
        <Divider />
        <MenuItem
          onClick={() => handleDeleteQuote(actionMenuQuote!)}
          sx={{ color: 'error.main' }}
        >
          <ListItemIcon>
            <Delete fontSize="small" sx={{ color: 'error.main' }} />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Quote Form */}
      <QuoteForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSave={handleQuoteSave}
        quote={selectedQuote}
        mode={formMode}
        companies={companies}
        contacts={contacts}
        opportunities={opportunities}
      />

      {/* Quote Detail */}
      <QuoteDetail
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        quote={selectedQuote}
        onQuoteUpdate={loadQuotes}
      />

      {/* Email Send Dialog */}
      {emailQuote && (
        <EmailSendDialog
          open={emailDialogOpen}
          onClose={() => setEmailDialogOpen(false)}
          documentType="quote"
          documentId={emailQuote.id}
          documentNumber={emailQuote.quote_number}
          companyName={emailQuote.company_name}
          contacts={emailContacts}
          onSendSuccess={handleEmailSuccess}
          onSendEmail={handleEmailSend}
          documentDetails={{
            currency: emailQuote.currency,
            totalValue: emailQuote.total_value,
            validUntil: emailQuote.valid_until,
          }}
        />
      )}

      {/* Convert to Contract Dialog */}
      <Dialog open={convertDialogOpen} onClose={() => setConvertDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Convert Quote to Contract</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Are you sure you want to convert this quote to a contract? This action will:
          </Typography>
          <Box component="ul" sx={{ pl: 2, mb: 2 }}>
            <li>Create a new contract with the quote details</li>
            <li>Set the quote status to "Converted"</li>
            <li>Link the contract to the original quote</li>
          </Box>
          <Typography variant="body2" color="text.secondary">
            Quote: <strong>{convertingQuote?.quote_number}</strong>
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConvertDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleConvertConfirm} variant="contained">
            Convert to Contract
          </Button>
        </DialogActions>
      </Dialog>

      {/* Success Snackbar */}
      <Snackbar
        open={!!success}
        autoHideDuration={6000}
        onClose={() => setSuccess('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setSuccess('')} severity="success">
          {success}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Quotes;
