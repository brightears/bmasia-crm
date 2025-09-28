import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Area,
  AreaChart,
} from 'recharts';
import { Box, Typography, Card, CardContent, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { TrendingUp, TrendingDown } from '@mui/icons-material';

interface TrendData {
  month: string;
  revenue: number;
  opportunities: number;
  deals: number;
}

interface RevenueTrendChartProps {
  data: TrendData[];
  loading?: boolean;
}

const RevenueTrendChart: React.FC<RevenueTrendChartProps> = ({ data, loading = false }) => {
  const [chartType, setChartType] = React.useState<'line' | 'area'>('line');

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const calculateTrend = () => {
    if (data.length < 2) return { trend: 0, isPositive: true };

    const current = data[data.length - 1].revenue;
    const previous = data[data.length - 2].revenue;
    const trend = ((current - previous) / previous) * 100;

    return { trend: Math.abs(trend), isPositive: trend >= 0 };
  };

  const { trend, isPositive } = calculateTrend();

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <Box
          sx={{
            bgcolor: 'background.paper',
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
            p: 2,
            boxShadow: 2,
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
            {label}
          </Typography>
          <Typography variant="body2" color="success.main">
            Revenue: {formatCurrency(payload[0].value)}
          </Typography>
          {payload[0].payload.opportunities && (
            <Typography variant="body2" color="primary">
              Opportunities: {payload[0].payload.opportunities}
            </Typography>
          )}
          {payload[0].payload.deals && (
            <Typography variant="body2" color="info.main">
              Deals Closed: {payload[0].payload.deals}
            </Typography>
          )}
        </Box>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Revenue Trend
          </Typography>
          <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">Loading revenue data...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Typography variant="h6" gutterBottom>
              Revenue Trend
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {isPositive ? (
                <TrendingUp color="success" fontSize="small" />
              ) : (
                <TrendingDown color="error" fontSize="small" />
              )}
              <Typography
                variant="body2"
                color={isPositive ? 'success.main' : 'error.main'}
                sx={{ fontWeight: 'bold' }}
              >
                {trend.toFixed(1)}% vs last month
              </Typography>
            </Box>
          </Box>

          <ToggleButtonGroup
            value={chartType}
            exclusive
            onChange={(_, newType) => newType && setChartType(newType)}
            size="small"
          >
            <ToggleButton value="line">Line</ToggleButton>
            <ToggleButton value="area">Area</ToggleButton>
          </ToggleButtonGroup>
        </Box>

        <ResponsiveContainer width="100%" height={300}>
          {chartType === 'line' ? (
            <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => `$${(value / 1000)}K`} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="revenue"
                stroke="#2e7d32"
                strokeWidth={3}
                dot={{
                  fill: '#2e7d32',
                  strokeWidth: 2,
                  r: 4,
                }}
                activeDot={{
                  r: 6,
                  stroke: '#2e7d32',
                  strokeWidth: 2,
                  fill: '#ffffff',
                }}
              />
            </LineChart>
          ) : (
            <AreaChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => `$${(value / 1000)}K`} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="#2e7d32"
                fill="#2e7d32"
                fillOpacity={0.3}
                strokeWidth={2}
              />
            </AreaChart>
          )}
        </ResponsiveContainer>

        {/* Quick Stats */}
        <Box sx={{ mt: 2, display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Avg Monthly Revenue
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              {formatCurrency(data.reduce((sum, item) => sum + item.revenue, 0) / data.length)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Total Revenue (12 months)
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              {formatCurrency(data.reduce((sum, item) => sum + item.revenue, 0))}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Best Month
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              {data.reduce((max, item) => item.revenue > max.revenue ? item : max, data[0])?.month}
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default RevenueTrendChart;