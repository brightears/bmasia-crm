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
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Tooltip,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  InputAdornment,
  Stack,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Search as SearchIcon,
  FilterList as FilterListIcon,
  Wifi as WifiIcon,
  WifiOff as WifiOffIcon,
  DevicesOther as DevicesOtherIcon,
  Schedule as ScheduleIcon,
  Business as BusinessIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import apiService from '../services/api';
import { Zone } from '../types';

type StatusFilter = 'all' | 'online' | 'offline' | 'no_device' | 'pending' | 'expired';

const getStatusColor = (status: string): 'success' | 'error' | 'default' | 'warning' | 'info' => {
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

const getStatusIcon = (status: string) => {
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

const ZoneStatus: React.FC = () => {
  const navigate = useNavigate();
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const loadZones = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getZones({ page_size: 1000 });
      setZones(response.results || []);
    } catch (err: any) {
      console.error('Error loading zones:', err);
      setError(err.message || 'Failed to load zones');
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
      await loadZones();

      // Show success message
      alert(result.message || `Synced ${result.synced} zones successfully`);
    } catch (err: any) {
      console.error('Error syncing zones:', err);
      setError(err.message || 'Failed to sync zones');
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    loadZones();
  }, []);

  // Filter zones based on search and status
  const filteredZones = zones.filter((zone) => {
    const matchesSearch =
      zone.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      zone.company_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      '';

    const matchesStatus = statusFilter === 'all' || zone.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  // Calculate statistics
  const stats = {
    total: zones.length,
    online: zones.filter(z => z.status === 'online').length,
    offline: zones.filter(z => z.status === 'offline').length,
    noDevice: zones.filter(z => z.status === 'no_device').length,
    pending: zones.filter(z => z.status === 'pending').length,
    expired: zones.filter(z => z.status === 'expired').length,
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

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <WifiIcon /> Zone Status Dashboard
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Monitor and sync all music zones across companies
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadZones}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={syncing ? <CircularProgress size={20} /> : <RefreshIcon />}
            onClick={handleSyncAll}
            disabled={syncing || loading}
            color="primary"
          >
            {syncing ? 'Syncing...' : 'Sync All Zones'}
          </Button>
        </Stack>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
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
          <Card sx={{ borderLeft: 4, borderColor: 'info.main' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Expired
              </Typography>
              <Typography variant="h4" color="info.main">{stats.expired}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
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
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Status Filter</InputLabel>
              <Select
                value={statusFilter}
                label="Status Filter"
                onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                startAdornment={
                  <InputAdornment position="start">
                    <FilterListIcon />
                  </InputAdornment>
                }
              >
                <MenuItem value="all">All Statuses</MenuItem>
                <MenuItem value="online">Online</MenuItem>
                <MenuItem value="offline">Offline</MenuItem>
                <MenuItem value="no_device">No Device</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
                <MenuItem value="expired">Expired</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Typography variant="body2" color="text.secondary" align="right">
              {filteredZones.length} zone{filteredZones.length !== 1 ? 's' : ''} found
            </Typography>
          </Grid>
        </Grid>
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
              {searchQuery || statusFilter !== 'all'
                ? 'Try adjusting your filters'
                : 'Create zones in the Zones page to see them here'
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
                    <TableCell>Status</TableCell>
                    <TableCell>Platform</TableCell>
                    <TableCell>Device</TableCell>
                    <TableCell>Contract</TableCell>
                    <TableCell>Last Updated</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paginatedZones.map((zone) => (
                    <TableRow
                      key={zone.id}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/zones/${zone.id}`)}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {zone.name}
                        </Typography>
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
                          icon={getStatusIcon(zone.status)}
                          label={zone.status_display || zone.status}
                          color={getStatusColor(zone.status)}
                          size="small"
                          sx={{ textTransform: 'capitalize' }}
                        />
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
                            {formatTimestamp(zone.updated_at)}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title="View Details">
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/zones/${zone.id}`);
                            }}
                          >
                            <SearchIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
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
    </Box>
  );
};

export default ZoneStatus;
