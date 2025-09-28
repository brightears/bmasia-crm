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

interface ResolutionTimeData {
  month: string;
  avgResolutionTime: number;
  firstResponseTime: number;
  ticketsResolved: number;
  customerSatisfaction: number;
}

interface ResolutionTimeChartProps {
  data: ResolutionTimeData[];
  loading?: boolean;
}

const TECH_SUPPORT_COLORS = {
  primary: '#1976d2',
  secondary: '#42a5f5',
  accent: '#64b5f6',
  success: '#4caf50',
  warning: '#ff9800',
  error: '#f44336',
  info: '#2196f3',
};

const ResolutionTimeChart: React.FC<ResolutionTimeChartProps> = ({
  data,
  loading = false
}) => {
  const [chartType, setChartType] = useState<'line' | 'area' | 'composed'>('line');
  const [metric, setMetric] = useState<'avgResolutionTime' | 'firstResponseTime' | 'ticketsResolved' | 'customerSatisfaction'>('avgResolutionTime');

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

  const formatValue = (value: number, dataKey: string) => {
    switch (dataKey) {
      case 'avgResolutionTime':
      case 'firstResponseTime':
        return `${value.toFixed(1)}h`;
      case 'ticketsResolved':
        return value.toString();
      case 'customerSatisfaction':
        return `${value.toFixed(1)}/5`;
      default:
        return value.toString();
    }
  };

  const getMetricName = (metric: string) => {
    switch (metric) {
      case 'avgResolutionTime':
        return 'Avg Resolution Time';
      case 'firstResponseTime':
        return 'First Response Time';
      case 'ticketsResolved':
        return 'Tickets Resolved';
      case 'customerSatisfaction':
        return 'Customer Satisfaction';
      default:
        return metric;
    }
  };

  const getMetricColor = (metric: string) => {
    switch (metric) {
      case 'avgResolutionTime':
        return TECH_SUPPORT_COLORS.primary;
      case 'firstResponseTime':
        return TECH_SUPPORT_COLORS.secondary;
      case 'ticketsResolved':
        return TECH_SUPPORT_COLORS.success;
      case 'customerSatisfaction':
        return TECH_SUPPORT_COLORS.warning;
      default:
        return TECH_SUPPORT_COLORS.primary;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Resolution Time Trends
          </Typography>
          <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">Loading resolution time data...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2, flexWrap: 'wrap', gap: 2 }}>
          <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Resolution Time Trends
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <Select
                value={metric}
                onChange={(event: SelectChangeEvent) => setMetric(event.target.value as any)}
              >
                <MenuItem value="avgResolutionTime">Resolution Time</MenuItem>
                <MenuItem value="firstResponseTime">Response Time</MenuItem>
                <MenuItem value="ticketsResolved">Tickets Resolved</MenuItem>
                <MenuItem value="customerSatisfaction">Satisfaction</MenuItem>
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
              <ToggleButton value="composed">Combined</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </Box>

        <ResponsiveContainer width="100%" height={300}>
          {chartType === 'line' ? (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => formatValue(value, metric)} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey={metric}
                stroke={getMetricColor(metric)}
                strokeWidth={3}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
                name={getMetricName(metric)}
              />
            </LineChart>
          ) : chartType === 'area' ? (
            <AreaChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => formatValue(value, metric)} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey={metric}
                stroke={getMetricColor(metric)}
                fill={getMetricColor(metric)}
                fillOpacity={0.3}
                name={getMetricName(metric)}
              />
            </AreaChart>
          ) : (
            <ComposedChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis
                yAxisId="left"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => `${value.toFixed(1)}h`}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fontSize: 12 }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar
                yAxisId="right"
                dataKey="ticketsResolved"
                fill={TECH_SUPPORT_COLORS.success}
                fillOpacity={0.6}
                name="Tickets Resolved"
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="avgResolutionTime"
                stroke={TECH_SUPPORT_COLORS.primary}
                strokeWidth={2}
                name="Avg Resolution Time"
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="firstResponseTime"
                stroke={TECH_SUPPORT_COLORS.secondary}
                strokeWidth={2}
                strokeDasharray="5 5"
                name="First Response Time"
              />
            </ComposedChart>
          )}
        </ResponsiveContainer>

        {/* Trend Analysis */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Trend Analysis
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Current Avg Resolution
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {formatValue(data[data.length - 1]?.avgResolutionTime || 0, 'avgResolutionTime')}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Current Response Time
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {formatValue(data[data.length - 1]?.firstResponseTime || 0, 'firstResponseTime')}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Monthly Resolved
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data[data.length - 1]?.ticketsResolved || 0}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Satisfaction Trend
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {(() => {
                  if (data.length < 2) return 'N/A';
                  const current = data[data.length - 1]?.customerSatisfaction || 0;
                  const previous = data[data.length - 2]?.customerSatisfaction || 0;
                  const change = current - previous;
                  return change > 0 ? '↗ Improving' : change < 0 ? '↘ Declining' : '→ Stable';
                })()}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Best Performance Month
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.reduce((best, item) =>
                  item.avgResolutionTime < best.avgResolutionTime ? item : best,
                  data[0] || { month: 'N/A' }
                ).month}
              </Typography>
            </Box>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ResolutionTimeChart;