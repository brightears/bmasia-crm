import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  IconButton,
  InputAdornment,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
  Divider,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Tooltip,
  Menu,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Delete,
  MoreVert,
  ExpandMore,
  AutoFixHigh,
  PlayArrow,
  Pause,
  Schedule,
} from '@mui/icons-material';
import { ProspectSequence, ProspectSequenceStep } from '../types';
import ApiService from '../services/api';

const TRIGGER_TYPE_OPTIONS = [
  { value: 'manual', label: 'Manual', color: '#9e9e9e' },
  { value: 'new_opportunity', label: 'New Opportunity', color: '#2196f3' },
  { value: 'quote_sent', label: 'Quote Sent', color: '#ff9800' },
  { value: 'stale_deal', label: 'Stale Deal', color: '#f44336' },
];

const ACTION_TYPE_OPTIONS = [
  { value: 'email', label: 'Email' },
  { value: 'ai_email', label: 'AI Email' },
  { value: 'task', label: 'Task' },
  { value: 'stage_update', label: 'Stage Update' },
];

const TASK_TYPE_OPTIONS = [
  { value: 'call', label: 'Call' },
  { value: 'email', label: 'Email' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'follow_up', label: 'Follow Up' },
  { value: 'demo', label: 'Demo' },
  { value: 'other', label: 'Other' },
];

const STAGE_OPTIONS = [
  'Contacted',
  'Quotation Sent',
  'Contract Sent',
  'Won',
  'Lost',
];

const BILLING_ENTITY_OPTIONS = [
  { value: '', label: 'All Entities' },
  { value: 'BMAsia (Thailand) Co., Ltd.', label: 'BMAsia Thailand' },
  { value: 'BMAsia Limited', label: 'BMAsia Limited (HK)' },
];

function getTriggerChipColor(triggerType: string): 'default' | 'primary' | 'warning' | 'error' {
  switch (triggerType) {
    case 'new_opportunity': return 'primary';
    case 'quote_sent': return 'warning';
    case 'stale_deal': return 'error';
    default: return 'default';
  }
}

function getTriggerLabel(triggerType: string): string {
  const opt = TRIGGER_TYPE_OPTIONS.find((o) => o.value === triggerType);
  return opt ? opt.label : triggerType;
}

const emptyStep = (): Omit<ProspectSequenceStep, 'id'> => ({
  step_number: 1,
  delay_days: 1,
  action_type: 'email',
  email_subject_template: '',
  email_body_template: '',
  ai_prompt_instructions: '',
  task_title_template: '',
  task_type: 'follow_up',
  stage_to_set: '',
});

const emptyForm = () => ({
  name: '',
  description: '',
  trigger_type: 'manual' as ProspectSequence['trigger_type'],
  target_stages: [] as string[],
  is_active: true,
  billing_entity: 'BMAsia Limited',
  max_enrollments_per_company: 1,
  stale_days_threshold: 14,
  steps: [] as Array<Omit<ProspectSequenceStep, 'id'>>,
});

