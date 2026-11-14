import React from 'react';
import {
  BottomNavigation,
  BottomNavigationAction,
  Paper,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  TodayOutlined,
  BusinessOutlined,
  HistoryEduOutlined,
  TaskAltOutlined,
  Menu as MenuIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { isActivePath } from './navigation';

interface MobileBottomNavProps {
  /** Opens the full menu (the sidebar drawer). */
  onOpenMenu?: () => void;
}

// The same four shortcuts for everyone; everything else is one tap away under "Menu".
const ITEMS = [
  { label: 'Today', value: '/today', icon: <TodayOutlined /> },
  { label: 'Companies', value: '/companies', icon: <BusinessOutlined /> },
  { label: 'Contracts', value: '/contracts', icon: <HistoryEduOutlined /> },
  { label: 'Tasks', value: '/tasks', icon: <TaskAltOutlined /> },
];

const MENU = '__menu__';

const MobileBottomNav: React.FC<MobileBottomNavProps> = ({ onOpenMenu }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const location = useLocation();

  const current = ITEMS.find((item) => isActivePath(item.value, location.pathname))?.value ?? false;

  const handleChange = (_event: React.SyntheticEvent, newValue: string) => {
    if (newValue === MENU) {
      onOpenMenu?.();
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
      component="nav"
      aria-label="Shortcuts"
      sx={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: theme.zIndex.appBar,
        borderTop: 1,
        borderColor: 'divider',
        borderRadius: 0,
        pb: 'env(safe-area-inset-bottom)',
      }}
    >
      <BottomNavigation
        value={current}
        onChange={handleChange}
        showLabels
        sx={{
          bgcolor: 'background.paper',
          '& .MuiBottomNavigationAction-root': {
            minWidth: 'auto',
            color: 'text.secondary',
            '&.Mui-selected': { color: 'primary.main' },
          },
          '& .MuiBottomNavigationAction-label': {
            fontSize: '0.75rem',
            fontWeight: 500,
            '&.Mui-selected': { fontSize: '0.75rem', fontWeight: 600 },
          },
        }}
      >
        {ITEMS.map((item) => (
          <BottomNavigationAction key={item.value} label={item.label} value={item.value} icon={item.icon} />
        ))}
        <BottomNavigationAction label="Menu" value={MENU} icon={<MenuIcon />} />
      </BottomNavigation>
    </Paper>
  );
};

export default MobileBottomNav;
