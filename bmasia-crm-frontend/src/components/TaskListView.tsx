import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  TableSortLabel,
  Paper,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Avatar,
  Tooltip,
  Box,
  Typography,
  LinearProgress,
  useTheme,
  Checkbox,
  Button,
} from '@mui/material';
import {
  MoreVert,
  Edit,
  Delete,
  Visibility,
  Flag,
  Person,
  Business,
  Schedule,
  CheckCircle,
  Link as LinkIcon,
  Assignment,
} from '@mui/icons-material';
import { Task } from '../types';
import { format, isToday, isTomorrow, isPast, parseISO } from 'date-fns';

interface TaskListViewProps {
  tasks: Task[];
  onTaskClick: (task: Task) => void;
  onTaskEdit: (task: Task) => void;
  onTaskDelete: (taskId: string) => void;
  loading?: boolean;
}

type Order = 'asc' | 'desc';
type OrderBy = keyof Task;

interface HeadCell {
  id: OrderBy;
  label: string;
  numeric: boolean;
  sortable: boolean;
  width?: number;
}

const headCells: HeadCell[] = [
  { id: 'title', label: 'Task', numeric: false, sortable: true },
  { id: 'company_name', label: 'Company', numeric: false, sortable: true, width: 150 },
  { id: 'assigned_to_name', label: 'Assignee', numeric: false, sortable: true, width: 120 },
  { id: 'priority', label: 'Priority', numeric: false, sortable: true, width: 100 },
  { id: 'status', label: 'Status', numeric: false, sortable: true, width: 120 },
  { id: 'due_date', label: 'Due Date', numeric: false, sortable: true, width: 120 },
  { id: 'created_at', label: 'Created', numeric: false, sortable: true, width: 120 },
];

function descendingComparator(a: Task, b: Task, orderBy: OrderBy) {
  const aVal = a[orderBy];
  const bVal = b[orderBy];

  // Handle undefined values
  if (bVal == null && aVal == null) return 0;
  if (bVal == null) return -1;
  if (aVal == null) return 1;

  if (bVal < aVal) {
    return -1;
  }
  if (bVal > aVal) {
    return 1;
  }
  return 0;
}

function getComparator(
  order: Order,
  orderBy: OrderBy,
): (a: Task, b: Task) => number {
  return order === 'desc'
    ? (a, b) => descendingComparator(a, b, orderBy)
    : (a, b) => -descendingComparator(a, b, orderBy);
}

