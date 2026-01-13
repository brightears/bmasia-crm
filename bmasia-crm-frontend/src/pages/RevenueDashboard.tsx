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
  Grid,
  Alert,
  CircularProgress,
  SelectChangeEvent,
} from '@mui/material';
import {
  TrendingUp,
  Autorenew,
  AddCircle,
  RemoveCircle,
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
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [monthlyData, setMonthlyData] = useState<MonthlyRevenueData[]>([]);

  // Generate year options (current year and 3 years back)
  const yearOptions = Array.from({ length: 4 }, (_, i) => currentYear - i);

  useEffect(() => {
    loadRevenueData();
  }, [selectedYear]);

  const loadRevenueData = async () => {
    try {
      setLoading(true);
      setError('');
      // For now, using mock data until backend is ready
      const mockData: MonthlyRevenueData[] = generateMockData(selectedYear);
      setMonthlyData(mockData);
    } catch (err: any) {
      setError('Failed to load revenue data');
      console.error('Revenue dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  const generateMockData = (year: number): MonthlyRevenueData[] => {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];

    return months.map((month, index) => ({
      month: index + 1,
      month_name: month,
      new: {
        count: Math.floor(Math.random() * 10) + 3,
        value: Math.floor(Math.random() * 50000) + 20000,
      },
      renewal: {
        count: Math.floor(Math.random() * 15) + 5,
        value: Math.floor(Math.random() * 80000) + 40000,
      },
      addon: {
        count: Math.floor(Math.random() * 5) + 1,
        value: Math.floor(Math.random() * 20000) + 5000,
      },
      churn: {
        count: Math.floor(Math.random() * 3),
        value: -Math.floor(Math.random() * 15000),
      },
    }));
  };

  const handleYearChange = (event: SelectChangeEvent<number>) => {
    setSelectedYear(event.target.value as number);
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
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
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
        <FormControl sx={{ minWidth: 120 }}>
          <Select
            value={selectedYear}
            onChange={handleYearChange}
            size="small"
          >
            {yearOptions.map((year) => (
              <MenuItem key={year} value={year}>
                {year}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
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
    </Box>
  );
};

export default RevenueDashboard;
