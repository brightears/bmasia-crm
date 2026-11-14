import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  Skeleton,
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
  currencyForEntity,
} from '../constants/entities';
import { formatDate as formatDisplayDate, formatMoney, statusTone, visuallyHidden } from '../theme';
import { useListState, optionValues, idFromList } from '../hooks/useListState';
import { useListSearchBox } from '../hooks/useListSearchBox';
import { withListView } from '../hooks/listReturn';
import { PageHeader, EmptyState, ProductChip } from '../components/ui';

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
      {value === index && <Box>{children}</Box>}
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

/** The most the server returns in one page (its page_size cap). */
const PIPELINE_LIMIT = 1000;

const Opportunities: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // Search, filters, sort and page live in the address, so Back returns to the same view.
  const list = useListState(
    { q: '', page: 0, size: 25, stage: '', owner: '', entity: DEFAULT_ENTITY as EntityFilter, service: 'all' as ServiceFilter, sort: '-created_at' },
    {
      stage: optionValues(stageOptions),
      owner: idFromList(users),
      entity: optionValues(ENTITY_OPTIONS),
      service: optionValues(SERVICE_OPTIONS),
      sort: optionValues(sortOptions),
    },
    users.length
  );
  const [search, setSearch] = list.bind('q');
  const [page, setPage] = list.bind('page');
  // The box's own text, written to the address shortly after typing stops.
  const searchBox = useListSearchBox(search, (text) => {
    setSearch(text);
    setPage(0);
  });
  const [rowsPerPage, setRowsPerPage] = list.bind('size');
  const [totalCount, setTotalCount] = useState(0);
  const [currentTab, setCurrentTab] = useState(0);
  // The pipeline board loads its own copy of the list (not the table's 25-row page), so its
  // totals cover every opportunity that matches the filters, up to the server's limit.
  const [pipeline, setPipeline] = useState<{ items: Opportunity[]; count: number } | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineVersion, setPipelineVersion] = useState(0);
  const pipelineRequest = useRef(0);

  // Filters
  const [stageFilter, setStageFilter] = list.bind('stage');
  const [ownerFilter, setOwnerFilter] = list.bind('owner');
  const [entityFilter, setEntityFilter] = list.bind('entity');
  const [serviceFilter, setServiceFilter] = list.bind('service');
  const [sortBy, setSortBy] = list.bind('sort');

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

  useEffect(() => {
    if (currentTab !== 1) return;
    const request = ++pipelineRequest.current;
    const params: any = { page: 1, page_size: PIPELINE_LIMIT, ordering: sortBy, company__billing_entity: entityFilter };
    if (search) params.search = search;
    if (stageFilter) params.stage = stageFilter;
    if (ownerFilter) params.owner = ownerFilter;
    if (serviceFilter !== 'all') params.service_type = serviceFilter;
    setPipelineLoading(true);
    ApiService.getOpportunities(params)
      .then((response: ApiResponse<Opportunity>) => {
        if (request === pipelineRequest.current) setPipeline({ items: response.results, count: response.count });
      })
      .catch((err) => {
        console.error('Pipeline error:', err);
        if (request === pipelineRequest.current) setError('Failed to load the pipeline');
      })
      .finally(() => {
        if (request === pipelineRequest.current) setPipelineLoading(false);
      });
  }, [currentTab, search, stageFilter, ownerFilter, entityFilter, serviceFilter, sortBy, pipelineVersion]);

  const loadUsers = async () => {
    try {
      const response = await ApiService.getUsers({ page_size: 100 });
      setUsers(response.results);
    } catch (err) {
      console.error('Failed to load users:', err);
    }
  };

  const handleSearchChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    searchBox.onChange(event.target.value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    navigate(`/opportunities/${opportunity.id}`, withListView(list.searchParams));
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
        setPipelineVersion((v) => v + 1);
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
    setPipelineVersion((v) => v + 1);
  };

  const handleOpportunityUpdate = (opportunity: Opportunity) => {
    setOpportunities(prev =>
      prev.map(o => o.id === opportunity.id ? opportunity : o)
    );
    setPipeline((prev) =>
      prev && { ...prev, items: prev.items.map((o) => (o.id === opportunity.id ? opportunity : o)) }
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
    return formatDisplayDate(dateString);
  };

  const renderFilters = () => (
    <Box>
      <Box sx={{ p: 2, display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap', borderBottom: 1, borderColor: 'divider' }}>
        <TextField
          placeholder="Search opportunities..."
          value={searchBox.value}
          onChange={handleSearchChange}
          size="small"
          inputProps={{ 'aria-label': 'Search opportunities' }}
          sx={{ flex: '1 1 240px', maxWidth: { md: 360 } }}
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
                      bgcolor: statusTone(stage.value) === 'default' ? 'grey.500' : `${statusTone(stage.value)}.main`,
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
    </Box>
  );

  const renderTableView = () => (
    <>
      <TableContainer sx={{ borderRadius: 0 }}>
        <Table aria-label="Opportunities">
          <TableHead>
            <TableRow>
              <TableCell>Opportunity</TableCell>
              <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>Product</TableCell>
              <TableCell>Stage</TableCell>
              <TableCell align="right">Expected value</TableCell>
              <TableCell align="right" sx={{ display: { xs: 'none', md: 'table-cell' } }}>Probability</TableCell>
              <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' } }}>Owner</TableCell>
              <TableCell sx={{ display: { xs: 'none', xl: 'table-cell' } }}>Last contact</TableCell>
              <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>Follow-up</TableCell>
              <TableCell align="right"><Box component="span" sx={visuallyHidden}>Actions</Box></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={`skeleton-${i}`}>
                  <TableCell>
                    <Skeleton width="60%" />
                    <Skeleton width="40%" />
                  </TableCell>
                  {Array.from({ length: 8 }).map((__, j) => (
                    <TableCell key={j} sx={j === 0 || j === 3 ? { display: { xs: 'none', md: 'table-cell' } } : j === 4 ? { display: { xs: 'none', lg: 'table-cell' } } : j === 5 ? { display: { xs: 'none', xl: 'table-cell' } } : j === 6 ? { display: { xs: 'none', sm: 'table-cell' } } : undefined}>
                      <Skeleton width={j === 7 ? 24 : '70%'} />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : opportunities.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9}>
                  <EmptyState
                    icon={<Handshake />}
                    title={search || stageFilter || ownerFilter || serviceFilter !== 'all' ? 'No opportunities match these filters' : 'No opportunities yet'}
                    description={search || stageFilter || ownerFilter || serviceFilter !== 'all' ? 'Try a different search or clear the filters.' : 'Create the first opportunity to start tracking a deal.'}
                  />
                </TableCell>
              </TableRow>
            ) : (
              opportunities.map((opportunity) => (
                <TableRow key={opportunity.id} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/opportunities/${opportunity.id}`, withListView(list.searchParams))}>
                  <TableCell sx={{ maxWidth: 320 }}>
                    <Typography sx={{ fontWeight: 600, fontSize: '0.875rem' }} noWrap>
                      {opportunity.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" noWrap>
                      {opportunity.company_name}
                    </Typography>
                  </TableCell>
                  <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>
                    {opportunity.service_type ? (
                      <ProductChip value={opportunity.service_type} />
                    ) : (
                      <Typography variant="body2" color="text.disabled">—</Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip label={opportunity.stage} size="small" color={statusTone(opportunity.stage)} />
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {formatMoney(opportunity.expected_value || 0, currencyForEntity(opportunity.company_billing_entity))}
                  </TableCell>
                  <TableCell align="right" sx={{ display: { xs: 'none', md: 'table-cell' }, fontVariantNumeric: 'tabular-nums' }}>
                    {opportunity.probability}%
                  </TableCell>
                  <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' } }}>
                    <Typography variant="body2" noWrap>{opportunity.owner_name || '—'}</Typography>
                  </TableCell>
                  <TableCell sx={{ display: { xs: 'none', xl: 'table-cell' }, whiteSpace: 'nowrap' }}>
                    {formatDate(opportunity.last_contact_date)}
                  </TableCell>
                  <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' }, whiteSpace: 'nowrap' }}>
                    <Typography
                      variant="body2"
                      sx={{ color: opportunity.is_overdue ? 'error.main' : 'text.primary', fontWeight: opportunity.is_overdue ? 600 : 400 }}
                    >
                      {formatDate(opportunity.follow_up_date)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      aria-label={`Actions for ${opportunity.name}`}
                      onClick={(e) => { e.stopPropagation(); handleActionMenuOpen(e, opportunity); }}
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
    </>
  );

  return (
    <Box>
      <PageHeader
        title="Opportunities"
        subtitle="Deals in progress, from first contact to signed contract."
        actions={
          <>
            <Button
              variant="outlined"
              startIcon={exporting ? <CircularProgress size={16} color="inherit" /> : <PdfIcon />}
              onClick={handleExportPDF}
              disabled={exporting || loading}
            >
              Export PDF
            </Button>
            <Button variant="contained" startIcon={<Add />} onClick={handleCreateOpportunity}>
              New Opportunity
            </Button>
          </>
        }
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* One card: view tabs, filters (shared by both views), then the list or the pipeline */}
      <Paper sx={{ overflow: 'hidden' }}>
        <Tabs
          value={currentTab}
          onChange={handleTabChange}
          variant={isMobile ? 'fullWidth' : 'standard'}
          sx={{ px: 1 }}
        >
          <Tab icon={<TableView fontSize="small" />} label="List" iconPosition="start" />
          <Tab icon={<ViewKanban fontSize="small" />} label="Pipeline" iconPosition="start" />
        </Tabs>

        {renderFilters()}

        <TabPanel value={currentTab} index={0}>
          {renderTableView()}
        </TabPanel>

        <TabPanel value={currentTab} index={1}>
          <Box sx={{ p: 2 }}>
            <OpportunityPipeline
              opportunities={pipeline?.items ?? []}
              totalCount={pipeline?.count}
              onOpportunityUpdate={handleOpportunityUpdate}
              onOpportunityEdit={handleEditOpportunity}
              loading={pipelineLoading && !pipeline}
              entityFilter={entityFilter}
            />
          </Box>
        </TabPanel>
      </Paper>

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
