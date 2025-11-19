import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  TextField,
  MenuItem,
  CircularProgress,
  Alert,
  Autocomplete,
  Chip,
  GridLegacy as Grid,
  FormControl,
  InputLabel,
  Select,
} from '@mui/material';
import { Cancel, Save } from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { addDays } from 'date-fns';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Company, Contact, User, Ticket } from '../types';
import ApiService from '../services/api';

// Priority options with color coding
const priorityOptions = [
  { value: 'low', label: 'Low', color: 'default' as const },
  { value: 'medium', label: 'Medium', color: 'info' as const },
  { value: 'high', label: 'High', color: 'warning' as const },
  { value: 'urgent', label: 'Urgent', color: 'error' as const },
];

// Category options with descriptions
const categoryOptions = [
  { value: 'technical', label: 'Technical Support', description: 'Hardware, software, technical issues' },
  { value: 'billing', label: 'Billing/Finance', description: 'Invoices, payments, pricing' },
  { value: 'zone_config', label: 'Zone Configuration', description: 'Music zones, playlists, settings' },
  { value: 'account', label: 'Account Management', description: 'Account changes, upgrades, renewals' },
  { value: 'feature_request', label: 'Feature Request', description: 'New features, enhancements' },
  { value: 'general', label: 'General Inquiry', description: 'Questions, information requests' },
];

