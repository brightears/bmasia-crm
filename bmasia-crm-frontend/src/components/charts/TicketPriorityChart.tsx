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
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Avatar,
} from '@mui/material';
import {
  Error,
  Warning,
  Info,
  CheckCircle,
} from '@mui/icons-material';

interface TicketPriorityData {
  priority: string;
  count: number;
  percentage: number;
  fill: string;
}

interface TicketPriorityChartProps {
  data: TicketPriorityData[];
  loading?: boolean;
}

const TECH_SUPPORT_COLORS = {
  primary: '#1976d2',
  secondary: '#42a5f5',
  accent: '#64b5f6',
  priority: {
    critical: '#d32f2f',
    high: '#ff5722',
    medium: '#ff9800',
    low: '#4caf50',
  },
};

const TicketPriorityChart: React.FC<TicketPriorityChartProps> = ({
  data,
  loading = false
}) => {
  const [chartType, setChartType] = useState<'pie' | 'bar'>('pie');

  const getPriorityIcon = (priority: string) => {
    switch (priority.toLowerCase()) {
      case 'critical':
        return <Error />;
      case 'high':
        return <Warning />;
      case 'medium':
        return <Info />;
      case 'low':
        return <CheckCircle />;
      default:
        return <Info />;
    }
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
            {data.priority} Priority
          </Typography>
          <Typography variant="body2">
            Count: {data.count}
          </Typography>
          <Typography variant="body2">
            Percentage: {data.percentage}%
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
          <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Ticket Priority Breakdown
          </Typography>
          <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">Loading priority data...</Typography>
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
            Ticket Priority Breakdown
          </Typography>

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
                    dataKey="count"
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
                        {getPriorityIcon(item.priority)}
                      </Avatar>
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {item.priority}
                        </Typography>
                      }
                      secondary={
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            {item.count} tickets ({item.percentage}%)
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
            <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="priority"
                tick={{ fontSize: 12 }}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}

        {/* Priority Analysis */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Priority Analysis
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                High Priority Tickets
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.filter(item => item.priority === 'Critical' || item.priority === 'High')
                     .reduce((sum, item) => sum + item.count, 0)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Critical/High Ratio
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {(((data.filter(item => item.priority === 'Critical' || item.priority === 'High')
                       .reduce((sum, item) => sum + item.count, 0)) /
                   data.reduce((sum, item) => sum + item.count, 0)) * 100).toFixed(1)}%
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Most Common Priority
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.reduce((max, item) => item.count > max.count ? item : max, data[0])?.priority}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Attention Required
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold', color: TECH_SUPPORT_COLORS.priority.critical }}>
                {data.find(item => item.priority === 'Critical')?.count || 0} Critical
              </Typography>
            </Box>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default TicketPriorityChart;