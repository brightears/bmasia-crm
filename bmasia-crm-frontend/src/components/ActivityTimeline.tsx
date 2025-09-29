import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  Avatar,
  Chip,
  IconButton,
  Tooltip,
  Collapse,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  Divider,
  Alert,
  CircularProgress,
  useTheme,
} from '@mui/material';
import {
  Phone as PhoneIcon,
  Email as EmailIcon,
  Groups as GroupsIcon,
  Slideshow as SlideshowIcon,
  Description as ProposalIcon,
  FollowUp as FollowUpIcon,
  RequestQuote as QuoteIcon,
  Assignment as ContractIcon,
  MoreHoriz as OtherIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  AccessTime as TimeIcon,
  Person as PersonIcon,
  FilterList as FilterIcon,
  ClearAll as ClearIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV2';
import { OpportunityActivity } from '../types';
import ApiService from '../services/api';

interface ActivityTimelineProps {
  opportunityId?: string;
  contactId?: string;
  activities?: OpportunityActivity[];
  onEditActivity?: (activity: OpportunityActivity) => void;
  onDeleteActivity?: (activityId: string) => void;
  onRefresh?: () => void;
  showFilters?: boolean;
  compact?: boolean;
}

const activityTypes = [
  { value: 'Call', label: 'Call', icon: PhoneIcon, color: '#2196f3' },
  { value: 'Email', label: 'Email', icon: EmailIcon, color: '#ff9800' },
  { value: 'Meeting', label: 'Meeting', icon: GroupsIcon, color: '#4caf50' },
  { value: 'Demo', label: 'Demo', icon: SlideshowIcon, color: '#9c27b0' },
  { value: 'Proposal', label: 'Proposal', icon: ProposalIcon, color: '#f44336' },
  { value: 'Follow-up', label: 'Follow-up', icon: FollowUpIcon, color: '#ff5722' },
  { value: 'Quote', label: 'Quote', icon: QuoteIcon, color: '#607d8b' },
  { value: 'Contract', label: 'Contract', icon: ContractIcon, color: '#795548' },
  { value: 'Other', label: 'Other', icon: OtherIcon, color: '#9e9e9e' },
];

interface ActivityFilters {
  activityType: string;
  dateFrom: Date | null;
  dateTo: Date | null;
  completed: string; // 'all', 'completed', 'pending'
}

const ActivityTimeline: React.FC<ActivityTimelineProps> = ({
  opportunityId,
  contactId,
  activities: externalActivities,
  onEditActivity,
  onDeleteActivity,
  onRefresh,
  showFilters = true,
  compact = false,
}) => {
  const theme = useTheme();
  const [activities, setActivities] = useState<OpportunityActivity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedActivities, setExpandedActivities] = useState<Set<string>>(new Set());
  const [showFilterPanel, setShowFilterPanel] = useState(false);
  const [filters, setFilters] = useState<ActivityFilters>({
    activityType: 'all',
    dateFrom: null,
    dateTo: null,
    completed: 'all',
  });

  useEffect(() => {
    if (externalActivities) {
      setActivities(externalActivities);
    } else if (opportunityId || contactId) {
      loadActivities();
    }
  }, [opportunityId, contactId, externalActivities]);

  const loadActivities = async () => {
    try {
      setLoading(true);
      setError('');

      let result: OpportunityActivity[] = [];

      if (opportunityId) {
        result = await ApiService.getActivitiesByOpportunity(opportunityId);
      } else if (contactId) {
        result = await ApiService.getActivitiesByContact(contactId);
      } else {
        const response = await ApiService.getOpportunityActivities();
        result = response.results;
      }

      // Sort by date descending (newest first)
      result.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
      setActivities(result);
    } catch (err: any) {
      setError('Failed to load activities');
      console.error('Load activities error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteActivity = async (activityId: string) => {
    if (window.confirm('Are you sure you want to delete this activity?')) {
      try {
        await ApiService.deleteOpportunityActivity(activityId);
        setActivities(prev => prev.filter(a => a.id !== activityId));

        if (onDeleteActivity) {
          onDeleteActivity(activityId);
        }
        if (onRefresh) {
          onRefresh();
        }
      } catch (err) {
        setError('Failed to delete activity');
        console.error('Delete activity error:', err);
      }
    }
  };

  const toggleExpanded = (activityId: string) => {
    setExpandedActivities(prev => {
      const newSet = new Set(prev);
      if (newSet.has(activityId)) {
        newSet.delete(activityId);
      } else {
        newSet.add(activityId);
      }
      return newSet;
    });
  };

  const getActivityIcon = (activityType: string) => {
    const type = activityTypes.find(t => t.value === activityType);
    if (!type) return OtherIcon;
    return type.icon;
  };

  const getActivityColor = (activityType: string) => {
    const type = activityTypes.find(t => t.value === activityType);
    return type?.color || '#9e9e9e';
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return `Today at ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    } else if (diffDays === 1) {
      return `Yesterday at ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    } else if (diffDays < 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const formatDuration = (minutes: number): string => {
    if (minutes < 60) {
      return `${minutes}m`;
    } else {
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = minutes % 60;
      return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
    }
  };

  const applyFilters = (activities: OpportunityActivity[]): OpportunityActivity[] => {
    return activities.filter(activity => {
      // Activity type filter
      if (filters.activityType !== 'all' && activity.activity_type !== filters.activityType) {
        return false;
      }

      // Date range filter
      const activityDate = new Date(activity.date);
      if (filters.dateFrom && activityDate < filters.dateFrom) {
        return false;
      }
      if (filters.dateTo && activityDate > filters.dateTo) {
        return false;
      }

      // Completion status filter
      if (filters.completed === 'completed' && !activity.completed) {
        return false;
      }
      if (filters.completed === 'pending' && activity.completed) {
        return false;
      }

      return true;
    });
  };

  const clearFilters = () => {
    setFilters({
      activityType: 'all',
      dateFrom: null,
      dateTo: null,
      completed: 'all',
    });
  };

  const filteredActivities = applyFilters(activities);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {/* Header and Filters */}
        {showFilters && (
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">Activity Timeline</Typography>
              <Box>
                <Tooltip title="Toggle Filters">
                  <IconButton
                    onClick={() => setShowFilterPanel(!showFilterPanel)}
                    color={showFilterPanel ? 'primary' : 'default'}
                  >
                    <FilterIcon />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>

            <Collapse in={showFilterPanel}>
              <Paper sx={{ p: 2, mb: 2 }}>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                  <FormControl size="small" sx={{ minWidth: 120 }}>
                    <InputLabel>Activity Type</InputLabel>
                    <Select
                      value={filters.activityType}
                      onChange={(e) => setFilters(prev => ({ ...prev, activityType: e.target.value }))}
                      label="Activity Type"
                    >
                      <MenuItem value="all">All Types</MenuItem>
                      {activityTypes.map(type => (
                        <MenuItem key={type.value} value={type.value}>
                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            <Box
                              sx={{
                                width: 16,
                                height: 16,
                                borderRadius: '50%',
                                backgroundColor: type.color,
                                mr: 1,
                              }}
                            />
                            {type.label}
                          </Box>
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  <DatePicker
                    label="From Date"
                    value={filters.dateFrom}
                    onChange={(newValue) => setFilters(prev => ({ ...prev, dateFrom: newValue }))}
                    slotProps={{
                      textField: { size: 'small', sx: { width: 150 } }
                    }}
                  />

                  <DatePicker
                    label="To Date"
                    value={filters.dateTo}
                    onChange={(newValue) => setFilters(prev => ({ ...prev, dateTo: newValue }))}
                    slotProps={{
                      textField: { size: 'small', sx: { width: 150 } }
                    }}
                  />

                  <FormControl size="small" sx={{ minWidth: 120 }}>
                    <InputLabel>Status</InputLabel>
                    <Select
                      value={filters.completed}
                      onChange={(e) => setFilters(prev => ({ ...prev, completed: e.target.value }))}
                      label="Status"
                    >
                      <MenuItem value="all">All Activities</MenuItem>
                      <MenuItem value="completed">Completed</MenuItem>
                      <MenuItem value="pending">Pending</MenuItem>
                    </Select>
                  </FormControl>

                  <Tooltip title="Clear Filters">
                    <IconButton onClick={clearFilters} size="small">
                      <ClearIcon />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Paper>
            </Collapse>
          </Box>
        )}

        {/* Timeline */}
        {filteredActivities.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              No activities found
            </Typography>
          </Paper>
        ) : (
          <Stack spacing={compact ? 1 : 2}>
            {filteredActivities.map((activity, index) => {
              const isExpanded = expandedActivities.has(activity.id);
              const activityColor = getActivityColor(activity.activity_type);
              const ActivityIcon = getActivityIcon(activity.activity_type);

              return (
                <Card
                  key={activity.id}
                  sx={{
                    position: 'relative',
                    '&::before': index < filteredActivities.length - 1 ? {
                      content: '""',
                      position: 'absolute',
                      left: compact ? 16 : 24,
                      top: compact ? 48 : 56,
                      bottom: compact ? -8 : -16,
                      width: 2,
                      backgroundColor: 'divider',
                      zIndex: 0,
                    } : {},
                  }}
                >
                  <CardContent sx={{ p: compact ? 2 : 3 }}>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                      {/* Activity Icon */}
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: compact ? 32 : 40,
                          height: compact ? 32 : 40,
                          borderRadius: '50%',
                          backgroundColor: activityColor,
                          color: 'white',
                          flexShrink: 0,
                          zIndex: 1,
                          position: 'relative',
                        }}
                      >
                        <ActivityIcon sx={{ fontSize: compact ? 16 : 20 }} />
                      </Box>

                      {/* Activity Content */}
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                          <Box sx={{ flex: 1 }}>
                            <Typography variant={compact ? 'body2' : 'subtitle1'} sx={{ fontWeight: 600, mb: 0.5 }}>
                              {activity.subject}
                            </Typography>

                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                              <Chip
                                label={activity.activity_type}
                                size="small"
                                sx={{
                                  backgroundColor: activityColor,
                                  color: 'white',
                                  fontSize: '0.75rem',
                                  height: 20,
                                }}
                              />

                              <Typography variant="caption" color="text.secondary">
                                {formatDate(activity.date)}
                              </Typography>

                              {activity.duration_minutes && (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                  <TimeIcon sx={{ fontSize: 12 }} />
                                  <Typography variant="caption" color="text.secondary">
                                    {formatDuration(activity.duration_minutes)}
                                  </Typography>
                                </Box>
                              )}

                              {activity.contact_name && (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                  <PersonIcon sx={{ fontSize: 12 }} />
                                  <Typography variant="caption" color="text.secondary">
                                    {activity.contact_name}
                                  </Typography>
                                </Box>
                              )}

                              {activity.completed && (
                                <Chip
                                  label="Completed"
                                  size="small"
                                  color="success"
                                  variant="outlined"
                                  sx={{ height: 20, fontSize: '0.7rem' }}
                                />
                              )}

                              {activity.next_action_date && (
                                <Chip
                                  label={`Follow-up: ${new Date(activity.next_action_date).toLocaleDateString()}`}
                                  size="small"
                                  color="warning"
                                  variant="outlined"
                                  sx={{ height: 20, fontSize: '0.7rem' }}
                                />
                              )}
                            </Box>
                          </Box>

                          {/* Action Buttons */}
                          <Box sx={{ display: 'flex', gap: 0.5, ml: 1 }}>
                            {onEditActivity && (
                              <Tooltip title="Edit Activity">
                                <IconButton
                                  size="small"
                                  onClick={() => onEditActivity(activity)}
                                >
                                  <EditIcon sx={{ fontSize: 16 }} />
                                </IconButton>
                              </Tooltip>
                            )}

                            <Tooltip title="Delete Activity">
                              <IconButton
                                size="small"
                                onClick={() => handleDeleteActivity(activity.id)}
                                color="error"
                              >
                                <DeleteIcon sx={{ fontSize: 16 }} />
                              </IconButton>
                            </Tooltip>

                            {activity.description && (
                              <Tooltip title={isExpanded ? "Collapse" : "Expand"}>
                                <IconButton
                                  size="small"
                                  onClick={() => toggleExpanded(activity.id)}
                                >
                                  {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                </IconButton>
                              </Tooltip>
                            )}
                          </Box>
                        </Box>

                        {/* User Info */}
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                          <Avatar sx={{ width: 20, height: 20, fontSize: '0.7rem', backgroundColor: activityColor }}>
                            {activity.user_name?.split(' ').map(n => n[0]).join('').substring(0, 2)}
                          </Avatar>
                          <Typography variant="caption" color="text.secondary">
                            by {activity.user_name}
                          </Typography>
                        </Box>

                        {/* Expanded Description */}
                        <Collapse in={isExpanded}>
                          {activity.description && (
                            <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                                {activity.description}
                              </Typography>
                            </Box>
                          )}
                        </Collapse>
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              );
            })}
          </Stack>
        )}
      </Box>
    </LocalizationProvider>
  );
};

export default ActivityTimeline;