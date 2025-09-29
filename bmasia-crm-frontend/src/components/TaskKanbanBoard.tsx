import React, { useState } from 'react';
import { DragDropContext, Droppable, Draggable, DropResult } from 'react-beautiful-dnd';
import {
  Box,
  Paper,
  Typography,
  Chip,
  IconButton,
  Avatar,
  Tooltip,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  useTheme,
  Badge,
  Card,
  CardContent,
  CardActions,
  Button,
} from '@mui/material';
import {
  MoreVert,
  Edit,
  Delete,
  Visibility,
  Person,
  Schedule,
  Flag,
  Business,
  Link as LinkIcon,
  CheckCircle,
  RadioButtonUnchecked,
  PlayArrow,
  Pause,
  RateReview,
} from '@mui/icons-material';
import { Task } from '../types';
import { format, isToday, isTomorrow, isPast, parseISO } from 'date-fns';

interface TaskKanbanBoardProps {
  tasks: Task[];
  onTaskClick: (task: Task) => void;
  onTaskEdit: (task: Task) => void;
  onTaskDelete: (taskId: string) => void;
  onTaskStatusChange: (taskId: string, newStatus: Task['status']) => void;
  loading?: boolean;
}

interface KanbanColumn {
  id: Task['status'];
  title: string;
  color: string;
  icon: React.ReactElement;
  limit?: number;
}

const columns: KanbanColumn[] = [
  {
    id: 'To Do',
    title: 'To Do',
    color: '#e3f2fd',
    icon: <RadioButtonUnchecked />,
  },
  {
    id: 'In Progress',
    title: 'In Progress',
    color: '#fff3e0',
    icon: <PlayArrow />,
    limit: 5, // WIP limit
  },
  {
    id: 'Review',
    title: 'Review',
    color: '#f3e5f5',
    icon: <RateReview />,
    limit: 3,
  },
  {
    id: 'Done',
    title: 'Done',
    color: '#e8f5e8',
    icon: <CheckCircle />,
  },
];

