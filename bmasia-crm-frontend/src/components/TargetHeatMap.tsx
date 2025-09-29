import React from 'react';
import { Paper, Typography, Box, Tooltip } from '@mui/material';
import { SalesTarget } from '../types';

interface TargetHeatMapProps {
  targets: SalesTarget[];
}

interface HeatMapCell {
  month: string;
  targetType: string;
  achievement: number;
  count: number;
  avgValue: number;
}

const TargetHeatMap: React.FC<TargetHeatMapProps> = ({ targets }) => {
  const generateHeatMapData = (): HeatMapCell[] => {
    const data: HeatMapCell[] = [];
    const monthsMap = new Map<string, Map<string, { achievement: number[], values: number[] }>>();

    // Collect data by month and target type
    targets.forEach(target => {
      const startDate = new Date(target.period_start);
      const monthKey = startDate.toLocaleDateString('en-US', { year: '2-digit', month: 'short' });
      const targetType = target.target_type;

      if (!monthsMap.has(monthKey)) {
        monthsMap.set(monthKey, new Map());
      }

      const monthData = monthsMap.get(monthKey)!;
      if (!monthData.has(targetType)) {
        monthData.set(targetType, { achievement: [], values: [] });
      }

      monthData.get(targetType)!.achievement.push(target.achievement_percentage);
      monthData.get(targetType)!.values.push(target.current_value);
    });

    // Generate all possible combinations
    const allMonths = Array.from(monthsMap.keys()).sort();
    const allTargetTypes = ['Revenue', 'Units', 'Customers', 'Contracts'];

    allTargetTypes.forEach(targetType => {
      allMonths.forEach(month => {
        const monthData = monthsMap.get(month);
        const typeData = monthData?.get(targetType);

        if (typeData && typeData.achievement.length > 0) {
          const avgAchievement = typeData.achievement.reduce((sum, val) => sum + val, 0) / typeData.achievement.length;
          const avgValue = typeData.values.reduce((sum, val) => sum + val, 0) / typeData.values.length;

          data.push({
            month,
            targetType,
            achievement: Math.round(avgAchievement),
            count: typeData.achievement.length,
            avgValue: Math.round(avgValue),
          });
        } else {
          data.push({
            month,
            targetType,
            achievement: 0,
            count: 0,
            avgValue: 0,
          });
        }
      });
    });

    return data;
  };

  const heatMapData = generateHeatMapData();
  const months = Array.from(new Set(heatMapData.map(d => d.month))).sort();
  const targetTypes = ['Revenue', 'Units', 'Customers', 'Contracts'];

  const getColor = (achievement: number, count: number) => {
    if (count === 0) return '#f5f5f5'; // No data

    if (achievement >= 90) return '#1b5e20'; // Dark green
    if (achievement >= 80) return '#388e3c'; // Green
    if (achievement >= 70) return '#66bb6a'; // Light green
    if (achievement >= 60) return '#ffb74d'; // Orange
    if (achievement >= 40) return '#ff8a65'; // Light red
    if (achievement >= 20) return '#e57373'; // Red
    return '#c62828'; // Dark red
  };

  const getTextColor = (achievement: number, count: number) => {
    if (count === 0) return '#666';
    return achievement >= 70 ? '#fff' : '#000';
  };

  const getCellData = (month: string, targetType: string) => {
    return heatMapData.find(d => d.month === month && d.targetType === targetType) || {
      month,
      targetType,
      achievement: 0,
      count: 0,
      avgValue: 0,
    };
  };

  if (targets.length === 0) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Performance Heat Map
        </Typography>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body1" color="text.secondary">
            No target data available for heat map
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3 }} data-chart="target">
      <Typography variant="h6" gutterBottom>
        Performance Heat Map
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Average achievement percentage by target type and period
      </Typography>

      <Box sx={{ overflowX: 'auto' }}>
        <Box sx={{ minWidth: 500 }}>
          {/* Header row */}
          <Box sx={{ display: 'flex', mb: 1 }}>
            <Box sx={{ width: 100, height: 40, display: 'flex', alignItems: 'center' }}>
              <Typography variant="body2" fontWeight="bold">
                Type / Period
              </Typography>
            </Box>
            {months.map(month => (
              <Box
                key={month}
                sx={{
                  width: 80,
                  height: 40,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: 'grey.100',
                  border: '1px solid',
                  borderColor: 'grey.300',
                }}
              >
                <Typography variant="caption" fontWeight="bold">
                  {month}
                </Typography>
              </Box>
            ))}
          </Box>

          {/* Data rows */}
          {targetTypes.map(targetType => (
            <Box key={targetType} sx={{ display: 'flex', mb: 1 }}>
              <Box
                sx={{
                  width: 100,
                  height: 50,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: 'grey.100',
                  border: '1px solid',
                  borderColor: 'grey.300',
                }}
              >
                <Typography variant="body2" fontWeight="medium">
                  {targetType}
                </Typography>
              </Box>
              {months.map(month => {
                const cellData = getCellData(month, targetType);
                return (
                  <Tooltip
                    key={`${targetType}-${month}`}
                    title={
                      cellData.count === 0
                        ? 'No targets for this period'
                        : `${targetType} - ${month}
Achievement: ${cellData.achievement}%
Targets: ${cellData.count}
Avg Value: ${cellData.avgValue.toLocaleString()}`
                    }
                    arrow
                  >
                    <Box
                      sx={{
                        width: 80,
                        height: 50,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        bgcolor: getColor(cellData.achievement, cellData.count),
                        color: getTextColor(cellData.achievement, cellData.count),
                        border: '1px solid',
                        borderColor: 'grey.300',
                        cursor: 'pointer',
                        '&:hover': {
                          opacity: 0.8,
                        },
                      }}
                    >
                      <Box sx={{ textAlign: 'center' }}>
                        <Typography variant="caption" fontWeight="bold">
                          {cellData.count === 0 ? '-' : `${cellData.achievement}%`}
                        </Typography>
                        {cellData.count > 0 && (
                          <Typography variant="caption" sx={{ display: 'block', fontSize: '0.625rem' }}>
                            ({cellData.count})
                          </Typography>
                        )}
                      </Box>
                    </Box>
                  </Tooltip>
                );
              })}
            </Box>
          ))}
        </Box>
      </Box>

      {/* Legend */}
      <Box sx={{ mt: 3 }}>
        <Typography variant="body2" fontWeight="medium" gutterBottom>
          Achievement Legend:
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          {[
            { range: '90-100%', color: '#1b5e20' },
            { range: '80-89%', color: '#388e3c' },
            { range: '70-79%', color: '#66bb6a' },
            { range: '60-69%', color: '#ffb74d' },
            { range: '40-59%', color: '#ff8a65' },
            { range: '20-39%', color: '#e57373' },
            { range: '0-19%', color: '#c62828' },
            { range: 'No Data', color: '#f5f5f5' },
          ].map(({ range, color }) => (
            <Box key={range} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box
                sx={{
                  width: 20,
                  height: 20,
                  bgcolor: color,
                  border: '1px solid',
                  borderColor: 'grey.400',
                }}
              />
              <Typography variant="caption">
                {range}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {/* Summary statistics */}
      <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
        <Typography variant="subtitle2" gutterBottom>
          Heat Map Summary
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
          <Typography variant="body2">
            Total Data Points: {heatMapData.filter(d => d.count > 0).length}
          </Typography>
          <Typography variant="body2">
            Best Performance: {Math.max(...heatMapData.filter(d => d.count > 0).map(d => d.achievement), 0)}%
          </Typography>
          <Typography variant="body2">
            Average Achievement: {Math.round(heatMapData.filter(d => d.count > 0).reduce((sum, d) => sum + d.achievement, 0) / Math.max(heatMapData.filter(d => d.count > 0).length, 1))}%
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
};

export default TargetHeatMap;