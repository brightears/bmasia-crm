import React, { useState, useEffect } from 'react';
import {
  Fab,
  SpeedDial,
  SpeedDialAction,
  SpeedDialIcon,
  Box,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Typography,
  Divider,
  Paper,
  List,
  ListItem,
  Chip,
  IconButton,
  Tooltip,
  Badge,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Add as AddIcon,
  Phone as PhoneIcon,
  Email as EmailIcon,
  Groups as GroupsIcon,
  Slideshow as SlideshowIcon,
  Description as ProposalIcon,
  FollowUp as FollowUpIcon,
  RequestQuote as QuoteIcon,
  Assignment as ContractIcon,
  MoreHoriz as OtherIcon,
  History as HistoryIcon,
  Close as CloseIcon,
  AccessTime as TimeIcon,
} from '@mui/icons-material';
import { OpportunityActivity } from '../types';
import ApiService from '../services/api';
import ActivityForm from './ActivityForm';

interface QuickActivityProps {
  position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left';
  onActivityCreated?: (activity: OpportunityActivity) => void;
  showRecentActivities?: boolean;
  maxRecentActivities?: number;
}

const activityTypes = [
  { value: 'Call', label: 'Log Call', icon: PhoneIcon, color: '#2196f3' },
  { value: 'Email', label: 'Log Email', icon: EmailIcon, color: '#ff9800' },
  { value: 'Meeting', label: 'Log Meeting', icon: GroupsIcon, color: '#4caf50' },
  { value: 'Demo', label: 'Log Demo', icon: SlideshowIcon, color: '#9c27b0' },
  { value: 'Proposal', label: 'Log Proposal', icon: ProposalIcon, color: '#f44336' },
  { value: 'Follow-up', label: 'Log Follow-up', icon: FollowUpIcon, color: '#ff5722' },
  { value: 'Quote', label: 'Log Quote', icon: QuoteIcon, color: '#607d8b' },
  { value: 'Contract', label: 'Log Contract', icon: ContractIcon, color: '#795548' },
  { value: 'Other', label: 'Log Other', icon: OtherIcon, color: '#9e9e9e' },
];

