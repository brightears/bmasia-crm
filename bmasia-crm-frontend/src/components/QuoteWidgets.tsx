import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  Button,
  IconButton,
  CircularProgress,
  Alert,
  Divider,
  LinearProgress,
  GridLegacy as Grid,
  useTheme,
} from '@mui/material';
import {
  RequestQuote,
  TrendingUp,
  Schedule,
  CheckCircle,
  Visibility,
  Send,
  Warning,
  AttachMoney,
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, ComposedChart } from 'recharts';
import { Quote } from '../types';
import ApiService from '../services/api';

interface QuoteStats {
  total_quotes: number;
  pending_quotes: number;
  accepted_quotes: number;
  expired_quotes: number;
  total_value: number;
  acceptance_rate: number;
  average_value: number;
  quotes_expiring_soon: number;
}

const QuoteWidgets: React.FC = () => {
  const theme = useTheme();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [stats, setStats] = useState<QuoteStats | null>(null);
  const [expiringQuotes, setExpiringQuotes] = useState<Quote[]>([]);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [statusDistribution, setStatusDistribution] = useState<any[]>([]);

  useEffect(() => {
    loadQuoteData();
  }, []);

  const loadQuoteData = async () => {
    try {
      setLoading(true);
      const [statsResponse, expiringResponse] = await Promise.all([
        ApiService.getQuoteStats(),
        ApiService.getExpiringQuotes(),
      ]);

      setStats(statsResponse);
      setExpiringQuotes(expiringResponse);

      // Generate mock trend data (replace with real API data)
      const trendData = Array.from({ length: 6 }, (_, i) => {
        const date = new Date();
        date.setMonth(date.getMonth() - i);
        return {
          month: date.toLocaleDateString('en-US', { month: 'short' }),
          quotes: Math.floor(Math.random() * 50) + 20,
          value: Math.floor(Math.random() * 100000) + 50000,
        };
      }).reverse();
      setTrendData(trendData);

      // Generate status distribution
      if (statsResponse) {
        const distribution = [
          { name: 'Sent', value: statsResponse.pending_quotes, color: '#2196f3' },
          { name: 'Accepted', value: statsResponse.accepted_quotes, color: '#4caf50' },
          { name: 'Expired', value: statsResponse.expired_quotes, color: '#ff9800' },
          { name: 'Draft', value: Math.max(0, statsResponse.total_quotes - statsResponse.pending_quotes - statsResponse.accepted_quotes - statsResponse.expired_quotes), color: '#9e9e9e' },
        ].filter(item => item.value > 0);
        setStatusDistribution(distribution);
      }
    } catch (err) {
      setError('Failed to load quote data');
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
    switch (status) {
      case 'Draft': return '#9e9e9e';
      case 'Sent': return '#2196f3';
      case 'Accepted': return '#4caf50';
      case 'Rejected': return '#f44336';
      case 'Expired': return '#ff9800';
      default: return '#2196f3';
    }
  };

  if (loading) {
    return (
      <Grid container spacing={3}>
        {Array.from({ length: 4 }, (_, i) => (
          <Grid item xs={12} md={6} lg={3} key={i}>
            <Card>
              <CardContent sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 3 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Grid container spacing={3}>
      {/* KPI Cards */}
      <Grid item xs={12} sm={6} lg={3}>
        <Card sx={{ bgcolor: 'primary.main', color: 'primary.contrastText' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h4" fontWeight="bold">
                  {stats?.total_quotes || 0}
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }}>
                  Total Quotes
                </Typography>
              </Box>
              <RequestQuote sx={{ fontSize: 40, opacity: 0.8 }} />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} lg={3}>
        <Card sx={{ bgcolor: 'success.main', color: 'success.contrastText' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h4" fontWeight="bold">
                  {stats?.acceptance_rate?.toFixed(1) || '0.0'}%
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }}>
                  Acceptance Rate
                </Typography>
              </Box>
              <CheckCircle sx={{ fontSize: 40, opacity: 0.8 }} />
            </Box>
            <LinearProgress
              variant="determinate"
              value={stats?.acceptance_rate || 0}
              sx={{ mt: 2, bgcolor: 'rgba(255,255,255,0.2)', '& .MuiLinearProgress-bar': { bgcolor: 'rgba(255,255,255,0.8)' } }}
            />
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} lg={3}>
        <Card sx={{ bgcolor: 'info.main', color: 'info.contrastText' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h4" fontWeight="bold">
                  {formatCurrency(stats?.total_value || 0)}
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }}>
                  Total Quote Value
                </Typography>
              </Box>
              <AttachMoney sx={{ fontSize: 40, opacity: 0.8 }} />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} lg={3}>
        <Card sx={{ bgcolor: 'warning.main', color: 'warning.contrastText' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h4" fontWeight="bold">
                  {stats?.quotes_expiring_soon || 0}
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }}>
                  Expiring Soon
                </Typography>
              </Box>
              <Schedule sx={{ fontSize: 40, opacity: 0.8 }} />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* Quote Trend Chart */}
      <Grid item xs={12} lg={8}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
              <TrendingUp sx={{ mr: 1 }} />
              Quote Trends (Last 6 Months)
            </Typography>
            <Box sx={{ height: 300, width: '100%' }}>
              <ResponsiveContainer>
                <ComposedChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis yAxisId="left" />
                  <YAxis yAxisId="right" orientation="right" />
                  <Tooltip
                    formatter={(value: any, name: string) => {
                      if (name === 'value') return [formatCurrency(value), 'Quote Value'];
                      return [value, 'Quotes Count'];
                    }}
                  />
                  <Bar yAxisId="left" dataKey="quotes" fill="#2196f3" />
                  <Line yAxisId="right" type="monotone" dataKey="value" stroke="#4caf50" strokeWidth={3} dot={{ fill: '#4caf50' }} />
                </ComposedChart>
              </ResponsiveContainer>
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* Status Distribution */}
      <Grid item xs={12} lg={4}>
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Quote Status Distribution
            </Typography>
            <Box sx={{ height: 250, width: '100%' }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={statusDistribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    dataKey="value"
                    label={({ name, value, percent }) => `${name}: ${value} (${(percent * 100).toFixed(1)}%)`}
                  >
                    {statusDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* Quotes Expiring Soon */}
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center' }}>
                <Warning sx={{ mr: 1, color: 'warning.main' }} />
                Quotes Expiring Soon
              </Typography>
              <Button size="small" href="/quotes">
                View All
              </Button>
            </Box>

            {expiringQuotes.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                No quotes expiring soon
              </Typography>
            ) : (
              <List disablePadding>
                {expiringQuotes.slice(0, 5).map((quote, index) => (
                  <React.Fragment key={quote.id}>
                    <ListItem disablePadding sx={{ py: 1 }}>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <Typography variant="body2" fontWeight="medium">
                              {quote.quote_number}
                            </Typography>
                            <Chip
                              label={quote.status}
                              size="small"
                              sx={{
                                bgcolor: getStatusColor(quote.status),
                                color: 'white',
                                fontSize: '0.7rem',
                              }}
                            />
                          </Box>
                        }
                        secondary={
                          <Box sx={{ mt: 0.5 }}>
                            <Typography variant="caption" color="text.secondary">
                              {quote.company_name} • {formatCurrency(quote.total_value)}
                            </Typography>
                            <Typography variant="caption" sx={{ display: 'block', color: 'warning.main' }}>
                              Expires: {formatDate(quote.valid_until)}
                            </Typography>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <IconButton size="small" onClick={() => window.location.href = `/quotes/${quote.id}`}>
                          <Visibility fontSize="small" />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                    {index < expiringQuotes.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            )}
          </CardContent>
        </Card>
      </Grid>

      {/* Recent Quote Activity */}
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center' }}>
                <RequestQuote sx={{ mr: 1 }} />
                Recent Activity
              </Typography>
              <Button size="small" href="/quotes">
                View All
              </Button>
            </Box>

            <List disablePadding>
              {/* Mock activity data - replace with real data */}
              {[
                { id: 1, action: 'Quote Q-2024-1201-001 sent to Acme Corp', time: '2 hours ago', icon: <Send fontSize="small" color="primary" /> },
                { id: 2, action: 'Quote Q-2024-1130-003 accepted by Tech Solutions', time: '1 day ago', icon: <CheckCircle fontSize="small" color="success" /> },
                { id: 3, action: 'New quote Q-2024-1201-002 created for Restaurant Chain', time: '2 days ago', icon: <RequestQuote fontSize="small" color="info" /> },
                { id: 4, action: 'Quote Q-2024-1125-008 expired', time: '3 days ago', icon: <Schedule fontSize="small" color="warning" /> },
              ].map((activity, index) => (
                <React.Fragment key={activity.id}>
                  <ListItem disablePadding sx={{ py: 1 }}>
                    <ListItemText
                      primary={
                        <Typography variant="body2">
                          {activity.action}
                        </Typography>
                      }
                      secondary={
                        <Typography variant="caption" color="text.secondary">
                          {activity.time}
                        </Typography>
                      }
                    />
                    <Box sx={{ ml: 1 }}>
                      {activity.icon}
                    </Box>
                  </ListItem>
                  {index < 3 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};

export default QuoteWidgets;