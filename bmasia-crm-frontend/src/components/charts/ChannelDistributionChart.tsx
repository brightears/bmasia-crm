import React, { useState } from 'react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
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
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Avatar,
} from '@mui/material';
import {
  Email,
  Share as Social,
  Web,
  PhoneAndroid as Mobile,
  Search,
} from '@mui/icons-material';

interface ChannelData {
  channel: string;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
  fill: string;
}

interface ChannelDistributionChartProps {
  data: ChannelData[];
  loading?: boolean;
}

const MARKETING_COLORS = {
  primary: '#ff6f00',
  secondary: '#ff8f00',
  accent: '#ffb74d',
  channels: ['#ff6f00', '#ff8f00', '#ffb74d', '#ffcc80', '#ffe0b2'],
};

const ChannelDistributionChart: React.FC<ChannelDistributionChartProps> = ({
  data,
  loading = false
}) => {
  const [chartType, setChartType] = useState<'pie' | 'bar'>('pie');
  const [metric, setMetric] = useState<'impressions' | 'clicks' | 'conversions' | 'spend'>('impressions');

  const getChannelIcon = (channel: string) => {
    switch (channel.toLowerCase()) {
      case 'email':
        return <Email />;
      case 'social media':
        return <Social />;
      case 'web/display':
        return <Web />;
      case 'mobile':
        return <Mobile />;
      case 'search':
        return <Search />;
      default:
        return <Web />;
    }
  };

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

  const getPercentage = (value: number) => {
    const total = data.reduce((sum, item) => sum + item[metric], 0);
    return ((value / total) * 100).toFixed(1);
  };

  const CustomTooltip = ({ active, payload }: any) => {
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
            {data.channel}
          </Typography>
          <Typography variant="body2">
            Impressions: {formatValue(data.impressions, 'impressions')}
          </Typography>
          <Typography variant="body2">
            Clicks: {formatValue(data.clicks, 'clicks')}
          </Typography>
          <Typography variant="body2">
            Conversions: {formatValue(data.conversions, 'conversions')}
          </Typography>
          <Typography variant="body2">
            Spend: {formatValue(data.spend, 'spend')}
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 'bold', mt: 1 }}>
            CTR: {((data.clicks / data.impressions) * 100).toFixed(2)}%
          </Typography>
        </Box>
      );
    }
    return null;
  };

  const CustomPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
    if (percent < 0.05) return null; // Don't show labels for slices smaller than 5%

    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor={x > cx ? 'start' : 'end'}
        dominantBaseline="central"
        fontSize="12"
        fontWeight="bold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
            Channel Distribution
          </Typography>
          <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">Loading channel data...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2, flexWrap: 'wrap', gap: 2 }}>
          <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
            Channel Distribution
          </Typography>

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
              <ToggleButton value="pie">Pie</ToggleButton>
              <ToggleButton value="bar">Bar</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </Box>

        {chartType === 'pie' ? (
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Box sx={{ flex: 1 }}>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={data}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={<CustomPieLabel />}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey={metric}
                  >
                    {data.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </Box>

            {/* Legend */}
            <Box sx={{ ml: 2 }}>
              <List dense>
                {data.map((item, index) => (
                  <ListItem key={index} sx={{ py: 0.5 }}>
                    <ListItemIcon sx={{ minWidth: 40 }}>
                      <Avatar
                        sx={{
                          bgcolor: item.fill,
                          width: 24,
                          height: 24,
                          fontSize: '0.75rem'
                        }}
                      >
                        {getChannelIcon(item.channel)}
                      </Avatar>
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {item.channel}
                        </Typography>
                      }
                      secondary={
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            {formatValue(item[metric], metric)} ({getPercentage(item[metric])}%)
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          </Box>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="channel"
                tick={{ fontSize: 12 }}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => formatValue(value, metric)} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey={metric} radius={[4, 4, 0, 0]}>
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}

        {/* Channel Performance Summary */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
            Channel Performance Summary
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Best Performing Channel
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.reduce((max, item) => {
                  const maxCtr = (max.clicks / max.impressions) * 100;
                  const itemCtr = (item.clicks / item.impressions) * 100;
                  return itemCtr > maxCtr ? item : max;
                }, data[0])?.channel}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Highest Conversion Rate
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.reduce((max, item) => {
                  const maxRate = (max.conversions / max.clicks) * 100;
                  const itemRate = (item.conversions / item.clicks) * 100;
                  return itemRate > maxRate ? item : max;
                }, data[0])?.channel}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Most Cost Effective
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.reduce((min, item) => {
                  const minCpc = min.spend / min.clicks;
                  const itemCpc = item.spend / item.clicks;
                  return itemCpc < minCpc ? item : min;
                }, data[0])?.channel}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Total Reach
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {formatValue(data.reduce((sum, item) => sum + item.impressions, 0), 'impressions')}
              </Typography>
            </Box>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ChannelDistributionChart;