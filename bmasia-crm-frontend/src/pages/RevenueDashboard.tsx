import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  FormControl,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  GridLegacy as Grid,
  Alert,
  CircularProgress,
  SelectChangeEvent,
  Button,
  Snackbar,
  Tooltip,
  IconButton,
  Menu,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  TrendingUp,
  Autorenew,
  AddCircle,
  RemoveCircle,
  Refresh,
  Settings,
  PlayArrow,
  MoreVert,
} from '@mui/icons-material';
import { MonthlyRevenueData } from '../types';
import ApiService from '../services/api';

interface KPICardProps {
  title: string;
  value: string;
  count: number;
  icon: React.ReactNode;
  color: string;
}

const KPICard: React.FC<KPICardProps> = ({ title, value, count, icon, color }) => {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Box
            sx={{
              backgroundColor: color,
              borderRadius: '50%',
              width: 48,
              height: 48,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
            }}
          >
            {icon}
          </Box>
          <Typography variant="caption" color="text.secondary">
            {count} contracts
          </Typography>
        </Box>
        <Typography variant="h4" component="div" sx={{ mb: 0.5, fontWeight: 600 }}>
          {value}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {title}
        </Typography>
      </CardContent>
    </Card>
  );
};

const RevenueDashboard: React.FC = () => {
  const currentYear = new Date().getFullYear();
  const [selectedYear, setSelectedYear] = useState<number>(currentYear);
  const [currency, setCurrency] = useState<string>('USD');
  const [billingEntity, setBillingEntity] = useState<string>('bmasia_th');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [monthlyData, setMonthlyData] = useState<MonthlyRevenueData[]>([]);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);

  // Generate year options (current year and 3 years back)
  const yearOptions = Array.from({ length: 4 }, (_, i) => currentYear - i);

  useEffect(() => {
    loadRevenueData();
  }, [selectedYear, currency, billingEntity]);

  const loadRevenueData = async () => {
    try {
      setLoading(true);
      setError('');

      const response = await ApiService.getRevenueMonthly(selectedYear, currency, billingEntity);

      // Transform API response to component format
      const months = response.months || [];
      const monthNames = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
      ];

      // Fill in all 12 months with data or zeros
      const transformedData: MonthlyRevenueData[] = monthNames.map((name, index) => {
        const monthNum = index + 1;
        const monthData = months.find((m: any) => m.month === monthNum);

        return {
          month: monthNum,
          month_name: name,
          new: monthData?.new || { count: 0, value: 0 },
          renewal: monthData?.renewal || { count: 0, value: 0 },
          addon: monthData?.addon || { count: 0, value: 0 },
          churn: monthData?.churn || { count: 0, value: 0 },
        };
      });

      setMonthlyData(transformedData);
    } catch (err: any) {
      console.error('Revenue dashboard error:', err);
      setError('Failed to load revenue data. Make sure to initialize the finance module first.');
    } finally {
      setLoading(false);
    }
  };

  const handleYearChange = (event: SelectChangeEvent<number>) => {
    setSelectedYear(event.target.value as number);
  };

  const handleCurrencyChange = (event: SelectChangeEvent<string>) => {
    setCurrency(event.target.value);
  };

  const handleEntityChange = (event: SelectChangeEvent<string>) => {
    setBillingEntity(event.target.value);
  };

  const handleInitialize = async () => {
    setActionLoading('initialize');
    try {
      const result = await ApiService.initializeRevenueModule();
      setSnackbar({
        open: true,
        message: result.message || 'Finance module initialized successfully',
        severity: 'success',
      });
      loadRevenueData();
    } catch (err: any) {
      setSnackbar({
        open: true,
        message: err.response?.data?.error || 'Failed to initialize finance module',
        severity: 'error',
      });
    } finally {
      setActionLoading(null);
      setMenuAnchor(null);
    }
  };

  const handleClassifyContracts = async () => {
    setActionLoading('classify');
    try {
      const result = await ApiService.classifyContracts(true);
      setSnackbar({
        open: true,
        message: result.message || 'Contracts classified successfully',
        severity: 'success',
      });
      loadRevenueData();
    } catch (err: any) {
      setSnackbar({
        open: true,
        message: err.response?.data?.error || 'Failed to classify contracts',
        severity: 'error',
      });
    } finally {
      setActionLoading(null);
      setMenuAnchor(null);
    }
  };

  const handleGenerateSnapshots = async () => {
    setActionLoading('generate');
    try {
      const result = await ApiService.generateRevenueSnapshots(selectedYear, undefined, true);
      setSnackbar({
        open: true,
        message: result.message || 'Snapshots generated successfully',
        severity: 'success',
      });
      loadRevenueData();
    } catch (err: any) {
      setSnackbar({
        open: true,
        message: err.response?.data?.error || 'Failed to generate snapshots',
        severity: 'error',
      });
    } finally {
      setActionLoading(null);
      setMenuAnchor(null);
    }
  };

  const calculateYTDTotals = () => {
    const currentMonth = new Date().getMonth() + 1;
    const relevantMonths = selectedYear === currentYear
      ? monthlyData.slice(0, currentMonth)
      : monthlyData;

    return {
      new: relevantMonths.reduce((sum, m) => sum + m.new.value, 0),
      newCount: relevantMonths.reduce((sum, m) => sum + m.new.count, 0),
      renewal: relevantMonths.reduce((sum, m) => sum + m.renewal.value, 0),
      renewalCount: relevantMonths.reduce((sum, m) => sum + m.renewal.count, 0),
      addon: relevantMonths.reduce((sum, m) => sum + m.addon.value, 0),
      addonCount: relevantMonths.reduce((sum, m) => sum + m.addon.count, 0),
      churn: relevantMonths.reduce((sum, m) => sum + m.churn.value, 0),
      churnCount: relevantMonths.reduce((sum, m) => sum + m.churn.count, 0),
    };
  };

  const formatCurrency = (value: number): string => {
    const locale = currency === 'THB' ? 'th-TH' : 'en-US';
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(Math.abs(value));
  };

  const getMonthTotal = (month: MonthlyRevenueData): number => {
    return month.new.value + month.renewal.value + month.addon.value + month.churn.value;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  const ytdTotals = calculateYTDTotals();
  const hasData = monthlyData.some(m => m.new.count > 0 || m.renewal.count > 0 || m.addon.count > 0 || m.churn.count > 0);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Revenue Dashboard
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Year-to-date revenue breakdown by category
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <Select value={currency} onChange={handleCurrencyChange}>
              <MenuItem value="USD">USD</MenuItem>
              <MenuItem value="THB">THB</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <Select value={billingEntity} onChange={handleEntityChange}>
              <MenuItem value="bmasia_th">Thailand</MenuItem>
              <MenuItem value="bmasia_hk">Hong Kong</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <Select value={selectedYear} onChange={handleYearChange}>
              {yearOptions.map((year) => (
                <MenuItem key={year} value={year}>
                  {year}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Tooltip title="Refresh data">
            <IconButton onClick={loadRevenueData} disabled={loading}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <IconButton onClick={(e) => setMenuAnchor(e.currentTarget)}>
            <MoreVert />
          </IconButton>
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={() => setMenuAnchor(null)}
          >
            <MenuItem onClick={handleInitialize} disabled={actionLoading !== null}>
              <ListItemIcon>
                {actionLoading === 'initialize' ? <CircularProgress size={20} /> : <Settings fontSize="small" />}
              </ListItemIcon>
              <ListItemText>Initialize Finance Module</ListItemText>
            </MenuItem>
            <MenuItem onClick={handleClassifyContracts} disabled={actionLoading !== null}>
              <ListItemIcon>
                {actionLoading === 'classify' ? <CircularProgress size={20} /> : <PlayArrow fontSize="small" />}
              </ListItemIcon>
              <ListItemText>Classify All Contracts</ListItemText>
            </MenuItem>
            <MenuItem onClick={handleGenerateSnapshots} disabled={actionLoading !== null}>
              <ListItemIcon>
                {actionLoading === 'generate' ? <CircularProgress size={20} /> : <Refresh fontSize="small" />}
              </ListItemIcon>
              <ListItemText>Generate {selectedYear} Snapshots</ListItemText>
            </MenuItem>
          </Menu>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {!hasData && !error && (
        <Alert severity="info" sx={{ mb: 3 }}>
          No revenue data found for {selectedYear}. Click the menu (⋮) to initialize the finance module or generate snapshots.
        </Alert>
      )}

      {/* KPI Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="New Business"
            value={formatCurrency(ytdTotals.new)}
            count={ytdTotals.newCount}
            icon={<TrendingUp />}
            color="#FFA500"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Renewals"
            value={formatCurrency(ytdTotals.renewal)}
            count={ytdTotals.renewalCount}
            icon={<Autorenew />}
            color="#4CAF50"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Add-ons"
            value={formatCurrency(ytdTotals.addon)}
            count={ytdTotals.addonCount}
            icon={<AddCircle />}
            color="#2196F3"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Churned"
            value={formatCurrency(ytdTotals.churn)}
            count={ytdTotals.churnCount}
            icon={<RemoveCircle />}
            color="#F44336"
          />
        </Grid>
      </Grid>

      {/* Monthly Breakdown Table */}
      <Paper sx={{ width: '100%', overflow: 'hidden' }}>
        <TableContainer sx={{ maxHeight: 600 }}>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  Month
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  New Business
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  Renewals
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  Add-ons
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  Churned
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  Total
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {monthlyData.map((month) => {
                const total = getMonthTotal(month);
                return (
                  <TableRow
                    key={month.month}
                    hover
                    sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                  >
                    <TableCell component="th" scope="row" sx={{ fontWeight: 500 }}>
                      {month.month_name}
                    </TableCell>
                    <TableCell align="right">
                      <Box>
                        <Typography variant="body2">
                          {formatCurrency(month.new.value)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {month.new.count} contracts
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Box>
                        <Typography variant="body2">
                          {formatCurrency(month.renewal.value)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {month.renewal.count} contracts
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Box>
                        <Typography variant="body2">
                          {formatCurrency(month.addon.value)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {month.addon.count} contracts
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Box>
                        <Typography variant="body2" color="error">
                          {month.churn.value < 0 ? '-' : ''}{formatCurrency(month.churn.value)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {month.churn.count} contracts
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 600,
                          color: total >= 0 ? 'success.main' : 'error.main',
                        }}
                      >
                        {formatCurrency(total)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default RevenueDashboard;
