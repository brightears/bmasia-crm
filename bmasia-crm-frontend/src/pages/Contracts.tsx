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
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Visibility,
  Delete,
  FilterList,
  MoreVert,
  Business,
  CalendarToday,
  AttachMoney,
  Assignment,
  Warning,
  Refresh,
  GetApp,
  Email,
  Autorenew,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useSearchParams } from 'react-router-dom';
import { Contract, ApiResponse, Contact } from '../types';
import ApiService, { EmailSendData } from '../services/api';
import ContractForm from '../components/ContractForm';
import ContractDetail from '../components/ContractDetail';
import EmailSendDialog from '../components/EmailSendDialog';

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'Active', label: 'Active', color: '#4caf50' },
  { value: 'Renewed', label: 'Renewed', color: '#2196f3' },
  { value: 'Expired', label: 'Expired', color: '#9e9e9e' },
  { value: 'Cancelled', label: 'Cancelled', color: '#f44336' },
];

const typeOptions = [
  { value: '', label: 'All Types' },
  { value: 'Annual', label: 'Annual' },
  { value: 'Monthly', label: 'Monthly' },
  { value: 'One-time', label: 'One-time' },
  { value: 'Custom', label: 'Custom' },
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
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);

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

  // Handle query param for opening create dialog from dashboard
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setSelectedContract(null);
      setFormMode('create');
      setFormOpen(true);
      // Clear the query param to avoid re-opening on refresh
      searchParams.delete('new');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    loadContracts();
  }, [page, rowsPerPage, search, statusFilter, typeFilter, startDate, endDate]);

  const loadContracts = async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
      };

      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (typeFilter) params.contract_type = typeFilter;
      if (startDate) params.start_date_after = startDate.toISOString().split('T')[0];
      if (endDate) params.end_date_before = endDate.toISOString().split('T')[0];

      const response: ApiResponse<Contract> = await ApiService.getContracts(params);
      setContracts(response.results);
      setTotalCount(response.count);
    } catch (err: any) {
      setError('Failed to load contracts');
      console.error('Contracts error:', err);
    } finally {
      setLoading(false);
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
    setContracts(prev => {
      const existing = prev.find(c => c.id === contract.id);
      if (existing) {
        return prev.map(c => c.id === contract.id ? contract : c);
      } else {
        return [contract, ...prev];
      }
    });

    // If we're in create mode, increment total count
    if (formMode === 'create') {
      setTotalCount(prev => prev + 1);
    }
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
      '#2196f3': 'info',
      '#4caf50': 'success',
      '#f44336': 'error',
    };

    return colorMap[statusOption.color] || 'default';
  };

  const clearFilters = () => {
    setStatusFilter('');
    setTypeFilter('');
    setStartDate(null);
    setEndDate(null);
    setSearch('');
    setPage(0);
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

  const renderFilters = () => (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Grid container spacing={2} alignItems="center">
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            size="small"
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
                  {status.value && status.color && (
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Box
                        sx={{
                          width: 12,
                          height: 12,
                          borderRadius: '50%',
                          backgroundColor: status.color,
                          mr: 1,
                        }}
                      />
                    </Box>
                  )}
                  {status.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12} sm={6} md={2}>
          <FormControl fullWidth size="small">
            <InputLabel>Type</InputLabel>
            <Select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              label="Type"
            >
              {typeOptions.map((type) => (
                <MenuItem key={type.value} value={type.value}>
                  {type.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12} sm={6} md={2}>
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              label="Start Date"
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
              label="End Date"
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
        {renderFilters()}

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
                <TableCell>Renewal Date</TableCell>
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
                  <TableRow key={contract.id} hover>
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
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <AttachMoney sx={{ fontSize: 16, color: 'text.secondary' }} />
                        <Typography variant="body2">
                          {formatCurrency(contract.value, contract.currency)}
                        </Typography>
                      </Box>
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
                        onClick={(e) => handleActionMenuOpen(e, contract)}
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
          onClose={() => setFormOpen(false)}
          onSave={handleContractSave}
          contract={selectedContract}
          mode={formMode}
        />

        {/* Contract Detail */}
        <ContractDetail
          open={detailOpen}
          onClose={() => setDetailOpen(false)}
          onEdit={handleEditContract}
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
          <MenuItem onClick={() => handleEditContract(actionMenuContract!)}>
            <ListItemIcon>
              <Edit fontSize="small" />
            </ListItemIcon>
            <ListItemText>Edit</ListItemText>
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
    </LocalizationProvider>
  );
};

export default Contracts;