import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Tabs,
  Tab,
  Button,
  GridLegacy as Grid,
  Card,
  CardContent,
  Chip,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  Menu,
  ListItemIcon,
  ListItemText,
  IconButton,
  Snackbar,
} from '@mui/material';
import {
  Add as AddIcon,
  TrendingUp as TrendingUpIcon,
  Group as GroupIcon,
  Person as PersonIcon,
  Analytics as AnalyticsIcon,
  Warning as WarningIcon,
  FileDownload as FileDownloadIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import { SalesTarget, TargetAnalytics } from '../types';
import LoadingSkeleton from '../components/LoadingSkeleton';
import TargetForm from '../components/TargetForm';
import TargetDetail from '../components/TargetDetail';
import TargetProgressGauge from '../components/TargetProgressGauge';
import TargetTrendChart from '../components/TargetTrendChart';
import TeamPerformanceChart from '../components/TeamPerformanceChart';
import TargetHeatMap from '../components/TargetHeatMap';
import TargetLeaderboard from '../components/TargetLeaderboard';
import TargetPredictiveAnalysis from '../components/TargetPredictiveAnalysis';
import { useAuth } from '../contexts/AuthContext';
import { exportTargetsReport } from '../utils/exportUtils';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => (
  <div hidden={value !== index} style={{ width: '100%' }}>
    {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
  </div>
);

const SalesTargets: React.FC = () => {
  const { user } = useAuth();
  const [targets, setTargets] = useState<SalesTarget[]>([]);
  const [analytics, setAnalytics] = useState<TargetAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState(0);
  const [selectedTarget, setSelectedTarget] = useState<SalesTarget | null>(null);
  const [showTargetForm, setShowTargetForm] = useState(false);
  const [editingTarget, setEditingTarget] = useState<SalesTarget | null>(null);
  const [filterPeriod, setFilterPeriod] = useState<'all' | 'Monthly' | 'Quarterly' | 'Yearly'>('all');
  const [filterType, setFilterType] = useState<'all' | 'Revenue' | 'Units' | 'Customers' | 'Contracts'>('all');
  const [exportMenuAnchor, setExportMenuAnchor] = useState<null | HTMLElement>(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  useEffect(() => {
    loadData();
  }, [filterPeriod, filterType]);

  const loadData = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API calls
      await generateMockData();
    } catch (err: any) {
      setError('Failed to load sales targets data');
      console.error('Sales targets error:', err);
    } finally {
      setLoading(false);
    }
  };

  const generateMockData = async () => {
    // Generate mock targets for demonstration
    const mockTargets: SalesTarget[] = [
      {
        id: '1',
        name: 'Q4 2024 Revenue Target',
        period_type: 'Quarterly',
        period_start: '2024-10-01',
        period_end: '2024-12-31',
        target_type: 'Revenue',
        target_value: 250000,
        stretch_target: 300000,
        currency: 'USD',
        assigned_to: user?.id || '1',
        assigned_to_name: user?.first_name + ' ' + user?.last_name || 'John Doe',
        team_target: false,
        status: 'Active',
        current_value: 180000,
        achievement_percentage: 72,
        stretch_achievement_percentage: 60,
        is_on_track: true,
        forecasted_value: 240000,
        forecasted_achievement: 96,
        risk_level: 'Low',
        notes: 'Strong pipeline, on track to exceed target',
        created_by: user?.id || '1',
        created_by_name: user?.first_name + ' ' + user?.last_name || 'John Doe',
        created_at: '2024-09-01T00:00:00Z',
        updated_at: '2024-09-29T00:00:00Z',
        days_remaining: 92,
        days_total: 92,
        expected_daily_progress: 2717,
        actual_daily_progress: 3000,
        variance_from_plan: 283,
        previous_period_value: 220000,
        previous_period_achievement: 88,
        year_over_year_growth: 15.2,
      },
      {
        id: '2',
        name: 'Team Sales - New Customers',
        period_type: 'Monthly',
        period_start: '2024-09-01',
        period_end: '2024-09-30',
        target_type: 'Customers',
        target_value: 25,
        currency: 'USD',
        unit_type: 'customers',
        team_target: true,
        team_name: 'Sales Team A',
        status: 'Active',
        current_value: 18,
        achievement_percentage: 72,
        is_on_track: true,
        forecasted_value: 24,
        forecasted_achievement: 96,
        risk_level: 'Low',
        notes: 'Good progress on customer acquisition',
        created_by: user?.id || '1',
        created_by_name: user?.first_name + ' ' + user?.last_name || 'John Doe',
        created_at: '2024-09-01T00:00:00Z',
        updated_at: '2024-09-29T00:00:00Z',
        days_remaining: 1,
        days_total: 30,
        expected_daily_progress: 0.83,
        actual_daily_progress: 0.9,
        variance_from_plan: 0.07,
        previous_period_value: 22,
        previous_period_achievement: 88,
        year_over_year_growth: 20.5,
      },
    ];

    const mockAnalytics: TargetAnalytics = {
      total_targets: 12,
      active_targets: 8,
      achieved_targets: 3,
      at_risk_targets: 2,
      overall_achievement_rate: 78.5,
      revenue_targets: {
        total_target: 1200000,
        current_value: 850000,
        achievement_percentage: 70.8,
        targets_count: 5,
        at_risk_count: 1,
      },
      unit_targets: {
        total_target: 150,
        current_value: 120,
        achievement_percentage: 80,
        targets_count: 3,
        at_risk_count: 0,
      },
      customer_targets: {
        total_target: 75,
        current_value: 58,
        achievement_percentage: 77.3,
        targets_count: 2,
        at_risk_count: 1,
      },
      contract_targets: {
        total_target: 30,
        current_value: 22,
        achievement_percentage: 73.3,
        targets_count: 2,
        at_risk_count: 0,
      },
      team_performance: [],
      individual_performance: [],
      monthly_trends: [],
      predictions: [],
    };

    setTargets(mockTargets);
    setAnalytics(mockAnalytics);
  };

  const getFilteredTargets = () => {
    return targets.filter(target => {
      if (filterPeriod !== 'all' && target.period_type !== filterPeriod) return false;
      if (filterType !== 'all' && target.target_type !== filterType) return false;
      return true;
    });
  };

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

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleFilterPeriodChange = (event: SelectChangeEvent) => {
    setFilterPeriod(event.target.value as any);
  };

  const handleFilterTypeChange = (event: SelectChangeEvent) => {
    setFilterType(event.target.value as any);
  };

  const handleCreateTarget = () => {
    setEditingTarget(null);
    setShowTargetForm(true);
  };

  const handleEditTarget = (target: SalesTarget) => {
    setEditingTarget(target);
    setShowTargetForm(true);
  };

  const handleTargetSave = (target: SalesTarget) => {
    if (editingTarget) {
      setTargets(prev => prev.map(t => t.id === target.id ? target : t));
    } else {
      setTargets(prev => [...prev, { ...target, id: Date.now().toString() }]);
    }
    setShowTargetForm(false);
    setEditingTarget(null);
  };

  const handleTargetFormClose = () => {
    setShowTargetForm(false);
    setEditingTarget(null);
  };

  const handleExportClick = (event: React.MouseEvent<HTMLElement>) => {
    setExportMenuAnchor(event.currentTarget);
  };

  const handleExportClose = () => {
    setExportMenuAnchor(null);
  };

  const handleExport = async (format: 'pdf' | 'excel' | 'png') => {
    try {
      setExportLoading(true);
      setExportMenuAnchor(null);

      const filteredTargets = getFilteredTargets();
      const timestamp = new Date().toISOString().slice(0, 10);
      const filename = `sales-targets-${timestamp}`;

      await exportTargetsReport(filteredTargets, {
        format,
        filename,
        title: 'Sales Targets Report',
        subtitle: `Generated on ${new Date().toLocaleDateString()} • ${filteredTargets.length} targets`,
        includeCharts: format === 'pdf',
      });

      setSnackbarMessage(`Report exported successfully as ${format.toUpperCase()}`);
      setSnackbarOpen(true);
    } catch (error) {
      console.error('Export failed:', error);
      setSnackbarMessage('Export failed. Please try again.');
      setSnackbarOpen(true);
    } finally {
      setExportLoading(false);
    }
  };

  if (loading) {
    return <LoadingSkeleton variant="dashboard" />;
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  const filteredTargets = getFilteredTargets();

  return (
    <Box data-export="targets-page">
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Sales Targets
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <IconButton
            onClick={handleExportClick}
            disabled={exportLoading}
            sx={{ mr: 1 }}
          >
            <MoreVertIcon />
          </IconButton>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateTarget}
          >
            Create Target
          </Button>
        </Box>
      </Box>

      {/* Quick Stats Overview */}
      {analytics && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <TrendingUpIcon sx={{ color: 'primary.main', mr: 1 }} />
                  <Typography variant="h6">
                    {analytics.active_targets}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Active Targets
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <AnalyticsIcon sx={{ color: 'success.main', mr: 1 }} />
                  <Typography variant="h6">
                    {analytics.overall_achievement_rate.toFixed(1)}%
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Overall Achievement
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <GroupIcon sx={{ color: 'info.main', mr: 1 }} />
                  <Typography variant="h6">
                    {analytics.achieved_targets}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Achieved Targets
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <WarningIcon sx={{ color: 'warning.main', mr: 1 }} />
                  <Typography variant="h6">
                    {analytics.at_risk_targets}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  At Risk Targets
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Period</InputLabel>
            <Select
              value={filterPeriod}
              onChange={handleFilterPeriodChange}
              label="Period"
            >
              <MenuItem value="all">All Periods</MenuItem>
              <MenuItem value="Monthly">Monthly</MenuItem>
              <MenuItem value="Quarterly">Quarterly</MenuItem>
              <MenuItem value="Yearly">Yearly</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Type</InputLabel>
            <Select
              value={filterType}
              onChange={handleFilterTypeChange}
              label="Type"
            >
              <MenuItem value="all">All Types</MenuItem>
              <MenuItem value="Revenue">Revenue</MenuItem>
              <MenuItem value="Units">Units</MenuItem>
              <MenuItem value="Customers">Customers</MenuItem>
              <MenuItem value="Contracts">Contracts</MenuItem>
            </Select>
          </FormControl>
          <Typography variant="body2" color="text.secondary">
            Showing {filteredTargets.length} of {targets.length} targets
          </Typography>
        </Box>
      </Paper>

      <Paper sx={{ width: '100%' }}>
        <Tabs value={activeTab} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Overview" />
          <Tab label="Analytics" />
          <Tab label="Team Performance" />
          <Tab label="Individual Performance" />
          <Tab label="Predictions" />
        </Tabs>

        <TabPanel value={activeTab} index={0}>
          {/* Targets List with Progress Gauges */}
          <Grid container spacing={3}>
            {filteredTargets.map((target) => (
              <Grid item xs={12} md={6} lg={4} key={target.id}>
                <Card
                  sx={{
                    cursor: 'pointer',
                    '&:hover': { boxShadow: 4 }
                  }}
                  onClick={() => setSelectedTarget(target)}
                >
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                      <Typography variant="h6" noWrap>
                        {target.name}
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip
                          size="small"
                          label={target.status}
                          color={getStatusColor(target.status) as any}
                        />
                        <Chip
                          size="small"
                          label={target.risk_level}
                          color={getRiskColor(target.risk_level) as any}
                        />
                      </Box>
                    </Box>

                    <TargetProgressGauge
                      target={target}
                      size="small"
                    />

                    <Box sx={{ mt: 2, display: 'flex', justify: 'space-between' }}>
                      <Typography variant="body2" color="text.secondary">
                        {target.team_target ? (
                          <>
                            <GroupIcon sx={{ fontSize: 16, mr: 0.5 }} />
                            Team Target
                          </>
                        ) : (
                          <>
                            <PersonIcon sx={{ fontSize: 16, mr: 0.5 }} />
                            Individual
                          </>
                        )}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {target.days_remaining} days left
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          {filteredTargets.length === 0 && (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography variant="body1" color="text.secondary">
                No targets found matching your filters.
              </Typography>
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={handleCreateTarget}
                sx={{ mt: 2 }}
              >
                Create First Target
              </Button>
            </Box>
          )}
        </TabPanel>

        <TabPanel value={activeTab} index={1}>
          {analytics && (
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <TargetTrendChart targets={filteredTargets} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TargetHeatMap targets={filteredTargets} />
              </Grid>
            </Grid>
          )}
        </TabPanel>

        <TabPanel value={activeTab} index={2}>
          <TeamPerformanceChart targets={filteredTargets.filter(t => t.team_target)} />
        </TabPanel>

        <TabPanel value={activeTab} index={3}>
          <TargetLeaderboard targets={filteredTargets.filter(t => !t.team_target)} />
        </TabPanel>

        <TabPanel value={activeTab} index={4}>
          {analytics && (
            <TargetPredictiveAnalysis targets={filteredTargets} analytics={analytics} />
          )}
        </TabPanel>
      </Paper>

      {/* Target Form Dialog */}
      {showTargetForm && (
        <TargetForm
          open={showTargetForm}
          target={editingTarget}
          onSave={handleTargetSave}
          onClose={handleTargetFormClose}
        />
      )}

      {/* Target Detail Dialog */}
      {selectedTarget && (
        <TargetDetail
          open={Boolean(selectedTarget)}
          target={selectedTarget}
          onEdit={handleEditTarget}
          onClose={() => setSelectedTarget(null)}
        />
      )}

      {/* Export Menu */}
      <Menu
        anchorEl={exportMenuAnchor}
        open={Boolean(exportMenuAnchor)}
        onClose={handleExportClose}
      >
        <MenuItem onClick={() => handleExport('pdf')} disabled={exportLoading}>
          <ListItemIcon>
            <FileDownloadIcon />
          </ListItemIcon>
          <ListItemText primary="Export as PDF" />
        </MenuItem>
        <MenuItem onClick={() => handleExport('excel')} disabled={exportLoading}>
          <ListItemIcon>
            <FileDownloadIcon />
          </ListItemIcon>
          <ListItemText primary="Export as Excel" />
        </MenuItem>
        <MenuItem onClick={() => handleExport('png')} disabled={exportLoading}>
          <ListItemIcon>
            <FileDownloadIcon />
          </ListItemIcon>
          <ListItemText primary="Export as PNG" />
        </MenuItem>
      </Menu>

      {/* Success/Error Snackbar */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={4000}
        onClose={() => setSnackbarOpen(false)}
        message={snackbarMessage}
      />
    </Box>
  );
};

export default SalesTargets;