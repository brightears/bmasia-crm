import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  GridLegacy as Grid,
  LinearProgress,
  Chip,
  Avatar,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Alert,
  Button,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Warning,
  EmojiEvents,
  Speed,
  Group,
  Person,
  Add as AddIcon,
} from '@mui/icons-material';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { SalesTarget } from '../types';
import TargetProgressGauge from './TargetProgressGauge';
import { useAuth } from '../contexts/AuthContext';

interface TargetWidgetsProps {
  onCreateTarget?: () => void;
}

const TargetWidgets: React.FC<TargetWidgetsProps> = ({ onCreateTarget }) => {
  const { user } = useAuth();
  const [targets, setTargets] = useState<SalesTarget[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock data for demonstration - in real app, this would be an API call
    const mockTargets: SalesTarget[] = [
      {
        id: '1',
        name: 'Q4 2024 Revenue Target',
        period_type: 'Quarterly',
        period_start: '2024-10-01',
        period_end: '2024-12-31',
        target_type: 'Revenue',
        target_value: 250000,
        currency: 'USD',
        assigned_to: user?.id || '1',
        assigned_to_name: user?.first_name + ' ' + user?.last_name || 'John Doe',
        team_target: false,
        status: 'Active',
        current_value: 180000,
        achievement_percentage: 72,
        is_on_track: true,
        forecasted_value: 240000,
        forecasted_achievement: 96,
        risk_level: 'Low',
        created_by: user?.id || '1',
        created_by_name: user?.first_name + ' ' + user?.last_name || 'John Doe',
        created_at: '2024-09-01T00:00:00Z',
        updated_at: '2024-09-29T00:00:00Z',
        days_remaining: 92,
        days_total: 92,
        expected_daily_progress: 2717,
        actual_daily_progress: 3000,
        variance_from_plan: 283,
      },
      {
        id: '2',
        name: 'Monthly New Customers',
        period_type: 'Monthly',
        period_start: '2024-09-01',
        period_end: '2024-09-30',
        target_type: 'Customers',
        target_value: 15,
        currency: 'USD',
        unit_type: 'customers',
        assigned_to: user?.id || '1',
        assigned_to_name: user?.first_name + ' ' + user?.last_name || 'John Doe',
        team_target: false,
        status: 'Active',
        current_value: 12,
        achievement_percentage: 80,
        is_on_track: true,
        forecasted_value: 14,
        forecasted_achievement: 93,
        risk_level: 'Low',
        created_by: user?.id || '1',
        created_by_name: user?.first_name + ' ' + user?.last_name || 'John Doe',
        created_at: '2024-09-01T00:00:00Z',
        updated_at: '2024-09-29T00:00:00Z',
        days_remaining: 1,
        days_total: 30,
        expected_daily_progress: 0.5,
        actual_daily_progress: 0.6,
        variance_from_plan: 0.1,
      },
    ];

    setTargets(mockTargets);
    setLoading(false);
  }, [user]);

  const getCurrentMonthTargets = () => {
    const currentDate = new Date();
    return targets.filter(target => {
      const targetStart = new Date(target.period_start);
      const targetEnd = new Date(target.period_end);
      return currentDate >= targetStart && currentDate <= targetEnd;
    });
  };

  const getTargetsByRisk = () => {
    const atRisk = targets.filter(t => t.risk_level === 'High').length;
    const moderate = targets.filter(t => t.risk_level === 'Medium').length;
    const low = targets.filter(t => t.risk_level === 'Low').length;

    return [
      { name: 'Low Risk', value: low, color: '#4caf50' },
      { name: 'Medium Risk', value: moderate, color: '#ff9800' },
      { name: 'High Risk', value: atRisk, color: '#f44336' },
    ].filter(item => item.value > 0);
  };

  const getTeamLeaderboard = () => {
    // Mock team data - in real app, this would aggregate actual team performance
    return [
      { name: 'Sales Team A', achievement: 85, trend: 'up' },
      { name: 'Sales Team B', achievement: 78, trend: 'up' },
      { name: 'Sales Team C', achievement: 65, trend: 'down' },
    ];
  };

  const getIndividualAchievementRate = () => {
    const individualTargets = targets.filter(t => !t.team_target);
    if (individualTargets.length === 0) return 0;
    return individualTargets.reduce((sum, t) => sum + t.achievement_percentage, 0) / individualTargets.length;
  };

  const getForecastAccuracy = () => {
    // Mock forecast accuracy calculation
    return 87; // In real app, this would compare past forecasts with actual results
  };

  const currentTargets = getCurrentMonthTargets();
  const riskData = getTargetsByRisk();
  const teamLeaderboard = getTeamLeaderboard();
  const individualAchievement = getIndividualAchievementRate();
  const forecastAccuracy = getForecastAccuracy();

  const getAchievementColor = (achievement: number) => {
    if (achievement >= 90) return 'success.main';
    if (achievement >= 70) return 'info.main';
    if (achievement >= 50) return 'warning.main';
    return 'error.main';
  };

  const getTrendIcon = (trend: string) => {
    return trend === 'up' ? (
      <TrendingUp sx={{ color: 'success.main', fontSize: 16 }} />
    ) : (
      <TrendingDown sx={{ color: 'error.main', fontSize: 16 }} />
    );
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} sx={{ flex: '1 1 250px', minWidth: 200 }}>
            <CardContent>
              <Box sx={{ height: 100, bgcolor: 'grey.100', borderRadius: 1 }} />
            </CardContent>
          </Card>
        ))}
      </Box>
    );
  }

  return (
    <Grid container spacing={3}>
      {/* Current Month Progress */}
      <Grid item xs={12} md={6} lg={3}>
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Current Month Progress
            </Typography>
            {currentTargets.length > 0 ? (
              <Box>
                {currentTargets.slice(0, 2).map((target) => (
                  <Box key={target.id} sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="body2" noWrap>
                        {target.name}
                      </Typography>
                      <Typography variant="body2" fontWeight="bold" color={getAchievementColor(target.achievement_percentage)}>
                        {target.achievement_percentage}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={target.achievement_percentage}
                      sx={{
                        height: 6,
                        borderRadius: 3,
                        '& .MuiLinearProgress-bar': {
                          backgroundColor: getAchievementColor(target.achievement_percentage),
                        },
                      }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {target.days_remaining} days remaining
                    </Typography>
                  </Box>
                ))}
                {currentTargets.length > 2 && (
                  <Typography variant="caption" color="text.secondary">
                    +{currentTargets.length - 2} more targets
                  </Typography>
                )}
              </Box>
            ) : (
              <Box sx={{ textAlign: 'center', py: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  No active targets this month
                </Typography>
                {onCreateTarget && (
                  <Button
                    size="small"
                    startIcon={<AddIcon />}
                    onClick={onCreateTarget}
                    sx={{ mt: 1 }}
                  >
                    Create Target
                  </Button>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
      </Grid>

      {/* Team Leaderboard */}
      <Grid item xs={12} md={6} lg={3}>
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Team Leaderboard
            </Typography>
            <List dense>
              {teamLeaderboard.map((team, index) => (
                <ListItem key={team.name} sx={{ px: 0 }}>
                  <ListItemAvatar>
                    <Avatar sx={{ bgcolor: index === 0 ? '#ffd700' : index === 1 ? '#c0c0c0' : '#cd7f32', width: 32, height: 32 }}>
                      {index === 0 && <EmojiEvents sx={{ fontSize: 18 }} />}
                      {index > 0 && `#${index + 1}`}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={team.name}
                    secondary={`${team.achievement}%`}
                  />
                  {getTrendIcon(team.trend)}
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </Grid>

      {/* Individual Achievement Rate */}
      <Grid item xs={12} md={6} lg={3}>
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Person sx={{ color: 'primary.main', mr: 1 }} />
              <Typography variant="h6">
                Individual Achievement
              </Typography>
            </Box>
            <Typography variant="h4" color={getAchievementColor(individualAchievement)}>
              {Math.round(individualAchievement)}%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Average personal target achievement
            </Typography>
            <Box sx={{ mt: 2 }}>
              <LinearProgress
                variant="determinate"
                value={individualAchievement}
                sx={{
                  height: 8,
                  borderRadius: 4,
                  '& .MuiLinearProgress-bar': {
                    backgroundColor: getAchievementColor(individualAchievement),
                  },
                }}
              />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* Risk Distribution */}
      <Grid item xs={12} md={6} lg={3}>
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Risk Distribution
            </Typography>
            {riskData.length > 0 ? (
              <Box sx={{ height: 120, mb: 1 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={riskData}
                      cx="50%"
                      cy="50%"
                      innerRadius={25}
                      outerRadius={45}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {riskData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => [value, 'Targets']} />
                  </PieChart>
                </ResponsiveContainer>
              </Box>
            ) : (
              <Box sx={{ textAlign: 'center', py: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  No risk data available
                </Typography>
              </Box>
            )}
            {riskData.map((item) => (
              <Box key={item.name} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: item.color }} />
                <Typography variant="caption">
                  {item.name}: {item.value}
                </Typography>
              </Box>
            ))}
          </CardContent>
        </Card>
      </Grid>

      {/* Forecast Accuracy */}
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Speed sx={{ color: 'info.main', mr: 1 }} />
              <Typography variant="h6">
                Forecasting Performance
              </Typography>
            </Box>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="h4" color="info.main">
                  {forecastAccuracy}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Forecast Accuracy
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="h4" color="success.main">
                  {Math.round(targets.reduce((sum, t) => sum + t.forecasted_achievement, 0) / Math.max(targets.length, 1))}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Avg Forecasted Achievement
                </Typography>
              </Grid>
            </Grid>
            <Box sx={{ mt: 2 }}>
              <LinearProgress
                variant="determinate"
                value={forecastAccuracy}
                color="info"
                sx={{ height: 6, borderRadius: 3 }}
              />
              <Typography variant="caption" color="text.secondary">
                Based on historical forecast vs actual performance
              </Typography>
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* At Risk Alerts */}
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Warning sx={{ color: 'warning.main', mr: 1 }} />
              <Typography variant="h6">
                Targets at Risk
              </Typography>
            </Box>
            {targets.filter(t => t.risk_level === 'High' || t.achievement_percentage < 50).length > 0 ? (
              <List dense>
                {targets
                  .filter(t => t.risk_level === 'High' || t.achievement_percentage < 50)
                  .slice(0, 3)
                  .map((target) => (
                    <ListItem key={target.id} sx={{ px: 0 }}>
                      <ListItemText
                        primary={target.name}
                        secondary={`${target.achievement_percentage}% • ${target.days_remaining} days left`}
                      />
                      <Chip
                        size="small"
                        label={target.risk_level}
                        color={target.risk_level === 'High' ? 'error' : 'warning'}
                      />
                    </ListItem>
                  ))}
              </List>
            ) : (
              <Alert severity="success">
                <Typography variant="body2">
                  All targets are on track! No immediate risks detected.
                </Typography>
              </Alert>
            )}
          </CardContent>
        </Card>
      </Grid>

      {/* Recent Activity */}
      <Grid item xs={12}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Recent Target Activity
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h5" color="primary">
                    {targets.length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Active Targets
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h5" color="success.main">
                    {targets.filter(t => t.achievement_percentage >= 100).length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Achieved This Month
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h5" color="info.main">
                    {Math.round(targets.reduce((sum, t) => sum + t.achievement_percentage, 0) / Math.max(targets.length, 1))}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Overall Progress
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h5" color="warning.main">
                    {targets.filter(t => t.days_remaining <= 7).length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Due This Week
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};

export default TargetWidgets;