import React from 'react';
import { Paper, Typography, Box, FormControl, InputLabel, Select, MenuItem, SelectChangeEvent } from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { SalesTarget } from '../types';

interface TargetTrendChartProps {
  targets: SalesTarget[];
}

const TargetTrendChart: React.FC<TargetTrendChartProps> = ({ targets }) => {
  const [selectedMetric, setSelectedMetric] = React.useState<'achievement' | 'value' | 'forecast'>('achievement');
  const [selectedPeriod, setSelectedPeriod] = React.useState<'all' | 'Monthly' | 'Quarterly' | 'Yearly'>('all');

  const handleMetricChange = (event: SelectChangeEvent) => {
    setSelectedMetric(event.target.value as any);
  };

  const handlePeriodChange = (event: SelectChangeEvent) => {
    setSelectedPeriod(event.target.value as any);
  };

  const generateTrendData = () => {
    const filteredTargets = selectedPeriod === 'all'
      ? targets
      : targets.filter(t => t.period_type === selectedPeriod);

    // Group targets by month for trend analysis
    const monthlyData = new Map();

    filteredTargets.forEach(target => {
      const startDate = new Date(target.period_start);
      const monthKey = `${startDate.getFullYear()}-${(startDate.getMonth() + 1).toString().padStart(2, '0')}`;

      if (!monthlyData.has(monthKey)) {
        monthlyData.set(monthKey, {
          month: startDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short' }),
          targets: [],
          totalValue: 0,
          totalAchievement: 0,
          totalForecast: 0,
          count: 0,
        });
      }

      const monthEntry = monthlyData.get(monthKey);
      monthEntry.targets.push(target);
      monthEntry.totalValue += target.current_value;
      monthEntry.totalAchievement += target.achievement_percentage;
      monthEntry.totalForecast += target.forecasted_achievement;
      monthEntry.count++;
    });

    // Convert to array and calculate averages
    return Array.from(monthlyData.values())
      .map(entry => ({
        month: entry.month,
        achievement: Math.round(entry.totalAchievement / entry.count),
        value: entry.totalValue,
        forecast: Math.round(entry.totalForecast / entry.count),
        targetCount: entry.count,
      }))
      .sort((a, b) => a.month.localeCompare(b.month));
  };

  const trendData = generateTrendData();

  const getYAxisLabel = () => {
    switch (selectedMetric) {
      case 'achievement': return 'Achievement (%)';
      case 'value': return 'Value';
      case 'forecast': return 'Forecast (%)';
      default: return '';
    }
  };

  const getDataKey = () => {
    return selectedMetric;
  };

  const formatTooltipValue = (value: number, name: string) => {
    if (name === 'achievement' || name === 'forecast') {
      return [`${value}%`, name === 'achievement' ? 'Average Achievement' : 'Average Forecast'];
    }
    return [value.toLocaleString(), 'Total Value'];
  };

  if (targets.length === 0) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Target Trends
        </Typography>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body1" color="text.secondary">
            No target data available for trend analysis
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3 }} data-chart="target">
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">
          Target Trends
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Metric</InputLabel>
            <Select
              value={selectedMetric}
              onChange={handleMetricChange}
              label="Metric"
            >
              <MenuItem value="achievement">Achievement %</MenuItem>
              <MenuItem value="value">Current Value</MenuItem>
              <MenuItem value="forecast">Forecast %</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Period</InputLabel>
            <Select
              value={selectedPeriod}
              onChange={handlePeriodChange}
              label="Period"
            >
              <MenuItem value="all">All</MenuItem>
              <MenuItem value="Monthly">Monthly</MenuItem>
              <MenuItem value="Quarterly">Quarterly</MenuItem>
              <MenuItem value="Yearly">Yearly</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Box>

      {trendData.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body1" color="text.secondary">
            No trend data available for the selected filters
          </Typography>
        </Box>
      ) : (
        <Box sx={{ height: 350 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="month"
                tick={{ fontSize: 12 }}
              />
              <YAxis
                label={{ value: getYAxisLabel(), angle: -90, position: 'insideLeft' }}
                tick={{ fontSize: 12 }}
              />
              <Tooltip
                formatter={formatTooltipValue}
                labelFormatter={(label) => `Month: ${label}`}
                contentStyle={{
                  backgroundColor: '#f5f5f5',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey={getDataKey()}
                stroke="#1976d2"
                strokeWidth={3}
                dot={{ fill: '#1976d2', strokeWidth: 2, r: 6 }}
                activeDot={{ r: 8, stroke: '#1976d2', strokeWidth: 2 }}
                name={selectedMetric === 'achievement' ? 'Achievement %' :
                      selectedMetric === 'value' ? 'Current Value' : 'Forecast %'}
              />

              {selectedMetric === 'achievement' && (
                <Line
                  type="monotone"
                  dataKey="forecast"
                  stroke="#ff7300"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={{ fill: '#ff7300', strokeWidth: 2, r: 4 }}
                  name="Forecast %"
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </Box>
      )}

      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Showing {trendData.length} data points across {targets.length} targets
        </Typography>

        {selectedMetric === 'achievement' && (
          <Typography variant="body2" color="text.secondary">
            Dashed line shows forecasted achievement
          </Typography>
        )}
      </Box>

      {/* Summary statistics */}
      {trendData.length > 0 && (
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Trend Summary
          </Typography>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
            {selectedMetric === 'achievement' && (
              <>
                <Typography variant="body2">
                  Avg Achievement: {Math.round(trendData.reduce((sum, d) => sum + d.achievement, 0) / trendData.length)}%
                </Typography>
                <Typography variant="body2">
                  Best Month: {Math.max(...trendData.map(d => d.achievement))}%
                </Typography>
                <Typography variant="body2">
                  Trend: {trendData.length > 1 && trendData[trendData.length - 1].achievement > trendData[0].achievement ? '↗ Improving' : '↘ Declining'}
                </Typography>
              </>
            )}
            {selectedMetric === 'value' && (
              <>
                <Typography variant="body2">
                  Total Value: {trendData.reduce((sum, d) => sum + d.value, 0).toLocaleString()}
                </Typography>
                <Typography variant="body2">
                  Best Month: {Math.max(...trendData.map(d => d.value)).toLocaleString()}
                </Typography>
              </>
            )}
            {selectedMetric === 'forecast' && (
              <>
                <Typography variant="body2">
                  Avg Forecast: {Math.round(trendData.reduce((sum, d) => sum + d.forecast, 0) / trendData.length)}%
                </Typography>
                <Typography variant="body2">
                  Best Forecast: {Math.max(...trendData.map(d => d.forecast))}%
                </Typography>
              </>
            )}
          </Box>
        </Box>
      )}
    </Paper>
  );
};

export default TargetTrendChart;