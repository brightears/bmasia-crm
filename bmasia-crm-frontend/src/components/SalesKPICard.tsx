import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Skeleton,
  Tooltip,
} from '@mui/material';
import { TrendingUp, TrendingDown, TrendingFlat } from '@mui/icons-material';

interface SalesKPICardProps {
  title: string;
  value: number | string;
  previousValue?: number;
  icon: React.ReactNode;
  color?: string;
  format?: 'number' | 'currency' | 'percentage';
  loading?: boolean;
  tooltip?: string;
  trend?: 'up' | 'down' | 'flat';
  trendValue?: number;
}

const SalesKPICard: React.FC<SalesKPICardProps> = ({
  title,
  value,
  previousValue,
  icon,
  color = 'primary.main',
  format = 'number',
  loading = false,
  tooltip,
  trend,
  trendValue,
}) => {
  const formatValue = (val: number | string) => {
    if (typeof val === 'string') return val;

    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(val);
      case 'percentage':
        return `${val.toFixed(1)}%`;
      default:
        return val.toLocaleString();
    }
  };

  const calculateTrend = () => {
    if (!previousValue || typeof value !== 'number') return null;

    const change = ((value - previousValue) / previousValue) * 100;
    const isPositive = change >= 0;
    const isFlat = Math.abs(change) < 0.1;

    return {
      value: Math.abs(change),
      isPositive,
      isFlat,
      icon: isFlat ? TrendingFlat : isPositive ? TrendingUp : TrendingDown,
      color: isFlat ? 'text.secondary' : isPositive ? 'success.main' : 'error.main',
    };
  };

  const trendData = trendValue !== undefined ? {
    value: Math.abs(trendValue),
    isPositive: trendValue >= 0,
    isFlat: Math.abs(trendValue) < 0.1,
    icon: Math.abs(trendValue) < 0.1 ? TrendingFlat : trendValue >= 0 ? TrendingUp : TrendingDown,
    color: Math.abs(trendValue) < 0.1 ? 'text.secondary' : trendValue >= 0 ? 'success.main' : 'error.main',
  } : calculateTrend();

  if (loading) {
    return (
      <Card sx={{ height: '100%' }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <Skeleton variant="circular" width={24} height={24} sx={{ mr: 1 }} />
            <Skeleton variant="text" width={80} height={32} />
          </Box>
          <Skeleton variant="text" width={120} height={20} />
          <Skeleton variant="rectangular" width={60} height={20} sx={{ mt: 1, borderRadius: 1 }} />
        </CardContent>
      </Card>
    );
  }

  const cardContent = (
    <Card sx={{ height: '100%', cursor: tooltip ? 'help' : 'default' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Box sx={{ color, mr: 1, display: 'flex', alignItems: 'center' }}>
            {icon}
          </Box>
          <Typography variant="h6" component="div" sx={{ fontWeight: 'bold' }}>
            {formatValue(value)}
          </Typography>
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {title}
        </Typography>

        {trendData && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', color: trendData.color }}>
              <trendData.icon sx={{ fontSize: 16, mr: 0.5 }} />
            </Box>
            <Chip
              label={`${trendData.isPositive ? '+' : ''}${trendData.value.toFixed(1)}%`}
              size="small"
              color={trendData.isFlat ? 'default' : trendData.isPositive ? 'success' : 'error'}
              variant="outlined"
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );

  if (tooltip) {
    return (
      <Tooltip title={tooltip} arrow placement="top">
        {cardContent}
      </Tooltip>
    );
  }

  return cardContent;
};

export default SalesKPICard;