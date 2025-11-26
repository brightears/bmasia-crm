import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Alert,
  GridLegacy as Grid,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogContentText,
  Snackbar,
  LinearProgress,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Collapse,
  Tooltip,
  Skeleton,
} from '@mui/material';
import {
  ArrowBack,
  Edit,
  Timeline,
  People,
  Add,
  Delete,
  Pause,
  PlayArrow,
  PersonRemove,
  ExpandMore,
  ExpandLess,
  Error,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { EmailSequence, SequenceStep, SequenceEnrollment, SequenceStepExecution } from '../types';
import ApiService from '../services/api';
import SequenceForm from '../components/SequenceForm';
import SequenceStepForm from '../components/SequenceStepForm';
import EnrollContactDialog from '../components/EnrollContactDialog';

const SequenceDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [sequence, setSequence] = useState<EmailSequence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(false);

  // Steps state
  const [steps, setSteps] = useState<SequenceStep[]>([]);
  const [stepFormOpen, setStepFormOpen] = useState(false);
  const [editingStep, setEditingStep] = useState<SequenceStep | undefined>(undefined);
  const [deleteStepDialogOpen, setDeleteStepDialogOpen] = useState(false);
  const [stepToDelete, setStepToDelete] = useState<string | null>(null);
  const [loadingSteps, setLoadingSteps] = useState(false);

  // Enrollments state
  const [enrollments, setEnrollments] = useState<SequenceEnrollment[]>([]);
  const [enrollDialogOpen, setEnrollDialogOpen] = useState(false);
  const [loadingEnrollments, setLoadingEnrollments] = useState(false);
  const [enrollmentStatusFilter, setEnrollmentStatusFilter] = useState<string>('all');
  const [deleteEnrollmentDialogOpen, setDeleteEnrollmentDialogOpen] = useState(false);
  const [enrollmentToDelete, setEnrollmentToDelete] = useState<string | null>(null);

  // Execution tracking state
  const [expandedEnrollment, setExpandedEnrollment] = useState<string | null>(null);
  const [executionsByEnrollment, setExecutionsByEnrollment] = useState<Record<string, SequenceStepExecution[]>>({});
  const [loadingExecutions, setLoadingExecutions] = useState<Record<string, boolean>>({});

  // Snackbar state
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'info' | 'warning';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const loadSequence = async () => {
    if (!id) return;

    try {
      setLoading(true);
      setError('');
      const data = await ApiService.getEmailSequence(id);
      setSequence(data);
    } catch (err: any) {
      console.error('Load sequence error:', err);
      setError(`Failed to load sequence: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchSteps = async () => {
    if (!id) return;

    try {
      setLoadingSteps(true);
      const response = await ApiService.getSequenceSteps({ sequence: id, ordering: 'step_number' });
      setSteps(response.results || []);
    } catch (error) {
      console.error('Failed to fetch steps:', error);
      setSnackbar({ open: true, message: 'Failed to load steps', severity: 'error' });
    } finally {
      setLoadingSteps(false);
    }
  };

  const fetchEnrollments = async () => {
    if (!id) return;

    try {
      setLoadingEnrollments(true);
      const params: any = { sequence: id, ordering: '-enrolled_at' };

      if (enrollmentStatusFilter && enrollmentStatusFilter !== 'all') {
        params.status = enrollmentStatusFilter;
      }

      const response = await ApiService.getSequenceEnrollments(params);
      setEnrollments(response.results || []);
    } catch (error) {
      console.error('Failed to fetch enrollments:', error);
      setSnackbar({ open: true, message: 'Failed to load enrollments', severity: 'error' });
    } finally {
      setLoadingEnrollments(false);
    }
  };

  const fetchExecutionsForEnrollment = async (enrollmentId: string) => {
    if (executionsByEnrollment[enrollmentId]) {
      // Already fetched, just expand/collapse
      setExpandedEnrollment(expandedEnrollment === enrollmentId ? null : enrollmentId);
      return;
    }

    try {
      setLoadingExecutions({ ...loadingExecutions, [enrollmentId]: true });
      const response = await ApiService.getSequenceStepExecutions({
        enrollment: enrollmentId,
        ordering: 'step__step_number'
      });
      setExecutionsByEnrollment({
        ...executionsByEnrollment,
        [enrollmentId]: response.results
      });
      setExpandedEnrollment(enrollmentId);
    } catch (error) {
      console.error('Failed to fetch executions:', error);
      setSnackbar({
        open: true,
        message: 'Failed to load execution history',
        severity: 'error'
      });
    } finally {
      setLoadingExecutions({ ...loadingExecutions, [enrollmentId]: false });
    }
  };

  useEffect(() => {
    if (id) {
      loadSequence();
      fetchSteps();
      fetchEnrollments();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Refetch enrollments on filter change
  useEffect(() => {
    if (id) {
      fetchEnrollments();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrollmentStatusFilter]);

  const handleBack = () => {
    navigate('/email-automations');
  };

  const handleEdit = () => {
    setFormOpen(true);
  };

  const handleFormClose = () => {
    setFormOpen(false);
  };

  const handleFormSave = () => {
    setFormOpen(false);
    loadSequence();
  };

  const handleAddStep = () => {
    setEditingStep(undefined);
    setStepFormOpen(true);
  };

  const handleEditStep = (step: SequenceStep) => {
    setEditingStep(step);
    setStepFormOpen(true);
  };

  const handleDeleteStep = (stepId: string) => {
    setStepToDelete(stepId);
    setDeleteStepDialogOpen(true);
  };

  const confirmDeleteStep = async () => {
    if (!stepToDelete) return;

    try {
      await ApiService.deleteSequenceStep(stepToDelete);
      setSnackbar({ open: true, message: 'Step deleted successfully', severity: 'success' });
      fetchSteps();
      loadSequence(); // Refresh sequence to update total_steps count
    } catch (error) {
      console.error('Failed to delete step:', error);
      setSnackbar({ open: true, message: 'Failed to delete step', severity: 'error' });
    } finally {
      setDeleteStepDialogOpen(false);
      setStepToDelete(null);
    }
  };

  const handleStepFormSuccess = () => {
    setStepFormOpen(false);
    setEditingStep(undefined);
    fetchSteps();
    loadSequence(); // Refresh sequence to update total_steps count
    setSnackbar({ open: true, message: 'Step saved successfully', severity: 'success' });
  };

  const handleEnrollContact = () => {
    setEnrollDialogOpen(true);
  };

  const handleEnrollSuccess = () => {
    setEnrollDialogOpen(false);
    fetchEnrollments();
    loadSequence(); // Refresh to update active_enrollments count
  };

  const handlePauseEnrollment = async (enrollmentId: string) => {
    try {
      await ApiService.pauseSequenceEnrollment(enrollmentId);
      setSnackbar({ open: true, message: 'Enrollment paused', severity: 'success' });
      fetchEnrollments();
      loadSequence();
    } catch (error) {
      console.error('Failed to pause enrollment:', error);
      setSnackbar({ open: true, message: 'Failed to pause enrollment', severity: 'error' });
    }
  };

  const handleResumeEnrollment = async (enrollmentId: string) => {
    try {
      await ApiService.resumeSequenceEnrollment(enrollmentId);
      setSnackbar({ open: true, message: 'Enrollment resumed', severity: 'success' });
      fetchEnrollments();
      loadSequence();
    } catch (error) {
      console.error('Failed to resume enrollment:', error);
      setSnackbar({ open: true, message: 'Failed to resume enrollment', severity: 'error' });
    }
  };

  const handleUnenroll = (enrollmentId: string) => {
    setEnrollmentToDelete(enrollmentId);
    setDeleteEnrollmentDialogOpen(true);
  };

  const confirmUnenroll = async () => {
    if (!enrollmentToDelete) return;

    try {
      await ApiService.deleteSequenceEnrollment(enrollmentToDelete);
      setSnackbar({ open: true, message: 'Contact unenrolled', severity: 'success' });
      fetchEnrollments();
      loadSequence();
    } catch (error) {
      console.error('Failed to unenroll:', error);
      setSnackbar({ open: true, message: 'Failed to unenroll contact', severity: 'error' });
    } finally {
      setDeleteEnrollmentDialogOpen(false);
      setEnrollmentToDelete(null);
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
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

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <Box>
        <Button startIcon={<ArrowBack />} onClick={handleBack} sx={{ mb: 2 }}>
          Back to Sequences
        </Button>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Skeleton variant="text" width="60%" height={40} />
            <Skeleton variant="text" width="80%" />
            <Skeleton variant="rectangular" height={100} sx={{ mt: 2 }} />
          </CardContent>
        </Card>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
          <CircularProgress />
        </Box>
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button startIcon={<ArrowBack />} onClick={handleBack}>
          Back to Sequences
        </Button>
      </Box>
    );
  }

  if (!sequence) {
    return (
      <Box>
        <Alert severity="warning" sx={{ mb: 2 }}>
          Sequence not found
        </Alert>
        <Button startIcon={<ArrowBack />} onClick={handleBack}>
          Back to Sequences
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Button
            startIcon={<ArrowBack />}
            onClick={handleBack}
            sx={{ mb: 2 }}
          >
            Back to Sequences
          </Button>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="h4" component="h1">
              {sequence.name}
            </Typography>
            <Chip
              label={sequence.status.charAt(0).toUpperCase() + sequence.status.slice(1)}
              size="medium"
              color={getStatusColor(sequence.status)}
            />
          </Box>
        </Box>
        <Button
          variant="contained"
          startIcon={<Edit />}
          onClick={handleEdit}
          sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
        >
          Edit Sequence
        </Button>
      </Box>

      {/* Info Card */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Sequence Information
          </Typography>
          <Divider sx={{ mb: 2 }} />
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Description
              </Typography>
              <Typography variant="body1">
                {sequence.description || 'No description provided'}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Total Steps
              </Typography>
              <Typography variant="h6">
                {sequence.total_steps}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Active Enrollments
              </Typography>
              <Typography variant="h6">
                {sequence.active_enrollments}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Created By
              </Typography>
              <Typography variant="body1">
                {sequence.created_by_name}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Created
              </Typography>
              <Typography variant="body2">
                {formatDate(sequence.created_at)}
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Sequence Steps Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Timeline sx={{ color: '#FFA500' }} />
              <Typography variant="h6">
                Sequence Steps ({steps.length})
              </Typography>
            </Box>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={handleAddStep}
              sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
            >
              Add Step
            </Button>
          </Box>

          {loadingSteps ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : steps.length === 0 ? (
            <Box
              sx={{
                p: 4,
                textAlign: 'center',
                border: '2px dashed #ccc',
                borderRadius: 2,
                backgroundColor: '#f5f5f5',
              }}
            >
              <Timeline sx={{ fontSize: 48, color: '#ccc', mb: 1 }} />
              <Typography variant="body1" color="text.secondary">
                No steps added yet. Click "Add Step" to create your first email step.
              </Typography>
            </Box>
          ) : (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Step #</TableCell>
                    <TableCell>Name</TableCell>
                    <TableCell>Email Template</TableCell>
                    <TableCell>Delay (Days)</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {steps.map((step) => (
                    <TableRow key={step.id}>
                      <TableCell>{step.step_number}</TableCell>
                      <TableCell>{step.name}</TableCell>
                      <TableCell>{step.email_template_name}</TableCell>
                      <TableCell>{step.delay_days}</TableCell>
                      <TableCell>
                        <Chip
                          label={step.is_active ? 'Active' : 'Inactive'}
                          color={step.is_active ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <IconButton onClick={() => handleEditStep(step)} size="small">
                          <Edit />
                        </IconButton>
                        <IconButton onClick={() => handleDeleteStep(step.id)} size="small">
                          <Delete />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Enrollments Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <People sx={{ color: '#FFA500' }} />
              <Typography variant="h6">
                Enrolled Contacts ({enrollments.length})
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel>Status Filter</InputLabel>
                <Select
                  value={enrollmentStatusFilter}
                  onChange={(e) => setEnrollmentStatusFilter(e.target.value)}
                  label="Status Filter"
                >
                  <MenuItem value="all">All Statuses</MenuItem>
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="paused">Paused</MenuItem>
                  <MenuItem value="completed">Completed</MenuItem>
                  <MenuItem value="unsubscribed">Unsubscribed</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={handleEnrollContact}
                sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
              >
                Enroll Contact
              </Button>
            </Box>
          </Box>

          {loadingEnrollments ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : enrollments.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <People sx={{ fontSize: 64, color: '#ccc', mb: 2 }} />
              <Typography variant="body1" color="text.secondary">
                {enrollmentStatusFilter === 'all'
                  ? 'No contacts enrolled yet. Click "Enroll Contact" to get started.'
                  : `No ${enrollmentStatusFilter} enrollments found.`}
              </Typography>
            </Box>
          ) : (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell width={50}></TableCell>
                    <TableCell>Contact</TableCell>
                    <TableCell>Company</TableCell>
                    <TableCell>Progress</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Enrolled</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {enrollments.map((enrollment) => (
                    <React.Fragment key={enrollment.id}>
                      {/* Main enrollment row */}
                      <TableRow
                        sx={{
                          cursor: 'pointer',
                          '&:hover': { backgroundColor: '#f5f5f5' }
                        }}
                      >
                        <TableCell>
                          <Tooltip title="View execution timeline">
                            <IconButton
                              size="small"
                              onClick={() => fetchExecutionsForEnrollment(enrollment.id)}
                            >
                              {expandedEnrollment === enrollment.id ? <ExpandLess /> : <ExpandMore />}
                            </IconButton>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Box>
                            <Typography variant="body2" fontWeight="500">
                              {enrollment.contact_name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {enrollment.contact_email}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell>
                          {enrollment.company_name || '-'}
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={parseFloat(enrollment.progress)}
                              sx={{
                                width: 100,
                                height: 6,
                                borderRadius: 3,
                                backgroundColor: '#f0f0f0',
                                '& .MuiLinearProgress-bar': {
                                  backgroundColor: '#FFA500'
                                }
                              }}
                            />
                            <Typography variant="caption">
                              {enrollment.progress}
                            </Typography>
                          </Box>
                          <Typography variant="caption" color="text.secondary">
                            Step {enrollment.current_step_number} of {sequence?.total_steps || 0}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={enrollment.status.charAt(0).toUpperCase() + enrollment.status.slice(1)}
                            color={
                              enrollment.status === 'active' ? 'success' :
                              enrollment.status === 'paused' ? 'warning' :
                              enrollment.status === 'completed' ? 'success' :
                              'error'
                            }
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          {new Date(enrollment.enrolled_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell align="right">
                          <Tooltip title={enrollment.status === 'paused' ? 'Resume sequence' : 'Pause sequence'}>
                            <span>
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  enrollment.status === 'paused'
                                    ? handleResumeEnrollment(enrollment.id)
                                    : handlePauseEnrollment(enrollment.id);
                                }}
                                disabled={enrollment.status === 'completed' || enrollment.status === 'unsubscribed'}
                              >
                                {enrollment.status === 'paused' ? <PlayArrow /> : <Pause />}
                              </IconButton>
                            </span>
                          </Tooltip>
                          <Tooltip title="Unenroll contact">
                            <span>
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleUnenroll(enrollment.id);
                                }}
                                disabled={enrollment.status === 'unsubscribed'}
                              >
                                <PersonRemove />
                              </IconButton>
                            </span>
                          </Tooltip>
                        </TableCell>
                      </TableRow>

                      {/* Expanded row showing execution timeline */}
                      <TableRow>
                        <TableCell colSpan={7} sx={{ py: 0, borderBottom: expandedEnrollment === enrollment.id ? undefined : 'none' }}>
                          <Collapse in={expandedEnrollment === enrollment.id} timeout="auto" unmountOnExit>
                            <Box sx={{ py: 2, px: 4, backgroundColor: '#fafafa' }}>
                              <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Timeline sx={{ color: '#FFA500' }} />
                                Execution Timeline
                              </Typography>

                              {loadingExecutions[enrollment.id] ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                                  <CircularProgress size={24} />
                                </Box>
                              ) : executionsByEnrollment[enrollment.id]?.length === 0 ? (
                                <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                                  No executions yet. Emails will be scheduled according to step delays.
                                </Typography>
                              ) : (
                                <Table size="small">
                                  <TableHead>
                                    <TableRow>
                                      <TableCell>Step</TableCell>
                                      <TableCell>Email Template</TableCell>
                                      <TableCell>Scheduled For</TableCell>
                                      <TableCell>Sent At</TableCell>
                                      <TableCell>Status</TableCell>
                                      <TableCell>Attempts</TableCell>
                                    </TableRow>
                                  </TableHead>
                                  <TableBody>
                                    {executionsByEnrollment[enrollment.id]?.map((execution) => (
                                      <TableRow key={execution.id}>
                                        <TableCell>{execution.step_name}</TableCell>
                                        <TableCell>
                                          <Typography variant="caption">
                                            {execution.step_name}
                                          </Typography>
                                        </TableCell>
                                        <TableCell>
                                          <Typography variant="caption">
                                            {new Date(execution.scheduled_for).toLocaleString()}
                                          </Typography>
                                        </TableCell>
                                        <TableCell>
                                          <Typography variant="caption">
                                            {execution.sent_at
                                              ? new Date(execution.sent_at).toLocaleString()
                                              : '-'}
                                          </Typography>
                                        </TableCell>
                                        <TableCell>
                                          <Chip
                                            label={execution.status.charAt(0).toUpperCase() + execution.status.slice(1)}
                                            color={
                                              execution.status === 'sent' ? 'success' :
                                              execution.status === 'pending' || execution.status === 'scheduled' ? 'info' :
                                              execution.status === 'failed' ? 'error' :
                                              'default'
                                            }
                                            size="small"
                                          />
                                        </TableCell>
                                        <TableCell>
                                          <Typography variant="caption">
                                            {execution.attempt_count}
                                          </Typography>
                                          {execution.error_message && (
                                            <Tooltip title={execution.error_message}>
                                              <Error sx={{ fontSize: 16, color: 'error.main', ml: 0.5 }} />
                                            </Tooltip>
                                          )}
                                        </TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              )}
                            </Box>
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    </React.Fragment>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Form Modals */}
      <SequenceForm
        open={formOpen}
        onClose={handleFormClose}
        sequence={sequence}
        onSuccess={handleFormSave}
      />

      <SequenceStepForm
        open={stepFormOpen}
        onClose={() => {
          setStepFormOpen(false);
          setEditingStep(undefined);
        }}
        sequenceId={id!}
        step={editingStep}
        existingSteps={steps}
        onSuccess={handleStepFormSuccess}
      />

      {/* Delete Step Confirmation Dialog */}
      <Dialog open={deleteStepDialogOpen} onClose={() => setDeleteStepDialogOpen(false)}>
        <DialogTitle>Delete Step</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete this step? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteStepDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmDeleteStep} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Enroll Contact Dialog */}
      <EnrollContactDialog
        open={enrollDialogOpen}
        onClose={() => setEnrollDialogOpen(false)}
        sequenceId={id!}
        onSuccess={handleEnrollSuccess}
      />

      {/* Unenroll Confirmation Dialog */}
      <Dialog open={deleteEnrollmentDialogOpen} onClose={() => setDeleteEnrollmentDialogOpen(false)}>
        <DialogTitle>Unenroll Contact</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to unenroll this contact? This will stop all scheduled emails in the sequence.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteEnrollmentDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmUnenroll} color="error" variant="contained">
            Unenroll
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default SequenceDetail;
