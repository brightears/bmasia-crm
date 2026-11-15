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
  Skeleton,
  Tooltip,
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
  ReceiptLong,
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
import { formatDate as formatDisplayDate, formatMoney, statusTone, visuallyHidden } from '../theme';
import { PageHeader, EmptyState } from '../components/ui';
import { useListState, optionValues, idFromList } from '../hooks/useListState';
import { useListSearchBox } from '../hooks/useListSearchBox';

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
  const [totalCount, setTotalCount] = useState(0);

  // Search, filters, sort and page live in the address, so a filtered list can be shared as a
  // link and a reload keeps the view. Unknown values in the address fall back to the defaults.
  const list = useListState(
    { q: '', status: '', company: '', payment: '', sort: '-issue_date', page: 0, size: 25 },
    {
      status: optionValues(statusOptions),
      company: idFromList(companies),
      payment: optionValues(paymentMethods),
      sort: optionValues(sortOptions),
    },
    companies.length
  );
  const [search, setSearch] = list.bind('q');
  const [statusFilter, setStatusFilter] = list.bind('status');
  const [companyFilter, setCompanyFilter] = list.bind('company');
  const [paymentMethodFilter, setPaymentMethodFilter] = list.bind('payment');
  const [sortBy, setSortBy] = list.bind('sort');
  const [page, setPage] = list.bind('page');
  const [rowsPerPage, setRowsPerPage] = list.bind('size');
  // The box's own text, written to the address shortly after typing stops.
  const searchBox = useListSearchBox(search, (text) => {
    setSearch(text);
    setPage(0);
  });

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
  const [qbArAccountThb, setQbArAccountThb] = useState('');
  const [qbArAccountUsd, setQbArAccountUsd] = useState('');
  const [qbIncomeAccountSyb, setQbIncomeAccountSyb] = useState('');
  const [qbIncomeAccountBms, setQbIncomeAccountBms] = useState('');
  const [qbIncomeAccountDefault, setQbIncomeAccountDefault] = useState('');
  const [qbTaxAccount, setQbTaxAccount] = useState('');

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
      const companies = await ApiService.getCompaniesSimple();
      setCompanies(companies as any[]);
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
      // Clear these query params to prevent re-opening on navigation (the list's own view stays)
      ['new', 'company', 'contract', 'quote'].forEach((key) => searchParams.delete(key));
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

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
    return formatMoney(value, currency);
  };

  // Entity-specific QB account defaults (from Pom's actual QuickBooks chart of accounts)
  const QB_ENTITY_DEFAULTS: Record<string, {
    ar_thb: string; ar_usd: string;
    income_syb: string; income_bms: string; income_default: string;
    tax: string;
  }> = {
    'BMAsia (Thailand) Co., Ltd.': {
      ar_thb: '1005 น LOCAL ACCOUNTS RECEIVABLE',
      ar_usd: '1005.1 น OVERSEAS ACCOUNTS RECEIVABLE',
      income_syb: '4006.1 น SYB RESELLER',
      income_bms: '4006.2 น BMS MUSIC',
      income_default: '4006.1 น SYB RESELLER',
      tax: '2030.7 น TAX',
    },
    'BMAsia Limited': {
      ar_thb: '',
      ar_usd: '1005 น ACCOUNTS RECEIVABLE',
      income_syb: '4006.1 น SYB RESELLER',
      income_bms: '4006.2 น BMS MUSIC',
      income_default: '4006.1 น SYB RESELLER',
      tax: '',
    },
  };

  const handleQbEntityChange = (entity: string) => {
    setQbEntity(entity);
    const defaults = QB_ENTITY_DEFAULTS[entity];
    if (defaults) {
      setQbArAccountThb(defaults.ar_thb);
      setQbArAccountUsd(defaults.ar_usd);
      setQbIncomeAccountSyb(defaults.income_syb);
      setQbIncomeAccountBms(defaults.income_bms);
      setQbIncomeAccountDefault(defaults.income_default);
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
        ar_account_thb: qbArAccountThb || undefined,
        ar_account_usd: qbArAccountUsd || undefined,
        income_account_syb: qbIncomeAccountSyb || undefined,
        income_account_bms: qbIncomeAccountBms || undefined,
        income_account_default: qbIncomeAccountDefault || undefined,
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
    return formatDisplayDate(dateString);
  };

  const filtersActive = Boolean(search || statusFilter || companyFilter || paymentMethodFilter);
  const hideBelowSm = { display: { xs: 'none', sm: 'table-cell' } };
  const hideBelowMd = { display: { xs: 'none', md: 'table-cell' } };
  const hideBelowLg = { display: { xs: 'none', lg: 'table-cell' } };
  const cellHide = [undefined, undefined, undefined, hideBelowMd, hideBelowSm, undefined, hideBelowLg, undefined];

  return (
    <Box>
      <PageHeader
        title="Invoices"
        subtitle="Bills sent to customers, their payment status and receipts. Invoice numbers come from QuickBooks."
        actions={
          <>
            <Button variant="outlined" startIcon={<GetApp />} onClick={() => setQbExportOpen(true)}>
              Export to QuickBooks
            </Button>
            <Button variant="contained" startIcon={<Add />} onClick={handleCreateInvoice}>
              New Invoice
            </Button>
          </>
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
            sx={{ flex: '1 1 240px', maxWidth: { md: 340 } }}
            inputProps={{ 'aria-label': 'Search invoices' }}
            placeholder="Search by invoice number or company"
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
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="invoices-status-label">Status</InputLabel>
            <Select
              labelId="invoices-status-label"
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
              label="Status"
            >
              {statusOptions.map((status) => (
                <MenuItem key={status.value} value={status.value}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {status.value && (
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
            <InputLabel id="invoices-company-label">Company</InputLabel>
            <Select
              labelId="invoices-company-label"
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
          <FormControl size="small" sx={{ minWidth: 170 }}>
            <InputLabel id="invoices-payment-label">Payment</InputLabel>
            <Select
              labelId="invoices-payment-label"
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
              inputProps={{ 'aria-label': 'Sort invoices' }}
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

        <TableContainer sx={{ borderRadius: 0, position: 'relative' }}>
          <Table aria-label="Invoices">
            <TableHead>
              <TableRow>
                <TableCell>Invoice</TableCell>
                <TableCell>Company</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell sx={hideBelowMd}>Issued</TableCell>
                <TableCell sx={hideBelowSm}>Due</TableCell>
                <TableCell>Status</TableCell>
                <TableCell sx={hideBelowLg}>Payment</TableCell>
                <TableCell align="right"><Box component="span" sx={visuallyHidden}>Actions</Box></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={`skeleton-${i}`}>
                    {cellHide.map((hide, j) => (
                      <TableCell key={j} sx={hide}>
                        <Skeleton width={j === 7 ? 24 : '70%'} />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : invoices.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8}>
                    <EmptyState
                      icon={<ReceiptLong />}
                      title={filtersActive ? 'No invoices match these filters' : 'No invoices yet'}
                      description={filtersActive ? 'Try a different search or clear the filters.' : 'Create the first invoice, or start one from a contract.'}
                    />
                  </TableCell>
                </TableRow>
              ) : (
                invoices.map((invoice) => (
                  <TableRow key={invoice.id} hover sx={{ cursor: 'pointer' }} onClick={() => handleViewInvoice(invoice)}>
                    <TableCell>
                      <Typography sx={{ fontWeight: 600, fontSize: '0.875rem', whiteSpace: 'nowrap' }}>
                        {invoice.invoice_number}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ maxWidth: 260 }}>
                      <Typography variant="body2" sx={{ fontWeight: 500 }} noWrap>
                        {invoice.company_name}
                      </Typography>
                    </TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                      {formatCurrency(invoice.total_amount, invoice.currency)}
                    </TableCell>
                    <TableCell sx={{ ...hideBelowMd, whiteSpace: 'nowrap' }}>{formatDate(invoice.issue_date)}</TableCell>
                    <TableCell sx={{ ...hideBelowSm, whiteSpace: 'nowrap' }}>
                      <Typography variant="body2" sx={{ color: invoice.is_overdue ? 'error.main' : 'text.primary' }}>
                        {formatDate(invoice.due_date)}
                      </Typography>
                      {invoice.is_overdue && (
                        <Typography variant="caption" sx={{ color: 'error.main', display: 'block' }}>
                          {invoice.days_overdue} days overdue
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip label={invoice.status} size="small" color={statusTone(invoice.status)} />
                      {invoice.status === 'Paid' && invoice.receipt_number && (
                        <Typography
                          variant="caption"
                          display="block"
                          sx={{ mt: 0.5, color: invoice.receipt_sent ? 'success.main' : 'text.secondary' }}
                        >
                          {invoice.receipt_sent ? 'Receipt sent' : 'Receipt pending'}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell sx={hideBelowLg}>{invoice.payment_method || '—'}</TableCell>
                    <TableCell align="right">
                      <Tooltip title="More actions">
                        <IconButton
                          size="small"
                          aria-label={`More actions for invoice ${invoice.invoice_number}`}
                          onClick={(e) => { e.stopPropagation(); handleActionMenuOpen(e, invoice); }}
                        >
                          <MoreVert fontSize="small" />
                        </IconButton>
                      </Tooltip>
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
        {actionMenuInvoice?.status === 'Paid' && actionMenuInvoice?.receipt_number && (
          <MenuItem onClick={async () => {
            try {
              const blob = await ApiService.downloadReceiptPDF(actionMenuInvoice.id);
              const url = window.URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = `Receipt_Tax_Invoice_${actionMenuInvoice.receipt_number}.pdf`;
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
              window.URL.revokeObjectURL(url);
            } catch {
              setError('Failed to download receipt');
            }
            setActionMenuAnchor(null);
          }}>
            <ListItemIcon>
              <Receipt fontSize="small" sx={{ color: 'success.main' }} />
            </ListItemIcon>
            <ListItemText>Download Receipt</ListItemText>
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
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                Accounts Receivable (by currency)
              </Typography>
              {qbEntity.includes('Thailand') && (
                <TextField
                  fullWidth
                  size="small"
                  label="AR — THB (Local)"
                  value={qbArAccountThb}
                  onChange={(e) => setQbArAccountThb(e.target.value)}
                  helperText="Debit account for THB invoices"
                />
              )}
              <TextField
                fullWidth
                size="small"
                label={qbEntity.includes('Thailand') ? 'AR — USD (Overseas)' : 'AR — USD'}
                value={qbArAccountUsd}
                onChange={(e) => setQbArAccountUsd(e.target.value)}
                helperText="Debit account for USD invoices"
              />

              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, mt: 1 }}>
                Revenue Accounts (by product)
              </Typography>
              <TextField
                fullWidth
                size="small"
                label="SYB Revenue (Soundtrack)"
                value={qbIncomeAccountSyb}
                onChange={(e) => setQbIncomeAccountSyb(e.target.value)}
                helperText="Credit account for Soundtrack Your Brand line items"
              />
              <TextField
                fullWidth
                size="small"
                label="BMS Revenue (Beat Breeze)"
                value={qbIncomeAccountBms}
                onChange={(e) => setQbIncomeAccountBms(e.target.value)}
                helperText="Credit account for Beat Breeze Music Service line items"
              />
              <TextField
                fullWidth
                size="small"
                label="Default Revenue (Other)"
                value={qbIncomeAccountDefault}
                onChange={(e) => setQbIncomeAccountDefault(e.target.value)}
                helperText="Fallback account for hardware, installation, and other items"
              />

              {qbEntity.includes('Thailand') && (
                <>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, mt: 1 }}>
                    Tax
                  </Typography>
                  <TextField
                    fullWidth
                    size="small"
                    label="VAT Payable"
                    value={qbTaxAccount}
                    onChange={(e) => setQbTaxAccount(e.target.value)}
                    helperText="Credit account for 7% VAT"
                  />
                </>
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
