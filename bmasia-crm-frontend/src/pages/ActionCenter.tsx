import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  ButtonBase,
  Skeleton,
  Alert,
  Button,
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
import { PageHeader, EmptyState } from '../components/ui';

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

  const urgencyTone = (urgency: ActionItem['urgency']): 'error' | 'warning' | 'info' =>
    urgency === 'overdue' ? 'error' : urgency === 'today' ? 'warning' : 'info';

  const handleItemClick = (item: ActionItem) => {
    navigate(item.link_url);
  };

  const renderSummary = () => {
    if (!data) return null;

    const tiles = [
      { label: 'Overdue', value: data.summary.overdue_count, tone: 'error' as const, icon: <ErrorOutline /> },
      { label: 'Due today & tomorrow', value: data.summary.today_count, tone: 'warning' as const, icon: <Today /> },
      { label: 'Coming up this week', value: data.summary.upcoming_count, tone: 'info' as const, icon: <CalendarMonth /> },
      { label: 'Contracts expiring', value: data.summary.expiring_count, tone: 'warning' as const, icon: <Description /> },
    ];

    return (
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', md: 'repeat(4, minmax(0, 1fr))' },
          gap: { xs: 1.5, sm: 2 },
          mb: 3,
        }}
      >
        {tiles.map((tile) => (
          <Paper key={tile.label} sx={{ p: { xs: 1.5, sm: 2 }, display: 'flex', alignItems: 'center', gap: 1.5, minWidth: 0 }}>
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: 2,
                display: 'grid',
                placeItems: 'center',
                flexShrink: 0,
                bgcolor: tile.value > 0 ? `${tile.tone}.main` : 'action.hover',
                color: tile.value > 0 ? '#fff' : 'text.secondary',
                opacity: tile.value > 0 ? 1 : 0.8,
                '& svg': { fontSize: 20 },
              }}
            >
              {tile.icon}
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontSize: '1.5rem', fontWeight: 650, lineHeight: 1.1, fontVariantNumeric: 'tabular-nums' }}>
                {tile.value}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.3 }}>
                {tile.label}
              </Typography>
            </Box>
          </Paper>
        ))}
      </Box>
    );
  };

  const renderActionItem = (item: ActionItem) => {
    const tone = urgencyTone(item.urgency);

    return (
      <ButtonBase
        key={item.id}
        onClick={() => handleItemClick(item)}
        sx={{
          width: '100%',
          textAlign: 'left',
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          px: 2.5,
          py: 1.75,
          borderTop: 1,
          borderColor: 'divider',
          '&:hover': { bgcolor: 'action.hover' },
          '&:hover .row-chevron': { color: 'text.primary', transform: 'translateX(2px)' },
        }}
      >
        <Box
          sx={{
            width: 36,
            height: 36,
            borderRadius: 2,
            display: 'grid',
            placeItems: 'center',
            flexShrink: 0,
            bgcolor: 'action.hover',
            color: `${tone}.main`,
            '& svg': { fontSize: 20 },
          }}
        >
          {getTypeIcon(item.type)}
        </Box>

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.875rem' }} noWrap>
            {item.title}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', color: 'text.secondary' }}>
            <Typography variant="body2" color="text.secondary" noWrap>
              {item.subtitle}
            </Typography>
            {item.contact_name && (
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
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
                >
                  <Person sx={{ fontSize: 15 }} />
                  {item.contact_name}
                </Typography>
              </Tooltip>
            )}
          </Box>
        </Box>

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 1,
            flexWrap: 'wrap',
            maxWidth: { xs: 130, sm: 'none' },
          }}
        >
          {item.amount && item.currency && (
            <Typography
              variant="body2"
              sx={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums', display: { xs: 'none', sm: 'block' } }}
            >
              {item.currency} {item.amount.toLocaleString()}
            </Typography>
          )}
          {item.priority && (
            <Chip
              label={item.priority}
              size="small"
              variant="outlined"
              color={item.priority === 'High' || item.priority === 'Urgent' ? 'error' : 'default'}
              sx={{ display: { xs: 'none', sm: 'inline-flex' } }}
            />
          )}
          {item.type === 'contract' && item.meta?.auto_renew !== undefined && (
            <Chip
              label={item.meta.auto_renew ? 'Auto-renew' : 'Needs Renewal'}
              size="small"
              color={item.meta.auto_renew ? 'success' : 'warning'}
              sx={{ display: { xs: 'none', sm: 'inline-flex' } }}
            />
          )}
          <Chip label={item.time_context} size="small" color={tone} />
        </Box>
        <ChevronRight
          className="row-chevron"
          sx={{ color: 'text.disabled', transition: 'transform 120ms, color 120ms', flexShrink: 0 }}
        />
      </ButtonBase>
    );
  };

  const renderSection = (
    title: string,
    icon: React.ReactNode,
    tone: 'error' | 'warning' | 'info',
    items: ActionItem[]
  ) => {
    if (items.length === 0) return null;

    return (
      <Paper component="section" sx={{ mb: 3, overflow: 'hidden' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2.5, py: 1.75 }}>
          <Box sx={{ color: `${tone}.main`, display: 'flex', '& svg': { fontSize: 20 } }}>{icon}</Box>
          <Typography variant="h6" component="h2">
            {title}
          </Typography>
          <Chip label={items.length} size="small" color={tone} sx={{ ml: 0.5 }} />
        </Box>
        {items.map(renderActionItem)}
      </Paper>
    );
  };

  if (loading) {
    return (
      <Box>
        <PageHeader title="Today" subtitle="Loading what needs your attention…" />
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: 2, mb: 3 }}>
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rounded" height={72} />
          ))}
        </Box>
        <Skeleton variant="rounded" height={260} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <PageHeader title="Today" />
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={fetchActionItems}>
              Try again
            </Button>
          }
        >
          Could not load today's items: {error}
        </Alert>
      </Box>
    );
  }

  if (!data) return null;

  const overdueItems = data.items.filter((item) => item.urgency === 'overdue');
  const todayItems = data.items.filter((item) => item.urgency === 'today');
  const upcomingItems = data.items.filter((item) => item.urgency === 'upcoming');

  return (
    <Box>
      <PageHeader
        title="Today"
        subtitle={`${getGreeting()}, ${user?.first_name || 'there'}. Here's what needs your attention.`}
        actions={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Updated {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </Typography>
            <Tooltip title="Refresh">
              <IconButton onClick={fetchActionItems} aria-label="Refresh" sx={{ border: 1, borderColor: 'divider' }}>
                <Refresh fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        }
      />

      {renderSummary()}

      {data.items.length === 0 ? (
        <Paper>
          <EmptyState
            icon={<CheckCircle />}
            title="All caught up!"
            description="No urgent items need your attention right now."
          />
        </Paper>
      ) : (
        <>
          {renderSection('Overdue', <ErrorOutline />, 'error', overdueItems)}
          {renderSection('Due today & tomorrow', <Today />, 'warning', todayItems)}
          {renderSection('Coming up', <CalendarMonth />, 'info', upcomingItems)}
        </>
      )}
    </Box>
  );
};

export default ActionCenter;