const TaskCard: React.FC<{
  task: Task;
  index: number;
  onTaskClick: (task: Task) => void;
  onTaskEdit: (task: Task) => void;
  onTaskDelete: (taskId: string) => void;
}> = ({ task, index, onTaskClick, onTaskEdit, onTaskDelete }) => {
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const getPriorityColor = (priority: Task['priority']) => {
    switch (priority) {
      case 'Urgent': return theme.palette.error.main;
      case 'High': return theme.palette.warning.main;
      case 'Medium': return theme.palette.info.main;
      case 'Low': return theme.palette.success.main;
      default: return theme.palette.grey[400];
    }
  };

  const formatDueDate = (dueDate?: string) => {
    if (!dueDate) return null;

    const date = parseISO(dueDate);
    if (isToday(date)) return 'Today';
    if (isTomorrow(date)) return 'Tomorrow';
    if (isPast(date)) return `Overdue`;
    return format(date, 'MMM d');
  };

  const getDueDateColor = (dueDate?: string) => {
    if (!dueDate) return 'default';

    const date = parseISO(dueDate);
    if (isPast(date)) return 'error';
    if (isToday(date)) return 'warning';
    if (isTomorrow(date)) return 'info';
    return 'default';
  };

  const getInitials = (name?: string) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase();
  };

  const completedSubtasks = task.subtasks?.filter(s => s.completed).length || 0;
  const totalSubtasks = task.subtasks?.length || 0;

  return (
    <Draggable draggableId={task.id} index={index}>
      {(provided, snapshot) => (
        <Card
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          onClick={() => onTaskClick(task)}
          sx={{
            mb: 1,
            cursor: 'pointer',
            transform: snapshot.isDragging ? 'rotate(5deg)' : 'none',
            boxShadow: snapshot.isDragging ? theme.shadows[8] : theme.shadows[1],
            '&:hover': {
              boxShadow: theme.shadows[4],
            },
            transition: 'all 0.2s ease-in-out',
          }}
        >
          <CardContent sx={{ pb: 1 }}>
            {/* Header */}
            <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
              <Box display="flex" alignItems="center" gap={0.5}>
                <Flag
                  sx={{
                    fontSize: 16,
                    color: getPriorityColor(task.priority),
                  }}
                />
                {task.task_type && (
                  <Chip
                    label={task.task_type}
                    size="small"
                    sx={{ fontSize: '0.7rem', height: 20 }}
                  />
                )}
              </Box>
              <IconButton
                size="small"
                onClick={handleMenuClick}
                sx={{ p: 0.5 }}
              >
                <MoreVert fontSize="small" />
              </IconButton>
            </Box>

            {/* Title */}
            <Typography
              variant="body2"
              fontWeight="medium"
              gutterBottom
              sx={{
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {task.title}
            </Typography>

            {/* Company */}
            <Box display="flex" alignItems="center" gap={0.5} mb={1}>
              <Business sx={{ fontSize: 14, color: theme.palette.text.secondary }} />
              <Typography variant="caption" color="text.secondary">
                {task.company_name}
              </Typography>
            </Box>

            {/* Related entities */}
            {(task.related_opportunity_name || task.related_contract_number || task.related_contact_name) && (
              <Box display="flex" alignItems="center" gap={0.5} mb={1}>
                <LinkIcon sx={{ fontSize: 14, color: theme.palette.text.secondary }} />
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                  {task.related_opportunity_name || task.related_contract_number || task.related_contact_name}
                </Typography>
              </Box>
            )}

            {/* Progress indicator for subtasks */}
            {totalSubtasks > 0 && (
              <Box display="flex" alignItems="center" gap={0.5} mb={1}>
                <CheckCircle sx={{ fontSize: 14, color: theme.palette.success.main }} />
                <Typography variant="caption" color="text.secondary">
                  {completedSubtasks}/{totalSubtasks} subtasks
                </Typography>
              </Box>
            )}

            {/* Tags */}
            {task.tags && (
              <Box mb={1}>
                {task.tags.split(',').slice(0, 2).map((tag, index) => (
                  <Chip
                    key={index}
                    label={tag.trim()}
                    size="small"
                    variant="outlined"
                    sx={{ mr: 0.5, fontSize: '0.7rem', height: 18 }}
                  />
                ))}
                {task.tags.split(',').length > 2 && (
                  <Chip
                    label={`+${task.tags.split(',').length - 2}`}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: '0.7rem', height: 18 }}
                  />
                )}
              </Box>
            )}
          </CardContent>

          <CardActions sx={{ pt: 0, px: 2, pb: 2 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" width="100%">
              {/* Due date */}
              {task.due_date && (
                <Chip
                  label={formatDueDate(task.due_date)}
                  size="small"
                  color={getDueDateColor(task.due_date) as any}
                  icon={<Schedule sx={{ fontSize: 12 }} />}
                  sx={{ fontSize: '0.7rem', height: 22 }}
                />
              )}

              {/* Assignee */}
              <Box ml="auto">
                <Tooltip title={task.assigned_to_name || 'Unassigned'}>
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
                </Tooltip>
              </Box>
            </Box>
          </CardActions>

          {/* Action Menu */}
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            onClick={(e) => e.stopPropagation()}
          >
            <MenuItem
              onClick={(e) => {
                e.stopPropagation();
                onTaskClick(task);
                handleMenuClose();
              }}
            >
              <ListItemIcon>
                <Visibility fontSize="small" />
              </ListItemIcon>
              <ListItemText>View Details</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={(e) => {
                e.stopPropagation();
                onTaskEdit(task);
                handleMenuClose();
              }}
            >
              <ListItemIcon>
                <Edit fontSize="small" />
              </ListItemIcon>
              <ListItemText>Edit Task</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={(e) => {
                e.stopPropagation();
                onTaskDelete(task.id);
                handleMenuClose();
              }}
              sx={{ color: theme.palette.error.main }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}>
                <Delete fontSize="small" />
              </ListItemIcon>
              <ListItemText>Delete Task</ListItemText>
            </MenuItem>
          </Menu>
        </Card>
      )}
    </Draggable>
  );
};

const KanbanColumn: React.FC<{
  column: KanbanColumn;
  tasks: Task[];
  onTaskClick: (task: Task) => void;
  onTaskEdit: (task: Task) => void;
  onTaskDelete: (taskId: string) => void;
}> = ({ column, tasks, onTaskClick, onTaskEdit, onTaskDelete }) => {
  const theme = useTheme();
  const isOverLimit = column.limit && tasks.length > column.limit;

  return (
    <Box sx={{ minWidth: 280, mx: 1 }}>
      <Paper
        sx={{
          p: 1,
          mb: 1,
          bgcolor: column.color,
          borderLeft: `4px solid ${theme.palette.primary.main}`,
        }}
      >
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center" gap={1}>
            {column.icon}
            <Typography variant="subtitle2" fontWeight="bold">
              {column.title}
            </Typography>
            <Badge
              badgeContent={tasks.length}
              color={isOverLimit ? 'error' : 'primary'}
              max={99}
            />
          </Box>
          {column.limit && (
            <Typography variant="caption" color="text.secondary">
              Limit: {column.limit}
            </Typography>
          )}
        </Box>
      </Paper>

      <Droppable droppableId={column.id}>
        {(provided, snapshot) => (
          <Box
            ref={provided.innerRef}
            {...provided.droppableProps}
            sx={{
              minHeight: '60vh',
              p: 1,
              borderRadius: 1,
              bgcolor: snapshot.isDraggingOver ? theme.palette.action.hover : 'transparent',
              transition: 'background-color 0.2s ease',
            }}
          >
            {tasks.map((task, index) => (
              <TaskCard
                key={task.id}
                task={task}
                index={index}
                onTaskClick={onTaskClick}
                onTaskEdit={onTaskEdit}
                onTaskDelete={onTaskDelete}
              />
            ))}
            {provided.placeholder}

            {tasks.length === 0 && (
              <Box
                sx={{
                  p: 3,
                  textAlign: 'center',
                  color: theme.palette.text.secondary,
                  border: `2px dashed ${theme.palette.divider}`,
                  borderRadius: 1,
                }}
              >
                <Typography variant="body2">
                  Drop tasks here
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </Droppable>
    </Box>
  );
};

const TaskKanbanBoard: React.FC<TaskKanbanBoardProps> = ({
  tasks,
  onTaskClick,
  onTaskEdit,
  onTaskDelete,
  onTaskStatusChange,
  loading,
}) => {
  const theme = useTheme();

  const handleDragEnd = (result: DropResult) => {
    if (!result.destination) return;

    const { draggableId, destination } = result;
    const newStatus = destination.droppableId as Task['status'];

    // Find the task
    const task = tasks.find(t => t.id === draggableId);
    if (task && task.status !== newStatus) {
      onTaskStatusChange(draggableId, newStatus);
    }
  };

  const getTasksByStatus = (status: Task['status']) => {
    return tasks.filter(task => task.status === status);
  };

  return (
    <Box sx={{ position: 'relative' }}>
      <DragDropContext onDragEnd={handleDragEnd}>
        <Box
          sx={{
            display: 'flex',
            overflowX: 'auto',
            pb: 2,
            minHeight: '70vh',
            '&::-webkit-scrollbar': {
              height: 8,
            },
            '&::-webkit-scrollbar-track': {
              bgcolor: theme.palette.background.default,
            },
            '&::-webkit-scrollbar-thumb': {
              bgcolor: theme.palette.divider,
              borderRadius: 4,
              '&:hover': {
                bgcolor: theme.palette.text.secondary,
              },
            },
          }}
        >
          {columns.map((column) => (
            <KanbanColumn
              key={column.id}
              column={column}
              tasks={getTasksByStatus(column.id)}
              onTaskClick={onTaskClick}
              onTaskEdit={onTaskEdit}
              onTaskDelete={onTaskDelete}
            />
          ))}
        </Box>
      </DragDropContext>

      {/* Quick stats */}
      <Box
        sx={{
          position: 'absolute',
          bottom: -50,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
          gap: 2,
          pt: 2,
        }}
      >
        <Typography variant="caption" color="text.secondary">
          Total: {tasks.length} tasks
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Overdue: {tasks.filter(t => t.is_overdue).length}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Completed: {getTasksByStatus('Done').length}
        </Typography>
      </Box>
    </Box>
  );
};

export default TaskKanbanBoard;