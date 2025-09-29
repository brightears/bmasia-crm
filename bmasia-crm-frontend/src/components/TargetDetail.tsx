import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  GridLegacy as Grid,
  Box,
  Typography,
  Chip,
  Card,
  CardContent,
  Tabs,
  Tab,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
} from '@mui/material';
import {
  Edit as EditIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Schedule as ScheduleIcon,
  Person as PersonIcon,
  Group as GroupIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
} from 'recharts';
import { SalesTarget } from '../types';
import TargetProgressGauge from './TargetProgressGauge';

interface TargetDetailProps {
  open: boolean;
  target: SalesTarget;
  onEdit: (target: SalesTarget) => void;
  onClose: () => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => (
  <div hidden={value !== index}>
    {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
  </div>
);

const TargetDetail: React.FC<TargetDetailProps> = ({
  open,
  target,
  onEdit,
  onClose
}) => {
  const [activeTab, setActiveTab] = useState(0);

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const formatValue = (value: number) => {
    if (target.target_type === 'Revenue') {
      const symbol = target.currency === 'USD' ? '$' : target.currency === 'THB' ? '฿' : '€';
      return `${symbol}${value.toLocaleString()}`;
    }
    return `${value.toLocaleString()} ${target.unit_type || ''}`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  // Generate mock progress data for charts
  const generateProgressData = () => {
    const data = [];
    const startDate = new Date(target.period_start);
    const endDate = new Date(target.period_end);
    const totalDays = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
    const dailyTarget = target.target_value / totalDays;

    for (let i = 0; i <= Math.min(totalDays, 30); i++) {
      const date = new Date(startDate);
      date.setDate(date.getDate() + i);

      const expectedValue = dailyTarget * (i + 1);
      const actualValue = expectedValue * (0.7 + Math.random() * 0.4); // Random variance

      data.push({
        date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        expected: Math.round(expectedValue),
        actual: Math.round(actualValue),
        target: target.target_value,
      });
    }
    return data;
  };

  const generateWeeklyBreakdown = () => {
    const weeks = [];
    const startDate = new Date(target.period_start);
    const endDate = new Date(target.period_end);

    let currentWeek = new Date(startDate);
    let weekNumber = 1;

    while (currentWeek < endDate && weekNumber <= 8) {
      const weekEnd = new Date(currentWeek);
      weekEnd.setDate(weekEnd.getDate() + 6);

      const weekProgress = Math.min(100, (weekNumber / 8) * target.achievement_percentage);

      weeks.push({
        week: `Week ${weekNumber}`,
        period: `${currentWeek.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${weekEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`,
        target: Math.round(target.target_value * (weekNumber / 8)),
        actual: Math.round(target.current_value * (weekProgress / target.achievement_percentage || 1)),
        achievement: Math.round(weekProgress),
      });

      currentWeek.setDate(currentWeek.getDate() + 7);
      weekNumber++;
    }

    return weeks;
  };

  const progressData = generateProgressData();
  const weeklyData = generateWeeklyBreakdown();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Active': return 'primary';
      case 'Completed': return 'success';
      case 'Cancelled': return 'error';
      case 'Draft': return 'default';
      default: return 'default';
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'Low': return 'success';
      case 'Medium': return 'warning';
      case 'High': return 'error';
      default: return 'default';
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">{target.name}</Typography>
          <Box>
            <IconButton onClick={() => onEdit(target)} sx={{ mr: 1 }}>
              <EditIcon />
            </IconButton>
            <IconButton onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent>
        {/* Header Info */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} md={4}>
            <TargetProgressGauge target={target} size="large" />
          </Grid>

          <Grid item xs={12} md={8}>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">
                      Target Period
                    </Typography>
                    <Typography variant="body1">
                      {formatDate(target.period_start)} - {formatDate(target.period_end)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {target.days_remaining} days remaining
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">
                      Assignment
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                      {target.team_target ? (
                        <>
                          <GroupIcon sx={{ fontSize: 16, mr: 0.5 }} />
                          <Typography variant="body1">{target.team_name}</Typography>
                        </>
                      ) : (
                        <>
                          <PersonIcon sx={{ fontSize: 16, mr: 0.5 }} />
                          <Typography variant="body1">{target.assigned_to_name}</Typography>
                        </>
                      )}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">
                      Status
                    </Typography>
                    <Chip
                      label={target.status}
                      color={getStatusColor(target.status) as any}
                      sx={{ mt: 1 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">
                      Risk Level
                    </Typography>
                    <Chip
                      label={target.risk_level}
                      color={getRiskColor(target.risk_level) as any}
                      sx={{ mt: 1 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary">
                      Type
                    </Typography>
                    <Typography variant="body1" sx={{ mt: 1 }}>
                      {target.target_type}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Grid>
        </Grid>

        {/* Key Metrics */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <TrendingUpIcon sx={{ color: 'success.main', mr: 1 }} />
                  <Typography variant="h6">
                    {formatValue(target.current_value)}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Current Achievement
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={target.achievement_percentage}
                  sx={{ mt: 1 }}
                />
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <ScheduleIcon sx={{ color: 'info.main', mr: 1 }} />
                  <Typography variant="h6">
                    {target.forecasted_achievement.toFixed(0)}%
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Forecasted Achievement
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {formatValue(target.forecasted_value)} projected
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Typography variant="h6">
                    {target.variance_from_plan > 0 ? '+' : ''}{target.variance_from_plan.toFixed(1)}
                  </Typography>
                  {target.variance_from_plan > 0 ? (
                    <TrendingUpIcon sx={{ color: 'success.main', ml: 1 }} />
                  ) : (
                    <TrendingDownIcon sx={{ color: 'error.main', ml: 1 }} />
                  )}
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Variance from Plan
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Daily average: {target.actual_daily_progress.toLocaleString()}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Typography variant="h6" color="success.main">
                    {target.year_over_year_growth ? `+${target.year_over_year_growth.toFixed(1)}%` : 'N/A'}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  YoY Growth
                </Typography>
                {target.previous_period_value && (
                  <Typography variant="caption" color="text.secondary">
                    vs {formatValue(target.previous_period_value)}
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Detailed Tabs */}
        <Paper sx={{ width: '100%' }}>
          <Tabs value={activeTab} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tab label="Progress Tracking" />
            <Tab label="Weekly Breakdown" />
            <Tab label="Comparison" />
            <Tab label="Notes" />
          </Tabs>

          <TabPanel value={activeTab} index={0}>
            <Typography variant="h6" gutterBottom>
              Progress Over Time
            </Typography>
            <Box sx={{ height: 300, mb: 3 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={progressData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip formatter={(value: number) => [formatValue(value), '']} />
                  <Area
                    type="monotone"
                    dataKey="expected"
                    stackId="1"
                    stroke="#8884d8"
                    fill="#8884d8"
                    fillOpacity={0.3}
                    name="Expected"
                  />
                  <Area
                    type="monotone"
                    dataKey="actual"
                    stackId="2"
                    stroke="#82ca9d"
                    fill="#82ca9d"
                    fillOpacity={0.6}
                    name="Actual"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </Box>

            <Typography variant="body2" color="text.secondary">
              The chart shows your actual progress (green) compared to the expected pace (blue) needed to reach your target.
            </Typography>
          </TabPanel>

          <TabPanel value={activeTab} index={1}>
            <Typography variant="h6" gutterBottom>
              Weekly Performance Breakdown
            </Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Period</TableCell>
                    <TableCell align="right">Target</TableCell>
                    <TableCell align="right">Actual</TableCell>
                    <TableCell align="right">Achievement</TableCell>
                    <TableCell>Progress</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {weeklyData.map((week) => (
                    <TableRow key={week.week}>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {week.week}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {week.period}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        {formatValue(week.target)}
                      </TableCell>
                      <TableCell align="right">
                        {formatValue(week.actual)}
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          color={week.achievement >= 100 ? 'success.main' :
                                 week.achievement >= 80 ? 'info.main' :
                                 week.achievement >= 60 ? 'warning.main' : 'error.main'}
                        >
                          {week.achievement}%
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(week.achievement, 100)}
                          color={week.achievement >= 100 ? 'success' :
                                 week.achievement >= 80 ? 'info' :
                                 week.achievement >= 60 ? 'warning' : 'error'}
                          sx={{ width: 100 }}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </TabPanel>

          <TabPanel value={activeTab} index={2}>
            <Typography variant="h6" gutterBottom>
              Historical Comparison
            </Typography>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle1" gutterBottom>
                      Previous Period Performance
                    </Typography>
                    {target.previous_period_value ? (
                      <>
                        <Typography variant="h5" color="text.secondary">
                          {formatValue(target.previous_period_value)}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Achievement: {target.previous_period_achievement?.toFixed(0) || 0}%
                        </Typography>
                      </>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        No previous period data available
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle1" gutterBottom>
                      Current vs Previous
                    </Typography>
                    {target.year_over_year_growth && (
                      <>
                        <Typography
                          variant="h5"
                          color={target.year_over_year_growth > 0 ? 'success.main' : 'error.main'}
                        >
                          {target.year_over_year_growth > 0 ? '+' : ''}{target.year_over_year_growth.toFixed(1)}%
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Year-over-year growth
                        </Typography>
                      </>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </TabPanel>

          <TabPanel value={activeTab} index={3}>
            <Typography variant="h6" gutterBottom>
              Target Information
            </Typography>

            {target.justification && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Justification
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {target.justification}
                </Typography>
              </Box>
            )}

            {target.notes && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Notes
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {target.notes}
                </Typography>
              </Box>
            )}

            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Target Details
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="body2">
                    <strong>Created by:</strong> {target.created_by_name}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2">
                    <strong>Created:</strong> {formatDate(target.created_at)}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2">
                    <strong>Last updated:</strong> {formatDate(target.updated_at)}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2">
                    <strong>Period type:</strong> {target.period_type}
                  </Typography>
                </Grid>
              </Grid>
            </Box>
          </TabPanel>
        </Paper>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button onClick={() => onEdit(target)} variant="contained" startIcon={<EditIcon />}>
          Edit Target
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TargetDetail;