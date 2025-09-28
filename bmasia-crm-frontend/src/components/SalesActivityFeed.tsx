import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Avatar,
  Chip,
  Box,
  Skeleton,
  Button,
} from '@mui/material';
import {
  CheckCircle,
  Business,
  Schedule,
  CalendarToday,
  EventNote,
  Phone,
  Email,
  VideoCall,
  Assignment,
  MoreVert,
} from '@mui/icons-material';
import { format, isToday, isYesterday, formatDistanceToNow } from 'date-fns';

interface SalesActivity {
  id: string;
  type: 'deal_closed' | 'opportunity_created' | 'follow_up' | 'meeting' | 'call' | 'email' | 'demo' | 'proposal';
  title: string;
  description: string;
  value?: number;
  contact?: string;
  company: string;
  timestamp: string;
  status?: 'completed' | 'scheduled' | 'overdue' | 'in_progress';
  priority?: 'low' | 'medium' | 'high' | 'urgent';
}

interface SalesActivityFeedProps {
  activities: SalesActivity[];
  loading?: boolean;
  showViewAll?: boolean;
  onViewAll?: () => void;
  maxItems?: number;
}

const SalesActivityFeed: React.FC<SalesActivityFeedProps> = ({
  activities,
  loading = false,
  showViewAll = true,
  onViewAll,
  maxItems = 6,
}) => {
  const getActivityIcon = (type: string) => {
    const iconProps = { fontSize: 'small' as const };

    switch (type) {
      case 'deal_closed': return <CheckCircle color="success" {...iconProps} />;
      case 'opportunity_created': return <Business color="primary" {...iconProps} />;
      case 'follow_up': return <Schedule color="warning" {...iconProps} />;
      case 'meeting': return <CalendarToday color="info" {...iconProps} />;
      case 'call': return <Phone color="primary" {...iconProps} />;
      case 'email': return <Email color="info" {...iconProps} />;
      case 'demo': return <VideoCall color="success" {...iconProps} />;
      case 'proposal': return <Assignment color="warning" {...iconProps} />;
      default: return <EventNote {...iconProps} />;
    }
  };

  const getActivityColor = (status?: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'scheduled': return 'info';
      case 'overdue': return 'error';
      case 'in_progress': return 'warning';
      default: return 'default';
    }
  };

  const getPriorityColor = (priority?: string) => {
    switch (priority) {
      case 'urgent': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'info';
      default: return 'default';
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);

    if (isToday(date)) {
      return `Today, ${format(date, 'HH:mm')}`;
    } else if (isYesterday(date)) {
      return `Yesterday, ${format(date, 'HH:mm')}`;
    } else {
      return format(date, 'MMM dd, HH:mm');
    }
  };

  const displayActivities = activities.slice(0, maxItems);

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Recent Activity
          </Typography>
          <List>
            {Array.from({ length: 4 }).map((_, index) => (
              <ListItem key={index} divider>
                <ListItemAvatar>
                  <Skeleton variant="circular" width={40} height={40} />
                </ListItemAvatar>
                <ListItemText
                  primary={<Skeleton variant="text" width="60%" height={20} />}
                  secondary={
                    <Box>
                      <Skeleton variant="text" width="80%" height={16} />
                      <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                        <Skeleton variant="rectangular" width={60} height={20} sx={{ borderRadius: 1 }} />
                        <Skeleton variant="rectangular" width={80} height={20} sx={{ borderRadius: 1 }} />
                      </Box>
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            Recent Activity
          </Typography>
          {showViewAll && onViewAll && (
            <Button size="small" onClick={onViewAll} endIcon={<MoreVert />}>
              View All
            </Button>
          )}
        </Box>

        {displayActivities.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography variant="body2" color="text.secondary">
              No recent activities to display
            </Typography>
          </Box>
        ) : (
          <List>
            {displayActivities.map((activity, index) => (
              <ListItem
                key={activity.id}
                divider={index < displayActivities.length - 1}
                sx={{ px: 0 }}
              >
                <ListItemAvatar>
                  <Avatar sx={{ bgcolor: 'transparent' }}>
                    {getActivityIcon(activity.type)}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                      <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                        {activity.title}
                      </Typography>
                      {activity.priority && activity.priority !== 'low' && (
                        <Chip
                          label={activity.priority.toUpperCase()}
                          size="small"
                          color={getPriorityColor(activity.priority) as any}
                          variant="outlined"
                          sx={{ height: 20, fontSize: '0.7rem' }}
                        />
                      )}
                    </Box>
                  }
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {activity.description} - {activity.company}
                        {activity.contact && (
                          <Typography component="span" color="text.secondary">
                            {' '}• {activity.contact}
                          </Typography>
                        )}
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Typography variant="caption" color="text.secondary">
                          {formatTimestamp(activity.timestamp)}
                        </Typography>
                        {activity.value && (
                          <Chip
                            label={formatCurrency(activity.value)}
                            size="small"
                            color="success"
                            variant="filled"
                            sx={{ height: 20, fontSize: '0.7rem' }}
                          />
                        )}
                        {activity.status && (
                          <Chip
                            label={activity.status.replace('_', ' ').toUpperCase()}
                            size="small"
                            color={getActivityColor(activity.status) as any}
                            variant="outlined"
                            sx={{ height: 20, fontSize: '0.7rem' }}
                          />
                        )}
                      </Box>
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        )}

        {activities.length > maxItems && showViewAll && (
          <Box sx={{ mt: 2, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              Showing {maxItems} of {activities.length} activities
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default SalesActivityFeed;