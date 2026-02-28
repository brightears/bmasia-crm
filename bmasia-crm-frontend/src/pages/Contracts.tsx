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
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Visibility,
  Delete,
  MoreVert,
  Business,
  CalendarToday,
  Assignment,
  Warning,
  Refresh,
  GetApp,
  Email,
  Autorenew,
  Sort,
} from '@mui/icons-material';
import { useSearchParams } from 'react-router-dom';
import { Contract, ApiResponse, Contact } from '../types';
import ApiService, { EmailSendData } from '../services/api';
import ContractForm from '../components/ContractForm';
import ContractDetail from '../components/ContractDetail';
import EmailSendDialog from '../components/EmailSendDialog';

// Statuses where the contract is locked (terminal states only — Active is editable for date/term changes)
const LOCKED_STATUSES = ['Renewed', 'Expired', 'Cancelled'];

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'Draft', label: 'Draft', color: '#9e9e9e' },
  { value: 'Sent', label: 'Sent', color: '#ff9800' },
  { value: 'Active', label: 'Active', color: '#4caf50' },
  { value: 'Renewed', label: 'Renewed', color: '#2196f3' },
  { value: 'Expired', label: 'Expired', color: '#757575' },
  { value: 'Cancelled', label: 'Cancelled', color: '#f44336' },
];

const typeOptions = [
  { value: '', label: 'All Types' },
  { value: 'Annual', label: 'Annual' },
  { value: 'Monthly', label: 'Monthly' },
  { value: 'One-time', label: 'One-time' },
  { value: 'Custom', label: 'Custom' },
];

const sortOptions = [
  { value: '-start_date', label: 'Start Date (Newest)' },
  { value: 'start_date', label: 'Start Date (Oldest)' },
  { value: 'end_date', label: 'Ending Soonest' },
  { value: '-value', label: 'Highest Value' },
  { value: 'company__name', label: 'Company' },
  { value: 'contract_number', label: 'Contract Number' },
];

