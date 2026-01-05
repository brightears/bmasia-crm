import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  Tooltip,
  Stack,
  Divider,
} from '@mui/material';
import {
  Add as AddIcon,
  Business as BusinessIcon,
  People as PeopleIcon,
  Handshake as HandshakeIcon,
  Assignment as AssignmentIcon,
  Campaign as CampaignIcon,
  SupportAgent as SupportAgentIcon,
  AdminPanelSettings as AdminIcon,
  Phone as PhoneIcon,
  Email as EmailIcon,
  Event as EventIcon,
  TaskAlt as TaskIcon,
  Description as DescriptionIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import QuickTaskCreate from './QuickTaskCreate';

interface QuickAction {
  title: string;
  description: string;
  icon: React.ReactNode;
  action: () => void;
  color: string;
  roles?: string[];
}

const QuickActions: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [quickTaskOpen, setQuickTaskOpen] = useState(false);

  const quickActions: QuickAction[] = [
    // Sales Actions
    {
      title: 'Add Company',
      description: 'Create a new company record',
      icon: <BusinessIcon />,
      action: () => navigate('/companies/new'),
      color: '#1976d2',
      roles: ['Sales', 'Admin'],
    },
    {
      title: 'Add Contact',
      description: 'Add a new contact',
      icon: <PeopleIcon />,
      action: () => navigate('/contacts?new=true'),
      color: '#1976d2',
      roles: ['Sales', 'Admin'],
    },
    {
      title: 'New Opportunity',
      description: 'Create sales opportunity',
      icon: <HandshakeIcon />,
      action: () => navigate('/opportunities?new=true'),
      color: '#1976d2',
      roles: ['Sales', 'Admin'],
    },
    {
      title: 'Quick Call',
      description: 'Log a phone call',
      icon: <PhoneIcon />,
      action: () => navigate('/tasks?new=true&type=call'),
      color: '#1976d2',
      roles: ['Sales', 'Admin'],
    },

    // Marketing Actions
    {
      title: 'New Campaign',
      description: 'Create marketing campaign',
      icon: <CampaignIcon />,
      action: () => navigate('/campaigns/new'),
      color: '#7b1fa2',
      roles: ['Marketing', 'Admin'],
    },
    {
      title: 'Email Template',
      description: 'Create email template',
      icon: <EmailIcon />,
      action: () => navigate('/email-templates?new=true'),
      color: '#7b1fa2',
      roles: ['Marketing', 'Admin'],
    },
    {
      title: 'Schedule Event',
      description: 'Plan marketing event',
      icon: <EventIcon />,
      action: () => navigate('/tasks?new=true&type=event'),
      color: '#7b1fa2',
      roles: ['Marketing', 'Admin'],
    },

    // Tech Support Actions
    {
      title: 'New Ticket',
      description: 'Create support ticket',
      icon: <SupportAgentIcon />,
      action: () => navigate('/tickets/new'),
      color: '#388e3c',
      roles: ['Tech Support', 'Admin'],
    },
    {
      title: 'Add Task',
      description: 'Create a new task',
      icon: <TaskIcon />,
      action: () => setQuickTaskOpen(true),
      color: '#388e3c',
      roles: ['Tech Support', 'Sales', 'Marketing', 'Admin'],
    },

    // Admin Actions
    {
      title: 'New Contract',
      description: 'Create new contract',
      icon: <AssignmentIcon />,
      action: () => navigate('/contracts?new=true'),
      color: '#616161',
      roles: ['Admin'],
    },
    {
      title: 'New Quote',
      description: 'Create new quote',
      icon: <DescriptionIcon />,
      action: () => navigate('/quotes?new=true'),
      color: '#616161',
      roles: ['Sales', 'Admin'],
    },
    {
      title: 'User Management',
      description: 'Manage user accounts',
      icon: <AdminIcon />,
      action: () => navigate('/users'),
      color: '#616161',
      roles: ['Admin'],
    },
  ];

  const filteredActions = quickActions.filter(action =>
    !action.roles || action.roles.includes(user?.role || '')
  );

  const recentActions = [
    { title: 'Called ABC Corp', time: '2 hours ago', type: 'call' },
    { title: 'Updated XYZ opportunity', time: '4 hours ago', type: 'update' },
    { title: 'Created new contact', time: '1 day ago', type: 'create' },
    { title: 'Sent proposal to DEF Ltd', time: '2 days ago', type: 'email' },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        {/* Quick Actions */}
        <Box sx={{ flex: '2 1 500px', minWidth: 400 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Typography variant="h6" sx={{ flexGrow: 1 }}>
                  Quick Actions
                </Typography>
                <Tooltip title="Customize actions">
                  <IconButton size="small">
                    <AddIcon />
                  </IconButton>
                </Tooltip>
              </Box>

              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {filteredActions.slice(0, 8).map((action, index) => (
                  <Box key={index} sx={{ flex: '1 1 200px', minWidth: 180 }}>
                    <Card
                      sx={{
                        cursor: 'pointer',
                        transition: 'all 0.2s ease-in-out',
                        '&:hover': {
                          transform: 'translateY(-2px)',
                          boxShadow: 3,
                        },
                        border: '1px solid',
                        borderColor: 'divider',
                      }}
                      onClick={action.action}
                    >
                      <CardContent sx={{ textAlign: 'center', py: 2 }}>
                        <Box
                          sx={{
                            width: 48,
                            height: 48,
                            borderRadius: '50%',
                            backgroundColor: `${action.color}15`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            mx: 'auto',
                            mb: 2,
                            color: action.color,
                          }}
                        >
                          {action.icon}
                        </Box>
                        <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                          {action.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {action.description}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Box>
                ))}
              </Box>

              {filteredActions.length > 8 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                  <Button variant="outlined" size="small">
                    View All Actions
                  </Button>
                </Box>
              )}
            </CardContent>
          </Card>
        </Box>

        {/* Recent Activity */}
        <Box sx={{ flex: '1 1 300px', minWidth: 250 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Recent Activity
              </Typography>

              <Stack spacing={2}>
                {recentActions.map((activity, index) => (
                  <Box key={index}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                      <Box
                        sx={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          backgroundColor: 'primary.main',
                          mt: 1,
                          flexShrink: 0,
                        }}
                      />
                      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {activity.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {activity.time}
                        </Typography>
                      </Box>
                    </Box>
                    {index < recentActions.length - 1 && (
                      <Divider sx={{ my: 1.5, ml: 3 }} />
                    )}
                  </Box>
                ))}
              </Stack>

              <Box sx={{ mt: 3 }}>
                <Button
                  variant="text"
                  size="small"
                  fullWidth
                  onClick={() => navigate('/activity')}
                >
                  View All Activity
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>

      {/* Quick Task Create Dialog */}
      <QuickTaskCreate
        open={quickTaskOpen}
        onClose={() => setQuickTaskOpen(false)}
        onSuccess={(task) => {
          setQuickTaskOpen(false);
          // Navigate to tasks page or show success message
          navigate('/tasks');
        }}
      />
    </Box>
  );
};

export default QuickActions;