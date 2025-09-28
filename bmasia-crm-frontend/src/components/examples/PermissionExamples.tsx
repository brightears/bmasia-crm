import React from 'react';
import { Button, Box, Typography, Chip } from '@mui/material';
import { Add, Edit, Delete, Download } from '@mui/icons-material';
import PermissionWrapper from '../PermissionWrapper';
import { usePermissions } from '../../hooks/usePermissions';

/**
 * Example components showing how to use permission-based UI controls
 * This file serves as documentation and reference for implementing permissions
 */

const PermissionExamples: React.FC = () => {
  const permissions = usePermissions();

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Permission-Based UI Examples
      </Typography>

      {/* Basic Permission Wrapper Examples */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          1. Basic Permission Checks
        </Typography>

        {/* Show button only if user can create companies */}
        <PermissionWrapper permission="create_companies">
          <Button variant="contained" startIcon={<Add />} sx={{ mr: 2 }}>
            Add Company
          </Button>
        </PermissionWrapper>

        {/* Show button only if user can edit companies */}
        <PermissionWrapper permission="edit_companies">
          <Button variant="outlined" startIcon={<Edit />} sx={{ mr: 2 }}>
            Edit Company
          </Button>
        </PermissionWrapper>

        {/* Show button only if user can delete companies */}
        <PermissionWrapper permission="delete_companies">
          <Button variant="outlined" color="error" startIcon={<Delete />}>
            Delete Company
          </Button>
        </PermissionWrapper>
      </Box>

      {/* Role-Based Examples */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          2. Role-Based Controls
        </Typography>

        {/* Admin-only content */}
        <PermissionWrapper role="Admin">
          <Chip label="Admin Only" color="error" sx={{ mr: 1 }} />
        </PermissionWrapper>

        {/* Sales or Marketing roles */}
        <PermissionWrapper role={['Sales', 'Marketing']}>
          <Chip label="Sales/Marketing" color="primary" sx={{ mr: 1 }} />
        </PermissionWrapper>

        {/* Tech Support or Admin */}
        <PermissionWrapper role={['Tech Support', 'Admin']}>
          <Chip label="Tech/Admin" color="secondary" />
        </PermissionWrapper>
      </Box>

      {/* Module Access Examples */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          3. Module Access Controls
        </Typography>

        <PermissionWrapper module="analytics">
          <Button variant="contained" color="info" sx={{ mr: 2 }}>
            View Analytics
          </Button>
        </PermissionWrapper>

        <PermissionWrapper module="users">
          <Button variant="outlined" sx={{ mr: 2 }}>
            Manage Users
          </Button>
        </PermissionWrapper>

        <PermissionWrapper module="audit">
          <Button variant="outlined">
            Audit Logs
          </Button>
        </PermissionWrapper>
      </Box>

      {/* Complex Permission Logic */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          4. Complex Permission Logic
        </Typography>

        {/* Require both permission AND role */}
        <PermissionWrapper
          permission="export_data"
          role={['Marketing', 'Admin']}
          requireAll={true}
        >
          <Button variant="contained" startIcon={<Download />} sx={{ mr: 2 }}>
            Export Data (Marketing/Admin + Permission)
          </Button>
        </PermissionWrapper>

        {/* Either permission OR role (default behavior) */}
        <PermissionWrapper
          permission="view_analytics"
          role="Admin"
        >
          <Button variant="outlined">
            View Reports (Analytics Permission OR Admin)
          </Button>
        </PermissionWrapper>
      </Box>

      {/* Hook-Based Permission Checks */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          5. Hook-Based Permission Checks
        </Typography>

        <Box sx={{ mb: 2 }}>
          <Typography variant="body2">
            Can create companies: {permissions.companies.canCreate() ? '✅' : '❌'}
          </Typography>
          <Typography variant="body2">
            Can edit companies: {permissions.companies.canEdit() ? '✅' : '❌'}
          </Typography>
          <Typography variant="body2">
            Can delete companies: {permissions.companies.canDelete() ? '✅' : '❌'}
          </Typography>
        </Box>

        <Box sx={{ mb: 2 }}>
          <Typography variant="body2">
            Is Admin: {permissions.isAdmin() ? '✅' : '❌'}
          </Typography>
          <Typography variant="body2">
            Is Sales: {permissions.isSales() ? '✅' : '❌'}
          </Typography>
          <Typography variant="body2">
            Can view sensitive data: {permissions.canViewSensitiveData() ? '✅' : '❌'}
          </Typography>
        </Box>

        {/* Conditional rendering based on permissions */}
        {permissions.companies.canCreate() && (
          <Button variant="contained" startIcon={<Add />}>
            Create New Company (Hook Check)
          </Button>
        )}
      </Box>

      {/* Entity-Specific CRUD Operations */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          6. Entity-Specific CRUD Operations
        </Typography>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
          {permissions.opportunities.canView() && (
            <Chip label="View Opportunities" color="default" />
          )}
          {permissions.opportunities.canCreate() && (
            <Chip label="Create Opportunities" color="success" />
          )}
          {permissions.opportunities.canEdit() && (
            <Chip label="Edit Opportunities" color="warning" />
          )}
          {permissions.opportunities.canDelete() && (
            <Chip label="Delete Opportunities" color="error" />
          )}
        </Box>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {permissions.tasks.canView() && (
            <Chip label="View Tasks" color="default" />
          )}
          {permissions.tasks.canCreate() && (
            <Chip label="Create Tasks" color="success" />
          )}
          {permissions.tasks.canEditOwn() && (
            <Chip label="Edit Own Tasks" color="info" />
          )}
          {permissions.tasks.canEditAll() && (
            <Chip label="Edit All Tasks" color="warning" />
          )}
        </Box>
      </Box>

      {/* Fallback Content */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          7. Fallback Content
        </Typography>

        <PermissionWrapper
          permission="manage_users"
          fallback={
            <Typography color="text.secondary" variant="body2">
              You don't have permission to manage users.
            </Typography>
          }
        >
          <Button variant="contained">Manage Users</Button>
        </PermissionWrapper>
      </Box>
    </Box>
  );
};

export default PermissionExamples;