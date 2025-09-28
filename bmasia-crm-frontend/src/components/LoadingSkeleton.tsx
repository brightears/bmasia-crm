import React from 'react';
import {
  Box,
  Skeleton,
  Card,
  CardContent,
  Stack,
} from '@mui/material';

interface LoadingSkeletonProps {
  variant?: 'dashboard' | 'table' | 'form' | 'card' | 'list';
  rows?: number;
  height?: number | string;
}

const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  variant = 'card',
  rows = 3,
  height = 'auto',
}) => {
  const renderDashboardSkeleton = () => (
    <Box sx={{ width: '100%' }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Skeleton variant="text" width="30%" height={40} />
        <Skeleton variant="text" width="60%" height={24} />
      </Box>

      {/* Stats Cards */}
      <Box sx={{ display: 'flex', gap: 3, mb: 4, flexWrap: 'wrap' }}>
        {[1, 2, 3, 4].map((item) => (
          <Box key={item} sx={{ flex: '1 1 250px', minWidth: 200 }}>
            <Card>
              <CardContent>
                <Stack spacing={1}>
                  <Skeleton variant="text" width="60%" height={20} />
                  <Skeleton variant="text" width="40%" height={32} />
                  <Skeleton variant="text" width="30%" height={16} />
                </Stack>
              </CardContent>
            </Card>
          </Box>
        ))}
      </Box>

      {/* Chart Area */}
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '2 1 500px', minWidth: 400 }}>
          <Card>
            <CardContent>
              <Skeleton variant="text" width="30%" height={24} sx={{ mb: 2 }} />
              <Skeleton variant="rectangular" height={300} />
            </CardContent>
          </Card>
        </Box>
        <Box sx={{ flex: '1 1 300px', minWidth: 250 }}>
          <Card>
            <CardContent>
              <Skeleton variant="text" width="50%" height={24} sx={{ mb: 2 }} />
              <Stack spacing={2}>
                {[1, 2, 3, 4, 5].map((item) => (
                  <Box key={item} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Skeleton variant="circular" width={32} height={32} />
                    <Box sx={{ flexGrow: 1 }}>
                      <Skeleton variant="text" width="70%" height={16} />
                      <Skeleton variant="text" width="40%" height={14} />
                    </Box>
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );

  const renderTableSkeleton = () => (
    <Box sx={{ width: '100%' }}>
      {/* Table Header */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, p: 2 }}>
        <Skeleton variant="text" width="20%" height={24} />
        <Skeleton variant="text" width="25%" height={24} />
        <Skeleton variant="text" width="15%" height={24} />
        <Skeleton variant="text" width="20%" height={24} />
        <Skeleton variant="text" width="20%" height={24} />
      </Box>

      {/* Table Rows */}
      {Array.from({ length: rows }).map((_, index) => (
        <Box key={index} sx={{ display: 'flex', gap: 2, mb: 1, p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Skeleton variant="text" width="20%" height={20} />
          <Skeleton variant="text" width="25%" height={20} />
          <Skeleton variant="text" width="15%" height={20} />
          <Skeleton variant="text" width="20%" height={20} />
          <Skeleton variant="text" width="20%" height={20} />
        </Box>
      ))}
    </Box>
  );

  const renderFormSkeleton = () => (
    <Card>
      <CardContent>
        <Stack spacing={3}>
          <Skeleton variant="text" width="40%" height={32} />

          {Array.from({ length: rows }).map((_, index) => (
            <Box key={index}>
              <Skeleton variant="text" width="20%" height={20} sx={{ mb: 1 }} />
              <Skeleton variant="rectangular" height={56} />
            </Box>
          ))}

          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 3 }}>
            <Skeleton variant="rectangular" width={100} height={36} />
            <Skeleton variant="rectangular" width={80} height={36} />
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );

  const renderCardSkeleton = () => (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Skeleton variant="text" width="60%" height={24} />
          <Skeleton variant="text" width="100%" height={20} />
          <Skeleton variant="text" width="80%" height={20} />
          <Skeleton variant="rectangular" height={height === 'auto' ? 120 : height} />
        </Stack>
      </CardContent>
    </Card>
  );

  const renderListSkeleton = () => (
    <Stack spacing={2}>
      {Array.from({ length: rows }).map((_, index) => (
        <Box key={index} sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
          <Skeleton variant="circular" width={40} height={40} />
          <Box sx={{ flexGrow: 1 }}>
            <Skeleton variant="text" width="60%" height={20} />
            <Skeleton variant="text" width="40%" height={16} />
          </Box>
          <Skeleton variant="rectangular" width={80} height={32} />
        </Box>
      ))}
    </Stack>
  );

  switch (variant) {
    case 'dashboard':
      return renderDashboardSkeleton();
    case 'table':
      return renderTableSkeleton();
    case 'form':
      return renderFormSkeleton();
    case 'list':
      return renderListSkeleton();
    case 'card':
    default:
      return renderCardSkeleton();
  }
};

export default LoadingSkeleton;