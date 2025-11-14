import React, { useState, useEffect } from 'react';
import {
  Container,
  Paper,
  Typography,
  Box,
  Stack,
  Card,
  CardContent,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Checkbox,
  Alert,
  CircularProgress,
  Link,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Schedule as ScheduleIcon,
  PlayArrow as PlayArrowIcon,
  Email as EmailIcon,
  OpenInNew as OpenInNewIcon,
} from '@mui/icons-material';
import apiService, { AutomationStatus, TestRunResult, AutomatedEmail } from '../services/api';

const Settings: React.FC = () => {
  const [status, setStatus] = useState<AutomationStatus | null>(null);
  const [recentEmails, setRecentEmails] = useState<AutomatedEmail[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningTest, setRunningTest] = useState(false);
  const [selectedType, setSelectedType] = useState<string>('all');
  const [dryRun, setDryRun] = useState<boolean>(true);
  const [testResult, setTestResult] = useState<TestRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [statusData, emailsData] = await Promise.all([
        apiService.getAutomationStatus(),
        apiService.getRecentAutomatedEmails(),
      ]);
      setStatus(statusData);
      setRecentEmails(emailsData);
    } catch (err: any) {
      console.error('Failed to fetch automation data:', err);
      setError(err.response?.data?.message || 'Failed to load automation data');
    } finally {
      setLoading(false);
    }
  };

  const handleTestRun = async () => {
    try {
      setRunningTest(true);
      setTestResult(null);
      setError(null);
      const result = await apiService.testRunAutomation(selectedType, dryRun);
      setTestResult(result);
      // Refresh data after successful run
      if (result.success && !dryRun) {
        await fetchData();
      }
    } catch (err: any) {
      console.error('Failed to run test:', err);
      setError(err.response?.data?.error || 'Failed to run automation test');
    } finally {
      setRunningTest(false);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = (statusCode: string) => {
    switch (statusCode) {
      case 'sent':
        return 'success';
      case 'failed':
        return 'error';
      case 'pending':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getTypeColor = (typeCode: string) => {
    switch (typeCode) {
      case 'renewal':
        return 'primary';
      case 'payment':
        return 'error';
      case 'quarterly':
        return 'info';
      default:
        return 'default';
    }
  };

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        System Settings
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Stack spacing={3}>
        {/* Status and Statistics Row */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
          {/* Automation Status Card */}
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <EmailIcon sx={{ mr: 1, color: '#FFA500' }} />
                <Typography variant="h6">Email Automation</Typography>
              </Box>

              <Box mb={2}>
                <Chip
                  icon={status?.enabled ? <CheckCircleIcon /> : <CancelIcon />}
                  label={status?.enabled ? 'Active' : 'Inactive'}
                  color={status?.enabled ? 'success' : 'default'}
                  sx={{ fontWeight: 'bold' }}
                />
              </Box>

              <Box mb={1}>
                <Typography variant="body2" color="text.secondary">
                  Schedule
                </Typography>
                <Typography variant="body1" sx={{ display: 'flex', alignItems: 'center' }}>
                  <ScheduleIcon sx={{ mr: 1, fontSize: '1.2rem' }} />
                  {status?.cron_description}
                </Typography>
              </Box>

              <Box mb={1}>
                <Typography variant="body2" color="text.secondary">
                  Last Run
                </Typography>
                <Typography variant="body1">
                  {formatDate(status?.last_run || null)}
                </Typography>
              </Box>

              <Box>
                <Typography variant="body2" color="text.secondary">
                  Next Scheduled Run
                </Typography>
                <Typography variant="body1">
                  {formatDate(status?.next_run || null)}
                </Typography>
              </Box>
            </CardContent>
          </Card>

          {/* Statistics Card */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Last 7 Days Statistics
              </Typography>

              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                <Box>
                  <Paper elevation={0} sx={{ p: 2, bgcolor: '#f5f5f5' }}>
                    <Typography variant="body2" color="text.secondary">
                      Renewal Reminders
                    </Typography>
                    <Typography variant="h4" color="primary">
                      {status?.recent_stats.renewal_sent || 0}
                    </Typography>
                  </Paper>
                </Box>

                <Box>
                  <Paper elevation={0} sx={{ p: 2, bgcolor: '#f5f5f5' }}>
                    <Typography variant="body2" color="text.secondary">
                      Payment Reminders
                    </Typography>
                    <Typography variant="h4" color="error">
                      {status?.recent_stats.payment_sent || 0}
                    </Typography>
                  </Paper>
                </Box>

                <Box>
                  <Paper elevation={0} sx={{ p: 2, bgcolor: '#f5f5f5' }}>
                    <Typography variant="body2" color="text.secondary">
                      Quarterly Check-ins
                    </Typography>
                    <Typography variant="h4" color="info.main">
                      {status?.recent_stats.quarterly_sent || 0}
                    </Typography>
                  </Paper>
                </Box>

                <Box>
                  <Paper elevation={0} sx={{ p: 2, bgcolor: '#f5f5f5' }}>
                    <Typography variant="body2" color="text.secondary">
                      Total Sent
                    </Typography>
                    <Typography variant="h4" sx={{ color: '#FFA500' }}>
                      {status?.recent_stats.total_sent_last_7_days || 0}
                    </Typography>
                  </Paper>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Manual Trigger Section */}
        <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Manual Trigger
              </Typography>

              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr 1fr' }, gap: 2, alignItems: 'center' }}>
                <Box>
                  <FormControl fullWidth>
                    <InputLabel>Email Type</InputLabel>
                    <Select
                      value={selectedType}
                      label="Email Type"
                      onChange={(e) => setSelectedType(e.target.value)}
                      disabled={runningTest}
                    >
                      <MenuItem value="all">All Types</MenuItem>
                      <MenuItem value="renewal">Renewal Reminders</MenuItem>
                      <MenuItem value="payment">Payment Reminders</MenuItem>
                      <MenuItem value="quarterly">Quarterly Check-ins</MenuItem>
                    </Select>
                  </FormControl>
                </Box>

                <Box>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={dryRun}
                        onChange={(e) => setDryRun(e.target.checked)}
                        disabled={runningTest}
                      />
                    }
                    label="Dry Run (test without sending)"
                  />
                </Box>

                <Box>
                  <Button
                    variant="contained"
                    startIcon={runningTest ? <CircularProgress size={20} /> : <PlayArrowIcon />}
                    onClick={handleTestRun}
                    disabled={runningTest}
                    fullWidth
                    sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
                  >
                    {runningTest ? 'Running...' : 'Run Now'}
                  </Button>
                </Box>
              </Box>

              {testResult && (
                <Box mt={2}>
                  <Alert
                    severity={testResult.success ? 'success' : 'error'}
                    onClose={() => setTestResult(null)}
                  >
                    <Typography variant="body2" fontWeight="bold">
                      {testResult.success ? 'Success!' : 'Failed'}
                      {testResult.dry_run && ' (Dry Run)'}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>
                      {testResult.output || testResult.error}
                    </Typography>
                  </Alert>
                </Box>
              )}
            </CardContent>
          </Card>

        {/* Recent Activity Table */}
        <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">Recent Automated Emails</Typography>
                <Button
                  size="small"
                  endIcon={<OpenInNewIcon />}
                  component={Link}
                  href="/admin/crm_app/emaillog/"
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{ color: '#FFA500' }}
                >
                  Advanced Settings
                </Button>
              </Box>

              {recentEmails.length === 0 ? (
                <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
                  No automated emails sent yet
                </Typography>
              ) : (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Date</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell>Company</TableCell>
                        <TableCell>Recipient</TableCell>
                        <TableCell>Subject</TableCell>
                        <TableCell>Status</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {recentEmails.map((email) => (
                        <TableRow key={email.id}>
                          <TableCell>
                            {new Date(email.date).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={email.type}
                              size="small"
                              color={getTypeColor(email.type_code) as any}
                            />
                          </TableCell>
                          <TableCell>{email.company || '-'}</TableCell>
                          <TableCell>{email.recipients}</TableCell>
                          <TableCell sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {email.subject}
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={email.status}
                              size="small"
                              color={getStatusColor(email.status_code) as any}
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </CardContent>
          </Card>
      </Stack>
    </Container>
  );
};

export default Settings;
