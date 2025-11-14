import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  GridLegacy as Grid,
} from '@mui/material';
import {
  Email,
  CheckCircle,
  Visibility,
  TouchApp,
  Block,
  Unsubscribe,
} from '@mui/icons-material';
import { EmailCampaign } from '../types';

interface CampaignAnalyticsProps {
  campaign: EmailCampaign;
}

const getOpenRateColor = (rate: number): string => {
  if (rate >= 20) return '#4caf50'; // green
  if (rate >= 10) return '#ff9800'; // orange
  return '#f44336'; // red
};

const getClickRateColor = (rate: number): string => {
  if (rate >= 3) return '#4caf50'; // green
  if (rate >= 1) return '#ff9800'; // orange
  return '#f44336'; // red
};

const getBounceRateColor = (rate: number): string => {
  if (rate <= 2) return '#4caf50'; // green
  if (rate <= 5) return '#ff9800'; // orange
  return '#f44336'; // red
};

const formatRate = (rate: number): string => {
  return `${rate.toFixed(1)}%`;
};

interface MetricCardProps {
  title: string;
  value: number;
  rate?: number;
  icon: React.ReactNode;
  color?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, rate, icon, color }) => {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 40,
              height: 40,
              borderRadius: 1,
              backgroundColor: color ? `${color}20` : 'primary.light',
              color: color || 'primary.main',
              mr: 2,
            }}
          >
            {icon}
          </Box>
          <Typography variant="body2" color="text.secondary">
            {title}
          </Typography>
        </Box>
        <Typography variant="h4" fontWeight="bold">
          {value.toLocaleString()}
        </Typography>
        {rate !== undefined && (
          <Typography variant="body2" sx={{ color: color || 'text.secondary', mt: 0.5 }}>
            {formatRate(rate)}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

const CampaignAnalytics: React.FC<CampaignAnalyticsProps> = ({ campaign }) => {
  const metrics = [
    {
      title: 'Sent',
      value: campaign.total_sent,
      icon: <Email />,
      color: '#2196f3',
    },
    {
      title: 'Delivered',
      value: campaign.total_delivered,
      icon: <CheckCircle />,
      color: '#4caf50',
    },
    {
      title: 'Opened',
      value: campaign.total_opened,
      rate: campaign.open_rate,
      icon: <Visibility />,
      color: getOpenRateColor(campaign.open_rate),
    },
    {
      title: 'Clicked',
      value: campaign.total_clicked,
      rate: campaign.click_rate,
      icon: <TouchApp />,
      color: getClickRateColor(campaign.click_rate),
    },
    {
      title: 'Bounced',
      value: campaign.total_bounced,
      rate: campaign.bounce_rate,
      icon: <Block />,
      color: getBounceRateColor(campaign.bounce_rate),
    },
    {
      title: 'Unsubscribed',
      value: campaign.total_unsubscribed,
      icon: <Unsubscribe />,
      color: '#9e9e9e',
    },
  ];

  return (
    <Grid container spacing={2}>
      {metrics.map((metric, index) => (
        <Grid item xs={12} sm={6} md={4} lg={2} key={index}>
          <MetricCard
            title={metric.title}
            value={metric.value}
            rate={metric.rate}
            icon={metric.icon}
            color={metric.color}
          />
        </Grid>
      ))}
    </Grid>
  );
};

export default CampaignAnalytics;
