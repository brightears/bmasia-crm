import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
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
  Payment,
  MoreVert,
  Receipt,
  Business,
  Schedule,
  AccountBalance,
  Warning,
  CheckCircle,
  Cancel,
  Sort,
} from '@mui/icons-material';
import { Invoice, ApiResponse, Company, Contract } from '../types';
import ApiService from '../services/api';
import InvoiceForm from '../components/InvoiceForm';
import InvoiceDetail from '../components/InvoiceDetail';

const statusOptions = [
  { value: '', label: 'All Status' },
  { value: 'Draft', label: 'Draft', color: '#9e9e9e', icon: <Edit fontSize="small" /> },
  { value: 'Sent', label: 'Sent', color: '#2196f3', icon: <Send fontSize="small" /> },
  { value: 'Paid', label: 'Paid', color: '#4caf50', icon: <CheckCircle fontSize="small" /> },
  { value: 'Overdue', label: 'Overdue', color: '#f44336', icon: <Warning fontSize="small" /> },
  { value: 'Cancelled', label: 'Cancelled', color: '#f44336', icon: <Cancel fontSize="small" /> },
  { value: 'Refunded', label: 'Refunded', color: '#9c27b0', icon: <AccountBalance fontSize="small" /> },
];

const paymentMethods = [
  { value: '', label: 'All Payment Methods' },
  { value: 'Cash', label: 'Cash' },
  { value: 'Check', label: 'Check' },
  { value: 'Credit Card', label: 'Credit Card' },
  { value: 'Bank Transfer', label: 'Bank Transfer' },
  { value: 'Online Payment', label: 'Online Payment' },
  { value: 'Other', label: 'Other' },
];

const sortOptions = [
  { value: '-issue_date', label: 'Newest (Issue Date)' },
  { value: 'issue_date', label: 'Oldest (Issue Date)' },
  { value: 'due_date', label: 'Due Date Soonest' },
  { value: '-total_amount', label: 'Highest Amount' },
  { value: 'company__name', label: 'Company' },
];

