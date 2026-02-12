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
  Select,
  MenuItem,
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
  Sort,
  MoreVert,
  PictureAsPdf as PdfIcon,
  TableView,
  ViewKanban,
  Handshake,
  TrendingUp,
  Person,
  Business,
  Schedule,
} from '@mui/icons-material';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Opportunity, ApiResponse, User } from '../types';
import ApiService from '../services/api';
import OpportunityForm from '../components/OpportunityForm';
import OpportunityPipeline from '../components/OpportunityPipeline';
import {
  EntityFilter, ServiceFilter, DEFAULT_ENTITY,
  ENTITY_OPTIONS, SERVICE_OPTIONS,
  formatCurrency, getServiceLabel,
} from '../constants/entities';

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

const sortOptions = [
  { value: '-created_at', label: 'Newest First' },
  { value: 'created_at', label: 'Oldest First' },
  { value: '-expected_value', label: 'Highest Value' },
  { value: 'expected_value', label: 'Lowest Value' },
  { value: '-probability', label: 'Highest Probability' },
  { value: 'expected_close_date', label: 'Close Date (Soonest)' },
  { value: '-last_contact_date', label: 'Last Contacted' },
];

const Opportunities: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

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
  const [entityFilter, setEntityFilter] = useState<EntityFilter>(DEFAULT_ENTITY);
  const [serviceFilter, setServiceFilter] = useState<ServiceFilter>('all');
  const [sortBy, setSortBy] = useState('-created_at');

  // Form state
  const [formOpen, setFormOpen] = useState(false);
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');

  // Export
  const [exporting, setExporting] = useState(false);

  // Action menu
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [actionMenuOpportunity, setActionMenuOpportunity] = useState<Opportunity | null>(null);

  // Handle query param for opening create dialog from dashboard
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setSelectedOpportunity(null);
      setFormMode('create');
      setFormOpen(true);
      searchParams.delete('new');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    loadOpportunities();
    loadUsers();
  }, [page, rowsPerPage, search, stageFilter, ownerFilter, entityFilter, serviceFilter, sortBy]);

  const loadOpportunities = async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
        ordering: sortBy,
      };

      if (search) params.search = search;
      if (stageFilter) params.stage = stageFilter;
      if (ownerFilter) params.owner = ownerFilter;
      params.company__billing_entity = entityFilter;
      if (serviceFilter !== 'all') params.service_type = serviceFilter;

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

  const handleSearchChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(0);
  }, []);

  const handleStageChange = useCallback((event: any) => {
    setStageFilter(event.target.value);
    setPage(0);
  }, []);

  const handleOwnerChange = useCallback((event: any) => {
    setOwnerFilter(event.target.value);
    setPage(0);
  }, []);

  const handleEntityChange = useCallback((event: any) => {
    setEntityFilter(event.target.value as EntityFilter);
    setPage(0);
  }, []);

  const handleServiceChange = useCallback((event: any) => {
    setServiceFilter(event.target.value as ServiceFilter);
    setPage(0);
  }, []);

  const handleSortChange = useCallback((event: any) => {
    setSortBy(event.target.value);
    setPage(0);
  }, []);

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

  const handleViewOpportunity = (opportunity: Opportunity) => {
    setActionMenuAnchor(null);
    navigate(`/opportunities/${opportunity.id}`);
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const token = localStorage.getItem('bmasia_access_token') || sessionStorage.getItem('bmasia_access_token');
      const baseUrl = process.env.REACT_APP_API_URL || '';
      const params = new URLSearchParams();

      if (search) params.append('search', search);
      if (stageFilter) params.append('stage', stageFilter);
      if (ownerFilter) params.append('owner', ownerFilter);
      params.append('company__billing_entity', entityFilter);
      if (serviceFilter !== 'all') params.append('service_type', serviceFilter);
      params.append('ordering', sortBy);

      const response = await fetch(
        `${baseUrl}/api/v1/opportunities/export/pdf/?${params.toString()}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const today = new Date().toISOString().split('T')[0];
      a.download = `Opportunities_${today}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Export error:', err);
      setError('Failed to export PDF');
    } finally {
      setExporting(false);
    }
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

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  const getStageColor = (stage: string): string => {
    return stageOptions.find(s => s.value === stage)?.color || '#2196f3';
  };

  const renderFilters = () => (
    <Paper sx={{ mb: 2 }}>
      <Box sx={{ p: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <TextField
          placeholder="Search opportunities..."
          value={search}
          onChange={handleSearchChange}
          size="small"
          sx={{ flex: 1, minWidth: 200 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ),
          }}
        />

        <FormControl size="small" sx={{ minWidth: 150 }}>
          <Select
            value={stageFilter}
            onChange={handleStageChange}
            displayEmpty
            renderValue={(value) => value || 'All Stages'}
          >
            {stageOptions.map((stage) => (
              <MenuItem key={stage.value} value={stage.value}>
                {stage.value && (
                  <Box
                    sx={{
                      width: 12,
                      height: 12,
                      borderRadius: '50%',
                      backgroundColor: stage.color,
                      mr: 1,
                      display: 'inline-block',
                    }}
                  />
                )}
                {stage.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 140 }}>
          <Select
            value={ownerFilter}
            onChange={handleOwnerChange}
            displayEmpty
            renderValue={(value) => {
              if (!value) return 'All Owners';
              const user = users.find(u => u.id === value);
              return user ? `${user.first_name} ${user.last_name}` : 'All Owners';
            }}
          >
            <MenuItem value="">All Owners</MenuItem>
            {users.map((user) => (
              <MenuItem key={user.id} value={user.id}>
                {user.first_name} {user.last_name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 180 }}>
          <Select
            value={entityFilter}
            onChange={handleEntityChange}
            renderValue={(value) => {
              const opt = ENTITY_OPTIONS.find(e => e.value === value);
              return opt?.label || value;
            }}
          >
            {ENTITY_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 150 }}>
          <Select
            value={serviceFilter}
            onChange={handleServiceChange}
            renderValue={(value) => {
              const opt = SERVICE_OPTIONS.find(s => s.value === value);
              return opt?.label || 'All Services';
            }}
          >
            {SERVICE_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 170 }}>
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
  );

  const renderTableView = () => (
    <>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Company</TableCell>
              <TableCell>Opportunity Name</TableCell>
              <TableCell>Service</TableCell>
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
                <TableCell colSpan={10} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : opportunities.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10} align="center">
                  <Box sx={{ py: 4 }}>
                    <Handshake sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No opportunities found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search || stageFilter || ownerFilter || serviceFilter !== 'all' ? 'Try adjusting your filters' : 'Start by creating your first opportunity'}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              opportunities.map((opportunity) => (
                <TableRow key={opportunity.id} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/opportunities/${opportunity.id}`)}>
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
                      label={getServiceLabel(opportunity.service_type)}
                      size="small"
                      variant="outlined"
                      sx={{ fontSize: '0.75rem' }}
                    />
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
                    <Typography variant="body2">
                      {formatCurrency(opportunity.expected_value || 0, opportunity.company_billing_entity)}
                    </Typography>
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
                      onClick={(e) => { e.stopPropagation(); handleActionMenuOpen(e, opportunity); }}
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
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Opportunities
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={exporting ? <CircularProgress size={16} /> : <PdfIcon />}
            onClick={handleExportPDF}
            disabled={exporting || loading}
            size={isMobile ? "small" : "medium"}
          >
            Export PDF
          </Button>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleCreateOpportunity}
            size={isMobile ? "small" : "medium"}
          >
            New Opportunity
          </Button>
        </Box>
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

      {/* Filters — shared by both tabs */}
      {renderFilters()}

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
          entityFilter={entityFilter}
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
        <MenuItem onClick={() => handleViewOpportunity(actionMenuOpportunity!)}>
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
  );
};

export default Opportunities;
