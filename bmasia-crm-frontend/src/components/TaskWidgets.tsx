import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  CardHeader,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Chip,
  IconButton,
  Avatar,
  Tooltip,
  Button,
  Alert,
  CircularProgress,
  useTheme,
  Divider,
  LinearProgress,
  Badge,
} from '@mui/material';
import {
  Assignment as AssignmentIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Schedule as ScheduleIcon,
  TrendingUp as TrendingUpIcon,
  Person as PersonIcon,
  Flag as FlagIcon,
  MoreVert as MoreVertIcon,
  Visibility as VisibilityIcon,
  Today as TodayIcon,
  Group as GroupIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend } from 'recharts';
import { Task } from '../types';
import ApiService from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { format, parseISO, isToday, isTomorrow, isPast, startOfWeek, endOfWeek } from 'date-fns';

interface TaskWidgetsProps {
  onTaskClick?: (task: Task) => void;
}

const TaskWidgets: React.FC<TaskWidgetsProps> = ({ onTaskClick }) => {
  const theme = useTheme();
  const { user } = useAuth();
  const [myTasks, setMyTasks] = useState<Task[]>([]);
  const [overdueTasks, setOverdueTasks] = useState<Task[]>([]);
  const [allTasks, setAllTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTaskData();
  }, []);

  const loadTaskData = async () => {
    try {
      setLoading(true);
      const [myTasksData, overdueTasksData, allTasksData] = await Promise.all([
        ApiService.getMyTasks(),
        ApiService.getOverdueTasks(),
        ApiService.getTasks({ page_size: 100 }), // Get recent tasks for analytics
      ]);

      setMyTasks(myTasksData);
      setOverdueTasks(overdueTasksData);
      setAllTasks(allTasksData.results);
    } catch (err: any) {
      setError('Failed to load task data');
      console.error('Task widget error:', err);
    } finally {
      setLoading(false);
    }
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

  const getStatusColor = (status: Task['status']) => {
    switch (status) {
      case 'To Do': return 'default';
      case 'In Progress': return 'info';
      case 'Done': return 'success';
      case 'Cancelled': return 'error';
      case 'On Hold': return 'warning';
      default: return 'default';
    }
  };

  const getInitials = (name?: string) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase();
  };

  const formatDueDate = (dueDate?: string) => {
    if (!dueDate) return null;

    const date = parseISO(dueDate);
    if (isToday(date)) return 'Today';
    if (isTomorrow(date)) return 'Tomorrow';
    if (isPast(date)) return 'Overdue';
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

  // Analytics data
  const getTasksByStatus = () => {
    const statusCounts = allTasks.reduce((acc, task) => {
      acc[task.status] = (acc[task.status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return Object.entries(statusCounts).map(([status, count]) => {
      const statusColor = getStatusColor(status as Task['status']);
      let color: string;

      switch (statusColor) {
        case 'error': color = theme.palette.error.main; break;
        case 'warning': color = theme.palette.warning.main; break;
        case 'info': color = theme.palette.info.main; break;
        case 'success': color = theme.palette.success.main; break;
        default: color = theme.palette.primary.main; break;
      }

      return {
        name: status,
        value: count,
        color,
      };
    });
  };

  const getTasksByPriority = () => {
    const priorityCounts = allTasks.reduce((acc, task) => {
      acc[task.priority] = (acc[task.priority] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return Object.entries(priorityCounts).map(([priority, count]) => ({
      name: priority,
      value: count,
      color: getPriorityColor(priority as Task['priority']),
    }));
  };

  const getTeamTaskDistribution = () => {
    const userTasks = allTasks.reduce((acc, task) => {
      const assignee = task.assigned_to_name || 'Unassigned';
      acc[assignee] = (acc[assignee] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return Object.entries(userTasks)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 8) // Top 8 users
      .map(([name, count]) => ({
        name: name.length > 12 ? name.substring(0, 12) + '...' : name,
        tasks: count,
      }));
  };

  const getCompletionRate = () => {
    const completed = allTasks.filter(t => t.status === 'Done').length;
    const total = allTasks.length;
    return total > 0 ? Math.round((completed / total) * 100) : 0;
  };

  const getTodayTasks = () => {
    return myTasks.filter(task => {
      if (!task.due_date) return false;
      return isToday(parseISO(task.due_date));
    });
  };

  const getThisWeekTasks = () => {
    const weekStart = startOfWeek(new Date());
    const weekEnd = endOfWeek(new Date());

    return myTasks.filter(task => {
      if (!task.due_date) return false;
      const dueDate = parseISO(task.due_date);
      return dueDate >= weekStart && dueDate <= weekEnd;
    });
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={3}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  const todayTasks = getTodayTasks();
  const thisWeekTasks = getThisWeekTasks();
  const statusData = getTasksByStatus();
  const priorityData = getTasksByPriority();
  const teamData = getTeamTaskDistribution();
  const completionRate = getCompletionRate();

  return (
    <Box>
      {/* Quick Stats Row */}
      <Box display="flex" gap={2} mb={3} flexWrap="wrap">
        <Card sx={{ flex: '1 1 200px', minWidth: 200 }}>
          <CardContent>
            <Box display="flex" alignItems="center" gap={1}>
              <TodayIcon color="primary" />
              <Box>
                <Typography variant="h4">{todayTasks.length}</Typography>
                <Typography variant="body2" color="text.secondary">
                  Due Today
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ flex: '1 1 200px', minWidth: 200 }}>
          <CardContent>
            <Box display="flex" alignItems="center" gap={1}>
              <WarningIcon color="error" />
              <Box>
                <Typography variant="h4" color="error.main">
                  {overdueTasks.length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Overdue
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ flex: '1 1 200px', minWidth: 200 }}>
          <CardContent>
            <Box display="flex" alignItems="center" gap={1}>
              <AssignmentIcon color="info" />
              <Box>
                <Typography variant="h4">{myTasks.length}</Typography>
                <Typography variant="body2" color="text.secondary">
                  My Tasks
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ flex: '1 1 200px', minWidth: 200 }}>
          <CardContent>
            <Box display="flex" alignItems="center" gap={1}>
              <SpeedIcon color="success" />
              <Box>
                <Typography variant="h4" color="success.main">
                  {completionRate}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Completion Rate
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Box>

      {/* Main Content Row */}
      <Box display="flex" gap={3} flexWrap="wrap">
        {/* My Tasks Today */}
        <Card sx={{ flex: '1 1 400px', minWidth: 400 }}>
          <CardHeader
            title="My Tasks Today"
            avatar={<TodayIcon color="primary" />}
            action={
              <Button size="small" href="/tasks">
                View All
              </Button>
            }
          />
          <CardContent sx={{ pt: 0, maxHeight: 400, overflow: 'auto' }}>
            {todayTasks.length > 0 ? (
              <List dense>
                {todayTasks.slice(0, 6).map((task) => (
                  <ListItem
                    key={task.id}
                    component="div"
                    onClick={() => onTaskClick?.(task)}
                    sx={{
                      borderRadius: 1,
                      mb: 1,
                      cursor: 'pointer',
                      '&:hover': {
                        bgcolor: theme.palette.action.hover,
                      },
                    }}
                  >
                    <ListItemIcon>
                      <FlagIcon
                        sx={{ color: getPriorityColor(task.priority), fontSize: 20 }}
                      />
                    </ListItemIcon>
                    <ListItemText
                      primary={task.title}
                      secondary={
                        <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                          <Chip
                            label={task.status}
                            size="small"
                            color={getStatusColor(task.status) as any}
                            variant="outlined"
                          />
                          <Typography variant="caption" color="text.secondary">
                            {task.company_name}
                          </Typography>
                        </Box>
                      }
                      primaryTypographyProps={{
                        sx: {
                          display: '-webkit-box',
                          WebkitLineClamp: 1,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        },
                      }}
                    />
                    <ListItemSecondaryAction>
                      <Avatar
                        sx={{
                          width: 32,
                          height: 32,
                          fontSize: '0.8rem',
                          bgcolor: theme.palette.primary.main,
                        }}
                      >
                        {getInitials(task.assigned_to_name)}
                      </Avatar>
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
            ) : (
              <Box textAlign="center" py={4}>
                <CheckCircleIcon sx={{ fontSize: 48, color: theme.palette.success.main, mb: 1 }} />
                <Typography variant="body1" color="text.secondary">
                  No tasks due today
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Great job staying on top of your schedule!
                </Typography>
              </Box>
            )}
          </CardContent>
        </Card>

        {/* Overdue Tasks Alert */}
        <Card sx={{ flex: '1 1 400px', minWidth: 400 }}>
          <CardHeader
            title="Overdue Tasks"
            avatar={<WarningIcon color="error" />}
            action={
              overdueTasks.length > 0 && (
                <Badge badgeContent={overdueTasks.length} color="error">
                  <Button size="small" color="error" href="/tasks?filter=overdue">
                    View All
                  </Button>
                </Badge>
              )
            }
          />
          <CardContent sx={{ pt: 0, maxHeight: 400, overflow: 'auto' }}>
            {overdueTasks.length > 0 ? (
              <List dense>
                {overdueTasks.slice(0, 6).map((task) => (
                  <ListItem
                    key={task.id}
                    component="div"
                    onClick={() => onTaskClick?.(task)}
                    sx={{
                      borderRadius: 1,
                      mb: 1,
                      cursor: 'pointer',
                      bgcolor: theme.palette.error.light + '20',
                      '&:hover': {
                        bgcolor: theme.palette.error.light + '40',
                      },
                    }}
                  >
                    <ListItemIcon>
                      <WarningIcon color="error" />
                    </ListItemIcon>
                    <ListItemText
                      primary={task.title}
                      secondary={
                        <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                          <Chip
                            label={formatDueDate(task.due_date)}
                            size="small"
                            color="error"
                          />
                          <Typography variant="caption" color="text.secondary">
                            {task.company_name}
                          </Typography>
                        </Box>
                      }
                      primaryTypographyProps={{
                        sx: {
                          display: '-webkit-box',
                          WebkitLineClamp: 1,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        },
                      }}
                    />
                    <ListItemSecondaryAction>
                      <Avatar
                        sx={{
                          width: 32,
                          height: 32,
                          fontSize: '0.8rem',
                          bgcolor: theme.palette.error.main,
                        }}
                      >
                        {getInitials(task.assigned_to_name)}
                      </Avatar>
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
            ) : (
              <Box textAlign="center" py={4}>
                <CheckCircleIcon sx={{ fontSize: 48, color: theme.palette.success.main, mb: 1 }} />
                <Typography variant="body1" color="text.secondary">
                  No overdue tasks
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  All tasks are on track!
                </Typography>
              </Box>
            )}
          </CardContent>
        </Card>
      </Box>

      {/* Analytics Row */}
      <Box display="flex" gap={3} mt={3} flexWrap="wrap">
        {/* Task Status Distribution */}
        <Card sx={{ flex: '1 1 300px', minWidth: 300 }}>
          <CardHeader
            title="Task Status Distribution"
            avatar={<TrendingUpIcon />}
          />
          <CardContent sx={{ pt: 0 }}>
            {statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, value, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {statusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Box textAlign="center" py={4}>
                <Typography variant="body2" color="text.secondary">
                  No task data available
                </Typography>
              </Box>
            )}
          </CardContent>
        </Card>

        {/* Team Task Distribution */}
        <Card sx={{ flex: '1 1 400px', minWidth: 400 }}>
          <CardHeader
            title="Team Task Distribution"
            avatar={<GroupIcon />}
          />
          <CardContent sx={{ pt: 0 }}>
            {teamData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={teamData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="name"
                    angle={-45}
                    textAnchor="end"
                    height={80}
                    fontSize={12}
                  />
                  <YAxis />
                  <RechartsTooltip />
                  <Bar dataKey="tasks" fill={theme.palette.primary.main} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Box textAlign="center" py={4}>
                <Typography variant="body2" color="text.secondary">
                  No team task data available
                </Typography>
              </Box>
            )}
          </CardContent>
        </Card>

        {/* Task Completion Progress */}
        <Card sx={{ flex: '1 1 300px', minWidth: 300 }}>
          <CardHeader
            title="Overall Progress"
            avatar={<SpeedIcon />}
          />
          <CardContent sx={{ pt: 0 }}>
            <Box textAlign="center" py={2}>
              <Typography variant="h3" color="primary" gutterBottom>
                {completionRate}%
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Tasks Completed
              </Typography>
              <LinearProgress
                variant="determinate"
                value={completionRate}
                sx={{ height: 8, borderRadius: 4, mb: 2 }}
              />
              <Typography variant="body2" color="text.secondary">
                {allTasks.filter(t => t.status === 'Done').length} of {allTasks.length} tasks complete
              </Typography>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Priority Breakdown
              </Typography>
              {priorityData.map((item) => (
                <Box key={item.name} display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <Box
                      width={12}
                      height={12}
                      borderRadius="50%"
                      bgcolor={item.color}
                    />
                    <Typography variant="body2">{item.name}</Typography>
                  </Box>
                  <Typography variant="body2" fontWeight="bold">
                    {item.value}
                  </Typography>
                </Box>
              ))}
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};

export default TaskWidgets;