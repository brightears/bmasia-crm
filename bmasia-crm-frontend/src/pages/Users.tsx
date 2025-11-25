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
  InputLabel,
  Select,
  MenuItem,
  Snackbar,
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Delete,
  CheckCircle,
  Cancel as CancelIcon,
  Person,
  Block,
} from '@mui/icons-material';
import { User, UserRole, USER_ROLE_LABELS, ApiResponse } from '../types';
import ApiService from '../services/api';
import UserForm from '../components/UserForm';

const Users: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<UserRole | 'All'>('All');
  const [statusFilter, setStatusFilter] = useState<'All' | 'Active' | 'Inactive'>('All');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error'>('success');

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
        search: search || undefined,
      };

      // Add role filter
      if (roleFilter !== 'All') {
        params.role = roleFilter;
      }

      // Add status filter
      if (statusFilter === 'Active') {
        params.is_active = 'true';
      } else if (statusFilter === 'Inactive') {
        params.is_active = 'false';
      }

      const response: ApiResponse<User> = await ApiService.getUsers(params);
      setUsers(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err: any) {
      console.error('Users error:', err);
      setError(`Failed to load users: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setUsers([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, roleFilter, statusFilter]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(0);
  };

  const handleRoleFilterChange = (event: any) => {
    setRoleFilter(event.target.value);
    setPage(0);
  };

  const handleStatusFilterChange = (event: any) => {
    setStatusFilter(event.target.value);
    setPage(0);
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleCreateUser = () => {
    setEditingUser(null);
    setFormOpen(true);
  };

  const handleEditUser = (user: User) => {
    setEditingUser(user);
    setFormOpen(true);
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setEditingUser(null);
  };

  const handleFormSuccess = (message: string) => {
    loadUsers();
    setFormOpen(false);
    setEditingUser(null);
    showSnackbar(message, 'success');
  };

  const handleDeleteClick = (user: User) => {
    setUserToDelete(user);
    setDeleteDialogOpen(true);
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setUserToDelete(null);
  };

  const handleDeleteConfirm = async () => {
    if (!userToDelete) return;

    try {
      setDeleteLoading(true);
      setError('');
      await ApiService.deleteUser(userToDelete.id);
      loadUsers();
      setDeleteDialogOpen(false);
      setUserToDelete(null);
      showSnackbar('User deleted successfully', 'success');
    } catch (err: any) {
      console.error('Delete user error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      setError(`Failed to delete user: ${errorMsg}`);
      showSnackbar(`Failed to delete user: ${errorMsg}`, 'error');
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleToggleActive = async (user: User) => {
    try {
      if (user.is_active) {
        await ApiService.deactivateUser(user.id);
        showSnackbar(`${user.full_name || user.username} deactivated successfully`, 'success');
      } else {
        await ApiService.activateUser(user.id);
        showSnackbar(`${user.full_name || user.username} activated successfully`, 'success');
      }
      loadUsers();
    } catch (err: any) {
      console.error('Toggle active error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      showSnackbar(`Failed to update user status: ${errorMsg}`, 'error');
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  };

  const handleSnackbarClose = () => {
    setSnackbarOpen(false);
  };

  const getRoleColor = (role: UserRole | string): 'error' | 'primary' | 'success' | 'info' | 'warning' => {
    switch (role) {
      case 'Admin':
        return 'error';
      case 'Sales':
        return 'primary';
      case 'Finance':
        return 'success';
      case 'Tech':
        return 'info';
      case 'Music':
        return 'warning';
      default:
        return 'primary';
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          User Management
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreateUser}
        >
          Add User
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ mb: 2 }}>
        <Box sx={{ p: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            placeholder="Search by name or email..."
            value={search}
            onChange={handleSearchChange}
            sx={{ flexGrow: 1, minWidth: 250 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />
          <FormControl sx={{ minWidth: 150 }}>
            <InputLabel>Role</InputLabel>
            <Select
              value={roleFilter}
              onChange={handleRoleFilterChange}
              label="Role"
            >
              <MenuItem value="All">All Roles</MenuItem>
              <MenuItem value="Sales">Sales</MenuItem>
              <MenuItem value="Finance">Finance</MenuItem>
              <MenuItem value="Tech">Tech Support</MenuItem>
              <MenuItem value="Music">Music Design</MenuItem>
              <MenuItem value="Admin">Administrator</MenuItem>
            </Select>
          </FormControl>
          <FormControl sx={{ minWidth: 150 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={statusFilter}
              onChange={handleStatusFilterChange}
              label="Status"
            >
              <MenuItem value="All">All</MenuItem>
              <MenuItem value="Active">Active</MenuItem>
              <MenuItem value="Inactive">Inactive</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Department</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>SMTP</TableCell>
              <TableCell>Last Login</TableCell>
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
            ) : users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <Box sx={{ py: 4 }}>
                    <Person sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No users found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search || roleFilter !== 'All' || statusFilter !== 'All'
                        ? 'Try adjusting your filters'
                        : 'Start by adding your first user'}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => (
                <TableRow key={user.id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Person sx={{ mr: 1, color: 'text.secondary' }} />
                      <Box>
                        <Typography variant="body2" fontWeight="medium">
                          {user.full_name || `${user.first_name} ${user.last_name}`.trim() || user.username}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          @{user.username}
                        </Typography>
                      </Box>
                    </Box>
                  </TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>
                    <Chip
                      label={USER_ROLE_LABELS[user.role as UserRole] || user.role}
                      size="small"
                      color={getRoleColor(user.role as UserRole)}
                    />
                  </TableCell>
                  <TableCell>{user.department || '-'}</TableCell>
                  <TableCell>
                    <Chip
                      label={user.is_active ? 'Active' : 'Inactive'}
                      size="small"
                      color={user.is_active ? 'success' : 'default'}
                      icon={user.is_active ? <CheckCircle /> : <Block />}
                    />
                  </TableCell>
                  <TableCell>
                    {user.smtp_configured ? (
                      <CheckCircle sx={{ color: 'success.main', fontSize: 20 }} />
                    ) : (
                      <CancelIcon sx={{ color: 'text.disabled', fontSize: 20 }} />
                    )}
                  </TableCell>
                  <TableCell>
                    {user.last_login ? (
                      <Typography variant="caption">
                        {new Date(user.last_login).toLocaleDateString()}
                      </Typography>
                    ) : (
                      <Typography variant="caption" color="text.secondary">
                        Never
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      onClick={() => handleEditUser(user)}
                      title="Edit User"
                    >
                      <Edit />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleToggleActive(user)}
                      title={user.is_active ? 'Deactivate User' : 'Activate User'}
                      color={user.is_active ? 'warning' : 'success'}
                    >
                      {user.is_active ? <Block /> : <CheckCircle />}
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDeleteClick(user)}
                      title="Delete User"
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

      {/* User Form Modal */}
      <UserForm
        open={formOpen}
        onClose={handleFormClose}
        onSuccess={handleFormSuccess}
        user={editingUser}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteCancel}
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-description"
      >
        <DialogTitle id="delete-dialog-title">
          Delete User?
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="delete-dialog-description">
            Are you sure you want to delete <strong>{userToDelete?.full_name || userToDelete?.username}</strong>?
            This action cannot be undone and will remove all user data.
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

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={4000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleSnackbarClose} severity={snackbarSeverity} sx={{ width: '100%' }}>
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Users;
