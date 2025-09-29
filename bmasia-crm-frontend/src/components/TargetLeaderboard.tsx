import React, { useState } from 'react';
import {
  Paper,
  Typography,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Avatar,
  Chip,
  LinearProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Card,
  CardContent,
  SelectChangeEvent,
} from '@mui/material';
import {
  EmojiEvents,
  TrendingUp,
  TrendingDown,
  Remove,
} from '@mui/icons-material';
import { SalesTarget } from '../types';

interface TargetLeaderboardProps {
  targets: SalesTarget[];
}

interface LeaderboardEntry {
  userId: string;
  userName: string;
  targets: SalesTarget[];
  totalAchievement: number;
  avgAchievement: number;
  bestTarget: SalesTarget;
  totalValue: number;
  targetCount: number;
  rank: number;
  trend: 'up' | 'down' | 'stable';
}

const TargetLeaderboard: React.FC<TargetLeaderboardProps> = ({ targets }) => {
  const [sortBy, setSortBy] = useState<'achievement' | 'value' | 'count'>('achievement');
  const [filterType, setFilterType] = useState<'all' | 'Revenue' | 'Units' | 'Customers' | 'Contracts'>('all');

  const individualTargets = targets.filter(t => !t.team_target && t.assigned_to);

  const generateLeaderboardData = (): LeaderboardEntry[] => {
    const userMap = new Map<string, {
      targets: SalesTarget[];
      totalAchievement: number;
      totalValue: number;
    }>();

    const filteredTargets = filterType === 'all'
      ? individualTargets
      : individualTargets.filter(t => t.target_type === filterType);

    filteredTargets.forEach(target => {
      const userId = target.assigned_to!;
      const userName = target.assigned_to_name || 'Unknown User';

      if (!userMap.has(userId)) {
        userMap.set(userId, {
          targets: [],
          totalAchievement: 0,
          totalValue: 0,
        });
      }

      const userData = userMap.get(userId)!;
      userData.targets.push(target);
      userData.totalAchievement += target.achievement_percentage;
      userData.totalValue += target.current_value;
    });

    const leaderboardData: LeaderboardEntry[] = Array.from(userMap.entries()).map(([userId, userData]) => {
      const userName = userData.targets[0]?.assigned_to_name || 'Unknown User';
      const avgAchievement = userData.totalAchievement / userData.targets.length;
      const bestTarget = userData.targets.reduce((best, current) =>
        current.achievement_percentage > best.achievement_percentage ? current : best
      );

      // Mock trend calculation (in real app, this would compare with historical data)
      const trend: 'up' | 'down' | 'stable' = avgAchievement > 75 ? 'up' : avgAchievement < 50 ? 'down' : 'stable';

      return {
        userId,
        userName,
        targets: userData.targets,
        totalAchievement: userData.totalAchievement,
        avgAchievement,
        bestTarget,
        totalValue: userData.totalValue,
        targetCount: userData.targets.length,
        rank: 0, // Will be set after sorting
        trend,
      };
    });

    // Sort based on selected criteria
    let sortedData: LeaderboardEntry[];
    switch (sortBy) {
      case 'achievement':
        sortedData = leaderboardData.sort((a, b) => b.avgAchievement - a.avgAchievement);
        break;
      case 'value':
        sortedData = leaderboardData.sort((a, b) => b.totalValue - a.totalValue);
        break;
      case 'count':
        sortedData = leaderboardData.sort((a, b) => b.targetCount - a.targetCount);
        break;
      default:
        sortedData = leaderboardData;
    }

    // Assign ranks
    return sortedData.map((entry, index) => ({ ...entry, rank: index + 1 }));
  };

  const leaderboardData = generateLeaderboardData();

  const handleSortByChange = (event: SelectChangeEvent) => {
    setSortBy(event.target.value as any);
  };

  const handleFilterTypeChange = (event: SelectChangeEvent) => {
    setFilterType(event.target.value as any);
  };

  const getRankColor = (rank: number) => {
    if (rank === 1) return '#ffd700'; // Gold
    if (rank === 2) return '#c0c0c0'; // Silver
    if (rank === 3) return '#cd7f32'; // Bronze
    return '#e0e0e0'; // Default
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up':
        return <TrendingUp sx={{ color: 'success.main', fontSize: 16 }} />;
      case 'down':
        return <TrendingDown sx={{ color: 'error.main', fontSize: 16 }} />;
      default:
        return <Remove sx={{ color: 'grey.500', fontSize: 16 }} />;
    }
  };

  const getPerformanceColor = (achievement: number) => {
    if (achievement >= 90) return 'success';
    if (achievement >= 70) return 'info';
    if (achievement >= 50) return 'warning';
    return 'error';
  };

  const formatValue = (value: number, target: SalesTarget) => {
    if (target.target_type === 'Revenue') {
      const symbol = target.currency === 'USD' ? '$' : target.currency === 'THB' ? '฿' : '€';
      if (value >= 1000000) {
        return `${symbol}${(value / 1000000).toFixed(1)}M`;
      } else if (value >= 1000) {
        return `${symbol}${(value / 1000).toFixed(1)}K`;
      }
      return `${symbol}${value.toLocaleString()}`;
    }
    return `${value.toLocaleString()} ${target.unit_type || ''}`;
  };

  if (individualTargets.length === 0) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Individual Performance Leaderboard
        </Typography>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body1" color="text.secondary">
            No individual targets available
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Top Performers Cards */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Top Performers
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Sort By</InputLabel>
            <Select
              value={sortBy}
              onChange={handleSortByChange}
              label="Sort By"
            >
              <MenuItem value="achievement">Achievement %</MenuItem>
              <MenuItem value="value">Total Value</MenuItem>
              <MenuItem value="count">Target Count</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Filter Type</InputLabel>
            <Select
              value={filterType}
              onChange={handleFilterTypeChange}
              label="Filter Type"
            >
              <MenuItem value="all">All Types</MenuItem>
              <MenuItem value="Revenue">Revenue</MenuItem>
              <MenuItem value="Units">Units</MenuItem>
              <MenuItem value="Customers">Customers</MenuItem>
              <MenuItem value="Contracts">Contracts</MenuItem>
            </Select>
          </FormControl>
        </Box>

        {/* Top 3 Cards */}
        {leaderboardData.length > 0 && (
          <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
            {leaderboardData.slice(0, 3).map((entry) => (
              <Card key={entry.userId} sx={{ flex: '1 1 300px', minWidth: 250 }}>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                    <Avatar
                      sx={{
                        bgcolor: getRankColor(entry.rank),
                        color: entry.rank <= 3 ? '#000' : '#666',
                        fontWeight: 'bold',
                      }}
                    >
                      {entry.rank === 1 && <EmojiEvents />}
                      {entry.rank > 1 && `#${entry.rank}`}
                    </Avatar>
                    <Box>
                      <Typography variant="h6">
                        {entry.userName}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {entry.targetCount} target{entry.targetCount !== 1 ? 's' : ''}
                      </Typography>
                    </Box>
                    {getTrendIcon(entry.trend)}
                  </Box>

                  <Box sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="body2" color="text.secondary">
                        Average Achievement
                      </Typography>
                      <Typography variant="h6" fontWeight="bold" color={`${getPerformanceColor(entry.avgAchievement)}.main`}>
                        {Math.round(entry.avgAchievement)}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={Math.min(entry.avgAchievement, 100)}
                      color={getPerformanceColor(entry.avgAchievement) as any}
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                  </Box>

                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="body2" color="text.secondary">
                      Best: {Math.round(entry.bestTarget.achievement_percentage)}%
                    </Typography>
                    <Chip
                      size="small"
                      label={entry.avgAchievement >= 80 ? 'Excellent' : entry.avgAchievement >= 60 ? 'Good' : 'Needs Focus'}
                      color={getPerformanceColor(entry.avgAchievement) as any}
                    />
                  </Box>
                </CardContent>
              </Card>
            ))}
          </Box>
        )}
      </Paper>

      {/* Full Leaderboard Table */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Full Leaderboard
        </Typography>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Rank</TableCell>
                <TableCell>User</TableCell>
                <TableCell align="center">Targets</TableCell>
                <TableCell align="center">Avg Achievement</TableCell>
                <TableCell align="center">Best Target</TableCell>
                <TableCell align="center">Total Value</TableCell>
                <TableCell align="center">Status</TableCell>
                <TableCell align="center">Trend</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {leaderboardData.map((entry) => (
                <TableRow key={entry.userId} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Avatar
                        sx={{
                          width: 32,
                          height: 32,
                          bgcolor: getRankColor(entry.rank),
                          color: entry.rank <= 3 ? '#000' : '#666',
                          fontSize: '0.875rem',
                          fontWeight: 'bold',
                        }}
                      >
                        {entry.rank === 1 && <EmojiEvents sx={{ fontSize: 20 }} />}
                        {entry.rank > 1 && entry.rank}
                      </Avatar>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {entry.userName}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2">
                      {entry.targetCount}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Box sx={{ minWidth: 80 }}>
                      <Typography variant="body2" fontWeight="bold" color={`${getPerformanceColor(entry.avgAchievement)}.main`}>
                        {Math.round(entry.avgAchievement)}%
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={Math.min(entry.avgAchievement, 100)}
                        color={getPerformanceColor(entry.avgAchievement) as any}
                        sx={{ height: 4, borderRadius: 2, mt: 0.5 }}
                      />
                    </Box>
                  </TableCell>
                  <TableCell align="center">
                    <Box>
                      <Typography variant="body2" fontWeight="medium">
                        {Math.round(entry.bestTarget.achievement_percentage)}%
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {entry.bestTarget.target_type}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2">
                      {formatValue(entry.totalValue, entry.targets[0])}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Chip
                      size="small"
                      label={
                        entry.avgAchievement >= 90 ? 'Excellent' :
                        entry.avgAchievement >= 80 ? 'Great' :
                        entry.avgAchievement >= 70 ? 'Good' :
                        entry.avgAchievement >= 60 ? 'Fair' : 'Needs Focus'
                      }
                      color={getPerformanceColor(entry.avgAchievement) as any}
                    />
                  </TableCell>
                  <TableCell align="center">
                    {getTrendIcon(entry.trend)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Leaderboard Statistics */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Leaderboard Statistics
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="primary">
              {leaderboardData.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Participants
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="success.main">
              {Math.round(leaderboardData.reduce((sum, entry) => sum + entry.avgAchievement, 0) / Math.max(leaderboardData.length, 1))}%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Average Achievement
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="info.main">
              {leaderboardData.filter(entry => entry.avgAchievement >= 80).length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Top Performers
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="warning.main">
              {leaderboardData.length > 0 ? Math.round(Math.max(...leaderboardData.map(entry => entry.avgAchievement))) : 0}%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Highest Achievement
            </Typography>
          </Box>
        </Box>
      </Paper>
    </Box>
  );
};

export default TargetLeaderboard;