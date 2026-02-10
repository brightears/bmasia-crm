import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  GridLegacy as Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  CircularProgress,
  Alert,
  InputAdornment,
  IconButton,
} from '@mui/material';
import {
  Close as CloseIcon,
  Person as PersonIcon,
  Business as BusinessIcon,
  Schedule as ScheduleIcon,
  Flag as FlagIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import {
  Task,
  User,
  Company,
  Opportunity,
  Contract,
  Contact,
} from '../types';

interface TaskFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (task: Partial<Task>) => void;
  task?: Task | null;
  mode: 'create' | 'edit';
  users: User[];
  companies: Company[];
  opportunities: Opportunity[];
  contracts: Contract[];
  contacts: Contact[];
  initialTaskType?: string | null;
}

const priorityOptions = [
  { value: 'Low', label: 'Low', color: '#4caf50' },
  { value: 'Medium', label: 'Medium', color: '#2196f3' },
  { value: 'High', label: 'High', color: '#ff9800' },
  { value: 'Urgent', label: 'Urgent', color: '#f44336' },
];

const statusOptions = [
  { value: 'To Do', label: 'To Do' },
  { value: 'In Progress', label: 'In Progress' },
  { value: 'Done', label: 'Done' },
  { value: 'On Hold', label: 'On Hold' },
  { value: 'Cancelled', label: 'Cancelled' },
];

const taskTypeOptions = [
  { value: 'Call', label: 'Call' },
  { value: 'Email', label: 'Email' },
  { value: 'Follow-up', label: 'Follow-up' },
  { value: 'Meeting', label: 'Meeting' },
  { value: 'Other', label: 'Other' },
];

