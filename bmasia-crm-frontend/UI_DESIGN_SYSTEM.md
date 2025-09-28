# BMAsia CRM UI Design System

## Overview

The BMAsia CRM features a modern, department-specific UI design system built with Material-UI 7 that adapts to different user roles and provides an optimal experience across all devices.

## Key Features

### 🎨 Department-Specific Design
- **Sales**: Blue color scheme (#1976d2) - Professional and trustworthy
- **Marketing**: Purple color scheme (#7b1fa2) - Creative and engaging
- **Tech Support**: Green color scheme (#388e3c) - Reliable and calming
- **Admin**: Gray color scheme (#616161) - Neutral and authoritative

### 📱 Responsive Navigation
- **Desktop**: Full sidebar navigation (280px width)
- **Tablet**: Collapsible sidebar (64px mini width)
- **Mobile**: Bottom navigation bar + hamburger menu

### 🌓 Theme System
- Light/Dark mode toggle
- Department-specific color palettes
- Consistent typography and spacing
- Custom Material-UI component overrides

### ✨ Modern UI Components
- Smooth animations and transitions
- Loading skeletons for better perceived performance
- Interactive notifications system
- Global search functionality
- Quick actions dashboard

## Component Architecture

### Layout Components

#### `Layout.tsx`
Main layout wrapper that provides:
- Department-specific header with company branding
- Adaptive sidebar navigation
- User profile and settings menu
- Search functionality
- Notification center
- Theme toggle

#### `MobileBottomNav.tsx`
Mobile-optimized bottom navigation:
- Role-based navigation items
- Badge support for notifications
- Smooth transitions
- Touch-friendly design

#### `QuickActions.tsx`
Dashboard component featuring:
- Role-specific quick action buttons
- Recent activity feed
- One-click access to common tasks
- Visual hierarchy with icons and descriptions

#### `LoadingSkeleton.tsx`
Reusable loading states:
- Multiple variants (dashboard, table, form, card, list)
- Consistent with design system
- Improves perceived performance

### Theme System

#### `ThemeContext.tsx`
Centralized theme management:
- Department-specific color schemes
- Light/dark mode persistence
- Material-UI component customizations
- Typography system

## Navigation Structure

### Sales Department
- **Overview**: Dashboard, Quick Actions
- **Customer Management**: Companies, Contacts, Opportunities
- **Sales Operations**: Quotes, Targets, Tasks

### Marketing Department
- **Overview**: Dashboard, Analytics
- **Campaign Management**: Campaigns, Email Templates, Segments

### Tech Support Department
- **Overview**: Dashboard, My Queue
- **Support Operations**: Tickets, Knowledge Base, Equipment, SLAs

### Admin Department
- **Overview**: Dashboard, System Status
- **Business Data**: All customer/sales data access
- **Administration**: User Management, Settings, Audit Logs

## Design Principles

### 1. **Progressive Disclosure**
Information is revealed progressively to avoid overwhelming users. Complex features are hidden behind intuitive navigation patterns.

### 2. **Role-Based Experience**
Each department gets a tailored experience with relevant tools and information prominently displayed.

### 3. **Mobile-First Design**
All components are designed mobile-first and progressively enhanced for larger screens.

### 4. **Accessibility**
- WCAG 2.1 AA compliance
- Keyboard navigation support
- Screen reader compatibility
- High contrast ratios
- Focus management

### 5. **Performance**
- Smooth 60fps animations
- Optimized loading states
- Efficient component rendering
- Minimal bundle size impact

## Usage Examples

### Implementing Department-Specific Features

```tsx
import { useAuth } from '../contexts/AuthContext';

const MyComponent = () => {
  const { user } = useAuth();

  // Show department-specific content
  if (user?.role === 'Sales') {
    return <SalesSpecificContent />;
  }

  return <DefaultContent />;
};
```

### Using the Theme System

```tsx
import { useThemeContext } from '../contexts/ThemeContext';

const MyComponent = () => {
  const { darkMode, toggleDarkMode, departmentTheme } = useThemeContext();
  const theme = departmentTheme(user?.role || 'Admin');

  return (
    <Box sx={{ backgroundColor: theme.palette.primary.main }}>
      Content with department colors
    </Box>
  );
};
```

### Loading States

```tsx
import LoadingSkeleton from '../components/LoadingSkeleton';

const DataTable = ({ loading, data }) => {
  if (loading) {
    return <LoadingSkeleton variant="table" rows={5} />;
  }

  return <DataGrid data={data} />;
};
```

## Customization Guide

### Adding New Department Colors

1. Update `departmentColors` in `ThemeContext.tsx`
2. Add role-specific navigation in `Layout.tsx`
3. Update `navigationConfig` object

### Creating New Navigation Items

```tsx
// In navigationConfig
{
  title: 'New Section',
  items: [
    {
      text: 'New Page',
      icon: <NewIcon />,
      path: '/new-page',
      badge: 5 // Optional notification count
    }
  ]
}
```

### Custom Loading Skeletons

```tsx
// Add new variant to LoadingSkeleton.tsx
const renderCustomSkeleton = () => (
  <Stack spacing={2}>
    {/* Your custom skeleton structure */}
  </Stack>
);
```

## Best Practices

### 1. **Consistent Spacing**
Use Material-UI's spacing system (theme.spacing()) for all margins and padding.

### 2. **Color Usage**
- Use department colors for primary actions and highlights
- Maintain sufficient contrast ratios
- Use semantic colors (error, warning, success) appropriately

### 3. **Typography Hierarchy**
Follow the established typography scale:
- H1-H6 for headings
- Body1/Body2 for content
- Caption for metadata

### 4. **Animation Guidelines**
- Use theme transitions for consistency
- Respect `prefers-reduced-motion`
- Keep animations purposeful and quick (200-300ms)

### 5. **Responsive Design**
- Test on multiple device sizes
- Use breakpoint helpers from Material-UI
- Ensure touch targets are at least 44px

## Future Enhancements

### Planned Features
- [ ] Advanced notification system with real-time updates
- [ ] Customizable dashboard widgets
- [ ] Advanced search with filters
- [ ] Keyboard shortcuts overlay
- [ ] Tour/onboarding system
- [ ] Advanced theming options
- [ ] Print-friendly layouts
- [ ] Offline support indicators

### Performance Optimizations
- [ ] Code splitting by department
- [ ] Virtual scrolling for large lists
- [ ] Image optimization
- [ ] Service worker integration

## Support

For questions about the design system or to report issues:

1. Check existing patterns in the codebase
2. Refer to Material-UI documentation
3. Consider accessibility implications
4. Test across devices and browsers

The design system is built to be maintainable, scalable, and user-friendly. When adding new features, always consider the impact on all user roles and device types.