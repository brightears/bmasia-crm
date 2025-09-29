import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Chip,
  Button,
  IconButton,
  GridLegacy as Grid,
  LinearProgress,
  Divider,
  useTheme,
} from '@mui/material';
import {
  Receipt,
  Warning,
  AttachMoney,
  TrendingUp,
  AccountBalance,
  Schedule,
  Send,
  Visibility,
  KeyboardArrowRight,
  MonetizationOn,
} from '@mui/icons-material';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import { Invoice } from '../types';
import ApiService from '../services/api';

interface InvoiceStats {
  total_invoices: number;
  total_amount: number;
  paid_amount: number;
  pending_amount: number;
  overdue_amount: number;
  overdue_count: number;
  monthly_revenue: Array<{
    month: string;
    revenue: number;
  }>;
  status_breakdown: Array<{
    status: string;
    count: number;
    amount: number;
  }>;
  payment_collection_rate: number;
}

const InvoiceWidgets: React.FC = () => {
  const theme = useTheme();
  const [stats, setStats] = useState<InvoiceStats | null>(null);
  const [overdueInvoices, setOverdueInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadInvoiceData();
  }, []);

  const loadInvoiceData = async () => {
    try {
      setLoading(true);
      const [invoiceStats, overdueData] = await Promise.all([
        ApiService.getInvoiceStats(),
        ApiService.getOverdueInvoices(),
      ]);

      setStats(invoiceStats);
      setOverdueInvoices(overdueData.slice(0, 5)); // Show only first 5
    } catch (err: any) {
      setError('Failed to load invoice data');
      console.error('Invoice data error:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: string): string => {
    const colors: { [key: string]: string } = {
      'Draft': '#9e9e9e',
      'Sent': '#2196f3',
      'Paid': '#4caf50',
      'Pending': '#ff9800',
      'Overdue': '#f44336',
      'Cancelled': '#f44336',
      'Refunded': '#9c27b0',
    };
    return colors[status] || '#2196f3';
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !stats) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error || 'Failed to load invoice data'}
      </Alert>
    );
  }


  return (
    <Box>
      {/* Invoice Overview Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <AttachMoney sx={{ color: 'success.main', mr: 1 }} />
                <Typography variant="h6" component="div">
                  {formatCurrency(stats.total_amount)}
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Total Outstanding
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {stats.total_invoices} invoices
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Warning sx={{ color: 'error.main', mr: 1 }} />
                <Typography variant="h6" component="div">
                  {formatCurrency(stats.overdue_amount)}
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Overdue Amount
              </Typography>
              <Typography variant="caption" color="error.main">
                {stats.overdue_count} overdue invoices
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <TrendingUp sx={{ color: 'info.main', mr: 1 }} />
                <Typography variant="h6" component="div">
                  {stats.payment_collection_rate.toFixed(1)}%
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Collection Rate
              </Typography>
              <LinearProgress
                variant="determinate"
                value={stats.payment_collection_rate}
                sx={{ mt: 1, height: 6, borderRadius: 3 }}
                color="info"
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <MonetizationOn sx={{ color: 'primary.main', mr: 1 }} />
                <Typography variant="h6" component="div">
                  {formatCurrency(stats.paid_amount)}
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Paid This Month
              </Typography>
              <Typography variant="caption" color="success.main">
                ↗ Payment received
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* Monthly Revenue Chart */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Monthly Revenue Trend
            </Typography>
            <Box sx={{ height: 300, mt: 2 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={stats.monthly_revenue}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="month"
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => formatCurrency(value)}
                  />
                  <Tooltip
                    formatter={(value: number) => [formatCurrency(value), 'Revenue']}
                    labelStyle={{ color: theme.palette.text.primary }}
                    contentStyle={{
                      backgroundColor: theme.palette.background.paper,
                      border: `1px solid ${theme.palette.divider}`,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="revenue"
                    stroke={theme.palette.primary.main}
                    strokeWidth={3}
                    dot={{ fill: theme.palette.primary.main, strokeWidth: 2, r: 4 }}
                    activeDot={{ r: 6, stroke: theme.palette.primary.main, strokeWidth: 2 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Invoice Status Breakdown */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Invoice Status
            </Typography>
            <Box sx={{ height: 300, mt: 2 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={stats.status_breakdown}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    dataKey="count"
                    nameKey="status"
                    label={({ name, count }) => `${name}: ${count}`}
                  >
                    {stats.status_breakdown.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={getStatusColor(entry.status)}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number, name) => [value, name === 'count' ? 'Invoices' : name]}
                    labelStyle={{ color: theme.palette.text.primary }}
                    contentStyle={{
                      backgroundColor: theme.palette.background.paper,
                      border: `1px solid ${theme.palette.divider}`,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Overdue Invoices Alert */}
        {overdueInvoices.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <Warning sx={{ color: 'error.main', mr: 1 }} />
                  <Typography variant="h6" color="error.main">
                    Overdue Invoices Alert
                  </Typography>
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  endIcon={<KeyboardArrowRight />}
                  href="/invoices?status=Overdue"
                >
                  View All
                </Button>
              </Box>

              <List>
                {overdueInvoices.map((invoice, index) => (
                  <React.Fragment key={invoice.id}>
                    <ListItem>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Typography variant="body1" fontWeight="medium">
                              {invoice.invoice_number} - {invoice.company_name}
                            </Typography>
                            <Typography variant="h6" color="error.main">
                              {formatCurrency(invoice.total_amount)}
                            </Typography>
                          </Box>
                        }
                        secondary={
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Schedule sx={{ fontSize: 16, color: 'text.secondary' }} />
                              <Typography variant="body2" color="text.secondary">
                                Due: {formatDate(invoice.due_date)}
                              </Typography>
                              <Chip
                                label={`${invoice.days_overdue} days overdue`}
                                size="small"
                                color="error"
                              />
                            </Box>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                              <IconButton size="small" title="View Details">
                                <Visibility fontSize="small" />
                              </IconButton>
                              <IconButton size="small" title="Send Reminder">
                                <Send fontSize="small" />
                              </IconButton>
                            </Box>
                          </Box>
                        }
                      />
                    </ListItem>
                    {index < overdueInvoices.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </Paper>
          </Grid>
        )}

        {/* Payment Collection Summary */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Payment Collection Summary
            </Typography>
            <Box sx={{ mt: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="body2">Paid Amount:</Typography>
                <Typography variant="body2" fontWeight="medium" color="success.main">
                  {formatCurrency(stats.paid_amount)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="body2">Pending Amount:</Typography>
                <Typography variant="body2" fontWeight="medium" color="warning.main">
                  {formatCurrency(stats.pending_amount)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="body2">Overdue Amount:</Typography>
                <Typography variant="body2" fontWeight="medium" color="error.main">
                  {formatCurrency(stats.overdue_amount)}
                </Typography>
              </Box>
              <Divider sx={{ my: 2 }} />
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="h6">Total Outstanding:</Typography>
                <Typography variant="h6" color="primary">
                  {formatCurrency(stats.total_amount)}
                </Typography>
              </Box>
            </Box>
          </Paper>
        </Grid>

        {/* Quick Actions */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Quick Actions
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
              <Button
                variant="contained"
                startIcon={<Receipt />}
                href="/invoices?action=create"
                fullWidth
              >
                Create New Invoice
              </Button>
              <Button
                variant="outlined"
                startIcon={<Warning />}
                href="/invoices?status=Overdue"
                color="error"
                fullWidth
              >
                Review Overdue Invoices ({stats.overdue_count})
              </Button>
              <Button
                variant="outlined"
                startIcon={<Send />}
                href="/invoices?status=Draft"
                fullWidth
              >
                Send Draft Invoices
              </Button>
              <Button
                variant="outlined"
                startIcon={<AccountBalance />}
                href="/invoices?status=Pending"
                fullWidth
              >
                Track Pending Payments
              </Button>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default InvoiceWidgets;