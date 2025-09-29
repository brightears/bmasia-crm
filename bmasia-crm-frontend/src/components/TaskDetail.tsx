import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Chip,
  Avatar,
  IconButton,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  LinearProgress,
  Tooltip,
  Menu,
  MenuItem,
  ListItemAvatar,
  Paper,
  Card,
  CardContent,
  CardHeader,
  Tabs,
  Tab,
  TextField,
  FormControlLabel,
  Checkbox,
  useTheme,
  Alert,
} from '@mui/material';
import {
  Close as CloseIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Flag as FlagIcon,
  Person as PersonIcon,
  Business as BusinessIcon,
  Schedule as ScheduleIcon,
  CheckCircle as CheckCircleIcon,
  RadioButtonUnchecked as RadioButtonUncheckedIcon,
  Comment as CommentIcon,
  AttachFile as AttachFileIcon,
  MoreVert as MoreVertIcon,
  PlayArrow as PlayArrowIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  RateReview as RateReviewIcon,
  Link as LinkIcon,
  Timeline as TimelineIcon,
  AccessTime as AccessTimeIcon,
  Assignment as AssignmentIcon,
  Label as LabelIcon,
} from '@mui/icons-material';
import { Task, TaskComment, User } from '../types';
import { format, parseISO, formatDistanceToNow } from 'date-fns';

