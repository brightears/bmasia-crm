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
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Visibility,
  Business,
  Delete,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { Company, ApiResponse } from '../types';
import ApiService from '../services/api';
import CompanyForm from '../components/CompanyForm';

const Companies: React.FC = () => {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
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
      };

      console.log('Loading companies with params:', params);
      const response: ApiResponse<Company> = await ApiService.getCompanies(params);
      console.log('Companies API response:', response);
      console.log('Companies count:', response.count, 'Results:', response.results.length);

      setCompanies(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err: any) {
      console.error('Companies error - Full error object:', err);
      console.error('Error response:', err.response);
      console.error('Error message:', err.message);
      setError(`Failed to load companies: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setCompanies([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search]);

  useEffect(() => {
    loadCompanies();
  }, [loadCompanies]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(0); // Reset to first page when searching
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

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Companies
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreateCompany}
        >
          Add Company
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ mb: 2 }}>
        <Box sx={{ p: 2 }}>
          <TextField
            fullWidth
            placeholder="Search companies..."
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
        </Box>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Company Name</TableCell>
              <TableCell>Country</TableCell>
              <TableCell>Industry</TableCell>
              <TableCell>Subscription Plans</TableCell>
              <TableCell>Opportunities</TableCell>
              <TableCell>Contracts</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : companies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <Box sx={{ py: 4 }}>
                    <Business sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No companies found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search ? 'Try adjusting your search terms' : 'Start by adding your first company'}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              companies.map((company) => (
                <TableRow key={company.id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Business sx={{ mr: 1, color: 'text.secondary' }} />
                      <Box>
                        <Typography variant="body2" fontWeight="medium">
                          {company.name}
                        </Typography>
                        {company.website && (
                          <Typography variant="caption" color="text.secondary">
                            {company.website}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                  </TableCell>
                  <TableCell>{company.country || '-'}</TableCell>
                  <TableCell>{company.industry || '-'}</TableCell>
                  <TableCell>
                    <Typography variant="caption" sx={{ maxWidth: 200, display: 'block' }}>
                      {company.subscription_summary || 'No active subscriptions'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={company.opportunities_count} 
                      size="small" 
                      color={company.opportunities_count > 0 ? 'primary' : 'default'}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={company.active_contracts_count} 
                      size="small" 
                      color={company.active_contracts_count > 0 ? 'success' : 'default'}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={company.is_active ? 'Active' : 'Inactive'} 
                      size="small"
                      color={company.is_active ? 'success' : 'default'}
                    />
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      onClick={() => handleViewCompany(company.id)}
                      title="View Details"
                    >
                      <Visibility />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleEditCompany(company)}
                      title="Edit Company"
                    >
                      <Edit />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDeleteClick(company)}
                      title="Delete Company"
                      color="error"
                    >
                      <Delete />
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
            startIcon={deleteLoading ? <CircularProgress size={16} /> : <Delete />}
          >
            {deleteLoading ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Companies;