const TaskListView: React.FC<TaskListViewProps> = ({
  tasks,
  onTaskClick,
  onTaskEdit,
  onTaskDelete,
  loading,
}) => {
  const theme = useTheme();
  const [order, setOrder] = useState<Order>('desc');
  const [orderBy, setOrderBy] = useState<OrderBy>('created_at');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [selectedTasks, setSelectedTasks] = useState<Set<string>>(new Set());

  const handleRequestSort = (property: OrderBy) => {
    const isAsc = orderBy === property && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(property);
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, task: Task) => {
    event.stopPropagation();
    setSelectedTask(task);
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedTask(null);
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleSelectTask = (taskId: string) => {
    const newSelected = new Set(selectedTasks);
    if (newSelected.has(taskId)) {
      newSelected.delete(taskId);
    } else {
      newSelected.add(taskId);
    }
    setSelectedTasks(newSelected);
  };

  const handleSelectAllTasks = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const newSelected = new Set(visibleTasks.map(task => task.id));
      setSelectedTasks(newSelected);
    } else {
      setSelectedTasks(new Set());
    }
  };

  const getPriorityColor = (priority: Task['priority']) => {
    switch (priority) {
      case 'Urgent': return 'error';
      case 'High': return 'warning';
      case 'Medium': return 'info';
      case 'Low': return 'success';
      default: return 'default';
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

  const formatDueDate = (dueDate?: string) => {
    if (!dueDate) return '-';

    const date = parseISO(dueDate);
    if (isToday(date)) return 'Today';
    if (isTomorrow(date)) return 'Tomorrow';
    if (isPast(date)) return `${format(date, 'MMM d')} (Overdue)`;
    return format(date, 'MMM d, yyyy');
  };

  const getDueDateColor = (dueDate?: string) => {
    if (!dueDate) return 'default';

    const date = parseISO(dueDate);
    if (isPast(date)) return theme.palette.error.main;
    if (isToday(date)) return theme.palette.warning.main;
    if (isTomorrow(date)) return theme.palette.info.main;
    return theme.palette.text.secondary;
  };

  const getInitials = (name?: string) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase();
  };

  const getSubtaskProgress = (task: Task) => {
    if (!task.subtasks || task.subtasks.length === 0) return null;

    const completed = task.subtasks.filter(s => s.completed).length;
    const total = task.subtasks.length;
    const percentage = Math.round((completed / total) * 100);

    return { completed, total, percentage };
  };

  // Sort and paginate tasks
  const sortedTasks = React.useMemo(
    () => tasks.slice().sort(getComparator(order, orderBy)),
    [order, orderBy, tasks]
  );

  const visibleTasks = React.useMemo(
    () => sortedTasks.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
    [sortedTasks, page, rowsPerPage]
  );

  const isSelected = (id: string) => selectedTasks.has(id);
  const numSelected = selectedTasks.size;

  return (
    <Paper sx={{ width: '100%' }}>
      {/* Bulk Actions */}
      {numSelected > 0 && (
        <Box
          sx={{
            pl: { sm: 2 },
            pr: { xs: 1, sm: 1 },
            py: 1,
            bgcolor: theme.palette.primary.light + '20',
          }}
        >
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="subtitle1" component="div">
              {numSelected} selected
            </Typography>
            <Box>
              <Button size="small" sx={{ mr: 1 }}>
                Bulk Edit
              </Button>
              <Button size="small" color="error">
                Bulk Delete
              </Button>
            </Box>
          </Box>
        </Box>
      )}

      <TableContainer>
        <Table sx={{ minWidth: 750 }} aria-labelledby="taskTable" size="medium">
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  color="primary"
                  indeterminate={numSelected > 0 && numSelected < visibleTasks.length}
                  checked={visibleTasks.length > 0 && numSelected === visibleTasks.length}
                  onChange={handleSelectAllTasks}
                  inputProps={{
                    'aria-label': 'select all tasks',
                  }}
                />
              </TableCell>
              {headCells.map((headCell) => (
                <TableCell
                  key={headCell.id}
                  align={headCell.numeric ? 'right' : 'left'}
                  sortDirection={orderBy === headCell.id ? order : false}
                  sx={{ width: headCell.width }}
                >
                  {headCell.sortable ? (
                    <TableSortLabel
                      active={orderBy === headCell.id}
                      direction={orderBy === headCell.id ? order : 'asc'}
                      onClick={() => handleRequestSort(headCell.id)}
                    >
                      {headCell.label}
                    </TableSortLabel>
                  ) : (
                    headCell.label
                  )}
                </TableCell>
              ))}
              <TableCell width={80}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading && (
              <TableRow>
                <TableCell colSpan={headCells.length + 2}>
                  <LinearProgress />
                </TableCell>
              </TableRow>
            )}
            {visibleTasks.map((task) => {
              const isItemSelected = isSelected(task.id);
              const progress = getSubtaskProgress(task);

              return (
                <TableRow
                  hover
                  onClick={() => onTaskClick(task)}
                  role="checkbox"
                  aria-checked={isItemSelected}
                  tabIndex={-1}
                  key={task.id}
                  selected={isItemSelected}
                  sx={{
                    cursor: 'pointer',
                    '&:hover': {
                      bgcolor: theme.palette.action.hover,
                    },
                  }}
                >
                  <TableCell padding="checkbox">
                    <Checkbox
                      color="primary"
                      checked={isItemSelected}
                      onChange={() => handleSelectTask(task.id)}
                      onClick={(e) => e.stopPropagation()}
                      inputProps={{
                        'aria-labelledby': `task-${task.id}`,
                      }}
                    />
                  </TableCell>

                  {/* Title */}
                  <TableCell>
                    <Box>
                      <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                        <Flag
                          sx={{
                            fontSize: 16,
                            color: getPriorityColor(task.priority) === 'default'
                              ? theme.palette.grey[400]
                              : theme.palette[getPriorityColor(task.priority) as 'error' | 'warning' | 'info' | 'success'].main,
                          }}
                        />
                        <Typography
                          variant="body2"
                          fontWeight="medium"
                          sx={{
                            display: '-webkit-box',
                            WebkitLineClamp: 1,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                          }}
                        >
                          {task.title}
                        </Typography>
                        {task.task_type && (
                          <Chip
                            label={task.task_type}
                            size="small"
                            sx={{ fontSize: '0.7rem', height: 20 }}
                          />
                        )}
                      </Box>

                      {/* Related entities */}
                      {(task.related_opportunity_name || task.related_contract_number || task.related_contact_name) && (
                        <Box display="flex" alignItems="center" gap={0.5}>
                          <LinkIcon sx={{ fontSize: 12, color: theme.palette.text.secondary }} />
                          <Typography variant="caption" color="text.secondary">
                            {task.related_opportunity_name || task.related_contract_number || task.related_contact_name}
                          </Typography>
                        </Box>
                      )}

                      {/* Subtask progress */}
                      {progress && (
                        <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                          <Assignment sx={{ fontSize: 12, color: theme.palette.text.secondary }} />
                          <Typography variant="caption" color="text.secondary">
                            {progress.completed}/{progress.total} subtasks
                          </Typography>
                          <LinearProgress
                            variant="determinate"
                            value={progress.percentage}
                            sx={{ width: 60, height: 4 }}
                          />
                        </Box>
                      )}
                    </Box>
                  </TableCell>

                  {/* Company */}
                  <TableCell>
                    <Box display="flex" alignItems="center" gap={0.5}>
                      <Business sx={{ fontSize: 16, color: theme.palette.text.secondary }} />
                      <Typography variant="body2" noWrap>
                        {task.company_name}
                      </Typography>
                    </Box>
                  </TableCell>

                  {/* Assignee */}
                  <TableCell>
                    <Box display="flex" alignItems="center" gap={1}>
                      <Tooltip title={task.assigned_to_name || 'Unassigned'}>
                        <Avatar
                          sx={{
                            width: 32,
                            height: 32,
                            fontSize: '0.8rem',
                            bgcolor: task.assigned_to ? theme.palette.primary.main : theme.palette.grey[400],
                          }}
                        >
                          {getInitials(task.assigned_to_name)}
                        </Avatar>
                      </Tooltip>
                      <Typography variant="body2" noWrap>
                        {task.assigned_to_name || 'Unassigned'}
                      </Typography>
                    </Box>
                  </TableCell>

                  {/* Priority */}
                  <TableCell>
                    <Chip
                      label={task.priority}
                      size="small"
                      color={getPriorityColor(task.priority) as any}
                      variant={task.priority === 'Urgent' ? 'filled' : 'outlined'}
                    />
                  </TableCell>

                  {/* Status */}
                  <TableCell>
                    <Chip
                      label={task.status}
                      size="small"
                      color={getStatusColor(task.status) as any}
                      variant="outlined"
                    />
                  </TableCell>

                  {/* Due Date */}
                  <TableCell>
                    <Box display="flex" alignItems="center" gap={0.5}>
                      <Schedule
                        sx={{
                          fontSize: 16,
                          color: getDueDateColor(task.due_date),
                        }}
                      />
                      <Typography
                        variant="body2"
                        sx={{ color: getDueDateColor(task.due_date) }}
                      >
                        {formatDueDate(task.due_date)}
                      </Typography>
                    </Box>
                  </TableCell>

                  {/* Created */}
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {format(parseISO(task.created_at), 'MMM d')}
                    </Typography>
                  </TableCell>

                  {/* Actions */}
                  <TableCell>
                    <IconButton
                      size="small"
                      onClick={(e) => handleMenuClick(e, task)}
                    >
                      <MoreVert />
                    </IconButton>
                  </TableCell>
                </TableRow>
              );
            })}

            {visibleTasks.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={headCells.length + 2} align="center">
                  <Box py={3}>
                    <Typography variant="body1" color="text.secondary">
                      No tasks found
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        rowsPerPageOptions={[10, 25, 50, 100]}
        component="div"
        count={tasks.length}
        rowsPerPage={rowsPerPage}
        page={page}
        onPageChange={handleChangePage}
        onRowsPerPageChange={handleChangeRowsPerPage}
      />

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
            if (selectedTask) {
              onTaskClick(selectedTask);
            }
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
            if (selectedTask) {
              onTaskEdit(selectedTask);
            }
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
            if (selectedTask) {
              onTaskDelete(selectedTask.id);
            }
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
    </Paper>
  );
};

export default TaskListView;