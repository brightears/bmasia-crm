import React, { useState, useRef, useEffect } from 'react';
import {
  AppBar,
  Box,
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
  Button,
  Collapse,
  ButtonBase,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Logout,
  KeyboardDoubleArrowLeft,
  KeyboardDoubleArrowRight,
  ExpandMore,
  LightModeOutlined,
  DarkModeOutlined,
  PersonOutline,
  CameraAltOutlined,
  KeyboardArrowDown,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import ApiService from '../services/api';
import { useThemeContext } from '../contexts/ThemeContext';
import MobileBottomNav from './MobileBottomNav';
import GlobalSearch from './GlobalSearch';
import { buildNavGroups, findNavLocation, isActivePath, NavGroup } from './navigation';
import { layout } from '../theme';

const drawerWidth = layout.sidebarWidth;
const miniDrawerWidth = layout.sidebarCollapsedWidth;

// Groups that start open on a first visit. After that the browser remembers which groups
// the user opened or closed. The group holding the current page is always opened too.
const DEFAULT_OPEN_GROUPS = ['home', 'customers', 'sales'];
const OPEN_GROUPS_KEY = 'bmasia.menu.openGroups';

const readOpenGroups = (): string[] => {
  try {
    const saved = JSON.parse(localStorage.getItem(OPEN_GROUPS_KEY) || 'null');
    return Array.isArray(saved) ? saved.filter((g) => typeof g === 'string') : DEFAULT_OPEN_GROUPS;
  } catch {
    return DEFAULT_OPEN_GROUPS;
  }
};

interface LayoutProps {
  children: React.ReactNode;
}

interface NavigationSectionProps {
  group: NavGroup;
  isCollapsed: boolean;
  currentPath: string;
  open: boolean;
  onToggle: () => void;
  onNavigate: (path: string) => void;
}

const NavigationSection: React.FC<NavigationSectionProps> = ({
  group,
  isCollapsed,
  currentPath,
  open,
  onToggle,
  onNavigate,
}) => {
  const renderItem = (item: NavGroup['items'][number]) => {
    const selected = isActivePath(item.path, currentPath);
    const button = (
      <ListItemButton
        selected={selected}
        onClick={() => onNavigate(item.path)}
        aria-current={selected ? 'page' : undefined}
        sx={{
          minHeight: 36,
          mx: 1,
          my: '1px',
          px: isCollapsed ? 0 : 1.25,
          justifyContent: isCollapsed ? 'center' : 'flex-start',
          position: 'relative',
          '&.Mui-selected::before': {
            content: '""',
            position: 'absolute',
            left: -8,
            top: 8,
            bottom: 8,
            width: 3,
            borderRadius: '0 3px 3px 0',
            bgcolor: 'primary.main',
          },
        }}
      >
        <ListItemIcon
          sx={{
            minWidth: isCollapsed ? 0 : 32,
            color: selected ? 'primary.main' : 'text.secondary',
            '& svg': { fontSize: 20 },
          }}
        >
          <Badge badgeContent={item.badge} color="error" max={99}>
            {item.icon}
          </Badge>
        </ListItemIcon>
        {!isCollapsed && (
          <ListItemText
            primary={item.text}
            primaryTypographyProps={{
              fontSize: '0.875rem',
              fontWeight: selected ? 600 : 500,
              color: 'text.primary',
              noWrap: true,
            }}
          />
        )}
      </ListItemButton>
    );

    return (
      <ListItem key={item.path} disablePadding>
        {isCollapsed ? (
          <Tooltip title={item.text} placement="right">
            {button}
          </Tooltip>
        ) : (
          button
        )}
      </ListItem>
    );
  };

  if (isCollapsed) {
    return (
      <>
        {group.items.map(renderItem)}
        <Divider sx={{ my: 1, mx: 1.5 }} />
      </>
    );
  }

  if (!group.title) {
    return <Box sx={{ mb: 1 }}>{group.items.map(renderItem)}</Box>;
  }

  return (
    <Box sx={{ mb: 0.5 }}>
      <ButtonBase
        onClick={onToggle}
        aria-expanded={open}
        sx={{
          width: 'calc(100% - 16px)',
          mx: 1,
          px: 1.25,
          py: 0.75,
          borderRadius: 1,
          justifyContent: 'space-between',
          color: 'text.secondary',
          '&:hover': { bgcolor: 'action.hover' },
        }}
      >
        <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1.4 }}>
          {group.title}
        </Typography>
        <ExpandMore
          sx={{
            fontSize: 18,
            transition: 'transform 150ms',
            transform: open ? 'rotate(0deg)' : 'rotate(-90deg)',
          }}
        />
      </ButtonBase>
      <Collapse in={open} timeout="auto" unmountOnExit>
        <List component="div" disablePadding>
          {group.items.map(renderItem)}
        </List>
      </Collapse>
    </Box>
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
  const [aiDraftsPendingCount, setAiDraftsPendingCount] = useState(0);
  const [openGroups, setOpenGroups] = useState<string[]>(readOpenGroups);

  useEffect(() => {
    try {
      localStorage.setItem(OPEN_GROUPS_KEY, JSON.stringify(openGroups));
    } catch {
      // Storage can be unavailable (private window); the menu still works.
    }
  }, [openGroups]);

  const { darkMode, toggleDarkMode } = useThemeContext();
  const avatarInputRef = useRef<HTMLInputElement>(null);

  // Fetch AI drafts pending count on mount and every 60 seconds
  React.useEffect(() => {
    const fetchPendingCount = async () => {
      try {
        const data = await ApiService.getAIEmailDraftPendingCount();
        setAiDraftsPendingCount(data.count || 0);
      } catch {
        // Silently fail if endpoint not yet available
      }
    };
    fetchPendingCount();
    const interval = setInterval(fetchPendingCount, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      await ApiService.uploadAvatar(file);
      // Update user in auth context by reloading
      window.location.reload();
    } catch (err) {
      console.error('Avatar upload failed:', err);
      alert('Failed to upload avatar. Please try again.');
    }
  };

  const navGroups = buildNavGroups(aiDraftsPendingCount);
  const { group: currentGroup, item: currentItem } = findNavLocation(navGroups, location.pathname);

  // Make sure the group of the page being shown is open.
  useEffect(() => {
    if (currentGroup && !openGroups.includes(currentGroup.id)) {
      setOpenGroups((prev) => [...prev, currentGroup.id]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentGroup?.id]);

  const toggleGroup = (id: string) =>
    setOpenGroups((prev) => (prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]));

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

  const collapsed = drawerCollapsed && !isMobile;
  const initials = `${user?.first_name?.[0] || ''}${user?.last_name?.[0] || ''}`.toUpperCase();

  const drawer = (
    <Box component="nav" aria-label="Main menu" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Brand */}
      <Box
        sx={{
          height: layout.topBarHeight,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          px: collapsed ? 0 : 2.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <ButtonBase
          onClick={() => handleNavigate('/today')}
          aria-label="BMAsia CRM home"
          sx={{ borderRadius: 1, display: 'flex', alignItems: 'center', gap: 1.25 }}
        >
          {collapsed ? (
            <Box component="img" src="/bmasia-mark.png" alt="BMAsia" sx={{ height: 32, width: 32 }} />
          ) : (
            <>
              {/* The grey wordmark is hard to read on dark backgrounds, so dark mode uses the white version. */}
              <Box
                component="img"
                src={darkMode ? '/bmasia-logo-white.png' : '/bmasia-logo.png'}
                alt="BMAsia"
                sx={{ height: 30, display: 'block' }}
              />
              <Box
                component="span"
                sx={{
                  fontSize: '0.6875rem',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  color: 'text.secondary',
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: '4px',
                  px: 0.75,
                  py: '1px',
                  mt: '6px',
                }}
              >
                CRM
              </Box>
            </>
          )}
        </ButtonBase>
      </Box>

      {/* Navigation */}
      <Box sx={{ flexGrow: 1, overflowY: 'auto', overflowX: 'hidden', py: 1.5 }}>
        <List disablePadding>
          {navGroups.map((group) => (
            <NavigationSection
              key={group.id}
              group={group}
              isCollapsed={collapsed}
              currentPath={location.pathname}
              open={openGroups.includes(group.id)}
              onToggle={() => toggleGroup(group.id)}
              onNavigate={handleNavigate}
            />
          ))}
        </List>
      </Box>

      {/* Collapse toggle */}
      {!isMobile && (
        <Box sx={{ borderTop: 1, borderColor: 'divider', p: 1, display: 'flex', justifyContent: collapsed ? 'center' : 'flex-end' }}>
          <Tooltip title={collapsed ? 'Expand menu' : 'Collapse menu'} placement="right">
            <IconButton onClick={handleDrawerCollapse} size="small" aria-label={collapsed ? 'Expand menu' : 'Collapse menu'}>
              {collapsed ? <KeyboardDoubleArrowRight fontSize="small" /> : <KeyboardDoubleArrowLeft fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>
      )}
    </Box>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      {/* Top bar */}
      <AppBar
        position="fixed"
        sx={{
          width: { md: `calc(100% - ${getCurrentDrawerWidth()}px)` },
          ml: { md: `${getCurrentDrawerWidth()}px` },
          transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Toolbar sx={{ gap: 1.5, minHeight: { xs: 56, sm: layout.topBarHeight }, px: { xs: 1.5, md: 3 } }}>
          {/* Mobile menu button */}
          <IconButton
            aria-label="Open menu"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ display: { md: 'none' }, color: 'text.primary' }}
          >
            <MenuIcon />
          </IconButton>
          <Box
            component="img"
            src="/bmasia-mark.png"
            alt=""
            sx={{ display: { xs: 'block', md: 'none' }, height: 28, width: 28 }}
          />

          {/* Where am I */}
          <Box sx={{ flexGrow: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 1 }}>
            {currentItem && (
              <Typography noWrap sx={{ fontSize: '0.875rem', color: 'text.secondary' }}>
                {currentGroup?.title && (
                  <Box component="span" sx={{ display: { xs: 'none', sm: 'inline' } }}>
                    {currentGroup.title}
                    <Box component="span" sx={{ mx: 1, color: 'text.disabled' }}>
                      /
                    </Box>
                  </Box>
                )}
                <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
                  {currentItem.text}
                </Box>
              </Typography>
            )}
          </Box>

          {/* Search the whole CRM */}
          <GlobalSearch />

          {/* Header actions */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Tooltip title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}>
              <IconButton onClick={toggleDarkMode} aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}>
                {darkMode ? <LightModeOutlined fontSize="small" /> : <DarkModeOutlined fontSize="small" />}
              </IconButton>
            </Tooltip>

            <Button
              onClick={handleUserMenuOpen}
              aria-haspopup="menu"
              aria-label="Account menu"
              color="inherit"
              variant="text"
              endIcon={<KeyboardArrowDown sx={{ color: 'text.secondary', display: { xs: 'none', sm: 'block' } }} />}
              sx={{ pl: 0.75, pr: 1, py: 0.5, minHeight: 40, gap: 0.5 }}
            >
              <Avatar src={user?.avatar_url || undefined} sx={{ width: 30, height: 30, mr: { xs: 0, sm: 1 } }}>
                {initials}
              </Avatar>
              <Box sx={{ textAlign: 'left', display: { xs: 'none', sm: 'block' }, lineHeight: 1.2 }}>
                <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, lineHeight: 1.25 }}>
                  {user?.first_name} {user?.last_name}
                </Typography>
                <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', lineHeight: 1.25 }}>
                  {user?.role}
                </Typography>
              </Box>
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Navigation Drawer */}
      <Box
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
              bgcolor: 'background.paper',
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
              bgcolor: 'background.paper',
              borderRight: 1,
              borderColor: 'divider',
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
          px: { xs: 2, sm: 3, lg: 4 },
          pt: { xs: 2, sm: 3 },
          pb: { xs: 10, md: 4 }, // Extra padding bottom for mobile bottom nav
          width: { md: `calc(100% - ${getCurrentDrawerWidth()}px)` },
          minWidth: 0,
          transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
          backgroundColor: 'background.default',
          minHeight: '100vh',
        }}
      >
        <Toolbar sx={{ minHeight: { xs: 56, sm: layout.topBarHeight } }} />
        <Box sx={{ maxWidth: layout.pageMaxWidth, mx: 'auto', width: '100%' }}>{children}</Box>
      </Box>

      {/* User Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleUserMenuClose}
        onClick={handleUserMenuClose}
        slotProps={{ paper: { sx: { mt: 1, minWidth: 220 } } }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <Box sx={{ px: 2, py: 1.25 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
            {user?.first_name} {user?.last_name}
          </Typography>
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{user?.role}</Typography>
        </Box>
        <Divider sx={{ my: 0.5 }} />
        <MenuItem onClick={() => { handleNavigate('/profile'); handleUserMenuClose(); }}>
          <PersonOutline fontSize="small" sx={{ mr: 1.5, color: 'text.secondary' }} />
          My profile
        </MenuItem>
        <MenuItem onClick={() => { avatarInputRef.current?.click(); handleUserMenuClose(); }}>
          <CameraAltOutlined fontSize="small" sx={{ mr: 1.5, color: 'text.secondary' }} />
          Change photo
        </MenuItem>
        <Divider sx={{ my: 0.5 }} />
        <MenuItem onClick={handleLogout}>
          <Logout fontSize="small" sx={{ mr: 1.5, color: 'text.secondary' }} />
          Sign out
        </MenuItem>
      </Menu>

      {/* Mobile Bottom Navigation */}
      <MobileBottomNav onOpenMenu={() => setMobileOpen(true)} />

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
