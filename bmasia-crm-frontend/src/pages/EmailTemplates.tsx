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
  Checkbox,
} from '@mui/material';
import {
  Add,
  Search,
  MoreVert,
  Edit,
  Delete,
  Preview,
  ContentCopy,
  Email,
  Campaign,
  CheckBox,
  CheckBoxOutlineBlank,
  IndeterminateCheckBox,
  Close,
} from '@mui/icons-material';
import { EmailTemplate, ApiResponse } from '../types';
import ApiService from '../services/api';
import EmailTemplateForm from '../components/EmailTemplateForm';
import EmailTemplatePreview from '../components/EmailTemplatePreview';

const EmailTemplates: React.FC = () => {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [info, setInfo] = useState('');
  const [search, setSearch] = useState('');
  const [templateTypeFilter, setTemplateTypeFilter] = useState('');
  const [languageFilter, setLanguageFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [usageFilter, setUsageFilter] = useState<string>('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  // Form modal state
  const [formOpen, setFormOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | null>(null);
  const [duplicateData, setDuplicateData] = useState<Partial<EmailTemplate> | null>(null);

  // Preview modal state
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTemplateId, setPreviewTemplateId] = useState<string | null>(null);

  // Menu state
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingTemplate, setDeletingTemplate] = useState<EmailTemplate | null>(null);

  // Bulk selection state
  const [selected, setSelected] = useState<string[]>([]);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);

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
      if (languageFilter) params.language = languageFilter;
      if (activeFilter) params.is_active = activeFilter === 'true';
      if (usageFilter === 'used') params.has_campaigns = true;
      if (usageFilter === 'unused') params.has_campaigns = false;

      console.log('Loading email templates with params:', params);
      const response: ApiResponse<EmailTemplate> = await ApiService.getEmailTemplates(params);
      console.log('Email Templates API response:', response);

      setTemplates(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err: any) {
      console.error('Email templates error:', err);
      setError(`Failed to load email templates: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setTemplates([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, templateTypeFilter, languageFilter, activeFilter, usageFilter]);

  useEffect(() => {
    loadTemplates();
    // Clear selection on page/filter changes
    setSelected([]);
  }, [loadTemplates]);

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

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, template: EmailTemplate) => {
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

  const handleEditTemplate = (template: EmailTemplate) => {
    setEditingTemplate(template);
    setFormOpen(true);
    handleMenuClose();
  };

  const handlePreviewTemplate = (template: EmailTemplate) => {
    setPreviewTemplateId(template.id);
    setPreviewOpen(true);
    handleMenuClose();
  };

  const handleDuplicateTemplate = async (template: EmailTemplate) => {
    try {
      setError('');
      setInfo('');
      // Call the backend duplicate endpoint to get template data without saving
      const duplicatedData = await ApiService.duplicateEmailTemplate(template.id);

      // Remove id and timestamps to ensure form treats it as new template
      // Append " (Copy)" to the name
      const templateWithCopy = {
        ...duplicatedData,
        id: undefined,
        created_at: undefined,
        updated_at: undefined,
        name: `${duplicatedData.name || template.name} (Copy)`,
      } as Partial<EmailTemplate>;

      // Set the duplicate data and open the form in create mode
      setDuplicateData(templateWithCopy);
      setEditingTemplate(null); // Ensure we're in create mode
      setFormOpen(true);
      setInfo('Template duplicated. Change the template type to save.');
    } catch (err: any) {
      console.error('Duplicate template error:', err);
      setError(`Failed to duplicate template: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    }
    handleMenuClose();
  };

  const handleDeleteClick = (template: EmailTemplate) => {
    setDeletingTemplate(template);
    setDeleteDialogOpen(true);
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    if (!deletingTemplate) return;

    try {
      setError('');
      await ApiService.deleteEmailTemplate(deletingTemplate.id);
      setSuccess('Template deleted successfully');
      loadTemplates();
      setDeleteDialogOpen(false);
      setDeletingTemplate(null);
    } catch (err: any) {
      console.error('Delete template error:', err);
      setError(`Failed to delete template: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setDeletingTemplate(null);
  };

  const handleFormSave = () => {
    setFormOpen(false);
    setEditingTemplate(null);
    setDuplicateData(null);
    setInfo('');
    setSuccess(editingTemplate ? 'Template updated successfully' : 'Template created successfully');
    loadTemplates();
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setEditingTemplate(null);
    setDuplicateData(null);
    setInfo('');
  };

  const handlePreviewClose = () => {
    setPreviewOpen(false);
    setPreviewTemplateId(null);
  };

  // Bulk selection handlers
  const handleSelectAll = () => {
    if (selected.length === templates.length) {
      setSelected([]);
    } else {
      setSelected(templates.map((t) => t.id));
    }
  };

  const handleSelectOne = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleBulkActivate = async () => {
    try {
      setBulkLoading(true);
      setError('');
      const result = await ApiService.bulkOperateEmailTemplates('activate', selected);
      setSuccess(result.message || `${result.count} template(s) activated successfully`);
      setSelected([]);
      loadTemplates();
    } catch (err: any) {
      console.error('Bulk activate error:', err);
      setError(`Failed to activate templates: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkDeactivate = async () => {
    try {
      setBulkLoading(true);
      setError('');
      const result = await ApiService.bulkOperateEmailTemplates('deactivate', selected);
      setSuccess(result.message || `${result.count} template(s) deactivated successfully`);
      setSelected([]);
      loadTemplates();
    } catch (err: any) {
      console.error('Bulk deactivate error:', err);
      setError(`Failed to deactivate templates: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkDeleteClick = () => {
    setBulkDeleteDialogOpen(true);
  };

  const handleBulkDeleteConfirm = async () => {
    try {
      setBulkLoading(true);
      setError('');
      const result = await ApiService.bulkOperateEmailTemplates('delete', selected);
      setSuccess(result.message || `${result.count} template(s) deleted successfully`);
      setSelected([]);
      setBulkDeleteDialogOpen(false);
      loadTemplates();
    } catch (err: any) {
      console.error('Bulk delete error:', err);
      setError(`Failed to delete templates: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkDeleteCancel = () => {
    setBulkDeleteDialogOpen(false);
  };

  const handleClearSelection = () => {
    setSelected([]);
  };

  const isAllSelected = templates.length > 0 && selected.length === templates.length;
  const isIndeterminate = selected.length > 0 && selected.length < templates.length;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Email Templates
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreateTemplate}
          sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
        >
          New Template
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

      {info && (
        <Alert severity="info" sx={{ mb: 2 }} onClose={() => setInfo('')}>
          {info}
        </Alert>
      )}

      <Paper sx={{ mb: 2, p: 2 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={12} lg={4}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search templates by name or subject..."
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
          <Grid item xs={12} sm={6} md={3} lg={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Type</InputLabel>
              <Select
                value={templateTypeFilter}
                label="Type"
                onChange={(e) => {
                  setTemplateTypeFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="">All Types</MenuItem>
                <MenuItem value="renewal_30_days">Renewal 30 Days</MenuItem>
                <MenuItem value="renewal_14_days">Renewal 14 Days</MenuItem>
                <MenuItem value="renewal_7_days">Renewal 7 Days</MenuItem>
                <MenuItem value="renewal_urgent">Renewal Urgent</MenuItem>
                <MenuItem value="invoice_new">Invoice New</MenuItem>
                <MenuItem value="payment_reminder_7_days">Payment Reminder 7 Days</MenuItem>
                <MenuItem value="payment_reminder_14_days">Payment Reminder 14 Days</MenuItem>
                <MenuItem value="payment_overdue">Payment Overdue</MenuItem>
                <MenuItem value="quarterly_checkin">Quarterly Check-in</MenuItem>
                <MenuItem value="seasonal_christmas">Seasonal Christmas</MenuItem>
                <MenuItem value="seasonal_newyear">Seasonal New Year</MenuItem>
                <MenuItem value="seasonal_songkran">Seasonal Songkran</MenuItem>
                <MenuItem value="seasonal_ramadan">Seasonal Ramadan</MenuItem>
                <MenuItem value="zone_offline_48h">Zone Offline 48h</MenuItem>
                <MenuItem value="zone_offline_7d">Zone Offline 7d</MenuItem>
                <MenuItem value="welcome">Welcome</MenuItem>
                <MenuItem value="contract_signed">Contract Signed</MenuItem>
                <MenuItem value="quote_send">Quote Send</MenuItem>
                <MenuItem value="contract_send">Contract Send</MenuItem>
                <MenuItem value="invoice_send">Invoice Send</MenuItem>
                <MenuItem value="renewal_manual">Renewal Manual</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3} lg={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Language</InputLabel>
              <Select
                value={languageFilter}
                label="Language"
                onChange={(e) => {
                  setLanguageFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="">All Languages</MenuItem>
                <MenuItem value="en">English</MenuItem>
                <MenuItem value="th">Thai</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3} lg={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Usage</InputLabel>
              <Select
                value={usageFilter}
                label="Usage"
                onChange={(e) => {
                  setUsageFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="all">All Templates</MenuItem>
                <MenuItem value="used">Used in Campaigns</MenuItem>
                <MenuItem value="unused">Not Used</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3} lg={2}>
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
        </Grid>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  indeterminate={isIndeterminate}
                  checked={isAllSelected}
                  onChange={handleSelectAll}
                  disabled={loading || templates.length === 0}
                />
              </TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Language</TableCell>
              <TableCell>Department</TableCell>
              <TableCell>Campaigns</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : templates.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <Box sx={{ py: 4 }}>
                    <Email sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No templates found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search || templateTypeFilter || languageFilter || activeFilter
                        ? 'Try adjusting your filters'
                        : 'Start by creating your first email template'}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              templates.map((template) => (
                <TableRow
                  key={template.id}
                  hover
                  selected={selected.includes(template.id)}
                  sx={{
                    '&.Mui-selected': {
                      backgroundColor: 'rgba(255, 165, 0, 0.08)',
                      '&:hover': {
                        backgroundColor: 'rgba(255, 165, 0, 0.12)',
                      }
                    }
                  }}
                >
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selected.includes(template.id)}
                      onChange={() => handleSelectOne(template.id)}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {template.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {template.subject}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={template.template_type_display || template.template_type}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={template.language.toUpperCase()}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    {template.department ? (
                      <Typography variant="body2">{template.department}</Typography>
                    ) : (
                      <Typography variant="caption" color="text.secondary">-</Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {template.campaigns_using !== undefined ? (
                      <Chip
                        label={template.campaigns_using === 0 ? 'Not used' : `${template.campaigns_using} campaign${template.campaigns_using === 1 ? '' : 's'}`}
                        size="small"
                        color={template.campaigns_using > 0 ? 'primary' : 'default'}
                        icon={template.campaigns_using > 0 ? <Campaign /> : undefined}
                      />
                    ) : (
                      '-'
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={template.is_active ? 'Active' : 'Inactive'}
                      size="small"
                      color={template.is_active ? 'success' : 'default'}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      onClick={(e) => handleMenuOpen(e, template)}
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
        <MenuItem onClick={() => selectedTemplate && handleEditTemplate(selectedTemplate)}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => selectedTemplate && handlePreviewTemplate(selectedTemplate)}>
          <ListItemIcon>
            <Preview fontSize="small" />
          </ListItemIcon>
          <ListItemText>Preview</ListItemText>
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
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Template?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the template "{deletingTemplate?.name}"? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog open={bulkDeleteDialogOpen} onClose={handleBulkDeleteCancel}>
        <DialogTitle>Delete {selected.length} Template{selected.length === 1 ? '' : 's'}?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete {selected.length} template{selected.length === 1 ? '' : 's'}? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleBulkDeleteCancel} disabled={bulkLoading}>Cancel</Button>
          <Button onClick={handleBulkDeleteConfirm} color="error" variant="contained" disabled={bulkLoading}>
            {bulkLoading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk Actions Bar */}
      {selected.length > 0 && (
        <Paper
          elevation={8}
          sx={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            p: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            zIndex: 1200,
            borderTop: '3px solid #FFA500',
            backgroundColor: 'background.paper',
            flexWrap: 'wrap',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="body1" fontWeight="medium">
              {selected.length} template{selected.length === 1 ? '' : 's'} selected
            </Typography>
            <Button
              variant="outlined"
              size="small"
              onClick={handleBulkActivate}
              disabled={bulkLoading}
              startIcon={bulkLoading ? <CircularProgress size={16} /> : null}
            >
              Activate
            </Button>
            <Button
              variant="outlined"
              size="small"
              onClick={handleBulkDeactivate}
              disabled={bulkLoading}
              startIcon={bulkLoading ? <CircularProgress size={16} /> : null}
            >
              Deactivate
            </Button>
            <Button
              variant="outlined"
              size="small"
              color="error"
              onClick={handleBulkDeleteClick}
              disabled={bulkLoading}
              startIcon={<Delete />}
            >
              Delete
            </Button>
          </Box>
          <IconButton
            size="small"
            onClick={handleClearSelection}
            disabled={bulkLoading}
            sx={{ '&:hover': { backgroundColor: 'rgba(255, 165, 0, 0.1)' } }}
          >
            <Close />
          </IconButton>
        </Paper>
      )}

      {/* Form Modal */}
      <EmailTemplateForm
        open={formOpen}
        onClose={handleFormClose}
        template={(editingTemplate || duplicateData) as EmailTemplate | null}
        onSave={handleFormSave}
      />

      {/* Preview Modal */}
      {previewTemplateId && (
        <EmailTemplatePreview
          open={previewOpen}
          onClose={handlePreviewClose}
          templateId={previewTemplateId}
        />
      )}
    </Box>
  );
};

export default EmailTemplates;