const Invoices: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
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
  const [paymentMethodFilter, setPaymentMethodFilter] = useState('');
  const [sortBy, setSortBy] = useState('-issue_date');

  // Form state
  const [formOpen, setFormOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');

  // Action menu
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [actionMenuInvoice, setActionMenuInvoice] = useState<Invoice | null>(null);

  // Pre-fill from query params (e.g., from Contract/Quote detail)
  const [initialCompanyId, setInitialCompanyId] = useState('');
  const [initialContractId, setInitialContractId] = useState('');

  // Payment dialog
  const [paymentDialogOpen, setPaymentDialogOpen] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('');
  const [transactionId, setTransactionId] = useState('');
  const [paymentNotes, setPaymentNotes] = useState('');

  // QuickBooks export dialog
  const [qbExportOpen, setQbExportOpen] = useState(false);
  const [qbExporting, setQbExporting] = useState(false);
  const [qbEntity, setQbEntity] = useState('');
  const [qbStatus, setQbStatus] = useState('Sent');
  const [qbDateFrom, setQbDateFrom] = useState('');
  const [qbDateTo, setQbDateTo] = useState('');
  const [qbArAccount, setQbArAccount] = useState('Accounts Receivable');
  const [qbIncomeAccount, setQbIncomeAccount] = useState('Service Revenue');
  const [qbTaxAccount, setQbTaxAccount] = useState('VAT Payable');

  const loadInvoices = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
        search: search || undefined,
        status: statusFilter || undefined,
        company: companyFilter || undefined,
        payment_method: paymentMethodFilter || undefined,
        ordering: sortBy,
      };

      const response: ApiResponse<Invoice> = await ApiService.getInvoices(params);
      setInvoices(response.results);
      setTotalCount(response.count);
    } catch (err: any) {
      setError('Failed to load invoices');
      console.error('Invoices error:', err);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, statusFilter, companyFilter, paymentMethodFilter, sortBy]);

  const loadCompanies = async () => {
    try {
      const response = await ApiService.getCompanies({ page_size: 1000, ordering: 'name' });
      setCompanies(response.results);
    } catch (err) {
      console.error('Failed to load companies:', err);
    }
  };

  const loadContracts = async () => {
    try {
      const response = await ApiService.getContracts({ page_size: 100 });
      setContracts(response.results);
    } catch (err) {
      console.error('Failed to load contracts:', err);
    }
  };

  useEffect(() => {
    loadInvoices();
  }, [loadInvoices]);

  useEffect(() => {
    loadCompanies();
    loadContracts();
  }, []);

  // Auto-open invoice form from query params (e.g., from Contract/Quote detail)
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setInitialCompanyId(searchParams.get('company') || '');
      setInitialContractId(searchParams.get('contract') || '');
      setFormMode('create');
      setSelectedInvoice(null);
      setFormOpen(true);
      // Clear query params to prevent re-opening on navigation
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(0);
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

  const handleCreateInvoice = () => {
    setSelectedInvoice(null);
    setFormMode('create');
    setFormOpen(true);
  };

  const handleEditInvoice = (invoice: Invoice) => {
    setSelectedInvoice(invoice);
    setFormMode('edit');
    setFormOpen(true);
    setActionMenuAnchor(null);
  };

  const handleViewInvoice = (invoice: Invoice) => {
    setSelectedInvoice(invoice);
    setDetailOpen(true);
    setActionMenuAnchor(null);
  };

  const handleDeleteInvoice = async (invoice: Invoice) => {
    if (window.confirm(`Are you sure you want to delete invoice ${invoice.invoice_number}?`)) {
      try {
        await ApiService.deleteInvoice(invoice.id);
        setSuccess('Invoice deleted successfully');
        loadInvoices();
      } catch (err) {
        setError('Failed to delete invoice');
      }
    }
    setActionMenuAnchor(null);
  };

  const handleSendInvoice = async (invoice: Invoice) => {
    try {
      await ApiService.sendInvoice(invoice.id);
      setSuccess('Invoice sent successfully');
      loadInvoices();
    } catch (err) {
      setError('Failed to send invoice');
    }
    setActionMenuAnchor(null);
  };

  const handleMarkAsSent = async (invoice: Invoice) => {
    try {
      await ApiService.updateInvoice(invoice.id, { status: 'Sent' });
      setSuccess('Invoice marked as sent');
      loadInvoices();
    } catch (err) {
      setError('Failed to update invoice status');
    }
    setActionMenuAnchor(null);
  };

  const handleDownloadPDF = async (invoice: Invoice) => {
    try {
      const blob = await ApiService.downloadInvoicePDF(invoice.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Invoice_${invoice.invoice_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download PDF');
    }
    setActionMenuAnchor(null);
  };

  const handleMarkAsPaid = (invoice: Invoice) => {
    setSelectedInvoice(invoice);
    setPaymentDialogOpen(true);
    setActionMenuAnchor(null);
  };

  const handlePaymentSubmit = async () => {
    if (!selectedInvoice) return;

    try {
      await ApiService.markInvoicePaid(selectedInvoice.id, {
        payment_method: paymentMethod,
        transaction_id: transactionId,
        notes: paymentNotes,
      });
      setSuccess('Invoice marked as paid successfully');
      setPaymentDialogOpen(false);
      setPaymentMethod('');
      setTransactionId('');
      setPaymentNotes('');
      loadInvoices();
    } catch (err) {
      setError('Failed to mark invoice as paid');
    }
  };

  const handleInvoiceSave = (invoice: Invoice) => {
    setInvoices(prev => {
      const existing = prev.find(i => i.id === invoice.id);
      if (existing) {
        return prev.map(i => i.id === invoice.id ? invoice : i);
      } else {
        return [invoice, ...prev];
      }
    });

    if (formMode === 'create') {
      setTotalCount(prev => prev + 1);
    }
  };

  const handleActionMenuOpen = (event: React.MouseEvent<HTMLElement>, invoice: Invoice) => {
    setActionMenuAnchor(event.currentTarget);
    setActionMenuInvoice(invoice);
  };

  const handleActionMenuClose = () => {
    setActionMenuAnchor(null);
    setActionMenuInvoice(null);
  };

  const formatCurrency = (value: number, currency: string = 'USD'): string => {
    const locale = currency === 'THB' ? 'th-TH' : 'en-US';
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(value);
  };

  // Entity-specific QB account defaults
  const QB_ENTITY_DEFAULTS: Record<string, { ar: string; income: string; tax: string }> = {
    'BMAsia (Thailand) Co., Ltd.': { ar: 'Accounts Receivable', income: 'Service Revenue', tax: 'VAT Payable' },
    'BMAsia Limited': { ar: 'Accounts Receivable', income: 'Service Revenue', tax: '' },
  };

  const handleQbEntityChange = (entity: string) => {
    setQbEntity(entity);
    const defaults = QB_ENTITY_DEFAULTS[entity];
    if (defaults) {
      setQbArAccount(defaults.ar);
      setQbIncomeAccount(defaults.income);
      setQbTaxAccount(defaults.tax);
    }
  };

  const handleQBExport = async () => {
    if (!qbEntity) {
      setError('Please select a billing entity');
      return;
    }
    try {
      setQbExporting(true);
      const blob = await ApiService.exportQuickBooks({
        billing_entity: qbEntity,
        status: qbStatus || undefined,
        date_from: qbDateFrom || undefined,
        date_to: qbDateTo || undefined,
        ar_account: qbArAccount,
        income_account: qbIncomeAccount,
        tax_account: qbTaxAccount || undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const entityAbbr = qbEntity.includes('Thailand') ? 'BMAT' : 'BMAL';
      const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      link.download = `invoices-${entityAbbr}-${dateStr}.iif`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      setQbExportOpen(false);
      setSuccess('QuickBooks IIF file exported successfully');
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError('No invoices match the selected filters');
      } else if (err.response?.status === 400) {
        setError('Please select a billing entity');
      } else {
        setError('Failed to export invoices. Please try again.');
      }
    } finally {
      setQbExporting(false);
    }
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: string): string => {
    return statusOptions.find(s => s.value === status)?.color || '#2196f3';
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Invoices
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<GetApp />}
            onClick={() => setQbExportOpen(true)}
            sx={{
              borderColor: '#FFA500',
              color: '#FFA500',
              '&:hover': { borderColor: '#FF8C00', bgcolor: 'rgba(255, 165, 0, 0.08)' },
            }}
          >
            Export to QuickBooks
          </Button>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleCreateInvoice}
          >
            New Invoice
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Search and Filters */}
      <Paper sx={{ mb: 2 }}>
        <Box sx={{ p: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            fullWidth
            placeholder="Search invoices..."
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
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
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
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Payment</InputLabel>
            <Select
              value={paymentMethodFilter}
              onChange={(e) => { setPaymentMethodFilter(e.target.value); setPage(0); }}
              label="Payment"
            >
              {paymentMethods.map((method) => (
                <MenuItem key={method.value} value={method.value}>
                  {method.label}
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
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Invoice Number</TableCell>
              <TableCell>Company</TableCell>
              <TableCell>Amount</TableCell>
              <TableCell>Issue Date</TableCell>
              <TableCell>Due Date</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Payment Method</TableCell>
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
            ) : invoices.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <Box sx={{ py: 4 }}>
                    <Receipt sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No invoices found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search || statusFilter || companyFilter || paymentMethodFilter ?
                        'Try adjusting your filters' :
                        'Start by creating your first invoice'
                      }
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              invoices.map((invoice) => (
                <TableRow key={invoice.id} hover sx={{ cursor: 'pointer' }} onClick={() => handleViewInvoice(invoice)}>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {invoice.invoice_number}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Business sx={{ mr: 1, color: 'text.secondary', fontSize: 16 }} />
                      <Typography variant="body2">
                        {invoice.company_name}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatCurrency(invoice.total_amount, invoice.currency)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Schedule sx={{ fontSize: 16, color: 'text.secondary', mr: 0.5 }} />
                      <Typography variant="body2">
                        {formatDate(invoice.issue_date)}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{
                      color: invoice.is_overdue ? 'error.main' : 'text.primary'
                    }}>
                      {formatDate(invoice.due_date)}
                      {invoice.is_overdue && (
                        <Typography variant="caption" sx={{ color: 'error.main', display: 'block' }}>
                          {invoice.days_overdue} days overdue
                        </Typography>
                      )}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={invoice.status}
                      size="small"
                      sx={{
                        backgroundColor: getStatusColor(invoice.status),
                        color: 'white',
                        fontWeight: 600
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {invoice.payment_method || '-'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      onClick={(e) => { e.stopPropagation(); handleActionMenuOpen(e, invoice); }}
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
        <MenuItem onClick={() => handleViewInvoice(actionMenuInvoice!)}>
          <ListItemIcon>
            <Visibility fontSize="small" />
          </ListItemIcon>
          <ListItemText>View Details</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleEditInvoice(actionMenuInvoice!)}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleDownloadPDF(actionMenuInvoice!)}>
          <ListItemIcon>
            <GetApp fontSize="small" />
          </ListItemIcon>
          <ListItemText>Download PDF</ListItemText>
        </MenuItem>
        {actionMenuInvoice?.status === 'Draft' && (
          <MenuItem onClick={() => handleSendInvoice(actionMenuInvoice!)}>
            <ListItemIcon>
              <Send fontSize="small" />
            </ListItemIcon>
            <ListItemText>Send via Email</ListItemText>
          </MenuItem>
        )}
        {actionMenuInvoice?.status === 'Draft' && (
          <MenuItem onClick={() => handleMarkAsSent(actionMenuInvoice!)}>
            <ListItemIcon>
              <CheckCircle fontSize="small" />
            </ListItemIcon>
            <ListItemText>Mark as Sent</ListItemText>
          </MenuItem>
        )}
        {(actionMenuInvoice?.status === 'Sent' || actionMenuInvoice?.status === 'Overdue') && (
          <MenuItem onClick={() => handleMarkAsPaid(actionMenuInvoice!)}>
            <ListItemIcon>
              <Payment fontSize="small" />
            </ListItemIcon>
            <ListItemText>Mark as Paid</ListItemText>
          </MenuItem>
        )}
        <Divider />
        <MenuItem
          onClick={() => handleDeleteInvoice(actionMenuInvoice!)}
          sx={{ color: 'error.main' }}
        >
          <ListItemIcon>
            <Delete fontSize="small" sx={{ color: 'error.main' }} />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Invoice Form */}
      <InvoiceForm
        open={formOpen}
        onClose={() => {
          setFormOpen(false);
          setInitialCompanyId('');
          setInitialContractId('');
        }}
        onSave={handleInvoiceSave}
        invoice={selectedInvoice}
        mode={formMode}
        companies={companies}
        contracts={contracts}
        initialCompanyId={initialCompanyId}
        initialContractId={initialContractId}
      />

      {/* Invoice Detail */}
      <InvoiceDetail
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        invoice={selectedInvoice}
        onInvoiceUpdate={loadInvoices}
      />

      {/* Payment Dialog */}
      <Dialog open={paymentDialogOpen} onClose={() => setPaymentDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Mark Invoice as Paid</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Payment Method</InputLabel>
              <Select
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value)}
                label="Payment Method"
              >
                {paymentMethods.slice(1).map((method) => (
                  <MenuItem key={method.value} value={method.value}>
                    {method.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              fullWidth
              label="Transaction ID"
              value={transactionId}
              onChange={(e) => setTransactionId(e.target.value)}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Notes"
              value={paymentNotes}
              onChange={(e) => setPaymentNotes(e.target.value)}
              multiline
              rows={3}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPaymentDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handlePaymentSubmit}
            variant="contained"
            disabled={!paymentMethod}
          >
            Mark as Paid
          </Button>
        </DialogActions>
      </Dialog>

      {/* QuickBooks Export Dialog */}
      <Dialog
        open={qbExportOpen}
        onClose={() => setQbExportOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Export to QuickBooks</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Export invoices as an IIF file for import into QuickBooks Pro 2016.
            Each entity exports to a separate file for its QuickBooks company.
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <FormControl fullWidth size="small" required error={!qbEntity}>
              <InputLabel>Billing Entity *</InputLabel>
              <Select
                value={qbEntity}
                onChange={(e) => handleQbEntityChange(e.target.value)}
                label="Billing Entity *"
              >
                <MenuItem value="BMAsia (Thailand) Co., Ltd.">BMAsia Thailand (THB)</MenuItem>
                <MenuItem value="BMAsia Limited">BMAsia Limited (USD)</MenuItem>
              </Select>
            </FormControl>

            <FormControl fullWidth size="small">
              <InputLabel>Invoice Status</InputLabel>
              <Select
                value={qbStatus}
                onChange={(e) => setQbStatus(e.target.value)}
                label="Invoice Status"
              >
                <MenuItem value="">All Statuses</MenuItem>
                <MenuItem value="Sent">Sent</MenuItem>
                <MenuItem value="Paid">Paid</MenuItem>
                <MenuItem value="Overdue">Overdue</MenuItem>
                <MenuItem value="Sent,Paid,Overdue">Sent + Paid + Overdue</MenuItem>
              </Select>
            </FormControl>

            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                fullWidth
                size="small"
                label="Date From"
                type="date"
                value={qbDateFrom}
                onChange={(e) => setQbDateFrom(e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                fullWidth
                size="small"
                label="Date To"
                type="date"
                value={qbDateTo}
                onChange={(e) => setQbDateTo(e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Box>

            <Typography variant="subtitle2" sx={{ mt: 1, mb: -1, color: 'text.secondary' }}>
              QuickBooks Account Mapping
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <TextField
                fullWidth
                size="small"
                label="Accounts Receivable (AR)"
                value={qbArAccount}
                onChange={(e) => setQbArAccount(e.target.value)}
                helperText="Debit account — must match your QB AR account name exactly"
              />
              <TextField
                fullWidth
                size="small"
                label="Sales / Income Account"
                value={qbIncomeAccount}
                onChange={(e) => setQbIncomeAccount(e.target.value)}
                helperText="Credit account for revenue — must match your QB income account name exactly"
              />
              {qbEntity.includes('Thailand') && (
                <TextField
                  fullWidth
                  size="small"
                  label="VAT Payable Account"
                  value={qbTaxAccount}
                  onChange={(e) => setQbTaxAccount(e.target.value)}
                  helperText="Credit account for 7% VAT — must match your QB tax liability account name"
                />
              )}
            </Box>

            <Alert severity="info" sx={{ mt: 1 }}>
              Customer names in the CRM must match your QuickBooks customer list exactly for successful import.
            </Alert>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setQbExportOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleQBExport}
            disabled={qbExporting || !qbEntity}
            startIcon={qbExporting ? <CircularProgress size={16} /> : <GetApp />}
            sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
          >
            {qbExporting ? 'Exporting...' : 'Export IIF File'}
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

export default Invoices;
