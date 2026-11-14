import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Alert,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputAdornment,
  Skeleton,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Link,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
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
  Assignment as TaskIcon,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  ComposedChart,
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
import { DashboardStats, Task } from '../types';
import { EntityFilter, DEFAULT_ENTITY, ENTITY_OPTIONS, formatCurrency, currencyForEntity } from '../constants/entities';
import { useAuth } from '../contexts/AuthContext';
import { PageHeader, SectionCard } from '../components/ui';
import { brand, status, formatMoney } from '../theme';
import { moneyLines, negativeMoneyLines, revenueChange, trendCurrencies, trendSeries } from './dashboardMoney';

type Tone = 'success' | 'warning' | 'error' | 'info' | 'neutral';

/** good below `warnAbove`, attention up to `errorAbove`, problem above it. */
const countTone = (count: number, errorAbove: number): Tone => (count > errorAbove ? 'error' : count > 0 ? 'warning' : 'success');

interface KPICardProps {
  title: string;
  /** One line per currency for money; a single line for counts and rates. */
  lines: string[];
  subtitle?: string[];
  trend?: { value: number; label: string; isPositive: boolean };
  icon: React.ReactNode;
  tone: Tone;
  actionLink?: { label: string; onClick: () => void };
}

const KPICard: React.FC<KPICardProps> = ({ title, lines, subtitle, trend, icon, tone, actionLink }) => {
  const color = status[tone].main;
  return (
    <Paper sx={{ p: 2.5, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 40,
              height: 40,
              borderRadius: 2,
              bgcolor: alpha(color, 0.12),
              color,
              flexShrink: 0,
            }}
          >
            {icon}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
            {title}
          </Typography>
        </Box>
        {lines.map((line, i) => (
          <Typography
            key={i}
            sx={{
              fontWeight: 600,
              fontSize: i === 0 ? '1.75rem' : '1.125rem',
              lineHeight: 1.25,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {line}
          </Typography>
        ))}
        {subtitle?.map((line, i) => (
          <Typography key={i} variant="body2" color="text.secondary" sx={{ mt: i === 0 ? 0.5 : 0 }}>
            {line}
          </Typography>
        ))}
        {trend && (
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
            {trend.isPositive ? (
              <ArrowUpward sx={{ fontSize: 16, color: 'success.main', mr: 0.5 }} />
            ) : (
              <ArrowDownward sx={{ fontSize: 16, color: 'error.main', mr: 0.5 }} />
            )}
            <Typography variant="caption" sx={{ color: trend.isPositive ? 'success.main' : 'error.main', fontWeight: 600 }}>
              {Math.abs(trend.value).toFixed(1)}% {trend.label}
            </Typography>
          </Box>
        )}
      </Box>
      {actionLink && (
        <Link component="button" variant="body2" onClick={actionLink.onClick} sx={{ mt: 1.5, alignSelf: 'flex-start', fontWeight: 500 }}>
          {actionLink.label} →
        </Link>
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

const stageColors: Record<string, string> = {
  Contacted: status.neutral.main,
  'Quotation Sent': status.info.main,
  'Contract Sent': brand.amberText,
  Won: status.success.main,
  Lost: status.error.main,
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [entityFilter, setEntityFilter] = useState<EntityFilter>(DEFAULT_ENTITY);
  const [myTasks, setMyTasks] = useState<Task[]>([]);
  const [trendCurrency, setTrendCurrency] = useState<string | null>(null);

  const loadDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const dashboardStats = await ApiService.getDashboardStats({ billing_entity: entityFilter });
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

  // The trend chart shows one currency at a time (amounts in different currencies never share an axis).
  const currencies = useMemo(() => trendCurrencies(stats?.revenue_trend, entityFilter), [stats, entityFilter]);
  const shownCurrency = currencies.length ? (trendCurrency && currencies.includes(trendCurrency) ? trendCurrency : currencies[0]) : null;
  const chartCurrency = shownCurrency || currencyForEntity(entityFilter);
  const fmtChart = (v: number) => formatMoney(Math.round(v), chartCurrency);

  const header = (
    <PageHeader
      title="Dashboard"
      subtitle={`Business health for one billing entity. Last refreshed ${lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.`}
      actions={
        <>
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <Select
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value as EntityFilter)}
              inputProps={{ 'aria-label': 'Billing entity' }}
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
          <Tooltip title="Refresh">
            <IconButton onClick={loadDashboardData} aria-label="Refresh dashboard">
              <Refresh />
            </IconButton>
          </Tooltip>
        </>
      }
    />
  );

  if (loading && !stats) {
    return (
      <Box>
        {header}
        <Skeleton variant="rounded" height={88} sx={{ mb: 3 }} />
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 2.5 }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="rounded" height={150} />
          ))}
        </Box>
      </Box>
    );
  }

  if (error && !stats) {
    return (
      <Box>
        {header}
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      </Box>
    );
  }

  if (!stats) {
    return null;
  }

  // The old trend compared monthly revenue (not net); keep that, per currency when available.
  const monthlyTrend = revenueChange(
    { total: stats.monthly_revenue, byCurrency: stats.monthly_revenue_by_currency },
    { total: stats.previous_month_revenue, byCurrency: stats.previous_month_revenue_by_currency },
    entityFilter
  );
  const winRate = Number(stats.win_rate);
  const previousWinRate = Number(stats.previous_win_rate);
  const winRateChange = previousWinRate === 0 ? 0 : ((winRate - previousWinRate) / previousWinRate) * 100;

  const kpiCards: KPICardProps[] = [
    {
      title: 'Net Revenue This Month',
      lines: moneyLines(stats.net_revenue_by_currency, stats.net_revenue ?? stats.monthly_revenue, entityFilter),
      trend: { value: monthlyTrend.value, label: monthlyTrend.label, isPositive: monthlyTrend.value >= 0 },
      icon: <TrendingUp />,
      tone: 'success',
    },
    {
      title: 'Active Pipeline',
      // Opportunities have no currency of their own; their values are in the entity's currency.
      lines: [formatCurrency(stats.opportunities_value, entityFilter)],
      subtitle: [`${stats.active_opportunities} opportunities`],
      icon: <Handshake />,
      tone: 'info',
    },
    {
      title: 'Win Rate',
      lines: [`${winRate.toFixed(1)}%`],
      trend: { value: winRateChange, label: 'vs last month', isPositive: winRateChange >= 0 },
      icon: <EmojiEvents />,
      tone: winRate > 50 ? 'success' : winRate > 30 ? 'warning' : 'error',
    },
    {
      title: 'Pending Renewals',
      lines: [String(stats.pending_renewals)],
      subtitle: moneyLines(stats.pending_renewal_value_by_currency, stats.pending_renewal_value, entityFilter),
      icon: <EventRepeat />,
      tone: countTone(stats.pending_renewals, 5),
    },
    {
      title: 'Overdue Invoices',
      lines: [String(stats.overdue_invoices)],
      subtitle: moneyLines(stats.total_overdue_amount_by_currency, stats.total_overdue_amount, entityFilter),
      icon: <Receipt />,
      tone: countTone(stats.overdue_invoices, 3),
      actionLink: stats.overdue_invoices > 0 ? { label: 'View in Today', onClick: () => navigate('/today') } : undefined,
    },
    {
      title: 'Tasks Overdue',
      lines: [String(stats.overdue_tasks)],
      icon: <Warning />,
      tone: countTone(stats.overdue_tasks, 3),
      actionLink: stats.overdue_tasks > 0 ? { label: 'View in Today', onClick: () => navigate('/today') } : undefined,
    },
  ];

  const revenueBreakdown = [
    {
      label: 'New Revenue',
      lines: moneyLines(stats.new_revenue_by_currency, stats.new_revenue ?? 0, entityFilter),
      icon: <FiberNew sx={{ fontSize: 20 }} />,
      color: status.success.main,
    },
    {
      label: 'Renewals',
      lines: moneyLines(stats.renewal_revenue_by_currency, stats.renewal_revenue ?? 0, entityFilter),
      icon: <EventRepeat sx={{ fontSize: 20 }} />,
      color: status.info.main,
    },
    {
      label: 'Churned',
      lines: negativeMoneyLines(stats.churned_revenue_by_currency, stats.churned_revenue ?? 0, entityFilter),
      icon: <TrendingDown sx={{ fontSize: 20 }} />,
      color: status.error.main,
      subtitle: stats.churned_count ? `${stats.churned_count} contract${stats.churned_count !== 1 ? 's' : ''}` : undefined,
    },
    {
      label: 'Net Revenue',
      lines: moneyLines(stats.net_revenue_by_currency, stats.net_revenue ?? stats.monthly_revenue, entityFilter),
      icon: <AccountBalance sx={{ fontSize: 20 }} />,
      color: brand.amberText,
    },
  ];

  const pipelineData = Object.entries(stats.pipeline_stages || {}).map(([stage, data]) => ({
    stage,
    count: data.count,
    value: data.value,
  }));

  const CustomPipelineTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <Paper sx={{ p: 1.5 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {data.stage}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {data.count} opportunities — {formatCurrency(data.value, entityFilter)}
          </Typography>
        </Paper>
      );
    }
    return null;
  };

  const trendData = stats.revenue_trend ? trendSeries(stats.revenue_trend, shownCurrency) : [];
  const hasBreakdown = stats.revenue_trend?.some((p) => p.new_revenue !== undefined);
  const gridStroke = theme.palette.divider;
  const axisTick = { fill: theme.palette.text.secondary, fontSize: 12 };
  const overdueTasks = myTasks.filter((t) => t.is_overdue).length;

  return (
    <Box>
      {header}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Personal greeting */}
      <Paper
        sx={{
          p: 2.5,
          mb: 3,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: { xs: 'flex-start', sm: 'center' },
          flexDirection: { xs: 'column', sm: 'row' },
          gap: 1.5,
          bgcolor: theme.palette.mode === 'dark' ? 'background.paper' : brand.amberTint,
          borderColor: theme.palette.mode === 'dark' ? undefined : brand.amberTint2,
        }}
      >
        <Box>
          <Typography variant="h5" component="p" sx={{ fontWeight: 600, mb: 0.5 }}>
            {getGreeting()}, {user?.first_name || 'there'}
          </Typography>
          {myTasks.length > 0 ? (
            <Typography color="text.secondary">
              You have <strong>{myTasks.length} active task{myTasks.length !== 1 ? 's' : ''}</strong>
              {overdueTasks > 0 && (
                <Typography component="span" sx={{ color: 'error.main', fontWeight: 600 }}>
                  {' '}&mdash; {overdueTasks} overdue
                </Typography>
              )}
            </Typography>
          ) : (
            <Typography color="text.secondary">No active tasks — you're all caught up.</Typography>
          )}
        </Box>
        <Link component="button" variant="body2" onClick={() => navigate('/tasks')} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, fontWeight: 500 }}>
          <TaskIcon sx={{ fontSize: 18 }} />
          View tasks
        </Link>
      </Paper>

      {/* KPI cards */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 2.5, mb: 3 }}>
        {kpiCards.map((card) => (
          <KPICard key={card.title} {...card} />
        ))}
      </Box>

      {/* Revenue breakdown */}
      {stats.new_revenue !== undefined && (
        <SectionCard title="Revenue this month" subtitle="New contracts, renewals and churn" sx={{ mb: 3 }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2 }}>
            {revenueBreakdown.map((item) => (
              <Box
                key={item.label}
                sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, p: 1.5, borderLeft: 3, borderColor: item.color, borderRadius: 1, bgcolor: 'action.hover' }}
              >
                <Box sx={{ color: item.color, display: 'flex', mt: 0.25 }}>{item.icon}</Box>
                <Box>
                  <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                    {item.label}
                  </Typography>
                  {item.lines.map((line, i) => (
                    <Typography key={i} variant="subtitle1" sx={{ fontWeight: 600, lineHeight: 1.3, fontVariantNumeric: 'tabular-nums' }}>
                      {line}
                    </Typography>
                  ))}
                  {item.subtitle && (
                    <Typography variant="caption" color="text.secondary">
                      {item.subtitle}
                    </Typography>
                  )}
                </Box>
              </Box>
            ))}
          </Box>
        </SectionCard>
      )}

      {/* Sales pipeline */}
      {pipelineData.length > 0 && (
        <SectionCard title="Sales pipeline" subtitle={`Expected value by stage, in ${currencyForEntity(entityFilter)}`} sx={{ mb: 3 }}>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={pipelineData} layout="vertical" margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis type="number" tickFormatter={(v) => formatCurrency(v, entityFilter)} tick={axisTick} />
              <YAxis type="category" dataKey="stage" width={120} tick={axisTick} />
              <RechartsTooltip content={<CustomPipelineTooltip />} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                {pipelineData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={stageColors[entry.stage] || status.neutral.main} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      )}

      {/* Revenue trend */}
      {stats.revenue_trend && stats.revenue_trend.length > 0 && (
        <SectionCard
          title="Revenue trend, last 6 months"
          subtitle={hasBreakdown ? `New revenue, renewals and churn, in ${chartCurrency}` : `In ${chartCurrency}`}
          action={
            currencies.length > 1 ? (
              <ToggleButtonGroup
                size="small"
                exclusive
                value={shownCurrency}
                onChange={(_, v) => v && setTrendCurrency(v)}
                aria-label="Currency shown in the chart"
              >
                {currencies.map((c) => (
                  <ToggleButton key={c} value={c}>
                    {c}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            ) : undefined
          }
        >
          <ResponsiveContainer width="100%" height={320}>
            {hasBreakdown ? (
              // A composed chart, so the churn and net lines draw next to the stacked areas.
              <ComposedChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                <XAxis dataKey="month" tick={axisTick} />
                <YAxis tickFormatter={fmtChart} tick={axisTick} width={96} />
                <RechartsTooltip formatter={(value: any, name: string) => [fmtChart(Number(value)), name]} />
                <Legend />
                <Area type="monotone" dataKey="new_revenue" stackId="1" stroke={status.success.main} fill={status.success.main} fillOpacity={0.35} name="New" />
                <Area type="monotone" dataKey="renewal_revenue" stackId="1" stroke={status.info.main} fill={status.info.main} fillOpacity={0.35} name="Renewals" />
                <Line type="monotone" dataKey="churned_revenue" stroke={status.error.main} strokeDasharray="5 5" strokeWidth={2} name="Churn" dot={{ fill: status.error.main, r: 3 }} />
                <Line type="monotone" dataKey="net_revenue" stroke={brand.amberText} strokeWidth={2} name="Net" dot={{ fill: brand.amberText, r: 3 }} />
              </ComposedChart>
            ) : (
              <AreaChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                <XAxis dataKey="month" tick={axisTick} />
                <YAxis tickFormatter={fmtChart} tick={axisTick} width={96} />
                <RechartsTooltip formatter={(value: any) => fmtChart(Number(value))} />
                <Area type="monotone" dataKey="revenue" stroke={status.info.main} fill={status.info.main} fillOpacity={0.12} />
              </AreaChart>
            )}
          </ResponsiveContainer>
        </SectionCard>
      )}
    </Box>
  );
};

export default Dashboard;
