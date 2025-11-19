import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Chip,
  IconButton,
  Alert,
  CircularProgress,
  TextField,
  FormControlLabel,
  Checkbox,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Card,
  CardContent,
  Snackbar,
} from '@mui/material';
import { GridLegacy as Grid } from '@mui/material';
import {
  ArrowBack,
  Edit,
  Delete,
  Comment as CommentIcon,
  Lock,
  AttachFile,
  CloudUpload,
  GetApp,
  DeleteOutline,
  Warning,
} from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { Ticket, User } from '../types';
import ApiService from '../services/api';
import { formatDistanceToNow, format } from 'date-fns';

const TicketDetail: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [isInternalNote, setIsInternalNote] = useState(false);
  const [commentLoading, setCommentLoading] = useState(false);
  const [statusChanging, setStatusChanging] = useState(false);
  const [assignmentChanging, setAssignmentChanging] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  const loadTicket = useCallback(async () => {
    if (!id) return;

    try {
      setLoading(true);
      setError('');
      const data = await ApiService.getTicket(id);
      setTicket(data);
    } catch (err: any) {
      console.error('Failed to load ticket:', err);
      setError(`Failed to load ticket: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadUsers = useCallback(async () => {
    try {
      const response = await ApiService.getUsers();
      setUsers(response.results || []);
    } catch (err: any) {
      console.error('Failed to load users:', err);
    }
  }, []);

  useEffect(() => {
    loadTicket();
    loadUsers();
  }, [loadTicket, loadUsers]);

  const handleStatusChange = async (newStatus: string) => {
    if (!ticket) return;

    try {
      setStatusChanging(true);
      await ApiService.updateTicket(ticket.id, { status: newStatus });
      await loadTicket();
      setSuccessMessage(`Status changed to ${formatStatusLabel(newStatus)}`);
    } catch (err: any) {
      console.error('Failed to change status:', err);
      setError(`Failed to change status: ${err.response?.data?.detail || err.message}`);
    } finally {
      setStatusChanging(false);
    }
  };

  const handleAssignmentChange = async (userId: string) => {
    if (!ticket) return;

    try {
      setAssignmentChanging(true);
      await ApiService.assignTicket(ticket.id, userId || null);
      await loadTicket();
      setSuccessMessage(userId ? 'Ticket assigned successfully' : 'Ticket unassigned');
    } catch (err: any) {
      console.error('Failed to change assignment:', err);
      setError(`Failed to change assignment: ${err.response?.data?.detail || err.message}`);
    } finally {
      setAssignmentChanging(false);
    }
  };

  const handleAddComment = async () => {
    if (!ticket || !commentText.trim()) return;

    try {
      setCommentLoading(true);
      await ApiService.addTicketComment(ticket.id, {
        text: commentText,
        is_internal: isInternalNote,
      });
      await loadTicket();
      setCommentText('');
      setIsInternalNote(false);
      setSuccessMessage(isInternalNote ? 'Internal note added' : 'Comment added');
    } catch (err: any) {
      console.error('Failed to add comment:', err);
      setError(`Failed to add comment: ${err.response?.data?.detail || err.message}`);
    } finally {
      setCommentLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!ticket || !event.target.files || event.target.files.length === 0) return;

    const file = event.target.files[0];

    try {
      setUploadingFile(true);
      await ApiService.uploadTicketAttachment(ticket.id, file);
      await loadTicket();
      setSuccessMessage('File uploaded successfully');
    } catch (err: any) {
      console.error('Failed to upload file:', err);
      setError(`Failed to upload file: ${err.response?.data?.detail || err.message}`);
    } finally {
      setUploadingFile(false);
    }
  };

  const handleDeleteClick = () => {
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!ticket) return;

    try {
      setDeleteLoading(true);
      await ApiService.deleteTicket(ticket.id);
      navigate('/tickets');
    } catch (err: any) {
      console.error('Failed to delete ticket:', err);
      setError(`Failed to delete ticket: ${err.response?.data?.detail || err.message}`);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
  };

  const getStatusColor = (status: string): 'default' | 'primary' | 'info' | 'warning' | 'secondary' | 'success' => {
    switch (status) {
      case 'new':
        return 'primary';
      case 'assigned':
        return 'info';
      case 'in_progress':
        return 'warning';
      case 'pending':
        return 'secondary';
      case 'resolved':
        return 'success';
      case 'closed':
        return 'default';
      default:
        return 'default';
    }
  };

  const getPriorityColor = (priority: string): 'default' | 'error' | 'warning' | 'info' => {
    switch (priority) {
      case 'urgent':
        return 'error';
      case 'high':
        return 'warning';
      case 'medium':
        return 'info';
      case 'low':
        return 'default';
      default:
        return 'default';
    }
  };

  const formatStatusLabel = (status: string): string => {
    return status.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  };

  const formatCategoryLabel = (category: string): string => {
    return category.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatTimestamp = (dateString: string): string => {
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true });
    } catch {
      return dateString;
    }
  };

  const formatFullDate = (dateString: string): string => {
    try {
      return format(new Date(dateString), 'MMM dd, yyyy h:mm a');
    } catch {
      return dateString;
    }
  };

  const sortedComments = ticket?.comments
    ? [...ticket.comments].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      )
    : [];

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress sx={{ color: '#FFA500' }} />
      </Box>
    );
  }

  if (!ticket) {
    return (
      <Box>
        <Alert severity="error">Ticket not found</Alert>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/tickets')} sx={{ mt: 2 }}>
          Back to Tickets
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box display="flex" alignItems="center" gap={2}>
          <IconButton onClick={() => navigate('/tickets')}>
            <ArrowBack />
          </IconButton>
          <Box>
            <Typography variant="h4" component="h1">
              Ticket {ticket.ticket_number}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {ticket.subject}
            </Typography>
          </Box>
        </Box>
        <Box display="flex" gap={1}>
          <Button
            variant="outlined"
            startIcon={<Edit />}
            onClick={() => navigate(`/tickets/${ticket.id}/edit`)}
          >
            Edit
          </Button>
          <Button
            variant="outlined"
            color="error"
            startIcon={<Delete />}
            onClick={handleDeleteClick}
          >
            Delete
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError('')} sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Overdue Banner */}
      {ticket.is_overdue && ticket.due_date && (
        <Alert severity="error" icon={<Warning />} sx={{ mb: 3 }}>
          <Typography variant="body2" fontWeight={500}>
            OVERDUE - Due {formatFullDate(ticket.due_date)}
          </Typography>
        </Alert>
      )}

      {/* Main Content */}
      <Grid container spacing={3}>
        {/* Left Column (60%) */}
        <Grid item xs={12} md={7}>
          {/* Description Card */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Description
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                {ticket.description}
              </Typography>
            </CardContent>
          </Card>

          {/* Timeline Card */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Timeline
              </Typography>
              <List>
                {sortedComments.map((comment, index) => (
                  <React.Fragment key={comment.id}>
                    <ListItem
                      alignItems="flex-start"
                      sx={{
                        bgcolor: comment.is_internal ? '#FFF9E6' : 'transparent',
                        borderRadius: 1,
                        mb: 1,
                      }}
                    >
                      <ListItemAvatar>
                        <Avatar sx={{ bgcolor: comment.is_internal ? '#FFA500' : 'primary.main' }}>
                          {comment.is_internal ? <Lock /> : <CommentIcon />}
                        </Avatar>
                      </ListItemAvatar>
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={1}>
                            <Typography variant="body2" fontWeight={500}>
                              {comment.author_name || 'Unknown'}
                            </Typography>
                            {comment.author_role && (
                              <Chip label={comment.author_role} size="small" />
                            )}
                            {comment.is_internal && (
                              <Chip
                                label="Internal"
                                size="small"
                                sx={{ bgcolor: '#FFA500', color: 'white' }}
                              />
                            )}
                            <Typography variant="caption" color="text.secondary">
                              {formatTimestamp(comment.created_at)}
                            </Typography>
                          </Box>
                        }
                        secondary={
                          <Typography
                            variant="body2"
                            color="text.primary"
                            sx={{ mt: 1, whiteSpace: 'pre-wrap' }}
                          >
                            {comment.text}
                          </Typography>
                        }
                      />
                    </ListItem>
                    {index < sortedComments.length - 1 && <Divider sx={{ my: 1 }} />}
                  </React.Fragment>
                ))}
                {sortedComments.length === 0 && (
                  <Typography variant="body2" color="text.secondary" textAlign="center" py={2}>
                    No comments yet
                  </Typography>
                )}
              </List>
            </CardContent>
          </Card>

          {/* Add Comment Form */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Add Comment
              </Typography>
              <TextField
                fullWidth
                multiline
                rows={4}
                placeholder={isInternalNote ? 'Add an internal note...' : 'Add a comment...'}
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                sx={{
                  mb: 2,
                  '& .MuiOutlinedInput-root': {
                    borderColor: isInternalNote ? '#FFA500' : undefined,
                  },
                }}
              />
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={isInternalNote}
                      onChange={(e) => setIsInternalNote(e.target.checked)}
                      sx={{
                        color: '#FFA500',
                        '&.Mui-checked': { color: '#FFA500' },
                      }}
                    />
                  }
                  label={
                    <Box display="flex" alignItems="center" gap={0.5}>
                      <Lock fontSize="small" />
                      <Typography variant="body2">Internal Note</Typography>
                    </Box>
                  }
                />
                <Box display="flex" gap={1}>
                  <Typography variant="caption" color="text.secondary" alignSelf="center">
                    {commentText.length} characters
                  </Typography>
                  <Button
                    variant="contained"
                    onClick={handleAddComment}
                    disabled={!commentText.trim() || commentLoading}
                    startIcon={commentLoading ? <CircularProgress size={16} /> : undefined}
                    sx={{
                      bgcolor: '#FFA500',
                      '&:hover': { bgcolor: '#FF8C00' },
                    }}
                  >
                    {isInternalNote ? 'Add Internal Note' : 'Add Comment'}
                  </Button>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Right Column (40%) */}
        <Grid item xs={12} md={5}>
          {/* Status Card */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Status
              </Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Current Status
                  </Typography>
                  <Chip
                    label={formatStatusLabel(ticket.status)}
                    color={getStatusColor(ticket.status)}
                  />
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Priority
                  </Typography>
                  <Chip
                    label={ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1)}
                    color={getPriorityColor(ticket.priority)}
                  />
                </Box>
                <FormControl fullWidth size="small">
                  <InputLabel>Change Status</InputLabel>
                  <Select
                    value={ticket.status}
                    label="Change Status"
                    onChange={(e) => handleStatusChange(e.target.value)}
                    disabled={statusChanging}
                  >
                    <MenuItem value="new">New</MenuItem>
                    <MenuItem value="assigned">Assigned</MenuItem>
                    <MenuItem value="in_progress">In Progress</MenuItem>
                    <MenuItem value="pending">Pending</MenuItem>
                    <MenuItem value="resolved">Resolved</MenuItem>
                    <MenuItem value="closed">Closed</MenuItem>
                  </Select>
                </FormControl>
                {ticket.due_date && (
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Due Date
                    </Typography>
                    <Typography variant="body2">{formatFullDate(ticket.due_date)}</Typography>
                  </Box>
                )}
              </Box>
            </CardContent>
          </Card>

          {/* Details Card */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Details
              </Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Company
                  </Typography>
                  <Typography variant="body2">{ticket.company_name}</Typography>
                </Box>
                {ticket.contact_name && (
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Contact
                    </Typography>
                    <Typography variant="body2">{ticket.contact_name}</Typography>
                  </Box>
                )}
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Category
                  </Typography>
                  <Typography variant="body2">{formatCategoryLabel(ticket.category)}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Assigned To
                  </Typography>
                  <FormControl fullWidth size="small">
                    <Select
                      value={ticket.assigned_to || ''}
                      onChange={(e) => handleAssignmentChange(e.target.value)}
                      disabled={assignmentChanging}
                      displayEmpty
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
                </Box>
                {ticket.tags && (
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Tags
                    </Typography>
                    <Box display="flex" flexWrap="wrap" gap={0.5}>
                      {ticket.tags.split(',').map((tag, index) => (
                        <Chip key={index} label={tag.trim()} size="small" />
                      ))}
                    </Box>
                  </Box>
                )}
              </Box>
            </CardContent>
          </Card>

          {/* Time Tracking Card */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Time Tracking
              </Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Created
                  </Typography>
                  <Typography variant="body2">{formatFullDate(ticket.created_at)}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatTimestamp(ticket.created_at)}
                  </Typography>
                </Box>
                {ticket.first_response_at && (
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      First Response
                    </Typography>
                    <Typography variant="body2">{formatFullDate(ticket.first_response_at)}</Typography>
                    {ticket.first_response_time_hours && (
                      <Typography variant="caption" color="text.secondary">
                        {Math.round(ticket.first_response_time_hours)} hours
                      </Typography>
                    )}
                  </Box>
                )}
                {ticket.resolved_at && (
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Resolved
                    </Typography>
                    <Typography variant="body2">{formatFullDate(ticket.resolved_at)}</Typography>
                    {ticket.resolution_time_hours && (
                      <Typography variant="caption" color="text.secondary">
                        {Math.round(ticket.resolution_time_hours)} hours
                      </Typography>
                    )}
                  </Box>
                )}
              </Box>
            </CardContent>
          </Card>

          {/* Attachments Card */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Attachments
              </Typography>
              <List>
                {ticket.attachments?.map((attachment) => (
                  <ListItem
                    key={attachment.id}
                    secondaryAction={
                      <Box display="flex" gap={1}>
                        <IconButton
                          edge="end"
                          size="small"
                          component="a"
                          href={attachment.file}
                          download
                        >
                          <GetApp />
                        </IconButton>
                        <IconButton edge="end" size="small" color="error">
                          <DeleteOutline />
                        </IconButton>
                      </Box>
                    }
                  >
                    <ListItemAvatar>
                      <Avatar>
                        <AttachFile />
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={attachment.name}
                      secondary={`${formatFileSize(attachment.size)} - ${formatTimestamp(attachment.created_at)}`}
                    />
                  </ListItem>
                ))}
                {(!ticket.attachments || ticket.attachments.length === 0) && (
                  <Typography variant="body2" color="text.secondary" textAlign="center" py={2}>
                    No attachments
                  </Typography>
                )}
              </List>
              <Button
                variant="outlined"
                fullWidth
                startIcon={uploadingFile ? <CircularProgress size={16} /> : <CloudUpload />}
                component="label"
                disabled={uploadingFile}
                sx={{ mt: 2 }}
              >
                Upload File
                <input type="file" hidden onChange={handleFileUpload} />
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Ticket</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete ticket "{ticket.ticket_number}"? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel} disabled={deleteLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disabled={deleteLoading}
            startIcon={deleteLoading ? <CircularProgress size={16} /> : <Delete />}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Success Snackbar */}
      <Snackbar
        open={!!successMessage}
        autoHideDuration={3000}
        onClose={() => setSuccessMessage('')}
        message={successMessage}
      />
    </Box>
  );
};

export default TicketDetail;
