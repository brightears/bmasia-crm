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
  Tooltip,
} from '@mui/material';
import {
  Add,
  MoreVert,
  Refresh,
  Edit,
  Delete,
  Group,
  FileCopy,
  PlaylistAdd,
  AutoFixHigh,
  FiberManualRecord,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { CustomerSegment } from '../types';
import ApiService from '../services/api';
import EnrollSegmentDialog from '../components/EnrollSegmentDialog';

const Segments: React.FC = () => {
  const navigate = useNavigate();
  const [segments, setSegments] = useState<CustomerSegment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedSegment, setSelectedSegment] = useState<CustomerSegment | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [segmentToDelete, setSegmentToDelete] = useState<CustomerSegment | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [enrollDialogOpen, setEnrollDialogOpen] = useState(false);
  const [enrollSegment, setEnrollSegment] = useState<CustomerSegment | null>(null);

  const loadSegments = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const response = await ApiService.getSegments();
      setSegments(response.results || []);
    } catch (err: any) {
      console.error('Failed to load segments:', err);
      setError(`Failed to load segments: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setSegments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSegments();
  }, [loadSegments]);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, segment: CustomerSegment) => {
    setAnchorEl(event.currentTarget);
    setSelectedSegment(segment);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedSegment(null);
  };

  const handleViewMembers = () => {
    if (selectedSegment) {
      navigate(`/segments/${selectedSegment.id}/members`);
    }
    handleMenuClose();
  };

  const handleEdit = () => {
    if (selectedSegment) {
      navigate(`/segments/${selectedSegment.id}/edit`);
    }
    handleMenuClose();
  };

  const handleRecalculate = async () => {
    if (!selectedSegment) return;

    try {
      await ApiService.recalculateSegment(selectedSegment.id);
      await loadSegments(); // Refresh the list
      handleMenuClose();
    } catch (err: any) {
      console.error('Failed to recalculate segment:', err);
      setError(`Failed to recalculate segment: ${err.response?.data?.detail || err.message}`);
      handleMenuClose();
    }
  };

  const handleEnrollInSequence = () => {
    if (selectedSegment) {
      setEnrollSegment(selectedSegment);
      setEnrollDialogOpen(true);
    }
    handleMenuClose();
  };

  const handleDuplicate = async () => {
    if (!selectedSegment) return;

    try {
      const newName = `${selectedSegment.name} (Copy)`;
      await ApiService.duplicateSegment(selectedSegment.id, { name: newName });
      await loadSegments(); // Refresh the list
      handleMenuClose();
    } catch (err: any) {
      console.error('Failed to duplicate segment:', err);
      setError(`Failed to duplicate segment: ${err.response?.data?.detail || err.message}`);
      handleMenuClose();
    }
  };

  const handleDeleteClick = () => {
    if (selectedSegment) {
      setSegmentToDelete(selectedSegment);
      setDeleteDialogOpen(true);
    }
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    if (!segmentToDelete) return;

    try {
      setDeleteLoading(true);
      await ApiService.deleteSegment(segmentToDelete.id);
      await loadSegments();
      setDeleteDialogOpen(false);
      setSegmentToDelete(null);
    } catch (err: any) {
      console.error('Failed to delete segment:', err);
      setError(`Failed to delete segment: ${err.response?.data?.detail || err.message}`);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setSegmentToDelete(null);
  };

  const handleEnrollSuccess = () => {
    setEnrollDialogOpen(false);
    setEnrollSegment(null);
    loadSegments();
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

  const getTypeIcon = (type: string) => {
    return type === 'dynamic' ? <AutoFixHigh fontSize="small" /> : <FiberManualRecord fontSize="small" />;
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress sx={{ color: '#FFA500' }} />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Customer Segments
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Create and manage customer segments for targeted campaigns
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => navigate('/segments/new')}
          sx={{
            bgcolor: '#FFA500',
            '&:hover': { bgcolor: '#FF8C00' },
          }}
        >
          New Segment
        </Button>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError('')} sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: '#f5f5f5' }}>
              <TableCell width="50px">Type</TableCell>
              <TableCell>Segment</TableCell>
              <TableCell width="120px">Status</TableCell>
              <TableCell width="100px" align="center">Members</TableCell>
              <TableCell width="130px">Last Used</TableCell>
              <TableCell width="100px" align="center">Times Used</TableCell>
              <TableCell width="80px" align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {segments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                  <Group sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    No segments yet
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Create your first segment to organize and target your customers
                  </Typography>
                  <Button
                    variant="contained"
                    startIcon={<Add />}
                    onClick={() => navigate('/segments/new')}
                    sx={{
                      bgcolor: '#FFA500',
                      '&:hover': { bgcolor: '#FF8C00' },
                    }}
                  >
                    Create Segment
                  </Button>
                </TableCell>
              </TableRow>
            ) : (
              segments.map((segment) => (
                <TableRow key={segment.id} hover>
                  <TableCell>
                    <Tooltip title={segment.segment_type === 'dynamic' ? 'Dynamic - Auto-updates' : 'Static - Fixed members'}>
                      <Box display="flex" alignItems="center" color={segment.segment_type === 'dynamic' ? '#FFA500' : 'text.secondary'}>
                        {getTypeIcon(segment.segment_type)}
                      </Box>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {segment.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {segment.description}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={segment.status.charAt(0).toUpperCase() + segment.status.slice(1)}
                      color={getStatusColor(segment.status)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2" fontWeight={500}>
                      {segment.member_count.toLocaleString()}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {formatDate(segment.last_used_at)}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2" color="text.secondary">
                      {segment.times_used}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      onClick={(e) => handleMenuOpen(e, segment)}
                    >
                      <MoreVert />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleViewMembers}>
          <Group fontSize="small" sx={{ mr: 1 }} />
          View Members
        </MenuItem>
        <MenuItem onClick={handleEdit}>
          <Edit fontSize="small" sx={{ mr: 1 }} />
          Edit
        </MenuItem>
        {selectedSegment?.segment_type === 'dynamic' && (
          <MenuItem onClick={handleRecalculate}>
            <Refresh fontSize="small" sx={{ mr: 1 }} />
            Recalculate
          </MenuItem>
        )}
        <MenuItem onClick={handleEnrollInSequence}>
          <PlaylistAdd fontSize="small" sx={{ mr: 1 }} />
          Enroll in Sequence
        </MenuItem>
        <MenuItem onClick={handleDuplicate}>
          <FileCopy fontSize="small" sx={{ mr: 1 }} />
          Duplicate
        </MenuItem>
        <MenuItem onClick={handleDeleteClick} sx={{ color: 'error.main' }}>
          <Delete fontSize="small" sx={{ mr: 1 }} />
          Delete
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Segment</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete "{segmentToDelete?.name}"? This action cannot be undone.
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

      {/* Enroll in Sequence Dialog */}
      {enrollSegment && (
        <EnrollSegmentDialog
          open={enrollDialogOpen}
          onClose={() => {
            setEnrollDialogOpen(false);
            setEnrollSegment(null);
          }}
          segment={enrollSegment}
          onSuccess={handleEnrollSuccess}
        />
      )}
    </Box>
  );
};

export default Segments;
