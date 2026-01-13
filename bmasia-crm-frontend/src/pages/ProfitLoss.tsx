import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  LinearProgress,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  GridLegacy as Grid,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  AttachMoney as MoneyIcon,
  Receipt as ReceiptIcon,
  AccountBalance as AccountBalanceIcon,
  ShowChart as ChartIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import api from '../services/api';

// Backend P&L response interface (matches actual backend response)
interface PLCategory {
  category_id: string;
  category_name: string;
  amount: number;
  count: number;
}

interface PLResponse {
  period: {
    year: number;
    month?: number;
    month_name?: string;
    through_month?: number;
    type: string;
  };
  billing_entity: string;
  currency: string;
  revenue: {
    new: { count: number; value: number };
    renewal: { count: number; value: number };
    addon: { count: number; value: number };
    churn: { count: number; value: number };
    total: number;
  };
  cogs: {
    categories: PLCategory[];
    total: number;
  };
  gross_profit: number;
  gross_margin: number;
  operating_expenses: {
    gna: {
      categories: PLCategory[];
      total: number;
    };
    sales_marketing: {
      categories: PLCategory[];
      total: number;
    };
    total: number;
  };
  operating_income: number;
  operating_margin: number;
  net_profit: number;
  net_margin: number;
}

interface TrendData {
  month: number;
  month_name: string;
  revenue: number;
  cogs: number;
  gross_profit: number;
  operating_expenses: number;
  net_profit: number;
  gross_margin: number;
  net_margin: number;
}

// Format currency
const formatCurrency = (amount: number, currency: string = 'THB') => {
  const locale = currency === 'THB' ? 'th-TH' : currency === 'USD' ? 'en-US' : 'en-US';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

// Format percentage
const formatPercent = (value: number) => {
  return `${value.toFixed(1)}%`;
};

// KPI Card Component
interface KPICardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
  trend?: { value: number; isPositive: boolean };
}