interface TaskDetailProps {
  open: boolean;
  onClose: () => void;
  task: Task;
  onEdit: () => void;
  onDelete: (taskId: string) => void;
  onStatusChange: (taskId: string, newStatus: Task['status']) => void;
  users: User[];
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`task-tabpanel-${index}`}
      aria-labelledby={`task-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ py: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
};

const TaskDetail: React.FC<TaskDetailProps> = ({
  open,
  onClose,
  task,
  onEdit,
  onDelete,
  onStatusChange,
  users,
}) => {
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState(0);
  const [statusMenuAnchor, setStatusMenuAnchor] = useState<null | HTMLElement>(null);
  const [newComment, setNewComment] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);

  const getPriorityColor = (priority: Task['priority']) => {
    switch (priority) {
      case 'Urgent': return theme.palette.error.main;
      case 'High': return theme.palette.warning.main;
      case 'Medium': return theme.palette.info.main;
      case 'Low': return theme.palette.success.main;
      default: return theme.palette.grey[400];
    }
  };

  const getStatusColor = (status: Task['status']) => {
    switch (status) {
      case 'To Do': return 'default';
      case 'In Progress': return 'info';
      case 'Review': return 'warning';
      case 'Done': return 'success';
      case 'Cancelled': return 'error';
      case 'On Hold': return 'warning';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: Task['status']) => {
    switch (status) {
      case 'To Do': return <RadioButtonUncheckedIcon />;
      case 'In Progress': return <PlayArrowIcon />;
      case 'Review': return <RateReviewIcon />;
      case 'Done': return <CheckCircleIcon />;
      case 'Cancelled': return <StopIcon />;
      case 'On Hold': return <PauseIcon />;
      default: return <RadioButtonUncheckedIcon />;
    }
  };

  const getInitials = (name?: string) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase();
  };

  const formatDueDate = (dueDate?: string) => {
    if (!dueDate) return 'No due date';

    const date = parseISO(dueDate);
    const distance = formatDistanceToNow(date, { addSuffix: true });
    const formatted = format(date, 'MMM d, yyyy');

    return `${formatted} (${distance})`;
  };

  const getDueDateColor = () => {
    if (!task.due_date) return theme.palette.text.secondary;
    if (task.is_overdue) return theme.palette.error.main;

    const date = parseISO(task.due_date);
    const now = new Date();
    const diffDays = Math.ceil((date.getTime() - now.getTime()) / (1000 * 3600 * 24));

    if (diffDays === 0) return theme.palette.warning.main;
    if (diffDays === 1) return theme.palette.info.main;
    return theme.palette.text.secondary;
  };

  const getSubtaskProgress = () => {
    if (!task.subtasks || task.subtasks.length === 0) return null;

    const completed = task.subtasks.filter(s => s.completed).length;
    const total = task.subtasks.length;
    const percentage = Math.round((completed / total) * 100);

    return { completed, total, percentage };
  };

  const handleStatusMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setStatusMenuAnchor(event.currentTarget);
  };

  const handleStatusMenuClose = () => {
    setStatusMenuAnchor(null);
  };

  const handleStatusChange = (newStatus: Task['status']) => {
    onStatusChange(task.id, newStatus);
    handleStatusMenuClose();
  };

  const handleDeleteClick = () => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      onDelete(task.id);
    }
  };

  const handleSubmitComment = async () => {
    if (!newComment.trim()) return;

    setSubmittingComment(true);
    try {
      // This would integrate with the API to add comments
      console.log('Adding comment:', newComment);
      setNewComment('');
    } catch (error) {
      console.error('Error adding comment:', error);
    } finally {
      setSubmittingComment(false);
    }
  };

  const progress = getSubtaskProgress();

  const statusOptions = [
    { value: 'To Do', label: 'To Do' },
    { value: 'In Progress', label: 'In Progress' },
    { value: 'Review', label: 'Review' },
    { value: 'Done', label: 'Done' },
    { value: 'On Hold', label: 'On Hold' },
    { value: 'Cancelled', label: 'Cancelled' },
  ];

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { minHeight: '80vh' }
      }}
    >
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start">
          <Box flex={1}>
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              <FlagIcon sx={{ color: getPriorityColor(task.priority) }} />
              <Typography variant="h5" component="h1">
                {task.title}
              </Typography>
              {task.task_type && (
                <Chip
                  label={task.task_type}
                  size="small"
                  sx={{ ml: 1 }}
                />
              )}
            </Box>

            <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
              <Button
                variant="outlined"
                size="small"
                startIcon={getStatusIcon(task.status)}
                color={getStatusColor(task.status) as any}
                onClick={handleStatusMenuClick}
                sx={{ minWidth: 120 }}
              >
                {task.status}
              </Button>

              <Chip
                label={task.priority}
                size="small"
                sx={{ color: getPriorityColor(task.priority) }}
                variant="outlined"
              />

              {task.is_overdue && (
                <Chip
                  label="Overdue"
                  size="small"
                  color="error"
                />
              )}
            </Box>
          </Box>

          <Box display="flex" alignItems="center" gap={1}>
            <IconButton onClick={onEdit}>
              <EditIcon />
            </IconButton>
            <IconButton onClick={handleDeleteClick} color="error">
              <DeleteIcon />
            </IconButton>
            <IconButton onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ p: 0 }}>
        <Tabs
          value={activeTab}
          onChange={(_, value) => setActiveTab(value)}
          sx={{ borderBottom: 1, borderColor: 'divider', px: 3 }}
        >
          <Tab label="Overview" />
          <Tab label="Subtasks" />
          <Tab label="Activity" />
          <Tab label="Time Tracking" />
        </Tabs>

        <Box sx={{ px: 3 }}>
          {/* Overview Tab */}
          <TabPanel value={activeTab} index={0}>
            <Box display="flex" gap={3}>
              {/* Left Column */}
              <Box flex={2}>
                <Card sx={{ mb: 3 }}>
                  <CardHeader title="Description" />
                  <CardContent sx={{ pt: 0 }}>
                    <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                      {task.description || 'No description provided.'}
                    </Typography>
                  </CardContent>
                </Card>

                {/* Related Entities */}
                {(task.related_opportunity_name || task.related_contract_number || task.related_contact_name) && (
                  <Card sx={{ mb: 3 }}>
                    <CardHeader
                      title="Related Entities"
                      avatar={<LinkIcon />}
                    />
                    <CardContent sx={{ pt: 0 }}>
                      <List dense>
                        {task.related_opportunity_name && (
                          <ListItem>
                            <ListItemIcon>
                              <BusinessIcon />
                            </ListItemIcon>
                            <ListItemText
                              primary="Opportunity"
                              secondary={task.related_opportunity_name}
                            />
                          </ListItem>
                        )}
                        {task.related_contract_number && (
                          <ListItem>
                            <ListItemIcon>
                              <AssignmentIcon />
                            </ListItemIcon>
                            <ListItemText
                              primary="Contract"
                              secondary={task.related_contract_number}
                            />
                          </ListItem>
                        )}
                        {task.related_contact_name && (
                          <ListItem>
                            <ListItemIcon>
                              <PersonIcon />
                            </ListItemIcon>
                            <ListItemText
                              primary="Contact"
                              secondary={task.related_contact_name}
                            />
                          </ListItem>
                        )}
                      </List>
                    </CardContent>
                  </Card>
                )}

                {/* Tags */}
                {task.tags && (
                  <Card>
                    <CardHeader
                      title="Tags"
                      avatar={<LabelIcon />}
                    />
                    <CardContent sx={{ pt: 0 }}>
                      <Box display="flex" gap={1} flexWrap="wrap">
                        {task.tags.split(',').map((tag, index) => (
                          <Chip
                            key={index}
                            label={tag.trim()}
                            size="small"
                            variant="outlined"
                          />
                        ))}
                      </Box>
                    </CardContent>
                  </Card>
                )}
              </Box>

              {/* Right Column */}
              <Box flex={1}>
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    Task Details
                  </Typography>

                  <List dense>
                    <ListItem>
                      <ListItemIcon>
                        <BusinessIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Company"
                        secondary={task.company_name}
                      />
                    </ListItem>

                    <ListItem>
                      <ListItemIcon>
                        <PersonIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Assignee"
                        secondary={
                          <Box display="flex" alignItems="center" gap={1}>
                            <Avatar
                              sx={{
                                width: 24,
                                height: 24,
                                fontSize: '0.7rem',
                                bgcolor: task.assigned_to ? theme.palette.primary.main : theme.palette.grey[400],
                              }}
                            >
                              {getInitials(task.assigned_to_name)}
                            </Avatar>
                            {task.assigned_to_name || 'Unassigned'}
                          </Box>
                        }
                      />
                    </ListItem>

                    <ListItem>
                      <ListItemIcon>
                        <ScheduleIcon sx={{ color: getDueDateColor() }} />
                      </ListItemIcon>
                      <ListItemText
                        primary="Due Date"
                        secondary={
                          <Typography
                            variant="body2"
                            sx={{ color: getDueDateColor() }}
                          >
                            {formatDueDate(task.due_date)}
                          </Typography>
                        }
                      />
                    </ListItem>

                    <ListItem>
                      <ListItemIcon>
                        <PersonIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Created by"
                        secondary={task.created_by_name}
                      />
                    </ListItem>

                    <ListItem>
                      <ListItemIcon>
                        <TimelineIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Created"
                        secondary={format(parseISO(task.created_at), 'MMM d, yyyy')}
                      />
                    </ListItem>

                    {task.completed_at && (
                      <ListItem>
                        <ListItemIcon>
                          <CheckCircleIcon />
                        </ListItemIcon>
                        <ListItemText
                          primary="Completed"
                          secondary={format(parseISO(task.completed_at), 'MMM d, yyyy')}
                        />
                      </ListItem>
                    )}
                  </List>
                </Paper>

                {/* Progress */}
                {progress && (
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="h6" gutterBottom>
                      Progress
                    </Typography>
                    <Box display="flex" alignItems="center" gap={1} mb={1}>
                      <CheckCircleIcon color="success" />
                      <Typography variant="body2">
                        {progress.completed} of {progress.total} subtasks completed
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={progress.percentage}
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                      {progress.percentage}% complete
                    </Typography>
                  </Paper>
                )}
              </Box>
            </Box>
          </TabPanel>

          {/* Subtasks Tab */}
          <TabPanel value={activeTab} index={1}>
            {task.subtasks && task.subtasks.length > 0 ? (
              <List>
                {task.subtasks.map((subtask, index) => (
                  <ListItem key={index} dense>
                    <ListItemIcon>
                      <Checkbox
                        edge="start"
                        checked={subtask.completed}
                        disabled // Read-only in view mode
                      />
                    </ListItemIcon>
                    <ListItemText
                      primary={subtask.title}
                      sx={{
                        textDecoration: subtask.completed ? 'line-through' : 'none',
                        opacity: subtask.completed ? 0.6 : 1,
                      }}
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Box textAlign="center" py={4}>
                <AssignmentIcon sx={{ fontSize: 48, color: theme.palette.text.disabled, mb: 2 }} />
                <Typography variant="body1" color="text.secondary">
                  No subtasks for this task
                </Typography>
              </Box>
            )}
          </TabPanel>

          {/* Activity Tab */}
          <TabPanel value={activeTab} index={2}>
            <Box mb={3}>
              <TextField
                fullWidth
                multiline
                rows={3}
                placeholder="Add a comment..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                disabled={submittingComment}
              />
              <Box mt={1} display="flex" justifyContent="flex-end">
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleSubmitComment}
                  disabled={!newComment.trim() || submittingComment}
                >
                  {submittingComment ? 'Adding...' : 'Add Comment'}
                </Button>
              </Box>
            </Box>

            {task.comments && task.comments.length > 0 ? (
              <List>
                {task.comments.map((comment) => (
                  <ListItem key={comment.id} alignItems="flex-start">
                    <ListItemAvatar>
                      <Avatar>
                        {getInitials(comment.user_name)}
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="subtitle2">
                            {comment.user_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {formatDistanceToNow(parseISO(comment.created_at), { addSuffix: true })}
                          </Typography>
                        </Box>
                      }
                      secondary={
                        <Typography
                          variant="body2"
                          sx={{ whiteSpace: 'pre-wrap', mt: 0.5 }}
                        >
                          {comment.comment}
                        </Typography>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Box textAlign="center" py={4}>
                <CommentIcon sx={{ fontSize: 48, color: theme.palette.text.disabled, mb: 2 }} />
                <Typography variant="body1" color="text.secondary">
                  No comments yet
                </Typography>
              </Box>
            )}
          </TabPanel>

          {/* Time Tracking Tab */}
          <TabPanel value={activeTab} index={3}>
            <Box display="flex" gap={3}>
              <Card sx={{ flex: 1 }}>
                <CardHeader
                  title="Estimated Time"
                  avatar={<AccessTimeIcon />}
                />
                <CardContent>
                  <Typography variant="h4">
                    {task.estimated_hours ? `${task.estimated_hours}h` : 'Not set'}
                  </Typography>
                </CardContent>
              </Card>

              <Card sx={{ flex: 1 }}>
                <CardHeader
                  title="Actual Time"
                  avatar={<AccessTimeIcon />}
                />
                <CardContent>
                  <Typography variant="h4">
                    {task.actual_hours ? `${task.actual_hours}h` : 'Not tracked'}
                  </Typography>
                </CardContent>
              </Card>

              {task.estimated_hours && task.actual_hours && (
                <Card sx={{ flex: 1 }}>
                  <CardHeader
                    title="Variance"
                    avatar={<TimelineIcon />}
                  />
                  <CardContent>
                    <Typography
                      variant="h4"
                      color={
                        task.actual_hours > task.estimated_hours
                          ? theme.palette.error.main
                          : theme.palette.success.main
                      }
                    >
                      {task.actual_hours > task.estimated_hours ? '+' : ''}
                      {(task.actual_hours - task.estimated_hours).toFixed(1)}h
                    </Typography>
                  </CardContent>
                </Card>
              )}
            </Box>

            {task.estimated_hours && task.actual_hours && (
              <Alert
                severity={task.actual_hours > task.estimated_hours ? 'warning' : 'success'}
                sx={{ mt: 2 }}
              >
                {task.actual_hours > task.estimated_hours
                  ? 'Task took longer than estimated'
                  : 'Task completed within estimated time'}
              </Alert>
            )}
          </TabPanel>
        </Box>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>
          Close
        </Button>
        <Button variant="contained" onClick={onEdit}>
          Edit Task
        </Button>
      </DialogActions>

      {/* Status Change Menu */}
      <Menu
        anchorEl={statusMenuAnchor}
        open={Boolean(statusMenuAnchor)}
        onClose={handleStatusMenuClose}
      >
        {statusOptions.map((status) => (
          <MenuItem
            key={status.value}
            onClick={() => handleStatusChange(status.value as Task['status'])}
            selected={task.status === status.value}
          >
            <ListItemIcon>
              {getStatusIcon(status.value as Task['status'])}
            </ListItemIcon>
            <ListItemText>{status.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </Dialog>
  );
};

export default TaskDetail;