import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  Alert,
} from '@mui/material';
import {
  Business,
  Handshake,
  Assignment,
  Receipt,
  Warning,
  TrendingUp,
} from '@mui/icons-material';
import { DashboardStats } from '../types';
import ApiService from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import QuickActions from '../components/QuickActions';
import LoadingSkeleton from '../components/LoadingSkeleton';
import SalesDashboard from '../components/SalesDashboard';
import ContractWidgets from '../components/ContractWidgets';
import InvoiceWidgets from '../components/InvoiceWidgets';
import TaskWidgets from '../components/TaskWidgets';

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const dashboardStats = await ApiService.getDashboardStats();
      setStats(dashboardStats);
    } catch (err: any) {
      setError('Failed to load dashboard data');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <LoadingSkeleton variant="dashboard" />;
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

  const getDepartmentGreeting = () => {
    switch (user?.role) {
      case 'Sales':
        return 'Ready to close some deals today?';
      case 'Marketing':
        return 'Time to engage and convert!';
      case 'Tech Support':
        return 'Ready to solve customer challenges?';
      case 'Admin':
        return 'Everything running smoothly.';
      default:
        return 'Here\'s your overview.';
    }
  };

  // Show Sales-specific dashboard for Sales users
  if (user?.role === 'Sales') {
    return <SalesDashboard />;
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        {user?.role} Dashboard
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Welcome back, {user?.first_name}! {getDepartmentGreeting()}
      </Typography>

      {/* Quick Actions */}
      <Box sx={{ mb: 4 }}>
        <QuickActions />
      </Box>

      {/* Main Stats */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <StatCard
            title="Total Companies"
            value={stats.total_companies}
            icon={<Business />}
          />
        </Box>
        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <StatCard
            title="Active Opportunities"
            value={stats.active_opportunities}
            icon={<Handshake />}
            color="success.main"
          />
        </Box>
        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <StatCard
            title="Active Contracts"
            value={stats.active_contracts}
            icon={<Assignment />}
            color="info.main"
          />
        </Box>
        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <StatCard
            title="Overdue Tasks"
            value={stats.overdue_tasks}
            icon={<Warning />}
            color="error.main"
          />
        </Box>
      </Box>

      {/* Secondary Stats */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 300px', minWidth: 250 }}>
          <StatCard
            title="Opportunities Value"
            value={stats.opportunities_value}
            icon={<TrendingUp />}
            format="currency"
            color="success.main"
          />
        </Box>
        <Box sx={{ flex: '1 1 300px', minWidth: 250 }}>
          <StatCard
            title="Contracts Value"
            value={stats.contracts_value}
            icon={<Assignment />}
            format="currency"
            color="info.main"
          />
        </Box>
        <Box sx={{ flex: '1 1 300px', minWidth: 250 }}>
          <StatCard
            title="Overdue Invoices"
            value={stats.overdue_invoices}
            icon={<Receipt />}
            color="error.main"
          />
        </Box>
      </Box>

      {/* Sales Funnel - only show for Sales users */}
      {(['Sales', 'Admin'] as const).includes(user?.role as any) && (
        <Box sx={{ mb: 3 }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Sales Pipeline
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Box sx={{ flex: '1 1 180px', minWidth: 150 }}>
                <StatCard
                  title="Contacted"
                  value={stats.contacted_count}
                  icon={<Handshake />}
                />
              </Box>
              <Box sx={{ flex: '1 1 180px', minWidth: 150 }}>
                <StatCard
                  title="Quotation Sent"
                  value={stats.quotation_count}
                  icon={<Handshake />}
                />
              </Box>
              <Box sx={{ flex: '1 1 180px', minWidth: 150 }}>
                <StatCard
                  title="Contract Sent"
                  value={stats.contract_count}
                  icon={<Handshake />}
                />
              </Box>
              <Box sx={{ flex: '1 1 180px', minWidth: 150 }}>
                <StatCard
                  title="Won"
                  value={stats.won_count}
                  icon={<Handshake />}
                  color="success.main"
                />
              </Box>
              <Box sx={{ flex: '1 1 180px', minWidth: 150 }}>
                <StatCard
                  title="Lost"
                  value={stats.lost_count}
                  icon={<Handshake />}
                  color="error.main"
                />
              </Box>
            </Box>
          </Paper>
        </Box>
      )}

      {/* Contract Management Section - show for Admin, Sales */}
      {(['Admin', 'Sales'] as const).includes(user?.role as any) && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h5" gutterBottom>
            Contract Management
          </Typography>
          <ContractWidgets />
        </Box>
      )}

      {/* Invoice Management Section - show for Admin, Sales */}
      {(['Admin', 'Sales'] as const).includes(user?.role as any) && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h5" gutterBottom>
            Invoice Management
          </Typography>
          <InvoiceWidgets />
        </Box>
      )}

      {/* Task Management Section */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          Task Management
        </Typography>
        <TaskWidgets />
      </Box>

      {/* Monthly Summary */}
      <Box sx={{ mb: 3 }}>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Monthly Summary
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Box sx={{ flex: '1 1 300px', minWidth: 250 }}>
              <StatCard
                title="Monthly Revenue"
                value={stats.monthly_revenue}
                icon={<TrendingUp />}
                format="currency"
                color="success.main"
              />
            </Box>
            <Box sx={{ flex: '1 1 200px', minWidth: 150 }}>
              <StatCard
                title="New Opportunities"
                value={stats.monthly_new_opportunities}
                icon={<Handshake />}
              />
            </Box>
            <Box sx={{ flex: '1 1 200px', minWidth: 150 }}>
              <StatCard
                title="Closed Deals"
                value={stats.monthly_closed_deals}
                icon={<Assignment />}
                color="success.main"
              />
            </Box>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
};

export default Dashboard;