const KPICard: React.FC<KPICardProps> = ({ title, value, subtitle, icon, color, trend }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Box display="flex" alignItems="flex-start" justifyContent="space-between">
        <Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {title}
          </Typography>
          <Typography variant="h4" component="div" fontWeight="bold" color={color}>
            {value}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" mt={0.5}>
              {subtitle}
            </Typography>
          )}
        </Box>
        <Box
          sx={{
            backgroundColor: `${color}15`,
            borderRadius: 2,
            p: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {React.cloneElement(icon as React.ReactElement, { sx: { color, fontSize: 32 } })}
        </Box>
      </Box>
      {trend && (
        <Box mt={1} display="flex" alignItems="center" gap={0.5}>
          {trend.isPositive ? (
            <TrendingUpIcon sx={{ color: '#4caf50', fontSize: 18 }} />
          ) : (
            <TrendingDownIcon sx={{ color: '#f44336', fontSize: 18 }} />
          )}
          <Typography
            variant="body2"
            sx={{ color: trend.isPositive ? '#4caf50' : '#f44336' }}
          >
            {trend.isPositive ? '+' : ''}{formatPercent(trend.value)} vs last year
          </Typography>
        </Box>
      )}
    </CardContent>
  </Card>
);

// P&L Statement Table Component
interface PLTableProps {
  statement: PLResponse;
  currency: string;
}

const PLStatementTable: React.FC<PLTableProps> = ({ statement, currency }) => {
  const periodLabel = statement.period.type === 'ytd'
    ? `Year-to-Date through ${statement.period.month_name || `Month ${statement.period.through_month}`}`
    : statement.period.month_name;

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow sx={{ backgroundColor: 'grey.100' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold">
                Profit & Loss Statement - {periodLabel} {statement.period.year}
              </Typography>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {/* Revenue Section */}
          <TableRow sx={{ backgroundColor: '#e3f2fd' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" color="primary">REVENUE</Typography>
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>New Contracts ({statement.revenue.new.count})</TableCell>
            <TableCell align="right">{formatCurrency(statement.revenue.new.value, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Renewals ({statement.revenue.renewal.count})</TableCell>
            <TableCell align="right">{formatCurrency(statement.revenue.renewal.value, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Add-ons ({statement.revenue.addon.count})</TableCell>
            <TableCell align="right">{formatCurrency(statement.revenue.addon.value, currency)}</TableCell>
          </TableRow>
          {statement.revenue.churn.count > 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4, color: '#d32f2f' }}>Churn ({statement.revenue.churn.count})</TableCell>
              <TableCell align="right" sx={{ color: '#d32f2f' }}>{formatCurrency(statement.revenue.churn.value, currency)}</TableCell>
            </TableRow>
          )}
          <TableRow sx={{ borderTop: 2, borderColor: 'grey.300' }}>
            <TableCell sx={{ fontWeight: 'bold' }}>Total Revenue</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'bold', color: '#1976d2' }}>
              {formatCurrency(statement.revenue.total, currency)}
            </TableCell>
          </TableRow>

          {/* COGS Section */}
          <TableRow sx={{ backgroundColor: '#fff3e0' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" sx={{ color: '#e65100' }}>COST OF GOODS SOLD (COGS)</Typography>
            </TableCell>
          </TableRow>
          {statement.cogs.categories.map((item) => (
            <TableRow key={item.category_id}>
              <TableCell sx={{ pl: 4 }}>{item.category_name}</TableCell>
              <TableCell align="right">{formatCurrency(item.amount, currency)}</TableCell>
            </TableRow>
          ))}
          {statement.cogs.categories.length === 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4, fontStyle: 'italic' }} colSpan={2}>No COGS expenses recorded</TableCell>
            </TableRow>
          )}
          <TableRow sx={{ borderTop: 2, borderColor: 'grey.300' }}>
            <TableCell sx={{ fontWeight: 'bold' }}>Total COGS</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'bold', color: '#e65100' }}>
              {formatCurrency(statement.cogs.total, currency)}
            </TableCell>
          </TableRow>

          {/* Gross Profit */}
          <TableRow sx={{ backgroundColor: '#e8f5e9' }}>
            <TableCell>
              <Typography fontWeight="bold" color="success.main">GROSS PROFIT</Typography>
            </TableCell>
            <TableCell align="right">
              <Typography fontWeight="bold" color="success.main">
                {formatCurrency(statement.gross_profit, currency)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                ({formatPercent(statement.gross_margin)} margin)
              </Typography>
            </TableCell>
          </TableRow>

          {/* G&A Section */}
          <TableRow sx={{ backgroundColor: '#f3e5f5' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" sx={{ color: '#7b1fa2' }}>GENERAL & ADMINISTRATIVE (G&A)</Typography>
            </TableCell>
          </TableRow>
          {statement.operating_expenses.gna.categories.map((item) => (
            <TableRow key={item.category_id}>
              <TableCell sx={{ pl: 4 }}>{item.category_name}</TableCell>
              <TableCell align="right">{formatCurrency(item.amount, currency)}</TableCell>
            </TableRow>
          ))}
          {statement.operating_expenses.gna.categories.length === 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4, fontStyle: 'italic' }} colSpan={2}>No G&A expenses recorded</TableCell>
            </TableRow>
          )}
          <TableRow sx={{ borderTop: 1, borderColor: 'grey.300' }}>
            <TableCell sx={{ pl: 2, fontWeight: 'medium' }}>Total G&A</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'medium' }}>
              {formatCurrency(statement.operating_expenses.gna.total, currency)}
            </TableCell>
          </TableRow>

          {/* Sales & Marketing Section */}
          <TableRow sx={{ backgroundColor: '#e0f7fa' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" sx={{ color: '#00838f' }}>SALES & MARKETING</Typography>
            </TableCell>
          </TableRow>
          {statement.operating_expenses.sales_marketing.categories.map((item) => (
            <TableRow key={item.category_id}>
              <TableCell sx={{ pl: 4 }}>{item.category_name}</TableCell>
              <TableCell align="right">{formatCurrency(item.amount, currency)}</TableCell>
            </TableRow>
          ))}
          {statement.operating_expenses.sales_marketing.categories.length === 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4, fontStyle: 'italic' }} colSpan={2}>No Sales & Marketing expenses recorded</TableCell>
            </TableRow>
          )}
          <TableRow sx={{ borderTop: 1, borderColor: 'grey.300' }}>
            <TableCell sx={{ pl: 2, fontWeight: 'medium' }}>Total Sales & Marketing</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'medium' }}>
              {formatCurrency(statement.operating_expenses.sales_marketing.total, currency)}
            </TableCell>
          </TableRow>

          {/* Total Operating Expenses */}
          <TableRow sx={{ borderTop: 2, borderColor: 'grey.400' }}>
            <TableCell sx={{ fontWeight: 'bold' }}>Total Operating Expenses</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'bold', color: '#d32f2f' }}>
              {formatCurrency(statement.operating_expenses.total, currency)}
            </TableCell>
          </TableRow>

          {/* Operating Income */}
          <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
            <TableCell>
              <Typography fontWeight="bold">OPERATING INCOME</Typography>
            </TableCell>
            <TableCell align="right">
              <Typography fontWeight="bold" color={statement.operating_income >= 0 ? 'success.main' : 'error.main'}>
                {formatCurrency(statement.operating_income, currency)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                ({formatPercent(statement.operating_margin)} margin)
              </Typography>
            </TableCell>
          </TableRow>

          {/* Net Profit */}
          <TableRow sx={{ backgroundColor: statement.net_profit >= 0 ? '#c8e6c9' : '#ffcdd2' }}>
            <TableCell>
              <Typography variant="h6" fontWeight="bold">
                NET PROFIT
              </Typography>
            </TableCell>
            <TableCell align="right">
              <Typography variant="h6" fontWeight="bold" color={statement.net_profit >= 0 ? 'success.main' : 'error.main'}>
                {formatCurrency(statement.net_profit, currency)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                ({formatPercent(statement.net_margin)} margin)
              </Typography>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </TableContainer>
  );
};

