import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Breadcrumbs,
  Link,
  Snackbar,
  Autocomplete,
  Chip,
} from '@mui/material';
import { NavigateNext, ArrowBack, Send, Schedule, Close } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import ApiService from '../services/api';
import AudienceSelector from '../components/AudienceSelector';
import { EmailTemplate } from '../types';

const steps = ['Campaign Basics', 'Email Content', 'Select Audience', 'Schedule', 'Review & Send'];

const CampaignCreate: React.FC = () => {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Form data
  const [name, setName] = useState('');
  const [campaignType, setCampaignType] = useState<string>('newsletter');
  const [subject, setSubject] = useState('');
  const [emailBody, setEmailBody] = useState('');
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([]);
  const [scheduledDate, setScheduledDate] = useState<Date | null>(null);
  const [sendImmediately, setSendImmediately] = useState(true);

  // Template selection
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);

  // Fetch templates on mount
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        setTemplatesLoading(true);
        const response = await ApiService.getEmailTemplates({ is_active: true });
        setTemplates(response.results || []);
      } catch (error) {
        console.error('Failed to load templates:', error);
      } finally {
        setTemplatesLoading(false);
      }
    };
    fetchTemplates();
  }, []);

  // Auto-fill subject and body when template is selected
  useEffect(() => {
    if (selectedTemplate) {
      setSubject(selectedTemplate.subject || '');
      setEmailBody(selectedTemplate.body_text || '');
    }
  }, [selectedTemplate]);

  const handleNext = () => {
    // Validate current step
    if (activeStep === 0 && (!name || !campaignType || !subject)) {
      setError('Please fill in all required fields');
      return;
    }
    if (activeStep === 1 && !emailBody) {
      setError('Please enter email content');
      return;
    }
    if (activeStep === 2 && selectedContactIds.length === 0) {
      setError('Please select at least one recipient');
      return;
    }
    if (activeStep === 3 && !sendImmediately && !scheduledDate) {
      setError('Please select a scheduled date or choose to send immediately');
      return;
    }

    setError('');
    setActiveStep((prevActiveStep) => prevActiveStep + 1);
  };

  const handleBack = () => {
    setError('');
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setError('');

      const campaignData = {
        name,
        campaign_type: campaignType,
        subject,
        target_audience: { custom_body: emailBody },
        template: selectedTemplate?.id || null,
        send_immediately: sendImmediately,
        scheduled_send_date: sendImmediately ? null : scheduledDate?.toISOString(),
        contact_ids: selectedContactIds,
      };

      console.log('Creating campaign:', campaignData);
      const createdCampaign = await ApiService.createCampaign(campaignData);
      console.log('Campaign created:', createdCampaign);

      setSuccessMessage('Campaign created successfully!');

      // Navigate to campaign detail page after a short delay
      setTimeout(() => {
        navigate(`/campaigns/${createdCampaign.id}`);
      }, 1500);
    } catch (err: any) {
      console.error('Campaign creation error:', err);
      setError(`Failed to create campaign: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Campaign Basics
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Define the basic information for your email campaign
            </Typography>

            <TextField
              fullWidth
              required
              label="Campaign Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Monthly Newsletter - January 2025"
              sx={{ mb: 3 }}
            />

            <Autocomplete
              fullWidth
              options={templates}
              value={selectedTemplate}
              onChange={(event, newValue) => setSelectedTemplate(newValue)}
              groupBy={(option) => option.template_type_display || option.template_type}
              getOptionLabel={(option) => `${option.name} (${option.template_type_display || option.template_type})`}
              loading={templatesLoading}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Email Template (Optional)"
                  helperText="Select a template to auto-fill subject and body"
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {templatesLoading ? <CircularProgress color="inherit" size={20} /> : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
              sx={{ mb: 3 }}
            />

            <FormControl fullWidth required sx={{ mb: 3 }}>
              <InputLabel>Campaign Type</InputLabel>
              <Select
                value={campaignType}
                label="Campaign Type"
                onChange={(e) => setCampaignType(e.target.value)}
              >
                <MenuItem value="renewal">Renewal Reminder</MenuItem>
                <MenuItem value="payment">Payment Reminder</MenuItem>
                <MenuItem value="quarterly">Quarterly Update</MenuItem>
                <MenuItem value="newsletter">Newsletter</MenuItem>
                <MenuItem value="promotion">Promotion</MenuItem>
                <MenuItem value="onboarding">Onboarding</MenuItem>
                <MenuItem value="engagement">Engagement</MenuItem>
              </Select>
            </FormControl>

            {selectedTemplate && (
              <Box sx={{ mb: 2 }}>
                <Chip
                  label={`Template: ${selectedTemplate.name}`}
                  onDelete={() => setSelectedTemplate(null)}
                  deleteIcon={<Close />}
                  sx={{
                    backgroundColor: '#FFA500',
                    color: 'white',
                    '& .MuiChip-deleteIcon': {
                      color: 'white',
                      '&:hover': {
                        color: 'rgba(255, 255, 255, 0.7)',
                      },
                    },
                  }}
                />
              </Box>
            )}

            <TextField
              fullWidth
              required
              label="Email Subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g., Your monthly music update from BMAsia"
              helperText="This will be the email subject line"
              sx={{ mb: 2 }}
            />
          </Box>
        );

      case 1:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Email Content
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Write the body of your email. You can use plain text or include formatting.
            </Typography>

            <TextField
              fullWidth
              required
              multiline
              rows={15}
              label="Email Body"
              value={emailBody}
              onChange={(e) => setEmailBody(e.target.value)}
              placeholder="Enter your email content here..."
              helperText="Tip: Keep your message clear and concise"
            />
          </Box>
        );

      case 2:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Select Audience
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose which contacts will receive this campaign
            </Typography>

            <AudienceSelector
              selectedContactIds={selectedContactIds}
              onSelectionChange={setSelectedContactIds}
            />
          </Box>
        );

      case 3:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Schedule Campaign
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose when to send this campaign
            </Typography>

            <Box sx={{ mb: 3 }}>
              <Button
                variant={sendImmediately ? 'contained' : 'outlined'}
                onClick={() => setSendImmediately(true)}
                sx={{
                  mr: 2,
                  backgroundColor: sendImmediately ? '#FFA500' : 'transparent',
                  '&:hover': { backgroundColor: sendImmediately ? '#FF8C00' : 'transparent' },
                }}
              >
                Send Immediately
              </Button>
              <Button
                variant={!sendImmediately ? 'contained' : 'outlined'}
                onClick={() => setSendImmediately(false)}
                sx={{
                  backgroundColor: !sendImmediately ? '#FFA500' : 'transparent',
                  '&:hover': { backgroundColor: !sendImmediately ? '#FF8C00' : 'transparent' },
                }}
              >
                Schedule for Later
              </Button>
            </Box>

            {!sendImmediately && (
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <DateTimePicker
                  label="Scheduled Send Date"
                  value={scheduledDate}
                  onChange={(newValue) => setScheduledDate(newValue)}
                  minDateTime={new Date()}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      required: true,
                      helperText: 'Select when this campaign should be sent',
                    },
                  }}
                />
              </LocalizationProvider>
            )}
          </Box>
        );

      case 4:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Review & Send
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Review your campaign details before sending
            </Typography>

            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Campaign Name
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                {name}
              </Typography>

              <Typography variant="subtitle2" color="text.secondary">
                Type
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                {campaignType}
              </Typography>

              {selectedTemplate && (
                <>
                  <Typography variant="subtitle2" color="text.secondary">
                    Template
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {selectedTemplate.name}
                  </Typography>
                </>
              )}

              <Typography variant="subtitle2" color="text.secondary">
                Subject
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                {subject}
              </Typography>

              <Typography variant="subtitle2" color="text.secondary">
                Recipients
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                {selectedContactIds.length} contacts
              </Typography>

              <Typography variant="subtitle2" color="text.secondary">
                Schedule
              </Typography>
              <Typography variant="body1">
                {sendImmediately
                  ? 'Send immediately after creation'
                  : `Scheduled for ${scheduledDate?.toLocaleString()}`}
              </Typography>
            </Paper>

            <Alert severity="info">
              {sendImmediately
                ? 'This campaign will be sent immediately to all recipients.'
                : 'This campaign will be sent at the scheduled time.'}
            </Alert>
          </Box>
        );

      default:
        return null;
    }
  };

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
        <Typography color="text.primary">New Campaign</Typography>
      </Breadcrumbs>

      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate('/campaigns')}
          sx={{ mr: 2 }}
        >
          Back
        </Button>
        <Typography variant="h4" component="h1">
          Create New Campaign
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        <Box sx={{ minHeight: 400 }}>{renderStepContent(activeStep)}</Box>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
          <Button disabled={activeStep === 0} onClick={handleBack}>
            Back
          </Button>
          <Box>
            {activeStep === steps.length - 1 ? (
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={loading}
                startIcon={loading ? <CircularProgress size={16} /> : sendImmediately ? <Send /> : <Schedule />}
                sx={{
                  backgroundColor: '#FFA500',
                  '&:hover': { backgroundColor: '#FF8C00' },
                }}
              >
                {loading ? 'Creating...' : sendImmediately ? 'Create & Send' : 'Create Campaign'}
              </Button>
            ) : (
              <Button
                variant="contained"
                onClick={handleNext}
                endIcon={<NavigateNext />}
                sx={{
                  backgroundColor: '#FFA500',
                  '&:hover': { backgroundColor: '#FF8C00' },
                }}
              >
                Next
              </Button>
            )}
          </Box>
        </Box>
      </Paper>

      <Snackbar
        open={!!successMessage}
        autoHideDuration={3000}
        onClose={() => setSuccessMessage('')}
        message={successMessage}
      />
    </Box>
  );
};

export default CampaignCreate;
