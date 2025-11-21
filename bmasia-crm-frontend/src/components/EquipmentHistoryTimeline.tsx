import React from 'react';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
} from '@mui/lab';
import { Box, Typography, Paper, Chip } from '@mui/material';
import {
  Build,
  Settings,
  Construction,
  Upgrade,
  SwapHoriz,
  Delete,
  Notes,
} from '@mui/icons-material';
import { EquipmentHistory } from '../types';
import { format } from 'date-fns';

interface EquipmentHistoryTimelineProps {
  history: EquipmentHistory[];
}

const EquipmentHistoryTimeline: React.FC<EquipmentHistoryTimelineProps> = ({ history }) => {
  const getActionIcon = (action: string) => {
    switch (action) {
      case 'installed':
        return <Build />;
      case 'maintenance':
        return <Settings />;
      case 'repair':
        return <Construction />;
      case 'upgrade':
        return <Upgrade />;
      case 'replaced':
        return <SwapHoriz />;
      case 'retired':
        return <Delete />;
      case 'note':
      default:
        return <Notes />;
    }
  };

  const getActionColor = (action: string): 'success' | 'info' | 'warning' | 'error' | 'grey' => {
    switch (action) {
      case 'installed':
        return 'success';
      case 'maintenance':
        return 'info';
      case 'repair':
        return 'warning';
      case 'retired':
        return 'error';
      default:
        return 'grey';
    }
  };

  // Sort history by date (newest first)
  const sortedHistory = [...history].sort(
    (a, b) => new Date(b.performed_at).getTime() - new Date(a.performed_at).getTime()
  );

  return (
    <Timeline position="right">
      {sortedHistory.map((entry, index) => (
        <TimelineItem key={entry.id}>
          <TimelineOppositeContent color="text.secondary" sx={{ flex: 0.2, pt: 2 }}>
            <Typography variant="caption">
              {format(new Date(entry.performed_at), 'MMM dd, yyyy')}
            </Typography>
            <Typography variant="caption" display="block">
              {format(new Date(entry.performed_at), 'HH:mm')}
            </Typography>
          </TimelineOppositeContent>
          <TimelineSeparator>
            <TimelineDot color={getActionColor(entry.action)}>
              {getActionIcon(entry.action)}
            </TimelineDot>
            {index < sortedHistory.length - 1 && <TimelineConnector />}
          </TimelineSeparator>
          <TimelineContent sx={{ pb: 3 }}>
            <Paper elevation={2} sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Chip
                  label={entry.action}
                  size="small"
                  color={getActionColor(entry.action)}
                  sx={{ textTransform: 'capitalize' }}
                />
                {entry.performed_by_name && (
                  <Typography variant="caption" color="text.secondary">
                    by {entry.performed_by_name}
                  </Typography>
                )}
              </Box>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {entry.description}
              </Typography>
            </Paper>
          </TimelineContent>
        </TimelineItem>
      ))}
    </Timeline>
  );
};

export default EquipmentHistoryTimeline;
