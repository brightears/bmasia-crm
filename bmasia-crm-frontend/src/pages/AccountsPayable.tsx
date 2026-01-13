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
  IconButton,
  Collapse,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  Tooltip,
  LinearProgress,
  Stack,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  KeyboardArrowDown as ExpandMoreIcon,
  KeyboardArrowUp as ExpandLessIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Schedule as ScheduleIcon,
  AttachMoney as MoneyIcon,
} from '@mui/icons-material';
import api from '../services/api';
import { APAgingReport, APAgingSummary, APVendorDetail, APExpenseDetail } from '../types';

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
  trend?: 'good' | 'warning' | 'danger';
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
        <Box mt={1}>
          <Chip
            size="small"
            label={trend === 'good' ? 'All Current' : trend === 'warning' ? 'Some Overdue' : 'Action Required'}
            color={trend === 'good' ? 'success' : trend === 'warning' ? 'warning' : 'error'}
            variant="outlined"
          />
        </Box>
      )}
    </CardContent>
  </Card>
);

// Aging Distribution Bar
interface AgingBarProps {
  summary: APAgingSummary;
  currency: string;
}

const AgingDistributionBar: React.FC<AgingBarProps> = ({ summary, currency }) => {
  const total = summary.total_ap || 1;
  const buckets = [
    { label: 'Current', value: summary.current, color: '#4caf50' },
    { label: '1-30', value: summary['1_30'], color: '#ff9800' },
    { label: '31-60', value: summary['31_60'], color: '#f57c00' },
    { label: '61-90', value: summary['61_90'], color: '#e65100' },
    { label: '90+', value: summary['90_plus'], color: '#d32f2f' },
  ];

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          AP Aging Distribution
        </Typography>

        {/* Stacked Bar */}
        <Box sx={{ display: 'flex', height: 32, borderRadius: 1, overflow: 'hidden', mb: 2 }}>
          {buckets.map((bucket) => {
            const percent = (bucket.value / total) * 100;
            if (percent === 0) return null;
            return (
              <Tooltip
                key={bucket.label}
                title={`${bucket.label}: ${formatCurrency(bucket.value, currency)} (${formatPercent(percent)})`}
              >
                <Box
                  sx={{
                    width: `${percent}%`,
                    backgroundColor: bucket.color,
                    transition: 'width 0.3s ease',
                    minWidth: percent > 0 ? '2%' : 0,
                  }}
                />
              </Tooltip>
            );
          })}
        </Box>

        {/* Legend */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          {buckets.map((bucket) => (
            <Box key={bucket.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box sx={{ width: 12, height: 12, borderRadius: 0.5, backgroundColor: bucket.color }} />
              <Typography variant="body2" color="text.secondary">
                {bucket.label}: {formatCurrency(bucket.value, currency)}
              </Typography>
            </Box>
          ))}
        </Box>
      </CardContent>
    </Card>
  );
};

// Vendor Row Component (expandable)
interface VendorRowProps {
  vendor: APVendorDetail;
  currency: string;
}

const VendorRow: React.FC<VendorRowProps> = ({ vendor, currency }) => {
  const [open, setOpen] = useState(false);

  const getAgingColor = (bucket: string) => {
    switch (bucket) {
      case 'current': return 'success';
      case '1_30': return 'warning';
      case '31_60': return 'warning';
      case '61_90': return 'error';
      case '90_plus': return 'error';
      default: return 'default';
    }
  };

  const hasOverdue = vendor['1_30'] > 0 || vendor['31_60'] > 0 || vendor['61_90'] > 0 || vendor['90_plus'] > 0;

  return (
    <>
      <TableRow sx={{ '& > *': { borderBottom: 'unset' }, cursor: 'pointer' }} onClick={() => setOpen(!open)}>
        <TableCell>
          <IconButton size="small">
            {open ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        </TableCell>
        <TableCell>
          <Box display="flex" alignItems="center" gap={1}>
            <Typography fontWeight="medium">{vendor.vendor_name}</Typography>
            {hasOverdue && (
              <Tooltip title="Has overdue expenses">
                <WarningIcon color="warning" fontSize="small" />
              </Tooltip>
            )}
          </Box>
        </TableCell>
        <TableCell align="right">{formatCurrency(vendor.total, currency)}</TableCell>
        <TableCell align="right" sx={{ color: '#4caf50' }}>{formatCurrency(vendor.current, currency)}</TableCell>
        <TableCell align="right" sx={{ color: vendor['1_30'] > 0 ? '#ff9800' : 'inherit' }}>
          {formatCurrency(vendor['1_30'], currency)}
        </TableCell>
        <TableCell align="right" sx={{ color: vendor['31_60'] > 0 ? '#f57c00' : 'inherit' }}>
          {formatCurrency(vendor['31_60'], currency)}
        </TableCell>
        <TableCell align="right" sx={{ color: vendor['61_90'] > 0 ? '#e65100' : 'inherit' }}>
          {formatCurrency(vendor['61_90'], currency)}
        </TableCell>
        <TableCell align="right" sx={{ color: vendor['90_plus'] > 0 ? '#d32f2f' : 'inherit' }}>
          {formatCurrency(vendor['90_plus'], currency)}
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={8}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 2 }}>
              <Typography variant="subtitle2" gutterBottom component="div">
                Expense Details ({vendor.expenses.length} items)
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Description</TableCell>
                    <TableCell>Invoice #</TableCell>
                    <TableCell>Category</TableCell>
                    <TableCell>Due Date</TableCell>
                    <TableCell align="right">Amount</TableCell>
                    <TableCell align="right">Days Overdue</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {vendor.expenses.map((expense: APExpenseDetail) => (
                    <TableRow key={expense.expense_id}>
                      <TableCell>{expense.description}</TableCell>
                      <TableCell>{expense.vendor_invoice_number || '-'}</TableCell>
                      <TableCell>{expense.category_name}</TableCell>
                      <TableCell>{expense.due_date || '-'}</TableCell>
                      <TableCell align="right">{formatCurrency(expense.amount, currency)}</TableCell>
                      <TableCell align="right">
                        {expense.days_overdue > 0 ? (
                          <Chip
                            size="small"
                            label={`${expense.days_overdue} days`}
                            color={getAgingColor(expense.aging_bucket)}
                          />
                        ) : (
                          <Chip size="small" label="Current" color="success" />
                        )}
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={expense.status}
                          color={expense.status === 'paid' ? 'success' : expense.status === 'approved' ? 'info' : 'default'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
};

// Main Component
const AccountsPayable: React.FC = () => {
  const [report, setReport] = useState<APAgingReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currency, setCurrency] = useState<string>('');
  const [billingEntity, setBillingEntity] = useState<string>('');

  useEffect(() => {
    loadReport();
  }, [currency, billingEntity]);

  const loadReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAPAgingReport(
        currency || undefined,
        billingEntity || undefined
      );
      setReport(data);
    } catch (err: any) {
      console.error('Error loading AP aging report:', err);
      setError(err.message || 'Failed to load AP aging report');
    } finally {
      setLoading(false);
    }
  };

  if (loading && !report) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  const summary = report?.summary || {
    total_ap: 0,
    current: 0,
    '1_30': 0,
    '31_60': 0,
    '61_90': 0,
    '90_plus': 0,
    expense_count: 0,
  };

  const overdueTotal = summary['1_30'] + summary['31_60'] + summary['61_90'] + summary['90_plus'];
  const criticalTotal = summary['61_90'] + summary['90_plus'];
  const displayCurrency = currency || 'THB';

  // Determine trend status
  const getTrend = (): 'good' | 'warning' | 'danger' => {
    if (criticalTotal > 0) return 'danger';
    if (overdueTotal > 0) return 'warning';
    return 'good';
  };

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight="bold">
            Accounts Payable Aging
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Track outstanding vendor bills and payment priorities
          </Typography>
        </Box>
        <Stack direction="row" spacing={2}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
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
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Total AP Outstanding"
            value={formatCurrency(summary.total_ap, displayCurrency)}
            subtitle={`${summary.expense_count} expenses`}
            icon={<MoneyIcon />}
            color="#1976d2"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Current (Not Yet Due)"
            value={formatCurrency(summary.current, displayCurrency)}
            subtitle={summary.total_ap > 0 ? `${formatPercent((summary.current / summary.total_ap) * 100)} of total` : '0%'}
            icon={<CheckCircleIcon />}
            color="#4caf50"
            trend="good"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Overdue (1-60 Days)"
            value={formatCurrency(summary['1_30'] + summary['31_60'], displayCurrency)}
            subtitle="Action recommended"
            icon={<ScheduleIcon />}
            color="#ff9800"
            trend={overdueTotal > 0 ? 'warning' : 'good'}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Critical (60+ Days)"
            value={formatCurrency(criticalTotal, displayCurrency)}
            subtitle="Urgent action required"
            icon={<WarningIcon />}
            color="#d32f2f"
            trend={criticalTotal > 0 ? 'danger' : 'good'}
          />
        </Grid>
      </Grid>

      {/* Aging Distribution Bar */}
      {report && <AgingDistributionBar summary={summary} currency={displayCurrency} />}

      {/* Vendor Breakdown Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            AP by Vendor
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow sx={{ backgroundColor: 'grey.50' }}>
                  <TableCell width={50} />
                  <TableCell>Vendor</TableCell>
                  <TableCell align="right">Total</TableCell>
                  <TableCell align="right">Current</TableCell>
                  <TableCell align="right">1-30 Days</TableCell>
                  <TableCell align="right">31-60 Days</TableCell>
                  <TableCell align="right">61-90 Days</TableCell>
                  <TableCell align="right">90+ Days</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {report?.by_vendor && report.by_vendor.length > 0 ? (
                  report.by_vendor.map((vendor) => (
                    <VendorRow key={vendor.vendor_id} vendor={vendor} currency={displayCurrency} />
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={8} align="center">
                      <Typography color="text.secondary" py={4}>
                        No outstanding expenses found
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Report Info */}
      {report && (
        <Box mt={2}>
          <Typography variant="caption" color="text.secondary">
            Report generated as of: {report.as_of_date} |
            Currency: {report.currency} |
            Entity: {report.billing_entity === 'all' ? 'All Entities' : report.billing_entity}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default AccountsPayable;
