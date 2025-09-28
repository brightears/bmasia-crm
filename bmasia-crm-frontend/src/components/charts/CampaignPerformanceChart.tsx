import React, { useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ComposedChart,
  Bar,
  Area,
  AreaChart,
} from 'recharts';
import {
  Box,
  Typography,
  Card,
  CardContent,
  ToggleButton,
  ToggleButtonGroup,
  FormControl,
  Select,
  MenuItem,
  SelectChangeEvent,
} from '@mui/material';
import { TrendingUp, TrendingDown } from '@mui/icons-material';

interface CampaignPerformanceData {
  month: string;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
}

interface CampaignPerformanceChartProps {
  data: CampaignPerformanceData[];
  loading?: boolean;
}

const MARKETING_COLORS = {
  primary: '#ff6f00',
  secondary: '#ff8f00',
  accent: '#ffb74d',
  success: '#4caf50',
  info: '#2196f3',
  warning: '#ff9800',
};

const CampaignPerformanceChart: React.FC<CampaignPerformanceChartProps> = ({
  data,
  loading = false
}) => {
  const [chartType, setChartType] = useState<'line' | 'area' | 'composed'>('line');
  const [metric, setMetric] = useState<'impressions' | 'clicks' | 'conversions' | 'spend'>('impressions');

  const formatValue = (value: number, type: string) => {
    switch (type) {
      case 'spend':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(value);
      case 'impressions':
        return value >= 1000000 ? `${(value / 1000000).toFixed(1)}M` : `${(value / 1000).toFixed(0)}K`;
      case 'clicks':
      case 'conversions':
        return value >= 1000 ? `${(value / 1000).toFixed(1)}K` : value.toString();
      default:
        return value.toLocaleString();
    }
  };

  const calculateTrend = () => {
    if (data.length < 2) return { trend: 0, isPositive: true };

    const current = data[data.length - 1][metric];
    const previous = data[data.length - 2][metric];
    const trend = ((current - previous) / previous) * 100;

    return { trend: Math.abs(trend), isPositive: trend >= 0 };
  };

  const { trend, isPositive } = calculateTrend();

  const getMetricColor = () => {
    switch (metric) {
      case 'impressions':
        return MARKETING_COLORS.primary;
      case 'clicks':
        return MARKETING_COLORS.info;
      case 'conversions':
        return MARKETING_COLORS.success;
      case 'spend':
        return MARKETING_COLORS.warning;
      default:
        return MARKETING_COLORS.primary;
    }
  };

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
          {payload.map((entry: any, index: number) => (
            <Typography key={index} variant="body2" sx={{ color: entry.color }}>
              {entry.name}: {formatValue(entry.value, entry.dataKey)}
            </Typography>
          ))}
        </Box>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
            Campaign Performance Over Time
          </Typography>
          <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">Loading campaign performance data...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2, flexWrap: 'wrap', gap: 2 }}>
          <Box>
            <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
              Campaign Performance Over Time
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

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <Select
                value={metric}
                onChange={(event: SelectChangeEvent) => setMetric(event.target.value as any)}
              >
                <MenuItem value="impressions">Impressions</MenuItem>
                <MenuItem value="clicks">Clicks</MenuItem>
                <MenuItem value="conversions">Conversions</MenuItem>
                <MenuItem value="spend">Spend</MenuItem>
              </Select>
            </FormControl>

            <ToggleButtonGroup
              value={chartType}
              exclusive
              onChange={(_, newType) => newType && setChartType(newType)}
              size="small"
            >
              <ToggleButton value="line">Line</ToggleButton>
              <ToggleButton value="area">Area</ToggleButton>
              <ToggleButton value="composed">Multi</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </Box>

        <ResponsiveContainer width="100%" height={300}>
          {chartType === 'line' ? (
            <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => formatValue(value, metric)} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey={metric}
                stroke={getMetricColor()}
                strokeWidth={3}
                dot={{
                  fill: getMetricColor(),
                  strokeWidth: 2,
                  r: 4,
                }}
                activeDot={{
                  r: 6,
                  stroke: getMetricColor(),
                  strokeWidth: 2,
                  fill: '#ffffff',
                }}
              />
            </LineChart>
          ) : chartType === 'area' ? (
            <AreaChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => formatValue(value, metric)} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey={metric}
                stroke={getMetricColor()}
                fill={getMetricColor()}
                fillOpacity={0.3}
                strokeWidth={2}
              />
            </AreaChart>
          ) : (
            <ComposedChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
              <Tooltip content={<CustomTooltip />} />

              <Bar yAxisId="left" dataKey="impressions" fill={MARKETING_COLORS.primary} name="Impressions" />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="conversions"
                stroke={MARKETING_COLORS.success}
                strokeWidth={3}
                name="Conversions"
              />
            </ComposedChart>
          )}
        </ResponsiveContainer>

        {/* Quick Stats */}
        <Box sx={{ mt: 2, display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Avg Monthly {metric.charAt(0).toUpperCase() + metric.slice(1)}
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold', color: getMetricColor() }}>
              {formatValue(data.reduce((sum, item) => sum + item[metric], 0) / data.length, metric)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Total {metric.charAt(0).toUpperCase() + metric.slice(1)} (12 months)
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              {formatValue(data.reduce((sum, item) => sum + item[metric], 0), metric)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Best Month
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              {data.reduce((max, item) => item[metric] > max[metric] ? item : max, data[0])?.month}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Avg CTR
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              {((data.reduce((sum, item) => sum + item.clicks, 0) / data.reduce((sum, item) => sum + item.impressions, 0)) * 100).toFixed(2)}%
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default CampaignPerformanceChart;