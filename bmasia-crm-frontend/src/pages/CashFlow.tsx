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
  Button,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  AccountBalance as AccountBalanceIcon,
  ShowChart as ChartIcon,
  AttachMoney as MoneyIcon,
  Build as BuildIcon,
  PictureAsPdf as PdfIcon,
  TableChart as ExcelIcon,
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
} from 'recharts';

// Backend Cash Flow response interface
interface CashFlowResponse {
  period: {
    year: number;
    month?: number;
    month_name?: string;
    type: string;
  };
  billing_entity: string;
  currency: string;
  operating_activities: {
    cash_from_customers: { count: number; value: number };
    cash_to_suppliers: { count: number; value: number };
    cash_to_employees: { value: number };
    other: number;
    net_cash_from_operations: number;
  };
  investing_activities: {
    capex_purchases: { count: number; value: number };
    asset_sales: number;
    other: number;
    net_cash_from_investing: number;
  };
  financing_activities: {
    loan_proceeds: number;
    loan_repayments: number;
    equity_injections: number;
    dividends_paid: number;
    other: number;
    net_cash_from_financing: number;
  };
  net_change_in_cash: number;
  opening_cash_balance: number;
  closing_cash_balance: number;
}

interface TrendData {
  month: number;
  month_name: string;
  operating: number;
  investing: number;
  financing: number;
  net_change: number;
  closing_balance: number;
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
            {trend.isPositive ? '+' : ''}{formatCurrency(Math.abs(trend.value), 'THB')} vs last year
          </Typography>
        </Box>
      )}
    </CardContent>
  </Card>
);

// Cash Flow Statement Table Component
interface CashFlowTableProps {
  statement: CashFlowResponse;
  currency: string;
}