const ProspectSequences: React.FC = () => {
  const [sequences, setSequences] = useState<ProspectSequence[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Pagination
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [search, setSearch] = useState('');
  const [triggerFilter, setTriggerFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingId, setDeletingId] = useState('');
  const [deletingName, setDeletingName] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);

  // Form state
  const [form, setForm] = useState(emptyForm());

  // Action menu
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [actionMenuSequence, setActionMenuSequence] = useState<ProspectSequence | null>(null);

  const loadSequences = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
      };
      if (search) params.search = search;
      if (triggerFilter) params.trigger_type = triggerFilter;
      if (activeFilter !== '') params.is_active = activeFilter;

      const data = await ApiService.getProspectSequences();
      // API may return paginated or array
      if (data && data.results) {
        setSequences(data.results);
        setTotalCount(data.count || 0);
      } else if (Array.isArray(data)) {
        setSequences(data);
        setTotalCount(data.length);
      } else {
        setSequences([]);
        setTotalCount(0);
      }
    } catch (err: any) {
      setError('Failed to load sequences. The backend endpoint may not be available yet.');
      setSequences([]);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, triggerFilter, activeFilter]);

  useEffect(() => {
    loadSequences();
  }, [loadSequences]);

  const handleOpenCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
    setDialogOpen(true);
  };

  const handleOpenEdit = (seq: ProspectSequence) => {
    setEditingId(seq.id);
    setForm({
      name: seq.name,
      description: seq.description,
      trigger_type: seq.trigger_type,
      target_stages: seq.target_stages || [],
      is_active: seq.is_active,
      billing_entity: seq.billing_entity,
      max_enrollments_per_company: seq.max_enrollments_per_company,
      stale_days_threshold: seq.stale_days_threshold,
      steps: (seq.steps || []).map((s) => ({
        step_number: s.step_number,
        delay_days: s.delay_days,
        action_type: s.action_type,
        email_subject_template: s.email_subject_template,
        email_body_template: s.email_body_template,
        ai_prompt_instructions: s.ai_prompt_instructions,
        task_title_template: s.task_title_template,
        task_type: s.task_type,
        stage_to_set: s.stage_to_set,
      })),
    });
    setDialogOpen(true);
    setActionMenuAnchor(null);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      setError('Sequence name is required.');
      return;
    }
    try {
      setSaveLoading(true);
      if (editingId) {
        await ApiService.updateProspectSequence(editingId, form);
        setSuccess('Sequence updated successfully.');
      } else {
        await ApiService.createProspectSequence(form);
        setSuccess('Sequence created successfully.');
      }
      setDialogOpen(false);
      loadSequences();
    } catch (err: any) {
      setError('Failed to save sequence.');
    } finally {
      setSaveLoading(false);
    }
  };

  const handleDeleteClick = (seq: ProspectSequence) => {
    setDeletingId(seq.id);
    setDeletingName(seq.name);
    setDeleteDialogOpen(true);
    setActionMenuAnchor(null);
  };

  const handleDeleteConfirm = async () => {
    try {
      setDeleteLoading(true);
      await ApiService.deleteProspectSequence(deletingId);
      setSuccess('Sequence deleted.');
      setDeleteDialogOpen(false);
      loadSequences();
    } catch (err: any) {
      setError('Failed to delete sequence.');
    } finally {
      setDeleteLoading(false);
    }
  };

  // Steps management
  const addStep = () => {
    const nextNum = form.steps.length + 1;
    setForm((prev) => ({
      ...prev,
      steps: [...prev.steps, { ...emptyStep(), step_number: nextNum }],
    }));
  };

  const removeStep = (index: number) => {
    setForm((prev) => {
      const updated = prev.steps.filter((_, i) => i !== index).map((s, i) => ({
        ...s,
        step_number: i + 1,
      }));
      return { ...prev, steps: updated };
    });
  };

  const updateStep = (index: number, field: string, value: any) => {
    setForm((prev) => {
      const updated = prev.steps.map((s, i) =>
        i === index ? { ...s, [field]: value } : s
      );
      return { ...prev, steps: updated };
    });
  };

  const handleActionMenuOpen = (event: React.MouseEvent<HTMLElement>, seq: ProspectSequence) => {
    event.stopPropagation();
    setActionMenuAnchor(event.currentTarget);
    setActionMenuSequence(seq);
  };

  const handleActionMenuClose = () => {
    setActionMenuAnchor(null);
    setActionMenuSequence(null);
  };

  const filteredSequences = sequences.filter((seq) => {
    if (search && !seq.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (triggerFilter && seq.trigger_type !== triggerFilter) return false;
    if (activeFilter === 'true' && !seq.is_active) return false;
    if (activeFilter === 'false' && seq.is_active) return false;
    return true;
  });

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Prospect Sequences
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Automated outreach sequences for sales prospects
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<Add />} onClick={handleOpenCreate}>
          New Sequence
        </Button>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Search sequences..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ minWidth: 240 }}
          />
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Trigger Type</InputLabel>
            <Select
              value={triggerFilter}
              label="Trigger Type"
              onChange={(e) => setTriggerFilter(e.target.value)}
            >
              <MenuItem value="">All Triggers</MenuItem>
              {TRIGGER_TYPE_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={activeFilter}
              label="Status"
              onChange={(e) => setActiveFilter(e.target.value)}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="true">Active</MenuItem>
              <MenuItem value="false">Inactive</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Table */}
      <Paper>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Trigger</TableCell>
                <TableCell align="center">Steps</TableCell>
                <TableCell align="center">Active Enrollments</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Entity</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                    <CircularProgress size={32} />
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                      Loading sequences...
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : filteredSequences.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                    <AutoFixHigh sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography variant="body1" color="text.secondary">
                      No sequences found
                    </Typography>
                    <Typography variant="body2" color="text.disabled">
                      Create your first prospect sequence to get started
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                filteredSequences.map((seq) => (
                  <TableRow
                    key={seq.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => handleOpenEdit(seq)}
                  >
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>
                        {seq.name}
                      </Typography>
                      {seq.description && (
                        <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 300, display: 'block' }}>
                          {seq.description}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={getTriggerLabel(seq.trigger_type)}
                        color={getTriggerChipColor(seq.trigger_type)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={seq.steps ? seq.steps.length : 0}
                        size="small"
                        icon={<Schedule sx={{ fontSize: '0.875rem' }} />}
                        sx={{ bgcolor: 'action.hover' }}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="body2">{seq.active_enrollments || 0}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={seq.is_active ? 'Active' : 'Inactive'}
                        color={seq.is_active ? 'success' : 'default'}
                        size="small"
                        icon={seq.is_active ? <PlayArrow sx={{ fontSize: '0.875rem' }} /> : <Pause sx={{ fontSize: '0.875rem' }} />}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary" noWrap>
                        {seq.billing_entity || 'All'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={(e) => handleActionMenuOpen(e, seq)}
                      >
                        <MoreVert fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50]}
          component="div"
          count={totalCount || filteredSequences.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
        />
      </Paper>

      {/* Action Menu */}
      <Menu
        anchorEl={actionMenuAnchor}
        open={Boolean(actionMenuAnchor)}
        onClose={handleActionMenuClose}
        onClick={(e) => e.stopPropagation()}
      >
        <MenuItem
          onClick={() => {
            if (actionMenuSequence) handleOpenEdit(actionMenuSequence);
          }}
        >
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <Divider />
        <MenuItem
          onClick={() => {
            if (actionMenuSequence) handleDeleteClick(actionMenuSequence);
          }}
          sx={{ color: 'error.main' }}
        >
          <ListItemIcon>
            <Delete fontSize="small" color="error" />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          {editingId ? 'Edit Sequence' : 'New Prospect Sequence'}
        </DialogTitle>
        <DialogContent dividers>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            {/* Basic Fields */}
            <TextField
              label="Sequence Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              fullWidth
            />
            <TextField
              label="Description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              multiline
              rows={2}
              fullWidth
            />

            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <FormControl sx={{ minWidth: 200 }}>
                <InputLabel>Trigger Type</InputLabel>
                <Select
                  value={form.trigger_type}
                  label="Trigger Type"
                  onChange={(e) =>
                    setForm({ ...form, trigger_type: e.target.value as ProspectSequence['trigger_type'] })
                  }
                >
                  {TRIGGER_TYPE_OPTIONS.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl sx={{ minWidth: 220 }}>
                <InputLabel>Billing Entity</InputLabel>
                <Select
                  value={form.billing_entity}
                  label="Billing Entity"
                  onChange={(e) => setForm({ ...form, billing_entity: e.target.value })}
                >
                  {BILLING_ENTITY_OPTIONS.filter((o) => o.value !== '').map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                label="Max Enrollments/Company"
                type="number"
                value={form.max_enrollments_per_company}
                onChange={(e) =>
                  setForm({ ...form, max_enrollments_per_company: parseInt(e.target.value, 10) || 1 })
                }
                sx={{ width: 200 }}
                inputProps={{ min: 1 }}
              />

              {form.trigger_type === 'stale_deal' && (
                <TextField
                  label="Stale Days Threshold"
                  type="number"
                  value={form.stale_days_threshold}
                  onChange={(e) =>
                    setForm({ ...form, stale_days_threshold: parseInt(e.target.value, 10) || 14 })
                  }
                  sx={{ width: 200 }}
                  inputProps={{ min: 1 }}
                />
              )}
            </Box>

            {/* Target Stages */}
            <FormControl fullWidth>
              <InputLabel>Target Stages (optional)</InputLabel>
              <Select
                multiple
                value={form.target_stages}
                label="Target Stages (optional)"
                onChange={(e) => {
                  const value = e.target.value;
                  setForm({
                    ...form,
                    target_stages: typeof value === 'string' ? value.split(',') : value,
                  });
                }}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {(selected as string[]).map((val) => (
                      <Chip key={val} label={val} size="small" />
                    ))}
                  </Box>
                )}
              >
                {STAGE_OPTIONS.map((stage) => (
                  <MenuItem key={stage} value={stage}>
                    {stage}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControlLabel
              control={
                <Switch
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  color="success"
                />
              }
              label="Active"
            />

            <Divider />

            {/* Steps Section */}
            <Box>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
                Sequence Steps ({form.steps.length})
              </Typography>

              {form.steps.map((step, index) => (
                <Accordion key={index} defaultExpanded={index === 0} sx={{ mb: 1 }}>
                  <AccordionSummary expandIcon={<ExpandMore />}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 1 }}>
                      <Chip label={`Step ${step.step_number}`} size="small" color="primary" />
                      <Typography variant="body2">
                        After {step.delay_days} day{step.delay_days !== 1 ? 's' : ''}
                      </Typography>
                      <Chip
                        label={ACTION_TYPE_OPTIONS.find((o) => o.value === step.action_type)?.label || step.action_type}
                        size="small"
                        sx={{ ml: 'auto', mr: 1 }}
                      />
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <Box sx={{ display: 'flex', gap: 2 }}>
                        <TextField
                          label="Delay (days)"
                          type="number"
                          value={step.delay_days}
                          onChange={(e) => updateStep(index, 'delay_days', parseInt(e.target.value, 10) || 0)}
                          sx={{ width: 140 }}
                          inputProps={{ min: 0 }}
                        />
                        <FormControl sx={{ minWidth: 180 }}>
                          <InputLabel>Action Type</InputLabel>
                          <Select
                            value={step.action_type}
                            label="Action Type"
                            onChange={(e) => updateStep(index, 'action_type', e.target.value)}
                          >
                            {ACTION_TYPE_OPTIONS.map((opt) => (
                              <MenuItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Box>

                      {/* Conditional fields based on action_type */}
                      {step.action_type === 'email' && (
                        <>
                          <TextField
                            label="Email Subject Template"
                            value={step.email_subject_template}
                            onChange={(e) => updateStep(index, 'email_subject_template', e.target.value)}
                            fullWidth
                            placeholder="e.g. Following up on your interest in {{company_name}}"
                          />
                          <TextField
                            label="Email Body Template"
                            value={step.email_body_template}
                            onChange={(e) => updateStep(index, 'email_body_template', e.target.value)}
                            multiline
                            rows={4}
                            fullWidth
                            placeholder="Email body with template variables like {{contact_name}}, {{company_name}}..."
                          />
                        </>
                      )}

                      {step.action_type === 'ai_email' && (
                        <TextField
                          label="AI Prompt Instructions"
                          value={step.ai_prompt_instructions}
                          onChange={(e) => updateStep(index, 'ai_prompt_instructions', e.target.value)}
                          multiline
                          rows={4}
                          fullWidth
                          placeholder="Describe what the AI should write, e.g. Write a personalized follow-up email for a music streaming prospect who received a quote for {{zone_count}} zones..."
                        />
                      )}

                      {step.action_type === 'task' && (
                        <>
                          <TextField
                            label="Task Title Template"
                            value={step.task_title_template}
                            onChange={(e) => updateStep(index, 'task_title_template', e.target.value)}
                            fullWidth
                            placeholder="e.g. Follow up call with {{contact_name}}"
                          />
                          <FormControl sx={{ minWidth: 180 }}>
                            <InputLabel>Task Type</InputLabel>
                            <Select
                              value={step.task_type}
                              label="Task Type"
                              onChange={(e) => updateStep(index, 'task_type', e.target.value)}
                            >
                              {TASK_TYPE_OPTIONS.map((opt) => (
                                <MenuItem key={opt.value} value={opt.value}>
                                  {opt.label}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        </>
                      )}

                      {step.action_type === 'stage_update' && (
                        <FormControl sx={{ minWidth: 220 }}>
                          <InputLabel>Stage to Set</InputLabel>
                          <Select
                            value={step.stage_to_set}
                            label="Stage to Set"
                            onChange={(e) => updateStep(index, 'stage_to_set', e.target.value)}
                          >
                            {STAGE_OPTIONS.map((stage) => (
                              <MenuItem key={stage} value={stage}>
                                {stage}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      )}

                      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <Button
                          variant="outlined"
                          color="error"
                          size="small"
                          startIcon={<Delete />}
                          onClick={() => removeStep(index)}
                        >
                          Remove Step
                        </Button>
                      </Box>
                    </Box>
                  </AccordionDetails>
                </Accordion>
              ))}

              <Button
                variant="outlined"
                startIcon={<Add />}
                onClick={addStep}
                sx={{ mt: 1 }}
              >
                Add Step
              </Button>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog} disabled={saveLoading}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saveLoading}
            startIcon={saveLoading ? <CircularProgress size={16} /> : undefined}
          >
            {editingId ? 'Save Changes' : 'Create Sequence'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Delete Sequence</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete <strong>{deletingName}</strong>? This will also cancel all
            active enrollments.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleteLoading}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDeleteConfirm}
            disabled={deleteLoading}
            startIcon={deleteLoading ? <CircularProgress size={16} /> : <Delete />}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Success Snackbar */}
      <Snackbar
        open={Boolean(success)}
        autoHideDuration={4000}
        onClose={() => setSuccess('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="success" onClose={() => setSuccess('')}>
          {success}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ProspectSequences;
