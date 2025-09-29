import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  Paper,
  IconButton,
  InputAdornment,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  GridLegacy as Grid,
  Tabs,
  Tab,
  Chip,
  useTheme,
  useMediaQuery,
  Fab,
  Badge,
  Snackbar,
} from '@mui/material';
import {
  Add,
  Search,
  FilterList,
  ViewKanban,
  TableView,
  Refresh,
  Close,
} from '@mui/icons-material';
import { Task, User, Company, Opportunity, Contract, Contact } from '../types';
import ApiService from '../services/api';
import TaskKanbanBoard from '../components/TaskKanbanBoard';
import TaskListView from '../components/TaskListView';
import TaskForm from '../components/TaskForm';
import TaskDetail from '../components/TaskDetail';
import LoadingSkeleton from '../components/LoadingSkeleton';

interface TaskFilters {
  assignee?: string;
  priority?: string;
  status?: string;
  task_type?: string;
  due_date_range?: 'today' | 'this_week' | 'this_month' | 'overdue';
  related_entity?: string;
}

const Tasks: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const [tasks, setTasks] = useState<Task[]>([]);
  const [filteredTasks, setFilteredTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<TaskFilters>({});
  const [showFilters, setShowFilters] = useState(false);

  // UI State
  const [viewMode, setViewMode] = useState<'kanban' | 'list'>('kanban');
  const [taskFormOpen, setTaskFormOpen] = useState(false);
  const [taskDetailOpen, setTaskDetailOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');

  // Notifications
  const [notification, setNotification] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'warning' | 'info';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const showNotification = (message: string, severity: 'success' | 'error' | 'warning' | 'info' = 'success') => {
    setNotification({ open: true, message, severity });
  };

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await ApiService.getTasks();
      setTasks(response.results);
      setFilteredTasks(response.results);
    } catch (error: any) {
      console.error('Error fetching tasks:', error);
      setError('Failed to load tasks');
      showNotification('Failed to load tasks', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSupportingData = useCallback(async () => {
    try {
      const [usersRes, companiesRes, opportunitiesRes, contractsRes, contactsRes] = await Promise.all([
        ApiService.getUsers(),
        ApiService.getCompanies({ page_size: 1000 }),
        ApiService.getOpportunities({ page_size: 1000 }),
        ApiService.getContracts({ page_size: 1000 }),
        ApiService.getContacts({ page_size: 1000 }),
      ]);

      setUsers(usersRes.results);
      setCompanies(companiesRes.results);
      setOpportunities(opportunitiesRes.results);
      setContracts(contractsRes.results);
      setContacts(contactsRes.results);
    } catch (error: any) {
      console.error('Error fetching supporting data:', error);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
    fetchSupportingData();
  }, [fetchTasks, fetchSupportingData]);

  useEffect(() => {
    applyFilters();
  }, [searchQuery, filters, tasks]);

  const applyFilters = () => {
    let filtered = tasks.filter(task => {
      // Search query filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        if (!task.title.toLowerCase().includes(query) &&
            !task.description.toLowerCase().includes(query) &&
            !task.company_name.toLowerCase().includes(query) &&
            !task.assigned_to_name?.toLowerCase().includes(query)) {
          return false;
        }
      }

      // Assignee filter
      if (filters.assignee && task.assigned_to !== filters.assignee) {
        return false;
      }

      // Priority filter
      if (filters.priority && task.priority !== filters.priority) {
        return false;
      }

      // Status filter
      if (filters.status && task.status !== filters.status) {
        return false;
      }

      // Task type filter
      if (filters.task_type && task.task_type !== filters.task_type) {
        return false;
      }

      // Due date range filter
      if (filters.due_date_range && task.due_date) {
        const dueDate = new Date(task.due_date);
        const now = new Date();

        switch (filters.due_date_range) {
          case 'today':
            if (dueDate.toDateString() !== now.toDateString()) {
              return false;
            }
            break;
          case 'this_week':
            const weekStart = new Date(now.setDate(now.getDate() - now.getDay()));
            const weekEnd = new Date(now.setDate(weekStart.getDate() + 6));
            if (dueDate < weekStart || dueDate > weekEnd) {
              return false;
            }
            break;
          case 'this_month':
            if (dueDate.getMonth() !== now.getMonth() || dueDate.getFullYear() !== now.getFullYear()) {
              return false;
            }
            break;
          case 'overdue':
            if (!task.is_overdue) {
              return false;
            }
            break;
        }
      }

      return true;
    });

    setFilteredTasks(filtered);
  };

  const handleCreateTask = () => {
    setSelectedTask(null);
    setFormMode('create');
    setTaskFormOpen(true);
  };

  const handleEditTask = (task: Task) => {
    setSelectedTask(task);
    setFormMode('edit');
    setTaskFormOpen(true);
  };

  const handleViewTask = (task: Task) => {
    setSelectedTask(task);
    setTaskDetailOpen(true);
  };

  const handleTaskSave = async (taskData: Partial<Task>) => {
    try {
      if (formMode === 'create') {
        const newTask = await ApiService.createTask(taskData);
        setTasks(prev => [newTask, ...prev]);
        showNotification('Task created successfully');
      } else if (selectedTask) {
        const updatedTask = await ApiService.updateTask(selectedTask.id, taskData);
        setTasks(prev => prev.map(t => t.id === updatedTask.id ? updatedTask : t));
        showNotification('Task updated successfully');
      }
      setTaskFormOpen(false);
    } catch (error: any) {
      console.error('Error saving task:', error);
      showNotification('Failed to save task', 'error');
    }
  };

  const handleTaskDelete = async (taskId: string) => {
    try {
      await ApiService.deleteTask(taskId);
      setTasks(prev => prev.filter(t => t.id !== taskId));
      showNotification('Task deleted successfully');
    } catch (error: any) {
      console.error('Error deleting task:', error);
      showNotification('Failed to delete task', 'error');
    }
  };

  const handleTaskStatusChange = async (taskId: string, newStatus: Task['status']) => {
    try {
      const updatedTask = await ApiService.updateTask(taskId, { status: newStatus });
      setTasks(prev => prev.map(t => t.id === updatedTask.id ? updatedTask : t));
      showNotification('Task status updated');
    } catch (error: any) {
      console.error('Error updating task status:', error);
      showNotification('Failed to update task status', 'error');
    }
  };

  const clearFilters = () => {
    setFilters({});
    setSearchQuery('');
  };

  const getFilterCount = () => {
    return Object.values(filters).filter(Boolean).length + (searchQuery ? 1 : 0);
  };

  const getOverdueCount = () => {
    return tasks.filter(t => t.is_overdue).length;
  };

  const getMyTasksCount = () => {
    // This would need the current user context
    return tasks.filter(t => t.status !== 'Done' && t.status !== 'Cancelled').length;
  };

  if (loading && tasks.length === 0) {
    return <LoadingSkeleton />;
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Task Management
          </Typography>
          <Box display="flex" gap={2} alignItems="center">
            <Chip
              label={`${filteredTasks.length} Tasks`}
              color="primary"
              variant="outlined"
            />
            {getOverdueCount() > 0 && (
              <Chip
                label={`${getOverdueCount()} Overdue`}
                color="error"
              />
            )}
            <Chip
              label={`${getMyTasksCount()} Active`}
              color="success"
              variant="outlined"
            />
          </Box>
        </Box>

        <Box display="flex" gap={1} alignItems="center">
          <IconButton onClick={fetchTasks} disabled={loading}>
            <Refresh />
          </IconButton>

          <IconButton
            onClick={() => setShowFilters(!showFilters)}
            color={getFilterCount() > 0 ? 'primary' : 'default'}
          >
            <Badge badgeContent={getFilterCount()} color="error">
              <FilterList />
            </Badge>
          </IconButton>

          <Tabs
            value={viewMode}
            onChange={(_, value) => setViewMode(value)}
            sx={{ minHeight: 32 }}
          >
            <Tab
              value="kanban"
              icon={<ViewKanban />}
              label={!isMobile ? "Board" : undefined}
              sx={{ minHeight: 32, py: 0.5 }}
            />
            <Tab
              value="list"
              icon={<TableView />}
              label={!isMobile ? "List" : undefined}
              sx={{ minHeight: 32, py: 0.5 }}
            />
          </Tabs>

          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleCreateTask}
            size={isMobile ? "small" : "medium"}
          >
            {isMobile ? "Add" : "Create Task"}
          </Button>
        </Box>
      </Box>

      {/* Filters */}
      {showFilters && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search tasks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Search />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>

            <Grid item xs={12} sm={6} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Assignee</InputLabel>
                <Select
                  value={filters.assignee || ''}
                  label="Assignee"
                  onChange={(e) => setFilters(prev => ({ ...prev, assignee: e.target.value }))}
                >
                  <MenuItem value="">All</MenuItem>
                  {users.map((user) => (
                    <MenuItem key={user.id} value={user.id}>
                      {user.first_name} {user.last_name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Priority</InputLabel>
                <Select
                  value={filters.priority || ''}
                  label="Priority"
                  onChange={(e) => setFilters(prev => ({ ...prev, priority: e.target.value }))}
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="Low">Low</MenuItem>
                  <MenuItem value="Medium">Medium</MenuItem>
                  <MenuItem value="High">High</MenuItem>
                  <MenuItem value="Urgent">Urgent</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Status</InputLabel>
                <Select
                  value={filters.status || ''}
                  label="Status"
                  onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="To Do">To Do</MenuItem>
                  <MenuItem value="In Progress">In Progress</MenuItem>
                  <MenuItem value="Review">Review</MenuItem>
                  <MenuItem value="Done">Done</MenuItem>
                  <MenuItem value="On Hold">On Hold</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Due Date</InputLabel>
                <Select
                  value={filters.due_date_range || ''}
                  label="Due Date"
                  onChange={(e) => setFilters(prev => ({ ...prev, due_date_range: e.target.value as any }))}
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="today">Today</MenuItem>
                  <MenuItem value="this_week">This Week</MenuItem>
                  <MenuItem value="this_month">This Month</MenuItem>
                  <MenuItem value="overdue">Overdue</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={1}>
              <Button
                onClick={clearFilters}
                startIcon={<Close />}
                disabled={getFilterCount() === 0}
                size="small"
              >
                Clear
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Main Content */}
      <Box sx={{ position: 'relative' }}>
        {loading && <CircularProgress sx={{ position: 'absolute', top: 20, right: 20, zIndex: 1 }} />}

        {viewMode === 'kanban' ? (
          <TaskKanbanBoard
            tasks={filteredTasks}
            onTaskClick={handleViewTask}
            onTaskEdit={handleEditTask}
            onTaskDelete={handleTaskDelete}
            onTaskStatusChange={handleTaskStatusChange}
            loading={loading}
          />
        ) : (
          <TaskListView
            tasks={filteredTasks}
            onTaskClick={handleViewTask}
            onTaskEdit={handleEditTask}
            onTaskDelete={handleTaskDelete}
            loading={loading}
          />
        )}
      </Box>

      {/* Mobile FAB */}
      {isMobile && (
        <Fab
          color="primary"
          aria-label="add task"
          onClick={handleCreateTask}
          sx={{
            position: 'fixed',
            bottom: 16,
            right: 16,
            zIndex: 1000,
          }}
        >
          <Add />
        </Fab>
      )}

      {/* Task Form Dialog */}
      <TaskForm
        open={taskFormOpen}
        onClose={() => setTaskFormOpen(false)}
        onSave={handleTaskSave}
        task={selectedTask}
        mode={formMode}
        users={users}
        companies={companies}
        opportunities={opportunities}
        contracts={contracts}
        contacts={contacts}
      />

      {/* Task Detail Dialog */}
      {selectedTask && (
        <TaskDetail
          open={taskDetailOpen}
          onClose={() => setTaskDetailOpen(false)}
          task={selectedTask}
          onEdit={() => {
            setTaskDetailOpen(false);
            handleEditTask(selectedTask);
          }}
          onDelete={(taskId) => {
            setTaskDetailOpen(false);
            handleTaskDelete(taskId);
          }}
          onStatusChange={handleTaskStatusChange}
          users={users}
        />
      )}

      {/* Notification Snackbar */}
      <Snackbar
        open={notification.open}
        autoHideDuration={4000}
        onClose={() => setNotification(prev => ({ ...prev, open: false }))}
        message={notification.message}
        action={
          <IconButton
            size="small"
            color="inherit"
            onClick={() => setNotification(prev => ({ ...prev, open: false }))}
          >
            <Close fontSize="small" />
          </IconButton>
        }
      />
    </Box>
  );
};

export default Tasks;