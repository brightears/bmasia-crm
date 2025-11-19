import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  CircularProgress,
  Alert,
  RadioGroup,
  FormControlLabel,
  Radio,
  FormLabel,
  FormControl,
  Autocomplete,
  Typography,
} from '@mui/material';
import { Contact, SequenceEnrollment } from '../types';
import ApiService from '../services/api';

interface EnrollContactDialogProps {
  open: boolean;
  onClose: () => void;
  sequenceId: string;
  onSuccess: () => void;
}

const EnrollContactDialog: React.FC<EnrollContactDialogProps> = ({
  open,
  onClose,
  sequenceId,
  onSuccess,
}) => {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [notes, setNotes] = useState('');
  const [status, setStatus] = useState<'active' | 'paused'>('active');
  const [loading, setLoading] = useState(false);
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch contacts for autocomplete
  useEffect(() => {
    if (open) {
      fetchContacts();
    }
  }, [open, searchQuery]);

  const fetchContacts = async () => {
    try {
      setLoadingContacts(true);
      const params: any = { is_active: true, page_size: 50 };
      if (searchQuery) {
        params.search = searchQuery;
      }
      const response = await ApiService.getContacts(params);
      setContacts(response.results || []);
    } catch (error) {
      console.error('Failed to fetch contacts:', error);
    } finally {
      setLoadingContacts(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedContact) {
      setError('Please select a contact to enroll');
      return;
    }

    try {
      setLoading(true);
      setError('');

      const enrollmentData: Partial<SequenceEnrollment> = {
        sequence: sequenceId,
        contact: selectedContact.id,
        status: status,
        notes: notes,
      };

      await ApiService.createSequenceEnrollment(enrollmentData);
      setSuccess('Contact enrolled successfully');

      // Reset form
      setSelectedContact(null);
      setNotes('');
      setStatus('active');

      // Call success callback after a brief delay to show success message
      setTimeout(() => {
        onSuccess();
        handleClose();
      }, 1000);
    } catch (err: any) {
      console.error('Failed to enroll contact:', err);
      const errorMessage = err.response?.data?.detail
        || err.response?.data?.non_field_errors?.[0]
        || err.response?.data?.error
        || 'Failed to enroll contact';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setSelectedContact(null);
      setNotes('');
      setStatus('active');
      setError('');
      setSuccess('');
      setSearchQuery('');
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Enroll Contact in Sequence</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        {success && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {success}
          </Alert>
        )}

        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>How enrollment works:</strong>
          </Typography>
          <Typography variant="body2" component="div">
            <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
              <li>Contact will be enrolled starting from Step 1</li>
              <li>Emails will be sent according to step delays</li>
              <li>You can pause or unenroll at any time</li>
            </ul>
          </Typography>
        </Alert>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
          {/* Contact Autocomplete */}
          <Autocomplete
            options={contacts}
            value={selectedContact}
            onChange={(event, newValue) => setSelectedContact(newValue)}
            onInputChange={(event, newInputValue) => setSearchQuery(newInputValue)}
            getOptionLabel={(option) => `${option.name} (${option.email})`}
            loading={loadingContacts}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Contact"
                required
                placeholder="Search by name or email"
                InputProps={{
                  ...params.InputProps,
                  endAdornment: (
                    <>
                      {loadingContacts ? <CircularProgress color="inherit" size={20} /> : null}
                      {params.InputProps.endAdornment}
                    </>
                  ),
                }}
              />
            )}
            renderOption={(props, option) => (
              <li {...props} key={option.id}>
                <Box>
                  <Typography variant="body2" fontWeight="500">
                    {option.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {option.email}
                    {option.company_name && ` - ${option.company_name}`}
                  </Typography>
                </Box>
              </li>
            )}
          />

          {/* Notes TextField */}
          <TextField
            label="Notes"
            multiline
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes about this enrollment..."
            fullWidth
          />

          {/* Status Radio Group */}
          <FormControl component="fieldset">
            <FormLabel component="legend">Enrollment Status</FormLabel>
            <RadioGroup
              row
              value={status}
              onChange={(e) => setStatus(e.target.value as 'active' | 'paused')}
            >
              <FormControlLabel
                value="active"
                control={<Radio />}
                label="Active (Start sending emails)"
              />
              <FormControlLabel
                value="paused"
                control={<Radio />}
                label="Paused (Enroll but don't send)"
              />
            </RadioGroup>
          </FormControl>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading || !selectedContact}
          sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
        >
          {loading ? <CircularProgress size={24} /> : 'Enroll Contact'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EnrollContactDialog;
