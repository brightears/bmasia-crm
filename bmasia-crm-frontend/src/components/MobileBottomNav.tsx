import React, { useMemo } from 'react';
import {
  BottomNavigation,
  BottomNavigationAction,
  Paper,
  Badge,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Business as BusinessIcon,
  People as PeopleIcon,
  Handshake as HandshakeIcon,
  Campaign as CampaignIcon,
  SupportAgent as SupportAgentIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const MobileBottomNav: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const getNavigationItems = useMemo(() => {
    const baseItems = [
      {
        label: 'Dashboard',
        value: '/dashboard',
        icon: <DashboardIcon />,
        roles: ['Sales', 'Marketing', 'Tech Support', 'Admin'],
      },
    ];

    switch (user?.role) {
      case 'Sales':
        return [
          ...baseItems,
          {
            label: 'Companies',
            value: '/companies',
            icon: <BusinessIcon />,
            roles: ['Sales', 'Admin'],
          },
          {
            label: 'Contacts',
            value: '/contacts',
            icon: <PeopleIcon />,
            roles: ['Sales', 'Admin'],
          },
          {
            label: 'Opportunities',
            value: '/opportunities',
            icon: <Badge badgeContent={2} color="error"><HandshakeIcon /></Badge>,
            roles: ['Sales', 'Admin'],
          },
          {
            label: 'More',
            value: '/more',
            icon: <SettingsIcon />,
            roles: ['Sales', 'Marketing', 'Tech Support', 'Admin'],
          },
        ];

      case 'Marketing':
        return [
          ...baseItems,
          {
            label: 'Campaigns',
            value: '/campaigns',
            icon: <CampaignIcon />,
            roles: ['Marketing', 'Admin'],
          },
          {
            label: 'Contacts',
            value: '/contacts',
            icon: <PeopleIcon />,
            roles: ['Marketing', 'Admin'],
          },
          {
            label: 'Analytics',
            value: '/analytics',
            icon: <BusinessIcon />,
            roles: ['Marketing', 'Admin'],
          },
          {
            label: 'More',
            value: '/more',
            icon: <SettingsIcon />,
            roles: ['Sales', 'Marketing', 'Tech Support', 'Admin'],
          },
        ];

      case 'Tech Support':
        return [
          ...baseItems,
          {
            label: 'Tickets',
            value: '/tickets',
            icon: <Badge badgeContent={5} color="error"><SupportAgentIcon /></Badge>,
            roles: ['Tech Support', 'Admin'],
          },
          {
            label: 'Knowledge',
            value: '/knowledge-base',
            icon: <BusinessIcon />,
            roles: ['Tech Support', 'Admin'],
          },
          {
            label: 'Equipment',
            value: '/equipment',
            icon: <PeopleIcon />,
            roles: ['Tech Support', 'Admin'],
          },
          {
            label: 'More',
            value: '/more',
            icon: <SettingsIcon />,
            roles: ['Sales', 'Marketing', 'Tech Support', 'Admin'],
          },
        ];

      case 'Admin':
        return [
          ...baseItems,
          {
            label: 'Companies',
            value: '/companies',
            icon: <BusinessIcon />,
            roles: ['Admin'],
          },
          {
            label: 'Users',
            value: '/users',
            icon: <PeopleIcon />,
            roles: ['Admin'],
          },
          {
            label: 'Reports',
            value: '/reports',
            icon: <BusinessIcon />,
            roles: ['Admin'],
          },
          {
            label: 'More',
            value: '/more',
            icon: <SettingsIcon />,
            roles: ['Admin'],
          },
        ];

      default:
        return baseItems;
    }
  }, [user?.role]);

  const getCurrentValue = () => {
    const currentPath = location.pathname;
    const matchingItem = getNavigationItems.find(item =>
      currentPath.startsWith(item.value)
    );
    return matchingItem?.value || '/dashboard';
  };

  const handleChange = (event: React.SyntheticEvent, newValue: string) => {
    if (newValue === '/more') {
      // Handle "More" menu - could open a drawer or navigate to a menu page
      navigate('/more');
    } else {
      navigate(newValue);
    }
  };

  // Only show on mobile devices
  if (!isMobile) {
    return null;
  }

  return (
    <Paper
      sx={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: theme.zIndex.appBar,
        borderTop: '1px solid',
        borderColor: 'divider',
      }}
      elevation={3}
    >
      <BottomNavigation
        value={getCurrentValue()}
        onChange={handleChange}
        showLabels
        sx={{
          '& .MuiBottomNavigationAction-root': {
            minWidth: 'auto',
            paddingTop: 1,
            '&.Mui-selected': {
              color: 'primary.main',
            },
          },
        }}
      >
        {getNavigationItems.map((item) => (
          <BottomNavigationAction
            key={item.value}
            label={item.label}
            value={item.value}
            icon={item.icon}
            sx={{
              fontSize: '0.75rem',
              '& .MuiBottomNavigationAction-label': {
                fontSize: '0.75rem',
                fontWeight: 500,
              },
            }}
          />
        ))}
      </BottomNavigation>
    </Paper>
  );
};

export default MobileBottomNav;