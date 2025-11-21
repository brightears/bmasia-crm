import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Alert,
  CircularProgress,
  InputAdornment,
  IconButton,
} from '@mui/material';
import {
  Close as CloseIcon,
  Add as AddIcon,
  Flag as FlagIcon,
  Person as PersonIcon,
  Business as BusinessIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV2';
import {
  Task,
  User,
  Company,
} from '../types';
import ApiService from '../services/api';

interface QuickTaskCreateProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: (task: Task) => void;
}

const QuickTaskCreate: React.FC<QuickTaskCreateProps> = ({
  open,
  onClose,
  onSuccess,
}) => {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    priority: 'Medium' as Task['priority'],
    due_date: null as Date | null,
    company: '',
    assigned_to: '',
  });

  const [users, setUsers] = useState<User[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dataLoading, setDataLoading] = useState(false);

  useEffect(() => {
    if (open) {
      loadSupportingData();
    }
  }, [open]);

  const loadSupportingData = async () => {
    setDataLoading(true);
    try {
      const [usersRes, companiesRes] = await Promise.all([
        ApiService.getUsers(),
        ApiService.getCompanies({ page_size: 1000 }),
      ]);

      setUsers(usersRes.results);
      setCompanies(companiesRes.results);
    } catch (error: any) {
      console.error('Error fetching supporting data:', error);
      setError('Failed to load form data');
    } finally {
      setDataLoading(false);
    }
  };

  const handleChange = (field: string, value: any) => {
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
      if (!formData.title.trim()) {
        throw new Error('Title is required');
      }

      if (!formData.company) {
        throw new Error('Company is required');
      }

      // Prepare data for API
      const taskData = {
        title: formData.title.trim(),
        description: formData.description.trim() || '',
        priority: formData.priority,
        status: 'To Do' as Task['status'],
        due_date: formData.due_date?.toISOString(),
        company: formData.company,
        assigned_to: formData.assigned_to || undefined,
      };

      const newTask = await ApiService.createTask(taskData);

      onSuccess?.(newTask);
      onClose();

      // Reset form
      setFormData({
        title: '',
        description: '',
        priority: 'Medium',
        due_date: null,
        company: '',
        assigned_to: '',
      });
    } catch (error: any) {
      console.error('Error creating task:', error);
      setError(error.message || 'Failed to create task');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  const priorityOptions = [
    { value: 'Low', label: 'Low', color: '#4caf50' },
    { value: 'Medium', label: 'Medium', color: '#2196f3' },
    { value: 'High', label: 'High', color: '#ff9800' },
    { value: 'Urgent', label: 'Urgent', color: '#f44336' },
  ];

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Dialog
        open={open}
        onClose={handleClose}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          component: 'form',
          onSubmit: handleSubmit,
        }}
      >
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">
              Quick Create Task
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

          {dataLoading && (
            <Box display="flex" justifyContent="center" py={2}>
              <CircularProgress />
            </Box>
          )}

          {!dataLoading && (
            <Box display="flex" flexDirection="column" gap={2}>
              <TextField
                required
                fullWidth
                label="Task Title"
                value={formData.title}
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

              <TextField
                fullWidth
                multiline
                rows={2}
                label="Description"
                value={formData.description}
                onChange={(e) => handleChange('description', e.target.value)}
                disabled={loading}
              />

              <FormControl fullWidth required>
                <InputLabel>Company</InputLabel>
                <Select
                  value={formData.company}
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

              <Box display="flex" gap={2}>
                <FormControl fullWidth>
                  <InputLabel>Priority</InputLabel>
                  <Select
                    value={formData.priority}
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

                <FormControl fullWidth>
                  <InputLabel>Assignee</InputLabel>
                  <Select
                    value={formData.assigned_to}
                    label="Assignee"
                    onChange={(e) => handleChange('assigned_to', e.target.value)}
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
              </Box>

              <DatePicker
                label="Due Date (Optional)"
                value={formData.due_date}
                onChange={(date) => handleChange('due_date', date)}
                disabled={loading}
                slotProps={{
                  textField: {
                    fullWidth: true,
                  },
                }}
              />
            </Box>
          )}
        </DialogContent>

        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={loading || !formData.title.trim() || !formData.company || dataLoading}
            startIcon={loading ? <CircularProgress size={16} /> : <AddIcon />}
          >
            {loading ? 'Creating...' : 'Create Task'}
          </Button>
        </DialogActions>
      </Dialog>
    </LocalizationProvider>
  );
};

export default QuickTaskCreate;