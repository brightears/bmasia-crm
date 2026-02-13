import React, { useState, useRef } from 'react';
import {
  AppBar,
  Box,
  CssBaseline,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Menu,
  MenuItem,
  Avatar,
  Divider,
  useTheme,
  useMediaQuery,
  Badge,
  Tooltip,
  alpha,
  Chip,
  Button,
  Collapse,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Business as BusinessIcon,
  People as PeopleIcon,
  Assignment as AssignmentIcon,
  Receipt as ReceiptIcon,
  Logout,
  Notifications as NotificationsIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  ExpandLess,
  ExpandMore,
  Campaign as CampaignIcon,
  Email as EmailIcon,
  Group as GroupIcon,
  LightMode as LightModeIcon,
  DarkMode as DarkModeIcon,
  Person as PersonIcon,
  Today as TodayIcon,
  TrendingUp as TrendingUpIcon,
  Description as DescriptionIcon,
  TrackChanges as TrackChangesIcon,
  CheckCircle as CheckCircleIcon,
  Support as SupportIcon,
  MenuBook as MenuBookIcon,
  LocationOn,
  AutoMode as AutoModeIcon,
  Settings as SettingsIcon,
  Wifi as WifiIcon,
  AttachMoney as AttachMoneyIcon,
  CameraAlt as CameraAltIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import ApiService from '../services/api';
import { useThemeContext } from '../contexts/ThemeContext';
import MobileBottomNav from './MobileBottomNav';

const drawerWidth = 280;
const miniDrawerWidth = 64;

// Department color scheme - Supports both new and legacy roles
// Default color for unknown roles
const defaultDepartmentColor = {
  primary: '#616161',
  light: '#9e9e9e',
  dark: '#424242',
  background: alpha('#616161', 0.08),
};

const departmentColors: Record<string, { primary: string; light: string; dark: string; background: string }> = {
  Sales: {
    primary: '#1976d2',
    light: '#42a5f5',
    dark: '#1565c0',
    background: alpha('#1976d2', 0.08),
  },
  Finance: {
    primary: '#0288d1',
    light: '#03a9f4',
    dark: '#01579b',
    background: alpha('#0288d1', 0.08),
  },
  Tech: {
    primary: '#388e3c',
    light: '#66bb6a',
    dark: '#2e7d32',
    background: alpha('#388e3c', 0.08),
  },
  Music: {
    primary: '#7b1fa2',
    light: '#ba68c8',
    dark: '#6a1b9a',
    background: alpha('#7b1fa2', 0.08),
  },
  Admin: {
    primary: '#616161',
    light: '#9e9e9e',
    dark: '#424242',
    background: alpha('#616161', 0.08),
  },
  // Legacy role support
  Marketing: {
    primary: '#7b1fa2',
    light: '#ba68c8',
    dark: '#6a1b9a',
    background: alpha('#7b1fa2', 0.08),
  },
  'Tech Support': {
    primary: '#388e3c',
    light: '#66bb6a',
    dark: '#2e7d32',
    background: alpha('#388e3c', 0.08),
  },
};

// Unified navigation for all users
const unifiedNavigation = [
  {
    title: 'Overview',
    items: [
      { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
      { text: 'Today', icon: <TodayIcon />, path: '/today' },
    ],
  },
  {
    title: 'Customer Management',
    items: [
      { text: 'Companies', icon: <BusinessIcon />, path: '/companies' },
      { text: 'Contacts', icon: <PeopleIcon />, path: '/contacts' },
      { text: 'Opportunities', icon: <TrendingUpIcon />, path: '/opportunities' },
    ],
  },
  {
    title: 'Sales Operations',
    items: [
      { text: 'Quotes', icon: <DescriptionIcon />, path: '/quotes' },
      { text: 'Contracts', icon: <AssignmentIcon />, path: '/contracts' },
      { text: 'Invoices', icon: <ReceiptIcon />, path: '/invoices' },
      { text: 'Performance', icon: <TrackChangesIcon />, path: '/targets' },
      { text: 'Tasks', icon: <CheckCircleIcon />, path: '/tasks' },
    ],
  },
  {
    title: 'Marketing & Campaigns',
    items: [
      { text: 'Campaigns', icon: <CampaignIcon />, path: '/campaigns' },
      { text: 'Email Templates', icon: <EmailIcon />, path: '/email-templates' },
      { text: 'Email Automations', icon: <AutoModeIcon />, path: '/email-automations' },
      { text: 'Segments', icon: <GroupIcon />, path: '/segments' },
    ],
  },
  {
    title: 'Finance',
    items: [
      { text: 'Revenue', icon: <AttachMoneyIcon />, path: '/revenue' },
      { text: 'AR Aging', icon: <ReceiptIcon />, path: '/finance/ar' },
      { text: 'AP Aging', icon: <ReceiptIcon />, path: '/finance/ap' },
      { text: 'Profit & Loss', icon: <ReceiptIcon />, path: '/finance/pl' },
      { text: 'Cash Flow', icon: <ReceiptIcon />, path: '/finance/cash-flow' },
      { text: 'Balance Sheet', icon: <ReceiptIcon />, path: '/finance/balance-sheet' },
    ],
  },
  {
    title: 'Tech Support',
    items: [
      { text: 'Tickets', icon: <SupportIcon />, path: '/tickets' },
      { text: 'Knowledge Base', icon: <MenuBookIcon />, path: '/knowledge-base' },
      { text: 'Zones', icon: <LocationOn />, path: '/zones' },
    ],
  },
  {
    title: 'Administration',
    items: [
      { text: 'Users', icon: <PeopleIcon />, path: '/users' },
      { text: 'Contract Templates', icon: <DescriptionIcon />, path: '/contract-templates' },
      { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
    ],
  },
];


interface LayoutProps {
  children: React.ReactNode;
}

interface NavigationSectionProps {
  title: string;
  items: Array<{
    text: string;
    icon: React.ReactNode;
    path: string;
    badge?: number;
  }>;
  isCollapsed: boolean;
  currentPath: string;
  departmentColor: string;
  onNavigate: (path: string) => void;
}

const NavigationSection: React.FC<NavigationSectionProps> = ({
  title,
  items,
  isCollapsed,
  currentPath,
  departmentColor,
  onNavigate,
}) => {
  const [open, setOpen] = useState(true);

  if (isCollapsed) {
    return (
      <>
        {items.map((item) => (
          <Tooltip key={item.text} title={item.text} placement="right">
            <ListItem disablePadding>
              <ListItemButton
                selected={currentPath === item.path}
                onClick={() => onNavigate(item.path)}
                sx={{
                  minHeight: 48,
                  justifyContent: 'center',
                  px: 2.5,
                  '&:hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  },
                  '&.Mui-selected': {
                    backgroundColor: 'rgba(255, 140, 0, 0.15)',
                    '&:hover': {
                      backgroundColor: 'rgba(255, 140, 0, 0.25)',
                    },
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    minWidth: 0,
                    mr: 0,
                    justifyContent: 'center',
                    color: currentPath === item.path ? '#FF8C00' : '#94a3b8',
                  }}
                >
                  <Badge badgeContent={item.badge} color="error">
                    {item.icon}
                  </Badge>
                </ListItemIcon>
              </ListItemButton>
            </ListItem>
          </Tooltip>
        ))}
        <Divider sx={{ my: 1, borderColor: 'rgba(255,255,255,0.08)' }} />
      </>
    );
  }

  return (
    <>
      <ListItemButton onClick={() => setOpen(!open)} sx={{ py: 0.5 }}>
        <ListItemText
          primary={title}
          primaryTypographyProps={{
            fontSize: '0.875rem',
            fontWeight: 600,
            color: '#94a3b8',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        />
        {open ? <ExpandLess sx={{ color: '#94a3b8' }} /> : <ExpandMore sx={{ color: '#94a3b8' }} />}
      </ListItemButton>
      <Collapse in={open} timeout="auto" unmountOnExit>
        <List component="div" disablePadding>
          {items.map((item) => (
            <ListItem key={item.text} disablePadding>
              <ListItemButton
                selected={currentPath === item.path}
                onClick={() => onNavigate(item.path)}
                sx={{
                  pl: 3,
                  py: 1,
                  '&:hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  },
                  '&.Mui-selected': {
                    backgroundColor: 'rgba(255, 140, 0, 0.15)',
                    borderRight: '3px solid #FF8C00',
                    '&:hover': {
                      backgroundColor: 'rgba(255, 140, 0, 0.25)',
                    },
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    color: currentPath === item.path ? '#FF8C00' : '#94a3b8',
                  }}
                >
                  <Badge badgeContent={item.badge} color="error">
                    {item.icon}
                  </Badge>
                </ListItemIcon>
                <ListItemText primary={item.text} primaryTypographyProps={{ sx: { color: '#cbd5e1' } }} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Collapse>
    </>
  );
};

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.between('md', 'lg'));
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [drawerCollapsed, setDrawerCollapsed] = useState(isTablet);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [notificationAnchorEl, setNotificationAnchorEl] = useState<null | HTMLElement>(null);
  const { darkMode, toggleDarkMode } = useThemeContext();
  const avatarInputRef = useRef<HTMLInputElement>(null);

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const result = await ApiService.uploadAvatar(file);
      // Update user in auth context by reloading
      window.location.reload();
    } catch (err) {
      console.error('Avatar upload failed:', err);
    }
  };

  // Get unified navigation and default color
  const userRole = user?.role || 'Admin';
  const navigation = unifiedNavigation;
  const departmentColor = departmentColors[userRole] || defaultDepartmentColor;

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleDrawerCollapse = () => {
    setDrawerCollapsed(!drawerCollapsed);
  };

  const handleUserMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleUserMenuClose = () => {
    setAnchorEl(null);
  };

  const handleNotificationMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setNotificationAnchorEl(event.currentTarget);
  };

  const handleNotificationMenuClose = () => {
    setNotificationAnchorEl(null);
  };

  const handleLogout = async () => {
    handleUserMenuClose();
    await logout();
  };

  const handleNavigate = (path: string) => {
    navigate(path);
    if (isMobile) {
      setMobileOpen(false);
    }
  };

  const getCurrentDrawerWidth = () => {
    if (isMobile) return drawerWidth;
    return drawerCollapsed ? miniDrawerWidth : drawerWidth;
  };

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box
        sx={{
          height: 80,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          px: drawerCollapsed && !isMobile ? 1 : 2,
          backgroundColor: '#ffffff',
          borderBottom: '1px solid rgba(0,0,0,0.08)',
        }}
      >
        {drawerCollapsed && !isMobile ? (
          <Tooltip title="BMAsia CRM" placement="right">
            <Box component="img" src="/bmasia-logo.png" alt="BMAsia" sx={{ height: 36, borderRadius: '4px' }} />
          </Tooltip>
        ) : (
          <>
            <Box component="img" src="/bmasia-logo.png" alt="BMAsia" sx={{ height: 42, borderRadius: '4px' }} />
            {!isMobile && (
              <IconButton
                onClick={handleDrawerCollapse}
                size="small"
                sx={{ color: '#94a3b8', position: 'absolute', right: 8, top: 8 }}
              >
                {drawerCollapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
              </IconButton>
            )}
          </>
        )}
      </Box>

      {/* Department Badge */}
      {!drawerCollapsed && (
        <Box sx={{ p: 2, pb: 1 }}>
          <Chip
            label={user?.role || 'User'}
            size="small"
            sx={{
              backgroundColor: 'rgba(255, 140, 0, 0.15)',
              color: '#FFA500',
              fontWeight: 600,
              fontSize: '0.75rem',
            }}
          />
        </Box>
      )}

      {/* Navigation */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        <List sx={{ pt: drawerCollapsed ? 1 : 0 }}>
          {navigation.map((section) => (
            <NavigationSection
              key={section.title}
              title={section.title}
              items={section.items}
              isCollapsed={drawerCollapsed && !isMobile}
              currentPath={location.pathname}
              departmentColor={departmentColor.primary}
              onNavigate={handleNavigate}
            />
          ))}
        </List>
      </Box>

      {/* User Section */}
      {!drawerCollapsed && (
        <Box sx={{ p: 2, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <Avatar
              src={user?.avatar_url || undefined}
              sx={{
                width: 32,
                height: 32,
                mr: 1,
                backgroundColor: departmentColor.primary,
                fontSize: '0.875rem',
              }}
            >
              {user?.first_name?.[0]}{user?.last_name?.[0]}
            </Avatar>
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <Typography variant="body2" noWrap sx={{ fontWeight: 500, color: '#e2e8f0' }}>
                {user?.first_name} {user?.last_name}
              </Typography>
              <Typography variant="caption" noWrap sx={{ color: '#94a3b8' }}>
                {user?.role}
              </Typography>
            </Box>
          </Box>
        </Box>
      )}
    </Box>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />

      {/* Header AppBar */}
      <AppBar
        position="fixed"
        elevation={1}
        sx={{
          width: { md: `calc(100% - ${getCurrentDrawerWidth()}px)` },
          ml: { md: `${getCurrentDrawerWidth()}px` },
          backgroundColor: 'background.paper',
          color: 'text.primary',
          borderBottom: '1px solid',
          borderColor: 'divider',
          transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Toolbar sx={{ gap: 2 }}>
          {/* Mobile menu button */}
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>

          <Box sx={{ flexGrow: 1 }} />

          {/* Header actions */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {/* Theme toggle */}
            <Tooltip title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}>
              <IconButton
                onClick={toggleDarkMode}
                color="inherit"
              >
                {darkMode ? <LightModeIcon /> : <DarkModeIcon />}
              </IconButton>
            </Tooltip>

            {/* Notifications */}
            <Tooltip title="Notifications">
              <IconButton
                color="inherit"
                onClick={handleNotificationMenuOpen}
              >
                <Badge badgeContent={3} color="error">
                  <NotificationsIcon />
                </Badge>
              </IconButton>
            </Tooltip>

            {/* User menu */}
            <Button
              onClick={handleUserMenuOpen}
              sx={{
                textTransform: 'none',
                color: 'inherit',
                '&:hover': {
                  backgroundColor: 'action.hover',
                },
              }}
              startIcon={
                <Avatar
                  src={user?.avatar_url || undefined}
                  sx={{
                    width: 32,
                    height: 32,
                    backgroundColor: departmentColor.primary,
                    fontSize: '0.875rem',
                  }}
                >
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </Avatar>
              }
            >
              <Box sx={{ textAlign: 'left', display: { xs: 'none', sm: 'block' } }}>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  {user?.first_name} {user?.last_name}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {user?.role}
                </Typography>
              </Box>
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Navigation Drawer */}
      <Box
        component="nav"
        sx={{
          width: { md: getCurrentDrawerWidth() },
          flexShrink: { md: 0 },
          transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        {/* Mobile drawer */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: drawerWidth,
              border: 'none',
              backgroundColor: '#1e293b',
              color: '#cbd5e1',
            },
          }}
        >
          {drawer}
        </Drawer>

        {/* Desktop drawer */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: getCurrentDrawerWidth(),
              border: 'none',
              borderRight: '1px solid rgba(255,255,255,0.08)',
              backgroundColor: '#1e293b',
              color: '#cbd5e1',
              transition: theme.transitions.create('width', {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.leavingScreen,
              }),
              overflowX: 'hidden',
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: { xs: 2, sm: 3 },
          pb: { xs: 10, md: 3 }, // Extra padding bottom for mobile bottom nav
          width: { md: `calc(100% - ${getCurrentDrawerWidth()}px)` },
          transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
          backgroundColor: 'background.default',
          minHeight: '100vh',
        }}
      >
        <Toolbar />
        {children}
      </Box>

      {/* User Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleUserMenuClose}
        onClick={handleUserMenuClose}
        PaperProps={{
          elevation: 3,
          sx: {
            overflow: 'visible',
            filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
            mt: 1.5,
            minWidth: 200,
            '& .MuiAvatar-root': {
              width: 32,
              height: 32,
              ml: -0.5,
              mr: 1,
            },
          },
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <MenuItem onClick={() => { handleNavigate('/profile'); handleUserMenuClose(); }}>
          <PersonIcon sx={{ mr: 1 }} />
          Profile
        </MenuItem>
        <MenuItem onClick={() => { avatarInputRef.current?.click(); handleUserMenuClose(); }}>
          <CameraAltIcon sx={{ mr: 1 }} />
          Change Avatar
        </MenuItem>
        <Divider />
        <MenuItem onClick={handleLogout}>
          <Logout sx={{ mr: 1 }} />
          Logout
        </MenuItem>
      </Menu>

      {/* Notification Menu */}
      <Menu
        anchorEl={notificationAnchorEl}
        open={Boolean(notificationAnchorEl)}
        onClose={handleNotificationMenuClose}
        PaperProps={{
          elevation: 3,
          sx: {
            overflow: 'visible',
            filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
            mt: 1.5,
            minWidth: 320,
            maxWidth: 400,
          },
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Typography variant="h6">Notifications</Typography>
        </Box>
        <MenuItem>
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              New opportunity created
            </Typography>
            <Typography variant="caption" color="text.secondary">
              2 minutes ago
            </Typography>
          </Box>
        </MenuItem>
        <MenuItem>
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              Contract renewal due
            </Typography>
            <Typography variant="caption" color="text.secondary">
              1 hour ago
            </Typography>
          </Box>
        </MenuItem>
        <MenuItem>
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              Task overdue
            </Typography>
            <Typography variant="caption" color="text.secondary">
              3 hours ago
            </Typography>
          </Box>
        </MenuItem>
        <Divider />
        <MenuItem sx={{ justifyContent: 'center' }}>
          <Typography variant="body2" color="primary">
            View all notifications
          </Typography>
        </MenuItem>
      </Menu>

      {/* Mobile Bottom Navigation */}
      <MobileBottomNav />

      {/* Hidden avatar file input */}
      <input
        ref={avatarInputRef}
        type="file"
        accept="image/jpeg,image/png,image/gif,image/webp"
        style={{ display: 'none' }}
        onChange={handleAvatarUpload}
      />
    </Box>
  );
};

export default Layout;