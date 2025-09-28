import React, { useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ComposedChart,
  Line,
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

interface CategoryVolumeData {
  category: string;
  tickets: number;
  resolved: number;
  avgResolutionTime: number;
  fill: string;
}

interface TicketVolumeChartProps {
  data: CategoryVolumeData[];
  loading?: boolean;
}

const TECH_SUPPORT_COLORS = {
  primary: '#1976d2',
  secondary: '#42a5f5',
  accent: '#64b5f6',
  success: '#4caf50',
  warning: '#ff9800',
  categories: ['#1976d2', '#42a5f5', '#64b5f6', '#90caf9', '#bbdefb'],
};

const TicketVolumeChart: React.FC<TicketVolumeChartProps> = ({
  data,
  loading = false
}) => {
  const [chartType, setChartType] = useState<'bar' | 'composed'>('bar');
  const [metric, setMetric] = useState<'tickets' | 'resolved' | 'resolutionRate'>('tickets');

  const enhancedData = data.map(item => ({
    ...item,
    resolutionRate: (item.resolved / item.tickets) * 100,
    pending: item.tickets - item.resolved,
  }));

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
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
          <Typography variant="body2">
            Total Tickets: {data.tickets}
          </Typography>
          <Typography variant="body2">
            Resolved: {data.resolved}
          </Typography>
          <Typography variant="body2">
            Pending: {data.pending}
          </Typography>
          <Typography variant="body2">
            Resolution Rate: {data.resolutionRate.toFixed(1)}%
          </Typography>
          <Typography variant="body2">
            Avg Resolution Time: {data.avgResolutionTime.toFixed(1)}h
          </Typography>
        </Box>
      );
    }
    return null;
  };

  const formatCategoryName = (category: string) => {
    return category.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase());
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Ticket Volume by Category
          </Typography>
          <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">Loading volume data...</Typography>
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
            Ticket Volume by Category
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <Select
                value={metric}
                onChange={(event: SelectChangeEvent) => setMetric(event.target.value as any)}
              >
                <MenuItem value="tickets">Total Tickets</MenuItem>
                <MenuItem value="resolved">Resolved</MenuItem>
                <MenuItem value="resolutionRate">Resolution Rate</MenuItem>
              </Select>
            </FormControl>

            <ToggleButtonGroup
              value={chartType}
              exclusive
              onChange={(_, newType) => newType && setChartType(newType)}
              size="small"
            >
              <ToggleButton value="bar">Bar</ToggleButton>
              <ToggleButton value="composed">Detailed</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </Box>

        <ResponsiveContainer width="100%" height={300}>
          {chartType === 'bar' ? (
            <BarChart data={enhancedData} margin={{ top: 20, right: 30, left: 20, bottom: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="category"
                tick={{ fontSize: 11 }}
                angle={-45}
                textAnchor="end"
                height={80}
                tickFormatter={formatCategoryName}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                tickFormatter={(value) =>
                  metric === 'resolutionRate' ? `${value}%` : value.toString()
                }
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar
                dataKey={metric}
                radius={[4, 4, 0, 0]}
                fill={TECH_SUPPORT_COLORS.primary}
              />
            </BarChart>
          ) : (
            <ComposedChart data={enhancedData} margin={{ top: 20, right: 30, left: 20, bottom: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="category"
                tick={{ fontSize: 11 }}
                angle={-45}
                textAnchor="end"
                height={80}
                tickFormatter={formatCategoryName}
              />
              <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => `${value}h`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar
                yAxisId="left"
                dataKey="tickets"
                fill={TECH_SUPPORT_COLORS.accent}
                fillOpacity={0.6}
                name="Total Tickets"
              />
              <Bar
                yAxisId="left"
                dataKey="resolved"
                fill={TECH_SUPPORT_COLORS.success}
                name="Resolved"
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="avgResolutionTime"
                stroke={TECH_SUPPORT_COLORS.warning}
                strokeWidth={3}
                name="Avg Resolution Time"
              />
            </ComposedChart>
          )}
        </ResponsiveContainer>

        {/* Category Performance Summary */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Category Performance Summary
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Highest Volume Category
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {formatCategoryName(
                  enhancedData.reduce((max, item) => item.tickets > max.tickets ? item : max, enhancedData[0])?.category || 'N/A'
                )}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Best Resolution Rate
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {formatCategoryName(
                  enhancedData.reduce((max, item) => item.resolutionRate > max.resolutionRate ? item : max, enhancedData[0])?.category || 'N/A'
                )} ({enhancedData.reduce((max, item) => item.resolutionRate > max.resolutionRate ? item : max, enhancedData[0])?.resolutionRate.toFixed(1)}%)
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Fastest Resolution
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {formatCategoryName(
                  enhancedData.reduce((min, item) => item.avgResolutionTime < min.avgResolutionTime ? item : min, enhancedData[0])?.category || 'N/A'
                )} ({enhancedData.reduce((min, item) => item.avgResolutionTime < min.avgResolutionTime ? item : min, enhancedData[0])?.avgResolutionTime.toFixed(1)}h)
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Total Pending
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {enhancedData.reduce((sum, item) => sum + item.pending, 0)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Overall Resolution Rate
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {(
                  (enhancedData.reduce((sum, item) => sum + item.resolved, 0) /
                   enhancedData.reduce((sum, item) => sum + item.tickets, 0)) * 100
                ).toFixed(1)}%
              </Typography>
            </Box>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default TicketVolumeChart;