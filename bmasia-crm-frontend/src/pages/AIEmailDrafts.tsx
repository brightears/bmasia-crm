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
  TablePagination,
  Chip,
  IconButton,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
  Divider,
  Tabs,
  Tab,
  TextField,
  Tooltip,
  Badge,
} from '@mui/material';
import {
  CheckCircle,
  Cancel,
  Edit,
  SmartToy,
  Visibility,
  Timer,
} from '@mui/icons-material';
import { AIEmailDraft } from '../types';
import ApiService from '../services/api';

type DraftStatus = 'pending_review' | 'approved' | 'rejected' | 'edited' | 'expired' | '';

const STATUS_TABS: { value: DraftStatus; label: string }[] = [
  { value: 'pending_review', label: 'Pending Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: '', label: 'All' },
];

function getStatusChipColor(
  status: AIEmailDraft['status']
): 'warning' | 'success' | 'error' | 'info' | 'default' {
  switch (status) {
    case 'pending_review': return 'warning';
    case 'approved': return 'success';
    case 'rejected': return 'error';
    case 'edited': return 'info';
    case 'expired': return 'default';
    default: return 'default';
  }
}

function getStatusLabel(status: AIEmailDraft['status']): string {
  switch (status) {
    case 'pending_review': return 'Pending Review';
    case 'approved': return 'Approved';
    case 'rejected': return 'Rejected';
    case 'edited': return 'Edited & Approved';
    case 'expired': return 'Expired';
    default: return status;
  }
}

function formatExpiry(expiresAt: string): { label: string; isExpired: boolean; isUrgent: boolean } {
  const now = new Date();
  const expiry = new Date(expiresAt);
  const diffMs = expiry.getTime() - now.getTime();
  if (diffMs < 0) {
    return { label: 'Expired', isExpired: true, isUrgent: false };
  }
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
  if (diffHours < 1) {
    return { label: `${diffMins}m`, isExpired: false, isUrgent: true };
  }
  if (diffHours < 24) {
    return { label: `${diffHours}h ${diffMins}m`, isExpired: false, isUrgent: diffHours < 4 };
  }
  const diffDays = Math.floor(diffHours / 24);
  return { label: `${diffDays}d`, isExpired: false, isUrgent: false };
}

const AIEmailDrafts: React.FC = () => {
  const [drafts, setDrafts] = useState<AIEmailDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Pagination
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  // Tab / Filter
  const [activeTab, setActiveTab] = useState<DraftStatus>('pending_review');

  // Pending count for badge
  const [pendingCount, setPendingCount] = useState(0);

  // Selected draft for preview
  const [previewDraft, setPreviewDraft] = useState<AIEmailDraft | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  // Approve action loading
  const [approveLoadingId, setApproveLoadingId] = useState<string | null>(null);

  // Reject dialog
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [rejectDraftId, setRejectDraftId] = useState('');
  const [rejectPauseSequence, setRejectPauseSequence] = useState(false);
  const [rejectLoading, setRejectLoading] = useState(false);

  // Edit & Approve dialog
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editDraft, setEditDraft] = useState<AIEmailDraft | null>(null);
  const [editSubject, setEditSubject] = useState('');
  const [editBody, setEditBody] = useState('');
  const [editLoading, setEditLoading] = useState(false);

  const loadDrafts = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: any = { page: page + 1, page_size: rowsPerPage };
      if (activeTab) params.status = activeTab;

      const data = await ApiService.getAIEmailDrafts(params);
      if (data && data.results) {
        setDrafts(data.results);
        setTotalCount(data.count || 0);
      } else if (Array.isArray(data)) {
        setDrafts(data);
        setTotalCount(data.length);
      } else {
        setDrafts([]);
        setTotalCount(0);
      }
    } catch (err: any) {
      setError('Failed to load AI email drafts. The backend endpoint may not be available yet.');
      setDrafts([]);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, activeTab]);

  const loadPendingCount = useCallback(async () => {
    try {
      const data = await ApiService.getAIEmailDraftPendingCount();
      setPendingCount(data.count || 0);
    } catch {
      // Silently fail — endpoint may not exist yet
    }
  }, []);

  useEffect(() => {
    loadDrafts();
  }, [loadDrafts]);

  useEffect(() => {
    loadPendingCount();
    const interval = setInterval(loadPendingCount, 60000);
    return () => clearInterval(interval);
  }, [loadPendingCount]);

  const handleApprove = async (id: string) => {
    try {
      setApproveLoadingId(id);
      await ApiService.approveAIEmailDraft(id);
      setSuccess('Email draft approved and queued for sending.');
      loadDrafts();
      loadPendingCount();
    } catch (err: any) {
      setError('Failed to approve draft.');
    } finally {
      setApproveLoadingId(null);
    }
  };

  const handleOpenReject = (id: string) => {
    setRejectDraftId(id);
    setRejectPauseSequence(false);
    setRejectDialogOpen(true);
  };

  const handleRejectConfirm = async () => {
    try {
      setRejectLoading(true);
      await ApiService.rejectAIEmailDraft(rejectDraftId, { pause_sequence: rejectPauseSequence });
      setSuccess('Draft rejected.');
      setRejectDialogOpen(false);
      loadDrafts();
      loadPendingCount();
    } catch (err: any) {
      setError('Failed to reject draft.');
    } finally {
      setRejectLoading(false);
    }
  };

  const handleOpenEdit = (draft: AIEmailDraft) => {
    setEditDraft(draft);
    setEditSubject(draft.edited_subject || draft.subject);
    setEditBody(draft.edited_body_html || draft.body_html);
    setEditDialogOpen(true);
  };

  const handleEditAndApprove = async () => {
    if (!editDraft) return;
    try {
      setEditLoading(true);
      await ApiService.editAndApproveAIEmailDraft(editDraft.id, {
        subject: editSubject,
        body_html: editBody,
      });
      setSuccess('Draft edited and approved.');
      setEditDialogOpen(false);
      loadDrafts();
      loadPendingCount();
    } catch (err: any) {
      setError('Failed to edit and approve draft.');
    } finally {
      setEditLoading(false);
    }
  };

  const handleOpenPreview = (draft: AIEmailDraft) => {
    setPreviewDraft(draft);
    setPreviewOpen(true);
  };

  const tabPendingLabel = (tab: DraftStatus) => {
    if (tab === 'pending_review' && pendingCount > 0) {
      return (
        <Badge badgeContent={pendingCount} color="error" sx={{ pr: 1 }}>
          Pending Review
        </Badge>
      );
    }
    return STATUS_TABS.find((t) => t.value === tab)?.label || tab;
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            AI Email Drafts
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Review and approve AI-generated prospect emails before they are sent
          </Typography>
        </Box>
        {pendingCount > 0 && (
          <Chip
            icon={<SmartToy />}
            label={`${pendingCount} awaiting review`}
            color="warning"
            variant="outlined"
          />
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Status Tabs */}
      <Paper sx={{ mb: 2 }}>
        <Tabs
          value={activeTab}
          onChange={(_, val) => {
            setActiveTab(val);
            setPage(0);
          }}
          variant="scrollable"
          scrollButtons="auto"
        >
          {STATUS_TABS.map((tab) => (
            <Tab key={tab.value} value={tab.value} label={tabPendingLabel(tab.value)} />
          ))}
        </Tabs>
      </Paper>

      {/* Table */}
      <Paper>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Contact</TableCell>
                <TableCell>Company</TableCell>
                <TableCell>Sequence / Step</TableCell>
                <TableCell>Subject</TableCell>
                <TableCell>Expires</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                    <CircularProgress size={32} />
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                      Loading drafts...
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : drafts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                    <SmartToy sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography variant="body1" color="text.secondary">
                      No drafts found
                    </Typography>
                    <Typography variant="body2" color="text.disabled">
                      {activeTab === 'pending_review'
                        ? 'No drafts awaiting review. AI emails will appear here when generated.'
                        : 'No drafts match the selected filter.'}
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                drafts.map((draft) => {
                  const expiry = formatExpiry(draft.expires_at);
                  const isActionable = draft.status === 'pending_review' && !expiry.isExpired;
                  return (
                    <TableRow
                      key={draft.id}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => handleOpenPreview(draft)}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {draft.contact_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {draft.contact_email}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{draft.company_name}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 160 }}>
                          {draft.sequence_name}
                        </Typography>
                        <Chip label={`Step ${draft.step_number}`} size="small" sx={{ mt: 0.5 }} />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 240 }}>
                          {draft.edited_subject || draft.subject}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <Timer
                            fontSize="small"
                            sx={{
                              color: expiry.isExpired
                                ? 'text.disabled'
                                : expiry.isUrgent
                                ? 'error.main'
                                : 'text.secondary',
                            }}
                          />
                          <Typography
                            variant="body2"
                            sx={{
                              color: expiry.isExpired
                                ? 'text.disabled'
                                : expiry.isUrgent
                                ? 'error.main'
                                : 'text.primary',
                              fontWeight: expiry.isUrgent ? 600 : 400,
                            }}
                          >
                            {expiry.isExpired ? 'Expired' : `${expiry.label}`}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={getStatusLabel(draft.status)}
                          color={getStatusChipColor(draft.status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                          <Tooltip title="Preview">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleOpenPreview(draft);
                              }}
                            >
                              <Visibility fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          {isActionable && (
                            <>
                              <Tooltip title="Approve & Send">
                                <IconButton
                                  size="small"
                                  color="success"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleApprove(draft.id);
                                  }}
                                  disabled={approveLoadingId === draft.id}
                                >
                                  {approveLoadingId === draft.id ? (
                                    <CircularProgress size={16} />
                                  ) : (
                                    <CheckCircle fontSize="small" />
                                  )}
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Edit & Approve">
                                <IconButton
                                  size="small"
                                  color="info"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleOpenEdit(draft);
                                  }}
                                >
                                  <Edit fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Reject">
                                <IconButton
                                  size="small"
                                  color="error"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleOpenReject(draft.id);
                                  }}
                                >
                                  <Cancel fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50]}
          component="div"
          count={totalCount || drafts.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
        />
      </Paper>

      {/* Preview Dialog */}
      <Dialog open={previewOpen} onClose={() => setPreviewOpen(false)} maxWidth="md" fullWidth>
        {previewDraft && (
          <>
            <DialogTitle>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SmartToy color="primary" />
                <Box>
                  <Typography variant="h6">Email Preview</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {previewDraft.sequence_name} &mdash; Step {previewDraft.step_number}
                  </Typography>
                </Box>
                <Box sx={{ ml: 'auto' }}>
                  <Chip
                    label={getStatusLabel(previewDraft.status)}
                    color={getStatusChipColor(previewDraft.status)}
                    size="small"
                  />
                </Box>
              </Box>
            </DialogTitle>
            <DialogContent dividers>
              <Box sx={{ display: 'flex', gap: 3, mb: 2, flexWrap: 'wrap' }}>
                <Box sx={{ minWidth: 160 }}>
                  <Typography variant="caption" color="text.secondary">To</Typography>
                  <Typography variant="body2">
                    {previewDraft.contact_name} &lt;{previewDraft.contact_email}&gt;
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Company</Typography>
                  <Typography variant="body2">{previewDraft.company_name}</Typography>
                </Box>
                <Box sx={{ flexBasis: '100%' }}>
                  <Typography variant="caption" color="text.secondary">Subject</Typography>
                  <Typography variant="body1" fontWeight={600}>
                    {previewDraft.edited_subject || previewDraft.subject}
                  </Typography>
                </Box>
              </Box>
              <Divider sx={{ mb: 2 }} />
              <Paper
                variant="outlined"
                sx={{ p: 2, bgcolor: 'grey.50', minHeight: 200, maxHeight: 400, overflow: 'auto' }}
              >
                <div
                  dangerouslySetInnerHTML={{
                    __html: previewDraft.edited_body_html || previewDraft.body_html,
                  }}
                />
              </Paper>
              {previewDraft.expires_at && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Expires: {new Date(previewDraft.expires_at).toLocaleString()}
                  {previewDraft.auto_approved && ' (auto-approval enabled)'}
                </Typography>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setPreviewOpen(false)}>Close</Button>
              {previewDraft.status === 'pending_review' && !previewDraft.is_expired && (
                <>
                  <Button
                    color="error"
                    onClick={() => {
                      setPreviewOpen(false);
                      handleOpenReject(previewDraft.id);
                    }}
                    startIcon={<Cancel />}
                  >
                    Reject
                  </Button>
                  <Button
                    color="info"
                    onClick={() => {
                      setPreviewOpen(false);
                      handleOpenEdit(previewDraft);
                    }}
                    startIcon={<Edit />}
                  >
                    Edit & Approve
                  </Button>
                  <Button
                    variant="contained"
                    color="success"
                    onClick={() => {
                      setPreviewOpen(false);
                      handleApprove(previewDraft.id);
                    }}
                    startIcon={<CheckCircle />}
                  >
                    Approve & Send
                  </Button>
                </>
              )}
            </DialogActions>
          </>
        )}
      </Dialog>

      {/* Edit & Approve Dialog */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Edit & Approve Email</DialogTitle>
        <DialogContent dividers>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            {editDraft && (
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Box sx={{ minWidth: 160 }}>
                  <Typography variant="caption" color="text.secondary">To</Typography>
                  <Typography variant="body2">{editDraft.contact_name}</Typography>
                  <Typography variant="caption" color="text.secondary">{editDraft.contact_email}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Sequence</Typography>
                  <Typography variant="body2">{editDraft.sequence_name} &mdash; Step {editDraft.step_number}</Typography>
                </Box>
              </Box>
            )}
            <TextField
              label="Subject"
              value={editSubject}
              onChange={(e) => setEditSubject(e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Email Body (HTML)"
              value={editBody}
              onChange={(e) => setEditBody(e.target.value)}
              multiline
              rows={12}
              fullWidth
              required
              helperText="You can edit the HTML directly. The formatted version will be sent to the contact."
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)} disabled={editLoading}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="success"
            onClick={handleEditAndApprove}
            disabled={editLoading || !editSubject.trim() || !editBody.trim()}
            startIcon={editLoading ? <CircularProgress size={16} /> : <CheckCircle />}
          >
            Save & Approve
          </Button>
        </DialogActions>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={rejectDialogOpen} onClose={() => setRejectDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Reject Email Draft</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 2 }}>
            Are you sure you want to reject this AI-generated email draft?
          </Typography>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              p: 1.5,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              cursor: 'pointer',
              '&:hover': { bgcolor: 'action.hover' },
            }}
            onClick={() => setRejectPauseSequence(!rejectPauseSequence)}
          >
            <input
              type="checkbox"
              checked={rejectPauseSequence}
              onChange={(e) => setRejectPauseSequence(e.target.checked)}
              style={{ cursor: 'pointer' }}
            />
            <Box>
              <Typography variant="body2" fontWeight={600}>
                Also pause the sequence enrollment
              </Typography>
              <Typography variant="caption" color="text.secondary">
                This will stop further automated steps for this contact in this sequence
              </Typography>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectDialogOpen(false)} disabled={rejectLoading}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleRejectConfirm}
            disabled={rejectLoading}
            startIcon={rejectLoading ? <CircularProgress size={16} /> : <Cancel />}
          >
            Reject Draft
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

export default AIEmailDrafts;
