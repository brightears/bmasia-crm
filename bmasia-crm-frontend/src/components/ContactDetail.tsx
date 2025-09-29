import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Avatar,
  Chip,
  Grid,
  Card,
  CardContent,
  IconButton,
  Divider,
  Link,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Tab,
  Tabs,
  Alert,
  CircularProgress,
  Paper,
} from '@mui/material';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
} from '@mui/lab';
import {
  Edit,
  Email,
  Phone,
  Business,
  LinkedIn,
  Person,
  Close,
  CalendarToday,
  NoteAlt,
  Handshake,
  Assignment,
  Send,
} from '@mui/icons-material';
import { Contact, Opportunity, Note } from '../types';
import ApiService from '../services/api';

interface ContactDetailProps {
  open: boolean;
  onClose: () => void;
  contact: Contact | null;
  onEdit: () => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div hidden={value !== index}>
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
};

const ContactDetail: React.FC<ContactDetailProps> = ({
  open,
  onClose,
  contact,
  onEdit,
}) => {
  const [tabValue, setTabValue] = useState(0);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open && contact) {
      loadRelatedData();
    }
  }, [open, contact]);

  const loadRelatedData = async () => {
    if (!contact) return;

    setLoading(true);
    setError('');

    try {
      // Load opportunities related to this contact's company
      const opportunitiesResponse = await ApiService.getOpportunities({
        company: contact.company,
        page_size: 100,
      });
      setOpportunities(opportunitiesResponse.results);

      // Load notes related to this contact
      const notesResponse = await ApiService.getNotes({
        contact: contact.id,
        page_size: 100,
        ordering: '-created_at',
      });
      setNotes(notesResponse.results);
    } catch (err: any) {
      console.error('Failed to load related data:', err);
      setError('Failed to load contact details');
    } finally {
      setLoading(false);
    }
  };

  const handleSendEmail = () => {
    if (contact?.email) {
      window.open(`mailto:${contact.email}`, '_blank');
    }
  };

  const handlePhoneCall = (number: string) => {
    window.open(`tel:${number}`, '_blank');
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getOpportunityStageColor = (stage: string) => {
    const stageColors: Record<string, 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error'> = {
      'Contacted': 'primary',
      'Quotation Sent': 'secondary',
      'Contract Sent': 'warning',
      'Won': 'success',
      'Lost': 'error',
    };
    return stageColors[stage] || 'default';
  };

  const getNoteTypeIcon = (type: string) => {
    switch (type) {
      case 'Meeting':
        return <CalendarToday />;
      case 'Call':
        return <Phone />;
      case 'Email':
        return <Email />;
      default:
        return <NoteAlt />;
    }
  };

  if (!contact) {
    return null;
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { minHeight: '80vh' }
      }}
    >
      <DialogTitle sx={{ pb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Avatar sx={{ mr: 2, bgcolor: 'primary.main', width: 56, height: 56 }}>
              {contact.first_name[0]}{contact.last_name[0]}
            </Avatar>
            <Box>
              <Typography variant="h5" component="div">
                {contact.name}
              </Typography>
              <Typography variant="body1" color="text.secondary">
                {contact.title && `${contact.title} • `}{contact.company_name}
              </Typography>
            </Box>
          </Box>
          <IconButton onClick={onClose}>
            <Close />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 0 }}>
        {error && (
          <Alert severity="error" sx={{ m: 2 }}>
            {error}
          </Alert>
        )}

        <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
          <Tab label="Overview" />
          <Tab label="Opportunities" />
          <Tab label="Activity" />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          <Grid container spacing={3}>
            {/* Contact Information */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Contact Information
                  </Typography>
                  <List>
                    <ListItem>
                      <ListItemIcon>
                        <Email />
                      </ListItemIcon>
                      <ListItemText
                        primary="Email"
                        secondary={
                          <Link
                            component="button"
                            variant="body2"
                            onClick={handleSendEmail}
                            sx={{ textAlign: 'left' }}
                          >
                            {contact.email}
                          </Link>
                        }
                      />
                    </ListItem>
                    {contact.phone && (
                      <ListItem>
                        <ListItemIcon>
                          <Phone />
                        </ListItemIcon>
                        <ListItemText
                          primary="Phone"
                          secondary={
                            <Link
                              component="button"
                              variant="body2"
                              onClick={() => handlePhoneCall(contact.phone!)}
                              sx={{ textAlign: 'left' }}
                            >
                              {contact.phone}
                            </Link>
                          }
                        />
                      </ListItem>
                    )}
                    {contact.mobile && (
                      <ListItem>
                        <ListItemIcon>
                          <Phone />
                        </ListItemIcon>
                        <ListItemText
                          primary="Mobile"
                          secondary={
                            <Link
                              component="button"
                              variant="body2"
                              onClick={() => handlePhoneCall(contact.mobile!)}
                              sx={{ textAlign: 'left' }}
                            >
                              {contact.mobile}
                            </Link>
                          }
                        />
                      </ListItem>
                    )}
                    {contact.linkedin_url && (
                      <ListItem>
                        <ListItemIcon>
                          <LinkedIn />
                        </ListItemIcon>
                        <ListItemText
                          primary="LinkedIn"
                          secondary={
                            <Link
                              href={contact.linkedin_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              variant="body2"
                            >
                              View Profile
                            </Link>
                          }
                        />
                      </ListItem>
                    )}
                    <ListItem>
                      <ListItemIcon>
                        <Business />
                      </ListItemIcon>
                      <ListItemText
                        primary="Company"
                        secondary={contact.company_name}
                      />
                    </ListItem>
                    {contact.department && (
                      <ListItem>
                        <ListItemIcon>
                          <Person />
                        </ListItemIcon>
                        <ListItemText
                          primary="Department"
                          secondary={contact.department}
                        />
                      </ListItem>
                    )}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            {/* Contact Details */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Contact Details
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Status
                    </Typography>
                    <Chip
                      label={contact.status}
                      color={contact.status === 'Active' ? 'success' : 'default'}
                      size="small"
                    />
                  </Box>
                  {contact.is_decision_maker && (
                    <Box sx={{ mb: 2 }}>
                      <Chip
                        label="Decision Maker"
                        color="primary"
                        size="small"
                      />
                    </Box>
                  )}
                  {contact.preferred_contact_method && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Preferred Contact Method
                      </Typography>
                      <Typography variant="body2">
                        {contact.preferred_contact_method}
                      </Typography>
                    </Box>
                  )}
                  {contact.last_contacted && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Last Contacted
                      </Typography>
                      <Typography variant="body2">
                        {formatDate(contact.last_contacted)}
                      </Typography>
                    </Box>
                  )}
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Created
                    </Typography>
                    <Typography variant="body2">
                      {formatDate(contact.created_at)}
                    </Typography>
                  </Box>
                  {contact.notes && (
                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Notes
                      </Typography>
                      <Paper sx={{ p: 2, backgroundColor: 'grey.50' }}>
                        <Typography variant="body2" style={{ whiteSpace: 'pre-wrap' }}>
                          {contact.notes}
                        </Typography>
                      </Paper>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : opportunities.length === 0 ? (
            <Box sx={{ textAlign: 'center', p: 4 }}>
              <Handshake sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary">
                No opportunities found
              </Typography>
              <Typography variant="body2" color="text.secondary">
                No opportunities are associated with {contact.company_name}
              </Typography>
            </Box>
          ) : (
            <List>
              {opportunities.map((opportunity, index) => (
                <React.Fragment key={opportunity.id}>
                  <ListItem alignItems="flex-start">
                    <ListItemIcon>
                      <Handshake />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                          <Typography variant="body1" fontWeight="medium">
                            {opportunity.name}
                          </Typography>
                          <Chip
                            label={opportunity.stage}
                            size="small"
                            color={getOpportunityStageColor(opportunity.stage)}
                          />
                        </Box>
                      }
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary">
                            Value: ${opportunity.expected_value?.toLocaleString() || 'Not specified'}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            Owner: {opportunity.owner_name}
                          </Typography>
                          {opportunity.expected_close_date && (
                            <Typography variant="body2" color="text.secondary">
                              Expected Close: {formatDate(opportunity.expected_close_date)}
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                  {index < opportunities.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : notes.length === 0 ? (
            <Box sx={{ textAlign: 'center', p: 4 }}>
              <Assignment sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary">
                No activity found
              </Typography>
              <Typography variant="body2" color="text.secondary">
                No notes or activities have been recorded for this contact
              </Typography>
            </Box>
          ) : (
            <Timeline>
              {notes.map((note) => (
                <TimelineItem key={note.id}>
                  <TimelineSeparator>
                    <TimelineDot color="primary">
                      {getNoteTypeIcon(note.note_type)}
                    </TimelineDot>
                    <TimelineConnector />
                  </TimelineSeparator>
                  <TimelineContent>
                    <Paper sx={{ p: 2, mb: 2 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                        <Typography variant="body1" fontWeight="medium">
                          {note.title || note.note_type}
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Chip
                            label={note.note_type}
                            size="small"
                            variant="outlined"
                          />
                          <Chip
                            label={note.priority}
                            size="small"
                            color={note.priority === 'High' || note.priority === 'Urgent' ? 'error' : 'default'}
                          />
                        </Box>
                      </Box>
                      <Typography variant="body2" color="text.secondary" paragraph>
                        {note.text}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {note.author_name} • {formatDate(note.created_at)}
                      </Typography>
                    </Paper>
                  </TimelineContent>
                </TimelineItem>
              ))}
            </Timeline>
          )}
        </TabPanel>
      </DialogContent>

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button
          onClick={handleSendEmail}
          startIcon={<Send />}
          disabled={!contact.email}
        >
          Send Email
        </Button>
        <Button
          onClick={onEdit}
          variant="contained"
          startIcon={<Edit />}
        >
          Edit Contact
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ContactDetail;