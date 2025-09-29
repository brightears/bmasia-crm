import React, { useState, useEffect } from 'react';
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
  GridLegacy as Grid,
  Menu,
  ListItemIcon,
  ListItemText,
  Divider,
  useTheme,
  useMediaQuery,
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
  AttachMoney,
  Business,
  Schedule,
  FileCopy,
  CheckCircle,
  Cancel,
  Pending,
  Warning,
  Assignment,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV2';
import { Quote, ApiResponse, Company, Contact, Opportunity } from '../types';
import ApiService from '../services/api';
import QuoteForm from '../components/QuoteForm';
import QuoteDetail from '../components/QuoteDetail';

const statusOptions = [
  { value: '', label: 'All Status' },
  { value: 'Draft', label: 'Draft', color: '#9e9e9e', icon: <Edit fontSize="small" /> },
  { value: 'Sent', label: 'Sent', color: '#2196f3', icon: <Send fontSize="small" /> },
  { value: 'Accepted', label: 'Accepted', color: '#4caf50', icon: <CheckCircle fontSize="small" /> },
  { value: 'Rejected', label: 'Rejected', color: '#f44336', icon: <Cancel fontSize="small" /> },
  { value: 'Expired', label: 'Expired', color: '#ff9800', icon: <Warning fontSize="small" /> },
];

const Quotes: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [companyFilter, setCompanyFilter] = useState('');
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);

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

  useEffect(() => {
    loadQuotes();
    loadCompanies();
    loadContacts();
    loadOpportunities();
  }, [page, rowsPerPage, search, statusFilter, companyFilter, startDate, endDate]);

  const loadQuotes = async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
      };

      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (companyFilter) params.company = companyFilter;
      if (startDate) params.valid_from_after = startDate.toISOString().split('T')[0];
      if (endDate) params.valid_until_before = endDate.toISOString().split('T')[0];

      const response: ApiResponse<Quote> = await ApiService.getQuotes(params);
      setQuotes(response.results);
      setTotalCount(response.count);
    } catch (err: any) {
      setError('Failed to load quotes');
      console.error('Quotes error:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadCompanies = async () => {
    try {
      const response = await ApiService.getCompanies({ page_size: 100 });
      setCompanies(response.results);
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

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
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
      await ApiService.sendQuote(quote.id);
      setSuccess('Quote sent successfully');
      loadQuotes();
    } catch (err) {
      setError('Failed to send quote');
    }
    setActionMenuAnchor(null);
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

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: string): string => {
    return statusOptions.find(s => s.value === status)?.color || '#2196f3';
  };

  const clearFilters = () => {
    setStatusFilter('');
    setCompanyFilter('');
    setStartDate(null);
    setEndDate(null);
    setSearch('');
    setPage(0);
  };

  const renderFilters = () => (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Grid container spacing={2} alignItems="center">
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            size="small"
            placeholder="Search quotes..."
            value={search}
            onChange={handleSearchChange}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={2}>
          <FormControl fullWidth size="small">
            <InputLabel>Status</InputLabel>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              label="Status"
            >
              {statusOptions.map((status) => (
                <MenuItem key={status.value} value={status.value}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {status.value && (
                      <Box sx={{ mr: 1, color: status.color }}>
                        {status.icon}
                      </Box>
                    )}
                    {status.label}
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12} sm={6} md={2}>
          <FormControl fullWidth size="small">
            <InputLabel>Company</InputLabel>
            <Select
              value={companyFilter}
              onChange={(e) => setCompanyFilter(e.target.value)}
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
        </Grid>

        <Grid item xs={12} sm={6} md={2}>
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              label="Valid From"
              value={startDate}
              onChange={setStartDate}
              slotProps={{
                textField: {
                  size: 'small',
                  fullWidth: true,
                },
              }}
            />
          </LocalizationProvider>
        </Grid>

        <Grid item xs={12} sm={6} md={2}>
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              label="Valid Until"
              value={endDate}
              onChange={setEndDate}
              slotProps={{
                textField: {
                  size: 'small',
                  fullWidth: true,
                },
              }}
            />
          </LocalizationProvider>
        </Grid>

        <Grid item xs={12} sm={6} md={1}>
          <Button
            variant="outlined"
            onClick={clearFilters}
            size="small"
            sx={{ minWidth: 'auto' }}
          >
            Clear
          </Button>
        </Grid>
      </Grid>
    </Paper>
  );

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Quotes
          </Typography>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleCreateQuote}
            size={isMobile ? "small" : "medium"}
          >
            New Quote
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {renderFilters()}

        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Quote Number</TableCell>
                <TableCell>Company</TableCell>
                <TableCell>Contact</TableCell>
                <TableCell>Total Value</TableCell>
                <TableCell>Valid Until</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Created Date</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={8} align="center">
                    <CircularProgress />
                  </TableCell>
                </TableRow>
              ) : quotes.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} align="center">
                    <Box sx={{ py: 4 }}>
                      <RequestQuote sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                      <Typography variant="h6" color="text.secondary">
                        No quotes found
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {search || statusFilter || companyFilter ? 'Try adjusting your filters' : 'Start by creating your first quote'}
                      </Typography>
                    </Box>
                  </TableCell>
                </TableRow>
              ) : (
                quotes.map((quote) => (
                  <TableRow key={quote.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight="medium">
                        {quote.quote_number}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Business sx={{ mr: 1, color: 'text.secondary', fontSize: 16 }} />
                        <Typography variant="body2">
                          {quote.company_name}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {quote.contact_name || '-'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <AttachMoney sx={{ fontSize: 16, color: 'text.secondary' }} />
                        <Typography variant="body2">
                          {formatCurrency(quote.total_value)}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{
                        color: quote.is_expired ? 'error.main' : 'text.primary'
                      }}>
                        {formatDate(quote.valid_until)}
                        {quote.is_expired && (
                          <Typography variant="caption" sx={{ color: 'error.main', display: 'block' }}>
                            Expired
                          </Typography>
                        )}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={quote.status}
                        size="small"
                        sx={{
                          backgroundColor: getStatusColor(quote.status),
                          color: 'white',
                          fontWeight: 600
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Schedule sx={{ fontSize: 16, color: 'text.secondary', mr: 0.5 }} />
                        <Typography variant="body2">
                          {formatDate(quote.created_at)}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={(e) => handleActionMenuOpen(e, quote)}
                      >
                        <MoreVert />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <TablePagination
            rowsPerPageOptions={[10, 25, 50, 100]}
            component="div"
            count={totalCount}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
          />
        </TableContainer>

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
    </LocalizationProvider>
  );
};

export default Quotes;