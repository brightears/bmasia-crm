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
  GridLegacy as Grid,
} from '@mui/material';
import {
  AccountBalance as AccountBalanceIcon,
  BusinessCenter as BusinessIcon,
  TrendingUp as TrendingUpIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

// Backend Balance Sheet response interface
interface BalanceSheetResponse {
  period: {
    year: number;
    quarter: number;
    type: string;
  };
  billing_entity: string;
  currency: string;
  assets: {
    current_assets: {
      cash_and_bank: number;
      accounts_receivable: number;
      other_current_assets: number;
      total: number;
    };
    fixed_assets: {
      gross_fixed_assets: number;
      accumulated_depreciation: number;
      net_fixed_assets: number;
    };
    total: number;
  };
  liabilities: {
    current_liabilities: {
      accounts_payable: number;
      accrued_expenses: number;
      other_current_liabilities: number;
      total: number;
    };
    long_term_liabilities: {
      long_term_debt: number;
      other_long_term: number;
      total: number;
    };
    total: number;
  };
  equity: {
    share_capital: number;
    additional_paid_in_capital: number;
    retained_earnings: number;
    other_equity: number;
    total: number;
  };
  total_liabilities_and_equity: number;
  is_balanced: boolean;
}

interface TrendData {
  quarter: string;
  assets: number;
  liabilities: number;
  equity: number;
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
  isBalanced?: boolean;
}

const KPICard: React.FC<KPICardProps> = ({ title, value, subtitle, icon, color, isBalanced }) => (
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
      {isBalanced !== undefined && (
        <Box mt={1} display="flex" alignItems="center" gap={0.5}>
          {isBalanced ? (
            <>
              <CheckCircleIcon sx={{ color: '#4caf50', fontSize: 18 }} />
              <Typography variant="body2" sx={{ color: '#4caf50' }}>
                Balance sheet is balanced
              </Typography>
            </>
          ) : (
            <>
              <CancelIcon sx={{ color: '#f44336', fontSize: 18 }} />
              <Typography variant="body2" sx={{ color: '#f44336' }}>
                Balance sheet is not balanced
              </Typography>
            </>
          )}
        </Box>
      )}
    </CardContent>
  </Card>
);

// Balance Sheet Table Component
interface BalanceSheetTableProps {
  statement: BalanceSheetResponse;
  currency: string;
}

const BalanceSheetTable: React.FC<BalanceSheetTableProps> = ({ statement, currency }) => {
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow sx={{ backgroundColor: 'grey.100' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold">
                Balance Sheet - Q{statement.period.quarter} {statement.period.year}
              </Typography>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {/* ASSETS Section */}
          <TableRow sx={{ backgroundColor: '#e3f2fd' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" color="primary">ASSETS</Typography>
            </TableCell>
          </TableRow>

          {/* Current Assets */}
          <TableRow>
            <TableCell colSpan={2} sx={{ pl: 2, fontWeight: 'medium', backgroundColor: '#f5f5f5' }}>
              Current Assets
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Cash & Bank</TableCell>
            <TableCell align="right">{formatCurrency(statement.assets.current_assets.cash_and_bank, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Accounts Receivable</TableCell>
            <TableCell align="right">{formatCurrency(statement.assets.current_assets.accounts_receivable, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Other Current Assets</TableCell>
            <TableCell align="right">{formatCurrency(statement.assets.current_assets.other_current_assets, currency)}</TableCell>
          </TableRow>
          <TableRow sx={{ borderTop: 1, borderColor: 'grey.300' }}>
            <TableCell sx={{ pl: 2, fontWeight: 'medium' }}>Total Current Assets</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'medium' }}>
              {formatCurrency(statement.assets.current_assets.total, currency)}
            </TableCell>
          </TableRow>

          {/* Fixed Assets */}
          <TableRow>
            <TableCell colSpan={2} sx={{ pl: 2, fontWeight: 'medium', backgroundColor: '#f5f5f5' }}>
              Fixed Assets
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Gross Fixed Assets</TableCell>
            <TableCell align="right">{formatCurrency(statement.assets.fixed_assets.gross_fixed_assets, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4, color: '#d32f2f' }}>Less: Accumulated Depreciation</TableCell>
            <TableCell align="right" sx={{ color: '#d32f2f' }}>
              ({formatCurrency(statement.assets.fixed_assets.accumulated_depreciation, currency)})
            </TableCell>
          </TableRow>
          <TableRow sx={{ borderTop: 1, borderColor: 'grey.300' }}>
            <TableCell sx={{ pl: 2, fontWeight: 'medium' }}>Net Fixed Assets</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'medium' }}>
              {formatCurrency(statement.assets.fixed_assets.net_fixed_assets, currency)}
            </TableCell>
          </TableRow>

          {/* Total Assets */}
          <TableRow sx={{ borderTop: 2, borderColor: 'grey.400', backgroundColor: '#e3f2fd' }}>
            <TableCell>
              <Typography fontWeight="bold" color="primary">TOTAL ASSETS</Typography>
            </TableCell>
            <TableCell align="right">
              <Typography fontWeight="bold" color="primary">
                {formatCurrency(statement.assets.total, currency)}
              </Typography>
            </TableCell>
          </TableRow>

          {/* LIABILITIES Section */}
          <TableRow sx={{ backgroundColor: '#fff3e0' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" sx={{ color: '#e65100' }}>LIABILITIES</Typography>
            </TableCell>
          </TableRow>

          {/* Current Liabilities */}
          <TableRow>
            <TableCell colSpan={2} sx={{ pl: 2, fontWeight: 'medium', backgroundColor: '#f5f5f5' }}>
              Current Liabilities
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Accounts Payable</TableCell>
            <TableCell align="right">{formatCurrency(statement.liabilities.current_liabilities.accounts_payable, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Accrued Expenses</TableCell>
            <TableCell align="right">{formatCurrency(statement.liabilities.current_liabilities.accrued_expenses, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Other Current Liabilities</TableCell>
            <TableCell align="right">{formatCurrency(statement.liabilities.current_liabilities.other_current_liabilities, currency)}</TableCell>
          </TableRow>
          <TableRow sx={{ borderTop: 1, borderColor: 'grey.300' }}>
            <TableCell sx={{ pl: 2, fontWeight: 'medium' }}>Total Current Liabilities</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'medium' }}>
              {formatCurrency(statement.liabilities.current_liabilities.total, currency)}
            </TableCell>
          </TableRow>

          {/* Long-term Liabilities */}
          <TableRow>
            <TableCell colSpan={2} sx={{ pl: 2, fontWeight: 'medium', backgroundColor: '#f5f5f5' }}>
              Long-term Liabilities
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Long-term Debt</TableCell>
            <TableCell align="right">{formatCurrency(statement.liabilities.long_term_liabilities.long_term_debt, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Other Long-term</TableCell>
            <TableCell align="right">{formatCurrency(statement.liabilities.long_term_liabilities.other_long_term, currency)}</TableCell>
          </TableRow>
          <TableRow sx={{ borderTop: 1, borderColor: 'grey.300' }}>
            <TableCell sx={{ pl: 2, fontWeight: 'medium' }}>Total Long-term Liabilities</TableCell>
            <TableCell align="right" sx={{ fontWeight: 'medium' }}>
              {formatCurrency(statement.liabilities.long_term_liabilities.total, currency)}
            </TableCell>
          </TableRow>

          {/* Total Liabilities */}
          <TableRow sx={{ borderTop: 2, borderColor: 'grey.400', backgroundColor: '#fff3e0' }}>
            <TableCell>
              <Typography fontWeight="bold" sx={{ color: '#e65100' }}>TOTAL LIABILITIES</Typography>
            </TableCell>
            <TableCell align="right">
              <Typography fontWeight="bold" sx={{ color: '#e65100' }}>
                {formatCurrency(statement.liabilities.total, currency)}
              </Typography>
            </TableCell>
          </TableRow>

          {/* EQUITY Section */}
          <TableRow sx={{ backgroundColor: '#e8f5e9' }}>
            <TableCell colSpan={2}>
              <Typography fontWeight="bold" color="success.main">EQUITY</Typography>
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Share Capital</TableCell>
            <TableCell align="right">{formatCurrency(statement.equity.share_capital, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Additional Paid-in Capital</TableCell>
            <TableCell align="right">{formatCurrency(statement.equity.additional_paid_in_capital, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Retained Earnings</TableCell>
            <TableCell align="right">{formatCurrency(statement.equity.retained_earnings, currency)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell sx={{ pl: 4 }}>Other Equity</TableCell>
            <TableCell align="right">{formatCurrency(statement.equity.other_equity, currency)}</TableCell>
          </TableRow>
          <TableRow sx={{ borderTop: 2, borderColor: 'grey.400', backgroundColor: '#e8f5e9' }}>
            <TableCell>
              <Typography fontWeight="bold" color="success.main">TOTAL EQUITY</Typography>
            </TableCell>
            <TableCell align="right">
              <Typography fontWeight="bold" color="success.main">
                {formatCurrency(statement.equity.total, currency)}
              </Typography>
            </TableCell>
          </TableRow>

          {/* Total Liabilities & Equity */}
          <TableRow sx={{ backgroundColor: statement.is_balanced ? '#c8e6c9' : '#ffcdd2' }}>
            <TableCell>
              <Typography variant="h6" fontWeight="bold">
                TOTAL LIABILITIES & EQUITY
              </Typography>
            </TableCell>
            <TableCell align="right">
              <Typography variant="h6" fontWeight="bold" color={statement.is_balanced ? 'success.main' : 'error.main'}>
                {formatCurrency(statement.total_liabilities_and_equity, currency)}
              </Typography>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </TableContainer>
  );
};

// Quarterly Trend Chart Component
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
          Quarterly Balance Sheet Trend
        </Typography>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="quarter" />
            <YAxis
              tickFormatter={(value) => `${currencySymbol}${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip
              formatter={(value: number, name: string) => {
                const displayName = name === 'assets' ? 'Total Assets'
                  : name === 'liabilities' ? 'Total Liabilities'
                  : name === 'equity' ? 'Total Equity'
                  : name;
                return [formatCurrency(value, currency), displayName];
              }}
            />
            <Legend
              formatter={(value) => {
                return value === 'assets' ? 'Total Assets'
                  : value === 'liabilities' ? 'Total Liabilities'
                  : value === 'equity' ? 'Total Equity'
                  : value;
              }}
            />
            <Bar dataKey="assets" fill="#1976d2" name="assets" />
            <Bar dataKey="liabilities" fill="#e65100" name="liabilities" />
            <Bar dataKey="equity" fill="#4caf50" name="equity" />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// Main Component
const BalanceSheet: React.FC = () => {
  const [statement, setStatement] = useState<BalanceSheetResponse | null>(null);
  const [trendData, setTrendData] = useState<TrendData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [quarter, setQuarter] = useState<number>(Math.ceil((new Date().getMonth() + 1) / 3));
  const [currency, setCurrency] = useState<string>('');
  const [billingEntity, setBillingEntity] = useState<string>('');

  const quarters = [
    { value: 1, label: 'Q1' },
    { value: 2, label: 'Q2' },
    { value: 3, label: 'Q3' },
    { value: 4, label: 'Q4' },
  ];

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i);

  useEffect(() => {
    loadData();
  }, [year, quarter, currency, billingEntity]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Load Balance Sheet - use raw fetch to get proper response
      const token = localStorage.getItem('accessToken');
      const baseUrl = process.env.REACT_APP_API_URL || '';

      const params = new URLSearchParams();
      params.append('year', year.toString());
      params.append('quarter', quarter.toString());
      if (currency) params.append('currency', currency);
      if (billingEntity) params.append('billing_entity', billingEntity);

      const bsResponse = await fetch(
        `${baseUrl}/api/v1/balance-sheet/quarterly/?${params.toString()}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!bsResponse.ok) {
        throw new Error(`Failed to load balance sheet data: ${bsResponse.statusText}`);
      }

      const statementData: BalanceSheetResponse = await bsResponse.json();
      setStatement(statementData);

      // Load trend data
      const trendParams = new URLSearchParams();
      trendParams.append('year', year.toString());
      if (currency) trendParams.append('currency', currency);
      if (billingEntity) trendParams.append('billing_entity', billingEntity);

      const trendResponse = await fetch(
        `${baseUrl}/api/v1/balance-sheet/trend/?${trendParams.toString()}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (trendResponse.ok) {
        const trendJson = await trendResponse.json();
        // Extract quarters array from response
        const trend: TrendData[] = trendJson.quarters || trendJson;
        setTrendData(trend);
      }
    } catch (err: any) {
      console.error('Error loading balance sheet data:', err);
      setError(err.message || 'Failed to load balance sheet report');
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
            Balance Sheet
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Financial position showing assets, liabilities, and equity
          </Typography>
        </Box>
        <Stack direction="row" spacing={2} alignItems="center">
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
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel>Quarter</InputLabel>
            <Select
              value={quarter}
              label="Quarter"
              onChange={(e) => setQuarter(e.target.value as number)}
            >
              {quarters.map((q) => (
                <MenuItem key={q.value} value={q.value}>{q.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel>Entity</InputLabel>
            <Select
              value={billingEntity}
              label="Entity"
              onChange={(e) => setBillingEntity(e.target.value)}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="bmasia_th">BMAsia Thailand</MenuItem>
              <MenuItem value="bmasia_hk">BMAsia HK</MenuItem>
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
              title="Total Assets"
              value={formatCurrency(statement.assets.total, displayCurrency)}
              subtitle={`Q${quarter} ${year}`}
              icon={<AccountBalanceIcon />}
              color="#1976d2"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Total Liabilities"
              value={formatCurrency(statement.liabilities.total, displayCurrency)}
              subtitle={`Current: ${formatCurrency(statement.liabilities.current_liabilities.total, displayCurrency)}`}
              icon={<BusinessIcon />}
              color="#e65100"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Total Equity"
              value={formatCurrency(statement.equity.total, displayCurrency)}
              subtitle={`Retained: ${formatCurrency(statement.equity.retained_earnings, displayCurrency)}`}
              icon={<TrendingUpIcon />}
              color="#4caf50"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Balance Check"
              value={statement.is_balanced ? 'Balanced' : 'Not Balanced'}
              icon={statement.is_balanced ? <CheckCircleIcon /> : <CancelIcon />}
              color={statement.is_balanced ? '#4caf50' : '#f44336'}
              isBalanced={statement.is_balanced}
            />
          </Grid>
        </Grid>
      )}

      {/* Balance Sheet Table */}
      {statement && (
        <Box mb={3}>
          <BalanceSheetTable statement={statement} currency={displayCurrency} />
        </Box>
      )}

      {/* Quarterly Trend Chart */}
      {trendData.length > 0 && (
        <TrendChart data={trendData} currency={displayCurrency} />
      )}

      {/* Report Info */}
      {statement && (
        <Box mt={3}>
          <Typography variant="caption" color="text.secondary">
            Period: Q{statement.period.quarter} {statement.period.year} |
            Currency: {statement.currency} |
            Entity: {statement.billing_entity === 'all' ? 'All Entities' : statement.billing_entity} |
            Balanced: {statement.is_balanced ? 'Yes' : 'No'}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default BalanceSheet;
