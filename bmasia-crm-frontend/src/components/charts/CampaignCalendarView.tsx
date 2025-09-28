import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  IconButton,
  Tooltip,
  Paper,
} from '@mui/material';
import {
  ChevronLeft,
  ChevronRight,
  Email,
  Share as Social,
  Web,
  PhoneAndroid as Mobile,
  DisplaySettings,
  CalendarToday,
} from '@mui/icons-material';
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay, addMonths, subMonths, isWithinInterval, parseISO } from 'date-fns';

interface Campaign {
  id: string;
  name: string;
  status: 'active' | 'scheduled' | 'completed' | 'paused';
  channel: 'email' | 'social' | 'web' | 'mobile' | 'display';
  budget: number;
  spent: number;
  startDate: string;
  endDate: string;
}

interface CampaignCalendarViewProps {
  campaigns: Campaign[];
  loading?: boolean;
}

const MARKETING_COLORS = {
  primary: '#ff6f00',
  secondary: '#ff8f00',
  accent: '#ffb74d',
  status: {
    active: '#4caf50',
    scheduled: '#2196f3',
    completed: '#757575',
    paused: '#ff9800',
  },
};

const CampaignCalendarView: React.FC<CampaignCalendarViewProps> = ({
  campaigns,
  loading = false
}) => {
  const [currentDate, setCurrentDate] = useState(new Date());

  const monthStart = startOfMonth(currentDate);
  const monthEnd = endOfMonth(currentDate);
  const daysInMonth = eachDayOfInterval({ start: monthStart, end: monthEnd });

  const getChannelIcon = (channel: string) => {
    switch (channel) {
      case 'email':
        return <Email fontSize="small" />;
      case 'social':
        return <Social fontSize="small" />;
      case 'web':
        return <Web fontSize="small" />;
      case 'mobile':
        return <Mobile fontSize="small" />;
      case 'display':
        return <DisplaySettings fontSize="small" />;
      default:
        return <CalendarToday fontSize="small" />;
    }
  };

  const getStatusColor = (status: Campaign['status']) => {
    return MARKETING_COLORS.status[status];
  };

  const getCampaignsForDate = (date: Date) => {
    return campaigns.filter(campaign => {
      const startDate = parseISO(campaign.startDate);
      const endDate = parseISO(campaign.endDate);
      return isWithinInterval(date, { start: startDate, end: endDate });
    });
  };

  const getCampaignStartsForDate = (date: Date) => {
    return campaigns.filter(campaign => {
      const startDate = parseISO(campaign.startDate);
      return isSameDay(date, startDate);
    });
  };

  const getCampaignEndsForDate = (date: Date) => {
    return campaigns.filter(campaign => {
      const endDate = parseISO(campaign.endDate);
      return isSameDay(date, endDate);
    });
  };

  const navigateMonth = (direction: 'prev' | 'next') => {
    setCurrentDate(prev => direction === 'prev' ? subMonths(prev, 1) : addMonths(prev, 1));
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
            Campaign Calendar
          </Typography>
          <Box sx={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">Loading campaign calendar...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ color: MARKETING_COLORS.primary }}>
            Campaign Calendar
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Tooltip title="Previous Month">
              <IconButton onClick={() => navigateMonth('prev')} size="small">
                <ChevronLeft />
              </IconButton>
            </Tooltip>
            <Typography variant="h6" sx={{ minWidth: 150, textAlign: 'center' }}>
              {format(currentDate, 'MMMM yyyy')}
            </Typography>
            <Tooltip title="Next Month">
              <IconButton onClick={() => navigateMonth('next')} size="small">
                <ChevronRight />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Calendar Legend */}
        <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
          <Chip
            label="Active"
            size="small"
            sx={{ bgcolor: MARKETING_COLORS.status.active, color: 'white' }}
          />
          <Chip
            label="Scheduled"
            size="small"
            sx={{ bgcolor: MARKETING_COLORS.status.scheduled, color: 'white' }}
          />
          <Chip
            label="Completed"
            size="small"
            sx={{ bgcolor: MARKETING_COLORS.status.completed, color: 'white' }}
          />
          <Chip
            label="Paused"
            size="small"
            sx={{ bgcolor: MARKETING_COLORS.status.paused, color: 'white' }}
          />
        </Box>

        {/* Days of Week Header */}
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 0.5, mb: 1 }}>
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
            <Box key={day} sx={{ p: 1, textAlign: 'center', bgcolor: 'grey.100', borderRadius: 1 }}>
              <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
                {day}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* Calendar Grid */}
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 0.5 }}>
          {/* Empty cells for days before month start */}
          {Array.from({ length: monthStart.getDay() }).map((_, index) => (
            <Box key={`empty-${index}`} sx={{ height: 80 }} />
          ))}

          {/* Days of the month */}
          {daysInMonth.map(date => {
            const campaignsForDate = getCampaignsForDate(date);
            const campaignStarts = getCampaignStartsForDate(date);
            const campaignEnds = getCampaignEndsForDate(date);
            const isToday = isSameDay(date, new Date());

            return (
              <Box key={date.toString()}>
                <Paper
                  elevation={isToday ? 2 : 0}
                  sx={{
                    height: 80,
                    p: 0.5,
                    bgcolor: isToday ? 'primary.50' : 'transparent',
                    border: isToday ? 1 : 0,
                    borderColor: isToday ? 'primary.main' : 'transparent',
                    overflow: 'hidden',
                  }}
                >
                  {/* Date Number */}
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: isToday ? 'bold' : 'normal',
                      color: isToday ? 'primary.main' : 'text.primary'
                    }}
                  >
                    {format(date, 'd')}
                  </Typography>

                  {/* Campaign Indicators */}
                  <Box sx={{ mt: 0.5 }}>
                    {campaignStarts.slice(0, 2).map(campaign => (
                      <Tooltip
                        key={`start-${campaign.id}`}
                        title={`${campaign.name} starts`}
                        arrow
                      >
                        <Chip
                          label="Start"
                          size="small"
                          icon={getChannelIcon(campaign.channel)}
                          sx={{
                            height: 16,
                            fontSize: '0.65rem',
                            mb: 0.25,
                            bgcolor: getStatusColor(campaign.status),
                            color: 'white',
                            '& .MuiChip-icon': {
                              fontSize: '0.75rem',
                              color: 'white'
                            }
                          }}
                        />
                      </Tooltip>
                    ))}

                    {campaignEnds.slice(0, 2).map(campaign => (
                      <Tooltip
                        key={`end-${campaign.id}`}
                        title={`${campaign.name} ends`}
                        arrow
                      >
                        <Chip
                          label="End"
                          size="small"
                          variant="outlined"
                          sx={{
                            height: 16,
                            fontSize: '0.65rem',
                            mb: 0.25,
                            borderColor: getStatusColor(campaign.status),
                            color: getStatusColor(campaign.status),
                          }}
                        />
                      </Tooltip>
                    ))}

                    {/* Running Campaigns Indicator */}
                    {campaignsForDate.length > 0 && campaignStarts.length === 0 && campaignEnds.length === 0 && (
                      <Box
                        sx={{
                          width: '100%',
                          height: 3,
                          bgcolor: MARKETING_COLORS.primary,
                          borderRadius: 1.5,
                          opacity: 0.6,
                          mt: 0.5,
                        }}
                      />
                    )}

                    {/* Campaign Count */}
                    {campaignsForDate.length > 2 && (
                      <Typography
                        variant="caption"
                        sx={{
                          fontSize: '0.6rem',
                          color: 'text.secondary',
                          display: 'block',
                          mt: 0.25
                        }}
                      >
                        +{campaignsForDate.length - 2} more
                      </Typography>
                    )}
                  </Box>
                </Paper>
              </Box>
            );
          })}
        </Box>

        {/* Campaign Summary for Current Month */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
            {format(currentDate, 'MMMM yyyy')} Campaign Summary
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Active Campaigns
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {campaigns.filter(c => c.status === 'active').length}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Scheduled This Month
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {campaigns.filter(c => {
                  const startDate = parseISO(c.startDate);
                  return isWithinInterval(startDate, { start: monthStart, end: monthEnd }) && c.status === 'scheduled';
                }).length}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Ending This Month
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {campaigns.filter(c => {
                  const endDate = parseISO(c.endDate);
                  return isWithinInterval(endDate, { start: monthStart, end: monthEnd });
                }).length}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Total Budget
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {new Intl.NumberFormat('en-US', {
                  style: 'currency',
                  currency: 'USD',
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 0,
                }).format(
                  campaigns
                    .filter(c => {
                      const startDate = parseISO(c.startDate);
                      const endDate = parseISO(c.endDate);
                      return isWithinInterval(startDate, { start: monthStart, end: monthEnd }) ||
                             isWithinInterval(endDate, { start: monthStart, end: monthEnd }) ||
                             (startDate < monthStart && endDate > monthEnd);
                    })
                    .reduce((sum, c) => sum + c.budget, 0)
                )}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Upcoming Campaigns */}
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
            Upcoming Campaign Milestones
          </Typography>
          <Box sx={{ maxHeight: 120, overflow: 'auto' }}>
            {campaigns
              .filter(c => {
                const startDate = parseISO(c.startDate);
                const endDate = parseISO(c.endDate);
                return (startDate >= new Date() || endDate >= new Date()) && c.status !== 'completed';
              })
              .sort((a, b) => parseISO(a.startDate).getTime() - parseISO(b.startDate).getTime())
              .slice(0, 3)
              .map(campaign => (
                <Box key={campaign.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  {getChannelIcon(campaign.channel)}
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    {campaign.name}
                  </Typography>
                  <Chip
                    label={campaign.status}
                    size="small"
                    sx={{
                      bgcolor: getStatusColor(campaign.status),
                      color: 'white',
                      fontSize: '0.7rem'
                    }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {format(parseISO(campaign.startDate), 'MMM dd')}
                  </Typography>
                </Box>
              ))}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default CampaignCalendarView;