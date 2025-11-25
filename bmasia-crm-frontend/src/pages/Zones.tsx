import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  InputAdornment,
  Chip,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  GridLegacy as Grid,
} from '@mui/material';
import {
  Add,
  Search,
  LocationOn,
  FilterList,
} from '@mui/icons-material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { useNavigate } from 'react-router-dom';
import { Zone, Company, ContractZone } from '../types';
import ApiService from '../services/api';

const ZonesPage: React.FC = () => {
  const navigate = useNavigate();
  const [zones, setZones] = useState<Zone[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [zoneContracts, setZoneContracts] = useState<Record<string, ContractZone[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [companyFilter, setCompanyFilter] = useState<string>('all');
  const [platformFilter, setPlatformFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');
      const [zonesResponse, companiesResponse] = await Promise.all([
        ApiService.getZones(),
        ApiService.getCompanies({ is_active: true }),
      ]);
      const zonesData = zonesResponse.results || [];
      setZones(zonesData);
      setCompanies(companiesResponse.results || companiesResponse);

      // Load contract information for all zones
      const contractsData: Record<string, ContractZone[]> = {};
      await Promise.all(
        zonesData.map(async (zone) => {
          try {
            const contracts = await ApiService.getZoneContracts(zone.id);
            contractsData[zone.id] = contracts;
          } catch (err) {
            console.error(`Failed to load contracts for zone ${zone.id}:`, err);
            contractsData[zone.id] = [];
          }
        })
      );
      setZoneContracts(contractsData);
    } catch (err: any) {
      console.error('Zones load error:', err);
      setError('Failed to load zones');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return 'success';
      case 'offline':
        return 'error';
      case 'no_device':
        return 'warning';
      case 'expired':
        return 'error';
      case 'pending':
        return 'default';
      default:
        return 'default';
    }
  };

  const filteredZones = zones.filter((zone) => {
    const matchesSearch =
      zone.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      zone.company_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      zone.device_name?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCompany = companyFilter === 'all' || zone.company === companyFilter;
    const matchesPlatform = platformFilter === 'all' || zone.platform === platformFilter;
    const matchesStatus = statusFilter === 'all' || zone.status === statusFilter;

    return matchesSearch && matchesCompany && matchesPlatform && matchesStatus;
  });

  const columns: GridColDef[] = [
    {
      field: 'company_name',
      headerName: 'Company',
      width: 180,
      renderCell: (params: GridRenderCellParams) => (
        <Box
          sx={{
            cursor: 'pointer',
            color: 'primary.main',
            '&:hover': { textDecoration: 'underline' },
          }}
          onClick={() => navigate(`/companies/${params.row.company}`)}
        >
          {params.value}
        </Box>
      ),
    },
    {
      field: 'name',
      headerName: 'Zone Name',
      width: 180,
      renderCell: (params: GridRenderCellParams) => (
        <Box
          sx={{
            cursor: 'pointer',
            color: 'primary.main',
            fontWeight: 500,
            '&:hover': { textDecoration: 'underline' },
          }}
          onClick={() => navigate(`/zones/${params.row.id}`)}
        >
          {params.value}
        </Box>
      ),
    },
    {
      field: 'platform',
      headerName: 'Platform',
      width: 110,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value}
          size="small"
          variant="outlined"
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 110,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value?.replace('_', ' ')}
          size="small"
          color={getStatusColor(params.value as string) as any}
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    {
      field: 'current_contract',
      headerName: 'Current Contract',
      width: 200,
      renderCell: (params: GridRenderCellParams) => {
        const contracts = zoneContracts[params.row.id] || [];
        const activeContract = contracts.find(c => c.is_active);

        if (!activeContract) {
          return <Typography color="text.secondary" fontSize="0.875rem">No active contract</Typography>;
        }

        return (
          <Box
            sx={{
              cursor: 'pointer',
              color: 'primary.main',
              '&:hover': { textDecoration: 'underline' },
            }}
            onClick={() => navigate(`/contracts/${activeContract.contract}`)}
          >
            <Box>{activeContract.contract_number}</Box>
            <Typography variant="caption" color="text.secondary">
              {activeContract.start_date} - {activeContract.end_date || 'Ongoing'}
            </Typography>
          </Box>
        );
      },
    },
    {
      field: 'contract_count',
      headerName: 'Total Contracts',
      width: 130,
      align: 'center' as const,
      headerAlign: 'center' as const,
      renderCell: (params: GridRenderCellParams) => {
        const contracts = zoneContracts[params.row.id] || [];
        const activeCount = contracts.filter(c => c.is_active).length;
        const totalCount = contracts.length;

        return (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Typography variant="body2" fontWeight={500}>
              {totalCount}
            </Typography>
            {activeCount > 0 && (
              <Chip
                label={`${activeCount} active`}
                size="small"
                color="success"
                sx={{ height: 18, fontSize: '0.7rem' }}
              />
            )}
          </Box>
        );
      },
    },
  ];

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            <LocationOn sx={{ mr: 1, verticalAlign: 'bottom' }} />
            Zone Management
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage customer locations and music zones
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => navigate('/zones/new')}
          sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
        >
          New Zone
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search zones, companies..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
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
                onChange={(e) => setCompanyFilter(e.target.value)}
                label="Company"
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
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Platform</InputLabel>
              <Select
                value={platformFilter}
                onChange={(e) => setPlatformFilter(e.target.value)}
                label="Platform"
                startAdornment={
                  <InputAdornment position="start">
                    <FilterList fontSize="small" />
                  </InputAdornment>
                }
              >
                <MenuItem value="all">All Platforms</MenuItem>
                <MenuItem value="soundtrack">Soundtrack</MenuItem>
                <MenuItem value="beatbreeze">Beat Breeze</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                label="Status"
              >
                <MenuItem value="all">All Status</MenuItem>
                <MenuItem value="online">Online</MenuItem>
                <MenuItem value="offline">Offline</MenuItem>
                <MenuItem value="no_device">No Device</MenuItem>
                <MenuItem value="expired">Expired</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Typography variant="body2" color="text.secondary">
              {filteredZones.length} of {zones.length} zones
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* DataGrid */}
      <Paper>
        <DataGrid
          rows={filteredZones}
          columns={columns}
          initialState={{
            pagination: {
              paginationModel: { pageSize: 25, page: 0 },
            },
          }}
          pageSizeOptions={[10, 25, 50, 100]}
          disableRowSelectionOnClick
          autoHeight
          sx={{
            border: 0,
            '& .MuiDataGrid-cell:focus': {
              outline: 'none',
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: 'action.hover',
              cursor: 'pointer',
            },
          }}
        />
      </Paper>
    </Box>
  );
};

export default ZonesPage;
