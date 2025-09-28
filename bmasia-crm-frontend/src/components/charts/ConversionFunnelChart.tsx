import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from 'recharts';
import {
  Box,
  Typography,
  Card,
  CardContent,
  LinearProgress,
  Chip,
} from '@mui/material';
import { TrendingDown, People, Visibility, ShoppingCart, MonetizationOn } from '@mui/icons-material';

interface ConversionFunnelData {
  stage: string;
  visitors: number;
  percentage: number;
  fill: string;
}

interface ConversionFunnelChartProps {
  data: ConversionFunnelData[];
  loading?: boolean;
}

const MARKETING_COLORS = {
  primary: '#ff6f00',
  secondary: '#ff8f00',
  accent: '#ffb74d',
  funnel: ['#ff6f00', '#ff8f00', '#ffb74d', '#ffcc80', '#ffe0b2'],
};

const ConversionFunnelChart: React.FC<ConversionFunnelChartProps> = ({
  data,
  loading = false
}) => {
  const formatNumber = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    return value.toLocaleString();
  };

  const getStageIcon = (stage: string) => {
    switch (stage.toLowerCase()) {
      case 'visitors':
        return <Visibility />;
      case 'interested':
        return <People />;
      case 'consideration':
        return <Visibility />;
      case 'intent':
        return <ShoppingCart />;
      case 'purchase':
        return <MonetizationOn />;
      default:
        return <People />;
    }
  };

  const calculateDropOff = (currentIndex: number) => {
    if (currentIndex === 0) return null;
    const current = data[currentIndex].visitors;
    const previous = data[currentIndex - 1].visitors;
    const dropOff = ((previous - current) / previous) * 100;
    return dropOff;
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload;
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
            {dataPoint.stage}
          </Typography>
          <Typography variant="body2">
            Visitors: {formatNumber(dataPoint.visitors)}
          </Typography>
          <Typography variant="body2" sx={{ color: MARKETING_COLORS.primary }}>
            Conversion: {dataPoint.percentage.toFixed(1)}%
          </Typography>
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
            Conversion Funnel
          </Typography>
          <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">Loading funnel data...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
          Conversion Funnel
        </Typography>

        {/* Visual Funnel Representation */}
        <Box sx={{ mb: 3 }}>
          {data.map((stage, index) => {
            const dropOff = calculateDropOff(index);
            const widthPercentage = (stage.visitors / data[0].visitors) * 100;

            return (
              <Box key={stage.stage} sx={{ mb: 2 }}>
                {/* Stage Header */}
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box sx={{ color: stage.fill }}>
                      {getStageIcon(stage.stage)}
                    </Box>
                    <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                      {stage.stage}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      {formatNumber(stage.visitors)}
                    </Typography>
                    <Chip
                      label={`${stage.percentage.toFixed(1)}%`}
                      size="small"
                      sx={{
                        bgcolor: stage.fill,
                        color: 'white',
                        fontWeight: 'bold'
                      }}
                    />
                  </Box>
                </Box>

                {/* Progress Bar */}
                <Box sx={{ position: 'relative', mb: 1 }}>
                  <LinearProgress
                    variant="determinate"
                    value={widthPercentage}
                    sx={{
                      height: 24,
                      borderRadius: 12,
                      bgcolor: 'grey.200',
                      '& .MuiLinearProgress-bar': {
                        bgcolor: stage.fill,
                        borderRadius: 12,
                      },
                    }}
                  />
                  <Box
                    sx={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: widthPercentage > 50 ? 'white' : 'text.primary',
                        fontWeight: 'bold',
                      }}
                    >
                      {stage.percentage.toFixed(1)}%
                    </Typography>
                  </Box>
                </Box>

                {/* Drop-off Indicator */}
                {dropOff !== null && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: 4 }}>
                    <TrendingDown color="error" fontSize="small" />
                    <Typography variant="caption" color="error.main">
                      {dropOff.toFixed(1)}% drop-off from previous stage
                    </Typography>
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>

        {/* Bar Chart Alternative View */}
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="stage" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={formatNumber} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="visitors" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Funnel Analytics Summary */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
            Funnel Analytics
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Overall Conversion Rate
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold', color: MARKETING_COLORS.primary }}>
                {((data[data.length - 1].visitors / data[0].visitors) * 100).toFixed(2)}%
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Biggest Drop-off Stage
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {(() => {
                  let maxDropOff = 0;
                  let maxDropOffStage = '';
                  for (let i = 1; i < data.length; i++) {
                    const dropOff = ((data[i - 1].visitors - data[i].visitors) / data[i - 1].visitors) * 100;
                    if (dropOff > maxDropOff) {
                      maxDropOff = dropOff;
                      maxDropOffStage = `${data[i - 1].stage} → ${data[i].stage}`;
                    }
                  }
                  return maxDropOffStage;
                })()}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Total Visitors
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {formatNumber(data[0].visitors)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Total Conversions
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {formatNumber(data[data.length - 1].visitors)}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Optimization Recommendations */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'info.50', borderRadius: 1, border: 1, borderColor: 'info.200' }}>
          <Typography variant="subtitle2" gutterBottom sx={{ color: 'info.main' }}>
            Optimization Opportunities
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {data.map((stage, index) => {
              if (index === 0) return null;
              const dropOff = calculateDropOff(index);
              if (dropOff && dropOff > 60) {
                return (
                  <Typography key={stage.stage} variant="body2" color="text.secondary">
                    • High drop-off at {stage.stage} stage ({dropOff.toFixed(1)}%) - consider improving user experience
                  </Typography>
                );
              }
              return null;
            })}
            {data.every((_, index) => {
              if (index === 0) return true;
              const dropOff = calculateDropOff(index);
              return !dropOff || dropOff <= 60;
            }) && (
              <Typography variant="body2" color="success.main">
                • Funnel performance looks healthy across all stages
              </Typography>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ConversionFunnelChart;