const Contracts: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [searchParams, setSearchParams] = useSearchParams();

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
  const [typeFilter, setTypeFilter] = useState('');
  const [sortBy, setSortBy] = useState('-start_date');

  // Form state
  const [formOpen, setFormOpen] = useState(false);
  const [selectedContract, setSelectedContract] = useState<Contract | null>(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');

  // Detail dialog state
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailContractId, setDetailContractId] = useState<string | null>(null);

  // Action menu
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [actionMenuContract, setActionMenuContract] = useState<Contract | null>(null);

  // Email dialog state
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [emailContract, setEmailContract] = useState<Contract | null>(null);
  const [emailContacts, setEmailContacts] = useState<Contact[]>([]);

  // Pre-fill state for ContractForm (from query params)
  const [initialCompanyId, setInitialCompanyId] = useState('');
  const [initialQuoteId, setInitialQuoteId] = useState('');

  // Handle query param for opening create dialog (from dashboard or QuoteDetail)
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setInitialCompanyId(searchParams.get('company') || '');
      setInitialQuoteId(searchParams.get('quote') || '');
      setSelectedContract(null);
      setFormMode('create');
      setFormOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const loadContracts = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
        ordering: sortBy,
      };

      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (typeFilter) params.contract_type = typeFilter;

      const response: ApiResponse<Contract> = await ApiService.getContracts(params);
      setContracts(response.results);
      setTotalCount(response.count);
    } catch (err: any) {
      setError('Failed to load contracts');
      console.error('Contracts error:', err);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, statusFilter, typeFilter, sortBy]);

  useEffect(() => {
    loadContracts();
  }, [loadContracts]);

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

  const handleCreateContract = () => {
    setSelectedContract(null);
    setFormMode('create');
    setFormOpen(true);
  };

  const handleEditContract = (contract: Contract) => {
    setSelectedContract(contract);
    setFormMode('edit');
    setFormOpen(true);
    setActionMenuAnchor(null);
  };

  const handleViewContract = (contract: Contract) => {
    setDetailContractId(contract.id);
    setDetailOpen(true);
    setActionMenuAnchor(null);
  };

  const handleDeleteContract = async (contract: Contract) => {
    if (window.confirm(`Are you sure you want to delete contract "${contract.contract_number}"?`)) {
      try {
        await ApiService.deleteContract(contract.id);
        loadContracts();
      } catch (err) {
        setError('Failed to delete contract');
      }
    }
    setActionMenuAnchor(null);
  };

  const handleContractSave = (contract: Contract) => {
    const isNew = formMode === 'create';
    setContracts(prev => {
      const existing = prev.find(c => c.id === contract.id);
      if (existing) {
        return prev.map(c => c.id === contract.id ? contract : c);
      } else {
        return [contract, ...prev];
      }
    });

    // If we're in create mode, increment total count
    if (isNew) {
      setTotalCount(prev => prev + 1);
    }

    // Show success confirmation
    setSuccess(isNew ? 'Contract created successfully' : 'Contract updated successfully');
    setTimeout(() => setSuccess(''), 4000);
  };

  const handleActionMenuOpen = (event: React.MouseEvent<HTMLElement>, contract: Contract) => {
    setActionMenuAnchor(event.currentTarget);
    setActionMenuContract(contract);
  };

  const handleActionMenuClose = () => {
    setActionMenuAnchor(null);
    setActionMenuContract(null);
  };

  const formatCurrency = (value: number, currency = 'USD'): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    const statusOption = statusOptions.find(s => s.value === status);
    if (!statusOption?.color) return 'default';

    const colorMap: { [key: string]: any } = {
      '#9e9e9e': 'default',
      '#ff9800': 'warning',
      '#2196f3': 'info',
      '#4caf50': 'success',
      '#757575': 'default',
      '#f44336': 'error',
    };

    return colorMap[statusOption.color] || 'default';
  };

  const handleSendEmail = async (contract: Contract) => {
    try {
      // Fetch full contract details with company contacts
      const fullContract = await ApiService.getContract(contract.id);
      const company = await ApiService.getCompany(fullContract.company);

      setEmailContract(fullContract);
      setEmailContacts(company.contacts || []);
      setEmailDialogOpen(true);
      setActionMenuAnchor(null);
    } catch (err) {
      setError('Failed to load contract details');
      console.error('Error loading contract details:', err);
    }
  };

  const handleEmailSend = async (data: EmailSendData) => {
    if (!emailContract) return;

    await ApiService.sendContractEmail(emailContract.id, data);
  };

  const handleEmailSuccess = () => {
    setSuccess('Contract email sent successfully');
    loadContracts();
    // Auto-dismiss success message after 4 seconds
    setTimeout(() => setSuccess(''), 4000);
  };

  const handleDownloadPDF = async (contract: Contract) => {
    try {
      const blob = await ApiService.downloadContractPDF(contract.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Contract_${contract.contract_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download PDF');
    }
    setActionMenuAnchor(null);
  };

  const handleDuplicateForRenewal = async (contract: Contract) => {
    if (window.confirm(`Create renewal contract for "${contract.contract_number}"?\n\nThis will:\n• Create a new Active contract starting ${contract.end_date}\n• Mark the current contract as Renewed`)) {
      try {
        const result = await ApiService.duplicateForRenewal(contract.id);
        setSuccess(`Renewal contract ${result.new_contract.contract_number} created successfully`);
        loadContracts();
      } catch (err) {
        setError('Failed to create renewal contract');
      }
    }
    setActionMenuAnchor(null);
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Contracts
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreateContract}
          size={isMobile ? "small" : "medium"}
        >
          New Contract
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Filters */}
      <Paper sx={{ mb: 2 }}>
        <Box sx={{ p: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            fullWidth
            placeholder="Search contracts..."
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
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
              label="Status"
            >
              {statusOptions.map((status) => (
                <MenuItem key={status.value} value={status.value}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {status.value && status.color && (
                      <Box
                        sx={{
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          backgroundColor: status.color,
                          mr: 1,
                        }}
                      />
                    )}
                    {status.label}
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Type</InputLabel>
            <Select
              value={typeFilter}
              onChange={(e) => { setTypeFilter(e.target.value); setPage(0); }}
              label="Type"
            >
              {typeOptions.map((type) => (
                <MenuItem key={type.value} value={type.value}>
                  {type.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 220 }}>
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

      {/* Contracts Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Contract Number</TableCell>
              <TableCell>Company</TableCell>
              <TableCell>Start Date</TableCell>
              <TableCell>End Date</TableCell>
              <TableCell>Value</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Renewal</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={9} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : contracts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} align="center">
                  <Box sx={{ py: 4 }}>
                    <Assignment sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No contracts found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search || statusFilter || typeFilter ? 'Try adjusting your filters' : 'Start by creating your first contract'}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              contracts.map((contract) => (
                <TableRow key={contract.id} hover sx={{ cursor: 'pointer' }} onClick={() => handleViewContract(contract)}>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {contract.contract_number}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Business sx={{ mr: 1, color: 'text.secondary' }} />
                      <Typography variant="body2">
                        {contract.company_name}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <CalendarToday sx={{ fontSize: 16, color: 'text.secondary', mr: 0.5 }} />
                      <Typography variant="body2">
                        {formatDate(contract.start_date)}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{
                        color: contract.is_expiring_soon ? 'warning.main' : 'text.primary',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      <CalendarToday sx={{ fontSize: 16, mr: 0.5 }} />
                      {formatDate(contract.end_date)}
                      {contract.is_expiring_soon && (
                        <Warning sx={{ fontSize: 16, ml: 0.5, color: 'warning.main' }} />
                      )}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatCurrency(contract.value, contract.currency)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={contract.status}
                      size="small"
                      color={getStatusColor(contract.status)}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {contract.contract_type}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Refresh sx={{ fontSize: 16, color: 'text.secondary', mr: 0.5 }} />
                      <Typography variant="body2">
                        {contract.auto_renew ? 'Auto' : 'Manual'}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      onClick={(e) => { e.stopPropagation(); handleActionMenuOpen(e, contract); }}
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

      {/* Contract Form */}
      <ContractForm
        open={formOpen}
        onClose={() => { setFormOpen(false); setInitialCompanyId(''); setInitialQuoteId(''); }}
        onSave={handleContractSave}
        contract={selectedContract}
        mode={formMode}
        initialCompanyId={initialCompanyId}
        initialQuoteId={initialQuoteId}
      />

      {/* Contract Detail */}
      <ContractDetail
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        onEdit={handleEditContract}
        onContractUpdated={(updated) => {
          setContracts(prev => prev.map(c => c.id === updated.id ? updated : c));
        }}
        contractId={detailContractId}
      />

      {/* Email Send Dialog */}
      {emailContract && (
        <EmailSendDialog
          open={emailDialogOpen}
          onClose={() => setEmailDialogOpen(false)}
          documentType="contract"
          documentId={emailContract.id}
          documentNumber={emailContract.contract_number}
          companyName={emailContract.company_name}
          contacts={emailContacts}
          onSendSuccess={handleEmailSuccess}
          onSendEmail={handleEmailSend}
          documentDetails={{
            currency: emailContract.currency,
            totalValue: emailContract.value,
            startDate: emailContract.start_date,
            endDate: emailContract.end_date,
          }}
        />
      )}

      {/* Action Menu */}
      <Menu
        anchorEl={actionMenuAnchor}
        open={Boolean(actionMenuAnchor)}
        onClose={handleActionMenuClose}
      >
        <MenuItem onClick={() => handleViewContract(actionMenuContract!)}>
          <ListItemIcon>
            <Visibility fontSize="small" />
          </ListItemIcon>
          <ListItemText>View Details</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => handleEditContract(actionMenuContract!)}
          disabled={LOCKED_STATUSES.includes(actionMenuContract?.status || '')}
        >
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>
            Edit
            {LOCKED_STATUSES.includes(actionMenuContract?.status || '') && (
              <Typography component="span" variant="caption" color="text.secondary"> (locked)</Typography>
            )}
          </ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleSendEmail(actionMenuContract!)}>
          <ListItemIcon>
            <Email fontSize="small" />
          </ListItemIcon>
          <ListItemText>Send Email</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleDownloadPDF(actionMenuContract!)}>
          <ListItemIcon>
            <GetApp fontSize="small" />
          </ListItemIcon>
          <ListItemText>Download PDF</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => handleDuplicateForRenewal(actionMenuContract!)}
          disabled={actionMenuContract?.status !== 'Active'}
        >
          <ListItemIcon>
            <Autorenew fontSize="small" />
          </ListItemIcon>
          <ListItemText>Duplicate for Renewal</ListItemText>
        </MenuItem>
        <Divider />
        <MenuItem
          onClick={() => handleDeleteContract(actionMenuContract!)}
          sx={{ color: 'error.main' }}
        >
          <ListItemIcon>
            <Delete fontSize="small" sx={{ color: 'error.main' }} />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Success Snackbar */}
      {success && (
        <Alert severity="success" sx={{ position: 'fixed', bottom: 24, right: 24, zIndex: 9999 }}>
          {success}
        </Alert>
      )}
    </Box>
  );
};

export default Contracts;