const TicketForm: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEditMode = Boolean(id);

  // Form state
  const [company, setCompany] = useState('');
  const [contact, setContact] = useState<string | null>(null);
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'urgent'>('medium');
  const [category, setCategory] = useState<'technical' | 'billing' | 'zone_config' | 'account' | 'feature_request' | 'general'>('general');
  const [assignedTo, setAssignedTo] = useState<string | null>(null);
  const [dueDate, setDueDate] = useState<Date | null>(addDays(new Date(), 3));
  const [tags, setTags] = useState('');

  // Data state
  const [companies, setCompanies] = useState<Company[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);

  // UI state
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(isEditMode);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // Load companies
  useEffect(() => {
    loadCompanies();
  }, []);

  // Load users
  useEffect(() => {
    loadUsers();
  }, []);

  // Load contacts when company changes
  useEffect(() => {
    if (company) {
      loadContacts(company);
    } else {
      setContacts([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [company]);

  // Load existing ticket in edit mode
  useEffect(() => {
    if (isEditMode && id) {
      loadTicket();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isEditMode]);

  const loadCompanies = async () => {
    try {
      const response = await ApiService.getCompanies();
      setCompanies(response.results);
    } catch (err: any) {
      console.error('Failed to load companies:', err);
      setError('Failed to load companies');
    }
  };

  const loadUsers = async () => {
    try {
      const response = await ApiService.getUsers();
      setUsers(response.results);
    } catch (err: any) {
      console.error('Failed to load users:', err);
      setError('Failed to load users');
    }
  };

  const loadContacts = async (companyId: string) => {
    try {
      const response = await ApiService.getContacts({ company: companyId });
      setContacts(response.results);
    } catch (err: any) {
      console.error('Failed to load contacts:', err);
    }
  };

  const loadTicket = async () => {
    try {
      setInitialLoading(true);
      const ticket: Ticket = await ApiService.getTicket(id!);

      // Set form values
      setCompany(ticket.company);
      setContact(ticket.contact);
      setSubject(ticket.subject);
      setDescription(ticket.description);
      setPriority(ticket.priority);
      setCategory(ticket.category);
      setAssignedTo(ticket.assigned_to);
      setDueDate(ticket.due_date ? new Date(ticket.due_date) : null);
      setTags(ticket.tags || '');

      // Set selected company for autocomplete
      const companyObj = companies.find(c => c.id === ticket.company);
      if (companyObj) {
        setSelectedCompany(companyObj);
      }
    } catch (err: any) {
      console.error('Failed to load ticket:', err);
      setError(`Failed to load ticket: ${err.response?.data?.detail || err.message}`);
      // Navigate back after showing error
      setTimeout(() => navigate('/tickets'), 3000);
    } finally {
      setInitialLoading(false);
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!company.trim()) {
      errors.company = 'Company is required';
    }

    if (!subject.trim()) {
      errors.subject = 'Subject is required';
    } else if (subject.length > 200) {
      errors.subject = 'Subject must be 200 characters or less';
    }

    if (!description.trim()) {
      errors.description = 'Description is required';
    }

    if (!priority) {
      errors.priority = 'Priority is required';
    }

    if (!category) {
      errors.category = 'Category is required';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) {
      return;
    }

    try {
      setLoading(true);
      setError('');

      // Prepare data for submission
      const submitData = {
        company,
        contact: contact || null,
        subject,
        description,
        priority,
        category,
        assigned_to: assignedTo || null,
        due_date: dueDate ? dueDate.toISOString() : null,
        tags,
      };

      if (isEditMode && id) {
        // Update existing ticket
        await ApiService.updateTicket(id, submitData);
        setSuccessMessage('Ticket updated successfully');
        setTimeout(() => navigate(`/tickets/${id}`), 1500);
      } else {
        // Create new ticket
        const response = await ApiService.createTicket(submitData);
        setSuccessMessage('Ticket created successfully');
        setTimeout(() => navigate(`/tickets/${response.id}`), 1500);
      }
    } catch (err: any) {
      console.error('Failed to save ticket:', err);
      setError(err.response?.data?.detail || 'Failed to save ticket');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    navigate(-1);
  };

  const handleCompanyChange = (_: any, value: Company | null) => {
    setSelectedCompany(value);
    setCompany(value?.id || '');
    setContact(null); // Reset contact when company changes
  };

  const getPriorityChip = (value: string) => {
    const option = priorityOptions.find(opt => opt.value === value);
    if (!option) return null;
    return <Chip label={option.label} color={option.color} size="small" />;
  };

  // Show loading spinner while loading existing ticket
  if (initialLoading) {
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
            {isEditMode ? `Edit Ticket ${id ? `#${id}` : ''}` : 'Create New Ticket'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {isEditMode ? 'Update ticket details' : 'Create a support ticket for a customer'}
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Button
            variant="outlined"
            startIcon={<Cancel />}
            onClick={handleCancel}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={16} /> : <Save />}
            onClick={handleSubmit}
            disabled={loading}
            sx={{
              bgcolor: '#FFA500',
              '&:hover': { bgcolor: '#FF8C00' },
            }}
          >
            {isEditMode ? 'Update Ticket' : 'Create Ticket'}
          </Button>
        </Box>
      </Box>

      {/* Success Message */}
      {successMessage && (
        <Alert severity="success" onClose={() => setSuccessMessage('')} sx={{ mb: 3 }}>
          {successMessage}
        </Alert>
      )}

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError('')} sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Form */}
      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          {/* Company - Required */}
          <Grid item xs={12}>
            <Autocomplete
              options={companies}
              value={selectedCompany}
              onChange={handleCompanyChange}
              getOptionLabel={(option) => `${option.name}${option.country ? ` (${option.country})` : ''}`}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Company *"
                  required
                  error={Boolean(validationErrors.company)}
                  helperText={validationErrors.company}
                />
              )}
              disabled={loading}
            />
          </Grid>

          {/* Contact - Optional */}
          <Grid item xs={12}>
            <FormControl fullWidth disabled={!company || loading}>
              <InputLabel>Contact</InputLabel>
              <Select
                value={contact || ''}
                onChange={(e) => setContact(e.target.value || null)}
                label="Contact"
              >
                <MenuItem value="">
                  <em>None</em>
                </MenuItem>
                {contacts.map((contactOption) => (
                  <MenuItem key={contactOption.id} value={contactOption.id}>
                    {contactOption.name} ({contactOption.email})
                  </MenuItem>
                ))}
              </Select>
              {!company && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, ml: 1.5 }}>
                  Select a company first
                </Typography>
              )}
            </FormControl>
          </Grid>

          {/* Subject - Required */}
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Subject *"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              error={Boolean(validationErrors.subject)}
              helperText={validationErrors.subject || `${subject.length}/200 characters`}
              required
              disabled={loading}
              inputProps={{ maxLength: 200 }}
            />
          </Grid>

          {/* Description - Required */}
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Description *"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              error={Boolean(validationErrors.description)}
              helperText={validationErrors.description}
              required
              multiline
              rows={6}
              disabled={loading}
            />
          </Grid>

          {/* Priority - Required */}
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth required>
              <InputLabel>Priority *</InputLabel>
              <Select
                value={priority}
                onChange={(e) => setPriority(e.target.value as typeof priority)}
                error={Boolean(validationErrors.priority)}
                label="Priority *"
                disabled={loading}
                renderValue={(value) => (
                  <Box display="flex" alignItems="center">
                    {getPriorityChip(value as string)}
                  </Box>
                )}
              >
                {priorityOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    <Chip label={option.label} color={option.color} size="small" />
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Category - Required */}
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth required>
              <InputLabel>Category *</InputLabel>
              <Select
                value={category}
                onChange={(e) => setCategory(e.target.value as typeof category)}
                error={Boolean(validationErrors.category)}
                label="Category *"
                disabled={loading}
              >
                {categoryOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    <Box>
                      <Typography variant="body1">{option.label}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {option.description}
                      </Typography>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Assigned To - Optional */}
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Assigned To</InputLabel>
              <Select
                value={assignedTo || ''}
                onChange={(e) => setAssignedTo(e.target.value || null)}
                label="Assigned To"
                disabled={loading}
              >
                <MenuItem value="">
                  <em>Unassigned</em>
                </MenuItem>
                {users.map((user) => (
                  <MenuItem key={user.id} value={user.id}>
                    {user.first_name} {user.last_name} ({user.role})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Due Date - Optional */}
          <Grid item xs={12} sm={6}>
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <DateTimePicker
                label="Due Date"
                value={dueDate}
                onChange={(date) => setDueDate(date)}
                disabled={loading}
                slotProps={{
                  textField: {
                    fullWidth: true,
                  },
                }}
              />
            </LocalizationProvider>
          </Grid>

          {/* Tags - Optional */}
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Tags"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              helperText="Separate tags with commas"
              disabled={loading}
              placeholder="urgent, customer-request, hardware"
            />
          </Grid>

          {/* Form Actions */}
          <Grid item xs={12}>
            <Box display="flex" justifyContent="flex-end" gap={2} mt={2}>
              <Button
                variant="outlined"
                onClick={handleCancel}
                disabled={loading}
                size="large"
              >
                Cancel
              </Button>
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={loading}
                size="large"
                sx={{
                  bgcolor: '#FFA500',
                  '&:hover': { bgcolor: '#FF8C00' },
                }}
              >
                {loading && <CircularProgress size={20} sx={{ mr: 1 }} />}
                {isEditMode ? 'Update Ticket' : 'Create Ticket'}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default TicketForm;