const TaskForm: React.FC<TaskFormProps> = ({
  open,
  onClose,
  onSave,
  task,
  mode,
  users,
  companies,
  opportunities,
  contracts,
  contacts,
  initialTaskType,
}) => {
  const [formData, setFormData] = useState<Partial<Task>>({
    title: '',
    description: '',
    priority: 'Medium',
    status: 'To Do',
    task_type: 'Other',
    due_date: undefined,
    company: '',
    assigned_to: undefined,
    related_opportunity: undefined,
    related_contract: undefined,
    related_contact: undefined,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (task) {
      setFormData({
        ...task,
        due_date: task.due_date || undefined,
      });
    } else {
      // Use initialTaskType if provided, otherwise default to 'Other'
      const taskType = (initialTaskType || 'Other') as Task['task_type'];
      setFormData({
        title: '',
        description: '',
        priority: 'Medium',
        status: 'To Do',
        task_type: taskType,
        due_date: undefined,
        company: '',
        assigned_to: undefined,
        related_opportunity: undefined,
        related_contract: undefined,
        related_contact: undefined,
      });
    }
    setError(null);
  }, [task, open, initialTaskType]);

  const handleChange = (field: keyof Task, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Validation
      if (!formData.title?.trim()) {
        throw new Error('Title is required');
      }

      if (!formData.company) {
        throw new Error('Company is required');
      }

      // Prepare data for API
      const taskData = {
        ...formData,
        title: formData.title?.trim(),
        description: formData.description?.trim() || '',
        due_date: formData.due_date || undefined,
        related_opportunity: formData.related_opportunity || undefined,
        related_contract: formData.related_contract || undefined,
        related_contact: formData.related_contact || undefined,
      };

      await onSave(taskData);
      onClose();
    } catch (error: any) {
      console.error('Error saving task:', error);
      setError(error.message || 'Failed to save task');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  const getCompanyName = (companyId: string) => {
    return companies.find(c => c.id === companyId)?.name || '';
  };

  const getUserName = (userId: string) => {
    const user = users.find(u => u.id === userId);
    return user ? `${user.first_name} ${user.last_name}` : '';
  };

  const getRelatedOpportunities = () => {
    if (!formData.company) return [];
    return opportunities.filter(o => o.company === formData.company);
  };

  const getRelatedContracts = () => {
    if (!formData.company) return [];
    return contracts.filter(c => c.company === formData.company);
  };

  const getRelatedContacts = () => {
    if (!formData.company) return [];
    return contacts.filter(c => c.company === formData.company);
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Dialog
        open={open}
        onClose={handleClose}
        maxWidth="md"
        fullWidth
        PaperProps={{
          component: 'form',
          onSubmit: handleSubmit,
        }}
      >
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">
              {mode === 'create' ? 'Create New Task' : 'Edit Task'}
            </Typography>
            <IconButton onClick={handleClose} disabled={loading}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent dividers>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Grid container spacing={3}>
            {/* Basic Information */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Basic Information
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <TextField
                required
                fullWidth
                label="Task Title"
                value={formData.title || ''}
                onChange={(e) => handleChange('title', e.target.value)}
                disabled={loading}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <FlagIcon />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Description"
                value={formData.description || ''}
                onChange={(e) => handleChange('description', e.target.value)}
                disabled={loading}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth required>
                <InputLabel>Company</InputLabel>
                <Select
                  value={formData.company || ''}
                  label="Company *"
                  onChange={(e) => handleChange('company', e.target.value)}
                  disabled={loading}
                  startAdornment={
                    <InputAdornment position="start">
                      <BusinessIcon />
                    </InputAdornment>
                  }
                >
                  {companies.map((company) => (
                    <MenuItem key={company.id} value={company.id}>
                      {company.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Assignee</InputLabel>
                <Select
                  value={formData.assigned_to || ''}
                  label="Assignee"
                  onChange={(e) => handleChange('assigned_to', e.target.value || undefined)}
                  disabled={loading}
                  startAdornment={
                    <InputAdornment position="start">
                      <PersonIcon />
                    </InputAdornment>
                  }
                >
                  <MenuItem value="">
                    <em>Unassigned</em>
                  </MenuItem>
                  {users.map((user) => (
                    <MenuItem key={user.id} value={user.id}>
                      {user.first_name} {user.last_name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Priority</InputLabel>
                <Select
                  value={formData.priority || 'Medium'}
                  label="Priority"
                  onChange={(e) => handleChange('priority', e.target.value)}
                  disabled={loading}
                >
                  {priorityOptions.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      <Box display="flex" alignItems="center" gap={1}>
                        <Box
                          width={12}
                          height={12}
                          borderRadius="50%"
                          bgcolor={option.color}
                        />
                        {option.label}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select
                  value={formData.status || 'To Do'}
                  label="Status"
                  onChange={(e) => handleChange('status', e.target.value)}
                  disabled={loading}
                >
                  {statusOptions.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={4}>
              <DatePicker
                label="Due Date"
                value={formData.due_date ? new Date(formData.due_date) : null}
                onChange={(date) => handleChange('due_date', date?.toISOString())}
                disabled={loading}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    InputProps: {
                      startAdornment: (
                        <InputAdornment position="start">
                          <ScheduleIcon />
                        </InputAdornment>
                      ),
                    },
                  },
                }}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Task Type</InputLabel>
                <Select
                  value={formData.task_type || 'Other'}
                  label="Task Type"
                  onChange={(e) => handleChange('task_type', e.target.value)}
                  disabled={loading}
                >
                  {taskTypeOptions.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Related Opportunity</InputLabel>
                <Select
                  value={formData.related_opportunity || ''}
                  label="Related Opportunity"
                  onChange={(e) => handleChange('related_opportunity', e.target.value || undefined)}
                  disabled={loading || !formData.company}
                >
                  <MenuItem value="">
                    <em>None</em>
                  </MenuItem>
                  {getRelatedOpportunities().map((opportunity) => (
                    <MenuItem key={opportunity.id} value={opportunity.id}>
                      {opportunity.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Related Contract</InputLabel>
                <Select
                  value={formData.related_contract || ''}
                  label="Related Contract"
                  onChange={(e) => handleChange('related_contract', e.target.value || undefined)}
                  disabled={loading || !formData.company}
                >
                  <MenuItem value="">
                    <em>None</em>
                  </MenuItem>
                  {getRelatedContracts().map((contract) => (
                    <MenuItem key={contract.id} value={contract.id}>
                      {contract.contract_number}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Related Contact</InputLabel>
                <Select
                  value={formData.related_contact || ''}
                  label="Related Contact"
                  onChange={(e) => handleChange('related_contact', e.target.value || undefined)}
                  disabled={loading || !formData.company}
                >
                  <MenuItem value="">
                    <em>None</em>
                  </MenuItem>
                  {getRelatedContacts().map((contact) => (
                    <MenuItem key={contact.id} value={contact.id}>
                      {contact.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={loading || !formData.title?.trim() || !formData.company}
            startIcon={loading ? <CircularProgress size={16} /> : null}
          >
            {loading ? 'Saving...' : mode === 'create' ? 'Create Task' : 'Update Task'}
          </Button>
        </DialogActions>
      </Dialog>
    </LocalizationProvider>
  );
};

export default TaskForm;