const QuickActivity: React.FC<QuickActivityProps> = ({
  position = 'bottom-right',
  onActivityCreated,
  showRecentActivities = true,
  maxRecentActivities = 5,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [speedDialOpen, setSpeedDialOpen] = useState(false);
  const [activityFormOpen, setActivityFormOpen] = useState(false);
  const [selectedActivityType, setSelectedActivityType] = useState<string>('');
  const [recentActivities, setRecentActivities] = useState<OpportunityActivity[]>([]);
  const [recentActivitiesAnchor, setRecentActivitiesAnchor] = useState<null | HTMLElement>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (showRecentActivities) {
      loadRecentActivities();
    }
  }, [showRecentActivities]);

  const loadRecentActivities = async () => {
    try {
      setLoading(true);
      const response = await ApiService.getOpportunityActivities({
        page_size: maxRecentActivities,
        ordering: '-created_at'
      });
      setRecentActivities(response.results);
    } catch (err) {
      console.error('Failed to load recent activities:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSpeedDialAction = (activityType: string) => {
    setSelectedActivityType(activityType);
    setActivityFormOpen(true);
    setSpeedDialOpen(false);
  };

  const handleActivityCreated = (activity: OpportunityActivity) => {
    if (onActivityCreated) {
      onActivityCreated(activity);
    }

    // Refresh recent activities
    if (showRecentActivities) {
      loadRecentActivities();
    }
  };

  const handleRecentActivitiesClick = (event: React.MouseEvent<HTMLElement>) => {
    setRecentActivitiesAnchor(event.currentTarget);
  };

  const handleRecentActivitiesClose = () => {
    setRecentActivitiesAnchor(null);
  };

  const formatTimeAgo = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffTime / (1000 * 60 * 60));
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    if (diffHours < 1) {
      const diffMinutes = Math.floor(diffTime / (1000 * 60));
      return `${diffMinutes}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else {
      return `${diffDays}d ago`;
    }
  };

  const getActivityColor = (activityType: string) => {
    const type = activityTypes.find(t => t.value === activityType);
    return type?.color || '#9e9e9e';
  };

  const getPositionStyles = () => {
    const baseStyles = {
      position: 'fixed' as const,
      zIndex: theme.zIndex.speedDial,
    };

    switch (position) {
      case 'bottom-right':
        return { ...baseStyles, bottom: 16, right: 16 };
      case 'bottom-left':
        return { ...baseStyles, bottom: 16, left: 16 };
      case 'top-right':
        return { ...baseStyles, top: 16, right: 16 };
      case 'top-left':
        return { ...baseStyles, top: 16, left: 16 };
      default:
        return { ...baseStyles, bottom: 16, right: 16 };
    }
  };

  const positionStyles = getPositionStyles();

  return (
    <>
      <Box sx={positionStyles}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, alignItems: 'flex-end' }}>
          {/* Recent Activities Button */}
          {showRecentActivities && !isMobile && (
            <Tooltip title="Recent Activities">
              <Badge badgeContent={recentActivities.length} color="primary" max={9}>
                <Fab
                  size="small"
                  color="default"
                  onClick={handleRecentActivitiesClick}
                  sx={{
                    backgroundColor: 'background.paper',
                    boxShadow: theme.shadows[4],
                    '&:hover': {
                      backgroundColor: 'action.hover',
                    },
                  }}
                >
                  <HistoryIcon />
                </Fab>
              </Badge>
            </Tooltip>
          )}

          {/* Speed Dial */}
          <SpeedDial
            ariaLabel="Quick Activity"
            icon={<SpeedDialIcon />}
            onClose={() => setSpeedDialOpen(false)}
            onOpen={() => setSpeedDialOpen(true)}
            open={speedDialOpen}
            direction={position.includes('top') ? 'down' : 'up'}
            sx={{
              '& .MuiSpeedDial-fab': {
                backgroundColor: theme.palette.primary.main,
                '&:hover': {
                  backgroundColor: theme.palette.primary.dark,
                },
              },
            }}
          >
            {activityTypes.map((activity) => (
              <SpeedDialAction
                key={activity.value}
                icon={<activity.icon />}
                tooltipTitle={activity.label}
                onClick={() => handleSpeedDialAction(activity.value)}
                sx={{
                  '& .MuiSpeedDialAction-fab': {
                    backgroundColor: activity.color,
                    color: 'white',
                    '&:hover': {
                      backgroundColor: activity.color,
                      filter: 'brightness(0.9)',
                    },
                  },
                }}
              />
            ))}
          </SpeedDial>
        </Box>
      </Box>

      {/* Recent Activities Menu */}
      <Menu
        anchorEl={recentActivitiesAnchor}
        open={Boolean(recentActivitiesAnchor)}
        onClose={handleRecentActivitiesClose}
        PaperProps={{
          sx: {
            maxWidth: 400,
            maxHeight: 500,
          },
        }}
        transformOrigin={{
          vertical: position.includes('top') ? 'bottom' : 'top',
          horizontal: position.includes('left') ? 'left' : 'right',
        }}
        anchorOrigin={{
          vertical: position.includes('top') ? 'top' : 'bottom',
          horizontal: position.includes('left') ? 'left' : 'right',
        }}
      >
        <Box sx={{ p: 2, minWidth: 300 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="h6">Recent Activities</Typography>
            <IconButton size="small" onClick={handleRecentActivitiesClose}>
              <CloseIcon />
            </IconButton>
          </Box>

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
              <Typography variant="body2" color="text.secondary">Loading...</Typography>
            </Box>
          ) : recentActivities.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
              No recent activities
            </Typography>
          ) : (
            <List dense sx={{ pt: 0 }}>
              {recentActivities.map((activity, index) => (
                <React.Fragment key={activity.id}>
                  <ListItem sx={{ px: 0, py: 1 }}>
                    <Box sx={{ width: '100%' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <Box
                          sx={{
                            width: 16,
                            height: 16,
                            borderRadius: '50%',
                            backgroundColor: getActivityColor(activity.activity_type),
                            flexShrink: 0,
                          }}
                        />
                        <Typography variant="body2" sx={{ fontWeight: 600, flex: 1 }}>
                          {activity.subject}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {formatTimeAgo(activity.created_at)}
                        </Typography>
                      </Box>

                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 3 }}>
                        <Chip
                          label={activity.activity_type}
                          size="small"
                          sx={{
                            backgroundColor: getActivityColor(activity.activity_type),
                            color: 'white',
                            fontSize: '0.7rem',
                            height: 18,
                          }}
                        />

                        <Typography variant="caption" color="text.secondary">
                          by {activity.user_name}
                        </Typography>

                        {activity.duration_minutes && (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                            <TimeIcon sx={{ fontSize: 10 }} />
                            <Typography variant="caption" color="text.secondary">
                              {activity.duration_minutes}m
                            </Typography>
                          </Box>
                        )}
                      </Box>
                    </Box>
                  </ListItem>
                  {index < recentActivities.length - 1 && <Divider sx={{ my: 0.5 }} />}
                </React.Fragment>
              ))}
            </List>
          )}
        </Box>
      </Menu>

      {/* Activity Form */}
      <ActivityForm
        open={activityFormOpen}
        onClose={() => {
          setActivityFormOpen(false);
          setSelectedActivityType('');
        }}
        onSave={handleActivityCreated}
        mode="create"
      />
    </>
  );
};

export default QuickActivity;