const CashFlowStatementTable: React.FC<CashFlowTableProps> = ({ statement, currency }) => {
  const periodLabel = statement.period.type === 'ytd'
    ? `Year-to-Date through ${statement.period.month_name || `Month ${statement.period.month}`}`
    : statement.period.month_name;

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow sx={{ backgroundColor: 'grey.100' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold">
                Cash Flow Statement - {periodLabel} {statement.period.year}
              </Typography>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {/* Operating Activities Section */}
          <TableRow sx={{ backgroundColor: '#e3f2fd' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" color="primary">OPERATING ACTIVITIES</Typography>
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>
              Cash received from customers ({statement.operating_activities.cash_from_customers.count})
            </TableCell>
            <TableCell align="right" sx={{ color: '#4caf50' }}>
              {formatCurrency(statement.operating_activities.cash_from_customers.value, currency)}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>
              Cash paid to suppliers ({statement.operating_activities.cash_to_suppliers.count})
            </TableCell>
            <TableCell align="right" sx={{ color: '#d32f2f' }}>
              ({formatCurrency(statement.operating_activities.cash_to_suppliers.value, currency)})
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Cash paid to employees</TableCell>
            <TableCell align="right" sx={{ color: '#d32f2f' }}>
              ({formatCurrency(statement.operating_activities.cash_to_employees.value, currency)})
            </TableCell>
          </TableRow>
          {statement.operating_activities.other !== 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4 }}>Other operating activities</TableCell>
              <TableCell align="right" sx={{ color: statement.operating_activities.other >= 0 ? '#4caf50' : '#d32f2f' }}>
                {statement.operating_activities.other >= 0 ? '' : '('}
                {formatCurrency(Math.abs(statement.operating_activities.other), currency)}
                {statement.operating_activities.other >= 0 ? '' : ')'}
              </TableCell>
            </TableRow>
          )}
          <TableRow sx={{ borderTop: 2, borderColor: 'grey.300' }}>
            <TableCell sx={{ fontWeight: 'bold' }}>Net Cash from Operating Activities</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'bold', color: '#1976d2' }}>
              {formatCurrency(statement.operating_activities.net_cash_from_operations, currency)}
            </TableCell>
          </TableRow>

          {/* Investing Activities Section */}
          <TableRow sx={{ backgroundColor: '#fff3e0' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" sx={{ color: '#ff9800' }}>INVESTING ACTIVITIES</Typography>
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>
              Capital expenditures ({statement.investing_activities.capex_purchases.count})
            </TableCell>
            <TableCell align="right" sx={{ color: '#d32f2f' }}>
              ({formatCurrency(statement.investing_activities.capex_purchases.value, currency)})
            </TableCell>
          </TableRow>
          {statement.investing_activities.asset_sales !== 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4 }}>Proceeds from asset sales</TableCell>
              <TableCell align="right" sx={{ color: '#4caf50' }}>
                {formatCurrency(statement.investing_activities.asset_sales, currency)}
              </TableCell>
            </TableRow>
          )}
          {statement.investing_activities.other !== 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4 }}>Other investing activities</TableCell>
              <TableCell align="right" sx={{ color: statement.investing_activities.other >= 0 ? '#4caf50' : '#d32f2f' }}>
                {statement.investing_activities.other >= 0 ? '' : '('}
                {formatCurrency(Math.abs(statement.investing_activities.other), currency)}
                {statement.investing_activities.other >= 0 ? '' : ')'}
              </TableCell>
            </TableRow>
          )}
          <TableRow sx={{ borderTop: 2, borderColor: 'grey.300' }}>
            <TableCell sx={{ fontWeight: 'bold' }}>Net Cash from Investing Activities</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'bold', color: '#ff9800' }}>
              {formatCurrency(statement.investing_activities.net_cash_from_investing, currency)}
            </TableCell>
          </TableRow>

          {/* Financing Activities Section */}
          <TableRow sx={{ backgroundColor: '#f3e5f5' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" sx={{ color: '#9c27b0' }}>FINANCING ACTIVITIES</Typography>
            </TableCell>
          </TableRow>
          {statement.financing_activities.loan_proceeds !== 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4 }}>Loan proceeds</TableCell>
              <TableCell align="right" sx={{ color: '#4caf50' }}>
                {formatCurrency(statement.financing_activities.loan_proceeds, currency)}
              </TableCell>
            </TableRow>
          )}
          {statement.financing_activities.loan_repayments !== 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4 }}>Loan repayments</TableCell>
              <TableCell align="right" sx={{ color: '#d32f2f' }}>
                ({formatCurrency(statement.financing_activities.loan_repayments, currency)})
              </TableCell>
            </TableRow>
          )}
          {statement.financing_activities.equity_injections !== 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4 }}>Equity injections</TableCell>
              <TableCell align="right" sx={{ color: '#4caf50' }}>
                {formatCurrency(statement.financing_activities.equity_injections, currency)}
              </TableCell>
            </TableRow>
          )}
          {statement.financing_activities.dividends_paid !== 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4 }}>Dividends paid</TableCell>
              <TableCell align="right" sx={{ color: '#d32f2f' }}>
                ({formatCurrency(statement.financing_activities.dividends_paid, currency)})
              </TableCell>
            </TableRow>
          )}
          {statement.financing_activities.other !== 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4 }}>Other financing activities</TableCell>
              <TableCell align="right" sx={{ color: statement.financing_activities.other >= 0 ? '#4caf50' : '#d32f2f' }}>
                {statement.financing_activities.other >= 0 ? '' : '('}
                {formatCurrency(Math.abs(statement.financing_activities.other), currency)}
                {statement.financing_activities.other >= 0 ? '' : ')'}
              </TableCell>
            </TableRow>
          )}
          {statement.financing_activities.net_cash_from_financing === 0 && (
            <TableRow>
              <TableCell sx={{ pl: 4, fontStyle: 'italic' }} colSpan={2}>
                No financing activities recorded
              </TableCell>
            </TableRow>
          )}
          <TableRow sx={{ borderTop: 2, borderColor: 'grey.300' }}>
            <TableCell sx={{ fontWeight: 'bold' }}>Net Cash from Financing Activities</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'bold', color: '#9c27b0' }}>
              {formatCurrency(statement.financing_activities.net_cash_from_financing, currency)}
            </TableCell>
          </TableRow>

          {/* Net Change in Cash */}
          <TableRow sx={{ backgroundColor: statement.net_change_in_cash >= 0 ? '#e8f5e9' : '#ffebee' }}>
            <TableCell>
              <Typography fontWeight="bold" color={statement.net_change_in_cash >= 0 ? 'success.main' : 'error.main'}>
                NET CHANGE IN CASH
              </Typography>
            </TableCell>
            <TableCell align="right">
              <Typography fontWeight="bold" color={statement.net_change_in_cash >= 0 ? 'success.main' : 'error.main'}>
                {formatCurrency(statement.net_change_in_cash, currency)}
              </Typography>
            </TableCell>
          </TableRow>

          {/* Cash Balance */}
          <TableRow>
            <TableCell sx={{ pl: 2 }}>Opening cash balance</TableCell>
            <TableCell align="right">
              {formatCurrency(statement.opening_cash_balance, currency)}
            </TableCell>
          </TableRow>
          <TableRow sx={{ backgroundColor: '#e0f2f1' }}>
            <TableCell>
              <Typography variant="h6" fontWeight="bold">
                CLOSING CASH BALANCE
              </Typography>
            </TableCell>
            <TableCell align="right">
              <Typography variant="h6" fontWeight="bold" color="primary">
                {formatCurrency(statement.closing_cash_balance, currency)}
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
          Monthly Cash Flow Trend
        </Typography>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month_name" />
            <YAxis
              tickFormatter={(value) => `${currencySymbol}${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip
              formatter={(value: number, name: string) => {
                const displayName = name === 'operating' ? 'Operating Activities'
                  : name === 'investing' ? 'Investing Activities'
                  : name === 'financing' ? 'Financing Activities'
                  : name === 'net_change' ? 'Net Change in Cash'
                  : name === 'closing_balance' ? 'Closing Cash Balance'
                  : name;
                return [formatCurrency(value, currency), displayName];
              }}
            />
            <Legend
              formatter={(value) => {
                return value === 'operating' ? 'Operating Activities'
                  : value === 'investing' ? 'Investing Activities'
                  : value === 'financing' ? 'Financing Activities'
                  : value === 'net_change' ? 'Net Change'
                  : value === 'closing_balance' ? 'Cash Balance'
                  : value;
              }}
            />
            <Line
              type="monotone"
              dataKey="operating"
              stroke="#1976d2"
              strokeWidth={2}
              name="operating"
            />
            <Line
              type="monotone"
              dataKey="investing"
              stroke="#ff9800"
              strokeWidth={2}
              name="investing"
            />
            <Line
              type="monotone"
              dataKey="financing"
              stroke="#9c27b0"
              strokeWidth={2}
              name="financing"
            />
            <Line
              type="monotone"
              dataKey="net_change"
              stroke="#4caf50"
              strokeWidth={2}
              strokeDasharray="5 5"
              name="net_change"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// Main Component
const CashFlow: React.FC = () => {
  const [statement, setStatement] = useState<CashFlowResponse | null>(null);
  const [trendData, setTrendData] = useState<TrendData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [month, setMonth] = useState<number>(new Date().getMonth() + 1);
  const [currency, setCurrency] = useState<string>('');
  const [billingEntity, setBillingEntity] = useState<string>('');
  const [viewMode, setViewMode] = useState<'monthly' | 'ytd'>('monthly');
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null);

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
      // Load Cash Flow statement - use raw fetch to get proper response
      const token = localStorage.getItem('bmasia_access_token') || sessionStorage.getItem('bmasia_access_token');
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
      const cfResponse = await fetch(
        `${baseUrl}/api/v1/cash-flow/${endpoint}/?${params.toString()}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!cfResponse.ok) {
        throw new Error(`Failed to load cash flow data: ${cfResponse.statusText}`);
      }

      const statementData: CashFlowResponse = await cfResponse.json();
      setStatement(statementData);

      // Load trend data
      const trendParams = new URLSearchParams();
      trendParams.append('year', year.toString());
      if (currency) trendParams.append('currency', currency);
      if (billingEntity) trendParams.append('billing_entity', billingEntity);

      const trendResponse = await fetch(
        `${baseUrl}/api/v1/cash-flow/trend/?${trendParams.toString()}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (trendResponse.ok) {
        const trendJson = await trendResponse.json();
        // Extract months array from response
        const trend: TrendData[] = trendJson.months || [];
        setTrendData(trend);
      }
    } catch (err: any) {
      console.error('Error loading cash flow data:', err);
      setError(err.message || 'Failed to load cash flow report');
    } finally {
      setLoading(false);
    }
  };

  const handleExportPDF = async () => {
    setExporting('pdf');
    try {
      const token = localStorage.getItem('bmasia_access_token') || sessionStorage.getItem('bmasia_access_token');
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

      const response = await fetch(
        `${baseUrl}/api/v1/cash-flow/export/pdf/?${params.toString()}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `CashFlow_${year}_${viewMode === 'monthly' ? month : `YTD_M${month}`}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Export error:', err);
      setError('Failed to export PDF');
    } finally {
      setExporting(null);
    }
  };

  const handleExportExcel = async () => {
    setExporting('excel');
    try {
      const token = localStorage.getItem('bmasia_access_token') || sessionStorage.getItem('bmasia_access_token');
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

      const response = await fetch(
        `${baseUrl}/api/v1/cash-flow/export/excel/?${params.toString()}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `CashFlow_${year}_${viewMode === 'monthly' ? month : `YTD_M${month}`}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Export error:', err);
      setError('Failed to export Excel');
    } finally {
      setExporting(null);
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
            Cash Flow Statement
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Cash inflows and outflows from operating, investing, and financing activities
          </Typography>
        </Box>
        <Stack direction="row" spacing={2} alignItems="center">
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              size="small"
              startIcon={exporting === 'pdf' ? <CircularProgress size={16} /> : <PdfIcon />}
              onClick={handleExportPDF}
              disabled={exporting !== null || loading}
            >
              PDF
            </Button>
            <Button
              variant="outlined"
              size="small"
              startIcon={exporting === 'excel' ? <CircularProgress size={16} /> : <ExcelIcon />}
              onClick={handleExportExcel}
              disabled={exporting !== null || loading}
            >
              Excel
            </Button>
          </Stack>
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
              title="Net Cash Change"
              value={formatCurrency(statement.net_change_in_cash, displayCurrency)}
              subtitle={viewMode === 'monthly' ? `${months.find(m => m.value === month)?.label} ${year}` : `YTD ${year}`}
              icon={<ChartIcon />}
              color={statement.net_change_in_cash >= 0 ? '#4caf50' : '#f44336'}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Operating Cash Flow"
              value={formatCurrency(statement.operating_activities.net_cash_from_operations, displayCurrency)}
              subtitle="From operations"
              icon={<MoneyIcon />}
              color="#1976d2"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Investing Cash Flow"
              value={formatCurrency(statement.investing_activities.net_cash_from_investing, displayCurrency)}
              subtitle={`CapEx: ${formatCurrency(statement.investing_activities.capex_purchases.value, displayCurrency)}`}
              icon={<BuildIcon />}
              color="#ff9800"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Closing Cash Balance"
              value={formatCurrency(statement.closing_cash_balance, displayCurrency)}
              subtitle={`Opening: ${formatCurrency(statement.opening_cash_balance, displayCurrency)}`}
              icon={<AccountBalanceIcon />}
              color="#00897b"
            />
          </Grid>
        </Grid>
      )}

      {/* Cash Flow Statement Table */}
      {statement && (
        <Box mb={3}>
          <CashFlowStatementTable statement={statement} currency={displayCurrency} />
        </Box>
      )}

      {/* Trend Chart */}
      {trendData.length > 0 && (
        <TrendChart data={trendData} currency={displayCurrency} />
      )}

      {/* Report Info */}
      {statement && (
        <Box mt={3}>
          <Typography variant="caption" color="text.secondary">
            Period: {statement.period.year} {statement.period.type === 'monthly' ? statement.period.month_name : `YTD through ${statement.period.month_name}`} |
            Currency: {statement.currency} |
            Entity: {statement.billing_entity === 'all' ? 'All Entities' : statement.billing_entity}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default CashFlow;
