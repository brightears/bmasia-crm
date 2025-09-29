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
  Grid,
  Tabs,
  Tab,
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
  TableView,
  ViewKanban,
  Handshake,
  TrendingUp,
  AttachMoney,
  Person,
  Business,
  Schedule,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV2';
import { Opportunity, ApiResponse, User } from '../types';
import ApiService from '../services/api';
import OpportunityForm from '../components/OpportunityForm';
import OpportunityPipeline from '../components/OpportunityPipeline';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`opportunities-tabpanel-${index}`}
      aria-labelledby={`opportunities-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ pt: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const stageOptions = [
  { value: '', label: 'All Stages' },
  { value: 'Contacted', label: 'Contacted', color: '#2196f3' },
  { value: 'Quotation Sent', label: 'Quotation Sent', color: '#ff9800' },
  { value: 'Contract Sent', label: 'Contract Sent', color: '#9c27b0' },
  { value: 'Won', label: 'Won', color: '#4caf50' },
  { value: 'Lost', label: 'Lost', color: '#f44336' },
];

const Opportunities: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);
  const [currentTab, setCurrentTab] = useState(0);

  // Filters
  const [stageFilter, setStageFilter] = useState('');
  const [ownerFilter, setOwnerFilter] = useState('');
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [leadSourceFilter, setLeadSourceFilter] = useState('');

  // Form state
  const [formOpen, setFormOpen] = useState(false);
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');

  // Action menu
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [actionMenuOpportunity, setActionMenuOpportunity] = useState<Opportunity | null>(null);

  useEffect(() => {
    loadOpportunities();
    loadUsers();
  }, [page, rowsPerPage, search, stageFilter, ownerFilter, startDate, endDate, leadSourceFilter]);

  const loadOpportunities = async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
      };

      if (search) params.search = search;
      if (stageFilter) params.stage = stageFilter;
      if (ownerFilter) params.owner = ownerFilter;
      if (leadSourceFilter) params.lead_source = leadSourceFilter;
      if (startDate) params.created_after = startDate.toISOString().split('T')[0];
      if (endDate) params.created_before = endDate.toISOString().split('T')[0];

      const response: ApiResponse<Opportunity> = await ApiService.getOpportunities(params);
      setOpportunities(response.results);
      setTotalCount(response.count);
    } catch (err: any) {
      setError('Failed to load opportunities');
      console.error('Opportunities error:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      const response = await ApiService.getUsers({ page_size: 100 });
      setUsers(response.results);
    } catch (err) {
      console.error('Failed to load users:', err);
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

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  const handleCreateOpportunity = () => {
    setSelectedOpportunity(null);
    setFormMode('create');
    setFormOpen(true);
  };

  const handleEditOpportunity = (opportunity: Opportunity) => {
    setSelectedOpportunity(opportunity);
    setFormMode('edit');
    setFormOpen(true);
    setActionMenuAnchor(null);
  };

  const handleDeleteOpportunity = async (opportunity: Opportunity) => {
    if (window.confirm(`Are you sure you want to delete "${opportunity.name}"?`)) {
      try {
        await ApiService.deleteOpportunity(opportunity.id);
        loadOpportunities();
      } catch (err) {
        setError('Failed to delete opportunity');
      }
    }
    setActionMenuAnchor(null);
  };

  const handleOpportunitySave = (opportunity: Opportunity) => {
    setOpportunities(prev => {
      const existing = prev.find(o => o.id === opportunity.id);
      if (existing) {
        return prev.map(o => o.id === opportunity.id ? opportunity : o);
      } else {
        return [opportunity, ...prev];
      }
    });

    // If we're in create mode, increment total count
    if (formMode === 'create') {
      setTotalCount(prev => prev + 1);
    }
  };

  const handleOpportunityUpdate = (opportunity: Opportunity) => {
    setOpportunities(prev =>
      prev.map(o => o.id === opportunity.id ? opportunity : o)
    );
  };

  const handleActionMenuOpen = (event: React.MouseEvent<HTMLElement>, opportunity: Opportunity) => {
    setActionMenuAnchor(event.currentTarget);
    setActionMenuOpportunity(opportunity);
  };

  const handleActionMenuClose = () => {
    setActionMenuAnchor(null);
    setActionMenuOpportunity(null);
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  const getStageColor = (stage: string): string => {
    return stageOptions.find(s => s.value === stage)?.color || '#2196f3';
  };

  const clearFilters = () => {
    setStageFilter('');
    setOwnerFilter('');
    setStartDate(null);
    setEndDate(null);
    setLeadSourceFilter('');
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
            placeholder="Search opportunities..."
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
            <InputLabel>Stage</InputLabel>
            <Select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              label="Stage"
            >
              {stageOptions.map((stage) => (
                <MenuItem key={stage.value} value={stage.value}>
                  {stage.value && (
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Box
                        sx={{
                          width: 12,
                          height: 12,
                          borderRadius: '50%',
                          backgroundColor: stage.color,
                          mr: 1,
                        }}
                      />
                    </Box>
                  )}
                  {stage.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12} sm={6} md={2}>
          <FormControl fullWidth size="small">
            <InputLabel>Owner</InputLabel>
            <Select
              value={ownerFilter}
              onChange={(e) => setOwnerFilter(e.target.value)}
              label="Owner"
            >
              <MenuItem value="">All Owners</MenuItem>
              {users.map((user) => (
                <MenuItem key={user.id} value={user.id}>
                  {user.first_name} {user.last_name}
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

  const renderTableView = () => (
    <>
      {renderFilters()}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Company</TableCell>
              <TableCell>Opportunity Name</TableCell>
              <TableCell>Stage</TableCell>
              <TableCell>Expected Value</TableCell>
              <TableCell>Probability</TableCell>
              <TableCell>Owner</TableCell>
              <TableCell>Last Contact</TableCell>
              <TableCell>Follow-up Date</TableCell>
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
            ) : opportunities.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} align="center">
                  <Box sx={{ py: 4 }}>
                    <Handshake sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No opportunities found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search || stageFilter || ownerFilter ? 'Try adjusting your filters' : 'Start by creating your first opportunity'}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              opportunities.map((opportunity) => (
                <TableRow key={opportunity.id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Business sx={{ mr: 1, color: 'text.secondary' }} />
                      <Typography variant="body2">
                        {opportunity.company_name}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {opportunity.name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={opportunity.stage}
                      size="small"
                      sx={{
                        backgroundColor: getStageColor(opportunity.stage),
                        color: 'white',
                        fontWeight: 600
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <AttachMoney sx={{ fontSize: 16, color: 'text.secondary' }} />
                      <Typography variant="body2">
                        {formatCurrency(opportunity.expected_value || 0)}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <TrendingUp sx={{ fontSize: 16, color: 'text.secondary', mr: 0.5 }} />
                      <Typography variant="body2">
                        {opportunity.probability}%
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Person sx={{ fontSize: 16, color: 'text.secondary', mr: 0.5 }} />
                      <Typography variant="body2">
                        {opportunity.owner_name}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Schedule sx={{ fontSize: 16, color: 'text.secondary', mr: 0.5 }} />
                      <Typography variant="body2">
                        {formatDate(opportunity.last_contact_date)}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{
                      color: opportunity.is_overdue ? 'error.main' : 'text.primary'
                    }}>
                      {formatDate(opportunity.follow_up_date)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      onClick={(e) => handleActionMenuOpen(e, opportunity)}
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
    </>
  );

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Opportunities
          </Typography>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleCreateOpportunity}
            size={isMobile ? "small" : "medium"}
          >
            New Opportunity
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {/* Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs
            value={currentTab}
            onChange={handleTabChange}
            variant={isMobile ? "fullWidth" : "standard"}
          >
            <Tab
              icon={<TableView />}
              label="List View"
              iconPosition="start"
            />
            <Tab
              icon={<ViewKanban />}
              label="Pipeline"
              iconPosition="start"
            />
          </Tabs>
        </Paper>

        {/* Tab Panels */}
        <TabPanel value={currentTab} index={0}>
          {renderTableView()}
        </TabPanel>

        <TabPanel value={currentTab} index={1}>
          <OpportunityPipeline
            opportunities={opportunities}
            onOpportunityUpdate={handleOpportunityUpdate}
            onOpportunityEdit={handleEditOpportunity}
            loading={loading}
          />
        </TabPanel>

        {/* Opportunity Form */}
        <OpportunityForm
          open={formOpen}
          onClose={() => setFormOpen(false)}
          onSave={handleOpportunitySave}
          opportunity={selectedOpportunity}
          mode={formMode}
        />

        {/* Action Menu */}
        <Menu
          anchorEl={actionMenuAnchor}
          open={Boolean(actionMenuAnchor)}
          onClose={handleActionMenuClose}
        >
          <MenuItem onClick={() => handleEditOpportunity(actionMenuOpportunity!)}>
            <ListItemIcon>
              <Edit fontSize="small" />
            </ListItemIcon>
            <ListItemText>Edit</ListItemText>
          </MenuItem>
          <MenuItem onClick={() => {}/* Handle view details */}>
            <ListItemIcon>
              <Visibility fontSize="small" />
            </ListItemIcon>
            <ListItemText>View Details</ListItemText>
          </MenuItem>
          <Divider />
          <MenuItem
            onClick={() => handleDeleteOpportunity(actionMenuOpportunity!)}
            sx={{ color: 'error.main' }}
          >
            <ListItemIcon>
              <Delete fontSize="small" sx={{ color: 'error.main' }} />
            </ListItemIcon>
            <ListItemText>Delete</ListItemText>
          </MenuItem>
        </Menu>
      </Box>
    </LocalizationProvider>
  );
};

export default Opportunities;