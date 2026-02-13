import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputAdornment,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Handshake,
  EmojiEvents,
  EventRepeat,
  Receipt,
  Warning,
  Refresh,
  ArrowUpward,
  ArrowDownward,
  FiberNew,
  AccountBalance,
  FilterList,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from 'recharts';
import ApiService from '../services/api';
import { DashboardStats } from '../types';
import {
  EntityFilter,
  DEFAULT_ENTITY,
  ENTITY_OPTIONS,
  formatCurrency,
} from '../constants/entities';
import { useAuth } from '../contexts/AuthContext';
import { Task } from '../types';
import { alpha } from '@mui/material';
import {
  Assignment as TaskIcon,
  OpenInNew as OpenInNewIcon,
} from '@mui/icons-material';

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
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 44,
              height: 44,
              borderRadius: '12px',
              backgroundColor: alpha(iconColor, 0.1),
              color: iconColor,
              mr: 1.5,
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

const getGreeting = (): string => {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 17) return 'Good afternoon';
  return 'Good evening';
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [entityFilter, setEntityFilter] = useState<EntityFilter>(DEFAULT_ENTITY);
  const [myTasks, setMyTasks] = useState<Task[]>([]);

  const loadDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const dashboardStats = await ApiService.getDashboardStats({
        billing_entity: entityFilter,
      });
      setStats(dashboardStats);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError('Failed to load dashboard data');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  }, [entityFilter]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  useEffect(() => {
    const loadMyTasks = async () => {
      try {
        const tasks = await ApiService.getMyTasks();
        setMyTasks(tasks);
      } catch (err) {
        // Non-critical — don't show error
      }
    };
    loadMyTasks();
  }, []);

  const fmtCurrency = (amount: number): string => {
    return formatCurrency(amount, entityFilter);
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
      title: 'Net Revenue This Month',
      value: fmtCurrency(stats.net_revenue ?? stats.monthly_revenue),
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
      value: fmtCurrency(stats.opportunities_value),
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
      subtitle: fmtCurrency(stats.pending_renewal_value),
      icon: <EventRepeat />,
      iconColor: stats.pending_renewals > 5 ? '#f44336' : stats.pending_renewals > 0 ? '#ff9800' : '#4caf50',
      borderColor: stats.pending_renewals > 5 ? '#f44336' : stats.pending_renewals > 0 ? '#ff9800' : '#4caf50',
    },
    {
      title: 'Overdue Invoices',
      value: stats.overdue_invoices,
      subtitle: fmtCurrency(stats.total_overdue_amount),
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

  // Revenue breakdown data
  const revenueBreakdown = [
    {
      label: 'New Revenue',
      value: stats.new_revenue ?? 0,
      icon: <FiberNew sx={{ fontSize: 20 }} />,
      color: '#4caf50',
    },
    {
      label: 'Renewals',
      value: stats.renewal_revenue ?? 0,
      icon: <EventRepeat sx={{ fontSize: 20 }} />,
      color: '#2196f3',
    },
    {
      label: 'Churned',
      value: stats.churned_revenue ?? 0,
      icon: <TrendingDown sx={{ fontSize: 20 }} />,
      color: '#f44336',
      subtitle: stats.churned_count ? `${stats.churned_count} contract${stats.churned_count !== 1 ? 's' : ''}` : undefined,
    },
    {
      label: 'Net Revenue',
      value: stats.net_revenue ?? stats.monthly_revenue,
      icon: <AccountBalance sx={{ fontSize: 20 }} />,
      color: '#7b1fa2',
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
            {data.count} opportunities — {fmtCurrency(data.value)}
          </Typography>
        </Paper>
      );
    }
    return null;
  };

  // Check if trend data has breakdown fields
  const hasBreakdown = stats.revenue_trend?.some((p) => p.new_revenue !== undefined);

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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <Select
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value as EntityFilter)}
              startAdornment={
                <InputAdornment position="start">
                  <FilterList fontSize="small" />
                </InputAdornment>
              }
            >
              {ENTITY_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <IconButton onClick={loadDashboardData} color="primary">
            <Refresh />
          </IconButton>
        </Box>
      </Box>

      {/* Personalized Greeting */}
      <Paper
        sx={{
          p: 2.5,
          mb: 3,
          background: (theme) => theme.palette.mode === 'dark'
            ? 'linear-gradient(135deg, #1e293b 0%, #334155 100%)'
            : 'linear-gradient(135deg, #fff7ed 0%, #ffffff 100%)',
          border: (theme) => theme.palette.mode === 'dark'
            ? '1px solid rgba(255,255,255,0.08)'
            : '1px solid rgba(255, 140, 0, 0.12)',
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
              {getGreeting()}, {user?.first_name || 'there'}!
            </Typography>
            {myTasks.length > 0 ? (
              <Typography variant="body1" color="text.secondary">
                You have <strong>{myTasks.length} active task{myTasks.length !== 1 ? 's' : ''}</strong>
                {myTasks.filter(t => t.is_overdue).length > 0 && (
                  <Typography component="span" sx={{ color: 'error.main', fontWeight: 600 }}>
                    {' '}&mdash; {myTasks.filter(t => t.is_overdue).length} overdue
                  </Typography>
                )}
              </Typography>
            ) : (
              <Typography variant="body1" color="text.secondary">
                No active tasks — you're all caught up!
              </Typography>
            )}
          </Box>
          {myTasks.length > 0 && (
            <Box
              onClick={() => navigate('/tasks')}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                cursor: 'pointer',
                color: '#FF8C00',
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              <TaskIcon sx={{ fontSize: 18 }} />
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                View Tasks
              </Typography>
              <OpenInNewIcon sx={{ fontSize: 14 }} />
            </Box>
          )}
        </Box>
      </Paper>

      {/* Section 1: KPI Cards (6 cards in 2 rows of 3) */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 2.5,
          mb: 3,
        }}
      >
        {kpiCards.map((card, index) => (
          <KPICard key={index} {...card} />
        ))}
      </Box>

      {/* Section 2: Revenue Breakdown */}
      {(stats.new_revenue !== undefined) && (
        <Paper sx={{ p: 2.5, mb: 4 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
            Revenue Breakdown — This Month
          </Typography>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 2,
            }}
          >
            {revenueBreakdown.map((item) => (
              <Box
                key={item.label}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  p: 1.5,
                  borderLeft: 3,
                  borderColor: item.color,
                  borderRadius: 1,
                  bgcolor: 'action.hover',
                }}
              >
                <Box sx={{ color: item.color, display: 'flex' }}>{item.icon}</Box>
                <Box>
                  <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                    {item.label}
                  </Typography>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
                    {item.label === 'Churned' && item.value > 0 ? '-' : ''}
                    {fmtCurrency(item.value)}
                  </Typography>
                  {item.subtitle && (
                    <Typography variant="caption" color="text.secondary">
                      {item.subtitle}
                    </Typography>
                  )}
                </Box>
              </Box>
            ))}
          </Box>
        </Paper>
      )}

      {/* Section 3: Sales Pipeline */}
      {pipelineData.length > 0 && (
        <Paper sx={{ p: 3, mb: 4 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
            Sales Pipeline
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={pipelineData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tickFormatter={(v) => fmtCurrency(v)} />
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

      {/* Section 4: Revenue Trend */}
      {stats.revenue_trend && stats.revenue_trend.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5 }}>
            Revenue Trend — Last 6 Months
          </Typography>
          {hasBreakdown && (
            <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
              New revenue, renewals, and churn
            </Typography>
          )}
          <ResponsiveContainer width="100%" height={320}>
            {hasBreakdown ? (
              <AreaChart data={stats.revenue_trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis tickFormatter={(v) => fmtCurrency(v)} />
                <RechartsTooltip formatter={(value: any, name: string) => [fmtCurrency(value), name]} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="new_revenue"
                  stackId="1"
                  stroke="#4caf50"
                  fill="#4caf50"
                  fillOpacity={0.6}
                  name="New"
                />
                <Area
                  type="monotone"
                  dataKey="renewal_revenue"
                  stackId="1"
                  stroke="#2196f3"
                  fill="#2196f3"
                  fillOpacity={0.6}
                  name="Renewals"
                />
                <Line
                  type="monotone"
                  dataKey="churned_revenue"
                  stroke="#f44336"
                  strokeDasharray="5 5"
                  strokeWidth={2}
                  name="Churn"
                  dot={{ fill: '#f44336', r: 3 }}
                />
                <Line
                  type="monotone"
                  dataKey="net_revenue"
                  stroke="#ff9800"
                  strokeWidth={2}
                  name="Net"
                  dot={{ fill: '#ff9800', r: 3 }}
                />
              </AreaChart>
            ) : (
              <AreaChart data={stats.revenue_trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis tickFormatter={(v) => fmtCurrency(v)} />
                <RechartsTooltip formatter={(value: any) => fmtCurrency(value)} />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  stroke="#2196f3"
                  fill="#2196f3"
                  fillOpacity={0.1}
                />
              </AreaChart>
            )}
          </ResponsiveContainer>
        </Paper>
      )}
    </Box>
  );
};

export default Dashboard;
