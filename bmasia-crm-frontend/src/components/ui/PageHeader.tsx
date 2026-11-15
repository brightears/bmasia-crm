import React from 'react';
import { Box, Breadcrumbs, Link, Typography } from '@mui/material';
import { NavigateNext } from '@mui/icons-material';
import { Link as RouterLink } from 'react-router-dom';

export interface Crumb {
  label: string;
  to?: string;
}

interface PageHeaderProps {
  title: React.ReactNode;
  /** One line under the title: what the page is for, or key facts about a record. */
  subtitle?: React.ReactNode;
  breadcrumbs?: Crumb[];
  /** Buttons on the right. Put the main action last; it should be the only contained button. */
  actions?: React.ReactNode;
  /** Leading visual, e.g. a record avatar. */
  avatar?: React.ReactNode;
  /** Chips or small facts shown under the title. */
  meta?: React.ReactNode;
}

/**
 * Standard page header: breadcrumb, title, one-line description and actions.
 * Every page should start with this so titles and primary actions are always in the same place.
 */
const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, breadcrumbs, actions, avatar, meta }) => (
  <Box component="header" sx={{ mb: 3 }}>
    {breadcrumbs && breadcrumbs.length > 0 && (
      <Breadcrumbs
        separator={<NavigateNext sx={{ fontSize: 16 }} />}
        aria-label="breadcrumb"
        sx={{ mb: 1, '& .MuiBreadcrumbs-li': { fontSize: '0.8125rem' } }}
      >
        {breadcrumbs.map((crumb, i) =>
          crumb.to && i < breadcrumbs.length - 1 ? (
            <Link
              key={crumb.label}
              component={RouterLink}
              to={crumb.to}
              underline="hover"
              color="text.secondary"
              sx={{ fontSize: '0.8125rem' }}
            >
              {crumb.label}
            </Link>
          ) : (
            <Typography key={crumb.label} color="text.secondary" sx={{ fontSize: '0.8125rem' }}>
              {crumb.label}
            </Typography>
          )
        )}
      </Breadcrumbs>
    )}
    <Box
      sx={{
        display: 'flex',
        alignItems: { xs: 'flex-start', sm: 'center' },
        justifyContent: 'space-between',
        flexDirection: { xs: 'column', sm: 'row' },
        gap: 2,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 0 }}>
        {avatar}
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4" component="h1" sx={{ overflowWrap: 'anywhere' }}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="body1" color="text.secondary" sx={{ mt: 0.5 }}>
              {subtitle}
            </Typography>
          )}
          {meta && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, mt: 1 }}>{meta}</Box>
          )}
        </Box>
      </Box>
      {actions && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, flexShrink: 0, alignItems: 'center' }}>{actions}</Box>
      )}
    </Box>
  </Box>
);

export default PageHeader;
