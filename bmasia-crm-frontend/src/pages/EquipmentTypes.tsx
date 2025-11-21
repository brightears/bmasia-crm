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
} from '@mui/material';
import {
  Add,
  MoreVert,
  Edit,
  Delete,
  Category,
} from '@mui/icons-material';
import * as Icons from '@mui/icons-material';
import { EquipmentType } from '../types';
import ApiService from '../services/api';
import EquipmentTypeForm from '../components/EquipmentTypeForm';

// Helper function to render Material-UI icon by name
const renderIcon = (iconName: string) => {
  // Convert icon name to PascalCase (e.g., 'phone_android' -> 'PhoneAndroid')
  const pascalCase = iconName
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join('');

  const IconComponent = (Icons as any)[pascalCase];
  return IconComponent ? <IconComponent /> : <Icons.DevicesOther />;
};

const EquipmentTypes: React.FC = () => {
  const [equipmentTypes, setEquipmentTypes] = useState<EquipmentType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedType, setSelectedType] = useState<EquipmentType | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [typeToDelete, setTypeToDelete] = useState<EquipmentType | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editingType, setEditingType] = useState<EquipmentType | null>(null);

  const loadEquipmentTypes = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const response = await ApiService.getEquipmentTypes();
      setEquipmentTypes(response.results || []);
    } catch (err: any) {
      console.error('Failed to load equipment types:', err);
      setError(
        `Failed to load equipment types: ${
          err.response?.data?.detail || err.message || 'Unknown error'
        }`
      );
      setEquipmentTypes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEquipmentTypes();
  }, [loadEquipmentTypes]);

  const handleMenuOpen = (
    event: React.MouseEvent<HTMLElement>,
    type: EquipmentType
  ) => {
    setAnchorEl(event.currentTarget);
    setSelectedType(type);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedType(null);
  };

  const handleEdit = () => {
    if (selectedType) {
      setEditingType(selectedType);
      setFormOpen(true);
    }
    handleMenuClose();
  };

  const handleDeleteClick = () => {
    if (selectedType) {
      setTypeToDelete(selectedType);
      setDeleteDialogOpen(true);
    }
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    if (!typeToDelete) return;

    try {
      setDeleteLoading(true);
      await ApiService.deleteEquipmentType(typeToDelete.id);
      await loadEquipmentTypes();
      setDeleteDialogOpen(false);
      setTypeToDelete(null);
    } catch (err: any) {
      console.error('Failed to delete equipment type:', err);
      setError(
        `Failed to delete equipment type: ${
          err.response?.data?.detail || err.message
        }`
      );
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setTypeToDelete(null);
  };

  const handleNewType = () => {
    setEditingType(null);
    setFormOpen(true);
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setEditingType(null);
  };

  const handleFormSave = async () => {
    setFormOpen(false);
    setEditingType(null);
    await loadEquipmentTypes();
  };

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="400px"
      >
        <CircularProgress sx={{ color: '#FFA500' }} />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={3}
      >
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Equipment Types
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage equipment categories and types for your organization
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleNewType}
          sx={{
            bgcolor: '#FFA500',
            '&:hover': { bgcolor: '#FF8C00' },
          }}
        >
          New Equipment Type
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
              <TableCell width="60px" align="center">
                Icon
              </TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Description</TableCell>
              <TableCell width="150px" align="center">
                Equipment Count
              </TableCell>
              <TableCell width="80px" align="center">
                Actions
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {equipmentTypes.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 8 }}>
                  <Category
                    sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }}
                  />
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    No equipment types yet
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mb: 3 }}
                  >
                    Create your first equipment type to categorize your devices
                  </Typography>
                  <Button
                    variant="contained"
                    startIcon={<Add />}
                    onClick={handleNewType}
                    sx={{
                      bgcolor: '#FFA500',
                      '&:hover': { bgcolor: '#FF8C00' },
                    }}
                  >
                    Create Equipment Type
                  </Button>
                </TableCell>
              </TableRow>
            ) : (
              equipmentTypes.map((type) => (
                <TableRow key={type.id} hover>
                  <TableCell align="center">
                    <Box
                      sx={{
                        color: '#FFA500',
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                      }}
                    >
                      {renderIcon(type.icon)}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {type.name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {type.description || '-'}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Chip
                      label={type.equipment_count || 0}
                      size="small"
                      sx={{ minWidth: 50 }}
                    />
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      onClick={(e) => handleMenuOpen(e, type)}
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
        <MenuItem onClick={handleEdit}>
          <Edit fontSize="small" sx={{ mr: 1 }} />
          Edit
        </MenuItem>
        <MenuItem onClick={handleDeleteClick} sx={{ color: 'error.main' }}>
          <Delete fontSize="small" sx={{ mr: 1 }} />
          Delete
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Equipment Type</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete "{typeToDelete?.name}"?
            {typeToDelete?.equipment_count && typeToDelete.equipment_count > 0 ? (
              <Box sx={{ mt: 1, color: 'error.main' }}>
                Warning: This type is currently used by {typeToDelete.equipment_count} equipment item(s).
              </Box>
            ) : null}
            This action cannot be undone.
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
            startIcon={
              deleteLoading ? <CircularProgress size={16} /> : <Delete />
            }
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Equipment Type Form Dialog */}
      <EquipmentTypeForm
        open={formOpen}
        onClose={handleFormClose}
        onSave={handleFormSave}
        equipmentType={editingType}
      />
    </Box>
  );
};

export default EquipmentTypes;
