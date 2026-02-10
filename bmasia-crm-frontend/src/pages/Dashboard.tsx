import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  Chip,
} from '@mui/material';
import {
  TrendingUp,
  Handshake,
  EmojiEvents,
  EventRepeat,
  Receipt,
  Warning,
  Refresh,
  ArrowUpward,
  ArrowDownward,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import ApiService from '../services/api';
import { DashboardStats } from '../types';
import { useAuth } from '../contexts/AuthContext';

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: {
    value: number;
    label: string;
    isPositive: boolean;
  };
  icon: React.ReactNode;
  iconColor: string;
  borderColor: string;
  actionLink?: {
    label: string;
    onClick: () => void;
  };
}

const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  subtitle,
  trend,
  icon,
  iconColor,
  borderColor,
  actionLink,
}) => {
  return (
    <Paper
      sx={{
        p: 2.5,
        height: '100%',
        borderLeft: 4,
        borderColor: borderColor,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}
    >
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
          <Box
            sx={{
              color: iconColor,
              mr: 1.5,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {icon}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
            {title}
          </Typography>
        </Box>
        <Typography variant="h4" sx={{ fontWeight: 600, mb: 0.5 }}>
          {value}
        </Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        )}
        {trend && (
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
            {trend.isPositive ? (
              <ArrowUpward sx={{ fontSize: 16, color: 'success.main', mr: 0.5 }} />
            ) : (
              <ArrowDownward sx={{ fontSize: 16, color: 'error.main', mr: 0.5 }} />
            )}
            <Typography
              variant="caption"
              sx={{
                color: trend.isPositive ? 'success.main' : 'error.main',
                fontWeight: 600,
              }}
            >
              {Math.abs(trend.value).toFixed(1)}% {trend.label}
            </Typography>
          </Box>
        )}
      </Box>
      {actionLink && (
        <Box sx={{ mt: 1.5 }}>
          <Typography
            variant="caption"
            sx={{
              color: 'primary.main',
              cursor: 'pointer',
              '&:hover': { textDecoration: 'underline' },
            }}
            onClick={actionLink.onClick}
          >
            {actionLink.label} →
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError('');
      const dashboardStats = await ApiService.getDashboardStats();
      setStats(dashboardStats);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError('Failed to load dashboard data');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const calculatePercentChange = (current: number, previous: number): number => {
    if (previous === 0) return 0;
    return ((current - previous) / previous) * 100;
  };

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '400px',
        }}
      >
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

  const revenueChange = calculatePercentChange(
    stats.monthly_revenue,
    stats.previous_month_revenue
  );
  const winRateChange = calculatePercentChange(stats.win_rate, stats.previous_win_rate);

  // KPI Cards Data
  const kpiCards = [
    {
      title: 'Revenue This Month',
      value: formatCurrency(stats.monthly_revenue),
      trend: {
        value: revenueChange,
        label: 'vs last month',
        isPositive: revenueChange >= 0,
      },
      icon: <TrendingUp />,
      iconColor: '#4caf50',
      borderColor: '#4caf50',
    },
    {
      title: 'Active Pipeline',
      value: formatCurrency(stats.opportunities_value),
      subtitle: `${stats.active_opportunities} opportunities`,
      icon: <Handshake />,
      iconColor: '#2196f3',
      borderColor: '#2196f3',
    },
    {
      title: 'Win Rate',
      value: `${stats.win_rate.toFixed(1)}%`,
      trend: {
        value: winRateChange,
        label: 'vs last month',
        isPositive: winRateChange >= 0,
      },
      icon: <EmojiEvents />,
      iconColor:
        stats.win_rate > 50 ? '#4caf50' : stats.win_rate > 30 ? '#ff9800' : '#f44336',
      borderColor:
        stats.win_rate > 50 ? '#4caf50' : stats.win_rate > 30 ? '#ff9800' : '#f44336',
    },
    {
      title: 'Pending Renewals',
      value: stats.pending_renewals,
      subtitle: formatCurrency(stats.pending_renewal_value),
      icon: <EventRepeat />,
      iconColor: stats.pending_renewals > 5 ? '#f44336' : stats.pending_renewals > 0 ? '#ff9800' : '#4caf50',
      borderColor: stats.pending_renewals > 5 ? '#f44336' : stats.pending_renewals > 0 ? '#ff9800' : '#4caf50',
    },
    {
      title: 'Overdue Invoices',
      value: stats.overdue_invoices,
      subtitle: formatCurrency(stats.total_overdue_amount),
      icon: <Receipt />,
      iconColor: stats.overdue_invoices > 3 ? '#f44336' : stats.overdue_invoices > 0 ? '#ff9800' : '#4caf50',
      borderColor: stats.overdue_invoices > 3 ? '#f44336' : stats.overdue_invoices > 0 ? '#ff9800' : '#4caf50',
      actionLink:
        stats.overdue_invoices > 0
          ? {
              label: 'View in Today',
              onClick: () => navigate('/today'),
            }
          : undefined,
    },
    {
      title: 'Tasks Overdue',
      value: stats.overdue_tasks,
      icon: <Warning />,
      iconColor: stats.overdue_tasks > 3 ? '#f44336' : stats.overdue_tasks > 0 ? '#ff9800' : '#4caf50',
      borderColor: stats.overdue_tasks > 3 ? '#f44336' : stats.overdue_tasks > 0 ? '#ff9800' : '#4caf50',
      actionLink:
        stats.overdue_tasks > 0
          ? {
              label: 'View in Today',
              onClick: () => navigate('/today'),
            }
          : undefined,
    },
  ];

  // Transform pipeline_stages object to array for Recharts
  const pipelineData = Object.entries(stats.pipeline_stages || {}).map(
    ([stage, data]) => ({
      stage,
      count: data.count,
      value: data.value,
    })
  );

  const stageColors: Record<string, string> = {
    Contacted: '#42a5f5',
    'Quotation Sent': '#66bb6a',
    'Contract Sent': '#ffa726',
    Won: '#4caf50',
    Lost: '#ef5350',
  };

  const CustomPipelineTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <Paper sx={{ p: 1.5 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {data.stage}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {data.count} opportunities — {formatCurrency(data.value)}
          </Typography>
        </Paper>
      );
    }
    return null;
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 600 }}>
            Dashboard
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Last refreshed: {lastRefreshed.toLocaleTimeString()}
          </Typography>
        </Box>
        <IconButton onClick={loadDashboardData} color="primary">
          <Refresh />
        </IconButton>
      </Box>

      {/* Section 1: KPI Cards (6 cards in 2 rows of 3) */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 2.5,
          mb: 4,
        }}
      >
        {kpiCards.map((card, index) => (
          <KPICard key={index} {...card} />
        ))}
      </Box>

      {/* Section 2: Sales Pipeline */}
      {pipelineData.length > 0 && (
        <Paper sx={{ p: 3, mb: 4 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
            Sales Pipeline
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={pipelineData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="stage" width={130} />
              <RechartsTooltip content={<CustomPipelineTooltip />} />
              <Bar dataKey="value" radius={[0, 8, 8, 0]}>
                {pipelineData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={stageColors[entry.stage] || '#9e9e9e'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Paper>
      )}

      {/* Section 3: Revenue Trend */}
      {stats.revenue_trend && stats.revenue_trend.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
            Revenue Trend — Last 6 Months
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={stats.revenue_trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis
                tickFormatter={(value) =>
                  new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: 'USD',
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 0,
                  }).format(value)
                }
              />
              <RechartsTooltip
                formatter={(value: any) =>
                  new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: 'USD',
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 0,
                  }).format(value)
                }
              />
              <Line
                type="monotone"
                dataKey="revenue"
                stroke="#2196f3"
                strokeWidth={2}
                fill="#2196f3"
                fillOpacity={0.1}
              />
            </LineChart>
          </ResponsiveContainer>
        </Paper>
      )}
    </Box>
  );
};

export default Dashboard;
