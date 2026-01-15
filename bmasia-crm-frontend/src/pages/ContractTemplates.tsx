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
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  Add,
  Search,
  MoreVert,
  Edit,
  Delete,
  ContentCopy,
  Description,
} from '@mui/icons-material';
import { useSearchParams } from 'react-router-dom';
import { ContractTemplate, ApiResponse } from '../types';
import ApiService from '../services/api';
import ContractTemplateForm from '../components/ContractTemplateForm';

const TEMPLATE_TYPES = [
  { value: 'preamble', label: 'Preamble' },
  { value: 'payment_thailand', label: 'Payment - Thailand' },
  { value: 'payment_international', label: 'Payment - International' },
  { value: 'activation', label: 'Activation' },
  { value: 'service_standard', label: 'Service - Standard' },
  { value: 'service_managed', label: 'Service - Managed' },
  { value: 'service_custom', label: 'Service - Custom' },
];

const getTypeLabel = (type: string): string => {
  const found = TEMPLATE_TYPES.find(t => t.value === type);
  return found ? found.label : type;
};

const ContractTemplates: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [templates, setTemplates] = useState<ContractTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [search, setSearch] = useState('');
  const [templateTypeFilter, setTemplateTypeFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  // Form modal state
  const [formOpen, setFormOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ContractTemplate | null>(null);

  // Menu state
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<ContractTemplate | null>(null);

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingTemplate, setDeletingTemplate] = useState<ContractTemplate | null>(null);

  const loadTemplates = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
      };

      if (search) params.search = search;
      if (templateTypeFilter) params.template_type = templateTypeFilter;
      if (activeFilter) params.is_active = activeFilter === 'true';

      const response: ApiResponse<ContractTemplate> = await ApiService.getContractTemplates(params);
      setTemplates(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err: any) {
      console.error('Contract templates error:', err);
      setError(`Failed to load templates: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setTemplates([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, templateTypeFilter, activeFilter]);

  // Handle query param for opening create dialog
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setEditingTemplate(null);
      setFormOpen(true);
      searchParams.delete('new');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // Auto-dismiss success messages
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(''), 5000);
      return () => clearTimeout(timer);
    }
  }, [success]);

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

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, template: ContractTemplate) => {
    setAnchorEl(event.currentTarget);
    setSelectedTemplate(template);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedTemplate(null);
  };

  const handleCreateTemplate = () => {
    setEditingTemplate(null);
    setFormOpen(true);
  };

  const handleEditTemplate = (template: ContractTemplate) => {
    setEditingTemplate(template);
    setFormOpen(true);
    handleMenuClose();
  };

  const handleDuplicateTemplate = async (template: ContractTemplate) => {
    try {
      setError('');
      // Create a copy with modified name
      const duplicateData = {
        name: `${template.name} (Copy)`,
        template_type: template.template_type,
        content: template.content,
        version: template.version,
        is_default: false,
        is_active: template.is_active,
      };
      await ApiService.createContractTemplate(duplicateData);
      setSuccess('Template duplicated successfully');
      loadTemplates();
    } catch (err: any) {
      setError(`Failed to duplicate template: ${err.response?.data?.detail || err.message}`);
    }
    handleMenuClose();
  };

  const handleDeleteClick = (template: ContractTemplate) => {
    setDeletingTemplate(template);
    setDeleteDialogOpen(true);
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    if (!deletingTemplate) return;

    try {
      setError('');
      await ApiService.deleteContractTemplate(deletingTemplate.id);
      setSuccess('Template deleted successfully');
      loadTemplates();
    } catch (err: any) {
      setError(`Failed to delete template: ${err.response?.data?.detail || err.message}`);
    } finally {
      setDeleteDialogOpen(false);
      setDeletingTemplate(null);
    }
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setEditingTemplate(null);
  };

  const handleFormSave = () => {
    setSuccess(editingTemplate ? 'Template updated successfully' : 'Template created successfully');
    loadTemplates();
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Description sx={{ fontSize: 32, color: 'primary.main' }} />
          <Typography variant="h4" component="h1">
            Contract Templates
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreateTemplate}
        >
          Create Template
        </Button>
      </Box>

      {/* Alerts */}
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

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search templates..."
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
          <Grid item xs={12} sm={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Template Type</InputLabel>
              <Select
                value={templateTypeFilter}
                label="Template Type"
                onChange={(e) => {
                  setTemplateTypeFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="">All Types</MenuItem>
                {TEMPLATE_TYPES.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Status</InputLabel>
              <Select
                value={activeFilter}
                label="Status"
                onChange={(e) => {
                  setActiveFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="true">Active</MenuItem>
                <MenuItem value="false">Inactive</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={2}>
            <Typography variant="body2" color="text.secondary">
              {totalCount} template{totalCount !== 1 ? 's' : ''}
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Table */}
      <TableContainer component={Paper}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : templates.length === 0 ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">
              No templates found. Create your first template to get started.
            </Typography>
          </Box>
        ) : (
          <>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Version</TableCell>
                  <TableCell align="center">Default</TableCell>
                  <TableCell align="center">Status</TableCell>
                  <TableCell>Updated</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {templates.map((template) => (
                  <TableRow key={template.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500}>
                        {template.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={getTypeLabel(template.template_type)}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>{template.version}</TableCell>
                    <TableCell align="center">
                      {template.is_default && (
                        <Chip label="Default" size="small" color="primary" />
                      )}
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={template.is_active ? 'Active' : 'Inactive'}
                        size="small"
                        color={template.is_active ? 'success' : 'default'}
                      />
                    </TableCell>
                    <TableCell>{formatDate(template.updated_at)}</TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={(e) => handleMenuOpen(e, template)}
                      >
                        <MoreVert />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <TablePagination
              rowsPerPageOptions={[10, 25, 50]}
              component="div"
              count={totalCount}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={handleChangePage}
              onRowsPerPageChange={handleChangeRowsPerPage}
            />
          </>
        )}
      </TableContainer>

      {/* Context Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => selectedTemplate && handleEditTemplate(selectedTemplate)}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => selectedTemplate && handleDuplicateTemplate(selectedTemplate)}>
          <ListItemIcon>
            <ContentCopy fontSize="small" />
          </ListItemIcon>
          <ListItemText>Duplicate</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => selectedTemplate && handleDeleteClick(selectedTemplate)}>
          <ListItemIcon>
            <Delete fontSize="small" color="error" />
          </ListItemIcon>
          <ListItemText sx={{ color: 'error.main' }}>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Template</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete the template "{deletingTemplate?.name}"?
            This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Form Modal */}
      <ContractTemplateForm
        open={formOpen}
        onClose={handleFormClose}
        onSave={handleFormSave}
        template={editingTemplate}
      />
    </Box>
  );
};

export default ContractTemplates;
