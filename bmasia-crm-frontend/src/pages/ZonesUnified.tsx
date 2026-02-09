import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  GridLegacy as Grid,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  InputAdornment,
  Stack,
  Tabs,
  Tab,
  Tooltip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  Search as SearchIcon,
  FilterList as FilterListIcon,
  Wifi as WifiIcon,
  WifiOff as WifiOffIcon,
  DevicesOther as DevicesOtherIcon,
  Schedule as ScheduleIcon,
  Business as BusinessIcon,
  Delete as DeleteIcon,
  Visibility as VisibilityIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import apiService from '../services/api';
import { Zone, Company } from '../types';

type StatusFilter = 'all' | 'online' | 'offline' | 'no_device' | 'pending' | 'orphaned';

const getStatusColor = (status: string, isOrphaned?: boolean): 'success' | 'error' | 'default' | 'warning' | 'info' => {
  if (isOrphaned) return 'error';

  switch (status) {
    case 'online':
      return 'success';
    case 'offline':
      return 'error';
    case 'no_device':
      return 'default';
    case 'pending':
      return 'warning';
    case 'expired':
      return 'info';
    default:
      return 'default';
  }
};

const getStatusIcon = (status: string, isOrphaned?: boolean) => {
  if (isOrphaned) return <WarningIcon fontSize="small" />;

  switch (status) {
    case 'online':
      return <WifiIcon fontSize="small" />;
    case 'offline':
      return <WifiOffIcon fontSize="small" />;
    case 'no_device':
    case 'pending':
    case 'expired':
      return <DevicesOtherIcon fontSize="small" />;
    default:
      return <DevicesOtherIcon fontSize="small" />;
  }
};

