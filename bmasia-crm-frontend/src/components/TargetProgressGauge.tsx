import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { SalesTarget } from '../types';

interface TargetProgressGaugeProps {
  target: SalesTarget;
  size?: 'small' | 'medium' | 'large';
  showDetails?: boolean;
}

const TargetProgressGauge: React.FC<TargetProgressGaugeProps> = ({
  target,
  size = 'medium',
  showDetails = true
}) => {
  const theme = useTheme();

  const getSizeConfig = () => {
    switch (size) {
      case 'small':
        return { width: 120, height: 120, innerRadius: 35, outerRadius: 50 };
      case 'medium':
        return { width: 160, height: 160, innerRadius: 45, outerRadius: 65 };
      case 'large':
        return { width: 200, height: 200, innerRadius: 60, outerRadius: 85 };
    }
  };

  const { width, height, innerRadius, outerRadius } = getSizeConfig();

  const getProgressColor = (percentage: number) => {
    if (percentage >= 90) return theme.palette.success.main;
    if (percentage >= 70) return theme.palette.info.main;
    if (percentage >= 50) return theme.palette.warning.main;
    return theme.palette.error.main;
  };

  const formatValue = (value: number) => {
    if (target.target_type === 'Revenue') {
      const symbol = target.currency === 'USD' ? '$' : target.currency === 'THB' ? '฿' : '€';
      if (value >= 1000000) {
        return `${symbol}${(value / 1000000).toFixed(1)}M`;
      } else if (value >= 1000) {
        return `${symbol}${(value / 1000).toFixed(1)}K`;
      }
      return `${symbol}${value.toLocaleString()}`;
    } else {
      return value.toLocaleString();
    }
  };

  const progressData = [
    {
      name: 'Achieved',
      value: target.achievement_percentage,
      color: getProgressColor(target.achievement_percentage)
    },
    {
      name: 'Remaining',
      value: 100 - target.achievement_percentage,
      color: theme.palette.grey[300]
    }
  ];

  const stretchProgressData = target.stretch_target ? [
    {
      name: 'Achieved (Stretch)',
      value: target.stretch_achievement_percentage || 0,
      color: theme.palette.secondary.main
    },
    {
      name: 'Remaining (Stretch)',
      value: 100 - (target.stretch_achievement_percentage || 0),
      color: theme.palette.grey[200]
    }
  ] : [];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <Box sx={{ position: 'relative', width, height }}>
        <ResponsiveContainer width={width} height={height}>
          <PieChart>
            {/* Main target gauge */}
            <Pie
              data={progressData}
              cx="50%"
              cy="50%"
              innerRadius={innerRadius}
              outerRadius={outerRadius}
              startAngle={180}
              endAngle={0}
              dataKey="value"
            >
              {progressData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>

            {/* Stretch target gauge (outer ring) */}
            {target.stretch_target && (
              <Pie
                data={stretchProgressData}
                cx="50%"
                cy="50%"
                innerRadius={outerRadius + 2}
                outerRadius={outerRadius + 10}
                startAngle={180}
                endAngle={0}
                dataKey="value"
              >
                {stretchProgressData.map((entry, index) => (
                  <Cell key={`stretch-cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
            )}
          </PieChart>
        </ResponsiveContainer>

        {/* Center content */}
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -30%)',
            textAlign: 'center',
            zIndex: 1
          }}
        >
          <Typography
            variant={size === 'small' ? 'h6' : size === 'medium' ? 'h5' : 'h4'}
            fontWeight="bold"
            color={getProgressColor(target.achievement_percentage)}
          >
            {target.achievement_percentage.toFixed(0)}%
          </Typography>
          {size !== 'small' && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block' }}
            >
              of target
            </Typography>
          )}
        </Box>
      </Box>

      {showDetails && (
        <Box sx={{ mt: 2, textAlign: 'center', minWidth: 200 }}>
          <Box sx={{ mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Current: {formatValue(target.current_value)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Target: {formatValue(target.target_value)}
            </Typography>
            {target.stretch_target && (
              <Typography variant="body2" color="secondary.main">
                Stretch: {formatValue(target.stretch_target)} ({target.stretch_achievement_percentage?.toFixed(0) || 0}%)
              </Typography>
            )}
          </Box>

          <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2, mt: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box
                sx={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  bgcolor: getProgressColor(target.achievement_percentage)
                }}
              />
              <Typography variant="caption">Progress</Typography>
            </Box>
            {target.stretch_target && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    bgcolor: theme.palette.secondary.main
                  }}
                />
                <Typography variant="caption">Stretch</Typography>
              </Box>
            )}
          </Box>

          {/* Risk indicator */}
          {size !== 'small' && (
            <Box sx={{ mt: 1 }}>
              <Typography
                variant="caption"
                sx={{
                  px: 1,
                  py: 0.5,
                  borderRadius: 1,
                  bgcolor: target.risk_level === 'Low' ? 'success.light' :
                          target.risk_level === 'Medium' ? 'warning.light' : 'error.light',
                  color: target.risk_level === 'Low' ? 'success.dark' :
                         target.risk_level === 'Medium' ? 'warning.dark' : 'error.dark'
                }}
              >
                {target.risk_level} Risk
              </Typography>
            </Box>
          )}

          {/* Forecasted achievement */}
          {target.forecasted_achievement > 0 && size !== 'small' && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Forecasted: {target.forecasted_achievement.toFixed(0)}%
                {target.forecasted_achievement >= target.achievement_percentage && (
                  <Typography component="span" color="success.main"> ↗</Typography>
                )}
                {target.forecasted_achievement < target.achievement_percentage && (
                  <Typography component="span" color="error.main"> ↘</Typography>
                )}
              </Typography>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
};

export default TargetProgressGauge;