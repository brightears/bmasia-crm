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
  InputAdornment,
  Alert,
  CircularProgress,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  GridLegacy as Grid,
  IconButton,
  Menu,
  ListItemIcon,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
} from '@mui/material';
import {
  Add,
  Search,
  MoreVert,
  Edit,
  Delete,
  Visibility,
  FileCopy,
  Timeline,
  Archive,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { EmailSequence, ApiResponse } from '../types';
import ApiService from '../services/api';
import SequenceForm from '../components/SequenceForm';

const EmailAutomations: React.FC = () => {
  const navigate = useNavigate();
  const [sequences, setSequences] = useState<EmailSequence[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  // Form modal state
  const [formOpen, setFormOpen] = useState(false);
  const [editingSequence, setEditingSequence] = useState<EmailSequence | null>(null);

  // Menu state
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedSequence, setSelectedSequence] = useState<EmailSequence | null>(null);

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingSequence, setDeletingSequence] = useState<EmailSequence | null>(null);

  const loadSequences = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
      };

      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;

      // Add type filter
      if (typeFilter === 'auto') {
        params.sequence_type__startswith = 'auto_';
      } else if (typeFilter === 'manual') {
        params.sequence_type = 'manual';
      }

      console.log('Loading email automations with params:', params);
      const response: ApiResponse<EmailSequence> = await ApiService.getEmailSequences(params);
      console.log('Email Automations API response:', response);

      setSequences(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err: any) {
      console.error('Email automations error:', err);
      setError(`Failed to load email automations: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setSequences([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, statusFilter, typeFilter]);

  useEffect(() => {
    loadSequences();
  }, [loadSequences]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(0);
  };

  const handleTypeFilterChange = (event: React.SyntheticEvent, newValue: string) => {
    setTypeFilter(newValue);
    setPage(0);
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, sequence: EmailSequence) => {
    setAnchorEl(event.currentTarget);
    setSelectedSequence(sequence);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedSequence(null);
  };

  const handleCreateSequence = () => {
    setEditingSequence(null);
    setFormOpen(true);
  };

  const handleViewDetails = (sequence: EmailSequence) => {
    navigate(`/email-automations/${sequence.id}`);
    handleMenuClose();
  };

  const handleEditSequence = (sequence: EmailSequence) => {
    setEditingSequence(sequence);
    setFormOpen(true);
    handleMenuClose();
  };

  const handleDuplicateSequence = async (sequence: EmailSequence) => {
    try {
      setError('');
      await ApiService.duplicateEmailSequence(sequence.id);
      setSuccess('Automation duplicated successfully');
      loadSequences();
    } catch (err: any) {
      console.error('Duplicate automation error:', err);
      setError(`Failed to duplicate automation: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    }
    handleMenuClose();
  };

  const handleArchiveSequence = async (sequence: EmailSequence) => {
    // Warn if there are active enrollments
    if (sequence.active_enrollments > 0) {
      const confirmed = window.confirm(
        `This automation has ${sequence.active_enrollments} active enrollment(s). ` +
        'Archiving will not affect existing enrollments. Continue?'
      );
      if (!confirmed) {
        handleMenuClose();
        return;
      }
    }

    try {
      setError('');
      await ApiService.updateEmailSequence(sequence.id, { status: 'archived' });
      setSuccess('Automation archived successfully');
      loadSequences();
    } catch (err: any) {
      console.error('Archive automation error:', err);
      setError(`Failed to archive automation: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    }
    handleMenuClose();
  };

  const handleDeleteClick = (sequence: EmailSequence) => {
    setDeletingSequence(sequence);
    setDeleteDialogOpen(true);
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    if (!deletingSequence) return;

    try {
      setError('');
      await ApiService.deleteEmailSequence(deletingSequence.id);
      setSuccess('Automation deleted successfully');
      loadSequences();
      setDeleteDialogOpen(false);
      setDeletingSequence(null);
    } catch (err: any) {
      console.error('Delete automation error:', err);
      setError(`Failed to delete automation: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setDeletingSequence(null);
  };

  const handleFormSave = () => {
    setFormOpen(false);
    setEditingSequence(null);
    setSuccess(editingSequence ? 'Automation updated successfully' : 'Automation created successfully');
    loadSequences();
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setEditingSequence(null);
  };

  const getStatusColor = (status: string): 'success' | 'warning' | 'default' => {
    switch (status) {
      case 'active':
        return 'success';
      case 'paused':
        return 'warning';
      case 'archived':
        return 'default';
      default:
        return 'default';
    }
  };

  const getTypeLabel = (type: string): string => {
    switch (type) {
      case 'auto_renewal':
        return 'Auto: Renewal';
      case 'auto_payment':
        return 'Auto: Payment';
      case 'auto_quarterly':
        return 'Auto: Quarterly';
      case 'manual':
      default:
        return 'Manual';
    }
  };

  const getTypeColor = (type: string): 'primary' | 'default' => {
    if (type && type.startsWith('auto_')) {
      return 'primary';
    }
    return 'default';
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Email Automations
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreateSequence}
          sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
        >
          New Email Automation
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      <Paper sx={{ mb: 2 }}>
        {/* Filter Tabs */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs
            value={typeFilter}
            onChange={handleTypeFilterChange}
            sx={{ px: 2 }}
          >
            <Tab label="All" value="all" />
            <Tab label="Automatic" value="auto" />
            <Tab label="Manual" value="manual" />
          </Tabs>
        </Box>

        {/* Search and Status Filters */}
        <Box sx={{ p: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={8}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search automations by name or description..."
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
            <Grid item xs={12} md={4}>
              <FormControl fullWidth size="small">
                <InputLabel>Status</InputLabel>
                <Select
                  value={statusFilter}
                  label="Status"
                  onChange={(e) => {
                    setStatusFilter(e.target.value);
                    setPage(0);
                  }}
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="paused">Paused</MenuItem>
                  <MenuItem value="archived">Archived</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </Box>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="center">Total Steps</TableCell>
              <TableCell align="center">Active Enrollments</TableCell>
              <TableCell>Created By</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={9} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : sequences.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} align="center">
                  <Box sx={{ py: 8 }}>
                    <Timeline sx={{ fontSize: 80, color: '#FFA500', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary" gutterBottom>
                      {search || statusFilter || typeFilter !== 'all'
                        ? 'No Email Automations Found'
                        : 'No Email Automations Yet'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                      {search || statusFilter || typeFilter !== 'all'
                        ? 'Try adjusting your filters to find automations.'
                        : 'Create automated email sequences to nurture your contacts over time.'}
                    </Typography>
                    {!search && !statusFilter && typeFilter === 'all' && (
                      <Button
                        variant="contained"
                        startIcon={<Add />}
                        onClick={handleCreateSequence}
                        sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
                      >
                        Create Your First Automation
                      </Button>
                    )}
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              sequences.map((sequence) => (
                <TableRow
                  key={sequence.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => handleViewDetails(sequence)}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {sequence.name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={getTypeLabel(sequence.sequence_type || 'manual')}
                      size="small"
                      color={getTypeColor(sequence.sequence_type || 'manual')}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary" noWrap sx={{ maxWidth: 300 }}>
                      {sequence.description || '-'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={sequence.status.charAt(0).toUpperCase() + sequence.status.slice(1)}
                      size="small"
                      color={getStatusColor(sequence.status)}
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2">{sequence.total_steps}</Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2">{sequence.active_enrollments}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{sequence.created_by_name}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{formatDate(sequence.created_at)}</Typography>
                  </TableCell>
                  <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleMenuOpen(e, sequence);
                      }}
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

      {/* Actions Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => selectedSequence && handleViewDetails(selectedSequence)}>
          <ListItemIcon>
            <Visibility fontSize="small" />
          </ListItemIcon>
          <ListItemText>View Details</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => selectedSequence && handleEditSequence(selectedSequence)}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => selectedSequence && handleDuplicateSequence(selectedSequence)}>
          <ListItemIcon>
            <FileCopy fontSize="small" />
          </ListItemIcon>
          <ListItemText>Duplicate</ListItemText>
        </MenuItem>
        {selectedSequence?.status !== 'archived' && (
          <MenuItem onClick={() => selectedSequence && handleArchiveSequence(selectedSequence)}>
            <ListItemIcon>
              <Archive fontSize="small" />
            </ListItemIcon>
            <ListItemText>Archive</ListItemText>
          </MenuItem>
        )}
        <MenuItem onClick={() => selectedSequence && handleDeleteClick(selectedSequence)}>
          <ListItemIcon>
            <Delete fontSize="small" color="error" />
          </ListItemIcon>
          <ListItemText sx={{ color: 'error.main' }}>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Automation?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the automation "{deletingSequence?.name}"? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Form Modal */}
      <SequenceForm
        open={formOpen}
        onClose={handleFormClose}
        sequence={editingSequence}
        onSuccess={handleFormSave}
      />
    </Box>
  );
};

export default EmailAutomations;