const formatTimestamp = (timestamp?: string | null): string => {
  if (!timestamp) return 'Never';

  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min${diffMins !== 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
};

const ZonesUnified: React.FC = () => {
  const navigate = useNavigate();
  const [zones, setZones] = useState<Zone[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [companyFilter, setCompanyFilter] = useState<string>('all');
  const [platformFilter, setPlatformFilter] = useState<string>('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [zoneToDelete, setZoneToDelete] = useState<Zone | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [zonesResponse, companiesResponse] = await Promise.all([
        apiService.getZones({ page_size: 1000 }),
        apiService.getCompanies({ is_active: true }),
      ]);
      setZones(zonesResponse.results || []);
      setCompanies(companiesResponse.results || companiesResponse);
    } catch (err: any) {
      console.error('Error loading data:', err);
      setError(err.message || 'Failed to load zones and companies');
    } finally {
      setLoading(false);
    }
  };

  const handleSyncAll = async () => {
    try {
      setSyncing(true);
      setError(null);
      const result = await apiService.syncAllZones();

      // Reload zones after sync
      await loadData();

      // Show success message
      setSuccessMessage(result.message || `Synced ${result.synced} zones successfully`);
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: any) {
      console.error('Error syncing zones:', err);
      setError(err.message || 'Failed to sync zones');
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteZone = async () => {
    if (!zoneToDelete) return;

    try {
      setError(null);
      await apiService.deleteZone(zoneToDelete.id);

      // Remove from local state
      setZones(zones.filter(z => z.id !== zoneToDelete.id));

      setSuccessMessage(`Zone "${zoneToDelete.name}" deleted successfully`);
      setTimeout(() => setSuccessMessage(null), 5000);
      setDeleteDialogOpen(false);
      setZoneToDelete(null);
    } catch (err: any) {
      console.error('Error deleting zone:', err);
      setError(err.message || 'Failed to delete zone');
      setDeleteDialogOpen(false);
      setZoneToDelete(null);
    }
  };

  const openDeleteDialog = (zone: Zone, event: React.MouseEvent) => {
    event.stopPropagation();
    setZoneToDelete(zone);
    setDeleteDialogOpen(true);
  };

  useEffect(() => {
    loadData();
  }, []);

  // Filter zones based on search, status, company, and platform
  const filteredZones = zones.filter((zone) => {
    const matchesSearch =
      zone.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      zone.company_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      '';

    const matchesStatus =
      statusFilter === 'all' ? true :
      statusFilter === 'orphaned' ? zone.is_orphaned :
      zone.status === statusFilter;

    const matchesCompany = companyFilter === 'all' || zone.company === companyFilter;
    const matchesPlatform = platformFilter === 'all' || zone.platform === platformFilter;

    return matchesSearch && matchesStatus && matchesCompany && matchesPlatform;
  });

  // Calculate statistics
  const now = new Date();
  const last24h = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const soundtrackZones = zones.filter(z => z.platform === 'soundtrack');
  const syncedRecently = soundtrackZones.filter(z => z.last_api_sync && new Date(z.last_api_sync) >= last24h).length;

  const stats = {
    total: zones.length,
    online: zones.filter(z => z.status === 'online').length,
    offline: zones.filter(z => z.status === 'offline').length,
    noDevice: zones.filter(z => z.status === 'no_device').length,
    pending: zones.filter(z => z.status === 'pending').length,
    orphaned: zones.filter(z => z.is_orphaned).length,
    syncHealth: soundtrackZones.length > 0 ? Math.round((syncedRecently / soundtrackZones.length) * 100) : 100,
  };

  // Pagination
  const paginatedZones = filteredZones.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage
  );

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: StatusFilter) => {
    setStatusFilter(newValue);
    setPage(0);
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <WifiIcon /> Zone Management
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Monitor and manage all music zones across companies
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadData}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="outlined"
            startIcon={syncing ? <CircularProgress size={20} /> : <RefreshIcon />}
            onClick={handleSyncAll}
            disabled={syncing || loading}
            color="primary"
          >
            {syncing ? 'Syncing...' : 'Sync All Zones'}
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => navigate('/zones/new')}
            sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
          >
            New Zone
          </Button>
        </Stack>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Success Alert */}
      {successMessage && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {/* Statistics Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Total Zones
              </Typography>
              <Typography variant="h4">{stats.total}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card sx={{ borderLeft: 4, borderColor: 'success.main' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Online
              </Typography>
              <Typography variant="h4" color="success.main">{stats.online}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card sx={{ borderLeft: 4, borderColor: 'error.main' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Offline
              </Typography>
              <Typography variant="h4" color="error.main">{stats.offline}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card sx={{ borderLeft: 4, borderColor: 'grey.400' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                No Device
              </Typography>
              <Typography variant="h4" color="text.secondary">{stats.noDevice}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card sx={{ borderLeft: 4, borderColor: 'warning.main' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Pending
              </Typography>
              <Typography variant="h4" color="warning.main">{stats.pending}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card sx={{ borderLeft: 4, borderColor: 'error.dark' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Orphaned
              </Typography>
              <Typography variant="h4" color="error.dark">{stats.orphaned}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card sx={{ borderLeft: 4, borderColor: stats.syncHealth >= 80 ? 'info.main' : 'warning.main' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Sync Health
              </Typography>
              <Typography variant="h4" color={stats.syncHealth >= 80 ? 'info.main' : 'warning.main'}>
                {stats.syncHealth}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {syncedRecently}/{soundtrackZones.length} synced &lt;24h
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filter Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={statusFilter}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label={`All (${zones.length})`} value="all" />
          <Tab
            label={`Online (${stats.online})`}
            value="online"
            icon={<WifiIcon />}
            iconPosition="start"
          />
          <Tab
            label={`Offline (${stats.offline})`}
            value="offline"
            icon={<WifiOffIcon />}
            iconPosition="start"
          />
          <Tab
            label={`No Device (${stats.noDevice})`}
            value="no_device"
            icon={<DevicesOtherIcon />}
            iconPosition="start"
          />
          <Tab
            label={`Pending (${stats.pending})`}
            value="pending"
            icon={<ScheduleIcon />}
            iconPosition="start"
          />
          <Tab
            label={`Orphaned (${stats.orphaned})`}
            value="orphaned"
            icon={<WarningIcon />}
            iconPosition="start"
          />
        </Tabs>

        {/* Search and Filters */}
        <Box sx={{ p: 2 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search zones or companies..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Company</InputLabel>
                <Select
                  value={companyFilter}
                  label="Company"
                  onChange={(e) => setCompanyFilter(e.target.value)}
                >
                  <MenuItem value="all">All Companies</MenuItem>
                  {companies.map((company) => (
                    <MenuItem key={company.id} value={company.id}>
                      {company.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Platform</InputLabel>
                <Select
                  value={platformFilter}
                  label="Platform"
                  onChange={(e) => setPlatformFilter(e.target.value)}
                  startAdornment={
                    <InputAdornment position="start">
                      <FilterListIcon fontSize="small" />
                    </InputAdornment>
                  }
                >
                  <MenuItem value="all">All Platforms</MenuItem>
                  <MenuItem value="soundtrack">Soundtrack</MenuItem>
                  <MenuItem value="beatbreeze">Beat Breeze</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <Typography variant="body2" color="text.secondary" align="right">
                {filteredZones.length} zone{filteredZones.length !== 1 ? 's' : ''} found
              </Typography>
            </Grid>
          </Grid>
        </Box>
      </Paper>

      {/* Zones Table */}
      <Paper>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 8 }}>
            <CircularProgress />
          </Box>
        ) : filteredZones.length === 0 ? (
          <Box sx={{ p: 8, textAlign: 'center' }}>
            <DevicesOtherIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No zones found
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {searchQuery || statusFilter !== 'all' || companyFilter !== 'all' || platformFilter !== 'all'
                ? 'Try adjusting your filters'
                : 'Create zones to see them here'
              }
            </Typography>
          </Box>
        ) : (
          <>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Zone Name</TableCell>
                    <TableCell>Company</TableCell>
                    <TableCell>Platform</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Device</TableCell>
                    <TableCell>Contract</TableCell>
                    <TableCell>Last Sync</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paginatedZones.map((zone) => (
                    <TableRow
                      key={zone.id}
                      hover
                      sx={{
                        cursor: 'pointer',
                        backgroundColor: zone.is_orphaned ? 'error.lighter' : 'inherit',
                        '&:hover': {
                          backgroundColor: zone.is_orphaned ? 'error.light' : 'action.hover',
                        }
                      }}
                      onClick={() => navigate(`/zones/${zone.id}`)}
                    >
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {zone.is_orphaned && (
                            <Tooltip title="Orphaned zone - no active contract">
                              <WarningIcon fontSize="small" color="error" />
                            </Tooltip>
                          )}
                          <Typography variant="body2" fontWeight={500}>
                            {zone.name}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <BusinessIcon fontSize="small" color="action" />
                          <Typography variant="body2">
                            {zone.company_name || 'Unknown'}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={zone.platform}
                          size="small"
                          variant="outlined"
                          sx={{ textTransform: 'capitalize' }}
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          icon={getStatusIcon(zone.status, zone.is_orphaned)}
                          label={zone.is_orphaned ? 'Orphaned' : (zone.status_display || zone.status)}
                          color={getStatusColor(zone.status, zone.is_orphaned)}
                          size="small"
                          sx={{ textTransform: 'capitalize' }}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {zone.device_name || 'No device'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {zone.current_contract ? (
                          <Tooltip title={`Status: ${zone.current_contract.status}`}>
                            <Chip
                              label={zone.current_contract.contract_number}
                              size="small"
                              color="primary"
                              variant="outlined"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/contracts/${zone.current_contract!.id}`);
                              }}
                            />
                          </Tooltip>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            No contract
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <ScheduleIcon fontSize="small" color="action" />
                          <Typography variant="body2" color="text.secondary">
                            {formatTimestamp(zone.last_api_sync || zone.updated_at)}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Stack direction="row" spacing={1} justifyContent="flex-end">
                          <Tooltip title="View Details">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/zones/${zone.id}`);
                              }}
                            >
                              <VisibilityIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          {zone.is_orphaned && (
                            <Tooltip title="Delete orphaned zone">
                              <IconButton
                                size="small"
                                color="error"
                                onClick={(e) => openDeleteDialog(zone, e)}
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              rowsPerPageOptions={[10, 25, 50, 100]}
              component="div"
              count={filteredZones.length}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={handleChangePage}
              onRowsPerPageChange={handleChangeRowsPerPage}
            />
          </>
        )}
      </Paper>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
      >
        <DialogTitle>Delete Orphaned Zone</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to permanently delete the zone "{zoneToDelete?.name}"?
            This action cannot be undone.
          </DialogContentText>
          {zoneToDelete?.is_orphaned && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              This is an orphaned zone with no active contract. Deleting it will remove all historical data.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteZone} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ZonesUnified;
