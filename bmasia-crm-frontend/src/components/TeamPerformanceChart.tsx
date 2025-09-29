import React from 'react';
import { Paper, Typography, Box, Card, CardContent, LinearProgress, Avatar, Chip } from '@mui/material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { TrendingUp, TrendingDown, Remove } from '@mui/icons-material';
import { SalesTarget } from '../types';

interface TeamPerformanceChartProps {
  targets: SalesTarget[];
}

const TeamPerformanceChart: React.FC<TeamPerformanceChartProps> = ({ targets }) => {
  const teamTargets = targets.filter(t => t.team_target);

  const generateTeamPerformanceData = () => {
    const teamMap = new Map();

    teamTargets.forEach(target => {
      const teamName = target.team_name || 'Unknown Team';

      if (!teamMap.has(teamName)) {
        teamMap.set(teamName, {
          teamName,
          targets: [],
          totalTarget: 0,
          totalCurrent: 0,
          targetCount: 0,
        });
      }

      const team = teamMap.get(teamName);
      team.targets.push(target);
      team.totalTarget += target.target_value;
      team.totalCurrent += target.current_value;
      team.targetCount++;
    });

    return Array.from(teamMap.values()).map(team => ({
      ...team,
      achievement: team.totalTarget > 0 ? (team.totalCurrent / team.totalTarget) * 100 : 0,
      avgAchievement: team.targets.reduce((sum: number, t: SalesTarget) => sum + t.achievement_percentage, 0) / team.targetCount,
    })).sort((a, b) => b.avgAchievement - a.avgAchievement);
  };

  const teamPerformanceData = generateTeamPerformanceData();

  const getPerformanceColor = (achievement: number) => {
    if (achievement >= 90) return '#1b5e20';
    if (achievement >= 80) return '#388e3c';
    if (achievement >= 70) return '#66bb6a';
    if (achievement >= 60) return '#ffb74d';
    if (achievement >= 40) return '#ff8a65';
    return '#e57373';
  };

  const getTrendIcon = (achievement: number, forecast: number = achievement) => {
    if (forecast > achievement) return <TrendingUp sx={{ color: 'success.main', fontSize: 16 }} />;
    if (forecast < achievement) return <TrendingDown sx={{ color: 'error.main', fontSize: 16 }} />;
    return <Remove sx={{ color: 'grey.500', fontSize: 16 }} />;
  };

  const generateTargetTypeDistribution = () => {
    const typeMap = new Map();

    teamTargets.forEach(target => {
      const type = target.target_type;
      if (!typeMap.has(type)) {
        typeMap.set(type, { count: 0, totalValue: 0, totalAchievement: 0 });
      }

      const typeData = typeMap.get(type);
      typeData.count++;
      typeData.totalValue += target.current_value;
      typeData.totalAchievement += target.achievement_percentage;
    });

    return Array.from(typeMap.entries()).map(([type, data]) => ({
      name: type,
      count: data.count,
      avgAchievement: data.totalAchievement / data.count,
      totalValue: data.totalValue,
    }));
  };

  const targetTypeData = generateTargetTypeDistribution();
  const colors = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

  if (teamTargets.length === 0) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Team Performance
        </Typography>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body1" color="text.secondary">
            No team targets available
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Team Performance Bar Chart */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Team Achievement Comparison
        </Typography>
        <Box sx={{ height: 300, mb: 2 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={teamPerformanceData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="teamName" tick={{ fontSize: 12 }} />
              <YAxis label={{ value: 'Achievement (%)', angle: -90, position: 'insideLeft' }} />
              <Tooltip
                formatter={(value: number) => [`${Math.round(value)}%`, 'Average Achievement']}
                labelFormatter={(label) => `Team: ${label}`}
              />
              <Bar
                dataKey="avgAchievement"
                fill="#1976d2"
                radius={[4, 4, 0, 0]}
                name="Achievement %"
              >
                {teamPerformanceData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getPerformanceColor(entry.avgAchievement)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Box>

        {/* Team Performance Cards */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {teamPerformanceData.map((team, index) => (
            <Card key={team.teamName} variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Avatar sx={{ bgcolor: getPerformanceColor(team.avgAchievement), width: 32, height: 32 }}>
                      #{index + 1}
                    </Avatar>
                    <Box>
                      <Typography variant="h6" component="div">
                        {team.teamName}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {team.targetCount} active target{team.targetCount !== 1 ? 's' : ''}
                      </Typography>
                    </Box>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="h5" fontWeight="bold" color={getPerformanceColor(team.avgAchievement)}>
                      {Math.round(team.avgAchievement)}%
                    </Typography>
                    {getTrendIcon(team.avgAchievement)}
                  </Box>
                </Box>

                <LinearProgress
                  variant="determinate"
                  value={Math.min(team.avgAchievement, 100)}
                  sx={{
                    height: 8,
                    borderRadius: 4,
                    mb: 2,
                    '& .MuiLinearProgress-bar': {
                      backgroundColor: getPerformanceColor(team.avgAchievement),
                    },
                  }}
                />

                <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Current: {team.totalCurrent.toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Target: {team.totalTarget.toLocaleString()}
                  </Typography>
                  <Chip
                    size="small"
                    label={team.avgAchievement >= 80 ? 'Exceeding' : team.avgAchievement >= 60 ? 'On Track' : 'At Risk'}
                    color={team.avgAchievement >= 80 ? 'success' : team.avgAchievement >= 60 ? 'info' : 'error'}
                  />
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      </Paper>

      {/* Target Type Distribution */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Team Target Type Distribution
        </Typography>
        <Box sx={{ display: 'flex', gap: 4 }}>
          <Box sx={{ width: 300, height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={targetTypeData}
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  dataKey="count"
                  label={({ name, count }) => `${name}: ${count}`}
                >
                  {targetTypeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => [value, 'Count']} />
              </PieChart>
            </ResponsiveContainer>
          </Box>

          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle1" gutterBottom>
              Performance by Target Type
            </Typography>
            {targetTypeData.map((type, index) => (
              <Box key={type.name} sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        backgroundColor: colors[index % colors.length],
                        borderRadius: '50%',
                      }}
                    />
                    <Typography variant="body2" fontWeight="medium">
                      {type.name}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    {Math.round(type.avgAchievement)}% avg
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(type.avgAchievement, 100)}
                  sx={{
                    height: 6,
                    borderRadius: 3,
                    '& .MuiLinearProgress-bar': {
                      backgroundColor: colors[index % colors.length],
                    },
                  }}
                />
                <Typography variant="caption" color="text.secondary">
                  {type.count} target{type.count !== 1 ? 's' : ''} • Total: {type.totalValue.toLocaleString()}
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      </Paper>

      {/* Team Performance Summary */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Team Performance Summary
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="primary">
              {teamPerformanceData.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Active Teams
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="success.main">
              {Math.round(teamPerformanceData.reduce((sum, team) => sum + team.avgAchievement, 0) / Math.max(teamPerformanceData.length, 1))}%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Average Achievement
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="info.main">
              {teamPerformanceData.filter(team => team.avgAchievement >= 80).length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              High Performing Teams
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="warning.main">
              {teamPerformanceData.filter(team => team.avgAchievement < 60).length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Teams At Risk
            </Typography>
          </Box>
        </Box>
      </Paper>
    </Box>
  );
};

export default TeamPerformanceChart;