// Trend Chart Component
interface TrendChartProps {
  data: TrendData[];
  currency: string;
}

const TrendChart: React.FC<TrendChartProps> = ({ data, currency }) => {
  const currencySymbol = currency === 'THB' ? '฿' : '$';

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" fontWeight="bold" gutterBottom>
          Monthly P&L Trend
        </Typography>
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month_name" />
            <YAxis
              tickFormatter={(value) => `${currencySymbol}${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip
              formatter={(value: number, name: string) => [
                formatCurrency(value, currency),
                name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, ' ')
              ]}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="revenue"
              stroke="#1976d2"
              strokeWidth={2}
              name="Revenue"
            />
            <Line
              type="monotone"
              dataKey="gross_profit"
              stroke="#4caf50"
              strokeWidth={2}
              name="Gross Profit"
            />
            <Line
              type="monotone"
              dataKey="net_profit"
              stroke="#ff9800"
              strokeWidth={2}
              name="Net Profit"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// Margin Chart Component
interface MarginChartProps {
  data: TrendData[];
}

const MarginChart: React.FC<MarginChartProps> = ({ data }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" fontWeight="bold" gutterBottom>
          Margin Trend (%)
        </Typography>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month_name" />
            <YAxis tickFormatter={(value) => `${value}%`} />
            <Tooltip formatter={(value: number) => [`${value.toFixed(1)}%`]} />
            <Legend />
            <Bar dataKey="gross_margin" fill="#4caf50" name="Gross Margin %" />
            <Bar dataKey="net_margin" fill="#ff9800" name="Net Margin %" />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// Main Component
const ProfitLoss: React.FC = () => {
  const [statement, setStatement] = useState<PLResponse | null>(null);
  const [trendData, setTrendData] = useState<TrendData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [month, setMonth] = useState<number>(new Date().getMonth() + 1);
  const [currency, setCurrency] = useState<string>('');
  const [billingEntity, setBillingEntity] = useState<string>('');
  const [viewMode, setViewMode] = useState<'monthly' | 'ytd'>('monthly');

  const months = [
    { value: 1, label: 'January' },
    { value: 2, label: 'February' },
    { value: 3, label: 'March' },
    { value: 4, label: 'April' },
    { value: 5, label: 'May' },
    { value: 6, label: 'June' },
    { value: 7, label: 'July' },
    { value: 8, label: 'August' },
    { value: 9, label: 'September' },
    { value: 10, label: 'October' },
    { value: 11, label: 'November' },
    { value: 12, label: 'December' },
  ];

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i);

  useEffect(() => {
    loadData();
  }, [year, month, currency, billingEntity, viewMode]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Load P&L statement - use raw fetch to get proper response
      const token = localStorage.getItem('accessToken');
      const baseUrl = process.env.REACT_APP_API_URL || '';

      const params = new URLSearchParams();
      params.append('year', year.toString());

      if (viewMode === 'monthly') {
        params.append('month', month.toString());
      } else {
        params.append('through_month', month.toString());
      }

      if (currency) params.append('currency', currency);
      if (billingEntity) params.append('billing_entity', billingEntity);

      const endpoint = viewMode === 'monthly' ? 'monthly' : 'ytd';
      const plResponse = await fetch(
        `${baseUrl}/api/v1/profit-loss/${endpoint}/?${params.toString()}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!plResponse.ok) {
        throw new Error(`Failed to load P&L data: ${plResponse.statusText}`);
      }

      const statementData: PLResponse = await plResponse.json();
      setStatement(statementData);

      // Load trend data
      const trendParams = new URLSearchParams();
      trendParams.append('year', year.toString());
      if (currency) trendParams.append('currency', currency);
      if (billingEntity) trendParams.append('billing_entity', billingEntity);

      const trendResponse = await fetch(
        `${baseUrl}/api/v1/profit-loss/trend/?${trendParams.toString()}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (trendResponse.ok) {
        const trend: TrendData[] = await trendResponse.json();
        setTrendData(trend);
      }
    } catch (err: any) {
      console.error('Error loading P&L data:', err);
      setError(err.message || 'Failed to load P&L report');
    } finally {
      setLoading(false);
    }
  };

  if (loading && !statement) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  const displayCurrency = currency || 'THB';

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight="bold">
            Profit & Loss Statement
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Revenue, expenses, and profitability analysis
          </Typography>
        </Box>
        <Stack direction="row" spacing={2} alignItems="center">
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(_, newMode) => newMode && setViewMode(newMode)}
            size="small"
          >
            <ToggleButton value="monthly">Monthly</ToggleButton>
            <ToggleButton value="ytd">Year-to-Date</ToggleButton>
          </ToggleButtonGroup>
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel>Year</InputLabel>
            <Select
              value={year}
              label="Year"
              onChange={(e) => setYear(e.target.value as number)}
            >
              {years.map((y) => (
                <MenuItem key={y} value={y}>{y}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Month</InputLabel>
            <Select
              value={month}
              label="Month"
              onChange={(e) => setMonth(e.target.value as number)}
            >
              {months.map((m) => (
                <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel>Currency</InputLabel>
            <Select
              value={currency}
              label="Currency"
              onChange={(e) => setCurrency(e.target.value)}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="THB">THB</MenuItem>
              <MenuItem value="USD">USD</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Billing Entity</InputLabel>
            <Select
              value={billingEntity}
              label="Billing Entity"
              onChange={(e) => setBillingEntity(e.target.value)}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="bmasia_th">BMAsia Thailand</MenuItem>
              <MenuItem value="bmasia_hk">BMAsia HK</MenuItem>
            </Select>
          </FormControl>
        </Stack>
      </Box>

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* KPI Cards */}
      {statement && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Total Revenue"
              value={formatCurrency(statement.revenue.total, displayCurrency)}
              subtitle={viewMode === 'monthly' ? `${months.find(m => m.value === month)?.label} ${year}` : `YTD ${year}`}
              icon={<MoneyIcon />}
              color="#1976d2"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Gross Profit"
              value={formatCurrency(statement.gross_profit, displayCurrency)}
              subtitle={`${formatPercent(statement.gross_margin)} margin`}
              icon={<ReceiptIcon />}
              color="#4caf50"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Operating Expenses"
              value={formatCurrency(statement.operating_expenses.total, displayCurrency)}
              subtitle={`COGS: ${formatCurrency(statement.cogs.total, displayCurrency)}`}
              icon={<AccountBalanceIcon />}
              color="#ff9800"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Net Profit"
              value={formatCurrency(statement.net_profit, displayCurrency)}
              subtitle={`${formatPercent(statement.net_margin)} margin`}
              icon={<ChartIcon />}
              color={statement.net_profit >= 0 ? '#4caf50' : '#f44336'}
            />
          </Grid>
        </Grid>
      )}

      {/* P&L Statement Table */}
      {statement && (
        <Box mb={3}>
          <PLStatementTable statement={statement} currency={displayCurrency} />
        </Box>
      )}

      {/* Charts */}
      {trendData.length > 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} lg={6}>
            <TrendChart data={trendData} currency={displayCurrency} />
          </Grid>
          <Grid item xs={12} lg={6}>
            <MarginChart data={trendData} />
          </Grid>
        </Grid>
      )}

      {/* Report Info */}
      {statement && (
        <Box mt={3}>
          <Typography variant="caption" color="text.secondary">
            Period: {statement.period.year} {statement.period.type === 'monthly' ? statement.period.month_name : `YTD through Month ${statement.period.through_month}`} |
            Currency: {statement.currency} |
            Entity: {statement.billing_entity === 'all' ? 'All Entities' : statement.billing_entity}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default ProfitLoss;
