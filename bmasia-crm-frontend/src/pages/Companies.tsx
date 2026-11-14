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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  FormControl,
  Select,
  MenuItem,
  Avatar,
  Skeleton,
  Tooltip,
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Visibility,
  Business,
  Delete,
  Sort,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { Company, ApiResponse } from '../types';
import ApiService from '../services/api';
import CompanyForm from '../components/CompanyForm';
import { PageHeader, EmptyState, ProductChip } from '../components/ui';
import { visuallyHidden } from '../theme/a11y';
import { initialsOf } from '../theme';

const companyInitials = initialsOf;

const websiteHost = (url?: string) => {
  if (!url) return '';
  return url.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/$/, '');
};

const sortOptions = [
  { value: 'name', label: 'Name A-Z' },
  { value: '-name', label: 'Name Z-A' },
  { value: '-created_at', label: 'Newest First' },
  { value: 'created_at', label: 'Oldest First' },
  { value: '-updated_at', label: 'Recently Updated' },
  { value: 'country', label: 'Country' },
];

const Companies: React.FC = () => {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [companyToDelete, setCompanyToDelete] = useState<Company | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const loadCompanies = useCallback(async () => {
    try {
      setLoading(true);
      setError(''); // Clear previous errors
      const params = {
        page: page + 1,
        page_size: rowsPerPage,
        search: search || undefined,
        ordering: sortBy,
      };

      const response: ApiResponse<Company> = await ApiService.getCompanies(params);

      setCompanies(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err: any) {
      console.error('Companies error:', err);
      setError(`Failed to load companies: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setCompanies([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, sortBy]);

  useEffect(() => {
    loadCompanies();
  }, [loadCompanies]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(0); // Reset to first page when searching
  };

  const handleSortChange = (event: any) => {
    setSortBy(event.target.value);
    setPage(0); // Reset to first page when sorting
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleViewCompany = (id: string) => {
    navigate(`/companies/${id}`);
  };

  const handleCreateCompany = () => {
    setEditingCompany(null);
    setFormOpen(true);
  };

  const handleEditCompany = (company: Company) => {
    setEditingCompany(company);
    setFormOpen(true);
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setEditingCompany(null);
  };

  const handleFormSave = () => {
    // Refresh the list after save
    loadCompanies();
    // Reset form state
    setFormOpen(false);
    setEditingCompany(null);
  };

  const handleDeleteClick = (company: Company) => {
    setCompanyToDelete(company);
    setDeleteDialogOpen(true);
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setCompanyToDelete(null);
  };

  const handleDeleteConfirm = async () => {
    if (!companyToDelete) return;

    try {
      setDeleteLoading(true);
      setError('');
      await ApiService.deleteCompany(companyToDelete.id);

      // Refresh the list after successful deletion
      loadCompanies();

      // Close dialog and reset state
      setDeleteDialogOpen(false);
      setCompanyToDelete(null);
    } catch (err: any) {
      console.error('Delete company error:', err);
      setError(`Failed to delete company: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setDeleteLoading(false);
    }
  };

  const hideOnMobile = { display: { xs: 'none', md: 'table-cell' } };
  const wideOnly = { display: { xs: 'none', xl: 'table-cell' } };

  return (
    <Box>
      <PageHeader
        title="Companies"
        subtitle="Every customer account, with its product, contracts and open opportunities."
        actions={
          <Button variant="contained" startIcon={<Add />} onClick={handleCreateCompany}>
            Add Company
          </Button>
        }
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ overflow: 'hidden' }}>
        {/* Toolbar: search first, then sort */}
        <Box
          sx={{
            p: 2,
            display: 'flex',
            gap: 1.5,
            alignItems: 'center',
            flexWrap: { xs: 'wrap', sm: 'nowrap' },
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <TextField
            fullWidth
            placeholder="Search by company name, country or website"
            value={search}
            onChange={handleSearchChange}
            inputProps={{ 'aria-label': 'Search companies' }}
            sx={{ maxWidth: { sm: 480 } }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <Box sx={{ flexGrow: 1, display: { xs: 'none', sm: 'block' } }} />
          <FormControl size="small" sx={{ minWidth: 190 }}>
            <Select
              value={sortBy}
              onChange={handleSortChange}
              inputProps={{ 'aria-label': 'Sort companies' }}
              startAdornment={<Sort sx={{ mr: 0.5, ml: -0.5, color: 'text.secondary', fontSize: 18 }} />}
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

        <TableContainer sx={{ borderRadius: 0 }}>
          <Table aria-label="Companies">
            <TableHead>
              <TableRow>
                <TableCell>Company</TableCell>
                <TableCell sx={hideOnMobile}>Product</TableCell>
                <TableCell sx={hideOnMobile}>Country</TableCell>
                <TableCell sx={hideOnMobile}>Industry</TableCell>
                <TableCell sx={wideOnly}>Plan</TableCell>
                <TableCell sx={hideOnMobile} align="right">Opportunities</TableCell>
                <TableCell sx={hideOnMobile} align="right">Active contracts</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">
                  <Box component="span" sx={visuallyHidden}>Actions</Box>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={`skeleton-${i}`}>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Skeleton variant="rounded" width={32} height={32} />
                        <Box sx={{ flex: 1 }}>
                          <Skeleton width="60%" />
                          <Skeleton width="40%" />
                        </Box>
                      </Box>
                    </TableCell>
                    {Array.from({ length: 8 }).map((__, j) => (
                      <TableCell key={j} sx={j === 3 ? wideOnly : j < 6 ? hideOnMobile : undefined}>
                        <Skeleton width={j === 7 ? 60 : '70%'} />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : companies.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9}>
                    <EmptyState
                      icon={<Business />}
                      title={search ? 'No companies match your search' : 'No companies yet'}
                      description={
                        search
                          ? 'Check the spelling or search for part of the name.'
                          : 'Add your first customer to start tracking contracts and opportunities.'
                      }
                      action={
                        !search && (
                          <Button variant="contained" startIcon={<Add />} onClick={handleCreateCompany}>
                            Add Company
                          </Button>
                        )
                      }
                    />
                  </TableCell>
                </TableRow>
              ) : (
                companies.map((company) => (
                  <TableRow
                    key={company.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => handleViewCompany(company.id)}
                  >
                    <TableCell sx={{ maxWidth: { xs: 190, md: 300 } }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Avatar variant="rounded" sx={{ width: 32, height: 32, fontSize: '0.75rem' }}>
                          {companyInitials(company.name)}
                        </Avatar>
                        <Box sx={{ minWidth: 0 }}>
                          <Typography sx={{ fontWeight: 600, fontSize: '0.875rem' }} noWrap>
                            {company.name}
                          </Typography>
                          <Typography variant="body2" color="text.secondary" noWrap>
                            {[company.city, websiteHost(company.website)].filter(Boolean).join(' · ') || '—'}
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell sx={hideOnMobile}>
                      {company.contracted_product ? (
                        <ProductChip value={company.contracted_product} />
                      ) : (
                        <Typography variant="body2" color="text.disabled">—</Typography>
                      )}
                    </TableCell>
                    <TableCell sx={hideOnMobile}>{company.country || '—'}</TableCell>
                    <TableCell sx={hideOnMobile}>{company.industry || '—'}</TableCell>
                    <TableCell sx={wideOnly}>
                      <Typography variant="body2" color={company.subscription_summary ? 'text.primary' : 'text.secondary'} sx={{ maxWidth: 200 }}>
                        {company.subscription_summary || 'No active subscriptions'}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ ...hideOnMobile, fontVariantNumeric: 'tabular-nums' }} align="right">
                      {company.opportunities_count > 0 ? company.opportunities_count : <Box component="span" sx={{ color: 'text.disabled' }}>0</Box>}
                    </TableCell>
                    <TableCell sx={{ ...hideOnMobile, fontVariantNumeric: 'tabular-nums' }} align="right">
                      {company.active_contracts_count > 0 ? company.active_contracts_count : <Box component="span" sx={{ color: 'text.disabled' }}>0</Box>}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={company.is_active ? 'Active' : 'Inactive'}
                        size="small"
                        color={company.is_active ? 'success' : 'default'}
                      />
                    </TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap', py: 0.5 }}>
                      <Box className="row-actions">
                        <Tooltip title="Open">
                          <IconButton
                            size="small"
                            aria-label={`Open ${company.name}`}
                            onClick={(e) => { e.stopPropagation(); handleViewCompany(company.id); }}
                          >
                            <Visibility fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Edit">
                          <IconButton
                            size="small"
                            aria-label={`Edit ${company.name}`}
                            onClick={(e) => { e.stopPropagation(); handleEditCompany(company); }}
                          >
                            <Edit fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            aria-label={`Delete ${company.name}`}
                            onClick={(e) => { e.stopPropagation(); handleDeleteClick(company); }}
                            sx={{ '&:hover': { color: 'error.main' } }}
                          >
                            <Delete fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
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
      </Paper>

      {/* Company Form Modal */}
      <CompanyForm
        open={formOpen}
        onClose={handleFormClose}
        onSave={handleFormSave}
        company={editingCompany}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteCancel}
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-description"
      >
        <DialogTitle id="delete-dialog-title">
          Delete Company?
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="delete-dialog-description">
            Are you sure you want to delete <strong>{companyToDelete?.name}</strong>?
            This action cannot be undone and will remove all associated data.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleDeleteCancel}
            disabled={deleteLoading}
          >
            Cancel
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disabled={deleteLoading}
            startIcon={deleteLoading ? <CircularProgress size={16} color="inherit" /> : <Delete />}
          >
            {deleteLoading ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Companies;
