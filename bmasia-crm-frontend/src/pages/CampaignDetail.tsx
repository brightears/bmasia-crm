import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Chip,
  Alert,
  CircularProgress,
  Breadcrumbs,
  Link,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Divider,
  Card,
  CardContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Snackbar,
  Menu,
  MenuItem,
  IconButton,
} from '@mui/material';
import {
  ArrowBack,
  Send,
  Schedule,
  Pause,
  PlayArrow,
  Edit,
  MoreVert,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { EmailCampaignDetail, CampaignRecipient } from '../types';
import ApiService from '../services/api';
import CampaignAnalytics from '../components/CampaignAnalytics';

const getStatusColor = (
  status: string
): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
  switch (status) {
    case 'draft':
      return 'default';
    case 'scheduled':
      return 'info';
    case 'sending':
      return 'warning';
    case 'sent':
      return 'success';
    case 'paused':
      return 'warning';
    case 'cancelled':
      return 'error';
    default:
      return 'default';
  }
};

const getRecipientStatusColor = (
  status: string
): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
  switch (status) {
    case 'pending':
      return 'default';
    case 'sent':
      return 'info';
    case 'delivered':
      return 'success';
    case 'opened':
      return 'primary';
    case 'clicked':
      return 'secondary';
    case 'bounced':
      return 'error';
    case 'failed':
      return 'error';
    case 'unsubscribed':
      return 'warning';
    default:
      return 'default';
  }
};

const CampaignDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<EmailCampaignDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  // Recipients pagination
  const [recipientsPage, setRecipientsPage] = useState(0);
  const [recipientsRowsPerPage, setRecipientsRowsPerPage] = useState(25);

  // Test email dialog
  const [testDialogOpen, setTestDialogOpen] = useState(false);
  const [testEmails, setTestEmails] = useState('');

  // Schedule dialog
  const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false);
  const [scheduledDate, setScheduledDate] = useState<string>('');

  // More actions menu
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  useEffect(() => {
    if (id) {
      loadCampaignData();
    }
  }, [id]);

  const loadCampaignData = async () => {
    if (!id) return;

    try {
      setLoading(true);
      setError('');
      const campaignData = await ApiService.getCampaign(id);
      setCampaign(campaignData);
    } catch (err: any) {
      console.error('Campaign detail error:', err);
      setError('Failed to load campaign details');
    } finally {
      setLoading(false);
    }
  };

  const handleSendNow = async () => {
    if (!id || !campaign) return;

    try {
      setActionLoading(true);
      await ApiService.sendCampaign(id);
      setSuccessMessage('Campaign is being sent!');
      loadCampaignData();
    } catch (err: any) {
      setError(`Failed to send campaign: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handlePause = async () => {
    if (!id) return;

    try {
      setActionLoading(true);
      await ApiService.pauseCampaign(id);
      setSuccessMessage('Campaign paused successfully');
      loadCampaignData();
    } catch (err: any) {
      setError(`Failed to pause campaign: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async () => {
    if (!id) return;

    try {
      setActionLoading(true);
      await ApiService.resumeCampaign(id);
      setSuccessMessage('Campaign resumed successfully');
      loadCampaignData();
    } catch (err: any) {
      setError(`Failed to resume campaign: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSchedule = async () => {
    if (!id || !scheduledDate) return;

    try {
      setActionLoading(true);
      await ApiService.scheduleCampaign(id, scheduledDate);
      setSuccessMessage('Campaign scheduled successfully');
      setScheduleDialogOpen(false);
      loadCampaignData();
    } catch (err: any) {
      setError(`Failed to schedule campaign: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendTest = async () => {
    if (!id || !testEmails) return;

    try {
      setActionLoading(true);
      const emailList = testEmails.split(',').map((e) => e.trim());
      await ApiService.testCampaign(id, emailList);
      setSuccessMessage('Test email sent successfully');
      setTestDialogOpen(false);
      setTestEmails('');
    } catch (err: any) {
      setError(`Failed to send test email: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRecipientsPageChange = (event: unknown, newPage: number) => {
    setRecipientsPage(newPage);
  };

  const handleRecipientsRowsPerPageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRecipientsRowsPerPage(parseInt(event.target.value, 10));
    setRecipientsPage(0);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!campaign) {
    return (
      <Alert severity="error">
        Campaign not found
      </Alert>
    );
  }

  const paginatedRecipients = campaign.recipients.slice(
    recipientsPage * recipientsRowsPerPage,
    recipientsPage * recipientsRowsPerPage + recipientsRowsPerPage
  );

  return (
    <Box>
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          color="inherit"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate('/campaigns');
          }}
        >
          Campaigns
        </Link>
        <Typography color="text.primary">{campaign.name}</Typography>
      </Breadcrumbs>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Button
            startIcon={<ArrowBack />}
            onClick={() => navigate('/campaigns')}
          >
            Back
          </Button>
          <Box>
            <Typography variant="h4" component="h1">
              {campaign.name}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
              <Chip
                label={campaign.status_display}
                size="small"
                color={getStatusColor(campaign.status)}
              />
              <Chip
                label={campaign.campaign_type_display}
                size="small"
                variant="outlined"
              />
            </Box>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          {campaign.status === 'draft' && (
            <>
              <Button
                variant="outlined"
                startIcon={<Send />}
                onClick={() => setTestDialogOpen(true)}
              >
                Send Test
              </Button>
              <Button
                variant="outlined"
                startIcon={<Schedule />}
                onClick={() => setScheduleDialogOpen(true)}
              >
                Schedule
              </Button>
              <Button
                variant="contained"
                startIcon={<Send />}
                onClick={handleSendNow}
                disabled={actionLoading}
                sx={{
                  backgroundColor: '#FFA500',
                  '&:hover': { backgroundColor: '#FF8C00' },
                }}
              >
                Send Now
              </Button>
            </>
          )}

          {campaign.status === 'scheduled' && (
            <>
              <Button
                variant="outlined"
                startIcon={<Pause />}
                onClick={handlePause}
                disabled={actionLoading}
              >
                Pause
              </Button>
              <Button
                variant="outlined"
                startIcon={<Edit />}
                onClick={() => setScheduleDialogOpen(true)}
              >
                Edit Schedule
              </Button>
            </>
          )}

          {campaign.status === 'paused' && (
            <Button
              variant="contained"
              startIcon={<PlayArrow />}
              onClick={handleResume}
              disabled={actionLoading}
              sx={{
                backgroundColor: '#FFA500',
                '&:hover': { backgroundColor: '#FF8C00' },
              }}
            >
              Resume
            </Button>
          )}

          <IconButton onClick={(e) => setAnchorEl(e.currentTarget)}>
            <MoreVert />
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
          >
            <MenuItem onClick={() => { /* TODO: Implement edit */ }}>Edit Campaign</MenuItem>
            <MenuItem onClick={() => { /* TODO: Implement clone */ }}>Clone Campaign</MenuItem>
            <MenuItem onClick={() => { /* TODO: Implement delete */ }}>Delete Campaign</MenuItem>
          </Menu>
        </Box>
      </Box>

      {/* Analytics */}
      {campaign.status === 'sent' && (
        <Box sx={{ mb: 3 }}>
          <CampaignAnalytics campaign={campaign} />
        </Box>
      )}

      {/* Campaign Details */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Campaign Details
        </Typography>
        <Divider sx={{ mb: 2 }} />

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Subject
            </Typography>
            <Typography variant="body1" sx={{ mb: 2 }}>
              {campaign.subject}
            </Typography>

            <Typography variant="subtitle2" color="text.secondary">
              Sender Email
            </Typography>
            <Typography variant="body1" sx={{ mb: 2 }}>
              {campaign.sender_email}
            </Typography>

            <Typography variant="subtitle2" color="text.secondary">
              Recipients Count
            </Typography>
            <Typography variant="body1" sx={{ mb: 2 }}>
              {campaign.recipients_count}
            </Typography>
          </Box>

          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Created
            </Typography>
            <Typography variant="body1" sx={{ mb: 2 }}>
              {new Date(campaign.created_at).toLocaleString()}
            </Typography>

            {campaign.scheduled_send_date && (
              <>
                <Typography variant="subtitle2" color="text.secondary">
                  Scheduled Send Date
                </Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {new Date(campaign.scheduled_send_date).toLocaleString()}
                </Typography>
              </>
            )}

            {campaign.actual_send_date && (
              <>
                <Typography variant="subtitle2" color="text.secondary">
                  Actual Send Date
                </Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {new Date(campaign.actual_send_date).toLocaleString()}
                </Typography>
              </>
            )}
          </Box>
        </Box>

        <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2 }}>
          Email Body
        </Typography>
        <Paper variant="outlined" sx={{ p: 2, mt: 1, whiteSpace: 'pre-wrap', backgroundColor: '#f5f5f5' }}>
          {campaign.target_audience?.custom_body || 'No email body available'}
        </Paper>
      </Paper>

      {/* Recipients Table */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Recipients ({campaign.recipients.length})
        </Typography>
        <Divider sx={{ mb: 2 }} />

        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Contact</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Company</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Sent</TableCell>
                <TableCell>Opened</TableCell>
                <TableCell>Clicked</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedRecipients.map((recipient) => (
                <TableRow key={recipient.id}>
                  <TableCell>{recipient.contact_name}</TableCell>
                  <TableCell>{recipient.contact_email}</TableCell>
                  <TableCell>{recipient.contact_company}</TableCell>
                  <TableCell>
                    <Chip
                      label={recipient.status_display}
                      size="small"
                      color={getRecipientStatusColor(recipient.status)}
                    />
                  </TableCell>
                  <TableCell>
                    {recipient.sent_at ? new Date(recipient.sent_at).toLocaleString() : '-'}
                  </TableCell>
                  <TableCell>
                    {recipient.opened_at ? new Date(recipient.opened_at).toLocaleString() : '-'}
                  </TableCell>
                  <TableCell>
                    {recipient.clicked_at ? new Date(recipient.clicked_at).toLocaleString() : '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            rowsPerPageOptions={[10, 25, 50, 100]}
            component="div"
            count={campaign.recipients.length}
            rowsPerPage={recipientsRowsPerPage}
            page={recipientsPage}
            onPageChange={handleRecipientsPageChange}
            onRowsPerPageChange={handleRecipientsRowsPerPageChange}
          />
        </TableContainer>
      </Paper>

      {/* Test Email Dialog */}
      <Dialog open={testDialogOpen} onClose={() => setTestDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Send Test Email</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Test Email Addresses"
            value={testEmails}
            onChange={(e) => setTestEmails(e.target.value)}
            placeholder="email1@example.com, email2@example.com"
            helperText="Separate multiple emails with commas"
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTestDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleSendTest}
            variant="contained"
            disabled={actionLoading || !testEmails}
            sx={{
              backgroundColor: '#FFA500',
              '&:hover': { backgroundColor: '#FF8C00' },
            }}
          >
            Send Test
          </Button>
        </DialogActions>
      </Dialog>

      {/* Schedule Dialog */}
      <Dialog open={scheduleDialogOpen} onClose={() => setScheduleDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Schedule Campaign</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            type="datetime-local"
            label="Scheduled Send Date"
            value={scheduledDate}
            onChange={(e) => setScheduledDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setScheduleDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleSchedule}
            variant="contained"
            disabled={actionLoading || !scheduledDate}
            sx={{
              backgroundColor: '#FFA500',
              '&:hover': { backgroundColor: '#FF8C00' },
            }}
          >
            Schedule
          </Button>
        </DialogActions>
      </Dialog>

      {/* Success Snackbar */}
      <Snackbar
        open={!!successMessage}
        autoHideDuration={3000}
        onClose={() => setSuccessMessage('')}
        message={successMessage}
      />
    </Box>
  );
};

export default CampaignDetail;
