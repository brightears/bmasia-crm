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
  Build,
  FilterList,
  Settings,
} from '@mui/icons-material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { useNavigate } from 'react-router-dom';
import { Equipment, EquipmentType } from '../types';
import ApiService from '../services/api';
import { format } from 'date-fns';

const EquipmentPage: React.FC = () => {
  const navigate = useNavigate();
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [equipmentTypes, setEquipmentTypes] = useState<EquipmentType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');
      const [equipmentResponse, typesResponse] = await Promise.all([
        ApiService.getEquipment(),
        ApiService.getEquipmentTypes(),
      ]);
      setEquipment(equipmentResponse.results || []);
      setEquipmentTypes(typesResponse.results || []);
    } catch (err: any) {
      console.error('Equipment load error:', err);
      setError('Failed to load equipment');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'inactive':
        return 'default';
      case 'maintenance':
        return 'warning';
      case 'retired':
        return 'error';
      default:
        return 'default';
    }
  };

  const filteredEquipment = equipment.filter((item) => {
    const matchesSearch =
      item.equipment_number?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.serial_number?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.model_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.company_name?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
    const matchesType = typeFilter === 'all' || item.equipment_type === typeFilter;

    return matchesSearch && matchesStatus && matchesType;
  });

  const columns: GridColDef[] = [
    {
      field: 'equipment_number',
      headerName: 'Equipment #',
      width: 150,
      renderCell: (params: GridRenderCellParams) => (
        <Box
          sx={{
            cursor: 'pointer',
            color: 'primary.main',
            fontWeight: 500,
            '&:hover': { textDecoration: 'underline' },
          }}
          onClick={() => navigate(`/equipment/${params.row.id}`)}
        >
          {params.value}
        </Box>
      ),
    },
    {
      field: 'equipment_type_name',
      headerName: 'Type',
      width: 150,
    },
    {
      field: 'company_name',
      headerName: 'Company',
      width: 200,
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
      field: 'zone_name',
      headerName: 'Zone/Location',
      width: 180,
      renderCell: (params: GridRenderCellParams) => (
        <Box>
          {params.value || <Typography color="text.secondary" fontSize="0.875rem">-</Typography>}
        </Box>
      ),
    },
    {
      field: 'model_name',
      headerName: 'Model',
      width: 180,
    },
    {
      field: 'manufacturer',
      headerName: 'Manufacturer',
      width: 150,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value}
          size="small"
          color={getStatusColor(params.value as string) as any}
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    {
      field: 'installed_date',
      headerName: 'Installed',
      width: 120,
      renderCell: (params: GridRenderCellParams) =>
        params.value ? format(new Date(params.value), 'MMM dd, yyyy') : '-',
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
            <Build sx={{ mr: 1, verticalAlign: 'bottom' }} />
            Equipment Management
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Track and manage all customer equipment and devices
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<Settings />}
            onClick={() => navigate('/equipment-types')}
          >
            Manage Types
          </Button>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => navigate('/equipment/new')}
            sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
          >
            New Equipment
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search equipment, serial, model..."
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
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                label="Status"
                startAdornment={
                  <InputAdornment position="start">
                    <FilterList fontSize="small" />
                  </InputAdornment>
                }
              >
                <MenuItem value="all">All Status</MenuItem>
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="inactive">Inactive</MenuItem>
                <MenuItem value="maintenance">Maintenance</MenuItem>
                <MenuItem value="retired">Retired</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Type</InputLabel>
              <Select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                label="Type"
              >
                <MenuItem value="all">All Types</MenuItem>
                {equipmentTypes.map((type) => (
                  <MenuItem key={type.id} value={type.id}>
                    {type.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Typography variant="body2" color="text.secondary">
              {filteredEquipment.length} of {equipment.length} items
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* DataGrid */}
      <Paper>
        <DataGrid
          rows={filteredEquipment}
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

export default EquipmentPage;
