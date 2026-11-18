import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Button,
  Card,
  CardContent,
  Divider,
} from '@mui/material';
import { GridLegacy as Grid } from '@mui/material';
import {
  Add as AddIcon,
  Timeline as TimelineIcon,
} from '@mui/icons-material';
import { OpportunityActivity, Opportunity } from '../types';
import ActivityForm from '../components/ActivityForm';
import ActivityTimeline from '../components/ActivityTimeline';
import QuickActivity from '../components/QuickActivity';
import ApiService from '../services/api';

const ActivityDemo: React.FC = () => {
  const [activityFormOpen, setActivityFormOpen] = useState(false);
  const [activities, setActivities] = useState<OpportunityActivity[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);

      // Load opportunities and activities
      const [opportunitiesResponse, activitiesResponse] = await Promise.all([
        ApiService.getOpportunities({ page_size: 10 }),
        ApiService.getOpportunityActivities({ page_size: 20 })
      ]);

      setOpportunities(opportunitiesResponse.results);
      setActivities(activitiesResponse.results);

      // Set first opportunity as selected for demo
      if (opportunitiesResponse.results.length > 0) {
        setSelectedOpportunity(opportunitiesResponse.results[0]);
      }
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleActivityCreated = (activity: OpportunityActivity) => {
    setActivities(prev => [activity, ...prev]);
  };

  const handleEditActivity = (activity: OpportunityActivity) => {
    console.log('Edit activity:', activity);
    // Could open activity form in edit mode
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        Activity Logging System Demo
      </Typography>

      <Typography variant="body1" color="text.secondary" paragraph>
        This demo showcases the new Activity Logging System integrated with the BMAsia CRM.
        The system includes activity forms, timeline views, and quick action widgets.
      </Typography>

      <Grid container spacing={4}>
        {/* Activity Form Demo */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: 'fit-content' }}>
            <Typography variant="h6" gutterBottom>
              Activity Form
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Quick activity logging modal with support for all activity types.
            </Typography>

            <Box sx={{ mb: 2 }}>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => setActivityFormOpen(true)}
                sx={{ mb: 1, mr: 1 }}
              >
                Log Activity
              </Button>

              {selectedOpportunity && (
                <Button
                  variant="outlined"
                  startIcon={<AddIcon />}
                  onClick={() => setActivityFormOpen(true)}
                >
                  Log for {selectedOpportunity.name}
                </Button>
              )}
            </Box>

            <Typography variant="body2" color="text.secondary">
              Features:
            </Typography>
            <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
              <li>9 activity types with custom icons</li>
              <li>Date/time picker with duration tracking</li>
              <li>Contact association</li>
              <li>Follow-up scheduling</li>
              <li>Rich text descriptions</li>
            </ul>
          </Paper>
        </Grid>

        {/* Activity Timeline Demo */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: 'fit-content' }}>
            <Typography variant="h6" gutterBottom>
              Activity Timeline
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Visual timeline of all activities with filtering and search.
            </Typography>

            <Typography variant="body2" color="text.secondary">
              Features:
            </Typography>
            <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
              <li>Visual timeline with activity icons</li>
              <li>Expandable activity details</li>
              <li>Filter by type, date, and status</li>
              <li>Compact and full view modes</li>
              <li>Inline editing and deletion</li>
            </ul>
          </Paper>
        </Grid>

        {/* Opportunity Integration */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Opportunity Integration
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Activities are fully integrated with opportunities and contacts.
            </Typography>

            {selectedOpportunity && (
              <Card variant="outlined" sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="subtitle1">
                    {selectedOpportunity.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {selectedOpportunity.company_name} • {selectedOpportunity.stage}
                  </Typography>
                  <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                    Recent activities: {selectedOpportunity.recent_activities?.length || 0}
                  </Typography>
                </CardContent>
              </Card>
            )}

            <Typography variant="body2" color="text.secondary">
              Integration features:
            </Typography>
            <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
              <li>Activity indicators on opportunity cards</li>
              <li>Last activity date display</li>
              <li>Recent activities in opportunity forms</li>
              <li>Contact-specific activity filtering</li>
            </ul>
          </Paper>
        </Grid>

        {/* Quick Activity Widget */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Quick Activity Widget
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Floating action button for quick activity logging from anywhere in the app.
            </Typography>

            <Typography variant="body2" color="text.secondary">
              Widget features:
            </Typography>
            <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
              <li>Speed dial with activity type shortcuts</li>
              <li>Recent activities dropdown</li>
              <li>Configurable position</li>
              <li>Mobile-responsive design</li>
              <li>Real-time activity updates</li>
            </ul>

            <Typography variant="body2" color="info.main" sx={{ mt: 2 }}>
              Check the bottom-right corner to see the Quick Activity widget in action!
            </Typography>
          </Paper>
        </Grid>

        {/* Activity Timeline Display */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h6">
                Recent Activities Timeline
              </Typography>
              <Button
                variant="outlined"
                startIcon={<TimelineIcon />}
                onClick={loadData}
                disabled={loading}
              >
                Refresh
              </Button>
            </Box>

            <ActivityTimeline
              activities={activities}
              onEditActivity={handleEditActivity}
              onRefresh={loadData}
              showFilters={true}
              compact={false}
            />
          </Paper>
        </Grid>
      </Grid>

      {/* Activity Form */}
      <ActivityForm
        open={activityFormOpen}
        onClose={() => setActivityFormOpen(false)}
        onSave={handleActivityCreated}
        opportunity={selectedOpportunity}
        mode="create"
      />

      {/* Quick Activity Widget */}
      <QuickActivity
        position="bottom-right"
        onActivityCreated={handleActivityCreated}
        showRecentActivities={true}
        maxRecentActivities={5}
      />
    </Container>
  );
};

export default ActivityDemo;