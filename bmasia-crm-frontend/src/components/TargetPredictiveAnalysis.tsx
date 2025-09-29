import React from 'react';
import {
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  GridLegacy as Grid,
  Alert,
  Chip,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
} from '@mui/material';
import {
  TrendingUp,
  Warning,
  CheckCircle,
  Error,
  Lightbulb,
  Assessment,
  Speed,
  Timeline,
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
  ReferenceLine,
  ScatterChart,
  Scatter,
  Legend,
} from 'recharts';
import { SalesTarget, TargetAnalytics } from '../types';

interface TargetPredictiveAnalysisProps {
  targets: SalesTarget[];
  analytics: TargetAnalytics;
}

const TargetPredictiveAnalysis: React.FC<TargetPredictiveAnalysisProps> = ({
  targets,
  analytics
}) => {
  const generatePredictions = () => {
    return targets.map(target => {
      const daysElapsed = target.days_total - target.days_remaining;
      const currentPace = daysElapsed > 0 ? target.current_value / daysElapsed : 0;
      const projectedFinalValue = currentPace * target.days_total;
      const projectedAchievement = (projectedFinalValue / target.target_value) * 100;

      // Calculate confidence based on consistency
      const consistency = Math.max(0, 100 - Math.abs(target.variance_from_plan) * 10);
      const confidence = Math.min(95, consistency);

      // Determine risk factors
      const riskFactors = [];
      if (target.achievement_percentage < 50 && target.days_remaining < target.days_total * 0.5) {
        riskFactors.push('Low achievement with limited time remaining');
      }
      if (target.actual_daily_progress < target.expected_daily_progress) {
        riskFactors.push('Behind expected daily pace');
      }
      if (target.risk_level === 'High') {
        riskFactors.push('High risk classification');
      }

      // Determine recommended actions
      const recommendations = [];
      if (projectedAchievement < 80) {
        recommendations.push('Increase daily activity rate');
        recommendations.push('Review and optimize strategy');
      }
      if (target.days_remaining < 30) {
        recommendations.push('Focus on high-value opportunities');
      }
      if (target.variance_from_plan < -10) {
        recommendations.push('Analyze performance gaps');
      }

      return {
        target_id: target.id,
        target_name: target.name,
        current_achievement: target.achievement_percentage,
        predicted_achievement: Math.round(projectedAchievement),
        confidence_level: Math.round(confidence),
        probability_of_success: Math.round(Math.min(100, projectedAchievement)),
        risk_factors: riskFactors,
        recommended_actions: recommendations,
        days_remaining: target.days_remaining,
        current_pace: currentPace,
        required_pace: target.days_remaining > 0 ? (target.target_value - target.current_value) / target.days_remaining : 0,
      };
    });
  };

  const predictions = generatePredictions();

  const generateForecastData = () => {
    const today = new Date();
    const forecastData = [];

    for (let i = 0; i <= 30; i++) {
      const date = new Date(today);
      date.setDate(date.getDate() + i);

      const averageDailyProgress = targets.reduce((sum, target) => sum + target.actual_daily_progress, 0) / targets.length;
      const currentTotal = targets.reduce((sum, target) => sum + target.current_value, 0);
      const projectedValue = currentTotal + (averageDailyProgress * i);

      forecastData.push({
        date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        projected: Math.round(projectedValue),
        optimistic: Math.round(projectedValue * 1.2),
        conservative: Math.round(projectedValue * 0.8),
        target: targets.reduce((sum, target) => sum + target.target_value, 0),
      });
    }

    return forecastData;
  };

  const forecastData = generateForecastData();

  const generateRiskScoreData = () => {
    return targets.map(target => ({
      name: target.name.substring(0, 20) + (target.name.length > 20 ? '...' : ''),
      achievement: target.achievement_percentage,
      riskScore: target.risk_level === 'High' ? 80 : target.risk_level === 'Medium' ? 50 : 20,
      daysRemaining: target.days_remaining,
    }));
  };

  const riskScoreData = generateRiskScoreData();

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 80) return 'success.main';
    if (confidence >= 60) return 'info.main';
    if (confidence >= 40) return 'warning.main';
    return 'error.main';
  };

  const getProbabilityColor = (probability: number) => {
    if (probability >= 90) return 'success';
    if (probability >= 70) return 'info';
    if (probability >= 50) return 'warning';
    return 'error';
  };

  const getSuccessIcon = (probability: number) => {
    if (probability >= 80) return <CheckCircle color="success" />;
    if (probability >= 60) return <Warning color="warning" />;
    return <Error color="error" />;
  };

  if (targets.length === 0) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Predictive Analysis
        </Typography>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body1" color="text.secondary">
            No target data available for predictive analysis
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Overview Cards */}
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Assessment sx={{ color: 'primary.main', mr: 1 }} />
                <Typography variant="h6">
                  {Math.round(predictions.reduce((sum, p) => sum + p.predicted_achievement, 0) / predictions.length)}%
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Avg Predicted Achievement
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Speed sx={{ color: 'info.main', mr: 1 }} />
                <Typography variant="h6">
                  {Math.round(predictions.reduce((sum, p) => sum + p.confidence_level, 0) / predictions.length)}%
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Avg Confidence Level
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <CheckCircle sx={{ color: 'success.main', mr: 1 }} />
                <Typography variant="h6">
                  {predictions.filter(p => p.probability_of_success >= 80).length}
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Likely to Succeed
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Warning sx={{ color: 'warning.main', mr: 1 }} />
                <Typography variant="h6">
                  {predictions.filter(p => p.probability_of_success < 60).length}
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                At Risk
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Forecast Chart */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          30-Day Performance Forecast
        </Typography>
        <Box sx={{ height: 350, mb: 2 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={forecastData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number, name: string) => [
                  value.toLocaleString(),
                  name === 'projected' ? 'Projected' :
                  name === 'optimistic' ? 'Optimistic' :
                  name === 'conservative' ? 'Conservative' : 'Target'
                ]}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="conservative"
                stackId="1"
                stroke="#ff7300"
                fill="#ff7300"
                fillOpacity={0.2}
                name="Conservative"
              />
              <Area
                type="monotone"
                dataKey="projected"
                stackId="2"
                stroke="#1976d2"
                fill="#1976d2"
                fillOpacity={0.4}
                name="Projected"
              />
              <Area
                type="monotone"
                dataKey="optimistic"
                stackId="3"
                stroke="#4caf50"
                fill="#4caf50"
                fillOpacity={0.2}
                name="Optimistic"
              />
              <ReferenceLine y={forecastData[0]?.target} stroke="#e91e63" strokeDasharray="5 5" label="Target" />
            </AreaChart>
          </ResponsiveContainer>
        </Box>
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="body2">
            The forecast shows three scenarios based on current performance trends. The projected line represents the most likely outcome.
          </Typography>
        </Alert>
      </Paper>

      {/* Risk vs Achievement Scatter */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Risk vs Achievement Analysis
        </Typography>
        <Box sx={{ height: 300, mb: 2 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart data={riskScoreData}>
              <CartesianGrid />
              <XAxis
                type="number"
                dataKey="achievement"
                name="Achievement %"
                domain={[0, 100]}
                tick={{ fontSize: 12 }}
              />
              <YAxis
                type="number"
                dataKey="riskScore"
                name="Risk Score"
                domain={[0, 100]}
                tick={{ fontSize: 12 }}
              />
              <Tooltip
                formatter={(value: any, name: any) => [
                  name === 'riskScore' ? `${value} (Risk Score)` : `${value}%`,
                  name === 'riskScore' ? 'Risk' : 'Achievement'
                ]}
                labelFormatter={(label: any, payload: any) => payload?.[0]?.payload?.name || ''}
              />
              <Scatter
                dataKey="riskScore"
                fill="#8884d8"
                name="Targets"
              />
            </ScatterChart>
          </ResponsiveContainer>
        </Box>
        <Typography variant="body2" color="text.secondary">
          Targets in the bottom-right quadrant (high achievement, low risk) are performing well.
          Top-left quadrant targets (low achievement, high risk) need immediate attention.
        </Typography>
      </Paper>

      {/* Individual Target Predictions */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Individual Target Predictions
        </Typography>
        <Grid container spacing={2}>
          {predictions.map((prediction) => (
            <Grid item xs={12} md={6} key={prediction.target_id}>
              <Card variant="outlined">
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="subtitle1" noWrap>
                      {prediction.target_name}
                    </Typography>
                    {getSuccessIcon(prediction.probability_of_success)}
                  </Box>

                  <Grid container spacing={2} sx={{ mb: 2 }}>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">
                        Current
                      </Typography>
                      <Typography variant="h6">
                        {prediction.current_achievement}%
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="text.secondary">
                        Predicted
                      </Typography>
                      <Typography variant="h6" color={getConfidenceColor(prediction.confidence_level)}>
                        {prediction.predicted_achievement}%
                      </Typography>
                    </Grid>
                  </Grid>

                  <Box sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="body2" color="text.secondary">
                        Success Probability
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {prediction.probability_of_success}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={prediction.probability_of_success}
                      color={getProbabilityColor(prediction.probability_of_success) as any}
                      sx={{ height: 6, borderRadius: 3 }}
                    />
                  </Box>

                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Confidence: {prediction.confidence_level}%
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Days remaining: {prediction.days_remaining}
                    </Typography>
                  </Box>

                  {prediction.risk_factors.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" fontWeight="bold" color="error.main" gutterBottom>
                        Risk Factors:
                      </Typography>
                      <List dense>
                        {prediction.risk_factors.map((factor, index) => (
                          <ListItem key={index} sx={{ py: 0 }}>
                            <ListItemIcon sx={{ minWidth: 20 }}>
                              <Warning sx={{ fontSize: 16, color: 'warning.main' }} />
                            </ListItemIcon>
                            <ListItemText
                              primary={factor}
                              sx={{ '& .MuiTypography-root': { fontSize: '0.875rem' } }}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </Box>
                  )}

                  {prediction.recommended_actions.length > 0 && (
                    <Box>
                      <Typography variant="body2" fontWeight="bold" color="info.main" gutterBottom>
                        Recommendations:
                      </Typography>
                      <List dense>
                        {prediction.recommended_actions.map((action, index) => (
                          <ListItem key={index} sx={{ py: 0 }}>
                            <ListItemIcon sx={{ minWidth: 20 }}>
                              <Lightbulb sx={{ fontSize: 16, color: 'info.main' }} />
                            </ListItemIcon>
                            <ListItemText
                              primary={action}
                              sx={{ '& .MuiTypography-root': { fontSize: '0.875rem' } }}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Paper>

      {/* Key Insights */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Key Insights & Recommendations
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" gutterBottom color="success.main">
              <TrendingUp sx={{ fontSize: 16, mr: 1 }} />
              Positive Indicators
            </Typography>
            <List dense>
              <ListItem>
                <ListItemText primary={`${predictions.filter(p => p.predicted_achievement >= 100).length} targets are on track to exceed goals`} />
              </ListItem>
              <ListItem>
                <ListItemText primary={`Average confidence level is ${Math.round(predictions.reduce((sum, p) => sum + p.confidence_level, 0) / predictions.length)}%`} />
              </ListItem>
              <ListItem>
                <ListItemText primary={`${predictions.filter(p => p.current_pace > p.required_pace).length} targets are ahead of required pace`} />
              </ListItem>
            </List>
          </Grid>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" gutterBottom color="warning.main">
              <Warning sx={{ fontSize: 16, mr: 1 }} />
              Areas for Attention
            </Typography>
            <List dense>
              <ListItem>
                <ListItemText primary={`${predictions.filter(p => p.probability_of_success < 60).length} targets are at high risk`} />
              </ListItem>
              <ListItem>
                <ListItemText primary={`${predictions.filter(p => p.current_pace < p.required_pace).length} targets need pace improvement`} />
              </ListItem>
              <ListItem>
                <ListItemText primary="Consider reallocating resources to high-risk targets" />
              </ListItem>
            </List>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default TargetPredictiveAnalysis;