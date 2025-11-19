import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Alert,
  CircularProgress,
  Box,
  Typography,
  Chip,
} from '@mui/material';
import {
  PlaylistAdd,
  Group,
} from '@mui/icons-material';
import { CustomerSegment, EmailSequence } from '../types';
import ApiService from '../services/api';

interface EnrollSegmentDialogProps {
  open: boolean;
  onClose: () => void;
  segment: CustomerSegment;
  onSuccess: () => void;
}

const EnrollSegmentDialog: React.FC<EnrollSegmentDialogProps> = ({
  open,
  onClose,
  segment,
  onSuccess,
}) => {
  const [sequences, setSequences] = useState<EmailSequence[]>([]);
  const [selectedSequenceId, setSelectedSequenceId] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingSequences, setLoadingSequences] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [enrollmentResult, setEnrollmentResult] = useState<{
    enrolled_count: number;
    skipped_count: number;
    total_members: number;
  } | null>(null);

  // Load sequences on mount
  useEffect(() => {
    if (open) {
      loadSequences();
    }
  }, [open]);

  const loadSequences = async () => {
    try {
      setLoadingSequences(true);
      setError('');
      const response = await ApiService.getEmailSequences({ status: 'active' });
      setSequences(response.results || []);
    } catch (err: any) {
      console.error('Failed to load sequences:', err);
      setError(`Failed to load sequences: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoadingSequences(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedSequenceId) {
      setError('Please select an email sequence');
      return;
    }

    try {
      setLoading(true);
      setError('');
      const response = await ApiService.enrollSegmentInSequence(segment.id, {
        sequence_id: selectedSequenceId,
        notes,
      });

      setEnrollmentResult({
        enrolled_count: response.enrolled_count,
        skipped_count: response.skipped_count,
        total_members: response.total_members,
      });
      setSuccess(true);

      // Auto-close after 2 seconds
      setTimeout(() => {
        onSuccess();
        handleClose();
      }, 2000);
    } catch (err: any) {
      console.error('Failed to enroll segment:', err);
      setError(`Failed to enroll segment: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setSelectedSequenceId('');
      setNotes('');
      setError('');
      setSuccess(false);
      setEnrollmentResult(null);
      onClose();
    }
  };

  const selectedSequence = sequences.find(s => s.id === selectedSequenceId);

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <PlaylistAdd sx={{ color: '#FFA500' }} />
          <span>Enroll Segment in Email Sequence</span>
        </Box>
      </DialogTitle>
      <DialogContent>
        {success ? (
          <Alert severity="success" sx={{ mb: 2 }}>
            <Typography variant="body2" fontWeight={500} gutterBottom>
              Successfully enrolled segment members!
            </Typography>
            {enrollmentResult && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" display="block">
                  Enrolled: {enrollmentResult.enrolled_count} contacts
                </Typography>
                <Typography variant="caption" display="block">
                  Skipped: {enrollmentResult.skipped_count} contacts (already enrolled)
                </Typography>
                <Typography variant="caption" display="block">
                  Total members: {enrollmentResult.total_members}
                </Typography>
              </Box>
            )}
          </Alert>
        ) : (
          <>
            {error && (
              <Alert severity="error" onClose={() => setError('')} sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            {/* Segment Info */}
            <Box sx={{ mb: 3, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Segment
              </Typography>
              <Typography variant="body1" fontWeight={500} gutterBottom>
                {segment.name}
              </Typography>
              <Box display="flex" alignItems="center" gap={1}>
                <Group fontSize="small" color="action" />
                <Typography variant="body2" color="text.secondary">
                  {segment.member_count} member{segment.member_count !== 1 ? 's' : ''}
                </Typography>
                <Chip
                  label={segment.segment_type === 'dynamic' ? 'Dynamic' : 'Static'}
                  size="small"
                  sx={{ ml: 1 }}
                />
              </Box>
            </Box>

            {/* Sequence Selector */}
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel id="sequence-select-label">Email Sequence *</InputLabel>
              <Select
                labelId="sequence-select-label"
                value={selectedSequenceId}
                onChange={(e) => setSelectedSequenceId(e.target.value)}
                label="Email Sequence *"
                disabled={loadingSequences || loading}
              >
                {loadingSequences ? (
                  <MenuItem disabled>
                    <CircularProgress size={16} sx={{ mr: 1 }} />
                    Loading sequences...
                  </MenuItem>
                ) : sequences.length === 0 ? (
                  <MenuItem disabled>No active sequences available</MenuItem>
                ) : (
                  sequences.map((sequence) => (
                    <MenuItem key={sequence.id} value={sequence.id}>
                      {sequence.name} ({sequence.total_steps} steps)
                    </MenuItem>
                  ))
                )}
              </Select>
            </FormControl>

            {/* Sequence Details */}
            {selectedSequence && (
              <Box sx={{ mb: 2, p: 2, bgcolor: '#FFF8E1', borderRadius: 1 }}>
                <Typography variant="caption" color="text.secondary" display="block">
                  Sequence Details
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  {selectedSequence.description || 'No description'}
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                  {selectedSequence.total_steps} email{selectedSequence.total_steps !== 1 ? 's' : ''} will be sent
                </Typography>
              </Box>
            )}

            {/* Notes */}
            <TextField
              fullWidth
              label="Notes (Optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              rows={3}
              placeholder="Add any notes about this enrollment..."
              disabled={loading}
            />

            {/* Warning */}
            <Alert severity="info" sx={{ mt: 2 }}>
              Members will be enrolled immediately. Contacts already enrolled in this sequence will be skipped.
            </Alert>
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose} disabled={loading}>
          {success ? 'Close' : 'Cancel'}
        </Button>
        {!success && (
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={loading || !selectedSequenceId || loadingSequences}
            startIcon={loading ? <CircularProgress size={16} /> : <PlaylistAdd />}
            sx={{
              bgcolor: '#FFA500',
              '&:hover': { bgcolor: '#FF8C00' },
            }}
          >
            Enroll {segment.member_count} Member{segment.member_count !== 1 ? 's' : ''}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default EnrollSegmentDialog;
