import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography,
  Box,
  Paper,
  Button,
  Chip,
  CircularProgress,
  Alert,
  IconButton,
  Stepper,
  Step,
  StepLabel,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  GridLegacy as Grid,
} from '@mui/material';
import {
  ArrowBack,
  Edit,
  Delete,
  Person,
  Business,
  Add,
  Pause,
  PlayArrow,
  Cancel,
  AutoAwesome,
  Email,
  Phone,
  TrendingUp,
} from '@mui/icons-material';
import ApiService from '../services/api';
import { Opportunity, OpportunityActivity, Quote, Contract, Task, ProspectEnrollment, ProspectStepExecution } from '../types';
import OpportunityForm from '../components/OpportunityForm';
import ActivityTimeline from '../components/ActivityTimeline';
import ActivityForm from '../components/ActivityForm';
import { formatCurrency, getServiceLabel } from '../constants/entities';

const stageConfig = [
  { id: 'Contacted', label: 'Contacted', color: '#2196f3' },
  { id: 'Quotation Sent', label: 'Quotation Sent', color: '#ff9800' },
  { id: 'Contract Sent', label: 'Contract Sent', color: '#9c27b0' },
  { id: 'Won', label: 'Won', color: '#4caf50' },
  { id: 'Lost', label: 'Lost', color: '#f44336' },
];

const OpportunityDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [activities, setActivities] = useState<OpportunityActivity[]>([]);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [enrollments, setEnrollments] = useState<ProspectEnrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentTab, setCurrentTab] = useState(0);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [activityDialogOpen, setActivityDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  useEffect(() => {
    if (id) {
      loadOpportunityData();
    }
  }, [id]);

  const loadOpportunityData = async () => {
    try {
      setLoading(true);
      setError(null);
      const oppData = await ApiService.getOpportunity(id!);
      setOpportunity(oppData);
      await loadTabData(currentTab);
      setLoading(false);
    } catch (err: any) {
      console.error('Error loading opportunity:', err);
      setError(err.response?.data?.detail || 'Failed to load opportunity');
      setLoading(false);
    }
  };

  const loadTabData = async (tabIndex: number) => {
    try {
      if (tabIndex === 1) {
        const actData = await ApiService.getActivitiesByOpportunity(id!);
        setActivities(actData);
      } else if (tabIndex === 2) {
        const quotesData = await ApiService.getQuotes({ opportunity: id });
        setQuotes(quotesData.results || []);
      } else if (tabIndex === 3) {
        const contractsData = await ApiService.getContracts({ opportunity: id });
        setContracts(contractsData.results || []);
      } else if (tabIndex === 4) {
        const tasksData = await ApiService.getTasks({ related_opportunity: id });
        setTasks(tasksData.results || []);
      } else if (tabIndex === 5) {
        const enrollData = await ApiService.getProspectEnrollments({ opportunity: id });
        setEnrollments(enrollData.results || enrollData);
      }
    } catch (err) {
      console.error('Error loading tab data:', err);
    }
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
    loadTabData(newValue);
  };

  const handleEditSave = (updatedOpportunity: Opportunity) => {
    setOpportunity(updatedOpportunity);
    setEditDialogOpen(false);
  };

  const handleDelete = async () => {
    try {
      await ApiService.deleteOpportunity(id!);
      navigate('/opportunities');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete opportunity');
    }
  };

  const handleActivitySaved = () => {
    setActivityDialogOpen(false);
    loadTabData(1);
  };

  const formatDate = (dateString?: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getStageColor = (stage: string) => {
    return stageConfig.find(s => s.id === stage)?.color || '#757575';
  };

  const getActiveStep = (stage: string) => {
    const idx = stageConfig.findIndex(s => s.id === stage);
    return idx >= 0 ? idx : 0;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !opportunity) {
    return (
      <Box>
        <Alert severity="error">{error || 'Opportunity not found'}</Alert>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/opportunities')} sx={{ mt: 2 }}>
          Back to Opportunities
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" alignItems="center" gap={2} mb={3} flexWrap="wrap">
        <IconButton onClick={() => navigate('/opportunities')}>
          <ArrowBack />
        </IconButton>
        <Box flex={1} minWidth={200}>
          <Box display="flex" alignItems="center" gap={2} mb={0.5} flexWrap="wrap">
            <Typography variant="h4" component="h1">
              {opportunity.name}
            </Typography>
            <Chip
              label={opportunity.stage}
              sx={{
                backgroundColor: getStageColor(opportunity.stage),
                color: 'white',
                fontWeight: 600,
              }}
            />
            {opportunity.service_type && (
              <Chip
                label={getServiceLabel(opportunity.service_type)}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 500 }}
              />
            )}
          </Box>
          <Box display="flex" alignItems="center" gap={3} flexWrap="wrap">
            <Box
              display="flex"
              alignItems="center"
              gap={0.5}
              sx={{ cursor: 'pointer' }}
              onClick={() => navigate(`/companies/${opportunity.company}`)}
            >
              <Business fontSize="small" color="action" />
              <Typography variant="body2" color="primary">
                {opportunity.company_name}
              </Typography>
            </Box>
            <Box display="flex" alignItems="center" gap={0.5}>
              <Person fontSize="small" color="action" />
              <Typography variant="body2" color="text.secondary">
                {opportunity.owner_name}
              </Typography>
            </Box>
          </Box>
        </Box>
        <Button variant="outlined" startIcon={<Edit />} onClick={() => setEditDialogOpen(true)}>
          Edit
        </Button>
        <Button variant="outlined" color="error" startIcon={<Delete />} onClick={() => setDeleteDialogOpen(true)}>
          Delete
        </Button>
      </Box>

      {/* KPI Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Expected Value
            </Typography>
            <Typography variant="h5" fontWeight="bold">
              {formatCurrency(opportunity.expected_value || 0, opportunity?.company_billing_entity)}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Weighted Value
            </Typography>
            <Typography variant="h5" fontWeight="bold">
              {formatCurrency(opportunity.weighted_value || 0, opportunity?.company_billing_entity)}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Probability
            </Typography>
            <Typography variant="h5" fontWeight="bold">
              {opportunity.probability}%
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Days in Stage
            </Typography>
            <Typography variant="h5" fontWeight="bold">
              {opportunity.days_in_stage} days
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Stage Stepper */}
      <Paper sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Stepper activeStep={getActiveStep(opportunity.stage)} alternativeLabel>
          {stageConfig.map((stage) => (
            <Step key={stage.id} completed={
              opportunity.stage === 'Won' ? stageConfig.findIndex(s => s.id === stage.id) <= 3 :
              opportunity.stage === 'Lost' ? stageConfig.findIndex(s => s.id === stage.id) < getActiveStep(opportunity.stage) :
              stageConfig.findIndex(s => s.id === stage.id) < getActiveStep(opportunity.stage)
            }>
              <StepLabel
                StepIconProps={{
                  sx: {
                    ...(opportunity.stage === 'Won' && stage.id === 'Won' ? { color: '#4caf50 !important' } : {}),
                    ...(opportunity.stage === 'Lost' && stage.id === 'Lost' ? { color: '#f44336 !important' } : {}),
                  },
                }}
              >
                {stage.label}
              </StepLabel>
            </Step>
          ))}
        </Stepper>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ borderRadius: 2 }}>
        <Tabs value={currentTab} onChange={handleTabChange}>
          <Tab label="Overview" />
          <Tab label="Activities" />
          <Tab label="Quotes" />
          <Tab label="Contracts" />
          <Tab label="Tasks" />
          <Tab label="Automation" />
        </Tabs>

        <Box p={3}>
          {/* Overview Tab */}
          {currentTab === 0 && (
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                  <Typography variant="h6" gutterBottom>Basic Information</Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">Company</Typography>
                      <Typography
                        variant="body1"
                        color="primary"
                        sx={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/companies/${opportunity.company}`)}
                      >
                        {opportunity.company_name}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">Owner</Typography>
                      <Typography variant="body1">{opportunity.owner_name}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">Service</Typography>
                      <Typography variant="body1">{getServiceLabel(opportunity.service_type)}</Typography>
                    </Grid>
                    {opportunity.lead_source && (
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Lead Source</Typography>
                        <Typography variant="body1">{opportunity.lead_source}</Typography>
                      </Grid>
                    )}
                    {opportunity.contact_method && (
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Contact Method</Typography>
                        <Typography variant="body1">{opportunity.contact_method}</Typography>
                      </Grid>
                    )}
                    {opportunity.last_contact_date && (
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Last Contact</Typography>
                        <Typography variant="body1">{formatDate(opportunity.last_contact_date)}</Typography>
                      </Grid>
                    )}
                    {opportunity.follow_up_date && (
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Follow-up Date</Typography>
                        <Typography variant="body1" sx={{ color: opportunity.is_overdue ? 'error.main' : 'text.primary' }}>
                          {formatDate(opportunity.follow_up_date)}
                        </Typography>
                      </Grid>
                    )}
                    {opportunity.expected_close_date && (
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Expected Close</Typography>
                        <Typography variant="body1">{formatDate(opportunity.expected_close_date)}</Typography>
                      </Grid>
                    )}
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">Created</Typography>
                      <Typography variant="body1">{formatDate(opportunity.created_at)}</Typography>
                    </Grid>
                  </Grid>
                </Paper>
              </Grid>

              <Grid item xs={12} md={6}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, mb: 3 }}>
                  <Typography variant="h6" gutterBottom>Financial Details</Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">Expected Value</Typography>
                      <Typography variant="body1">{formatCurrency(opportunity.expected_value || 0, opportunity?.company_billing_entity)}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">Weighted Value</Typography>
                      <Typography variant="body1">{formatCurrency(opportunity.weighted_value || 0, opportunity?.company_billing_entity)}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">Probability</Typography>
                      <Typography variant="body1">{opportunity.probability}%</Typography>
                    </Grid>
                  </Grid>
                </Paper>

                {(opportunity.notes || opportunity.competitors || opportunity.pain_points || opportunity.decision_criteria) && (
                  <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                    <Typography variant="h6" gutterBottom>Additional Details</Typography>
                    <Grid container spacing={2}>
                      {opportunity.notes && (
                        <Grid item xs={12}>
                          <Typography variant="body2" color="text.secondary">Notes</Typography>
                          <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>{opportunity.notes}</Typography>
                        </Grid>
                      )}
                      {opportunity.competitors && (
                        <Grid item xs={12}>
                          <Typography variant="body2" color="text.secondary">Competitors</Typography>
                          <Typography variant="body1">{opportunity.competitors}</Typography>
                        </Grid>
                      )}
                      {opportunity.pain_points && (
                        <Grid item xs={12}>
                          <Typography variant="body2" color="text.secondary">Pain Points</Typography>
                          <Typography variant="body1">{opportunity.pain_points}</Typography>
                        </Grid>
                      )}
                      {opportunity.decision_criteria && (
                        <Grid item xs={12}>
                          <Typography variant="body2" color="text.secondary">Decision Criteria</Typography>
                          <Typography variant="body1">{opportunity.decision_criteria}</Typography>
                        </Grid>
                      )}
                    </Grid>
                  </Paper>
                )}
              </Grid>
            </Grid>
          )}

          {/* Activities Tab */}
          {currentTab === 1 && (
            <Box>
              <Box display="flex" justifyContent="flex-end" mb={2}>
                <Button variant="contained" startIcon={<Add />} onClick={() => setActivityDialogOpen(true)}>
                  Log Activity
                </Button>
              </Box>
              {activities.length > 0 ? (
                <ActivityTimeline activities={activities} />
              ) : (
                <Box textAlign="center" py={4}>
                  <Typography variant="body1" color="text.secondary">
                    No activities recorded yet
                  </Typography>
                </Box>
              )}
            </Box>
          )}

          {/* Quotes Tab */}
          {currentTab === 2 && (
            <Box>
              <Box display="flex" justifyContent="flex-end" mb={2}>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  onClick={() => navigate(`/quotes?new=true&opportunity=${id}&company=${opportunity.company}`)}
                >
                  Create Quote
                </Button>
              </Box>
              {quotes.length > 0 ? (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Quote #</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell align="right">Value</TableCell>
                        <TableCell>Valid From</TableCell>
                        <TableCell>Valid Until</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {quotes.map((quote) => (
                        <TableRow
                          key={quote.id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/quotes/${quote.id}`)}
                        >
                          <TableCell>{quote.quote_number}</TableCell>
                          <TableCell>
                            <Chip
                              label={quote.status}
                              size="small"
                              color={
                                quote.status === 'Accepted' ? 'success' :
                                quote.status === 'Rejected' ? 'error' : 'default'
                              }
                            />
                          </TableCell>
                          <TableCell align="right">{formatCurrency(quote.total_value || 0, opportunity?.company_billing_entity)}</TableCell>
                          <TableCell>{formatDate(quote.valid_from)}</TableCell>
                          <TableCell>{formatDate(quote.valid_until)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Box textAlign="center" py={4}>
                  <Typography variant="body1" color="text.secondary">
                    No quotes linked to this opportunity
                  </Typography>
                </Box>
              )}
            </Box>
          )}

          {/* Contracts Tab */}
          {currentTab === 3 && (
            <Box>
              {contracts.length > 0 ? (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Contract #</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell align="right">Value</TableCell>
                        <TableCell>Start Date</TableCell>
                        <TableCell>End Date</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {contracts.map((contract) => (
                        <TableRow
                          key={contract.id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/contracts/${contract.id}`)}
                        >
                          <TableCell>{contract.contract_number}</TableCell>
                          <TableCell>
                            <Chip
                              label={contract.status}
                              size="small"
                              color={
                                contract.status === 'Active' ? 'success' :
                                contract.status === 'Expired' ? 'error' : 'default'
                              }
                            />
                          </TableCell>
                          <TableCell align="right">{formatCurrency(contract.value || 0, opportunity?.company_billing_entity)}</TableCell>
                          <TableCell>{formatDate(contract.start_date)}</TableCell>
                          <TableCell>{formatDate(contract.end_date)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Box textAlign="center" py={4}>
                  <Typography variant="body1" color="text.secondary">
                    No contracts linked to this opportunity
                  </Typography>
                </Box>
              )}
            </Box>
          )}

          {/* Tasks Tab */}
          {currentTab === 4 && (
            <Box>
              <Box display="flex" justifyContent="flex-end" mb={2}>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  onClick={() => navigate(`/tasks?new=true&opportunity=${id}&company=${opportunity.company}`)}
                >
                  Create Task
                </Button>
              </Box>
              {tasks.length > 0 ? (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Title</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell>Priority</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Due Date</TableCell>
                        <TableCell>Assignee</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {tasks.map((task) => (
                        <TableRow
                          key={task.id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/tasks`)}
                        >
                          <TableCell>{task.title}</TableCell>
                          <TableCell>{task.task_type || 'N/A'}</TableCell>
                          <TableCell>
                            <Chip
                              label={task.priority}
                              size="small"
                              color={
                                task.priority === 'Urgent' ? 'error' :
                                task.priority === 'High' ? 'warning' :
                                task.priority === 'Medium' ? 'info' : 'default'
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={task.status}
                              size="small"
                              color={
                                task.status === 'Done' ? 'success' :
                                task.status === 'In Progress' ? 'primary' :
                                task.status === 'Cancelled' ? 'error' : 'default'
                              }
                            />
                          </TableCell>
                          <TableCell>{formatDate(task.due_date)}</TableCell>
                          <TableCell>{task.assigned_to_name || 'Unassigned'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Box textAlign="center" py={4}>
                  <Typography variant="body1" color="text.secondary">
                    No tasks linked to this opportunity
                  </Typography>
                </Box>
              )}
            </Box>
          )}

          {/* Automation Tab */}
          {currentTab === 5 && (
            <Box>
              {enrollments.length > 0 ? (
                <>
                  {enrollments.map((enrollment) => (
                    <Paper key={enrollment.id} variant="outlined" sx={{ p: 2, mb: 2 }}>
                      {/* Enrollment Header */}
                      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                        <Box display="flex" alignItems="center" gap={1}>
                          <AutoAwesome fontSize="small" color="primary" />
                          <Typography variant="subtitle1" fontWeight={600}>
                            {enrollment.sequence_name}
                          </Typography>
                          <Chip
                            label={enrollment.status}
                            size="small"
                            color={
                              enrollment.status === 'active' ? 'primary' :
                              enrollment.status === 'paused' ? 'warning' :
                              enrollment.status === 'completed' ? 'success' :
                              enrollment.status === 'replied' ? 'info' : 'default'
                            }
                          />
                        </Box>
                        <Box>
                          {enrollment.status === 'active' && (
                            <Button
                              size="small"
                              startIcon={<Pause />}
                              onClick={async (e) => {
                                e.stopPropagation();
                                await ApiService.pauseEnrollment(enrollment.id);
                                loadTabData(5);
                              }}
                            >
                              Pause
                            </Button>
                          )}
                          {enrollment.status === 'paused' && (
                            <Button
                              size="small"
                              startIcon={<PlayArrow />}
                              color="success"
                              onClick={async (e) => {
                                e.stopPropagation();
                                await ApiService.resumeEnrollment(enrollment.id);
                                loadTabData(5);
                              }}
                            >
                              Resume
                            </Button>
                          )}
                          {(enrollment.status === 'active' || enrollment.status === 'paused') && (
                            <Button
                              size="small"
                              startIcon={<Cancel />}
                              color="error"
                              onClick={async (e) => {
                                e.stopPropagation();
                                await ApiService.cancelEnrollment(enrollment.id);
                                loadTabData(5);
                              }}
                            >
                              Cancel
                            </Button>
                          )}
                        </Box>
                      </Box>

                      {/* Enrollment Info */}
                      <Box display="flex" gap={3} mb={2}>
                        <Typography variant="body2" color="text.secondary">
                          Contact: {enrollment.contact_name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Enrolled: {formatDate(enrollment.enrolled_at)}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Step {enrollment.current_step} of {enrollment.total_steps}
                        </Typography>
                        {enrollment.pause_reason && (
                          <Typography variant="body2" color="text.secondary">
                            Pause reason: {enrollment.pause_reason.replace(/_/g, ' ')}
                          </Typography>
                        )}
                      </Box>

                      {/* Step Executions */}
                      {enrollment.step_executions && enrollment.step_executions.length > 0 && (
                        <TableContainer>
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell>Step</TableCell>
                                <TableCell>Type</TableCell>
                                <TableCell>Scheduled</TableCell>
                                <TableCell>Executed</TableCell>
                                <TableCell>Status</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {Array.from(enrollment.step_executions)
                                .sort((a: ProspectStepExecution, b: ProspectStepExecution) => a.step_number - b.step_number)
                                .map((exec: ProspectStepExecution) => (
                                <TableRow key={exec.id}>
                                  <TableCell>{exec.step_number}</TableCell>
                                  <TableCell>
                                    <Box display="flex" alignItems="center" gap={0.5}>
                                      {exec.action_type === 'email' || exec.action_type === 'ai_email' ? (
                                        <Email fontSize="small" color="action" />
                                      ) : exec.action_type === 'task' ? (
                                        <Phone fontSize="small" color="action" />
                                      ) : (
                                        <TrendingUp fontSize="small" color="action" />
                                      )}
                                      {exec.action_type === 'ai_email' ? 'AI Email' :
                                       exec.action_type === 'email' ? 'Email' :
                                       exec.action_type === 'task' ? 'Task' :
                                       exec.action_type === 'stage_update' ? 'Stage Update' : exec.action_type}
                                    </Box>
                                  </TableCell>
                                  <TableCell>{formatDate(exec.scheduled_for)}</TableCell>
                                  <TableCell>{exec.executed_at ? formatDate(exec.executed_at) : '—'}</TableCell>
                                  <TableCell>
                                    <Chip
                                      label={exec.status === 'pending_approval' ? 'Pending Approval' : exec.status}
                                      size="small"
                                      color={
                                        exec.status === 'sent' ? 'success' :
                                        exec.status === 'pending_approval' ? 'warning' :
                                        exec.status === 'failed' ? 'error' :
                                        exec.status === 'pending' ? 'default' : 'default'
                                      }
                                    />
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      )}
                    </Paper>
                  ))}
                </>
              ) : (
                <Box textAlign="center" py={4}>
                  <Typography variant="body1" color="text.secondary">
                    No automation sequences for this opportunity
                  </Typography>
                </Box>
              )}
            </Box>
          )}
        </Box>
      </Paper>

      {/* Edit Opportunity Dialog */}
      <OpportunityForm
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        onSave={handleEditSave}
        opportunity={opportunity}
        mode="edit"
      />

      {/* Log Activity Dialog */}
      <ActivityForm
        open={activityDialogOpen}
        onClose={() => setActivityDialogOpen(false)}
        onSave={handleActivitySaved}
        opportunity={opportunity}
        mode="create"
      />

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Confirm Delete</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete "{opportunity.name}"? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDelete} color="error" variant="contained">Delete</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default OpportunityDetail;
