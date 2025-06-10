import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Chip,
} from '@mui/material';
import {
  Business,
  Handshake,
  Assignment,
  Receipt,
  Warning,
  TrendingUp,
} from '@mui/icons-material';
import { DashboardStats, Task } from '../types';
import ApiService from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color?: string;
  format?: 'number' | 'currency';
}

const StatCard: React.FC<StatCardProps> = ({ 
  title, 
  value, 
  icon, 
  color = 'primary.main',
  format = 'number' 
}) => {
  const formatValue = (val: number | string) => {
    if (format === 'currency' && typeof val === 'number') {
      return `$${val.toLocaleString()}`;
    }
    return val.toLocaleString();
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Box sx={{ color, mr: 1 }}>
            {icon}
          </Box>
          <Typography variant="h6" component="div">
            {formatValue(value)}
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">
          {title}
        </Typography>
      </CardContent>
    </Card>
  );
};

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [myTasks, setMyTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [dashboardStats, tasksData] = await Promise.all([
        ApiService.getDashboardStats(),
        ApiService.getMyTasks(),
      ]);
      
      setStats(dashboardStats);
      setMyTasks(tasksData.slice(0, 5)); // Show only first 5 tasks
    } catch (err: any) {
      setError('Failed to load dashboard data');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
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

  if (!stats) {
    return null;
  }

  const getTaskPriorityColor = (priority: string) => {
    switch (priority) {
      case 'Urgent': return 'error';
      case 'High': return 'warning';
      case 'Medium': return 'info';
      default: return 'default';
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Welcome back, {user?.first_name}! Here's your overview.
      </Typography>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Companies"
            value={stats.total_companies}
            icon={<Business />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Active Opportunities"
            value={stats.active_opportunities}
            icon={<Handshake />}
            color="success.main"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Active Contracts"
            value={stats.active_contracts}
            icon={<Assignment />}
            color="info.main"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Overdue Tasks"
            value={stats.overdue_tasks}
            icon={<Warning />}
            color="error.main"
          />
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            title="Opportunities Value"
            value={stats.opportunities_value}
            icon={<TrendingUp />}
            format="currency"
            color="success.main"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            title="Contracts Value"
            value={stats.contracts_value}
            icon={<Assignment />}
            format="currency"
            color="info.main"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            title="Overdue Invoices"
            value={stats.overdue_invoices}
            icon={<Receipt />}
            color="error.main"
          />
        </Grid>
      </Grid>

      {/* Sales Funnel - only show for Sales users */}
      {(user?.role === 'Sales' || user?.role === 'Admin') && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Sales Pipeline
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6} sm={4} md={2}>
                  <StatCard
                    title="Contacted"
                    value={stats.contacted_count}
                    icon={<Handshake />}
                  />
                </Grid>
                <Grid item xs={6} sm={4} md={2}>
                  <StatCard
                    title="Quotation Sent"
                    value={stats.quotation_count}
                    icon={<Handshake />}
                  />
                </Grid>
                <Grid item xs={6} sm={4} md={2}>
                  <StatCard
                    title="Contract Sent"
                    value={stats.contract_count}
                    icon={<Handshake />}
                  />
                </Grid>
                <Grid item xs={6} sm={4} md={2}>
                  <StatCard
                    title="Won"
                    value={stats.won_count}
                    icon={<Handshake />}
                    color="success.main"
                  />
                </Grid>
                <Grid item xs={6} sm={4} md={2}>
                  <StatCard
                    title="Lost"
                    value={stats.lost_count}
                    icon={<Handshake />}
                    color="error.main"
                  />
                </Grid>
              </Grid>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* My Tasks */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              My Recent Tasks
            </Typography>
            {myTasks.length > 0 ? (
              <List>
                {myTasks.map((task) => (
                  <ListItem key={task.id} divider>
                    <ListItemText
                      primary={task.title}
                      secondary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                          <Chip 
                            label={task.priority} 
                            size="small" 
                            color={getTaskPriorityColor(task.priority) as any}
                          />
                          <Chip 
                            label={task.status} 
                            size="small" 
                            variant="outlined"
                          />
                          {task.due_date && (
                            <Typography variant="caption" color="text.secondary">
                              Due: {new Date(task.due_date).toLocaleDateString()}
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No tasks assigned to you.
              </Typography>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Monthly Summary
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <StatCard
                  title="Monthly Revenue"
                  value={stats.monthly_revenue}
                  icon={<TrendingUp />}
                  format="currency"
                  color="success.main"
                />
              </Grid>
              <Grid item xs={6}>
                <StatCard
                  title="New Opportunities"
                  value={stats.monthly_new_opportunities}
                  icon={<Handshake />}
                />
              </Grid>
              <Grid item xs={6}>
                <StatCard
                  title="Closed Deals"
                  value={stats.monthly_closed_deals}
                  icon={<Assignment />}
                  color="success.main"
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;