import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Divider,
} from '@mui/material';
import {
  Assignment,
  Receipt,
  Handshake,
  Description,
  Person,
  ErrorOutline,
  Today,
  CalendarMonth,
  Refresh,
  CheckCircle,
  ChevronRight,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import ApiService from '../services/api';

interface ActionItem {
  id: string;
  type: 'task' | 'invoice' | 'opportunity' | 'contract';
  urgency: 'overdue' | 'today' | 'upcoming';
  title: string;
  subtitle: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  time_context: string;
  priority?: string;
  amount?: number;
  currency?: string;
  link_url: string;
  link_id: string;
  meta?: {
    task_type?: string;
    assigned_to?: string;
    stage?: string;
    auto_renew?: boolean;
    [key: string]: any;
  };
}

interface ActionCenterData {
  items: ActionItem[];
  summary: {
    overdue_count: number;
    today_count: number;
    upcoming_count: number;
    expiring_count: number;
  };
}

const ActionCenter: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<ActionCenterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  const fetchActionItems = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await ApiService.getActionCenterItems();
      setData(response);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.message || 'Failed to load action items');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActionItems();
  }, []);

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  const getTypeIcon = (type: ActionItem['type']) => {
    switch (type) {
      case 'task':
        return <Assignment />;
      case 'invoice':
        return <Receipt />;
      case 'opportunity':
        return <Handshake />;
      case 'contract':
        return <Description />;
      default:
        return <Assignment />;
    }
  };

  const getBorderColor = (urgency: ActionItem['urgency']) => {
    switch (urgency) {
      case 'overdue':
        return '#d32f2f';
      case 'today':
        return '#FFA500';
      case 'upcoming':
        return '#1976d2';
      default:
        return '#1976d2';
    }
  };

  const getUrgencyChipColor = (urgency: ActionItem['urgency']) => {
    switch (urgency) {
      case 'overdue':
        return { bg: '#d32f2f', color: '#fff' };
      case 'today':
        return { bg: '#FFA500', color: '#fff' };
      case 'upcoming':
        return { bg: '#1976d2', color: '#fff' };
      default:
        return { bg: '#1976d2', color: '#fff' };
    }
  };

  const handleItemClick = (item: ActionItem) => {
    navigate(item.link_url);
  };

  const renderSummaryChips = () => {
    if (!data) return null;

    const chips = [
      {
        label: `${data.summary.overdue_count} Overdue`,
        bg: '#d32f2f',
        show: data.summary.overdue_count > 0,
      },
      {
        label: `${data.summary.today_count} Due Today`,
        bg: '#FFA500',
        show: data.summary.today_count > 0,
      },
      {
        label: `${data.summary.upcoming_count} This Week`,
        bg: '#1976d2',
        show: data.summary.upcoming_count > 0,
      },
      {
        label: `${data.summary.expiring_count} Expiring`,
        bg: '#f57c00',
        show: data.summary.expiring_count > 0,
      },
    ];

    return (
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 3 }}>
        {chips
          .filter((chip) => chip.show)
          .map((chip, index) => (
            <Chip
              key={index}
              label={chip.label}
              sx={{
                backgroundColor: chip.bg,
                color: '#fff',
                fontWeight: 600,
              }}
            />
          ))}
      </Box>
    );
  };

  const renderActionItem = (item: ActionItem) => {
    const chipColors = getUrgencyChipColor(item.urgency);

    return (
      <Paper
        key={item.id}
        sx={{
          p: 2,
          mb: 2,
          borderLeft: `4px solid ${getBorderColor(item.urgency)}`,
          cursor: 'pointer',
          transition: 'all 0.2s',
          '&:hover': {
            boxShadow: 3,
            transform: 'translateX(4px)',
          },
        }}
        onClick={() => handleItemClick(item)}
      >
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <Box sx={{ color: getBorderColor(item.urgency), pt: 0.5 }}>
            {getTypeIcon(item.type)}
          </Box>

          <Box sx={{ flex: 1 }}>
            <Typography variant="body1" fontWeight={600} gutterBottom>
              {item.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {item.subtitle}
            </Typography>
            <Tooltip
              title={
                <Box>
                  <Typography variant="body2">{item.contact_email}</Typography>
                  {item.contact_phone && (
                    <Typography variant="body2">{item.contact_phone}</Typography>
                  )}
                </Box>
              }
              arrow
            >
              <Chip
                icon={<Person />}
                label={item.contact_name}
                size="small"
                sx={{ mt: 1 }}
              />
            </Tooltip>
          </Box>

          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              gap: 1,
            }}
          >
            <Chip
              label={item.time_context}
              size="small"
              sx={{
                backgroundColor: chipColors.bg,
                color: chipColors.color,
                fontWeight: 600,
              }}
            />
            {item.amount && item.currency && (
              <Typography variant="body2" fontWeight={600} color="primary">
                {item.currency} {item.amount.toLocaleString()}
              </Typography>
            )}
            {item.priority && (
              <Chip
                label={item.priority}
                size="small"
                color={item.priority === 'High' ? 'error' : 'default'}
              />
            )}
            {item.type === 'contract' && item.meta?.auto_renew !== undefined && (
              <Chip
                label={item.meta.auto_renew ? 'Auto-renew' : 'Needs Renewal'}
                size="small"
                color={item.meta.auto_renew ? 'success' : 'warning'}
              />
            )}
            <ChevronRight sx={{ color: 'text.secondary' }} />
          </Box>
        </Box>
      </Paper>
    );
  };

  const renderSection = (
    title: string,
    icon: React.ReactNode,
    color: string,
    items: ActionItem[]
  ) => {
    if (items.length === 0) return null;

    return (
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <Box sx={{ color }}>{icon}</Box>
          <Typography variant="h6" sx={{ color }}>
            {title}
          </Typography>
          <Chip label={items.length} size="small" sx={{ ml: 1 }} />
        </Box>
        <Divider sx={{ mb: 2 }} />
        {items.map(renderActionItem)}
      </Box>
    );
  };

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '400px',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">Error: {error}</Typography>
      </Box>
    );
  }

  if (!data) return null;

  const overdueItems = data.items.filter((item) => item.urgency === 'overdue');
  const todayItems = data.items.filter((item) => item.urgency === 'today');
  const upcomingItems = data.items.filter((item) => item.urgency === 'upcoming');

  return (
    <Box sx={{ p: 3 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          mb: 3,
        }}
      >
        <Box>
          <Typography variant="h4" gutterBottom>
            Today
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {getGreeting()}, {user?.first_name}! Here's what needs your attention.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 0.5 }}>
          <IconButton onClick={fetchActionItems} color="primary">
            <Refresh />
          </IconButton>
          <Typography variant="caption" color="text.secondary">
            Last refreshed: {lastRefreshed.toLocaleTimeString()}
          </Typography>
        </Box>
      </Box>

      {renderSummaryChips()}

      {data.items.length === 0 ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '300px',
            gap: 2,
          }}
        >
          <CheckCircle sx={{ fontSize: 80, color: '#4caf50' }} />
          <Typography variant="h5" fontWeight={600}>
            All caught up!
          </Typography>
          <Typography variant="body1" color="text.secondary">
            No urgent items need your attention right now.
          </Typography>
        </Box>
      ) : (
        <>
          {renderSection('Overdue', <ErrorOutline />, '#d32f2f', overdueItems)}
          {renderSection('Due Today & Tomorrow', <Today />, '#FFA500', todayItems)}
          {renderSection('Coming Up', <CalendarMonth />, '#1976d2', upcomingItems)}
        </>
      )}
    </Box>
  );
};

export default ActionCenter;
