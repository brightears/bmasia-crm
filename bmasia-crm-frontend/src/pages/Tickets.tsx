import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  TextField,
  InputAdornment,
  Skeleton,
  TablePagination,
} from '@mui/material';
import {
  Add,
  MoreVert,
  Refresh,
  Edit,
  Delete,
  Visibility,
  PersonAdd,
  Search,
  SupportAgent,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { Ticket } from '../types';
import ApiService from '../services/api';
import { formatDistanceToNow } from 'date-fns';

const Tickets: React.FC = () => {
  const navigate = useNavigate();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [ticketToDelete, setTicketToDelete] = useState<Ticket | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  const loadTickets = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const params: any = {
        limit: rowsPerPage,
        offset: page * rowsPerPage,
      };

      // Apply filters
      if (searchQuery) {
        params.search = searchQuery;
      }

      switch (activeFilter) {
        case 'my_tickets':
          params.my_tickets = 'true';
          break;
        case 'unassigned':
          params.unassigned = 'true';
          break;
        case 'open':
          params.open = 'true';
          break;
        case 'urgent':
          params.priority = 'urgent';
          break;
      }

      const response = await ApiService.getTickets(params);
      setTickets(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err: any) {
      console.error('Failed to load tickets:', err);
      setError(`Failed to load tickets: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setTickets([]);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, activeFilter, page, rowsPerPage]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, ticket: Ticket) => {
    setAnchorEl(event.currentTarget);
    setSelectedTicket(ticket);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedTicket(null);
  };

  const handleViewDetails = () => {
    if (selectedTicket) {
      navigate(`/tickets/${selectedTicket.id}`);
    }
    handleMenuClose();
  };

  const handleEdit = () => {
    if (selectedTicket) {
      navigate(`/tickets/${selectedTicket.id}/edit`);
    }
    handleMenuClose();
  };

  const handleAssign = () => {
    // TODO: Open assign dialog
    handleMenuClose();
  };

  const handleDeleteClick = () => {
    if (selectedTicket) {
      setTicketToDelete(selectedTicket);
      setDeleteDialogOpen(true);
    }
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    if (!ticketToDelete) return;

    try {
      setDeleteLoading(true);
      await ApiService.deleteTicket(ticketToDelete.id);
      await loadTickets();
      setDeleteDialogOpen(false);
      setTicketToDelete(null);
    } catch (err: any) {
      console.error('Failed to delete ticket:', err);
      setError(`Failed to delete ticket: ${err.response?.data?.detail || err.message}`);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setTicketToDelete(null);
  };

  const handleRowClick = (ticket: Ticket) => {
    navigate(`/tickets/${ticket.id}`);
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const getStatusColor = (status: string): 'default' | 'primary' | 'info' | 'warning' | 'secondary' | 'success' => {
    switch (status) {
      case 'new':
        return 'primary';
      case 'assigned':
        return 'info';
      case 'in_progress':
        return 'warning';
      case 'pending':
        return 'secondary';
      case 'resolved':
        return 'success';
      case 'closed':
        return 'default';
      default:
        return 'default';
    }
  };

  const getPriorityColor = (priority: string): 'default' | 'error' | 'warning' | 'info' => {
    switch (priority) {
      case 'urgent':
        return 'error';
      case 'high':
        return 'warning';
      case 'medium':
        return 'info';
      case 'low':
        return 'default';
      default:
        return 'default';
    }
  };

  const formatStatusLabel = (status: string): string => {
    return status.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  };

  const truncateText = (text: string, maxLength: number): string => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  const formatDate = (dateString: string): string => {
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true });
    } catch {
      return dateString;
    }
  };

  if (loading && tickets.length === 0) {
    return (
      <Box>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Skeleton variant="text" width={250} height={50} />
          <Skeleton variant="rectangular" width={150} height={40} />
        </Box>
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                {[1, 2, 3, 4, 5, 6, 7].map((i) => (
                  <TableCell key={i}>
                    <Skeleton variant="text" />
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {[1, 2, 3, 4, 5].map((row) => (
                <TableRow key={row}>
                  {[1, 2, 3, 4, 5, 6, 7].map((cell) => (
                    <TableCell key={cell}>
                      <Skeleton variant="text" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Support Tickets
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage customer support requests and technical issues
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <IconButton onClick={loadTickets} disabled={loading}>
            <Refresh />
          </IconButton>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => navigate('/tickets/new')}
            sx={{
              bgcolor: '#FFA500',
              '&:hover': { bgcolor: '#FF8C00' },
            }}
          >
            New Ticket
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError('')} sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Filter Chips */}
      <Box display="flex" gap={1} mb={2} flexWrap="wrap">
        <Chip
          label="All"
          onClick={() => setActiveFilter('all')}
          color={activeFilter === 'all' ? 'primary' : 'default'}
          sx={{
            bgcolor: activeFilter === 'all' ? '#FFA500' : undefined,
            '&:hover': { bgcolor: activeFilter === 'all' ? '#FF8C00' : undefined },
          }}
        />
        <Chip
          label="My Tickets"
          onClick={() => setActiveFilter('my_tickets')}
          color={activeFilter === 'my_tickets' ? 'primary' : 'default'}
          sx={{
            bgcolor: activeFilter === 'my_tickets' ? '#FFA500' : undefined,
            '&:hover': { bgcolor: activeFilter === 'my_tickets' ? '#FF8C00' : undefined },
          }}
        />
        <Chip
          label="Unassigned"
          onClick={() => setActiveFilter('unassigned')}
          color={activeFilter === 'unassigned' ? 'primary' : 'default'}
          sx={{
            bgcolor: activeFilter === 'unassigned' ? '#FFA500' : undefined,
            '&:hover': { bgcolor: activeFilter === 'unassigned' ? '#FF8C00' : undefined },
          }}
        />
        <Chip
          label="Open"
          onClick={() => setActiveFilter('open')}
          color={activeFilter === 'open' ? 'primary' : 'default'}
          sx={{
            bgcolor: activeFilter === 'open' ? '#FFA500' : undefined,
            '&:hover': { bgcolor: activeFilter === 'open' ? '#FF8C00' : undefined },
          }}
        />
        <Chip
          label="Urgent"
          onClick={() => setActiveFilter('urgent')}
          color={activeFilter === 'urgent' ? 'primary' : 'default'}
          sx={{
            bgcolor: activeFilter === 'urgent' ? '#FFA500' : undefined,
            '&:hover': { bgcolor: activeFilter === 'urgent' ? '#FF8C00' : undefined },
          }}
        />
      </Box>

      {/* Search Bar */}
      <Box mb={2}>
        <TextField
          fullWidth
          placeholder="Search tickets by number, subject, or company..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ),
          }}
          sx={{ maxWidth: 600 }}
        />
      </Box>

      {/* Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: '#f5f5f5' }}>
              <TableCell width="120px">Ticket #</TableCell>
              <TableCell>Subject</TableCell>
              <TableCell width="180px">Company</TableCell>
              <TableCell width="120px">Status</TableCell>
              <TableCell width="100px">Priority</TableCell>
              <TableCell width="150px">Assigned To</TableCell>
              <TableCell width="130px">Created</TableCell>
              <TableCell width="80px" align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tickets.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center" sx={{ py: 8 }}>
                  <SupportAgent sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    No tickets found
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    {activeFilter !== 'all'
                      ? 'Try changing the filter or search criteria'
                      : 'Create your first support ticket to get started'}
                  </Typography>
                  {activeFilter === 'all' && (
                    <Button
                      variant="contained"
                      startIcon={<Add />}
                      onClick={() => navigate('/tickets/new')}
                      sx={{
                        bgcolor: '#FFA500',
                        '&:hover': { bgcolor: '#FF8C00' },
                      }}
                    >
                      Create Ticket
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              tickets.map((ticket) => (
                <TableRow
                  key={ticket.id}
                  hover
                  onClick={() => handleRowClick(ticket)}
                  sx={{ cursor: 'pointer' }}
                >
                  <TableCell>
                    <Typography
                      variant="body2"
                      fontWeight={500}
                      color="primary"
                      sx={{ color: '#FFA500' }}
                    >
                      {ticket.ticket_number}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {truncateText(ticket.subject, 50)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {ticket.company_name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={formatStatusLabel(ticket.status)}
                      color={getStatusColor(ticket.status)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1)}
                      color={getPriorityColor(ticket.priority)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {ticket.assigned_to_name || 'Unassigned'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {formatDate(ticket.created_at)}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleMenuOpen(e, ticket);
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
        {tickets.length > 0 && (
          <TablePagination
            rowsPerPageOptions={[10, 25, 50, 100]}
            component="div"
            count={totalCount}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
          />
        )}
      </TableContainer>

      {/* Action Menu */}
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleMenuClose}>
        <MenuItem onClick={handleViewDetails}>
          <Visibility fontSize="small" sx={{ mr: 1 }} />
          View Details
        </MenuItem>
        <MenuItem onClick={handleEdit}>
          <Edit fontSize="small" sx={{ mr: 1 }} />
          Edit
        </MenuItem>
        <MenuItem onClick={handleAssign}>
          <PersonAdd fontSize="small" sx={{ mr: 1 }} />
          Assign
        </MenuItem>
        <MenuItem onClick={handleDeleteClick} sx={{ color: 'error.main' }}>
          <Delete fontSize="small" sx={{ mr: 1 }} />
          Delete
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Ticket</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete ticket "{ticketToDelete?.ticket_number}"? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel} disabled={deleteLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disabled={deleteLoading}
            startIcon={deleteLoading ? <CircularProgress size={16} /> : <Delete />}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Tickets;
