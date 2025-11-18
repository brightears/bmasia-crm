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
  const [search, setSearch] = useState('');
  const [templateTypeFilter, setTemplateTypeFilter] = useState('');
  const [languageFilter, setLanguageFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  // Form modal state
  const [formOpen, setFormOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | null>(null);

  // Preview modal state
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTemplateId, setPreviewTemplateId] = useState<string | null>(null);

  // Menu state
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingTemplate, setDeletingTemplate] = useState<EmailTemplate | null>(null);

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
  }, [page, rowsPerPage, search, templateTypeFilter, languageFilter, activeFilter]);

  useEffect(() => {
    loadTemplates();
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
      const duplicateData = {
        ...template,
        name: `${template.name} (Copy)`,
        id: undefined,
        created_at: undefined,
        updated_at: undefined,
      };
      await ApiService.createEmailTemplate(duplicateData);
      setSuccess('Template duplicated successfully');
      loadTemplates();
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
    setSuccess(editingTemplate ? 'Template updated successfully' : 'Template created successfully');
    loadTemplates();
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setEditingTemplate(null);
  };

  const handlePreviewClose = () => {
    setPreviewOpen(false);
    setPreviewTemplateId(null);
  };

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

      <Paper sx={{ mb: 2, p: 2 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
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
          <Grid item xs={12} sm={6} md={2}>
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
          <Grid item xs={12} sm={6} md={2}>
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
          <Grid item xs={12} sm={6} md={2}>
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
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Language</TableCell>
              <TableCell>Department</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : templates.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
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
                <TableRow key={template.id} hover>
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

      {/* Form Modal */}
      <EmailTemplateForm
        open={formOpen}
        onClose={handleFormClose}
        template={editingTemplate}
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
